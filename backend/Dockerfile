# Multi-stage: production runtime (default last stage) + test target with dev extras.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=ghcr.io/astral-sh/uv:0.11.23 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY uv.lock ./

FROM base AS test
COPY tests ./tests
RUN uv sync --frozen --extra dev \
    && chown -R appuser:appuser /app
USER appuser
WORKDIR /app
CMD ["uv", "run", "pytest", "-rs"]

FROM base AS runtime
RUN uv sync --frozen --no-dev \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
