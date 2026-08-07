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
  `typescript`). Los *anchors* (funciones/clases) alinean los chunks a
  estructuras reales, y el prefijo del archivo (docstring/imports/config) se
  indexa como chunk adicional.
- **Consecuencias**: añadir un lenguaje = añadir una gramática pip; F2 deja
  pendiente Java/C# (mismo mecanismo).

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
