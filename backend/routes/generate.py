import asyncio
import json
import logging

import ollama
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.config import OLLAMA_HOST, OLLAMA_CONTEXT_SIZE
from backend.schemas.models import (
    GenerateRequest, GenerateResponse,
    AgentGenerateRequest, AgentGenerateResponse,
    RegenerateTCRequest,
)
from backend.services.llm_service import generate_test_cases, stream_generate_test_cases
from backend.services.agent_service import run_agent_pipeline, stream_agent_pipeline
from backend.services.rag_service import semantic_search
from backend.utils.json_utils import find_first_json_object

router = APIRouter()
logger = logging.getLogger(__name__)
_ollama = ollama.Client(host=OLLAMA_HOST)


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


@router.post("/generate/agents/stream")
async def generate_agents_stream(req: AgentGenerateRequest):
    """Pipeline SSE: emite un evento tras cada agente para renderizado progresivo."""
    try:
        rag_context = ""
        if req.use_rag:
            try:
                rag_context = semantic_search(req.user_story)
            except Exception as exc:
                logger.warning("RAG no disponible en /generate/agents/stream: %s", exc)

        return StreamingResponse(
            stream_agent_pipeline(req, rag_context),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except Exception as e:
        logger.error("Error iniciando pipeline streaming | %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error en agentes: {str(e)}")


@router.post("/generate/agents", response_model=AgentGenerateResponse)
async def generate_agents(req: AgentGenerateRequest):
    """Pipeline de 3 agentes CrewAI: Generador + Revisor + Optimizador."""
    try:
        rag_context = ""
        if req.use_rag:
            try:
                rag_context = semantic_search(req.user_story)
            except Exception as exc:
                logger.warning("RAG no disponible en /generate/agents: %s", exc)

        return await run_agent_pipeline(req, rag_context)

    except ollama.ResponseError as e:
        raise HTTPException(status_code=503, detail=f"Error de Ollama: {str(e)}")
    except Exception as e:
        logger.error("Error en pipeline de agentes | %s", str(e))
        raise HTTPException(status_code=500, detail=f"Error en agentes: {str(e)}")


@router.post("/regenerate-tc")
async def regenerate_tc(req: RegenerateTCRequest):
    """Regenera un único caso de prueba conservando su ID y categoría."""
    cat_hint = (
        f" Genera exactamente 1 caso de prueba de categoría '{req.category}'."
        if req.category else " Genera exactamente 1 caso de prueba."
    )
    prompt = (
        f"Historia de usuario:\n{req.user_story}\n\n"
        f"Contexto: {req.context or 'Ninguno'}\n\n"
        f"INSTRUCCIÓN:{cat_hint} Mantén el ID {req.tc_id}. "
        "Responde SOLO con el objeto JSON del caso:\n"
        '{"id":"...","title":"...","category":"...","priority":"alto|medio|bajo",'
        '"preconditions":["..."],"steps":["..."],"expected_result":"...","test_type":"..."}'
    )
    try:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: _ollama.chat(
                model=req.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": req.temperature, "num_ctx": OLLAMA_CONTEXT_SIZE},
            ),
        )
        content = resp["message"]["content"]
        raw_json = find_first_json_object(content)
        if not raw_json:
            raise ValueError("El modelo no devolvió un JSON válido")
        tc = json.loads(raw_json)
        tc["id"] = req.tc_id
        return {"test_case": tc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pull-model")
async def pull_model(body: dict):
    """Descarga un modelo Ollama. Útil para descargar modelos desde la UI."""
    model = body.get("model", "").strip()
    if not model:
        raise HTTPException(status_code=422, detail="Nombre de modelo requerido")
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: _ollama.pull(model))
        return {"status": "ok", "model": model}
    except ollama.ResponseError as e:
        raise HTTPException(status_code=503, detail=f"Error descargando modelo: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/status")
async def rag_status():
    """Verifica si el índice RAG está construido."""
    try:
        from backend.services.rag_service import is_index_built, _get_collection
        built = is_index_built()
        count = _get_collection().count() if built else 0
        return {"built": built, "chunk_count": count}
    except Exception as exc:
        return {"built": False, "chunk_count": 0, "error": str(exc)}


def _extract_model_names(resp) -> list[str]:
    """Compatible con ollama SDK antiguo (dict) y nuevo (objetos Pydantic)."""
    raw = resp.get("models", []) if isinstance(resp, dict) else getattr(resp, "models", [])
    names = []
    for m in raw:
        if isinstance(m, dict):
            names.append(m.get("name") or m.get("model", ""))
        else:
            names.append(getattr(m, "name", None) or getattr(m, "model", ""))
    return [n for n in names if n]


@router.get("/models")
async def list_models():
    try:
        return {"models": _extract_model_names(_ollama.list()), "ollama_available": True}
    except Exception:
        return {"models": [], "ollama_available": False}


@router.get("/health")
async def health():
    try:
        names = _extract_model_names(_ollama.list())
        return {"status": "ok", "ollama": True, "models_count": len(names)}
    except Exception:
        return {"status": "degraded", "ollama": False, "models_count": 0}


@router.get("/model-status")
async def model_status(model: str = Query(..., description="Nombre del modelo")):
    try:
        available = _extract_model_names(_ollama.list())
        loaded = any(name.startswith(model) or model.startswith(name.split(":")[0]) for name in available)
        return {"model": model, "loaded": loaded}
    except Exception:
        return {"model": model, "loaded": False}
