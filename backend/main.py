"""
QA Test Case Generator
Copyright © 2026 Arnol Ferney Pérez & Jesus Andres Cabezas
Todos los derechos reservados.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import ollama
import json
import re
import os

app = FastAPI(title="QA Test Case Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class GenerateRequest(BaseModel):
    user_story: str
    model: str = "llama3:8b"
    context: str = ""


class GenerateResponse(BaseModel):
    test_cases: list
    edge_scenarios: list
    potential_bugs: list
    coverage_summary: dict
    raw_story: str


@app.post("/generate", response_model=GenerateResponse)
async def generate_test_cases(req: GenerateRequest):
    prompt = f"""Historia de Usuario / Requisito:
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

    try:
        response = ollama.chat(
            model=req.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.25, "num_ctx": 8192, "top_p": 0.7},
        )

        content = response["message"]["content"]

        # Limpiar cualquier texto antes o despues del JSON
        json_match = re.search(r"\{[\s\S]*\}", content)
        if not json_match:
            raise ValueError("El modelo no devolvió un JSON válido")

        json_str = json_match.group()
        
        # Reparar comillas dobles rotas
        json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Intentar segunda reparacion
            json_str = json_str.replace("'", '"')
            data = json.loads(json_str)

        return GenerateResponse(
            test_cases=data.get("test_cases", []),
            edge_scenarios=data.get("edge_scenarios", []),
            potential_bugs=data.get("potential_bugs", []),
            coverage_summary=data.get(
                "coverage_summary",
                {
                    "total_test_cases": len(data.get("test_cases", [])),
                    "categories_covered": [],
                    "estimated_coverage_percent": 75,
                    "missing_areas": [],
                },
            ),
            raw_story=req.user_story,
        )

    except ollama.ResponseError as e:
        raise HTTPException(status_code=503, detail=f"Error de Ollama: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Error parseando JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@app.get("/models")
async def list_models():
    try:
        models = ollama.list()
        return {"models": [m["name"] for m in models.get("models", [])]}
    except Exception:
        return {"models": ["llama3.2", "mistral", "phi3"]}


# Servir Frontend
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "../frontend/index.html"))

@app.get("/health")
async def health():
    return {"status": "ok"}
