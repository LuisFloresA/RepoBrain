# Backend de RepoBrain (FastAPI + Celery worker)
# Multi-stage: stage de build/deps + stage de runtime no-root.

# ---------- Stage 1: dependencias ----------
FROM python:3.14-slim AS deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Capa cacheable: las dependencias externas se instalan UNA sola vez. Los
# cambios de código no vuelven a compilar gramáticas ni a bajar torch/etc.
COPY requirements-runtime.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements-runtime.txt

# El código del proyecto se instala SIN re-resolver dependencias externas
# (--no-deps), para que esta capa sea barata y cacheable.
COPY pyproject.toml ./
COPY app ./app
COPY workers ./workers

RUN pip install --no-deps .

# ---------- Stage 2: runtime ----------
FROM python:3.14-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 --no-create-home appuser

WORKDIR /app

# Copiamos el entorno instalado en el stage de deps
COPY --from=deps /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY --from=deps /app/app ./app
COPY --from=deps /app/workers ./workers

# Directorios de datos/workspace con permisos del usuario no-raíz
RUN mkdir -p /app/data /app/workspace /app/cache \
    && chown -R appuser:appuser /app

ENV PYTHONPATH=/app \
    ENVIRONMENT=development \
    HF_HOME=/app/cache/huggingface \
    TRANSFORMERS_CACHE=/app/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/cache/sentence_transformers \
    TOKENIZERS_PARALLELISM=false

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]