# API (OpenAPI + ejemplos curl)

El esquema completo se autogenera en `GET /openapi.json` y la UI interactiva en
`/docs` (Swagger). Prefijo base: `/api` (backend en `:8000` internamente;
`http://localhost:8002` en el dev compose).

## Health

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/health/ready` | Readiness (reporta Redis) |

```bash
curl http://localhost:8002/health
curl http://localhost:8002/health/ready
```

## Repositorios

### Crear e indexar

```bash
curl -X POST http://localhost:8002/api/repos \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/pallets/flask","name":"flask","source":"url"}'
```

Respuesta `201`: el `Repo` queda en estado `indexing` (la indexación corre en el
worker). El demo embebido se crea con `"source":"demo"` sin URL.

**Ramas**: incluye `"branch":"develop"` para clonar solo esa rama
(`git clone --single-branch --branch develop`). Si se omite, se clona la rama
por defecto remota.

```bash
curl -X POST http://localhost:8002/api/repos \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/pallets/flask","branch":"1.1.x","name":"flask-1.1","source":"url"}'
```

### Listar / estado / re-indexar / eliminar

```bash
curl http://localhost:8002/api/repos
curl http://localhost:8002/api/repos/<id>/status
curl -X POST http://localhost:8002/api/repos/<id>/index
curl -X DELETE http://localhost:8002/api/repos/<id>
```

## Búsqueda híbrida

```bash
curl "http://localhost:8002/api/repos/<id>/search?q=dónde%20se%20valida%20el%20jwt&top_k=5"
```

Devuelve `results[]` con `path`, `start_line`, `end_line`, `snippet`, `score`,
`bm25_score`, `semantic_score`. Requiere repo en estado `ready` (409 si no).

## Q&A con LLM

```bash
curl -X POST http://localhost:8002/api/repos/<id>/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"¿cómo se hace el soft delete?","top_k":5}'
```

Respuesta: `answer` (texto), `citations[]` (`path`, `start_line`, `end_line`)
**validadas contra el checkout real**, `source` (`mock` | `openai-compatible`)
y `llm` (proveedor:modelo).

## Archivos

```bash
curl http://localhost:8002/api/repos/<id>/files/app/auth.py
```

Devuelve `content`, `language` y `line_count`. Las rutas se validan contra el
workspace (path traversal → 400/404).

## Mapa de arquitectura

```bash
curl http://localhost:8002/api/repos/<id>/architecture
```

Devuelve `nodes[]` (`id`, `label`, `kind` file/class/function, `path`, `line`),
`edges[]`, `mermaid` (declaración `graph TD`) y `markdown` (resumen + desglose
por archivo listo para exportar). Requiere repo en estado `ready`.

## Métricas de cobertura

`GET /api/repos/<id>/status` expone además: `branch`, `source_rev`,
`indexed_files`, `skipped_files`, `indexed_bytes`, `last_indexed_at`,
`stats` (`by_language`, `skipped_reasons`, `indexed_bytes`) y `last_changes`
(`full`, `count`, `files[{path,status}]`, `commits`). En re-indexaciones el
campo `last_changes` refleja exactamente qué cambió en el `git diff` desde el
último índice (ahorrando un re-indexado completo por debajo del umbral de 200
archivos).

## Notas

- Rate limiting por IP en `/api/*` (429 con `Retry-After`; configurable vía
  `REQUEST_RATE_LIMIT_PER_MINUTE`, `0` = desactivado).
- Códigos típicos: `201` creado, `400` ruta inválida, `404` no existe,
  `409` estado no `ready`, `422` validación DTO, `429` rate limit.
