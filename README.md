# RepoBrain

Búsqueda semántica y Q&A sobre código fuente. Pegas un repositorio, la
plataforma lo indexa (parseo con `tree-sitter` + *embeddings*) y respondes a
preguntas en lenguaje natural con respuestas que citan `archivo:línea`.

Proyecto de portafolio gemelo de TechDebt Radar. Implementación por fases.

## Estado

- **F0 — Esqueleto:** ✅ completado. Stack levantado con Docker Compose, `/health` y `/health/ready` responden OK.

## Quickstart

```bash
docker compose up --build
```

- Frontend: http://localhost:5174
- Backend API: http://localhost:8002
- Documentación OpenAPI: http://localhost:8002/docs

## Stack

FastAPI · Pydantic v2 · Celery + Redis · tree-sitter · BM25 (`bm25s`) ·
`all-MiniLM-L6-v2` · SQLite + FAISS · React 19 + TypeScript + Vite · Docker · GH Actions

## Fases

| Fase | Entregable | Estado |
|------|-----------|--------|
| F0 | Esqueleto (compose, health, CI) | ✅ |
| F1 | Index + búsqueda híbrida + visor | Pendiente |
| F2 | Q&A con LLM y citas validadas | Pendiente |
| F3 | Pulido y producción (docs, hardening) | Pendiente |

## Documentación

Los documentos fuente de diseño (única fuente de verdad):

- `01-repobrain-busqueda-semantica-codigo.md` — especificación de diseño.
- `01-repobrain-README.md` — plan de referencia.

## Seguridad

El código de un repositorio **nunca se ejecuta** (solo parseo estático), se
bloquea SSRF, se protege de *path traversal*, y los contenedores corren como
usuarios no-root. Detalle en `docs/seguridad.md` (F3).

## Licencia

MIT.