# API and worker image (same image, different command).
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    EMBEDDING_CACHE_DIR=/opt/models

# Tesseract OCR reads scanned PDF pages and images.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Bake the embedding model into the image so containers start without a network download.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/opt/models')"

COPY alembic.ini ./
COPY ai_engine ./ai_engine
COPY app ./app
COPY scripts ./scripts
COPY evals ./evals

RUN useradd --system --uid 10001 appuser \
    && mkdir -p /data/storage \
    && chown -R appuser /data \
    && chmod -R a+rX /opt/models
USER appuser

ENV STORAGE_LOCAL_DIR=/data/storage
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
