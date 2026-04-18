"""
Agent Service — Pipeline de 2 agentes CrewAI para generación y revisión de test cases.

Agente 1 — Generador : Produce la suite de test cases en JSON
Agente 2 — Revisor   : Evalúa cobertura, calidad y gaps de la suite generada
"""

import asyncio
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from backend.config import OPIK_API_KEY, OPIK_PROJECT_NAME
from backend.schemas.models import AgentGenerateRequest, AgentGenerateResponse, AgentTrace
from backend.services.llm_service import _parse_llm_output, _build_response

logger = logging.getLogger(__name__)

# ── Opik (reutiliza la misma configuración que llm_service) ───────────────────
_OPIK_ENABLED = False
try:
    import opik
    _OPIK_ENABLED = bool(OPIK_API_KEY)
except ImportError:
    pass

# ── Executor para correr CrewAI (síncrono) desde código async ─────────────────
_executor = ThreadPoolExecutor(max_workers=1)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_reviewer_output(text: str) -> dict:
    """Extrae el JSON del output del Revisor. Fallback a dict genérico."""
    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {
        "verdict": "OBSERVACIONES",
        "score": 0.5,
        "gaps": ["No se pudo parsear la respuesta del revisor"],
        "strengths": [],
        "recommendation": text[:200] if text else "Sin respuesta",
    }


def _run_crew(req: AgentGenerateRequest, rag_context: str) -> dict:
    """
    Ejecuta el pipeline CrewAI de forma síncrona.
    Retorna dict con los campos de AgentGenerateResponse.
    """
    from crewai import Agent, Task, Crew, LLM

    model_tag = f"ollama/{req.model}"
    base_url   = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    llm = LLM(model=model_tag, base_url=base_url, temperature=req.temperature)

    # ── Definición de agentes ─────────────────────────────────────────────────
    generator = Agent(
        role="QA Test Case Generator",
        goal="Generar una suite completa y detallada de casos de prueba estructurados en JSON para la historia de usuario indicada",
        backstory=(
            "Eres un ingeniero QA senior con 15 años de experiencia en pruebas de software. "
            "Conoces a fondo técnicas como partición de equivalencia, análisis de valores límite "
            "y pruebas de seguridad. Siempre generas al menos 12 casos de prueba cubriendo todas "
            "las categorías: happy_path, caso_limite, negativo, seguridad, rendimiento, "
            "usabilidad y compatibilidad. Cada caso tiene mínimo 5 pasos detallados y "
            "criterios de aceptación medibles. Respondes SIEMPRE en español."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )

    reviewer = Agent(
        role="QA Quality Reviewer",
        goal="Evaluar la calidad, cobertura y estructura de una suite de test cases y emitir un veredicto fundamentado",
        backstory=(
            "Eres un QA Lead con amplia experiencia auditando suites de prueba. "
            "Verificas que todos los tipos de prueba estén cubiertos, que los pasos sean "
            "específicos y que los casos no funcionales tengan criterios cuantitativos. "
            "Eres crítico pero constructivo. Respondes SIEMPRE en español."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )

    # ── Definición de tareas ──────────────────────────────────────────────────
    rag_section = (
        f"\n\nCONTEXTO DE BASE DE CONOCIMIENTO QA:\n{rag_context}\n"
        if rag_context else ""
    )

    task_generate = Task(
        description=(
            f"Genera una suite completa de casos de prueba para la siguiente historia de usuario.\n\n"
            f"HISTORIA DE USUARIO:\n{req.user_story}\n\n"
            f"CONTEXTO ADICIONAL: {req.context or 'Ninguno'}"
            f"{rag_section}\n\n"
            "INSTRUCCIONES:\n"
            "- Genera MÍNIMO 12 casos de prueba\n"
            "- Cubre las 7 categorías: happy_path, caso_limite, negativo, seguridad, rendimiento, usabilidad, compatibilidad\n"
            "- Cada caso debe tener mínimo 5 pasos detallados y específicos\n"
            "- Los casos de rendimiento deben incluir valores numéricos concretos (tiempos, usuarios)\n"
            "- Los casos de seguridad deben especificar el vector de ataque\n"
            "- Responde SOLO con JSON válido, sin texto adicional\n\n"
            "FORMATO JSON REQUERIDO:\n"
            '{"test_cases": [{"id": "TC-001", "title": "...", "category": "...", "priority": "alto|medio|bajo", '
            '"preconditions": ["..."], "steps": ["..."], "expected_result": "...", "test_type": "..."}], '
            '"edge_scenarios": [{"id": "ES-001", "scenario": "...", "risk_level": "...", "description": "..."}], '
            '"potential_bugs": [{"id": "BUG-001", "title": "...", "area": "...", "likelihood": "...", '
            '"description": "...", "suggested_test": "..."}], '
            '"coverage_summary": {"total_test_cases": 0, "categories_covered": [], '
            '"estimated_coverage_percent": 0, "missing_areas": []}}'
        ),
        expected_output="JSON válido con test_cases, edge_scenarios, potential_bugs y coverage_summary",
        agent=generator,
    )

    task_review = Task(
        description=(
            f"Revisa la suite de test cases generada para la siguiente historia de usuario.\n\n"
            f"HISTORIA DE USUARIO:\n{req.user_story}\n\n"
            "EVALÚA:\n"
            "1. ¿Están cubiertas las 7 categorías?\n"
            "2. ¿Los pasos son específicos y medibles?\n"
            "3. ¿Los casos de rendimiento tienen valores numéricos?\n"
            "4. ¿Los casos de seguridad especifican el vector de ataque?\n"
            "5. ¿Hay casos críticos faltantes?\n\n"
            "Responde SOLO con JSON:\n"
            '{"verdict": "APROBADO|OBSERVACIONES|RECHAZADO", "score": 0.0-1.0, '
            '"gaps": ["gap1"], "strengths": ["fortaleza1"], "recommendation": "texto breve"}'
        ),
        expected_output="JSON con verdict, score, gaps, strengths y recommendation",
        agent=reviewer,
        context=[task_generate],
    )

    # ── Ejecutar Crew ─────────────────────────────────────────────────────────
    crew = Crew(
        agents=[generator, reviewer],
        tasks=[task_generate, task_review],
        verbose=False,
    )

    t0 = time.monotonic()
    result = crew.kickoff()
    total_elapsed = time.monotonic() - t0

    # Extraer outputs de cada tarea
    gen_output = task_generate.output.raw if task_generate.output else ""
    rev_output = task_review.output.raw  if task_review.output  else ""

    # Parsear test cases del Agente 1
    try:
        parsed_data = _parse_llm_output(gen_output)
    except Exception as exc:
        logger.warning("Error parseando output del Generador: %s", exc)
        parsed_data = {"test_cases": [], "edge_scenarios": [], "potential_bugs": [], "coverage_summary": {}}

    # Parsear revisión del Agente 2
    review = _parse_reviewer_output(rev_output)

    # Construir trazas de agentes
    agent_trace = [
        AgentTrace(
            agent="Generador",
            elapsed_s=round(total_elapsed * 0.65, 2),
            summary=f"{len(parsed_data.get('test_cases', []))} casos generados",
        ),
        AgentTrace(
            agent="Revisor",
            elapsed_s=round(total_elapsed * 0.35, 2),
            summary=f"Veredicto: {review.get('verdict', '?')} | Score: {review.get('score', 0):.2f}",
        ),
    ]

    return {
        "parsed_data": parsed_data,
        "agent_trace": agent_trace,
        "review": review,
        "used_fallback": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Función principal (async)
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent_pipeline(
    req: AgentGenerateRequest,
    rag_context: str = "",
) -> AgentGenerateResponse:
    """
    Ejecuta el pipeline de 2 agentes CrewAI de forma asíncrona.
    Hace fallback a generate_test_cases si CrewAI falla.
    """
    opik_trace = None
    if _OPIK_ENABLED:
        try:
            _client = opik.Opik()
            opik_trace = _client.trace(
                name="agent_pipeline",
                input={
                    "user_story": req.user_story[:300],
                    "model": req.model,
                    "use_rag": bool(rag_context),
                },
                project_name=OPIK_PROJECT_NAME,
            )
        except Exception:
            pass

    try:
        # Correr CrewAI en executor para no bloquear el event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            lambda: _run_crew(req, rag_context),
        )

        parsed_data  = result["parsed_data"]
        agent_trace  = result["agent_trace"]
        review       = result["review"]
        used_fallback = result["used_fallback"]

    except Exception as exc:
        logger.error("CrewAI falló, usando fallback directo | %s", exc)
        # Fallback: generar directamente con llm_service
        from backend.schemas.models import GenerateRequest
        from backend.services.llm_service import generate_test_cases

        fallback_req = GenerateRequest(
            user_story=req.user_story,
            model=req.model,
            context=req.context,
            temperature=req.temperature,
        )
        fallback_resp = await generate_test_cases(fallback_req)
        parsed_data = fallback_resp.model_dump()
        agent_trace = [
            AgentTrace(agent="Fallback (sin agentes)", elapsed_s=0.0, summary=f"Error CrewAI: {str(exc)[:80]}")
        ]
        review = {}
        used_fallback = True

    # Cerrar traza Opik
    if opik_trace:
        try:
            review_summary = review.get("verdict", "N/A") if review else "fallback"
            opik_trace.end(output={
                "tc_count": len(parsed_data.get("test_cases", [])),
                "review_verdict": review_summary,
                "used_fallback": used_fallback,
            })
        except Exception:
            pass

    generate_resp = _build_response(parsed_data, req.user_story)

    return AgentGenerateResponse(
        test_cases=generate_resp.test_cases,
        edge_scenarios=generate_resp.edge_scenarios,
        potential_bugs=generate_resp.potential_bugs,
        coverage_summary=generate_resp.coverage_summary,
        raw_story=req.user_story,
        agent_trace=agent_trace,
        used_fallback=used_fallback,
    )
