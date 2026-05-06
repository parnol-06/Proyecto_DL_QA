import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.schemas.models import EvaluateRequest, EvaluateResponse
from backend.services.eval_service import run_evaluation, stream_evaluation
from backend.utils.logging_config import get_request_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(req: EvaluateRequest):
    t0 = time.perf_counter()
    logger.info(
        "evaluate request received",
        extra={
            "endpoint": "POST /evaluate",
            "model": req.model,
            "eval_model": req.eval_model,
            "requirement_length": len(req.requirement),
        },
    )
    try:
        result = await run_evaluation(req)
        logger.info(
            "evaluate request completed",
            extra={
                "endpoint": "POST /evaluate",
                "overall_score": result.overall,
                "all_passed": result.overall >= 0.6,
                "duration_ms": round((time.perf_counter() - t0) * 1000),
            },
        )
        return result
    except ValueError as e:
        logger.warning("evaluate validation error | %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        logger.error("evaluate service unavailable | %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(
            "evaluate unhandled error",
            exc_info=True,
            extra={"error": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Error en evaluación: {str(e)}")


@router.post("/evaluate/stream")
async def evaluate_stream(req: EvaluateRequest):
    logger.info(
        "evaluate/stream request received",
        extra={
            "endpoint": "POST /evaluate/stream",
            "model": req.model,
            "eval_model": req.eval_model,
            "requirement_length": len(req.requirement),
        },
    )

    async def generate():
        async for chunk in stream_evaluation(req):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
