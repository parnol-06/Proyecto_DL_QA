"""
Agent Service — 3-agent CrewAI pipeline with full observability.

Span hierarchy produced:

crew_pipeline
├── agent_generator
│   ├── llm_call_generator   ← wraps Crew.kickoff() to capture timing
│   └── llm_json_parse
├── agent_reviewer
│   └── llm_call_reviewer
└── agent_optimizer
    └── llm_call_optimizer

Feedback scores per agent:
- tc_completeness (Generator)
- reviewer_score  (Reviewer)
- optimization_coverage (Optimizer)

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
        "optimization_summary": "Could not parse optimizer response",
    }


def _parse_reviewer_output(text: str) -> dict:
    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {
        "verdict": "OBSERVATIONS",
        "score": 0.5,
        "gaps": ["Could not parse reviewer response"],
        "strengths": [],
        "recommendation": text[:200] if text else "No response",
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
        f"\n\nQA KNOWLEDGE BASE CONTEXT:\n{rag_context}\n"
        if rag_context else ""
    )

    all_cats   = ["happy_path", "edge_case", "negative", "security", "performance", "usability", "compatibility"]
    active_cats = req.categories if req.categories else all_cats
    tc_count    = getattr(req, "tc_count",   10)
    edge_count  = getattr(req, "edge_count",  4)
    bug_count   = getattr(req, "bug_count",   3)
    dist        = _build_category_dist(tc_count, active_cats)
    dist_lines  = "\n".join(f"  - {cat}: {count} case{'s' if count != 1 else ''}" for cat, count in dist)

    generator = Agent(
        role="QA Test Case Generator",
        goal=f"Generate exactly {tc_count} test cases distributed by category according to task instructions",
        backstory=(
            "You are a senior QA engineer with 15 years of software testing experience. "
            "You have deep knowledge of techniques such as equivalence partitioning, boundary value analysis "
            "and security testing. You generate EXACTLY the requested number of cases, "
            "strictly following the indicated category distribution. "
            "Each case has at least 5 detailed steps and measurable acceptance criteria. "
            "You ALWAYS respond in English."
        ),
        llm=llm, allow_delegation=False, verbose=False,
    )
    reviewer = Agent(
        role="QA Quality Reviewer",
        goal="Evaluate the quality, coverage and structure of a test case suite and issue a substantiated verdict",
        backstory=(
            "You are a QA Lead with extensive experience auditing test suites. "
            "You verify that all test types are covered, that steps are "
            "specific and that non-functional cases have quantitative criteria. "
            "You are critical but constructive. You ALWAYS respond in English."
        ),
        llm=llm, allow_delegation=False, verbose=False,
    )
    optimizer = Agent(
        role="QA Coverage Optimizer",
        goal="Identify and prioritize the critical missing test cases in the generated suite, based on the Reviewer's analysis",
        backstory=(
            "You are a QA Architect specialised in coverage gap analysis. "
            "You receive a test case suite and the Reviewer's quality analysis, and produce "
            "a prioritised list of the 3 most critical missing cases with full specification. "
            "You always prioritise: security > performance > critical business cases. "
            "You ALWAYS respond in English."
        ),
        llm=llm, allow_delegation=False, verbose=False,
    )

    task_generate = Task(
        description=(
            f"Generate a test case suite for the following user story.\n\n"
            f"USER STORY:\n{req.user_story}\n\n"
            f"ADDITIONAL CONTEXT: {req.context or 'None'}"
            f"{rag_section}\n\n"
            f"EXACT TEST CASE DISTRIBUTION TO GENERATE (total: {tc_count}):\n"
            f"{dist_lines}\n\n"
            "INSTRUCTIONS:\n"
            f"- Generate EXACTLY {tc_count} test cases following the above distribution\n"
            f"- The 'category' field of each case MUST be exactly one of: {', '.join(active_cats)}\n"
            f"- Generate EXACTLY {edge_count} edge scenarios\n"
            f"- Generate EXACTLY {bug_count} potential bugs\n"
            "- Each case must have at least 5 detailed and specific steps\n"
            "- Performance cases must include concrete numerical values (times, users)\n"
            "- Security cases must specify the attack vector\n"
            "- Respond ONLY with valid JSON, no additional text\n\n"
            "REQUIRED JSON FORMAT:\n"
            '{"test_cases": [{"id": "TC-001", "title": "...", "category": "...", "priority": "high|medium|low", '
            '"preconditions": ["..."], "steps": ["..."], "expected_result": "...", "test_type": "..."}], '
            '"edge_scenarios": [{"id": "ES-001", "scenario": "...", "risk_level": "...", "description": "..."}], '
            '"potential_bugs": [{"id": "BUG-001", "title": "...", "area": "...", "likelihood": "...", '
            '"description": "...", "suggested_test": "..."}], '
            '"coverage_summary": {"total_test_cases": 0, "categories_covered": [], '
            '"estimated_coverage_percent": 0, "missing_areas": []}}'
        ),
        expected_output="Valid JSON with test_cases, edge_scenarios, potential_bugs and coverage_summary",
        agent=generator,
    )
    task_review = Task(
        description=(
            f"Review the generated test case suite for the following user story.\n\n"
            f"USER STORY:\n{req.user_story}\n\n"
            "EVALUATE:\n"
            "1. Are all 7 categories covered?\n"
            "2. Are the steps specific and measurable?\n"
            "3. Do performance cases have numerical values?\n"
            "4. Do security cases specify the attack vector?\n"
            "5. Are there critical missing cases?\n\n"
            "Respond ONLY with JSON:\n"
            '{"verdict": "APPROVED|OBSERVATIONS|REJECTED", "score": 0.0-1.0, '
            '"gaps": ["gap1"], "strengths": ["strength1"], "recommendation": "brief text"}'
        ),
        expected_output="JSON with verdict, score, gaps, strengths and recommendation",
        agent=reviewer,
        context=[task_generate],
    )
    task_optimize = Task(
        description=(
            f"Based on the generated test case suite and the Reviewer's analysis for the story:\n\n"
            f"USER STORY: {req.user_story}\n\n"
            "INSTRUCTIONS:\n"
            "1. Identify the 3 most critical test cases MISSING from the suite\n"
            "2. Prioritise: security > performance > critical business cases\n"
            "3. For each missing case, generate its full specification\n"
            "4. Explain why each case is critical\n\n"
            "Respond ONLY with JSON:\n"
            '{"priority_gaps": [{"rank": 1, "category": "...", "reason": "...", '
            '"impact": "high|medium"}], '
            '"added_cases": [{"id": "OPT-001", "title": "...", "category": "...", '
            '"priority": "high|medium|low", "preconditions": ["..."], '
            '"steps": ["..."], "expected_result": "...", "test_type": "..."}], '
            '"optimization_summary": "brief text of what was optimised"}'
        ),
        expected_output="JSON with priority_gaps, added_cases and optimization_summary",
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

        # ── Agent 1: Generator ──────────────────────────────────────────────
        with tracer.agent_span("Generator", "QA Test Case Generator", step=1, total=3) as s:
            t0 = time.monotonic()
            with tracer.llm_inference_span("Generator", req.model, task_generate.description[:200]):
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
                    logger.warning("Error parsing Generator output: %s", exc)
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
                    "agent": "Generator",
                    "model": req.model,
                },
            )
            tracer.log_feedback_score(s, "tc_completeness", tc_completeness, "generation",
                                      reason=f"{tc_count_generated}/{req.tc_count} test cases generated")

        # ── Agent 2: Reviewer ────────────────────────────────────────────────
        with tracer.agent_span("Reviewer", "QA Quality Reviewer", step=2, total=3) as s:
            t1 = time.monotonic()
            with tracer.llm_inference_span("Reviewer", req.model, task_review.description[:200]):
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
                    "agent": "Reviewer",
                    "model": req.model,
                },
            )
            tracer.log_feedback_score(s, "reviewer_score", rev_score, "quality",
                                      reason=f"Verdict: {verdict}")

        # ── Agent 3: Optimizer ────────────────────────────────────────────────
        with tracer.agent_span("Optimizer", "QA Coverage Optimizer", step=3, total=3) as s:
            t2 = time.monotonic()
            with tracer.llm_inference_span("Optimizer", req.model, task_optimize.description[:200]):
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
                    "agent": "Optimizer",
                    "model": req.model,
                },
            )
            tracer.log_feedback_score(s, "optimization_coverage", optimization_ratio, "generation",
                                      reason=f"{added_count} critical cases added")

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
            "reviewer_score":   (rev_score, "quality", f"Reviewer verdict: {verdict}"),
            "coverage_pct":     (min(1.0, coverage_pct), "generation", "Estimated category coverage"),
            "tc_completeness":  (min(1.0, tc_count_generated / max(1, req.tc_count)), "generation",
                                 f"{tc_count_generated}/{req.tc_count} test cases"),
            "optimization_coverage": (min(1.0, added_count / 3) if added_count else 0.0, "generation",
                                      f"{added_count} cases added by optimizer"),
        })

    return {
        "parsed_data": parsed_data,
        "agent_trace": [
            AgentTrace(agent="Generator",  elapsed_s=t_gen,
                       summary=f"{tc_count_generated} cases generated"),
            AgentTrace(agent="Reviewer",   elapsed_s=t_rev,
                       summary=f"Verdict: {verdict} | Score: {rev_score:.2f}"),
            AgentTrace(agent="Optimizer",  elapsed_s=t_opt,
                       summary=f"{added_count} cases optimised | {opt_summary[:80]}"),
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

        # ── Agent 1: Generator ──────────────────────────────────────────────
        put_event({"event": "agent_start", "agent": "Generator", "step": 1, "total": 3})
        with tracer.agent_span("Generator", "QA Test Case Generator", step=1, total=3) as s:
            t0 = time.monotonic()
            with tracer.llm_inference_span("Generator", req.model, task_generate.description[:200]):
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
                    logger.warning("Error parsing Generator output: %s", exc)
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
                metadata={"elapsed_s": t_gen, "agent": "Generator"},
            )
            tracer.log_feedback_score(s, "tc_completeness", tc_completeness, "generation",
                                      reason=f"{tc_count_generated}/{req.tc_count} cases generated")

        for tc in parsed_data.get("test_cases") or []:
            put_event({"event": "case", "case": tc})
        put_event({
            "event": "agent_done", "agent": "Generator", "step": 1,
            "elapsed_s": t_gen,
            "summary": f"{tc_count_generated} cases generated",
            "data": parsed_data,
        })

        # ── Agent 2: Reviewer ────────────────────────────────────────────────
        put_event({"event": "agent_start", "agent": "Reviewer", "step": 2, "total": 3})
        with tracer.agent_span("Reviewer", "QA Quality Reviewer", step=2, total=3) as s:
            t1 = time.monotonic()
            with tracer.llm_inference_span("Reviewer", req.model, task_review.description[:200]):
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
                metadata={"elapsed_s": t_rev, "agent": "Reviewer"},
            )
            tracer.log_feedback_score(s, "reviewer_score", rev_score, "quality",
                                      reason=f"Verdict: {verdict}")

        put_event({
            "event": "agent_done", "agent": "Reviewer", "step": 2,
            "elapsed_s": t_rev,
            "summary": f"Verdict: {verdict} | Score: {rev_score:.2f}",
            "data": review,
        })

        # ── Agent 3: Optimizer ────────────────────────────────────────────────
        put_event({"event": "agent_start", "agent": "Optimizer", "step": 3, "total": 3})
        with tracer.agent_span("Optimizer", "QA Coverage Optimizer", step=3, total=3) as s:
            t2 = time.monotonic()
            with tracer.llm_inference_span("Optimizer", req.model, task_optimize.description[:200]):
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
                metadata={"elapsed_s": t_opt, "agent": "Optimizer"},
            )
            tracer.log_feedback_score(s, "optimization_coverage", optimization_ratio, "generation",
                                      reason=f"{added_count} critical cases added")

        for tc in optimizer_result.get("added_cases") or []:
            put_event({"event": "case", "case": tc})
        put_event({
            "event": "agent_done", "agent": "Optimizer", "step": 3,
            "elapsed_s": t_opt,
            "summary": f"{added_count} cases optimised | {opt_summary[:80]}",
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
            "reviewer_score":        (rev_score, "quality", f"Verdict: {verdict}"),
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
                {"agent": "Generator",  "elapsed_s": t_gen, "summary": f"{tc_count_generated} cases generated"},
                {"agent": "Reviewer",   "elapsed_s": t_rev, "summary": f"Verdict: {verdict} | Score: {rev_score:.2f}"},
                {"agent": "Optimizer",  "elapsed_s": t_opt, "summary": f"{added_count} cases optimised"},
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
        logger.error("CrewAI failed, using direct fallback | %s", exc)
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
            AgentTrace(agent="Fallback (no agents)", elapsed_s=0.0,
                       summary=f"CrewAI error: {str(exc)[:80]}")
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
            logger.error("Streaming pipeline error: %s", exc)
            tracer.record_error(exc, component="crewai", pipeline="generate_agents_stream")
            put_event({"event": "error", "message": str(exc)})

    loop.run_in_executor(_executor, _run)

    while True:
        event = await queue.get()
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if event.get("event") in ("done", "error"):
            break
