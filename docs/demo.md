# Demo — guión de 2 minutos

Objetivo: que el evaluador vea todo funcionando **sin API key, sin registro y
sin red** para el repositorio de ejemplo (está embebido y pre-indexado).

## Paso a paso

1. **Abrir la URL** del demo (10 s).
   - Frontend en `http://localhost:5174` (dev) o la URL desplegada.
   - El repo "Demo · login-api (JWT)" aparece ya listo con `status=ready`.

2. **Clic en "Probar ahora"** (15 s).
   - Ejecuta la búsqueda *"¿dónde se valida el JWT?"* con un clic.
   - Se ve el resultado con `app/auth.py:línea`, el *score* y el **snippet**.
   - Clic en el resultado: se abre el **visor con la línea resaltada**.

3. **Búsqueda propia** (30 s).
   - Escribe *"¿cómo se hace el soft delete?"* o *"¿en qué archivo está la
     conexión a la base de datos?"* → búsqueda híbrida real (BM25 + embeddings).

4. **Q&A al código** (30 s).
   - En el panel "Pregunta al código" escribe *"¿dónde se valida el jwt?"* →
     "Preguntar".
   - La respuesta llega **con citas verificadas** (`app/auth.py:28`) que abren
     el archivo en esa línea. El motor es el **mock** (no requiere API key);
     el pipeline es idéntico al de un LLM real.

5. **Repo real** (opcional, requiere red, 30 s).
   - "Indexar" un repo público (p. ej. `https://github.com/pallets/flask`) y ver
     el **progreso en vivo** hasta `ready`, luego buscar dentro.

## Si se quiere probar el LLM real

```bash
LLM_PROVIDER=deepseek LLM_API_KEY=... docker compose up -d --build
```

Sin clave, `/ask` sigue funcionando con el mock (anti-bloqueo).
