#!/bin/sh

OLLAMA_BASE=${OLLAMA_HOST:-http://localhost:11434}

# ── Esperar a Ollama (máximo 120 segundos) ───────────────────────────────────
echo "[entrypoint] Esperando a Ollama en $OLLAMA_BASE ..."
MAX_WAIT=120
WAITED=0
until curl -sf "$OLLAMA_BASE/api/tags" > /dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo "[entrypoint] ERROR: Ollama no respondió en ${MAX_WAIT}s. Abortando." >&2
    exit 1
  fi
  sleep 3
  WAITED=$((WAITED + 3))
done
echo "[entrypoint] Ollama disponible."

# ── Descargar nomic-embed-text (requerido para indexación RAG) ────────────────
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
TAGS=$(curl -sf "$OLLAMA_BASE/api/tags" 2>/dev/null || echo "{}")
if echo "$TAGS" | grep -q "\"${EMBED_MODEL}\""; then
  echo "[entrypoint] Modelo de embeddings '$EMBED_MODEL' ya disponible."
else
  echo "[entrypoint] Descargando modelo de embeddings '$EMBED_MODEL' ..."
  if curl -sf -X POST "$OLLAMA_BASE/api/pull" \
      -H 'Content-Type: application/json' \
      -d "{\"name\": \"${EMBED_MODEL}\"}" > /dev/null 2>&1; then
    echo "[entrypoint] Modelo '$EMBED_MODEL' descargado."
  else
    echo "[entrypoint] ADVERTENCIA: no se pudo descargar '$EMBED_MODEL'. El RAG no estará disponible."
  fi
fi

# ── Mostrar modelos LLM disponibles (sin descargar nada) ─────────────────────
echo "[entrypoint] Modelos LLM disponibles en Ollama:"
curl -sf "$OLLAMA_BASE/api/tags" 2>/dev/null \
  | python3 -c "
import sys, json
tags = json.load(sys.stdin)
models = [m['name'] for m in tags.get('models', []) if 'embed' not in m['name']]
if models:
    for m in models:
        print(f'  - {m}')
else:
    print('  (ninguno — descarga un modelo con: ollama pull <nombre>)')
" 2>/dev/null || echo "  (no se pudo leer la lista de modelos)"

# ── Configurar Opik ───────────────────────────────────────────────────────────
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

# ── Construir índice RAG si no existe ─────────────────────────────────────────
echo "[entrypoint] Verificando índice RAG..."
python -c "
import sys, os
sys.path.insert(0, '/app')
from backend.services.rag_service import is_index_built, build_index
if not is_index_built():
    print('[entrypoint] Construyendo índice RAG desde corpus/...')
    n = build_index()
    print(f'[entrypoint] Índice construido: {n} chunks.')
else:
    print('[entrypoint] Índice RAG ya existe.')
" || echo "[entrypoint] Advertencia: no se pudo construir el índice RAG."

# ── Iniciar servidor ──────────────────────────────────────────────────────────
echo "[entrypoint] Iniciando servidor FastAPI en :8000 ..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
