from unittest.mock import patch


async def test_models_with_ollama_available(client):
    mock_list = {"models": [{"name": "llama3.2"}, {"name": "mistral"}]}
    with patch("backend.routes.generate.ollama.list", return_value=mock_list):
        response = await client.get("/models")
    assert response.status_code == 200
    assert "llama3.2" in response.json()["models"]


async def test_models_fallback_when_ollama_unavailable(client):
    with patch("backend.routes.generate.ollama.list", side_effect=Exception("Ollama no disponible")):
        response = await client.get("/models")
    assert response.status_code == 200
    assert len(response.json()["models"]) > 0
