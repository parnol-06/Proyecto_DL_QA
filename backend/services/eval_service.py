"""
eval_service.py — DeepEval evaluation service.

run_evaluation() and stream_evaluation() are called from within root_trace()
contexts owned by the evaluate route. All spans created here are guaranteed
children of that trace because _cv_opik_trace_id is already set.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from uuid import uuid4

from backend.observability import tracer
from backend.schemas.models import EvaluateRequest, EvaluateResponse
from backend.utils.logging_config import set_evaluation_id, get_evaluation_id

logger = logging.getLogger(__name__)

_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from evaluator.metrics import evaluate_test_cases as _run_deepeval
    from evaluator.metrics import stream_evaluate_test_cases as _stream_deepeval
    _EVALUATOR_AVAILABLE = True
except Exception as e:
    logger.warning("DeepEval not available: %s", str(e), extra={"reason": str(e)})
    _EVALUATOR_AVAILABLE = False


def _input_summary(req: EvaluateRequest) -> dict:
    test_cases = req.generated_output.get("test_cases", []) if req.generated_output else []
    return {
        "model": req.model,
        "eval_model": req.eval_model,
        "requirement_chars": len(req.requirement),
        "test_case_count": len(test_cases),
        "source_generation_trace_id": req.source_generation_trace_id or "",
    }


async def run_evaluation(req: EvaluateRequest) -> EvaluateResponse:
    """
    Synchronous DeepEval evaluation wrapped in an async coroutine.
    Called from within evaluate route's root_trace() — no top-level trace created here.
    Creates a deepeval_evaluation child span + one metric span per metric.
    """
    if not _EVALUATOR_AVAILABLE:
        raise RuntimeError(
            "DeepEval no está disponible. Verifica que deepeval esté instalado y configurado."
        )

    evaluation_id = uuid4().hex[:12]
    set_evaluation_id(evaluation_id)
    summary = _input_summary(req)
    t0 = time.perf_counter()

    logger.info("evaluation started", extra={"event": "eval_start", **summary})

    test_cases = req.generated_output.get("test_cases", []) if req.generated_output else []
    effective_eval = req.eval_model or "llama3.2"

    try:
        with tracer.deepeval_span(
            metric_count=5,
            eval_model=effective_eval,
            test_case_count=len(test_cases),
        ) as eval_s:
            raw = _run_deepeval(
                user_story=req.requirement,
                generated_output=req.generated_output,
                model_name=req.model,
                eval_model_name=req.eval_model or None,
            )

            elapsed = round((time.perf_counter() - t0) * 1000)
            metrics = raw.get("metrics", {})
            overall = raw.get("overall_score", 0.0)
            all_passed = raw.get("all_passed", False)

            expected = {"Test Coverage", "Test Relevancy", "Test Consistency", "Step Specificity", "Non-Functional Balance"}
            missing = expected - set(metrics.keys())
            if missing:
                logger.warning(
                    "evaluation incomplete — metrics did not run",
                    extra={"event": "eval_incomplete", "missing_metrics": sorted(missing)},
                )

            for name, m in metrics.items():
                score = m.get("score")
                if score is None or (isinstance(score, float) and (score != score)):
                    logger.error(
                        "invalid metric score detected",
                        extra={"event": "invalid_score", "metric": name, "score": score},
                    )

            tracer.update_span(eval_s, output={
                "overall_score": overall,
                "all_passed": all_passed,
                "metrics_completed": len(metrics),
                "model_used": raw.get("model_used"),
                "scores": {k: v.get("score") for k, v in metrics.items()},
            }, metadata={
                "evaluation_id": evaluation_id,
                "elapsed_ms": elapsed,
                "missing_metrics": sorted(missing) if missing else [],
            })

            logger.info(
                "evaluation completed",
                extra={
                    "event": "eval_done",
                    "duration_ms": elapsed,
                    "overall_score": overall,
                    "all_passed": all_passed,
                    "model_used": raw.get("model_used"),
                    "scores": {k: v.get("score") for k, v in metrics.items()},
                },
            )

    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "evaluation failed",
            exc_info=True,
            extra={"event": "eval_error", "error": str(exc), "duration_ms": elapsed},
        )
        raise

    def score(key: str) -> float:
        return round(metrics.get(key, {}).get("score", 0.0), 3)

    return EvaluateResponse(
        coverage=score("Test Coverage"),
        relevancy=score("Test Relevancy"),
        consistency=score("Test Consistency"),
        specificity=score("Step Specificity"),
        nonfunctional_balance=score("Non-Functional Balance"),
        overall=round(overall, 3),
        model_used=raw.get("model_used", f"ollama/{req.model}"),
        evaluation_trace_id="",  # filled by the route after get_trace_id()
    )


async def stream_evaluation(req: EvaluateRequest):
    """
    Async generator that emits one SSE event per DeepEval metric as it completes.
    Called from within evaluate_stream route's root_trace() context.
    The executor thread inherits the asyncio context (Python 3.7+) so
    deepeval_span and metric_span are children of the route's root trace.
    """
    if not _EVALUATOR_AVAILABLE:
        yield f"data: {json.dumps({'error': 'DeepEval no disponible. Instala requirements-eval.txt'})}\n\n"
        return

    evaluation_id = uuid4().hex[:12]
    set_evaluation_id(evaluation_id)
    summary = _input_summary(req)
    t0 = time.perf_counter()

    logger.info("streaming evaluation started", extra={"event": "eval_stream_start", **summary})

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    test_cases = req.generated_output.get("test_cases", []) if req.generated_output else []
    effective_eval = req.eval_model or "llama3.2"

    def _run_sync():
        with tracer.deepeval_span(
            metric_count=5,
            eval_model=effective_eval,
            test_case_count=len(test_cases),
        ) as eval_s:
            scores: list[float] = []
            try:
                for event in _stream_deepeval(
                    user_story=req.requirement,
                    generated_output=req.generated_output,
                    model_name=req.model,
                    eval_model_name=req.eval_model or None,
                ):
                    if event.get("score") is not None:
                        scores.append(event["score"])
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as exc:
                logger.error(
                    "streaming evaluation thread error",
                    exc_info=True,
                    extra={"event": "eval_stream_error", "error": str(exc)},
                )
                loop.call_soon_threadsafe(queue.put_nowait, {"error": str(exc)})

            overall = round(sum(scores) / len(scores), 3) if scores else 0.0
            tracer.update_span(
                eval_s,
                output={
                    "overall_score": overall,
                    "metrics_completed": len(scores),
                    "evaluation_id": evaluation_id,
                },
            )

        loop.call_soon_threadsafe(queue.put_nowait, {"__end__": True})

    loop.run_in_executor(None, _run_sync)

    while True:
        event = await queue.get()
        if "__end__" in event:
            elapsed = round((time.perf_counter() - t0) * 1000)
            logger.info(
                "streaming evaluation finished",
                extra={"event": "eval_stream_done", "duration_ms": elapsed},
            )
            break
        yield f"data: {json.dumps(event)}\n\n"
        if event.get("error") or event.get("done"):
            break
