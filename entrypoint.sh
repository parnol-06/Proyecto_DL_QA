#!/bin/sh
set -e

MODEL=${OLLAMA_MODEL:-llama3.2}

echo "Esperando a que Ollama esté listo..."
until curl -sf http://ollama:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done
echo "Ollama disponible."

echo "Verificando modelo $MODEL..."
if ! curl -sf http://ollama:11434/api/tags | grep -q "$MODEL"; then
  echo "Descargando $MODEL (puede tardar varios minutos)..."
  curl -s -X POST http://ollama:11434/api/pull \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$MODEL\"}" | tail -1
  echo "Modelo $MODEL descargado."
else
  echo "Modelo $MODEL ya disponible."
fi

echo "Iniciando servidor..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
