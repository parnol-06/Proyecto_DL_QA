"""Tests para backend/services/agent_service.py"""
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from backend.schemas.models import AgentGenerateRequest

VALID_STORY = "Como usuario quiero iniciar sesión con email y contraseña para acceder a mi cuenta personal."


# ── _parse_reviewer_output ─────────────────────────────────────────────────────

def test_parse_reviewer_output_valid_json():
    from backend.services.agent_service import _parse_reviewer_output
    text = json.dumps({
        "verdict": "APROBADO",
        "score": 0.85,
        "gaps": [],
        "strengths": ["Cobertura completa"],
        "recommendation": "Sin cambios necesarios"
    })
    result = _parse_reviewer_output(text)
    assert result["verdict"] == "APROBADO"
    assert result["score"] == 0.85

def test_parse_reviewer_output_fallback_on_invalid():
    from backend.services.agent_service import _parse_reviewer_output
    result = _parse_reviewer_output("Texto plano sin JSON")
    assert "verdict" in result
    assert "score" in result
    assert result["score"] == 0.5  # valor de fallback

# ── _parse_optimizer_output ────────────────────────────────────────────────────

def test_parse_optimizer_output_valid_json():
    from backend.services.agent_service import _parse_optimizer_output
    text = json.dumps({
        "priority_gaps": [{"rank": 1, "category": "seguridad", "reason": "Falta SQL injection", "impact": "alto"}],
        "added_cases": [],
        "optimization_summary": "Se identificó brecha de seguridad"
    })
    result = _parse_optimizer_output(text)
    assert len(result["priority_gaps"]) == 1
    assert result["priority_gaps"][0]["rank"] == 1

def test_parse_optimizer_output_fallback_on_invalid():
    from backend.services.agent_service import _parse_optimizer_output
    result = _parse_optimizer_output("respuesta no estructurada del modelo")
    assert "priority_gaps" in result
    assert result["priority_gaps"] == []
    assert "added_cases" in result

# ── run_agent_pipeline fallback ────────────────────────────────────────────────

async def test_run_agent_pipeline_uses_fallback_when_crewai_fails():
    """Cuando CrewAI lanza excepción, el pipeline usa fallback directo (generate_test_cases)."""
    from backend.services.agent_service import run_agent_pipeline

    mock_fallback_resp = MagicMock()
    mock_fallback_resp.test_cases = [
        {"id": "TC-001", "title": "Login", "category": "happy_path",
         "priority": "alto", "preconditions": [], "steps": ["paso"], "expected_result": "OK", "test_type": "funcional"}
    ]
    mock_fallback_resp.edge_scenarios = []
    mock_fallback_resp.potential_bugs = []
    mock_fallback_resp.coverage_summary = {"total_test_cases": 1, "categories_covered": [], "estimated_coverage_percent": 50, "missing_areas": []}
    mock_fallback_resp.model_dump.return_value = {
        "test_cases": mock_fallback_resp.test_cases,
        "edge_scenarios": [], "potential_bugs": [], "coverage_summary": mock_fallback_resp.coverage_summary,
        "raw_story": VALID_STORY,
    }

    req = AgentGenerateRequest(user_story=VALID_STORY)

    with patch("backend.services.agent_service._run_crew", side_effect=Exception("CrewAI no disponible")), \
         patch("backend.services.agent_service.asyncio.get_event_loop") as mock_loop:
        # Simular que run_in_executor lanza la excepción del _run_crew
        mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("CrewAI no disponible"))
        with patch("backend.services.llm_service.generate_test_cases", return_value=mock_fallback_resp):
            result = await run_agent_pipeline(req)

    assert result.used_fallback is True
    assert len(result.agent_trace) == 1
    assert "Fallback" in result.agent_trace[0].agent

async def test_run_agent_pipeline_returns_3_traces_on_success():
    """En ejecución exitosa, agent_trace tiene exactamente 3 entradas."""
    from backend.services.agent_service import run_agent_pipeline

    mock_crew_result = {
        "parsed_data": {
            "test_cases": [{"id": "TC-001", "title": "T", "category": "happy_path",
                            "priority": "alto", "preconditions": [], "steps": ["s"],
                            "expected_result": "ok", "test_type": "funcional"}],
            "edge_scenarios": [], "potential_bugs": [],
            "coverage_summary": {"total_test_cases": 1, "categories_covered": [], "estimated_coverage_percent": 75, "missing_areas": []}
        },
        "agent_trace": [
            MagicMock(agent="Generador", elapsed_s=10.0, summary="1 casos generados"),
            MagicMock(agent="Revisor", elapsed_s=5.0, summary="Veredicto: APROBADO | Score: 0.85"),
            MagicMock(agent="Optimizador", elapsed_s=4.0, summary="2 casos optimizados"),
        ],
        "review": {"verdict": "APROBADO", "score": 0.85, "gaps": [], "strengths": [], "recommendation": "OK"},
        "optimizer_result": {"priority_gaps": [], "added_cases": [], "optimization_summary": "OK"},
        "used_fallback": False,
    }

    req = AgentGenerateRequest(user_story=VALID_STORY)

    with patch("backend.services.agent_service.asyncio.get_event_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_crew_result)
        result = await run_agent_pipeline(req)

    assert result.used_fallback is False
    assert len(result.agent_trace) == 3
