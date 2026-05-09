"""
routes/evaluate.py — Evaluation endpoints with full Opik observability.

Captures source_generation_trace_id for cross-pipeline correlation
(Generate → Evaluate lineage visible in Opik UI).

Span hierarchy:

POST /evaluate
├── request_validation
├── deepeval_evaluation
│   ├── metric_test_coverage
│   ├── metric_test_relevancy
│   ├── metric_test_consistency
│   ├── metric_step_specificity
│   └── metric_non_functional_balance
└── response_serialization

POST /evaluate/stream  (same but streaming)
"""

import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.observability import tracer
from backend.schemas.models import EvaluateRequest, EvaluateResponse
from backend.services.eval_service import run_evaluation, stream_evaluation

router = APIRouter()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# POST /evaluate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(req: EvaluateRequest):
    test_cases = req.generated_output.get("test_cases", []) if req.generated_output else []

    # Propagate source trace ID for Generate → Evaluate correlation
    if req.source_generation_trace_id:
        tracer.set_source_trace_id(req.source_generation_trace_id)

    with tracer.root_trace(
        "evaluate_request",
        input_data={
            "requirement": req.requirement[:300],
            "model": req.model,
            "eval_model": req.eval_model or "default",
            "test_case_count": len(test_cases),
        },
        metadata={
            "endpoint": "POST /evaluate",
            "pipeline": "evaluate",
            "requirement_chars": len(req.requirement),
            "test_case_count": len(test_cases),
            "model": req.model,
            "eval_model": req.eval_model or "default",
            "streaming": False,
            "source_generation_trace_id": req.source_generation_trace_id or "",
        },
        tags=["evaluate"],
        pipeline="evaluate",
    ) as t:
        t0 = time.perf_counter()
        logger.info(
            "evaluate request received",
            extra={
                "endpoint": "POST /evaluate",
                "model": req.model,
                "eval_model": req.eval_model,
                "requirement_length": len(req.requirement),
                "test_case_count": len(test_cases),
                "source_trace_id": req.source_generation_trace_id or "",
            },
        )
        try:
            with tracer.request_validation_span(
                "/evaluate",
                model=req.model,
                test_case_count=len(test_cases),
                eval_model=req.eval_model or "default",
            ):
                pass

            result = await run_evaluation(req)

            elapsed_ms = round((time.perf_counter() - t0) * 1000)

            with tracer.response_build_span(tc_count=len(test_cases)):
                pass

            evaluation_trace_id = tracer.get_trace_id()
            tracer.update_span(
                t,
                output={
                    "coverage": result.coverage,
                    "relevancy": result.relevancy,
                    "consistency": result.consistency,
                    "specificity": result.specificity,
                    "nonfunctional_balance": result.nonfunctional_balance,
                    "overall": result.overall,
                    "model_used": result.model_used,
                    "evaluation_trace_id": evaluation_trace_id,
                },
                metadata={
                    "total_duration_ms": elapsed_ms,
                    "status": "ok",
                    "source_generation_trace_id": req.source_generation_trace_id or "",
                },
            )
            tracer.log_pipeline_feedback(t, {
                "overall_score":         (result.overall, "deepeval", f"Overall score: {result.overall:.3f}"),
                "test_coverage":         (result.coverage, "deepeval", f"Coverage: {result.coverage:.3f}"),
                "test_relevancy":        (result.relevancy, "deepeval", f"Relevancy: {result.relevancy:.3f}"),
                "test_consistency":      (result.consistency, "deepeval", f"Consistency: {result.consistency:.3f}"),
                "step_specificity":      (result.specificity, "deepeval", f"Specificity: {result.specificity:.3f}"),
                "nonfunctional_balance": (result.nonfunctional_balance, "deepeval",
                                         f"NF Balance: {result.nonfunctional_balance:.3f}"),
            })

            result.evaluation_trace_id = evaluation_trace_id
            return result

        except ValueError as e:
            logger.warning("evaluate validation error | %s", e)
            tracer.record_error(e, target=t, component="validator", pipeline="evaluate")
            raise HTTPException(status_code=422, detail=str(e))
        except RuntimeError as e:
            logger.error("evaluate service unavailable | %s", e)
            tracer.record_error(e, target=t, component="deepeval", pipeline="evaluate")
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            logger.error("evaluate unhandled error", exc_info=True, extra={"error": str(e)})
            tracer.record_error(e, target=t, component="evaluate", pipeline="evaluate")
            raise HTTPException(status_code=500, detail=f"Error en evaluación: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# POST /evaluate/stream
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/evaluate/stream")
async def evaluate_stream(req: EvaluateRequest):
    test_cases = req.generated_output.get("test_cases", []) if req.generated_output else []

    if req.source_generation_trace_id:
        tracer.set_source_trace_id(req.source_generation_trace_id)

    logger.info(
        "evaluate/stream request received",
        extra={
            "endpoint": "POST /evaluate/stream",
            "model": req.model,
            "eval_model": req.eval_model,
            "requirement_length": len(req.requirement),
            "test_case_count": len(test_cases),
            "source_trace_id": req.source_generation_trace_id or "",
        },
    )

    async def traced_generate():
        with tracer.root_trace(
            "evaluate_stream_request",
            input_data={
                "requirement": req.requirement[:300],
                "model": req.model,
                "eval_model": req.eval_model or "default",
                "test_case_count": len(test_cases),
            },
            metadata={
                "endpoint": "POST /evaluate/stream",
                "pipeline": "evaluate_stream",
                "requirement_chars": len(req.requirement),
                "test_case_count": len(test_cases),
                "streaming": True,
                "source_generation_trace_id": req.source_generation_trace_id or "",
                "model": req.model,
                "eval_model": req.eval_model or "default",
            },
            tags=["evaluate", "stream"],
            pipeline="evaluate_stream",
        ) as t:
            with tracer.request_validation_span(
                "/evaluate/stream",
                model=req.model,
                test_case_count=len(test_cases),
            ):
                pass

            metrics_received = []
            async for chunk in stream_evaluation(req):
                yield chunk
                try:
                    if chunk.startswith("data: "):
                        payload = json.loads(chunk[6:])
                        if "metric" in payload and "score" in payload:
                            metrics_received.append((payload["metric"], payload["score"]))
                except Exception:
                    pass

            if metrics_received:
                overall = sum(s for _, s in metrics_received) / len(metrics_received)
                tracer.update_span(t, output={
                    "metrics_received": len(metrics_received),
                    "overall_score": round(overall, 3),
                })
                tracer.log_pipeline_feedback(t, {
                    "overall_score": (overall, "deepeval", f"Overall: {overall:.3f}"),
                    **{m: (s, "deepeval", f"{m}: {s:.3f}") for m, s in metrics_received},
                })

    return StreamingResponse(
        traced_generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
