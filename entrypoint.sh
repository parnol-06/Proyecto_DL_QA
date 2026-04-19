#!/bin/sh
set -e

OLLAMA_BASE=${OLLAMA_HOST:-http://ollama:11434}
MODEL=${OLLAMA_MODEL:-llama3.2}
EMBED_MODEL="nomic-embed-text"

# ── Esperar a Ollama ──────────────────────────────────────────────────────────
echo "[entrypoint] Esperando a Ollama en $OLLAMA_BASE ..."
until curl -sf "$OLLAMA_BASE/api/tags" > /dev/null 2>&1; do
  sleep 2
done
echo "[entrypoint] Ollama disponible."

# ── Descargar modelo principal ────────────────────────────────────────────────
if ! curl -sf "$OLLAMA_BASE/api/tags" | grep -q "\"$MODEL\""; then
  echo "[entrypoint] Descargando $MODEL (puede tardar varios minutos)..."
  curl -s -X POST "$OLLAMA_BASE/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$MODEL\"}" | tail -1
  echo "[entrypoint] $MODEL descargado."
else
  echo "[entrypoint] $MODEL ya disponible."
fi

# ── Descargar modelo de embeddings para RAG ───────────────────────────────────
if ! curl -sf "$OLLAMA_BASE/api/tags" | grep -q "\"$EMBED_MODEL\""; then
  echo "[entrypoint] Descargando $EMBED_MODEL (necesario para RAG)..."
  curl -s -X POST "$OLLAMA_BASE/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$EMBED_MODEL\"}" | tail -1
  echo "[entrypoint] $EMBED_MODEL descargado."
else
  echo "[entrypoint] $EMBED_MODEL ya disponible."
fi

# ── Configurar Opik (non-interactive, force=True evita prompts en Docker) ─────
if [ -n "$OPIK_API_KEY" ]; then
  echo "[entrypoint] Configurando Opik (workspace=$OPIK_WORKSPACE, proyecto=$OPIK_PROJECT_NAME)..."
  python -c "
import opik, os
opik.configure(
    api_key=os.environ['OPIK_API_KEY'],
    workspace=os.environ.get('OPIK_WORKSPACE') or None,
    force=True,
)
print('[entrypoint] Opik configurado correctamente.')
" || echo "[entrypoint] Advertencia: Opik no pudo configurarse (continuando sin trazas)."
fi

# ── Iniciar servidor ──────────────────────────────────────────────────────────
echo "[entrypoint] Iniciando servidor FastAPI en :8000 ..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
