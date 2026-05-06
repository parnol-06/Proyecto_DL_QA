import asyncio
import json
import logging
import os
import re
import time

import ollama

from backend.config import OLLAMA_HOST, OLLAMA_TEMPERATURE, OLLAMA_CONTEXT_SIZE, OPIK_API_KEY, OPIK_WORKSPACE, OPIK_PROJECT_NAME

_ollama = ollama.Client(host=OLLAMA_HOST)


def _calc_num_predict(tc_count: int, edge_count: int, bug_count: int) -> int:
    # ~280 tokens por TC (JSON con 5+ pasos en español), ~120 edge, ~160 bug, ~1000 overhead
    return max(4096, tc_count * 280 + edge_count * 120 + bug_count * 160 + 1000)
from backend.schemas.models import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)

_llm_semaphore = asyncio.Semaphore(1)

# ── Opik (observabilidad) ────────────────────────────────────────────────────
# force=True evita el prompt interactivo de confirmación de workspace.
# Necesario para entornos sin TTY (Docker, CI).
_OPIK_ENABLED = False
try:
    import opik
    if OPIK_API_KEY:
        opik.configure(
            api_key=OPIK_API_KEY,
            workspace=OPIK_WORKSPACE or None,
            force=True,
        )
        _OPIK_ENABLED = True
        logger.info("Opik configurado | workspace=%s | proyecto=%s", OPIK_WORKSPACE, OPIK_PROJECT_NAME)
    else:
        logger.warning("OPIK_API_KEY no definida — trazas deshabilitadas")
except ImportError:
    logger.warning("Paquete 'opik' no instalado — trazas deshabilitadas")
except Exception as exc:
    logger.warning("Error configurando Opik: %s", exc)

# ─────────────────────────────────────────────────────────────────────────────

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
    """Reparte tc_count lo más equitativamente posible entre las categorías."""
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
    json_match = re.search(r"\{[\s\S]*\}", content)
    if not json_match:
        raise ValueError("El modelo no devolvió un JSON válido")

    raw = json_match.group()

    # Intento 1: JSON estándar
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Intento 2: json-repair (maneja comillas faltantes, comas extra, etc.)
    try:
        from json_repair import repair_json
        repaired = repair_json(raw, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
    except Exception:
        pass

    # Intento 3: reparación manual de claves sin comillas (fallback legacy)
    try:
        fixed = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', raw)
        fixed = fixed.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError as err:
        logger.error("JSON irreparable | error=%s | fragmento=%s", err, raw[:300])
        raise


def _build_response(data: dict, raw_story: str) -> GenerateResponse:
    test_cases = data.get("test_cases", [])
    
    # Calcular automaticamente cobertura y categorias cubiertas
    covered_cats = list({tc.get("category") for tc in test_cases if tc.get("category")})
    all_expected_cats = {"happy_path", "caso_limite", "negativo", "seguridad", "rendimiento", "usabilidad", "compatibilidad"}
    coverage_pct = round((len(covered_cats) / len(all_expected_cats)) * 100, 2) if len(all_expected_cats) > 0 else 0
    missing_cats = list(all_expected_cats - set(covered_cats))
    
    default_coverage = {
        "total_test_cases": len(test_cases),
        "categories_covered": covered_cats,
        "estimated_coverage_percent": coverage_pct,
        "missing_areas": missing_cats,
    }
    
    # Usar coverage del LLM si existe, sino usar el calculado automaticamente
    coverage = data.get("coverage_summary") or default_coverage
    
    # Sobreescribir siempre valores reales calculados
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


async def stream_generate_test_cases(req: GenerateRequest):
    """
    Async generator SSE.
    El streaming síncrono de ollama corre en un thread executor para no
    bloquear el event loop — de lo contrario uvicorn cierra la conexión
    chunked antes de que termine (ERR_INCOMPLETE_CHUNKED_ENCODING).
    """
    rag_context = ""
    if req.use_rag:
        try:
            from backend.services.rag_service import semantic_search
            rag_context = semantic_search(req.user_story)
            if rag_context:
                logger.info("RAG: contexto recuperado (%d chars)", len(rag_context))
        except Exception as exc:
            logger.warning("RAG no disponible: %s", exc)

    opik_trace = None
    if _OPIK_ENABLED:
        try:
            _client = opik.Opik()
            opik_trace = _client.trace(
                name="stream_generate_test_cases",
                input={"user_story": req.user_story[:400], "model": req.model,
                       "temperature": req.temperature, "use_rag": req.use_rag},
                project_name=OPIK_PROJECT_NAME,
            )
        except Exception as exc:
            logger.warning("Error iniciando traza Opik: %s", exc)

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": _build_prompt(req, rag_context)},
    ]
    num_predict = _calc_num_predict(req.tc_count, req.edge_count, req.bug_count)
    num_ctx     = max(OLLAMA_CONTEXT_SIZE, num_predict + 3000)
    options = {"temperature": req.temperature, "num_ctx": num_ctx, "top_p": 0.7, "num_predict": num_predict}

    def _stream_sync() -> None:
        """Corre en hilo separado — nunca bloquea el event loop."""
        buf = []
        try:
            t0 = time.monotonic()
            for chunk in _ollama.chat(model=req.model, messages=messages,
                                     options=options, stream=True):
                token = chunk["message"]["content"]
                buf.append(token)
                loop.call_soon_threadsafe(queue.put_nowait, {"token": token})
            elapsed = round(time.monotonic() - t0, 2)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"done": True, "accumulated": "".join(buf), "elapsed": elapsed},
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
                logger.info("Stream completo | modelo=%s | tiempo=%.2fs", req.model, elapsed)
                break

    if opik_trace:
        try:
            opik_trace.end(output={"output_length_chars": len(accumulated),
                                   "elapsed_seconds": elapsed,
                                   "preview": accumulated[:300]})
        except Exception as exc:
            logger.warning("Error cerrando traza Opik: %s", exc)

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


if _OPIK_ENABLED:
    @opik.track(name="generate_test_cases", project_name=OPIK_PROJECT_NAME)
    def _tracked_ollama_call(user_story: str, model: str, messages: list, options: dict) -> str:
        response = _ollama.chat(model=model, messages=messages, options=options)
        return response["message"]["content"]
else:
    def _tracked_ollama_call(user_story: str, model: str, messages: list, options: dict) -> str:
        response = _ollama.chat(model=model, messages=messages, options=options)
        return response["message"]["content"]


async def generate_test_cases(req: GenerateRequest) -> GenerateResponse:
    rag_context = ""
    if req.use_rag:
        try:
            from backend.services.rag_service import semantic_search
            rag_context = semantic_search(req.user_story)
        except Exception as exc:
            logger.warning("RAG no disponible: %s", exc)

    async with _llm_semaphore:
        logger.info("Iniciando generación | modelo=%s | rag=%s", req.model, bool(rag_context))
        t0 = time.monotonic()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(req, rag_context)},
        ]
        num_predict = _calc_num_predict(req.tc_count, req.edge_count, req.bug_count)
        num_ctx     = max(OLLAMA_CONTEXT_SIZE, num_predict + 3000)
        options = {"temperature": req.temperature, "num_ctx": num_ctx, "top_p": 0.7, "num_predict": num_predict}

        content = _tracked_ollama_call(req.user_story[:400], req.model, messages, options)

        elapsed = time.monotonic() - t0
        logger.info("Respuesta recibida | modelo=%s | tiempo=%.2fs", req.model, elapsed)

    data = _parse_llm_output(content)
    return _build_response(data, req.user_story)
