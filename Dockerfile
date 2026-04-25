# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential gcc g++ cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Separar requirements para maximizar caché de capas
COPY requirements.txt ./

RUN pip install --no-cache-dir --prefix=/install \
        -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="Proyecto DL QA" \
      org.opencontainers.image.description="FastAPI + RAG + Ollama QA evaluation system" \
      org.opencontainers.image.source="https://github.com/parnol-06/Proyecto_DL_QA"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Una sola capa: instala curl + crea usuario no-root con shell desactivado
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --create-home --home-dir /home/appuser --shell /sbin/nologin appuser \
    && mkdir -p /app/chroma_db \
    && chown appuser:appgroup /app/chroma_db

WORKDIR /app

COPY --from=builder /install /usr/local

# Copiar solo lo necesario para runtime (tests/, scripts/ quedan fuera via .dockerignore)
COPY --chown=appuser:appgroup backend/      ./backend/
COPY --chown=appuser:appgroup frontend/     ./frontend/
COPY --chown=appuser:appgroup corpus/       ./corpus/
COPY --chown=appuser:appgroup entrypoint.sh ./

RUN chmod +x entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
