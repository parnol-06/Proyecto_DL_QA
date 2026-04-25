#!/bin/sh

OLLAMA_BASE=${OLLAMA_HOST:-http://ollama:11434}
PRIMARY_MODEL=${OLLAMA_MODEL:-qwen2.5:7b}
EMBED_MODEL="nomic-embed-text"

# ── Esperar a Ollama ──────────────────────────────────────────────────────────
echo "[entrypoint] Esperando a Ollama en $OLLAMA_BASE ..."
until curl -sf "$OLLAMA_BASE/api/tags" > /dev/null 2>&1; do
  sleep 3
done
echo "[entrypoint] Ollama disponible."

# ── Función de descarga ───────────────────────────────────────────────────────
pull_model() {
  MODEL_NAME=$1

  # Verificar si el modelo ya existe (coincidencia exacta en el campo "name")
  if curl -sf "$OLLAMA_BASE/api/tags" | grep -q "\"name\":\"$MODEL_NAME\""; then
    echo "[entrypoint] $MODEL_NAME ya disponible."
    return 0
  fi

  echo "[entrypoint] Descargando $MODEL_NAME — esto puede tardar varios minutos..."

  # Mostrar progreso real (sin -s); --no-buffer para ver líneas conforme llegan
  if curl --no-buffer -X POST "$OLLAMA_BASE/api/pull" \
       -H "Content-Type: application/json" \
       -d "{\"name\": \"$MODEL_NAME\"}"; then
    echo ""
    echo "[entrypoint] $MODEL_NAME descargado correctamente."
  else
    echo "[entrypoint] ADVERTENCIA: no se pudo descargar $MODEL_NAME (continuando de todas formas)."
  fi
}

# ── Descargar modelos ─────────────────────────────────────────────────────────
pull_model "$PRIMARY_MODEL"
pull_model "$EMBED_MODEL"

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
