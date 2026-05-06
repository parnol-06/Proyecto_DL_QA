"""
Tests para endpoints SSE de streaming.
Verifica que /generate/stream y /generate/agents/stream:
  - retornen content-type text/event-stream
  - emitan eventos data:
  - manejen errores mid-stream sin colgar
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

VALID_STORY = (
    "Como usuario registrado quiero iniciar sesión con mi email y contraseña "
    "para acceder a mi cuenta personal y ver mi historial de actividad."
)

MOCK_CHUNKS = [
    {"message": {"content": '{"test_cases":[{"id":"TC-001","title":"Login exitoso",'}},
    {"message": {"content": '"category":"happy_path","priority":"alto",'}},
    {"message": {"content": '"preconditions":["Usuario registrado"],'}},
    {"message": {"content": '"steps":["Ir a /login","Ingresar email","Ingresar contraseña","Clic en Entrar"],'}},
    {"message": {"content": '"expected_result":"Redirige al dashboard","test_type":"funcional"}]'}},
    {"message": {"content": ',"edge_scenarios":[],"potential_bugs":[],"coverage_summary":{"total_test_cases":1,"categories_covered":["happy_path"],"estimated_coverage_percent":30,"missing_areas":[]}}'}},
]


@pytest.mark.anyio
async def test_generate_stream_returns_event_stream(client):
    """El endpoint /generate/stream responde con content-type text/event-stream."""
    with patch("backend.services.llm_service.ollama.chat", return_value=iter(MOCK_CHUNKS)):
        res = await client.post("/generate/stream", json={"user_story": VALID_STORY})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")


@pytest.mark.anyio
async def test_generate_stream_emits_data_events(client):
    """El stream emite al menos un evento 'data:' con contenido JSON."""
    with patch("backend.services.llm_service.ollama.chat", return_value=iter(MOCK_CHUNKS)):
        res = await client.post("/generate/stream", json={"user_story": VALID_STORY})
    assert "data:" in res.text


@pytest.mark.anyio
async def test_generate_stream_short_story_returns_422(client):
    """Una historia demasiado corta (<20 chars) debe retornar 422 antes de hacer streaming."""
    res = await client.post("/generate/stream", json={"user_story": "muy corta"})
    assert res.status_code == 422


@pytest.mark.anyio
async def test_agents_stream_returns_event_stream(client):
    """El endpoint /generate/agents/stream responde con content-type text/event-stream."""
    async def _mock_pipeline(req, rag_context=""):
        yield f"data: {json.dumps({'event': 'agent_start', 'agent': 'Generador', 'step': 1, 'total': 3})}\n\n"
        yield f"data: {json.dumps({'event': 'done', 'data': {'test_cases': [], 'edge_scenarios': [], 'potential_bugs': [], 'coverage_summary': {}, 'raw_story': req.user_story, 'agent_trace': [], 'used_fallback': False, 'optimizer_output': {}}})}\n\n"

    with patch("backend.routes.generate.stream_agent_pipeline", side_effect=_mock_pipeline):
        res = await client.post("/generate/agents/stream", json={"user_story": VALID_STORY})
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
