"""
Agent Service — Pipeline de 3 agentes CrewAI para generación, revisión y optimización de test cases.

Agente 1 — Generador   : Produce la suite de test cases en JSON
Agente 2 — Revisor     : Evalúa cobertura, calidad y gaps de la suite generada
Agente 3 — Optimizador : Identifica y prioriza los casos críticos faltantes
"""

import asyncio
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from backend.config import OPIK_API_KEY, OPIK_WORKSPACE, OPIK_PROJECT_NAME
from backend.schemas.models import AgentGenerateRequest, AgentGenerateResponse, AgentTrace
from backend.services.llm_service import _parse_llm_output, _build_response

logger = logging.getLogger(__name__)

# ── Opik ─────────────────────────────────────────────────────────────────────
_OPIK_ENABLED = False
try:
    import opik
    if OPIK_API_KEY:
        opik.configure(api_key=OPIK_API_KEY, workspace=OPIK_WORKSPACE or None, force=True)
        _OPIK_ENABLED = True
except Exception:
    pass

# ── Executor para correr CrewAI (síncrono) desde código async ─────────────────
_executor = ThreadPoolExecutor(max_workers=1)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_optimizer_output(text: str) -> dict:
    """Extrae el JSON del output del Optimizador. Fallback a dict genérico."""
    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {
        "priority_gaps": [],
        "added_cases": [],
        "optimization_summary": "No se pudo parsear la respuesta del optimizador",
    }


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


def _build_agents_and_tasks(req: AgentGenerateRequest, rag_context: str):
    """Construye los agentes y tareas CrewAI reutilizables."""
    from crewai import Agent, Task, LLM

    model_tag = f"ollama/{req.model}"
    base_url  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    llm = LLM(model=model_tag, base_url=base_url, temperature=req.temperature)

    rag_section = (
        f"\n\nCONTEXTO DE BASE DE CONOCIMIENTO QA:\n{rag_context}\n"
        if rag_context else ""
    )

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
        llm=llm, allow_delegation=False, verbose=False,
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
        llm=llm, allow_delegation=False, verbose=False,
    )
    optimizer = Agent(
        role="QA Coverage Optimizer",
        goal="Identificar y priorizar los casos de prueba críticos faltantes en la suite generada, basándose en el análisis del Revisor",
        backstory=(
            "Eres un QA Architect especializado en análisis de brechas de cobertura. "
            "Recibes una suite de test cases y el análisis de calidad del Revisor, y produces "
            "una lista priorizada de los 3 casos más críticos que faltan, con su especificación completa. "
            "Siempre priorizas seguridad > rendimiento > casos de negocio críticos. "
            "Respondes SIEMPRE en español."
        ),
        llm=llm, allow_delegation=False, verbose=False,
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
    task_optimize = Task(
        description=(
            f"Basándote en la suite de test cases generada y el análisis del Revisor para la historia:\n\n"
            f"HISTORIA: {req.user_story}\n\n"
            "INSTRUCCIONES:\n"
            "1. Identifica los 3 casos de prueba más críticos que FALTAN en la suite\n"
            "2. Prioriza según: seguridad > rendimiento > casos de negocio críticos\n"
            "3. Para cada caso faltante, genera su especificación completa\n"
            "4. Explica por qué cada caso es crítico\n\n"
            "Responde SOLO con JSON:\n"
            '{"priority_gaps": [{"rank": 1, "category": "...", "reason": "...", '
            '"impact": "alto|medio"}], '
            '"added_cases": [{"id": "OPT-001", "title": "...", "category": "...", '
            '"priority": "alto|medio|bajo", "preconditions": ["..."], '
            '"steps": ["..."], "expected_result": "...", "test_type": "..."}], '
            '"optimization_summary": "texto breve de qué se optimizó"}'
        ),
        expected_output="JSON con priority_gaps, added_cases y optimization_summary",
        agent=optimizer,
        context=[task_generate, task_review],
    )

    return generator, reviewer, optimizer, task_generate, task_review, task_optimize


def _run_crew(req: AgentGenerateRequest, rag_context: str) -> dict:
    """Ejecuta el pipeline CrewAI de forma síncrona."""
    from crewai import Crew

    generator, reviewer, optimizer, task_generate, task_review, task_optimize = \
        _build_agents_and_tasks(req, rag_context)

    t0 = time.monotonic()
    Crew(agents=[generator], tasks=[task_generate], verbose=False).kickoff()
    t_gen = round(time.monotonic() - t0, 2)

    t1 = time.monotonic()
    Crew(agents=[reviewer], tasks=[task_review], verbose=False).kickoff()
    t_rev = round(time.monotonic() - t1, 2)

    t2 = time.monotonic()
    Crew(agents=[optimizer], tasks=[task_optimize], verbose=False).kickoff()
    t_opt = round(time.monotonic() - t2, 2)

    gen_output = task_generate.output.raw if task_generate.output else ""
    rev_output = task_review.output.raw   if task_review.output  else ""
    opt_output = task_optimize.output.raw if task_optimize.output else ""

    try:
        parsed_data = _parse_llm_output(gen_output)
    except Exception as exc:
        logger.warning("Error parseando output del Generador: %s", exc)
        parsed_data = {"test_cases": [], "edge_scenarios": [], "potential_bugs": [], "coverage_summary": {}}

    review         = _parse_reviewer_output(rev_output)
    optimizer_result = _parse_optimizer_output(opt_output)

    agent_trace = [
        AgentTrace(agent="Generador",   elapsed_s=t_gen,
                   summary=f"{len(parsed_data.get('test_cases', []))} casos generados"),
        AgentTrace(agent="Revisor",     elapsed_s=t_rev,
                   summary=f"Veredicto: {review.get('verdict', '?')} | Score: {review.get('score', 0):.2f}"),
        AgentTrace(agent="Optimizador", elapsed_s=t_opt,
                   summary=f"{len(optimizer_result.get('added_cases', []))} casos optimizados | {optimizer_result.get('optimization_summary', '')[:80]}"),
    ]

    return {
        "parsed_data": parsed_data,
        "agent_trace": agent_trace,
        "review": review,
        "optimizer_result": optimizer_result,
        "used_fallback": False,
    }


def _run_crew_streaming(req: AgentGenerateRequest, rag_context: str, put_event) -> None:
    """
    Igual que _run_crew pero llama a put_event() tras cada agente.
    Permite streaming SSE sin bloquear el event loop.
    """
    from crewai import Crew

    generator, reviewer, optimizer, task_generate, task_review, task_optimize = \
        _build_agents_and_tasks(req, rag_context)

    # ── Agente 1: Generador ──────────────────────────────────────────────────
    put_event({"event": "agent_start", "agent": "Generador", "step": 1, "total": 3})
    t0 = time.monotonic()
    Crew(agents=[generator], tasks=[task_generate], verbose=False).kickoff()
    t_gen = round(time.monotonic() - t0, 2)

    gen_output = task_generate.output.raw if task_generate.output else ""
    try:
        parsed_data = _parse_llm_output(gen_output)
    except Exception as exc:
        logger.warning("Error parseando output del Generador: %s", exc)
        parsed_data = {"test_cases": [], "edge_scenarios": [], "potential_bugs": [], "coverage_summary": {}}

    put_event({
        "event": "agent_done", "agent": "Generador", "step": 1,
        "elapsed_s": t_gen,
        "summary": f"{len(parsed_data.get('test_cases', []))} casos generados",
        "data": parsed_data,
    })

    # ── Agente 2: Revisor ────────────────────────────────────────────────────
    put_event({"event": "agent_start", "agent": "Revisor", "step": 2, "total": 3})
    t1 = time.monotonic()
    Crew(agents=[reviewer], tasks=[task_review], verbose=False).kickoff()
    t_rev = round(time.monotonic() - t1, 2)

    review = _parse_reviewer_output(task_review.output.raw if task_review.output else "")
    put_event({
        "event": "agent_done", "agent": "Revisor", "step": 2,
        "elapsed_s": t_rev,
        "summary": f"Veredicto: {review.get('verdict', '?')} | Score: {review.get('score', 0):.2f}",
        "data": review,
    })

    # ── Agente 3: Optimizador ────────────────────────────────────────────────
    put_event({"event": "agent_start", "agent": "Optimizador", "step": 3, "total": 3})
    t2 = time.monotonic()
    Crew(agents=[optimizer], tasks=[task_optimize], verbose=False).kickoff()
    t_opt = round(time.monotonic() - t2, 2)

    optimizer_result = _parse_optimizer_output(task_optimize.output.raw if task_optimize.output else "")
    put_event({
        "event": "agent_done", "agent": "Optimizador", "step": 3,
        "elapsed_s": t_opt,
        "summary": f"{len(optimizer_result.get('added_cases', []))} casos optimizados | {optimizer_result.get('optimization_summary', '')[:80]}",
        "data": optimizer_result,
    })

    # ── Evento final con respuesta completa ──────────────────────────────────
    generate_resp = _build_response(parsed_data, req.user_story)
    put_event({
        "event": "done",
        "data": {
            **generate_resp.model_dump(),
            "agent_trace": [
                {"agent": "Generador",   "elapsed_s": t_gen, "summary": f"{len(parsed_data.get('test_cases', []))} casos generados"},
                {"agent": "Revisor",     "elapsed_s": t_rev, "summary": f"Veredicto: {review.get('verdict', '?')} | Score: {review.get('score', 0):.2f}"},
                {"agent": "Optimizador", "elapsed_s": t_opt, "summary": f"{len(optimizer_result.get('added_cases', []))} casos optimizados"},
            ],
            "used_fallback": False,
            "optimizer_output": optimizer_result,
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# Función principal (async)
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent_pipeline(
    req: AgentGenerateRequest,
    rag_context: str = "",
) -> AgentGenerateResponse:
    """
    Ejecuta el pipeline de 3 agentes CrewAI de forma asíncrona.
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

        parsed_data     = result["parsed_data"]
        agent_trace     = result["agent_trace"]
        review          = result["review"]
        optimizer_result = result.get("optimizer_result", {})
        used_fallback   = result["used_fallback"]

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
        optimizer_result = {}
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
        optimizer_output=optimizer_result,
    )


async def stream_agent_pipeline(
    req: AgentGenerateRequest,
    rag_context: str = "",
):
    """
    Async generator SSE. Emite un evento tras cada agente:
      agent_start → agent_done (con datos parciales) → done (respuesta completa)
    El frontend puede renderizar los test cases en cuanto el Generador termina.
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def put_event(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _run() -> None:
        try:
            _run_crew_streaming(req, rag_context, put_event)
        except Exception as exc:
            logger.error("Error en pipeline streaming: %s", exc)
            put_event({"event": "error", "message": str(exc)})

    loop.run_in_executor(_executor, _run)

    while True:
        event = await queue.get()
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if event.get("event") in ("done", "error"):
            break
