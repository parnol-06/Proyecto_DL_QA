#!/bin/sh

OLLAMA_BASE=${OLLAMA_HOST:-http://host.docker.internal:11434}

# ── Esperar a Ollama ──────────────────────────────────────────────────────────
echo "[entrypoint] Esperando a Ollama en $OLLAMA_BASE ..."
until curl -sf "$OLLAMA_BASE/api/tags" > /dev/null 2>&1; do
  sleep 3
done
echo "[entrypoint] Ollama disponible."

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
