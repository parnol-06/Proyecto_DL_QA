from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import ollama
import json
import re

app = FastAPI(title="QA Test Case Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """You are a senior QA engineer expert in test case design.
Given a user story or requirement, you MUST respond ONLY with a valid JSON object.
No markdown, no explanation, just the raw JSON.

The JSON structure must be:
{
  "test_cases": [
    {
      "id": "TC-001",
      "title": "string",
      "category": "happy_path | edge_case | negative | security | performance",
      "priority": "high | medium | low",
      "preconditions": ["string"],
      "steps": ["string"],
      "expected_result": "string",
      "test_type": "functional | integration | ui | api"
    }
  ],
  "edge_scenarios": [
    {
      "id": "ES-001",
      "scenario": "string",
      "risk_level": "high | medium | low",
      "description": "string"
    }
  ],
  "potential_bugs": [
    {
      "id": "BUG-001",
      "title": "string",
      "area": "string",
      "likelihood": "high | medium | low",
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
    model: str = "llama3.2"
    context: str = ""


class GenerateResponse(BaseModel):
    test_cases: list
    edge_scenarios: list
    potential_bugs: list
    coverage_summary: dict
    raw_story: str


@app.post("/generate", response_model=GenerateResponse)
async def generate_test_cases(req: GenerateRequest):
    prompt = f"""User Story / Requirement:
{req.user_story}

Additional context:
{req.context if req.context else 'None'}

Generate comprehensive test cases, edge scenarios, and potential bugs for the above.
Remember: respond ONLY with the raw JSON object."""

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


@app.get("/health")
async def health():
    return {"status": "ok"}
