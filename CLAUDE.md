# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Descripción del Proyecto

Generador local de casos de prueba impulsado por IA. Toma historias de usuario/requisitos y produce 12-15+ casos de prueba estructurados en español, cubriendo 7 categorías (happy path, edge cases, negativo, seguridad, rendimiento, usabilidad, compatibilidad), junto con escenarios borde, bugs potenciales y métricas de cobertura.

**Stack**: FastAPI + Uvicorn (backend), Ollama (LLM local), Opik (observabilidad), DeepEval/GEval (evaluación), HTML/CSS/JS vanilla (frontend), CrewAI (agentes — Sprint Acad. 2), ChromaDB (vector store — Sprint Acad. 1).

## Comandos

### Configuración inicial
```bash
# Instalar Ollama desde https://ollama.ai, luego descargar los modelos
ollama pull llama3.2
ollama pull mistral

# IMPORTANTE en Windows: crear venv en ruta corta para evitar el límite de 260 chars
python -m venv C:/qa_venv
C:/qa_venv/Scripts/activate      # Windows PowerShell: C:\qa_venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-eval.txt   # DeepEval (opcional)
```

### Ejecutar la aplicación
```bash
cd backend
uvicorn main:app --reload --port 8000
# Abrir http://localhost:8000
```

### Ejecutar el evaluador standalone
```bash
cd evaluator
python metrics.py
```

### Ejecutar el notebook del Corte 1
```bash
# Desde la raíz del proyecto
jupyter notebook notebooks/corte1_prototipo.ipynb
```

## Variables de entorno (.env)

```
OLLAMA_MODEL=llama3.2
OLLAMA_TEMPERATURE=0.25
OLLAMA_CONTEXT_SIZE=8192
APP_PORT=8000

# Opik — obtener API key en https://www.comet.com/opik
OPIK_API_KEY=tu_api_key
OPIK_PROJECT_NAME=QA-Test-Generator
```

## Arquitectura

### Estructura de archivos clave
```
backend/
├── main.py              — App FastAPI, CORS, rutas, archivos estáticos
├── config.py            — Variables de entorno (Ollama + Opik)
├── routes/
│   ├── generate.py      — POST /generate, /generate/stream, GET /models, /health, /model-status
│   └── evaluate.py      — POST /evaluate
├── services/
│   ├── llm_service.py   — Prompt del sistema, llamada Ollama, parseo JSON, trazas Opik
│   ├── eval_service.py  — Wrapper DeepEval (importación condicional)
│   ├── rag_service.py   — [PENDIENTE Sprint Acad.1] Embeddings + ChromaDB
│   └── agent_service.py — [PENDIENTE Sprint Acad.2] Agentes CrewAI
└── schemas/models.py    — Pydantic: GenerateRequest/Response, EvaluateRequest/Response

frontend/
├── index.html           — Shell HTML
├── js/
│   ├── api.js           — loadModels(), health check, /model-status
│   ├── app.js           — generate(), evaluate(), export, streaming SSE, templates, historial
│   └── render.js        — renderTC(), renderEdge(), renderBugs(), renderCoverage()
└── css/styles.css

evaluator/metrics.py     — OllamaEvalModel + 3 métricas GEval (Coverage/Relevancy/Consistency)
notebooks/
└── corte1_prototipo.ipynb  — Notebook Corte 1 (Opik + DeepEval + arquitectura)
```

### Flujo de datos
1. Frontend envía `POST /generate/stream` con `{user_story, model, temperature, context}`
2. `llm_service.py` crea traza Opik, llama a Ollama con streaming SSE
3. Tokens se emiten al frontend en tiempo real; al completar se cierra la traza Opik
4. Respuesta JSON del LLM se parsea y repara con regex si es necesario
5. Frontend renderiza 4 tabs: Casos de Prueba, Escenarios Borde, Bugs, Cobertura

### Opik — trazas de observabilidad
- `stream_generate_test_cases()`: usa `opik.Opik().trace()` manualmente (generador async)
- `generate_test_cases()`: usa `@opik.track` sobre `_tracked_ollama_call()`
- SDK lee `OPIK_API_KEY` y `OPIK_PROJECT_NAME` automáticamente de `os.environ`
- Se habilita solo si `OPIK_API_KEY` está definida; falla silenciosamente si no

### Decisiones de diseño importantes
- **Sin base de datos**: La API es completamente stateless; no hay persistencia
- **Sin autenticación**: Diseñado exclusivamente para uso local
- **Temperatura 0.25**: Baja creatividad para maximizar consistencia en el output
- **Reparación de JSON**: `llm_service.py` incluye lógica de fallback con regex para corregir JSON mal formado del LLM
- **Métricas mock en frontend**: La cobertura mostrada en UI se calcula localmente; las métricas reales de DeepEval corren en `evaluator/metrics.py` o vía `POST /evaluate`
- **DeepEval opcional**: Se instala desde `requirements-eval.txt`; el backend falla con 503 si no está disponible
- **venv en ruta corta**: En Windows, crear el venv en `C:/qa_venv` para evitar el límite de 260 caracteres en rutas (litellm tiene paths muy largos)

### Prompt del sistema (crítico)
El comportamiento del LLM está controlado por 9 instrucciones obligatorias en `backend/services/llm_service.py` (constante `SYSTEM_PROMPT`). Cualquier cambio en categorías, idioma, o formato de output debe modificarse ahí.

### API endpoints
| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/generate` | Genera casos de prueba (sin streaming) |
| `POST` | `/generate/stream` | Genera casos de prueba con streaming SSE |
| `POST` | `/evaluate` | Evalúa con DeepEval (requiere `requirements-eval.txt`) |
| `GET` | `/models` | Lista modelos Ollama disponibles |
| `GET` | `/health` | Health check (ollama: true/false, models_count) |
| `GET` | `/model-status?model=X` | Si el modelo está cargado en memoria |
| `GET` | `/` | Sirve `frontend/index.html` |
