"""
RAG Service — Context retrieval from QA best-practices corpus.
Uses ChromaDB as vector store and nomic-embed-text (Ollama) for embeddings.
"""

import asyncio
import logging
import os
import time

import chromadb
import ollama

from backend.config import OLLAMA_HOST
from backend.observability import tracer

logger = logging.getLogger(__name__)

_ollama = ollama.Client(host=OLLAMA_HOST)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BASE_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CHROMA_PATH  = os.path.join(_BASE_DIR, "chroma_db")
CORPUS_DIR   = os.path.join(_BASE_DIR, "corpus")
EMBED_MODEL  = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
COLLECTION   = "qa_knowledge"
CHUNK_SIZE   = 500
CHUNK_OVERLAP = 50


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed(text: str) -> list[float]:
    """Generates embedding with nomic-embed-text via Ollama. Traced via embed_span."""
    with tracer.embed_span(text[:200]) as s:
        t0 = time.monotonic()
        response = _ollama.embed(model=EMBED_MODEL, input=text)
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        embedding = response["embeddings"][0]
        tracer.update_span(
            s,
            output={"embedding_dim": len(embedding)},
            metadata={"embed_time_ms": elapsed_ms, "input_chars": len(text)},
        )
        return embedding


def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_or_create_collection(name=COLLECTION)


# ── Chunking ──────────────────────────────────────────────────────────────────

def _chunk_text(text: str) -> list[str]:
    """Splits text into overlapping chunks."""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end].strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if len(c) > 50]


# ── Indexación ────────────────────────────────────────────────────────────────

@tracer.track("rag_build_index")
def build_index(corpus_dir: str = CORPUS_DIR) -> int:
    """
    Reads .md and .txt files from corpus_dir, generates embeddings and saves to ChromaDB.
    Returns the number of indexed chunks.
    """
    with tracer.child_span(
        "chromadb_build_index",
        span_type="tool",
        input_data={"corpus_dir": corpus_dir},
        metadata={"component": "chromadb", "operation": "build_index", "embed_model": EMBED_MODEL},
    ) as s:
        collection = _get_collection()

        existing = collection.count()
        if existing > 0:
            collection.delete(where={"source": {"$ne": ""}})
            logger.info("Collection cleared | previous_chunks=%d", existing)

        extensions = (".md", ".txt")
        total_chunks = 0

        for fname in os.listdir(corpus_dir):
            if not fname.lower().endswith(extensions):
                continue
            fpath = os.path.join(corpus_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                text = f.read()

            chunks = _chunk_text(text)
            logger.info("Indexing %s | chunks=%d", fname, len(chunks))

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

        logger.info("Index built | total_chunks=%d", total_chunks)
        tracer.update_span(
            s,
            output={"total_chunks_indexed": total_chunks},
            metadata={"files_processed": len(os.listdir(corpus_dir))},
        )
        return total_chunks


# ── Búsqueda semántica ────────────────────────────────────────────────────────

def semantic_search(query: str, k: int = 3) -> str:
    """
    Searches the k most relevant chunks for the query.
    Returns concatenated text or "" if no index exists or search fails.
    Creates child spans for embed + query phases.
    """
    try:
        collection = _get_collection()
        if collection.count() == 0:
            logger.debug("Vector store empty — RAG disabled")
            return ""

        # Embedding span is created inside _embed()
        t0 = time.monotonic()
        embedding = _embed(query)
        embed_ms = round((time.monotonic() - t0) * 1000)

        # ChromaDB query span
        with tracer.child_span(
            "chromadb_query",
            span_type="tool",
            input_data={"k": min(k, collection.count()), "collection": COLLECTION},
            metadata={
                "component": "chromadb",
                "operation": "query",
                "embed_time_ms": embed_ms,
            },
        ) as s:
            t1 = time.monotonic()
            n = min(k, collection.count())
            results = collection.query(query_embeddings=[embedding], n_results=n)
            query_ms = round((time.monotonic() - t1) * 1000)

            docs = results.get("documents", [[]])[0]
            if not docs:
                tracer.update_span(s, output={"docs_found": 0}, metadata={"query_time_ms": query_ms})
                return ""

            context = "\n\n---\n\n".join(docs)
            tracer.update_span(
                s,
                output={
                    "docs_found": len(docs),
                    "context_chars": len(context),
                    "context_preview": context[:200],
                },
                metadata={"query_time_ms": query_ms},
            )
            logger.info(
                "RAG: %d fragments retrieved",
                len(docs),
                extra={
                    "docs_found": len(docs),
                    "context_chars": len(context),
                    "embed_time_ms": embed_ms,
                    "query_time_ms": query_ms,
                },
            )
            return context

    except Exception as exc:
        logger.warning("RAG semantic_search failed: %s", exc)
        return ""


def is_index_built() -> bool:
    """True if the collection has at least 1 document."""
    try:
        return _get_collection().count() > 0
    except Exception:
        return False


async def async_semantic_search(query: str, k: int = 3) -> str:
    """Async-safe version of semantic_search: runs in thread executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, semantic_search, query, k)
