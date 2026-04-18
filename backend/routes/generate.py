import logging

import ollama
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.schemas.models import GenerateRequest, GenerateResponse
from backend.services.llm_service import generate_test_cases, stream_generate_test_cases

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    try:
        return await generate_test_cases(req)
    except ollama.ResponseError as e:
        logger.error("Error Ollama | %s", str(e))
        raise HTTPException(status_code=503, detail=f"Error de Ollama: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Error interno | %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    return StreamingResponse(
        stream_generate_test_cases(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/models")
async def list_models():
    try:
        models = ollama.list()
        return {"models": [m["name"] for m in models.get("models", [])]}
    except Exception:
        return {"models": ["llama3.2", "mistral", "phi3"]}


@router.get("/health")
async def health():
    try:
        models_resp = ollama.list()
        models_count = len(models_resp.get("models", []))
        return {"status": "ok", "ollama": True, "models_count": models_count}
    except Exception:
        return {"status": "degraded", "ollama": False, "models_count": 0}


@router.get("/model-status")
async def model_status(model: str = Query(..., description="Nombre del modelo")):
    try:
        ps_resp = ollama.ps()
        running = ps_resp.get("models", [])
        loaded = any(m.get("name", "").startswith(model) for m in running)
        return {"model": model, "loaded": loaded}
    except Exception:
        return {"model": model, "loaded": False}
