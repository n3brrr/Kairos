# syntax=docker/dockerfile:1

# Stage 1: build the frontend. Only this stage contains Node.
FROM node:24-slim AS frontend
ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0
WORKDIR /build/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: install the backend dependencies. uv lives only here, never in the runtime image.
FROM python:3.13-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=0
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src
RUN uv sync --frozen --no-dev --no-editable

# Stage 3: Python runtime. No Node, no uv, no build tools in the final image.
FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PATH="/app/backend/.venv/bin:$PATH"     KAIROS_DATA_DIR=/data     KAIROS_STATIC_DIR=/app/static
WORKDIR /app/backend
COPY --from=backend /app/backend/.venv ./.venv
COPY --from=frontend /build/frontend/dist /app/static

# /data must exist and belong to the runtime user BEFORE the VOLUME instruction: a fresh named
# volume copies this ownership, so the non-root user can write to it.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin kairos \
    && mkdir /data \
    && chown 10001:10001 /data
VOLUME /data
USER 10001

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]
# The container binds all interfaces; the host publishes the port on loopback only (compose.yaml).
CMD ["uvicorn", "kairos.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
