# ── Stage 1: Frontend build ──────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Layer-cache the dependency install separately from the source copy.
# npm ci is used when a lockfile is present (faster, deterministic, CI-safe).
# Fallback to install only when no lockfile exists (first-time dev setup).
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; \
    then npm ci --prefer-offline --no-audit --no-fund; \
    else npm install --prefer-offline --no-audit --no-fund; \
    fi

# Copy source and build (separate layer so dep-install is cached on src changes)
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python dependency builder ───────────────────────────────────────
FROM python:3.11-slim-bookworm AS py-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc g++ cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-eval.txt ./
# Upgrade pip first — pip 24.x has a buggy backtracking resolver that fails on
# crewai + deepeval + opik together. pip 26.x resolves this correctly.
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install \
        -r requirements.txt \
        -r requirements-eval.txt

# ── Stage 3: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="Proyecto DL QA" \
      org.opencontainers.image.description="FastAPI + React + DeepEval + Ollama QA system" \
      org.opencontainers.image.source="https://github.com/parnol-06/Proyecto_DL_QA"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --create-home \
               --home-dir /home/appuser --shell /sbin/nologin appuser \
    && mkdir -p /app/chroma_db \
    && chown appuser:appgroup /app/chroma_db

WORKDIR /app

# Python packages from builder
COPY --from=py-builder /install /usr/local

# App source (no frontend/src — only the built dist)
COPY --chown=appuser:appgroup backend/      ./backend/
COPY --chown=appuser:appgroup corpus/       ./corpus/
COPY --chown=appuser:appgroup evaluator/    ./evaluator/
COPY --chown=appuser:appgroup entrypoint.sh ./

# Built React frontend (replaces raw JS)
COPY --from=frontend-builder --chown=appuser:appgroup /frontend/dist ./frontend/dist/

# Fix Windows CRLF line endings for Linux container compatibility
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
