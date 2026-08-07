# Backend de RepoBrain (FastAPI + Celery worker)
# Multi-stage: stage de build/deps + stage de runtime no-root.

# ---------- Stage 1: dependencias ----------
FROM python:3.14-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY workers ./workers

RUN pip install --upgrade pip \
    && pip install .

# ---------- Stage 2: runtime ----------
FROM python:3.14-slim AS runtime

RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --no-create-home appuser

WORKDIR /app

# Copiamos el entorno instalado en el stage de deps
COPY --from=deps /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY --from=deps /app/app ./app
COPY --from=deps /app/workers ./workers

# Directorios de datos/workspace con permisos del usuario no-raíz
RUN mkdir -p /app/data /app/workspace \
    && chown -R appuser:appuser /app

ENV PYTHONPATH=/app \
    ENVIRONMENT=development

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]