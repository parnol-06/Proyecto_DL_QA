#!/bin/sh

OLLAMA_BASE=${OLLAMA_HOST:-http://localhost:11434}

# ── Wait for Ollama (up to 120 seconds) ──────────────────────────────────────
echo "[entrypoint] Waiting for Ollama at $OLLAMA_BASE ..."
MAX_WAIT=120
WAITED=0
until curl -sf "$OLLAMA_BASE/api/tags" > /dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[entrypoint] ERROR: Ollama did not respond within ${MAX_WAIT}s. Aborting." >&2
    exit 1
  fi
  sleep 3
  WAITED=$((WAITED + 3))
done
echo "[entrypoint] Ollama is available."

# ── Download nomic-embed-text (required for RAG indexing) ────────────────────
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
TAGS=$(curl -sf "$OLLAMA_BASE/api/tags" 2>/dev/null || echo "{}")
if echo "$TAGS" | grep -q "\"${EMBED_MODEL}\""; then
  echo "[entrypoint] Embedding model '$EMBED_MODEL' already available."
else
  echo "[entrypoint] Downloading embedding model '$EMBED_MODEL' ..."
  if curl -sf -X POST "$OLLAMA_BASE/api/pull" \
      -H 'Content-Type: application/json' \
      -d "{\"name\": \"${EMBED_MODEL}\"}" > /dev/null 2>&1; then
    echo "[entrypoint] Model '$EMBED_MODEL' downloaded."
  else
    echo "[entrypoint] WARNING: could not download '$EMBED_MODEL'. RAG will not be available."
  fi
fi

# ── List available LLM models (no downloads) ─────────────────────────────────
echo "[entrypoint] Available LLM models in Ollama:"
curl -sf "$OLLAMA_BASE/api/tags" 2>/dev/null \
  | python3 -c "
import sys, json
tags = json.load(sys.stdin)
models = [m['name'] for m in tags.get('models', []) if 'embed' not in m['name']]
if models:
    for m in models:
        print(f'  - {m}')
else:
    print('  (none — download a model with: ollama pull <name>)')
" 2>/dev/null || echo "  (could not read model list)"

# ── Configure Opik ────────────────────────────────────────────────────────────
if [ -n "$OPIK_API_KEY" ]; then
  echo "[entrypoint] Configuring Opik (workspace=$OPIK_WORKSPACE, project=$OPIK_PROJECT_NAME)..."
  python -c "
import opik, os
opik.configure(
    api_key=os.environ['OPIK_API_KEY'],
    workspace=os.environ.get('OPIK_WORKSPACE') or None,
    force=True,
)
print('[entrypoint] Opik configured successfully.')
" || echo "[entrypoint] Warning: Opik could not be configured (continuing without traces)."
fi

# ── Build RAG index if it does not exist ─────────────────────────────────────
echo "[entrypoint] Checking RAG index..."
python -c "
import sys, os
sys.path.insert(0, '/app')
from backend.services.rag_service import is_index_built, build_index
if not is_index_built():
    print('[entrypoint] Building RAG index from corpus/...')
    n = build_index()
    print(f'[entrypoint] Index built: {n} chunks.')
else:
    print('[entrypoint] RAG index already exists.')
" || echo "[entrypoint] Warning: could not build RAG index."

# ── Start server ──────────────────────────────────────────────────────────────
echo "[entrypoint] Starting FastAPI server on :8000 ..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
