import asyncio
import json
import logging
import re
import time

import ollama

from backend.config import OLLAMA_TEMPERATURE, OLLAMA_CONTEXT_SIZE
from backend.schemas.models import GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)

_llm_semaphore = asyncio.Semaphore(1)

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


def _build_prompt(req: GenerateRequest) -> str:
    return f"""Historia de Usuario / Requisito:
{req.user_story}

Contexto adicional:
{req.context if req.context else 'Ninguno'}

INSTRUCCION OBLIGATORIA: TODA LA RESPUESTA DEBE SER 100% EN IDIOMA ESPAÑOL.
Ninguna palabra, descripcion, titulo o texto debe estar en ingles.

Genera casos de prueba completos, escenarios limite y bugs potenciales para lo anterior.
GENERA MINIMO 15 CASOS DE PRUEBA MINIMO.
INCLUYE MINIMO 3 CASOS NO FUNCIONALES DE RENDIMIENTO.
INCLUYE MINIMO 2 CASOS DE SEGURIDAD.
INCLUYE MINIMO 2 CASOS DE USABILIDAD.
CADA CASO NO FUNCIONAL DEBE TENER VALORES NUMERICOS CONCRETOS Y MEDIBLES.
CADA CASO DEBE TENER MINIMO 5 PASOS DETALLADOS Y ESPECIFICOS.
Recuerda: responde SOLAMENTE con el objeto JSON crudo, sin ningun otro texto."""


def _parse_llm_output(content: str) -> dict:
    json_match = re.search(r"\{[\s\S]*\}", content)
    if not json_match:
        raise ValueError("El modelo no devolvió un JSON válido")

    json_str = json_match.group()
    json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as first_err:
        logger.warning("Fallo JSON primario, intentando reparación | fragmento=%s", json_str[:200])
        json_str = json_str.replace("'", '"')
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            logger.error("Fallo JSON irreparable | error=%s | fragmento=%s", first_err, json_str[:300])
            raise


async def stream_generate_test_cases(req: GenerateRequest):
    """Async generator que emite tokens SSE y al final el resultado JSON completo."""
    accumulated = ""
    async with _llm_semaphore:
        logger.info("Iniciando streaming | modelo=%s", req.model)
        t0 = time.monotonic()

        for chunk in ollama.chat(
            model=req.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(req)},
            ],
            options={"temperature": req.temperature, "num_ctx": OLLAMA_CONTEXT_SIZE, "top_p": 0.7},
            stream=True,
        ):
            token = chunk["message"]["content"]
            accumulated += token
            yield f"data: {json.dumps({'token': token})}\n\n"
            await asyncio.sleep(0)

        elapsed = time.monotonic() - t0
        logger.info("Stream completo | modelo=%s | tiempo=%.2fs", req.model, elapsed)

    try:
        data = _parse_llm_output(accumulated)
        result = GenerateResponse(
            test_cases=data.get("test_cases", []),
            edge_scenarios=data.get("edge_scenarios", []),
            potential_bugs=data.get("potential_bugs", []),
            coverage_summary=data.get("coverage_summary", {
                "total_test_cases": len(data.get("test_cases", [])),
                "categories_covered": [],
                "estimated_coverage_percent": 75,
                "missing_areas": [],
            }),
            raw_story=req.user_story,
        )
        yield f"data: {json.dumps({'result': result.model_dump()})}\n\n"
    except Exception as e:
        logger.error("Error parseando stream | %s", str(e))
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


async def generate_test_cases(req: GenerateRequest) -> GenerateResponse:
    async with _llm_semaphore:
        logger.info("Iniciando generación | modelo=%s", req.model)
        t0 = time.monotonic()

        response = ollama.chat(
            model=req.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(req)},
            ],
            options={"temperature": req.temperature, "num_ctx": OLLAMA_CONTEXT_SIZE, "top_p": 0.7},
        )

        elapsed = time.monotonic() - t0
        logger.info("Respuesta recibida | modelo=%s | tiempo=%.2fs", req.model, elapsed)

    data = _parse_llm_output(response["message"]["content"])

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
        raw_story=req.user_story,
    )
