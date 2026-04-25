"""Tests para backend/services/rag_service.py"""
import os
import pytest
from unittest.mock import patch, MagicMock


# ── _chunk_text ────────────────────────────────────────────────────────────────

def test_chunk_text_splits_correctly():
    from backend.services.rag_service import _chunk_text, CHUNK_SIZE, CHUNK_OVERLAP
    text = "A" * 1000
    chunks = _chunk_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_SIZE for c in chunks)

def test_chunk_text_filters_short_chunks():
    from backend.services.rag_service import _chunk_text
    text = "Hola"  # muy corto, debe filtrarse (< 50 chars)
    chunks = _chunk_text(text)
    assert chunks == []

def test_chunk_text_single_chunk_for_short_text():
    from backend.services.rag_service import _chunk_text
    text = "Este es un texto de prueba con suficiente contenido para pasar el filtro de longitud mínima."
    chunks = _chunk_text(text)
    assert len(chunks) == 1

# ── semantic_search ────────────────────────────────────────────────────────────

def test_semantic_search_returns_empty_when_collection_empty():
    """Si no hay chunks indexados, retorna string vacío sin lanzar excepción."""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0

    with patch("backend.services.rag_service._get_collection", return_value=mock_collection):
        from backend.services.rag_service import semantic_search
        result = semantic_search("test query")
    assert result == ""

def test_semantic_search_returns_context_when_indexed():
    """Con chunks indexados, retorna el texto de los documentos recuperados."""
    mock_collection = MagicMock()
    mock_collection.count.return_value = 5
    mock_collection.query.return_value = {
        "documents": [["Fragmento de buenas prácticas QA", "Otro fragmento relevante"]]
    }
    mock_embed = [0.1] * 768  # vector de embeddings simulado

    with patch("backend.services.rag_service._get_collection", return_value=mock_collection), \
         patch("backend.services.rag_service._embed", return_value=mock_embed):
        from backend.services.rag_service import semantic_search
        result = semantic_search("casos de prueba de login")

    assert "Fragmento de buenas prácticas QA" in result
    assert "Otro fragmento relevante" in result

def test_semantic_search_returns_empty_on_exception():
    """Si ChromaDB lanza excepción, retorna string vacío (no propaga el error)."""
    with patch("backend.services.rag_service._get_collection", side_effect=Exception("ChromaDB no disponible")):
        from backend.services.rag_service import semantic_search
        result = semantic_search("cualquier query")
    assert result == ""

# ── is_index_built ─────────────────────────────────────────────────────────────

def test_is_index_built_false_when_empty():
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    with patch("backend.services.rag_service._get_collection", return_value=mock_collection):
        from backend.services.rag_service import is_index_built
        assert is_index_built() is False

def test_is_index_built_true_when_has_docs():
    mock_collection = MagicMock()
    mock_collection.count.return_value = 42
    with patch("backend.services.rag_service._get_collection", return_value=mock_collection):
        from backend.services.rag_service import is_index_built
        assert is_index_built() is True

def test_is_index_built_false_on_exception():
    with patch("backend.services.rag_service._get_collection", side_effect=Exception("Error")):
        from backend.services.rag_service import is_index_built
        assert is_index_built() is False

# ── build_index ────────────────────────────────────────────────────────────────

def test_build_index_processes_corpus_files(tmp_path):
    """build_index lee archivos .md del corpus y los indexa en ChromaDB."""
    # Crear corpus temporal con 1 archivo .md
    corpus_file = tmp_path / "test_doc.md"
    corpus_file.write_text("A" * 600, encoding="utf-8")  # > CHUNK_SIZE → 2 chunks

    mock_collection = MagicMock()
    mock_collection.count.return_value = 0
    mock_embed = [0.1] * 768

    with patch("backend.services.rag_service._get_collection", return_value=mock_collection), \
         patch("backend.services.rag_service._embed", return_value=mock_embed):
        from backend.services.rag_service import build_index
        total = build_index(str(tmp_path))

    assert total >= 1
    assert mock_collection.upsert.called
