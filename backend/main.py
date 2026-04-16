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

SYSTEM_PROMPT = """Eres un ingeniero QA senior experto en diseño de casos de prueba.

✅ 🔴 INSTRUCCION ABSOLUTAMENTE OBLIGATORIA: TODA TU RESPUESTA DEBE SER EXCLUSIVAMENTE EN IDIOMA ESPAÑOL.
✅ NINGUNA PALABRA, TITULO, DESCRIPCION O TEXTO PUEDE ESTAR EN INGLES BAJO NINGUN CONCEPTO.
✅ TODOS LOS CAMPOS DEL JSON, TODAS LAS DESCRIPCIONES, TODOS LOS MENSAJES DEBEN SER EN ESPAÑOL.

Dada una historia de usuario o requisito, DEBES responder SOLAMENTE con un objeto JSON válido.
Sin formato markdown, sin explicaciones, solo el JSON crudo.

La estructura JSON debe ser:
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "string",
      "category": "happy_path | caso_limite | negativo | seguridad | rendimiento",
      "priority": "alto | medio | bajo",
      "preconditions": ["string"],
      "steps": ["string"],
      "expected_result": "string",
      "test_type": "funcional | integracion | ui | api"
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

✅ INSTRUCCION OBLIGATORIA: TODA LA RESPUESTA DEBE SER 100% EN IDIOMA ESPAÑOL.
Ninguna palabra, descripcion, titulo o texto debe estar en ingles.

Genera casos de prueba completos, escenarios limite y bugs potenciales para lo anterior.
Recuerda: responde SOLAMENTE con el objeto JSON crudo, sin ningun otro texto."""

    try:
        response = ollama.chat(
            model=req.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.3},
        )

        content = response["message"]["content"]

        json_match = re.search(r"\{[\s\S]*\}", content)
        if not json_match:
            raise ValueError("No JSON found in model response")

        data = json.loads(json_match.group())

        return GenerateResponse(
            test_cases=data.get("test_cases", []),
            edge_scenarios=data.get("edge_scenarios", []),
            potential_bugs=data.get("potential_bugs", []),
            coverage_summary=data.get(
                "coverage_summary",
                {
                    "total_test_cases": 0,
                    "categories_covered": [],
                    "estimated_coverage_percent": 0,
                    "missing_areas": [],
                },
            ),
            raw_story=req.user_story,
        )

    except ollama.ResponseError as e:
        raise HTTPException(status_code=503, detail=f"Ollama error: {str(e)}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Model returned invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
