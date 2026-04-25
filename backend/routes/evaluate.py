import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.schemas.models import EvaluateRequest, EvaluateResponse
from backend.services.eval_service import run_evaluation, stream_evaluation

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(req: EvaluateRequest):
    try:
        return await run_evaluation(req)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("Error en evaluación | %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error en evaluación: {str(e)}")


@router.post("/evaluate/stream")
async def evaluate_stream(req: EvaluateRequest):
    async def generate():
        async for chunk in stream_evaluation(req):
            yield chunk

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
