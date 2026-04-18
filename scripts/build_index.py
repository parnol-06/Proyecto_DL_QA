"""
Script para construir el índice RAG desde el corpus de documentos.
Ejecutar desde la raíz del proyecto:
    python scripts/build_index.py
"""

import os
import sys

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

import ollama
from backend.services.rag_service import build_index, CORPUS_DIR, EMBED_MODEL


def check_embed_model() -> bool:
    """Verifica que el modelo de embeddings está disponible en Ollama."""
    try:
        models = ollama.list()
        names = [m["name"].split(":")[0] for m in models.get("models", [])]
        return EMBED_MODEL in names or EMBED_MODEL.split(":")[0] in names
    except Exception:
        return False


def main():
    print("=" * 55)
    print("  QA Knowledge Base — Indexador RAG")
    print("=" * 55)

    if not os.path.isdir(CORPUS_DIR):
        print(f"\nNo existe el directorio corpus/: {CORPUS_DIR}")
        print("Crea la carpeta y agrega archivos .md o .txt con documentación QA.")
        sys.exit(1)

    docs = [f for f in os.listdir(CORPUS_DIR) if f.endswith((".md", ".txt"))]
    if not docs:
        print(f"\nNo se encontraron archivos .md o .txt en {CORPUS_DIR}")
        sys.exit(1)

    print(f"\nDocumentos encontrados: {docs}")

    if not check_embed_model():
        print(f"\nEl modelo de embeddings '{EMBED_MODEL}' no está disponible en Ollama.")
        print(f"Descárgalo con:  ollama pull {EMBED_MODEL}")
        sys.exit(1)

    print(f"\nModelo de embeddings: {EMBED_MODEL}")
    print(f"Corpus: {CORPUS_DIR}")
    print("\nIndexando documentos...")

    total = build_index(CORPUS_DIR)

    print(f"\nÍndice construido exitosamente.")
    print(f"  Chunks indexados: {total}")
    print(f"  Vector store: chroma_db/")
    print("\nEl RAG está listo. Activa la opción en la UI para usarlo.")


if __name__ == "__main__":
    main()
