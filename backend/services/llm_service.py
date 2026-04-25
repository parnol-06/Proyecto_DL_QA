import asyncio
import json
import logging
import os
import re
import time

import ollama

from backend.config import OLLAMA_TEMPERATURE, OLLAMA_CONTEXT_SIZE, OPIK_API_KEY, OPIK_WORKSPACE, OPIK_PROJECT_NAME
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
INSTRUCCION OBLIGATORIA N°2: DEBES GENERAR MINIMO 12 CASOS DE PRUEBA. NO MENOS.
INSTRUCCION OBLIGATORIA N°3: DEBES INCLUIR TODAS LAS CATEGORIAS: happy_path, caso_limite, negativo, seguridad, rendimiento, usabilidad, compatibilidad.
INSTRUCCION OBLIGATORIA N°4: CADA CASO DE PRUEBA DEBE TENER MINIMO 5 PASOS DETALLADOS.
INSTRUCCION OBLIGATORIA N°5: NO GENERES SOLO CASOS FUNCIONALES BASICOS. DEBES CUBRIR TODOS LOS TIPOS DE PRUEBA.
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


def _build_prompt(req: GenerateRequest, rag_context: str = "") -> str:
    rag_section = (
        f"\n\nCONTEXTO DE BASE DE CONOCIMIENTO QA (usa esta información para enriquecer los casos):\n"
        f"{rag_context}\n"
        if rag_context else ""
    )
    cats = getattr(req, "categories", [])
    all_cats = ["happy_path", "caso_limite", "negativo", "seguridad", "rendimiento", "usabilidad", "compatibilidad"]
    active_cats = cats if cats else all_cats
    cat_list = ", ".join(active_cats)

    return f"""Historia de Usuario / Requisito:
{req.user_story}

Contexto adicional:
{req.context if req.context else 'Ninguno'}
{rag_section}
INSTRUCCION OBLIGATORIA: TODA LA RESPUESTA DEBE SER 100% EN IDIOMA ESPAÑOL.
Ninguna palabra, descripcion, titulo o texto debe estar en ingles.

CATEGORIAS A GENERAR: {cat_list}
Solo genera casos de prueba para las categorías listadas arriba. No uses otras categorías.

Genera casos de prueba completos, escenarios limite y bugs potenciales para lo anterior.
GENERA MINIMO 12 CASOS DE PRUEBA.
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
    return GenerateResponse(
        test_cases=data.get("test_cases", []),
        edge_scenarios=data.get("edge_scenarios", []),
        potential_bugs=data.get("potential_bugs", []),
        coverage_summary=data.get("coverage_summary", {
            "total_test_cases": len(data.get("test_cases", [])),
            "categories_covered": [],
            "estimated_coverage_percent": 75,
            "missing_areas": [],
        }),
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
    options = {"temperature": req.temperature, "num_ctx": OLLAMA_CONTEXT_SIZE, "top_p": 0.7, "num_predict": 4096}

    def _stream_sync() -> None:
        """Corre en hilo separado — nunca bloquea el event loop."""
        buf = []
        try:
            t0 = time.monotonic()
            for chunk in ollama.chat(model=req.model, messages=messages,
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
        response = ollama.chat(model=model, messages=messages, options=options)
        return response["message"]["content"]
else:
    def _tracked_ollama_call(user_story: str, model: str, messages: list, options: dict) -> str:
        response = ollama.chat(model=model, messages=messages, options=options)
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
        options = {"temperature": req.temperature, "num_ctx": OLLAMA_CONTEXT_SIZE, "top_p": 0.7, "num_predict": 4096}

        content = _tracked_ollama_call(req.user_story[:400], req.model, messages, options)

        elapsed = time.monotonic() - t0
        logger.info("Respuesta recibida | modelo=%s | tiempo=%.2fs", req.model, elapsed)

    data = _parse_llm_output(content)
    return _build_response(data, req.user_story)
