"""
Agent Service — Pipeline de 3 agentes CrewAI con observabilidad completa.

Span hierarchy produced:

crew_pipeline
├── agent_1_generador
│   ├── llm_call_generador   ← wraps Crew.kickoff() to capture timing
│   └── llm_json_parse
├── agent_2_revisor
│   └── llm_call_revisor
└── agent_3_optimizador
    └── llm_call_optimizador

Feedback scores per agent:
- tc_completeness (Generador)
- reviewer_score  (Revisor)
- optimization_coverage (Optimizador)

Pipeline-level feedback scores:
- reviewer_score, coverage_pct, tc_completeness
"""

import asyncio
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor

from backend.config import OLLAMA_HOST
from backend.observability import tracer
from backend.schemas.models import AgentGenerateRequest, AgentGenerateResponse, AgentTrace
from backend.services.llm_service import _parse_llm_output, _build_response

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)


# ─────────────────────────────────────────────────────────────────────────────
# Output parsers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_optimizer_output(text: str) -> dict:
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


def _build_category_dist(tc_count: int, categories: list) -> list[tuple[str, int]]:
    n = len(categories)
    if n == 0:
        return []
    base, rem = divmod(tc_count, n)
    return [(cat, base + (1 if i < rem else 0)) for i, cat in enumerate(categories)]


def _build_agents_and_tasks(req: AgentGenerateRequest, rag_context: str):
    from crewai import Agent, Task, LLM

    model_tag   = f"ollama/{req.model}"
    max_tokens  = max(4096, req.tc_count * 280 + req.edge_count * 120 + req.bug_count * 160 + 1000)
    llm = LLM(model=model_tag, base_url=OLLAMA_HOST, temperature=req.temperature, max_tokens=max_tokens)

    rag_section = (
        f"\n\nCONTEXTO DE BASE DE CONOCIMIENTO QA:\n{rag_context}\n"
        if rag_context else ""
    )

    all_cats   = ["happy_path", "caso_limite", "negativo", "seguridad", "rendimiento", "usabilidad", "compatibilidad"]
    active_cats = req.categories if req.categories else all_cats
    tc_count    = getattr(req, "tc_count",   10)
    edge_count  = getattr(req, "edge_count",  4)
    bug_count   = getattr(req, "bug_count",   3)
    dist        = _build_category_dist(tc_count, active_cats)
    dist_lines  = "\n".join(f"  - {cat}: {count} caso{'s' if count != 1 else ''}" for cat, count in dist)

    generator = Agent(
        role="QA Test Case Generator",
        goal=f"Generar exactamente {tc_count} casos de prueba distribuidos por categoría según las instrucciones de la tarea",
        backstory=(
            "Eres un ingeniero QA senior con 15 años de experiencia en pruebas de software. "
            "Conoces a fondo técnicas como partición de equivalencia, análisis de valores límite "
            "y pruebas de seguridad. Generas EXACTAMENTE la cantidad de casos solicitada, "
            "respetando escrupulosamente la distribución por categorías indicada. "
            "Cada caso tiene mínimo 5 pasos detallados y criterios de aceptación medibles. "
            "Respondes SIEMPRE en español."
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
            f"Genera una suite de casos de prueba para la siguiente historia de usuario.\n\n"
            f"HISTORIA DE USUARIO:\n{req.user_story}\n\n"
            f"CONTEXTO ADICIONAL: {req.context or 'Ninguno'}"
            f"{rag_section}\n\n"
            f"DISTRIBUCION EXACTA DE TEST CASES A GENERAR (total: {tc_count}):\n"
            f"{dist_lines}\n\n"
            "INSTRUCCIONES:\n"
            f"- Genera EXACTAMENTE {tc_count} test cases respetando la distribución anterior\n"
            f"- El campo 'category' de cada caso DEBE ser exactamente uno de: {', '.join(active_cats)}\n"
            f"- Genera EXACTAMENTE {edge_count} edge scenarios\n"
            f"- Genera EXACTAMENTE {bug_count} bugs potenciales\n"
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


# ─────────────────────────────────────────────────────────────────────────────
# Synchronous crew executor (runs in thread pool)
# ─────────────────────────────────────────────────────────────────────────────

def _run_crew(req: AgentGenerateRequest, rag_context: str) -> dict:
    """
    Executes the 3-agent CrewAI pipeline synchronously.
    Runs in a thread executor — ContextVars are inherited (Python 3.7+).

    Each Crew.kickoff() is wrapped in llm_inference_span so the LLM call
    timing is captured as a named span in the Opik trace hierarchy.
    """
    from crewai import Crew

    generator, reviewer, optimizer, task_generate, task_review, task_optimize = \
        _build_agents_and_tasks(req, rag_context)

    parsed_data: dict = {}
    review: dict = {}
    optimizer_result: dict = {}
    t_gen = t_rev = t_opt = 0.0
    tc_count_generated = 0
    verdict = "?"
    rev_score = 0.0
    added_count = 0
    opt_summary = ""

    with tracer.crew_pipeline_span(req.tc_count, req.model, bool(rag_context)) as pipeline_s:

        # ── Agente 1: Generador ──────────────────────────────────────────────
        with tracer.agent_span("Generador", "QA Test Case Generator", step=1, total=3) as s:
            t0 = time.monotonic()
            with tracer.llm_inference_span("Generador", req.model, task_generate.description[:200]):
                Crew(agents=[generator], tasks=[task_generate], verbose=False).kickoff()
            t_gen = round(time.monotonic() - t0, 2)

            gen_output = task_generate.output.raw if task_generate.output else ""
            with tracer.parse_span(len(gen_output), component="crewai_generator_output") as ps:
                try:
                    parsed_data = _parse_llm_output(gen_output)
                    tracer.update_span(ps, output={
                        "success": True,
                        "tc_count": len(parsed_data.get("test_cases", [])),
                    })
                except Exception as exc:
                    tracer.update_span(ps, output={"success": False, "reason": str(exc)[:200]})
                    logger.warning("Error parseando output del Generador: %s", exc)
                    parsed_data = {"test_cases": [], "edge_scenarios": [], "potential_bugs": [], "coverage_summary": {}}

            tc_count_generated = len(parsed_data.get("test_cases", []))
            tc_completeness = min(1.0, tc_count_generated / max(1, req.tc_count))

            tracer.update_span(
                s,
                output={
                    "tc_count": tc_count_generated,
                    "edge_count": len(parsed_data.get("edge_scenarios", [])),
                    "bug_count": len(parsed_data.get("potential_bugs", [])),
                    "output_chars": len(gen_output),
                },
                metadata={
                    "elapsed_s": t_gen,
                    "agent": "Generador",
                    "model": req.model,
                },
            )
            tracer.log_feedback_score(s, "tc_completeness", tc_completeness, "generation",
                                      reason=f"{tc_count_generated}/{req.tc_count} test cases generados")

        # ── Agente 2: Revisor ────────────────────────────────────────────────
        with tracer.agent_span("Revisor", "QA Quality Reviewer", step=2, total=3) as s:
            t1 = time.monotonic()
            with tracer.llm_inference_span("Revisor", req.model, task_review.description[:200]):
                Crew(agents=[reviewer], tasks=[task_review], verbose=False).kickoff()
            t_rev = round(time.monotonic() - t1, 2)

            rev_output = task_review.output.raw if task_review.output else ""
            review = _parse_reviewer_output(rev_output)
            verdict = review.get("verdict", "?")
            rev_score = float(review.get("score", 0.0))

            tracer.update_span(
                s,
                output={
                    "verdict": verdict,
                    "score": rev_score,
                    "gaps": review.get("gaps", [])[:5],
                    "strengths": review.get("strengths", [])[:3],
                    "recommendation": review.get("recommendation", "")[:300],
                },
                metadata={
                    "elapsed_s": t_rev,
                    "agent": "Revisor",
                    "model": req.model,
                },
            )
            tracer.log_feedback_score(s, "reviewer_score", rev_score, "quality",
                                      reason=f"Veredicto: {verdict}")

        # ── Agente 3: Optimizador ────────────────────────────────────────────
        with tracer.agent_span("Optimizador", "QA Coverage Optimizer", step=3, total=3) as s:
            t2 = time.monotonic()
            with tracer.llm_inference_span("Optimizador", req.model, task_optimize.description[:200]):
                Crew(agents=[optimizer], tasks=[task_optimize], verbose=False).kickoff()
            t_opt = round(time.monotonic() - t2, 2)

            opt_output = task_optimize.output.raw if task_optimize.output else ""
            optimizer_result = _parse_optimizer_output(opt_output)
            added_count = len(optimizer_result.get("added_cases", []))
            opt_summary = optimizer_result.get("optimization_summary", "")
            optimization_ratio = min(1.0, added_count / 3) if added_count > 0 else 0.0

            tracer.update_span(
                s,
                output={
                    "added_cases_count": added_count,
                    "priority_gaps_count": len(optimizer_result.get("priority_gaps", [])),
                    "optimization_summary": opt_summary[:300],
                },
                metadata={
                    "elapsed_s": t_opt,
                    "agent": "Optimizador",
                    "model": req.model,
                },
            )
            tracer.log_feedback_score(s, "optimization_coverage", optimization_ratio, "generation",
                                      reason=f"{added_count} casos críticos agregados")

        # ── Pipeline summary ─────────────────────────────────────────────────
        coverage_raw = parsed_data.get("coverage_summary", {})
        coverage_pct = (
            float(coverage_raw.get("estimated_coverage_percent", 0)) / 100.0
            if isinstance(coverage_raw, dict) else 0.0
        )
        total_elapsed = round(t_gen + t_rev + t_opt, 2)

        tracer.update_span(
            pipeline_s,
            output={
                "tc_count_generated": tc_count_generated,
                "reviewer_verdict": verdict,
                "reviewer_score": rev_score,
                "optimizer_added": added_count,
                "total_elapsed_s": total_elapsed,
                "coverage_pct": round(coverage_pct * 100, 1),
            },
            metadata={
                "model": req.model,
                "rag_used": bool(rag_context),
                "agent_count": 3,
            },
        )
        tracer.log_pipeline_feedback(pipeline_s, {
            "reviewer_score":   (rev_score, "quality", f"Veredicto del Revisor: {verdict}"),
            "coverage_pct":     (min(1.0, coverage_pct), "generation", "Cobertura estimada de categorías"),
            "tc_completeness":  (min(1.0, tc_count_generated / max(1, req.tc_count)), "generation",
                                 f"{tc_count_generated}/{req.tc_count} test cases"),
            "optimization_coverage": (min(1.0, added_count / 3) if added_count else 0.0, "generation",
                                      f"{added_count} casos añadidos por optimizador"),
        })

    return {
        "parsed_data": parsed_data,
        "agent_trace": [
            AgentTrace(agent="Generador",   elapsed_s=t_gen,
                       summary=f"{tc_count_generated} casos generados"),
            AgentTrace(agent="Revisor",     elapsed_s=t_rev,
                       summary=f"Veredicto: {verdict} | Score: {rev_score:.2f}"),
            AgentTrace(agent="Optimizador", elapsed_s=t_opt,
                       summary=f"{added_count} casos optimizados | {opt_summary[:80]}"),
        ],
        "review": review,
        "optimizer_result": optimizer_result,
        "used_fallback": False,
        "reviewer_score": rev_score,
        "reviewer_verdict": verdict,
        "coverage_pct": coverage_pct,
    }


def _run_crew_streaming(req: AgentGenerateRequest, rag_context: str, put_event) -> None:
    """
    Same as _run_crew but calls put_event() after each agent.
    Runs in thread executor — ContextVars are inherited.
    """
    from crewai import Crew

    generator, reviewer, optimizer, task_generate, task_review, task_optimize = \
        _build_agents_and_tasks(req, rag_context)

    parsed_data: dict = {}
    review: dict = {}
    optimizer_result: dict = {}
    t_gen = t_rev = t_opt = 0.0
    tc_count_generated = 0
    verdict = "?"
    rev_score = 0.0
    added_count = 0
    opt_summary = ""

    with tracer.crew_pipeline_span(req.tc_count, req.model, bool(rag_context)) as pipeline_s:

        # ── Agente 1: Generador ──────────────────────────────────────────────
        put_event({"event": "agent_start", "agent": "Generador", "step": 1, "total": 3})
        with tracer.agent_span("Generador", "QA Test Case Generator", step=1, total=3) as s:
            t0 = time.monotonic()
            with tracer.llm_inference_span("Generador", req.model, task_generate.description[:200]):
                Crew(agents=[generator], tasks=[task_generate], verbose=False).kickoff()
            t_gen = round(time.monotonic() - t0, 2)

            gen_output = task_generate.output.raw if task_generate.output else ""
            with tracer.parse_span(len(gen_output), component="crewai_generator_output") as ps:
                try:
                    parsed_data = _parse_llm_output(gen_output)
                    tracer.update_span(ps, output={
                        "success": True,
                        "tc_count": len(parsed_data.get("test_cases", [])),
                    })
                except Exception as exc:
                    tracer.update_span(ps, output={"success": False, "reason": str(exc)[:200]})
                    logger.warning("Error parseando output del Generador: %s", exc)
                    parsed_data = {"test_cases": [], "edge_scenarios": [], "potential_bugs": [], "coverage_summary": {}}

            tc_count_generated = len(parsed_data.get("test_cases", []))
            tc_completeness = min(1.0, tc_count_generated / max(1, req.tc_count))

            tracer.update_span(
                s,
                output={
                    "tc_count": tc_count_generated,
                    "edge_count": len(parsed_data.get("edge_scenarios", [])),
                    "output_chars": len(gen_output),
                },
                metadata={"elapsed_s": t_gen, "agent": "Generador"},
            )
            tracer.log_feedback_score(s, "tc_completeness", tc_completeness, "generation",
                                      reason=f"{tc_count_generated}/{req.tc_count} casos generados")

        for tc in parsed_data.get("test_cases") or []:
            put_event({"event": "case", "case": tc})
        put_event({
            "event": "agent_done", "agent": "Generador", "step": 1,
            "elapsed_s": t_gen,
            "summary": f"{tc_count_generated} casos generados",
            "data": parsed_data,
        })

        # ── Agente 2: Revisor ────────────────────────────────────────────────
        put_event({"event": "agent_start", "agent": "Revisor", "step": 2, "total": 3})
        with tracer.agent_span("Revisor", "QA Quality Reviewer", step=2, total=3) as s:
            t1 = time.monotonic()
            with tracer.llm_inference_span("Revisor", req.model, task_review.description[:200]):
                Crew(agents=[reviewer], tasks=[task_review], verbose=False).kickoff()
            t_rev = round(time.monotonic() - t1, 2)

            rev_output = task_review.output.raw if task_review.output else ""
            review = _parse_reviewer_output(rev_output)
            verdict = review.get("verdict", "?")
            rev_score = float(review.get("score", 0.0))

            tracer.update_span(
                s,
                output={
                    "verdict": verdict,
                    "score": rev_score,
                    "gaps": review.get("gaps", [])[:5],
                    "strengths": review.get("strengths", [])[:3],
                    "recommendation": review.get("recommendation", "")[:300],
                },
                metadata={"elapsed_s": t_rev, "agent": "Revisor"},
            )
            tracer.log_feedback_score(s, "reviewer_score", rev_score, "quality",
                                      reason=f"Veredicto: {verdict}")

        put_event({
            "event": "agent_done", "agent": "Revisor", "step": 2,
            "elapsed_s": t_rev,
            "summary": f"Veredicto: {verdict} | Score: {rev_score:.2f}",
            "data": review,
        })

        # ── Agente 3: Optimizador ────────────────────────────────────────────
        put_event({"event": "agent_start", "agent": "Optimizador", "step": 3, "total": 3})
        with tracer.agent_span("Optimizador", "QA Coverage Optimizer", step=3, total=3) as s:
            t2 = time.monotonic()
            with tracer.llm_inference_span("Optimizador", req.model, task_optimize.description[:200]):
                Crew(agents=[optimizer], tasks=[task_optimize], verbose=False).kickoff()
            t_opt = round(time.monotonic() - t2, 2)

            opt_output = task_optimize.output.raw if task_optimize.output else ""
            optimizer_result = _parse_optimizer_output(opt_output)
            added_count = len(optimizer_result.get("added_cases", []))
            opt_summary = optimizer_result.get("optimization_summary", "")
            optimization_ratio = min(1.0, added_count / 3) if added_count > 0 else 0.0

            tracer.update_span(
                s,
                output={
                    "added_cases_count": added_count,
                    "priority_gaps_count": len(optimizer_result.get("priority_gaps", [])),
                    "optimization_summary": opt_summary[:300],
                },
                metadata={"elapsed_s": t_opt, "agent": "Optimizador"},
            )
            tracer.log_feedback_score(s, "optimization_coverage", optimization_ratio, "generation",
                                      reason=f"{added_count} casos críticos agregados")

        for tc in optimizer_result.get("added_cases") or []:
            put_event({"event": "case", "case": tc})
        put_event({
            "event": "agent_done", "agent": "Optimizador", "step": 3,
            "elapsed_s": t_opt,
            "summary": f"{added_count} casos optimizados | {opt_summary[:80]}",
            "data": optimizer_result,
        })

        # ── Pipeline summary ─────────────────────────────────────────────────
        coverage_raw = parsed_data.get("coverage_summary", {})
        coverage_pct = (
            float(coverage_raw.get("estimated_coverage_percent", 0)) / 100.0
            if isinstance(coverage_raw, dict) else 0.0
        )

        tracer.update_span(
            pipeline_s,
            output={
                "tc_count_generated": tc_count_generated,
                "reviewer_verdict": verdict,
                "reviewer_score": rev_score,
                "optimizer_added": added_count,
                "total_elapsed_s": round(t_gen + t_rev + t_opt, 2),
            },
        )
        tracer.log_pipeline_feedback(pipeline_s, {
            "reviewer_score":        (rev_score, "quality", f"Veredicto: {verdict}"),
            "coverage_pct":          (min(1.0, coverage_pct), "generation"),
            "tc_completeness":       (min(1.0, tc_count_generated / max(1, req.tc_count)), "generation"),
            "optimization_coverage": (min(1.0, added_count / 3) if added_count else 0.0, "generation"),
        })

    generate_resp = _build_response(parsed_data, req.user_story)
    put_event({
        "event": "done",
        "data": {
            **generate_resp.model_dump(),
            "agent_trace": [
                {"agent": "Generador",   "elapsed_s": t_gen, "summary": f"{tc_count_generated} casos generados"},
                {"agent": "Revisor",     "elapsed_s": t_rev, "summary": f"Veredicto: {verdict} | Score: {rev_score:.2f}"},
                {"agent": "Optimizador", "elapsed_s": t_opt, "summary": f"{added_count} casos optimizados"},
            ],
            "used_fallback": False,
            "optimizer_output": optimizer_result,
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# Async entry points (called from generate routes within root_trace)
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent_pipeline(
    req: AgentGenerateRequest,
    rag_context: str = "",
) -> AgentGenerateResponse:
    """
    Executes the 3-agent CrewAI pipeline asynchronously.
    Trace context propagates to the thread executor (Python 3.7+).
    Falls back to generate_test_cases() if CrewAI fails.
    """
    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _run_crew(req, rag_context)),
            timeout=300.0,
        )

        parsed_data      = result["parsed_data"]
        agent_trace      = result["agent_trace"]
        review           = result["review"]
        optimizer_result = result.get("optimizer_result", {})
        used_fallback    = result["used_fallback"]

    except Exception as exc:
        logger.error("CrewAI falló, usando fallback directo | %s", exc)
        tracer.record_error(exc, component="crewai", pipeline="generate_agents")

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
            AgentTrace(agent="Fallback (sin agentes)", elapsed_s=0.0,
                       summary=f"Error CrewAI: {str(exc)[:80]}")
        ]
        review = {}
        optimizer_result = {}
        used_fallback = True

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
    Async generator SSE. Emits one event per agent.
    Trace context propagates to the thread executor.
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
            tracer.record_error(exc, component="crewai", pipeline="generate_agents_stream")
            put_event({"event": "error", "message": str(exc)})

    loop.run_in_executor(_executor, _run)

    while True:
        event = await queue.get()
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if event.get("event") in ("done", "error"):
            break
