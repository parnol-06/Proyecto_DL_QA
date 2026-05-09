"""
routes/generate.py — Generation endpoints with full Opik observability.

Each endpoint owns its root_trace() with enriched metadata and feedback scores.
Child spans created in services (llm_service, rag_service, agent_service) are
guaranteed to attach as children because _cv_opik_trace_id is set by root_trace().

Span hierarchy produced per endpoint:

POST /generate
├── request_validation
├── generate_test_cases (service_span)
│   ├── rag_pipeline → embedding_generation + chromadb_query
│   ├── prompt_compilation
│   ├── ollama_chat (llm_span)
│   └── llm_json_parse
└── response_serialization

POST /generate/agents
├── request_validation
├── rag_pipeline (optional)
│   ├── embedding_generation
│   └── chromadb_query
├── crew_pipeline
│   ├── agent_1_generador
│   │   ├── llm_call_generador
│   │   └── llm_json_parse
│   ├── agent_2_revisor
│   │   └── llm_call_revisor
│   └── agent_3_optimizador
│       └── llm_call_optimizador
└── response_serialization

POST /generate/stream  (same structure, ends with response_stream)
POST /generate/agents/stream  (same structure, ends with response_stream)
"""

import asyncio
import json
import logging
import time

import ollama
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.config import OLLAMA_HOST, OLLAMA_CONTEXT_SIZE
from backend.observability import tracer
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


# ─────────────────────────────────────────────────────────────────────────────
# POST /generate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    with tracer.root_trace(
        "generate_request",
        input_data={
            "user_story": req.user_story[:300],
            "model": req.model,
            "tc_count": req.tc_count,
            "use_rag": req.use_rag,
            "categories": req.categories or [],
        },
        metadata={
            "endpoint": "POST /generate",
            "pipeline": "generate_normal",
            "user_story_size": len(req.user_story),
            "streaming": False,
            "evaluate_enabled": False,
            "rag_enabled": req.use_rag,
            "temperature": req.temperature,
            "model": req.model,
            "tc_count_requested": req.tc_count,
            "edge_count_requested": req.edge_count,
            "bug_count_requested": req.bug_count,
        },
        tags=["generate", "normal"],
        pipeline="generate_normal",
    ) as t:
        t0 = time.perf_counter()
        try:
            with tracer.request_validation_span(
                "/generate",
                model=req.model,
                tc_count=req.tc_count,
                use_rag=req.use_rag,
            ):
                pass

            result = await generate_test_cases(req)

            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            tc_count_actual = len(result.test_cases)
            coverage_pct = result.coverage_summary.get("estimated_coverage_percent", 0.0)
            tc_completeness = min(1.0, tc_count_actual / max(1, req.tc_count))
            output_validity = 1.0 if tc_count_actual > 0 else 0.0

            with tracer.response_build_span(
                tc_count=tc_count_actual,
                edge_count=len(result.edge_scenarios),
                bug_count=len(result.potential_bugs),
            ) as rs:
                tracer.update_span(rs, output={
                    "tc_count": tc_count_actual,
                    "categories_covered": result.coverage_summary.get("categories_covered", []),
                })

            tracer.update_span(
                t,
                output={
                    "tc_count": tc_count_actual,
                    "edge_count": len(result.edge_scenarios),
                    "bug_count": len(result.potential_bugs),
                    "coverage_pct": coverage_pct,
                    "categories_covered": result.coverage_summary.get("categories_covered", []),
                    "missing_areas": result.coverage_summary.get("missing_areas", []),
                },
                metadata={
                    "total_duration_ms": elapsed_ms,
                    "status": "ok",
                    "model": req.model,
                    "pipeline": "generate_normal",
                },
            )
            tracer.log_pipeline_feedback(t, {
                "coverage_pct":    (coverage_pct / 100.0, "generation", f"{coverage_pct:.1f}% cobertura de categorías"),
                "tc_completeness": (tc_completeness, "generation", f"{tc_count_actual}/{req.tc_count} casos generados"),
                "output_validity": (output_validity, "quality", "JSON con test cases válidos"),
                "rag_enabled":     (1.0 if req.use_rag else 0.0, "context", "RAG habilitado"),
            })

            generation_trace_id = tracer.get_trace_id()
            result.generation_trace_id = generation_trace_id
            return result

        except ollama.ResponseError as e:
            logger.error("Error Ollama | %s", str(e))
            tracer.record_error(e, target=t, component="ollama", pipeline="generate_normal")
            raise HTTPException(status_code=503, detail=f"Error de Ollama: {str(e)}")
        except ValueError as e:
            tracer.record_error(e, target=t, component="validator", pipeline="generate_normal")
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            logger.error("Error interno en /generate | %s", str(e))
            tracer.record_error(e, target=t, component="generate", pipeline="generate_normal")
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# POST /generate/stream
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    async def traced_stream():
        with tracer.root_trace(
            "generate_stream_request",
            input_data={
                "user_story": req.user_story[:300],
                "model": req.model,
                "tc_count": req.tc_count,
                "use_rag": req.use_rag,
            },
            metadata={
                "endpoint": "POST /generate/stream",
                "pipeline": "generate_stream",
                "user_story_size": len(req.user_story),
                "streaming": True,
                "rag_enabled": req.use_rag,
                "model": req.model,
                "temperature": req.temperature,
            },
            tags=["generate", "stream"],
            pipeline="generate_stream",
        ) as t:
            with tracer.request_validation_span("/generate/stream", model=req.model, tc_count=req.tc_count):
                pass

            chunks_emitted = 0
            ttft_ms: float = 0.0
            t_start = time.perf_counter()
            first_token_received = False

            with tracer.stream_lifecycle_span(req.model, "generate_stream") as stream_s:
                async for chunk in stream_generate_test_cases(req):
                    if not first_token_received and b"token" in chunk.encode():
                        ttft_ms = round((time.perf_counter() - t_start) * 1000)
                        first_token_received = True
                    chunks_emitted += 1
                    yield chunk

                stream_duration_ms = round((time.perf_counter() - t_start) * 1000)
                tracer.update_span(stream_s, output={
                    "chunks_emitted": chunks_emitted,
                    "ttft_ms": ttft_ms,
                    "stream_duration_ms": stream_duration_ms,
                })

            tracer.update_span(t, output={
                "chunks_emitted": chunks_emitted,
                "ttft_ms": ttft_ms,
            })
            tracer.log_pipeline_feedback(t, {
                "stream_completion": (1.0, "quality", f"{chunks_emitted} chunks emitidos"),
                "ttft_quality": (
                    max(0.0, 1.0 - ttft_ms / 10000.0) if ttft_ms > 0 else 0.0,
                    "latency",
                    f"TTFT: {ttft_ms}ms",
                ),
            })

    return StreamingResponse(
        traced_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /generate/agents/stream
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate/agents/stream")
async def generate_agents_stream(req: AgentGenerateRequest):
    """Pipeline SSE: emite un evento tras cada agente para renderizado progresivo."""
    async def traced_stream():
        with tracer.root_trace(
            "generate_agents_stream_request",
            input_data={
                "user_story": req.user_story[:300],
                "model": req.model,
                "tc_count": req.tc_count,
                "use_rag": req.use_rag,
            },
            metadata={
                "endpoint": "POST /generate/agents/stream",
                "pipeline": "generate_agents_stream",
                "user_story_size": len(req.user_story),
                "streaming": True,
                "rag_enabled": req.use_rag,
                "model": req.model,
                "temperature": req.temperature,
                "tc_count_requested": req.tc_count,
            },
            tags=["generate", "agents", "stream"],
            pipeline="generate_agents_stream",
        ) as t:
            with tracer.request_validation_span(
                "/generate/agents/stream", model=req.model, tc_count=req.tc_count
            ):
                pass

            rag_context = ""
            if req.use_rag:
                try:
                    with tracer.rag_span(req.user_story) as s:
                        rag_context = semantic_search(req.user_story)
                        tracer.update_span(
                            s,
                            output={"context_chars": len(rag_context), "has_context": bool(rag_context)},
                            metadata={"docs_retrieved": "3" if rag_context else "0"},
                        )
                except Exception as exc:
                    logger.warning("RAG no disponible en /generate/agents/stream: %s", exc)

            tracer.update_span(t, metadata={"rag_context_chars": len(rag_context)})

            chunks_emitted = 0
            t_stream_start = time.perf_counter()

            with tracer.stream_lifecycle_span(req.model, "generate_agents_stream") as stream_s:
                try:
                    async for chunk in stream_agent_pipeline(req, rag_context):
                        chunks_emitted += 1
                        yield chunk
                except Exception as e:
                    logger.error("Error en pipeline streaming | %s", str(e))
                    tracer.record_error(e, target=t, component="crewai", pipeline="generate_agents_stream")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

                stream_duration_ms = round((time.perf_counter() - t_stream_start) * 1000)
                tracer.update_span(stream_s, output={
                    "chunks_emitted": chunks_emitted,
                    "stream_duration_ms": stream_duration_ms,
                })

            tracer.update_span(t, output={"chunks_emitted": chunks_emitted})
            tracer.log_pipeline_feedback(t, {
                "rag_context_quality": (
                    1.0 if rag_context else 0.5,
                    "context",
                    "RAG context retrieved" if rag_context else "RAG not used",
                ),
                "stream_completion": (1.0, "quality", f"{chunks_emitted} chunks emitidos"),
            })

    return StreamingResponse(
        traced_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /generate/agents
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/generate/agents", response_model=AgentGenerateResponse)
async def generate_agents(req: AgentGenerateRequest):
    """Pipeline de 3 agentes CrewAI: Generador + Revisor + Optimizador."""
    with tracer.root_trace(
        "generate_agents_request",
        input_data={
            "user_story": req.user_story[:300],
            "model": req.model,
            "tc_count": req.tc_count,
            "use_rag": req.use_rag,
        },
        metadata={
            "endpoint": "POST /generate/agents",
            "pipeline": "generate_agents",
            "user_story_size": len(req.user_story),
            "streaming": False,
            "rag_enabled": req.use_rag,
            "model": req.model,
            "temperature": req.temperature,
            "tc_count_requested": req.tc_count,
            "edge_count_requested": req.edge_count,
            "bug_count_requested": req.bug_count,
        },
        tags=["generate", "agents"],
        pipeline="generate_agents",
    ) as t:
        t0 = time.perf_counter()
        try:
            with tracer.request_validation_span("/generate/agents", model=req.model, tc_count=req.tc_count):
                pass

            rag_context = ""
            if req.use_rag:
                try:
                    with tracer.rag_span(req.user_story) as s:
                        rag_context = semantic_search(req.user_story)
                        tracer.update_span(
                            s,
                            output={"context_chars": len(rag_context), "has_context": bool(rag_context)},
                            metadata={"docs_retrieved": "3" if rag_context else "0"},
                        )
                except Exception as exc:
                    logger.warning("RAG no disponible en /generate/agents: %s", exc)

            result = await run_agent_pipeline(req, rag_context)

            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            tc_count_actual = len(result.test_cases)
            coverage_pct = result.coverage_summary.get("estimated_coverage_percent", 0.0)
            tc_completeness = min(1.0, tc_count_actual / max(1, req.tc_count))

            with tracer.response_build_span(
                tc_count=tc_count_actual,
                edge_count=len(result.edge_scenarios),
                bug_count=len(result.potential_bugs),
            ):
                pass

            tracer.update_span(
                t,
                output={
                    "tc_count": tc_count_actual,
                    "coverage_pct": coverage_pct,
                    "used_fallback": result.used_fallback,
                    "agent_steps": len(result.agent_trace),
                },
                metadata={
                    "total_duration_ms": elapsed_ms,
                    "status": "ok",
                    "model": req.model,
                    "rag_context_chars": len(rag_context),
                },
            )
            tracer.log_pipeline_feedback(t, {
                "coverage_pct":    (coverage_pct / 100.0, "generation", f"{coverage_pct:.1f}% cobertura"),
                "tc_completeness": (tc_completeness, "generation", f"{tc_count_actual}/{req.tc_count} casos"),
                "pipeline_quality": (0.0 if result.used_fallback else 1.0, "quality",
                                     "Fallback activo" if result.used_fallback else "Pipeline completo"),
                "rag_context_quality": (1.0 if rag_context else 0.5, "context",
                                        "RAG context available" if rag_context else "No RAG context"),
            })

            result.generation_trace_id = tracer.get_trace_id()
            return result

        except ollama.ResponseError as e:
            tracer.record_error(e, target=t, component="ollama", pipeline="generate_agents")
            raise HTTPException(status_code=503, detail=f"Error de Ollama: {str(e)}")
        except Exception as e:
            logger.error("Error en pipeline de agentes | %s", str(e))
            tracer.record_error(e, target=t, component="crewai", pipeline="generate_agents")
            raise HTTPException(status_code=500, detail=f"Error en agentes: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# POST /regenerate-tc
# ─────────────────────────────────────────────────────────────────────────────

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
    with tracer.root_trace(
        "regenerate_tc_request",
        input_data={"tc_id": req.tc_id, "model": req.model, "category": req.category},
        metadata={"endpoint": "POST /regenerate-tc", "pipeline": "regenerate_tc"},
        tags=["regenerate"],
        pipeline="regenerate_tc",
    ) as t:
        try:
            loop = asyncio.get_running_loop()
            with tracer.llm_span(
                "ollama_chat_regenerate",
                model=req.model,
                user_prompt=prompt,
                temperature=req.temperature,
            ) as ls:
                resp = await loop.run_in_executor(
                    None,
                    lambda: _ollama.chat(
                        model=req.model,
                        messages=[{"role": "user", "content": prompt}],
                        options={"temperature": req.temperature, "num_ctx": OLLAMA_CONTEXT_SIZE},
                    ),
                )
                content = resp["message"]["content"]
                tracer.update_span(ls, output={"response_preview": content[:300]})

            raw_json = find_first_json_object(content)
            if not raw_json:
                raise ValueError("El modelo no devolvió un JSON válido")
            tc = json.loads(raw_json)
            tc["id"] = req.tc_id

            tracer.update_span(t, output={"tc_id": req.tc_id, "category": req.category})
            tracer.log_feedback_score(t, "regeneration_success", 1.0, "quality")
            return {"test_case": tc}
        except Exception as e:
            tracer.record_error(e, target=t, component="ollama", pipeline="regenerate_tc")
            raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# POST /pull-model
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/pull-model")
async def pull_model(body: dict):
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


# ─────────────────────────────────────────────────────────────────────────────
# GET /rag/status
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/rag/status")
async def rag_status():
    try:
        from backend.services.rag_service import is_index_built, _get_collection
        built = is_index_built()
        count = _get_collection().count() if built else 0
        return {"built": built, "chunk_count": count}
    except Exception as exc:
        return {"built": False, "chunk_count": 0, "error": str(exc)}


_EMBED_KEYWORDS = ("embed", "nomic", "bge", "e5-", "minilm")


def _extract_model_names(resp) -> list[str]:
    raw = resp.get("models", []) if isinstance(resp, dict) else getattr(resp, "models", [])
    names = []
    for m in raw:
        if isinstance(m, dict):
            names.append(m.get("name") or m.get("model", ""))
        else:
            names.append(getattr(m, "name", None) or getattr(m, "model", ""))
    return [n for n in names if n and not any(kw in n.lower() for kw in _EMBED_KEYWORDS)]


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
