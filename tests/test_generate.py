import json
from unittest.mock import patch

VALID_STORY = "Como usuario quiero iniciar sesión con email y contraseña para acceder a mi cuenta personal."

MOCK_LLM_RESPONSE = {
    "message": {
        "content": json.dumps({
            "test_cases": [
                {
                    "id": "TC-001", "title": "Login exitoso", "category": "happy_path",
                    "priority": "alto", "preconditions": ["Usuario registrado"],
                    "steps": ["Abrir app", "Ingresar email", "Ingresar contraseña", "Clic login", "Verificar dashboard"],
                    "expected_result": "El usuario accede al dashboard", "test_type": "funcional",
                }
            ],
            "edge_scenarios": [{"id": "ES-001", "scenario": "Email vacío", "risk_level": "alto", "description": "Sin email"}],
            "potential_bugs": [{"id": "BUG-001", "title": "SQL injection", "area": "auth", "likelihood": "medio", "description": "Input no sanitizado", "suggested_test": "Inyectar SQL"}],
            "coverage_summary": {"total_test_cases": 1, "categories_covered": ["happy_path"], "estimated_coverage_percent": 75, "missing_areas": []},
        })
    }
}


async def test_generate_valid_input(client):
    with patch("backend.services.llm_service.ollama.chat", return_value=MOCK_LLM_RESPONSE):
        response = await client.post("/generate", json={"user_story": VALID_STORY})
    assert response.status_code == 200
    body = response.json()
    assert len(body["test_cases"]) == 1
    assert body["test_cases"][0]["id"] == "TC-001"


async def test_generate_empty_story_returns_422(client):
    response = await client.post("/generate", json={"user_story": ""})
    assert response.status_code == 422


async def test_generate_too_short_returns_422(client):
    response = await client.post("/generate", json={"user_story": "muy corto"})
    assert response.status_code == 422


async def test_generate_too_long_returns_422(client):
    response = await client.post("/generate", json={"user_story": "x" * 3001})
    assert response.status_code == 422


async def test_generate_repairs_broken_json(client):
    broken_response = {
        "message": {
            "content": """{
                test_cases: [{
                    id: "TC-001", title: "Login", category: "happy_path",
                    priority: "alto", preconditions: ["Usuario registrado"],
                    steps: ["Paso 1", "Paso 2", "Paso 3", "Paso 4", "Paso 5"],
                    expected_result: "OK", test_type: "funcional"
                }],
                edge_scenarios: [], potential_bugs: [],
                coverage_summary: {total_test_cases: 1, categories_covered: [], estimated_coverage_percent: 50, missing_areas: []}
            }"""
        }
    }
    with patch("backend.services.llm_service.ollama.chat", return_value=broken_response):
        response = await client.post("/generate", json={"user_story": VALID_STORY})
    assert response.status_code == 200
    assert len(response.json()["test_cases"]) == 1
