# Arquitectura

RepoBrain es un buscador semántico y Q&A sobre código fuente. El usuario pega
una URL de GitHub, la plataforma clona e indexa el código (tree-sitter +
embeddings + BM25) y después permite buscar en lenguaje natural o hacer
preguntas que se responden con citas `archivo:línea`.

## Vista general

```
Cliente (React) -> API (FastAPI) -> Celery/Redis -> Worker (tree-sitter + embeddings)
                                                   |
                                        Storage (SQLite + FAISS)
                                        LLM (opcional, solo en /ask)
```

## Componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| `frontend/` | React 19 + Vite + Monaco | Buscador, visor de código con línea resaltada, panel Q&A |
| `backend/app/api/` | FastAPI | Routers: repos, index, search, ask, files, health |
| `backend/app/indexing/` | tree-sitter | Parseo a fragmentos (JS/TS/Python), chunking por ~512 tokens |
| `backend/app/vector/` | bm25s + FAISS | Ranking híbrido BM25 + embeddings, fusión RRF |
| `backend/app/llm/` | multi-proveedor | Cliente `/chat/completions` (OpenAI/DeepSeek/Gemini/Ollama) + mock |
| `backend/workers/` | Celery + Redis | Tarea `index_repo` con progreso (cola asíncrona) |
| `backend/app/db/` | SQLAlchemy + SQLite | Repos, chunks |

## Flujo de datos

1. `POST /api/repos` recibe una URL pública, clona un snapshot (`--depth 1`,
   `--no-hardlinks`) en el workspace aislado y crea el `Repo` en `indexing`.
2. La UI hace *polling* de `GET /api/repos/{id}/status` (barra de progreso).
3. El worker `index_repo` lista archivos, los parsea con tree-sitter (ancla
   funciones/clases), los trocea, genera embeddings por lotes y los persiste.
4. `GET /api/repos/{id}/search` fusiona el ranking BM25 (léxico) con el coseno
   sobre embeddings (semántico) usando **RRF** y devuelve `path:línea`.
5. `POST /api/repos/{id}/ask` recupera los top-K fragmentos como contexto,
   llama al LLM y **valida cada cita contra el checkout real** para evitar
   alucinaciones.

## Decisiones de arquitectura (ADRs)

### ADR-001 — Búsqueda híbrida BM25 + embeddings con fusión RRF
- **Contexto**: la búsqueda léxica sola no entiende intención ("soft delete"),
  y la semántica sola falla en terminología exacta y corpora pequeños.
- **Decisión**: combinar **bm25s** y **coseno sobre embeddings**, fusionando los
  rankings con **Reciprocal Rank Fusion** (RRF: `1/(K + rank)`), robusto ante
  escalas de puntuación distintas y datasets pequeños (la fusión min-max previa
  degeneraba en empates de score).
- **Consecuencias**: sin puntos de calibración entre motores; ambos pesos
  configurables (`HYBRID_WEIGHTS`).

### ADR-002 — tree-sitter en lugar de AST propio
- **Contexto**: parsear múltiples lenguajes con un AST escrito a mano es un
  proyecto en sí mismo.
- **Decisión**: usar **tree-sitter** (gramáticas `python`, `javascript`,
  `typescript`, `java`, `csharp`). Los *anchors* (funciones/clases) alinean
  los chunks a estructuras reales; el prefijo del archivo
  (docstring/imports/config) se indexa como chunk adicional; `extract_symbols`
  alimenta el mapa de arquitectura (Mermaid/Markdown).
- **Consecuencias**: añadir un lenguaje = añadir una gramática pip al registry
  (`LANGUAGE_REGISTRY`). El mapa de arquitectura reparsea estáticamente los
  fuentes del checkout; nunca los ejecuta.

### ADR-003 — SQLite + FAISS (no pgvector)
- **Contexto**: el demo debe funcionar sin infraestructura externa más allá de
  Redis.
- **Decisión**: persistir chunks en **SQLite** y vectores en **FAISS**
  (`IndexFlatIP`) con fallback a Numpy en CPUs sin AVX.
- **Consecuencias**: una sola máquina aguanta el demo; migrar a pgvector es
  posible si se requiere escala multiusuario.

### ADR-004 — Cliente LLM multi-proveedor + mock anti-bloqueo
- **Contexto**: el demo no debe depender de una API key ni de un proveedor pago.
- **Decisión**: contrato único `LLMClient.complete(system, user)` con
  `OpenAICompatClient` (protocolo `/chat/completions`, cubre OpenAI, DeepSeek,
  Gemini y Ollama) y `MockLLM` (respuesta plantilla basada en el top-1 chunk).
  Sin `LLM_API_KEY` configurada, la fábrica devuelve siempre el mock.
- **Consecuencias**: el pipeline de `/ask` se demuestra de punta a punta sin
  credenciales; con key basta cambiar `LLM_PROVIDER`.

### ADR-005 — Indexación asíncrona con Celery + Redis
- **Contexto**: clonar y embeder repos grandes no puede bloquear la API.
- **Decisión**: `index_repo` como tarea Celery con progreso persistido en
  `Repo.progress`; la UI hace polling de `/status`.
- **Consecuencias**: el backend escala sin cambios de código; Redis es
  requisito del stack (ya se usa para el broker).

### ADR-006 — Soporte de ramas e indexación incremental (git)
- **Contexto**: el usuario pidió indexar ramas distintas de `main` y que un
  re-indexado no reprocesara todo el repo (cueste tiempo en repos grandes).
- **Decisión**: `Repo.branch` se clona con `--single-branch --branch <rama>`.
  La re-indexación reutiliza el checkout: `sync_checkout` hace
  `git fetch --depth 1`, compara `HEAD..FETCH_HEAD` (`git diff --name-status`)
  y, si hay <= `incremental_max_changed` (200) archivos tocados, re-indexa solo
  esos paths y registra `last_changes` (estados A/M/D + commits). Por encima del
  umbral, o sin red, se re-escanea todo (`is_full`).
- **Consecuencias**: actualizar un repo ya indexado es O(archivos cambiados);
  `reset --hard FETCH_HEAD` se hace siempre para no indexar código obsoleto.
  Los powers por defecto migran columnas antiguas con ALTER TABLE ligero.

### ADR-007 — Métricas de cobertura y mapa de arquitectura
- **Contexto**: el usuario quería saber qué tan completo está el índice y
  exportar un mapa del proyecto a Markdown/Mermaid.
- **Decisión**: la tarea persiste `stats` (chunks por lenguaje, bytes útiles,
  razones de omisión), `indexed_files`, `skipped_files`, `source_rev`, y
  `last_changes`. Un endpoint `GET /api/repos/{id}/architecture` reparsea el
  checkout y genera nodos/edges + Mermaid + Markdown descargable.
- **Consecuencias**: métricas en `RepoOut` (todas opcionales para no romper
  clientes viejos); el mapa se genera bajo demanda, no se cachea aún (repos
  pequeños OK, repos gigantes exigirían caché por `source_rev`).

### ADR-008 — Repos privados vía SSH con deploy key (solo hosts conocidos)
- **Contexto**: producción en OCI debe indexar repos privados de
  GitHub/GitLab/Bitbucket sin credenciales propias del usuario.
- **Decisión**: `validate_clone_url` acepta `http(s)` (SSRF-check) y URLs SSH
  (`git@host:owner/repo.git` o `ssh://git@host/...`) **únicamente** hacia
  `github.com`, `gitlab.com` y `bitbucket.org`. Si la URL es SSH, el clonado y
  el fetch incremental usan `GIT_SSH_COMMAND` con la deploy key de
  `settings.git_ssh_key` (`IdentitiesOnly`, `accept-new`, known_hosts en
  `/dev/null`). Sin clave configurada, una URL SSH falla con mensaje claro.
- **Consecuencias**: el ataque SSRF no se aplica a SSH (hosts fijos y
  allowlist); el código clonado sigue sin ejecutarse (solo parseo estático).
  `RepoCreate.url` pasó de `HttpUrl` a `str` para admitir el formato scp-like.
