# QA Test Case Generator

> Genera suites de casos de prueba a partir de historias de usuario usando LLMs locales, RAG y agentes CrewAI.

**Backend:** FastAPI + Python 3.11 &nbsp;|&nbsp; **LLMs:** Ollama &nbsp;|&nbsp; **Agentes:** CrewAI &nbsp;|&nbsp; **Evaluación:** DeepEval &nbsp;|&nbsp; **Vector DB:** ChromaDB &nbsp;|&nbsp; **Observabilidad:** Opik

---

## Arquitectura

```
Historia de usuario (UI / API)
         |
         v
  +---------------------------+
  |   Frontend                |  React 18 + TypeScript + Vite 5
  |   (SPA — frontend/dist)   |  SSE streaming · export · batch mode
  |                           |  KPI bar · 5 tabs · pipeline trace
  +---------------------------+
              | HTTP / SSE
              v
  +-----------------------------+     +-------------------+
  |   FastAPI (Uvicorn)         |---->|  RAG Service      |
  |                             |     |  ChromaDB +       |
  |   ObservabilityMiddleware   |     |  nomic-embed-text |
  |   (X-Request-ID por req)    |     +-------------------+
  |   Structured JSON logging   |
  +-----------------------------+
         |              |
         v              v
  +-----------+  +----------------+
  | LLM Svc   |  | Agent Service  |
  | Ollama    |  | CrewAI         |
  | semáforo  |  | 3 agentes      |
  | concurr.  |  | + fallback     |
  +-----------+  +----------------+
         |
         v
  +--------------+
  | Eval Service |
  | DeepEval     |
  | 5 métricas   |
  | GEval        |
  +--------------+
         |
         v
  +--------------+
  |    Opik      |  Trazas · feedback scores · Generate→Evaluate
  +--------------+
```

---

## Inicio rápido

**Requisito previo:** tener [Ollama](https://ollama.com) instalado y corriendo en el host con al menos un modelo descargado (`ollama pull qwen2.5:7b`).

**Único comando:**
```bash
docker compose up --build
```

Esto se encarga automáticamente de:
- Construir la imagen React + Python (multi-stage)
- Esperar que Ollama esté disponible en el host (hasta 120 s)
- Descargar el modelo de embedding `nomic-embed-text`
- Construir el índice RAG desde `corpus/`
- Iniciar el servidor FastAPI en el puerto 8000

Abre en el navegador: **http://localhost:8000**

> La primera ejecución tarda mientras descarga modelos. Las siguientes arrancan en segundos.

### Modo desarrollo (Vite hot-reload)

```bash
# Levanta el backend + el servidor Vite con proxy inverso a :8000
docker compose --profile dev up
```

- Backend FastAPI: **http://localhost:8000**
- Frontend Vite: **http://localhost:5173** (hot-reload, proxies API al backend)

---

## Comandos útiles

```bash
# Ver logs en tiempo real
docker compose logs -f app

# Reconstruir índice RAG manualmente
docker compose exec app python scripts/build_index.py

# Apagar (conserva datos y modelos)
docker compose down

# Reset completo (borra volúmenes y el índice RAG)
docker compose down -v
```

---

## Funcionalidades

- Generación de casos de prueba con streaming en tiempo real (SSE)
- Pipeline de 3 agentes especializados (Generator → Reviewer → Optimizer)
- RAG con corpus de buenas prácticas QA, OWASP, IEEE 829 y performance testing
- Evaluación automática con 5 métricas personalizadas DeepEval (GEval)
- Exportación a JSON, CSV, Markdown y Excel (XLSX)
- Modo batch para múltiples historias (separadas por `---`)
- 8 plantillas predefinidas para pruebas rápidas
- Filtrado en vivo por categoría y prioridad
- Búsqueda de texto en los casos generados
- Regeneración individual de casos de prueba (`/regenerate-tc`)
- Descarga de modelos Ollama desde la UI (`/pull-model`)
- Persistencia de estado en `localStorage` (último resultado, configuración)
- Semáforo de concurrencia para no sobrecargar el LLM
- **Logging estructurado** con salida JSON y correlación por `request_id` / `evaluation_id`
- **Observabilidad distribuida** con Opik: trazas completas, TTFT, correlación Generate→Evaluate

---

## Estructura del proyecto

```
Proyecto_DL_QA/
├── .github/
│   └── workflows/ci.yml         # CI: pytest en push/PR a main
├── backend/
│   ├── main.py                  # FastAPI app, middleware CORS, lifespan
│   ├── config.py                # Variables de entorno (dotenv + defaults)
│   ├── observability/
│   │   ├── opik_manager.py      # root_trace(), child_span(), spans especializados
│   │   ├── tracer.py            # API pública (re-exporta todo el módulo)
│   │   ├── middleware.py        # ObservabilityMiddleware: X-Request-ID por request
│   │   ├── decorators.py        # @trace_pipeline, @trace_agent, @trace_llm, @trace_rag, @trace_eval
│   │   └── __init__.py
│   ├── routes/
│   │   ├── generate.py          # /generate, /generate/stream, /generate/agents, /generate/agents/stream
│   │   └── evaluate.py          # /evaluate, /evaluate/stream
│   ├── services/
│   │   ├── llm_service.py       # Ollama + streaming + TTFT + reparación JSON
│   │   ├── rag_service.py       # ChromaDB + nomic-embed-text
│   │   ├── agent_service.py     # CrewAI 3 agentes + fallback directo
│   │   └── eval_service.py      # Orquestador DeepEval (batch + streaming)
│   ├── utils/
│   │   ├── logging_config.py    # JSON/text logging + ContextVar correlation IDs
│   │   └── json_utils.py        # Parseo y reparación JSON de salida LLM
│   └── schemas/models.py        # Pydantic: request/response + trace_id correlation
├── evaluator/
│   └── metrics.py               # OllamaEvalModel + 5 GEval metrics + streaming runner
├── frontend/
│   ├── index.html               # Entry point legacy (fallback sin dist/)
│   ├── css/styles.css
│   ├── js/                      # JS legacy (fallback cuando no hay dist/)
│   │   ├── api.js
│   │   ├── render.js
│   │   ├── store.js
│   │   └── components/          # AgentPipeline, EvalPipeline, MetricCard, StreamMonitor, TCCard, WorkflowBar
│   ├── package.json             # React 18 · Vite 5 · Tailwind 3 · Zustand 5 · Framer Motion
│   ├── vite.config.ts           # Proxy dev → :8000, chunks vendor (react, motion, zustand, xlsx)
│   ├── tailwind.config.ts
│   └── src/                     # SPA React + TypeScript (producción)
│       ├── App.tsx              # Layout 3 col: Sidebar | main (KPI + 5 tabs) | RightPanel
│       ├── main.tsx
│       ├── styles/globals.css   # Design tokens CSS, skeleton, glass, animations
│       ├── types/index.ts       # TestCase, GenerateResult, AgentTrace, MetricResult…
│       ├── store/useStore.ts    # Estado global Zustand (result, filters, timers, toasts)
│       ├── hooks/
│       │   ├── useGenerate.ts   # generate() + generateBatch() + SSE streaming
│       │   ├── useEvaluate.ts   # evaluate() + streaming por métrica
│       │   └── useModels.ts     # lista y estado de modelos Ollama
│       ├── services/
│       │   ├── api.ts           # fetch wrapper centralizado
│       │   └── sse.ts           # Lector SSE (ReadSSE)
│       ├── lib/
│       │   ├── templates.ts     # 8 plantillas predefinidas
│       │   ├── export.ts        # copyJSON, downloadJSON, downloadCSV, downloadMarkdown, downloadXLSX
│       │   └── utils.ts         # fmtTime, scoreColor, helpers
│       └── components/
│           ├── layout/
│           │   ├── Header.tsx         # KPI bar: Test Cases · Bugs · Coverage · Score
│           │   ├── Sidebar.tsx        # Config: story, contexto, categorías, cantidad, templates
│           │   ├── RightPanel.tsx     # Evaluate, modelo LLM, export, model manager
│           │   └── WorkflowBar.tsx    # Indicador de paso activo (input→generate→evaluate→export)
│           ├── dashboard/
│           │   ├── TCCard.tsx         # Tarjeta expandible por caso de prueba + regenerar
│           │   ├── EdgeCard.tsx       # Tarjeta de escenario edge
│           │   ├── BugCard.tsx        # Tarjeta de bug potencial
│           │   ├── MetricsDashboard.tsx # Radar + barras por métrica DeepEval
│           │   └── CoveragePanel.tsx  # Resumen de cobertura por categoría
│           ├── sidebar/
│           │   ├── AgentPipeline.tsx  # Visualización del pipeline CrewAI en tiempo real
│           │   └── EvalPipeline.tsx   # Estado en vivo de la evaluación métrica a métrica
│           ├── forms/
│           │   ├── FilterChips.tsx    # Chips filtro por categoría y prioridad
│           │   └── StreamMonitor.tsx  # Monitor de tokens en streaming
│           └── ui/
│               └── Toast.tsx          # Notificaciones toast
├── corpus/
│   ├── qa_best_practices.md
│   ├── owasp_testing_guide.md
│   ├── performance_testing_principles.md
│   └── ieee_829_test_case_template.md
├── docs/
│   ├── guia_proyecto_deep_learning.md
│   └── manual_uso.md
├── scripts/
│   ├── build_index.py           # Indexa corpus/ en ChromaDB
│   ├── run_experiment.py        # 10 US × 2 configs → experiments/results.json
│   └── demo.py                  # Demo: 3 US con agentes + evaluación
├── tests/
│   ├── conftest.py
│   ├── test_generate.py
│   ├── test_health.py
│   ├── test_models.py
│   ├── test_rag_service.py
│   ├── test_agent_service.py
│   └── test_stream.py
├── experiments/                 # Resultados JSON del experimento comparativo
├── chroma_db/                   # Vector store ChromaDB (generado en ejecución)
├── mockup/                      # Referencia visual de diseño UI
├── Dockerfile                   # Multi-stage: Node 20 (build) → Python 3.11 (runtime, non-root)
├── docker-compose.yml           # Servicio app + perfil dev (frontend-dev)
├── entrypoint.sh                # Espera Ollama → embedding model → RAG → uvicorn
├── pytest.ini
├── requirements.txt             # fastapi, uvicorn, ollama, pydantic, opik, chromadb, crewai
├── requirements-eval.txt        # deepeval (opcional, Python ≤ 3.12)
├── requirements-dev.txt
└── .env.example
```

---

## Variables de entorno

Copia `.env.example` a `.env` para configurar:

| Variable | Descripción | Default |
|---|---|---|
| `OLLAMA_MODEL` | Modelo LLM para generación | `qwen2.5:7b` |
| `OLLAMA_EVAL_MODEL` | Modelo LLM para evaluación (debe ser distinto para evitar sesgo) | `llama3.2` |
| `OLLAMA_EMBED_MODEL` | Modelo de embedding (se descarga automáticamente) | `nomic-embed-text` |
| `OLLAMA_TEMPERATURE` | Temperatura del LLM | `0.25` |
| `OLLAMA_CONTEXT_SIZE` | Ventana de contexto en tokens | `8192` |
| `OLLAMA_HOST` | URL de Ollama (solo necesario en Docker) | `http://localhost:11434` |
| `APP_PORT` | Puerto del servidor FastAPI | `8000` |
| `OPIK_API_KEY` | API key de Opik — desactiva trazas si no se define | — |
| `OPIK_WORKSPACE` | Workspace de Opik | — |
| `OPIK_PROJECT_NAME` | Nombre del proyecto en Opik | `Qa_trace` |
| `LOG_FORMAT` | Formato del log: `json` (default) o `text` | `json` |
| `LOG_LEVEL` | Nivel de log: `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `ALLOWED_ORIGINS` | Orígenes CORS (JSON array) | `["*"]` |

> En Docker, `OLLAMA_HOST` se sobreescribe automáticamente a `http://host.docker.internal:11434`.

---

## Endpoints API

Documentación interactiva Swagger: **http://localhost:8000/docs**

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/generate` | Generación directa con LLM |
| `POST` | `/generate/stream` | Generación con streaming SSE |
| `POST` | `/generate/agents` | Pipeline completo de 3 agentes CrewAI |
| `POST` | `/generate/agents/stream` | Pipeline de agentes con streaming SSE |
| `POST` | `/evaluate` | Evaluación DeepEval (5 métricas, batch) |
| `POST` | `/evaluate/stream` | Evaluación con streaming SSE métrica a métrica |
| `POST` | `/regenerate-tc` | Regenera un caso de prueba individual |
| `POST` | `/pull-model` | Descarga un modelo Ollama desde la UI |
| `GET`  | `/models` | Lista modelos Ollama disponibles |
| `GET`  | `/model-status` | Estado de carga del modelo activo |
| `GET`  | `/rag/status` | Estado del índice RAG |
| `GET`  | `/health` | Health check |

---

## Pipeline de 3 agentes CrewAI

Cuando usas `/generate/agents` o `/generate/agents/stream`, la historia pasa por tres agentes en secuencia:

```
Historia de usuario
       |
       v
+---------------------+
|  Agent 1            |
|  Generator          |
|  Genera TCs en JSON |
|  cubriendo 7 cats.  |
+---------------------+
       |
       v
+---------------------+
|  Agent 2            |
|  Reviewer           |
|  Evalúa cobertura,  |
|  calidad y gaps.    |
|  Verdict:           |
|  APPROVED /         |
|  OBSERVATIONS /     |
|  REJECTED           |
+---------------------+
       |
       v
+---------------------+
|  Agent 3            |
|  Optimizer          |
|  Identifica gaps    |
|  críticos y los     |
|  especifica         |
|  completamente      |
+---------------------+
       |
       v
  Suite final consolidada
```

Si CrewAI falla, el servicio hace fallback automático a generación directa con LLM. Cada ejecución queda trazada en Opik con spans individuales por agente y tiempos reales.

---

## Logging estructurado

El módulo `backend/utils/logging_config.py` se configura en el lifespan de la aplicación.

### Formato JSON (default)

```json
{
  "ts": "2026-05-22T14:30:00.123Z",
  "level": "INFO",
  "logger": "backend.routes.generate",
  "msg": "generation complete",
  "request_id": "a1b2c3d4",
  "evaluation_id": "-",
  "tc_count": 12,
  "elapsed_s": 4.2
}
```

### Correlación de IDs

- `request_id`: asignado por `ObservabilityMiddleware` a cada request HTTP, propagado via `ContextVar` a todos los handlers y corrutinas downstream.
- `evaluation_id`: añadido en los endpoints de evaluación para correlacionar logs de una sesión DeepEval.

### Formato texto (útil en desarrollo)

```env
LOG_FORMAT=text
LOG_LEVEL=DEBUG
```

```
2026-05-22 14:30:00 | INFO     | eval=- | req=a1b2c3d4 | backend.routes.generate | generation complete
```

---

## Observabilidad (Opik)

El módulo `backend/observability/` implementa trazabilidad distribuida sobre [Opik](https://www.comet.com/site/products/opik/).

### Jerarquía de spans por endpoint

```
POST /generate/agents/stream  (root trace)
├── request_validation
├── rag_pipeline              (si use_rag=true)
│   ├── embedding_generation
│   └── chromadb_query
├── response_stream
│   └── crew_pipeline
│       ├── agent_generator
│       │   ├── llm_call_generator
│       │   └── llm_json_parse
│       ├── agent_reviewer
│       │   └── llm_call_reviewer
│       └── agent_optimizer
│           └── llm_call_optimizer
└── response_serialization

POST /evaluate  (root trace)
├── request_validation
├── deepeval_evaluation
│   ├── metric_test_coverage
│   ├── metric_test_relevancy
│   ├── metric_test_consistency
│   ├── metric_step_specificity
│   └── metric_non_functional_balance
└── response_serialization
```

### Feedback scores registrados

| Pipeline | Scores |
|---|---|
| `generate_normal` | `coverage_pct`, `tc_completeness`, `output_validity`, `rag_enabled` |
| `generate_agents` | `reviewer_score`, `coverage_pct`, `tc_completeness`, `pipeline_quality`, `rag_context_quality`, `optimization_coverage` |
| `evaluate` | `overall_score`, `test_coverage`, `test_relevancy`, `test_consistency`, `step_specificity`, `nonfunctional_balance` |
| `generate_stream` | `stream_completion`, `ttft_quality` |

### Correlación Generate → Evaluate

```json
// 1. Generar
POST /generate/agents
→ { "generation_trace_id": "abc123..." }

// 2. Evaluar vinculado a esa generación
POST /evaluate
{ "source_generation_trace_id": "abc123...", ... }
→ { "evaluation_trace_id": "def456..." }
```

### Configuración

```env
OPIK_API_KEY=tu_api_key
OPIK_WORKSPACE=tu_workspace
OPIK_PROJECT_NAME=Qa_trace
```

Si `OPIK_API_KEY` no está definida, las trazas se desactivan silenciosamente.

---

## Métricas de evaluación (DeepEval)

Todas las métricas usan `GEval` con `evaluation_steps` explícitos para evitar una llamada LLM extra de planificación. El modelo de evaluación (`OLLAMA_EVAL_MODEL`) debe ser diferente al de generación para evitar sesgo.

| Métrica | Threshold | Descripción |
|---|---|---|
| **Test Coverage** | 0.50 | Cubre happy path, negativos, edge cases y no-funcionales |
| **Test Relevancy** | 0.50 | Los casos son pertinentes a la historia de usuario |
| **Test Consistency** | 0.50 | Coherencia interna: lógica, precondiciones, nomenclatura |
| **Step Specificity** | 0.45 | Pasos concretos con datos reales, no genéricos |
| **Non-Functional Balance** | 0.40 | 25–30% de casos no-funcionales con criterios medibles |

El `generated_output` se normaliza a texto estructurado antes de evaluar para mejorar la precisión de modelos pequeños (llama3.2, mistral).

---

## Corpus RAG

| Archivo | Contenido |
|---|---|
| `qa_best_practices.md` | Principios QA, partición equivalencia, valores límite, tablas de decisión |
| `owasp_testing_guide.md` | OWASP Testing Guide v4.2: autenticación, autorización, sesiones, validación de entrada |
| `performance_testing_principles.md` | Load, stress, endurance, spike y soak testing con métricas y umbrales |
| `ieee_829_test_case_template.md` | Estándar IEEE 829-2008: estructura, campos obligatorios y formato de IDs |

---

## Scripts

```bash
# Construir índice RAG manualmente
python scripts/build_index.py

# Demo completo (3 historias, agentes + evaluación)
python scripts/demo.py

# Experimento comparativo: 10 US × 2 modelos → experiments/results.json
python scripts/run_experiment.py
```

El experimento compara Config-A (llama3.2, sin RAG) vs Config-B (mistral, con RAG) y exporta métricas de cobertura, tiempos y puntuaciones DeepEval.

---

## Tests

```bash
# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# Ejecutar suite completa
pytest tests/ -v

# Con cobertura
pytest tests/ --cov=backend
```

Los tests cubren: health check, modelos, generación (validación + reparación JSON), RAG (chunking + búsqueda semántica), agentes (parseo + pipeline + fallback) y streaming SSE.

El pipeline CI (`.github/workflows/ci.yml`) ejecuta `pytest tests/ -v` en cada push y pull request a `main`.

---

## Desarrollo del frontend

```bash
cd frontend

# Instalar dependencias
npm ci

# Servidor de desarrollo (requiere backend en :8000)
npm run dev          # → http://localhost:5173

# Build de producción (output → frontend/dist/)
npm run build

# Preview del build
npm run preview
```

Stack: **React 18** · **TypeScript 5** · **Vite 5** · **Tailwind CSS 3** · **Zustand 5** · **Framer Motion** · **Lucide React** · **xlsx**

---

© 2026 Arnol Ferney Perez & Jesus Andres Cabezas. Todos los derechos reservados.  
Proyecto desarrollado con fines académicos en el marco de la materia Deep Learning.
