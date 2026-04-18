"""
RAG Service — Recuperación de contexto desde corpus de buenas prácticas QA.
Usa ChromaDB como vector store y nomic-embed-text (Ollama) para embeddings.
"""

import logging
import os

import chromadb
import ollama

logger = logging.getLogger(__name__)

# ── Rutas ─────────────────────────────────────────────────────────────────────
_BASE_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CHROMA_PATH  = os.path.join(_BASE_DIR, "chroma_db")
CORPUS_DIR   = os.path.join(_BASE_DIR, "corpus")
EMBED_MODEL  = "nomic-embed-text"
COLLECTION   = "qa_knowledge"
CHUNK_SIZE   = 500
CHUNK_OVERLAP = 50

# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed(text: str) -> list[float]:
    """Genera embedding con nomic-embed-text via Ollama."""
    response = ollama.embed(model=EMBED_MODEL, input=text)
    return response["embeddings"][0]


def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name=COLLECTION)


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str) -> list[str]:
    """Divide texto en chunks con solapamiento."""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end].strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if len(c) > 50]


# ── Indexación ────────────────────────────────────────────────────────────────

def build_index(corpus_dir: str = CORPUS_DIR) -> int:
    """
    Lee .md y .txt de corpus_dir, genera embeddings y guarda en ChromaDB.
    Retorna el número de chunks indexados.
    """
    collection = _get_collection()

    # Limpiar colección existente para re-indexar
    existing = collection.count()
    if existing > 0:
        collection.delete(where={"source": {"$ne": ""}})
        logger.info("Colección limpiada | chunks previos=%d", existing)

    extensions = (".md", ".txt")
    total_chunks = 0

    for fname in os.listdir(corpus_dir):
        if not fname.lower().endswith(extensions):
            continue
        fpath = os.path.join(corpus_dir, fname)
        with open(fpath, encoding="utf-8") as f:
            text = f.read()

        chunks = _chunk_text(text)
        logger.info("Indexando %s | chunks=%d", fname, len(chunks))

        for i, chunk in enumerate(chunks):
            try:
                embedding = _embed(chunk)
                chunk_id = f"{fname}_chunk_{i}"
                collection.upsert(
                    ids=[chunk_id],
                    embeddings=[embedding],
                    documents=[chunk],
                    metadatas=[{"source": fname, "chunk": i}],
                )
                total_chunks += 1
            except Exception as exc:
                logger.warning("Error indexando chunk %d de %s: %s", i, fname, exc)

    logger.info("Índice construido | total_chunks=%d", total_chunks)
    return total_chunks


# ── Búsqueda semántica ────────────────────────────────────────────────────────

def semantic_search(query: str, k: int = 3) -> str:
    """
    Busca los k chunks más relevantes para la query.
    Retorna texto concatenado o "" si no hay índice o falla.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            logger.debug("Vector store vacío — RAG deshabilitado")
            return ""

        embedding = _embed(query)
        n = min(k, collection.count())
        results = collection.query(query_embeddings=[embedding], n_results=n)
        docs = results.get("documents", [[]])[0]
        if not docs:
            return ""

        context = "\n\n---\n\n".join(docs)
        logger.info("RAG: %d fragmentos recuperados para la consulta", len(docs))
        return context

    except Exception as exc:
        logger.warning("RAG semantic_search falló: %s", exc)
        return ""


def is_index_built() -> bool:
    """True si la colección tiene al menos 1 documento."""
    try:
        return _get_collection().count() > 0
    except Exception:
        return False
