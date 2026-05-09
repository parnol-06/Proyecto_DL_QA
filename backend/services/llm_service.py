"""
llm_service.py — LLM generation service (Ollama).

Called from within root_trace() contexts owned by generate routes.
Produces child spans:

generate_test_cases()
├── rag_pipeline (optional)
│   ├── embedding_generation
│   └── chromadb_query
├── prompt_compilation
├── ollama_chat (llm_span)
└── llm_json_parse

stream_generate_test_cases()
├── rag_pipeline (optional)
│   ├── embedding_generation
│   └── chromadb_query
├── ollama_stream (llm_span) ← tracks TTFT + chunk count
└── llm_json_parse
"""

import asyncio
import json
import logging
import re
import time

import ollama

from backend.config import OLLAMA_HOST, OLLAMA_TEMPERATURE, OLLAMA_CONTEXT_SIZE
from backend.observability import tracer
from backend.schemas.models import GenerateRequest, GenerateResponse

_ollama = ollama.Client(host=OLLAMA_HOST)

logger = logging.getLogger(__name__)

_llm_semaphore = asyncio.Semaphore(1)


def _calc_num_predict(tc_count: int, edge_count: int, bug_count: int) -> int:
    return max(4096, tc_count * 280 + edge_count * 120 + bug_count * 160 + 1000)


SYSTEM_PROMPT = """Eres un ingeniero QA senior EXPERTO con 15 años de experiencia. Tu trabajo es ser EXTREMADAMENTE DETALLISTA y minucioso.

INSTRUCCION OBLIGATORIA N°1: TODA TU RESPUESTA DEBE SER EXCLUSIVAMENTE EN IDIOMA ESPAÑOL. ABSOLUTAMENTE NADA EN INGLES.
INSTRUCCION OBLIGATORIA N°2: DEBES GENERAR EXACTAMENTE LA CANTIDAD DE CASOS INDICADA EN EL PROMPT. NI MAS NI MENOS.
INSTRUCCION OBLIGATORIA N°3: DEBES RESPETAR LA DISTRIBUCION POR CATEGORIA DEL PROMPT. EL CAMPO "category" DEBE COINCIDIR EXACTAMENTE CON LA CATEGORIA ASIGNADA.
INSTRUCCION OBLIGATORIA N°4: CADA CASO DE PRUEBA DEBE TENER MINIMO 5 PASOS DETALLADOS.
INSTRUCCION OBLIGATORIA N°5: NO GENERES SOLO CASOS FUNCIONALES BASICOS. DEBES CUBRIR TODOS LOS TIPOS DE PRUEBA INDICADOS.
INSTRUCCION OBLIGATORIA N°6: CADA PASO DEBE SER ESPECIFICO, NO GENERICO.
INSTRUCCION OBLIGATORIA N°7: LOS CASOS NO FUNCIONALES (RENDIMIENTO, SEGURIDAD, USABILIDAD) DEBEN TENER CONDICIONES Y RESULTADOS CUANTIFICABLES MEDIBLES. NO GENERICOS.
INSTRUCCION OBLIGATORIA N°8: PARA CASOS DE RENDIMIENTO SIEMPRE ESPECIFICA TIEMPOS MAXIMOS, CARGA Y NUMERO DE USUARIOS CONCRETOS.
INSTRUCCION OBLIGATORIA N°9: DIFERENCIA CLARAMENTE CASOS FUNCIONALES DE NO FUNCIONALES. NUNCA MEZCLALOS.

Dada una historia de usuario o requisito, DEBES responder SOLAMENTE con un objeto JSON válido.
Sin formato markdown, sin explicaciones, solo el JSON crudo.

La estructura JSON debe ser:
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "string",
      "category": "Camino Feliz | caso_limite | negativo | seguridad | rendimiento | usabilidad | compatibilidad",
      "priority": "alto | medio | bajo",
      "preconditions": ["string"],
      "steps": ["string"],
      "expected_result": "string",
      "test_type": "| No Funcional | funcional | integracion | ui | api | base_de_datos | rendimiento | seguridad"
    }
  ],
  "edge_scenarios": [
    {
      "id": "ES-001",
      "scenario": "string",
      "risk_level": "alto | medio | bajo",
      "description": "string"
    }
  ],
  "potential_bugs": [
    {
      "id": "BUG-001",
      "title": "string",
      "area": "string",
      "likelihood": "alto | medio | bajo",
      "description": "string",
      "suggested_test": "string"
    }
  ],
  "coverage_summary": {
    "total_test_cases": 0,
    "categories_covered": ["string"],
    "estimated_coverage_percent": 0,
    "missing_areas": ["string"]
  }
}"""


def _distribute_categories(tc_count: int, categories: list) -> list[tuple[str, int]]:
    n = len(categories)
    if n == 0:
        return []
    base, rem = divmod(tc_count, n)
    return [(cat, base + (1 if i < rem else 0)) for i, cat in enumerate(categories)]


def _build_prompt(req: GenerateRequest, rag_context: str = "") -> str:
    rag_section = (
        f"\n\nCONTEXTO DE BASE DE CONOCIMIENTO QA (usa esta información para enriquecer los casos):\n"
        f"{rag_context}\n"
        if rag_context else ""
    )
    cats = getattr(req, "categories", [])
    all_cats = ["happy_path", "caso_limite", "negativo", "seguridad", "rendimiento", "usabilidad", "compatibilidad"]
    active_cats = cats if cats else all_cats

    tc_count   = getattr(req, "tc_count",   10)
    edge_count = getattr(req, "edge_count",  4)
    bug_count  = getattr(req, "bug_count",   3)

    dist = _distribute_categories(tc_count, active_cats)
    dist_lines = "\n".join(f"  - {cat}: {count} caso{'s' if count != 1 else ''}" for cat, count in dist)

    return f"""Historia de Usuario / Requisito:
{req.user_story}

Contexto adicional:
{req.context if req.context else 'Ninguno'}
{rag_section}
INSTRUCCION OBLIGATORIA: TODA LA RESPUESTA DEBE SER 100% EN IDIOMA ESPAÑOL.

DISTRIBUCION EXACTA DE TEST CASES A GENERAR (total: {tc_count}):
{dist_lines}

REGLAS DE DISTRIBUCION:
- Genera EXACTAMENTE {tc_count} test cases en total.
- Genera EXACTAMENTE el número indicado para CADA categoría, ni uno más ni uno menos.
- El campo "category" de cada caso DEBE ser exactamente uno de: {", ".join(active_cats)}
- Genera los casos en el orden de la distribución: primero todos los de "{dist[0][0]}", luego los de la siguiente categoría, etc.

EDGE SCENARIOS: Genera EXACTAMENTE {edge_count} escenarios edge (array "edge_scenarios").
BUGS POTENCIALES: Genera EXACTAMENTE {bug_count} bugs potenciales (array "potential_bugs").

CADA CASO NO FUNCIONAL DEBE TENER VALORES NUMERICOS CONCRETOS Y MEDIBLES.
CADA CASO DEBE TENER MINIMO 5 PASOS DETALLADOS Y ESPECIFICOS.
Recuerda: responde SOLAMENTE con el objeto JSON crudo, sin ningun otro texto."""


def _parse_llm_output(content: str) -> dict:
    with tracer.parse_span(len(content)) as s:
        json_match = re.search(r"\{[\s\S]*\}", content)
        if not json_match:
            tracer.update_span(s, output={"success": False, "reason": "no_json_found"})
            raise ValueError("El modelo no devolvió un JSON válido")

        raw = json_match.group()
        result: dict | None = None

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            pass

        if result is None:
            try:
                from json_repair import repair_json
                repaired = repair_json(raw, return_objects=True)
                if isinstance(repaired, dict):
                    result = repaired
            except Exception:
                pass

        if result is None:
            try:
                fixed = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', raw)
                fixed = fixed.replace("'", '"')
                result = json.loads(fixed)
            except json.JSONDecodeError as err:
                tracer.update_span(s, output={"success": False, "reason": str(err)[:200]})
                logger.error("JSON irreparable | error=%s | fragmento=%s", err, raw[:300])
                raise

        tracer.update_span(s, output={
            "success": True,
            "tc_count": len(result.get("test_cases", [])),
            "has_edge_scenarios": bool(result.get("edge_scenarios")),
            "has_bugs": bool(result.get("potential_bugs")),
        })
        return result


def _build_response(data: dict, raw_story: str) -> GenerateResponse:
    test_cases = data.get("test_cases", [])

    covered_cats = list({tc.get("category") for tc in test_cases if tc.get("category")})
    all_expected_cats = {"happy_path", "caso_limite", "negativo", "seguridad", "rendimiento", "usabilidad", "compatibilidad"}
    coverage_pct = round((len(covered_cats) / len(all_expected_cats)) * 100, 2) if all_expected_cats else 0
    missing_cats = list(all_expected_cats - set(covered_cats))

    default_coverage = {
        "total_test_cases": len(test_cases),
        "categories_covered": covered_cats,
        "estimated_coverage_percent": coverage_pct,
        "missing_areas": missing_cats,
    }

    coverage = data.get("coverage_summary") or default_coverage
    coverage["total_test_cases"] = len(test_cases)
    coverage["categories_covered"] = covered_cats
    coverage["estimated_coverage_percent"] = coverage_pct
    coverage["missing_areas"] = missing_cats

    return GenerateResponse(
        test_cases=test_cases,
        edge_scenarios=data.get("edge_scenarios", []),
        potential_bugs=data.get("potential_bugs", []),
        coverage_summary=coverage,
        raw_story=raw_story,
    )


def _call_ollama_with_span(model: str, messages: list, options: dict, prompt_for_tokens: str = "") -> str:
    """
    Blocking Ollama chat call wrapped in an llm_span.
    Runs in main thread or thread executor — ContextVars propagate in both cases.
    """
    system_content = messages[0].get("content", "") if messages and messages[0].get("role") == "system" else ""
    user_content = messages[-1].get("content", "") if messages else prompt_for_tokens

    with tracer.llm_span(
        "ollama_chat",
        model=model,
        system_prompt=system_content,
        user_prompt=user_content,
        temperature=options.get("temperature", OLLAMA_TEMPERATURE),
        num_ctx=options.get("num_ctx", OLLAMA_CONTEXT_SIZE),
        num_predict=options.get("num_predict", 4096),
    ) as s:
        t0 = time.monotonic()
        response = _ollama.chat(model=model, messages=messages, options=options)
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        content = response["message"]["content"]

        output_tokens = tracer.estimate_tokens(content)
        input_tokens = tracer.estimate_tokens(system_content + user_content)
        tracer.update_span(
            s,
            output={"response_preview": content[:400]},
            metadata={
                "response_chars": len(content),
                "inference_time_ms": elapsed_ms,
                "tokens_output_estimated": output_tokens,
                "tokens_input_estimated": input_tokens,
                "usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            },
        )
        logger.info(
            "Ollama call complete",
            extra={
                "model": model,
                "inference_time_ms": elapsed_ms,
                "response_chars": len(content),
                "tokens_in_estimated": input_tokens,
                "tokens_out_estimated": output_tokens,
            },
        )
        return content


async def stream_generate_test_cases(req: GenerateRequest):
    """
    Async generator SSE.
    Tracks TTFT (time-to-first-token) and chunk count.
    """
    rag_context = ""
    if req.use_rag:
        try:
            from backend.services.rag_service import semantic_search
            with tracer.rag_span(req.user_story) as s:
                rag_context = semantic_search(req.user_story)
                tracer.update_span(
                    s,
                    output={"context_chars": len(rag_context), "has_context": bool(rag_context)},
                )
            if rag_context:
                logger.info("RAG: contexto recuperado (%d chars)", len(rag_context))
        except Exception as exc:
            logger.warning("RAG no disponible: %s", exc)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    prompt = _build_prompt(req, rag_context)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]
    num_predict = _calc_num_predict(req.tc_count, req.edge_count, req.bug_count)
    num_ctx     = max(OLLAMA_CONTEXT_SIZE, num_predict + 3000)
    options = {"temperature": req.temperature, "num_ctx": num_ctx, "top_p": 0.7, "num_predict": num_predict}

    def _stream_sync() -> None:
        buf = []
        input_tokens = tracer.estimate_tokens(SYSTEM_PROMPT + prompt)
        ttft_ms: float = 0.0
        chunk_count: int = 0

        with tracer.llm_span(
            "ollama_stream",
            model=req.model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=req.temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
        ) as s:
            try:
                t0 = time.monotonic()
                for chunk in _ollama.chat(model=req.model, messages=messages,
                                         options=options, stream=True):
                    token = chunk["message"]["content"]
                    buf.append(token)
                    if not ttft_ms and token:
                        ttft_ms = round((time.monotonic() - t0) * 1000)
                    chunk_count += 1
                    loop.call_soon_threadsafe(queue.put_nowait, {"token": token})

                elapsed = round((time.monotonic() - t0) * 1000)
                accumulated = "".join(buf)
                output_tokens = tracer.estimate_tokens(accumulated)
                tracer.update_span(
                    s,
                    output={"response_preview": accumulated[:300]},
                    metadata={
                        "response_chars": len(accumulated),
                        "inference_time_ms": elapsed,
                        "ttft_ms": ttft_ms,
                        "chunks_received": chunk_count,
                        "tokens_output_estimated": output_tokens,
                        "tokens_input_estimated": input_tokens,
                        "usage": {
                            "prompt_tokens": input_tokens,
                            "completion_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens,
                        },
                    },
                )
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"done": True, "accumulated": accumulated, "elapsed": elapsed, "ttft_ms": ttft_ms},
                )
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, {"error": str(exc)})

    async with _llm_semaphore:
        logger.info("Iniciando streaming | modelo=%s | rag=%s", req.model, bool(rag_context))
        loop.run_in_executor(None, _stream_sync)

        accumulated = ""
        elapsed = 0.0

        while True:
            item = await queue.get()

            if "token" in item:
                accumulated += item["token"]
                yield f"data: {json.dumps({'token': item['token']})}\n\n"

            elif "error" in item:
                logger.error("Error en stream ollama: %s", item["error"])
                yield f"data: {json.dumps({'error': item['error']})}\n\n"
                break

            elif "done" in item:
                accumulated = item["accumulated"]
                elapsed = item["elapsed"]
                logger.info("Stream completo | modelo=%s | tiempo=%.2fms | ttft=%.2fms",
                            req.model, elapsed, item.get("ttft_ms", 0))
                break

    try:
        data = _parse_llm_output(accumulated)
        result = _build_response(data, req.user_story)
        result_dict = result.model_dump()
        for tc in result_dict.get("test_cases") or []:
            yield f"data: {json.dumps({'case': tc})}\n\n"
        yield f"data: {json.dumps({'result': result_dict})}\n\n"
    except Exception as e:
        logger.error("Error parseando stream | %s", str(e))
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


async def generate_test_cases(req: GenerateRequest) -> GenerateResponse:
    """
    Non-streaming generation. Called from within a root_trace() in the generate route.
    Creates child spans that attach to the parent trace automatically.
    """
    rag_context = ""
    if req.use_rag:
        try:
            from backend.services.rag_service import semantic_search
            with tracer.rag_span(req.user_story) as s:
                rag_context = semantic_search(req.user_story)
                tracer.update_span(
                    s,
                    output={"context_chars": len(rag_context), "has_context": bool(rag_context)},
                )
        except Exception as exc:
            logger.warning("RAG no disponible: %s", exc)

    cats = getattr(req, "categories", []) or []
    with tracer.prompt_span(req.tc_count, cats, len(rag_context)) as ps:
        prompt = _build_prompt(req, rag_context)
        tracer.update_span(ps, output={
            "prompt_chars": len(prompt),
            "prompt_tokens_est": tracer.estimate_tokens(prompt),
            "rag_chars": len(rag_context),
        })

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    num_predict = _calc_num_predict(req.tc_count, req.edge_count, req.bug_count)
    num_ctx     = max(OLLAMA_CONTEXT_SIZE, num_predict + 3000)
    options = {"temperature": req.temperature, "num_ctx": num_ctx, "top_p": 0.7, "num_predict": num_predict}

    async with _llm_semaphore:
        logger.info("Iniciando generación | modelo=%s | rag=%s", req.model, bool(rag_context))
        t0 = time.monotonic()

        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(
            None,
            lambda: _call_ollama_with_span(req.model, messages, options, prompt),
        )

        logger.info("Respuesta recibida | modelo=%s | tiempo=%.2fs", req.model, time.monotonic() - t0)

    data = _parse_llm_output(content)
    return _build_response(data, req.user_story)
