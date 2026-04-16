# QA Test Case Generator 🧪
> Powered by Ollama (local LLM) + DeepEval (metrics) + FastAPI

---

## Stack

| Capa | Tecnología |
|------|-----------|
| LLM local | Ollama (llama3.2, mistral, phi3) |
| Backend | FastAPI + Python |
| Evaluación | DeepEval (GEval, AnswerRelevancy, Faithfulness) |
| Frontend | HTML/CSS/JS (single file, sin framework) |

---

## Setup rápido

### 1. Instalar Ollama
```bash
# Mac / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Descargar modelo
ollama pull llama3.2
# o
ollama pull mistral
```

### 2. Instalar dependencias Python
```bash
cd qa-generator
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Levantar la aplicación (UN SOLO COMANDO) ✅
```bash
cd backend
uvicorn main:app --reload --port 8000
```

✅ **¡Listo! Backend y Frontend corren juntos en el mismo servidor.**
Abre directamente en tu navegador: **http://localhost:8000**

No necesitas levantar servidores separados, no necesitas abrir archivos html directamente.

---

## Métricas DeepEval

### 1. Test Coverage (G-Eval)
Evalúa si los casos generados cubren todos los escenarios del requerimiento.
- Umbral mínimo: **0.6**
- Penaliza: happy path sin negativos, sin edge cases

### 2. Test Relevancy (G-Eval)
Evalúa si los casos son relevantes al requerimiento dado.
- Umbral mínimo: **0.7**
- Penaliza: casos genéricos no relacionados

### 3. Test Consistency (G-Eval)
Evalúa la consistencia interna de los casos generados.
- Umbral mínimo: **0.65**
- Penaliza: pasos que no llevan al resultado, prioridades incorrectas

### Correr métricas standalone:
```bash
cd evaluator
python metrics.py
```

---

## Estructura del proyecto

```
qa-generator/
├── backend/
│   └── main.py              # FastAPI app + Ollama client
├── evaluator/
│   └── metrics.py           # DeepEval metrics (GEval x3)
├── frontend/
│   └── index.html           # UI completa (single file)
├── requirements.txt
└── README.md
```

---

## Endpoints API

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/generate` | Genera test cases desde una historia de usuario |
| GET | `/models` | Lista modelos Ollama disponibles |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI automático |

### Ejemplo de request:
```json
POST /generate
{
  "user_story": "Como usuario quiero hacer login con email y contraseña...",
  "model": "llama3.2",
  "context": "App web de e-commerce"
}
```

---

## Cómo explicarlo en una entrevista

1. **Problema real**: Los QAs escriben casos de prueba manualmente → lento y propenso a olvidos
2. **Solución**: LLM local (privacidad, sin costos de API) genera casos estructurados
3. **Evaluación**: DeepEval con G-Eval mide calidad real del output, no solo que "responda algo"
4. **Diferenciador**: Todo corre offline → datos sensibles nunca salen de la empresa

---

## Ideas de extensión

- [ ] Exportar casos a JIRA / TestRail via API
- [ ] Generar código de test automatizado (Pytest, Cypress)
- [ ] Historial de generaciones con comparación de métricas
- [ ] Fine-tuning del modelo con casos de prueba propios
