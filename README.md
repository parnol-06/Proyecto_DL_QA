# QA Test Case Generator

> Genera suites de casos de prueba a partir de historias de usuario usando LLMs locales, RAG y agentes CrewAI.

**Backend:** FastAPI + Python 3.11 &nbsp;|&nbsp; **LLMs:** Ollama &nbsp;|&nbsp; **Agentes:** CrewAI &nbsp;|&nbsp; **Evaluación:** DeepEval &nbsp;|&nbsp; **Vector DB:** ChromaDB &nbsp;|&nbsp; **Observabilidad:** Opik

---

## Arquitectura

```
Historia de usuario (UI / API)
         |
         v
  +--------------+
  |   Frontend   |  SPA React + Vite — SSE streaming, export, batch mode
  |              |  WorkflowBar · AgentPipeline · MetricCards · filtros
  +--------------+
         |  HTTP / SSE
         v
  +--------------------+     +-------------------+
  |   FastAPI          |---->|  RAG Service      |
  |   Backend          |     |  ChromaDB +       |
  |   (Uvicorn)        |     |  nomic-embed-text |
  |                    |     +-------------------+
  |  ObservabilityMW   |
  |  (request_id)      |
  +--------------------+
         |
    +---------+----------+
    |                    |
    v                    v
+-----------+    +----------------+
| LLM Svc   |    | Agent Service  |
| Ollama    |    | CrewAI         |
| semáforo  |    | 3 agentes      |
| concurr.  |    | streaming      |
+-----------+    +----------------+
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
  |    Opik      |  Trazas distribuidas · feedback scores · correlación
  |              |  Generate → Evaluate · TTFT · spans CrewAI
  +--------------+
```

---

## Inicio rápido

**Requisito previo:** tener [Ollama](https://ollama.com) instalado y corriendo en el host.

**Único comando:**
```bash
docker compose up --build
```

Esto se encarga automáticamente de:
- Construir la imagen (multi-stage, usuario no-root)
- Esperar que Ollama esté disponible (hasta 120 s)
- Descargar el modelo de embedding `nomic-embed-text`
- Construir el índice RAG desde el corpus
- Iniciar el servidor FastAPI en el puerto 8000

Abre en el navegador: **http://localhost:8000**

> La primera ejecución tarda mientras descarga los modelos. Las siguientes arrancan en segundos.

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
- Pipeline de 3 agentes especializados (Generador → Revisor → Optimizador)
- RAG con corpus de buenas prácticas QA, OWASP, IEEE 829 y performance testing
- Evaluación automática con 5 métricas personalizadas DeepEval (GEval)
- Exportación a JSON, CSV, Markdown y Excel (XLSX)
- Modo batch para múltiples historias de usuario (separadas por `---`)
- 8 plantillas predefinidas para pruebas rápidas
- Filtrado en vivo por ID, categoría y prioridad
- Regeneración individual de casos de prueba
- Descarga de modelos Ollama desde la UI (`/pull-model`)
- Persistencia de estado en `localStorage` (último resultado, modo agente, métricas)
- Semáforo de concurrencia para evitar sobrecarga del LLM
- **Observabilidad distribuida** con Opik: trazas completas, correlación Generate→Evaluate, TTFT

---

## Estructura del proyecto

```
Proyecto_DL_QA/
├── backend/
│   ├── main.py              # FastAPI app + ObservabilityMiddleware + CORS
│   ├── config.py            # Variables de entorno centralizadas
│   ├── observability/       # Módulo de trazabilidad distribuida (Opik)
│   │   ├── opik_manager.py  # Core: root_trace(), child_span(), spans especializados
│   │   ├── tracer.py        # Shim público (re-exporta toda la API)
│   │   ├── middleware.py    # ObservabilityMiddleware: X-Request-ID por request
│   │   ├── decorators.py    # @trace_pipeline, @trace_agent, @trace_llm, @trace_rag, @trace_eval
│   │   └── __init__.py
│   ├── routes/
│   │   ├── generate.py      # /generate, /generate/stream, /generate/agents, /generate/agents/stream
│   │   └── evaluate.py      # /evaluate, /evaluate/stream
│   ├── services/
│   │   ├── llm_service.py   # Ollama + streaming + TTFT + reparación JSON + spans LLM
│   │   ├── rag_service.py   # ChromaDB + nomic-embed-text + embed_span + chromadb_query_span
│   │   ├── agent_service.py # CrewAI 3 agentes + llm_inference_span por agente + fallback
│   │   └── eval_service.py  # DeepEval + deepeval_span + metric_span por métrica
│   └── schemas/models.py    # Esquemas Pydantic (incluye *_trace_id para correlación)
├── evaluator/
│   └── metrics.py           # 5 métricas GEval personalizadas
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js           # fetch + lector SSE (ReadSSE)
│       ├── app.js           # lógica UI, WorkflowBar, StreamMonitor, AgentPipeline, batch, export
│       └── render.js        # Renderizado de cards TC / edge / bugs
├── corpus/                  # Base de conocimiento RAG
│   ├── qa_best_practices.md
│   ├── owasp_testing_guide.md
│   ├── performance_testing_principles.md
│   └── ieee_829_test_case_template.md
├── scripts/
│   ├── build_index.py       # Indexa corpus/ en ChromaDB
│   ├── run_experiment.py    # Experimento 10 US × 2 configs → experiments/results.json
│   └── demo.py              # Demo: 3 US con agentes + evaluación + comparativa de modelos
├── tests/
│   ├── conftest.py
│   ├── test_generate.py
│   ├── test_health.py
│   ├── test_models.py
│   ├── test_rag_service.py
│   ├── test_agent_service.py
│   └── test_stream.py
├── experiments/             # Resultados del experimento comparativo (JSON)
├── chroma_db/               # Vector store ChromaDB (generado en ejecución)
├── Dockerfile               # Multi-stage build, usuario no-root (appuser:1001)
├── docker-compose.yml
├── entrypoint.sh            # Espera Ollama → descarga modelos → construye RAG → uvicorn
├── requirements.txt         # Dependencias core
├── requirements-eval.txt    # DeepEval (requiere Python ≤ 3.12)
├── requirements-dev.txt     # Dependencias de desarrollo
└── .env.example
```

---

## Variables de entorno

Copia `.env.example` a `.env` para configurar:

| Variable | Descripción | Default |
|---|---|---|
| `OLLAMA_MODEL` | Modelo LLM para generación | — |
| `OLLAMA_EVAL_MODEL` | Modelo LLM para evaluación (distinto para evitar auto-evaluación) | — |
| `OLLAMA_EMBED_MODEL` | Modelo de embedding (se descarga automáticamente) | `nomic-embed-text` |
| `OLLAMA_TEMPERATURE` | Temperatura del LLM | `0.25` |
| `OLLAMA_CONTEXT_SIZE` | Ventana de contexto en tokens | `8192` |
| `OLLAMA_HOST` | Solo necesario en Docker | `http://ollama:11434` |
| `OPIK_API_KEY` | API key de Opik (opcional — desactiva trazas si no se define) | — |
| `OPIK_WORKSPACE` | Workspace de Opik | — |
| `OPIK_PROJECT_NAME` | Nombre del proyecto en Opik | `Qa_trace` |
| `ALLOWED_ORIGINS` | Orígenes CORS permitidos | `["*"]` |

---

## Endpoints API

Documentación interactiva Swagger: **http://localhost:8000/docs**

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/generate` | Generación directa con LLM |
| POST | `/generate/stream` | Generación con streaming SSE |
| POST | `/generate/agents` | Pipeline completo de 3 agentes |
| POST | `/generate/agents/stream` | Pipeline de agentes con streaming SSE |
| POST | `/evaluate` | Evaluación DeepEval (5 métricas) |
| POST | `/evaluate/stream` | Evaluación con streaming SSE por métrica |
| POST | `/regenerate-tc` | Regenera un caso de prueba individual |
| POST | `/pull-model` | Descarga un modelo Ollama desde la UI |
| GET  | `/models` | Lista modelos Ollama disponibles |
| GET  | `/rag/status` | Estado del índice RAG |
| GET  | `/health` | Health check |

---

## Pipeline de 3 agentes CrewAI

Cuando usas `/generate/agents` o `/generate/agents/stream`, la historia pasa por tres agentes en secuencia:

```
Historia de usuario
       |
       v
+---------------------+
|  Agente 1           |
|  Generador          |
|  Genera TCs en JSON |
|  cubriendo 7 cats.  |
+---------------------+
       |
       v
+---------------------+
|  Agente 2           |
|  Revisor            |
|  Evalúa cobertura,  |
|  calidad y gaps.    |
|  Veredicto:         |
|  APROBADO /         |
|  OBSERVACIONES /    |
|  RECHAZADO          |
+---------------------+
       |
       v
+---------------------+
|  Agente 3           |
|  Optimizador        |
|  Identifica 3 casos |
|  críticos faltantes |
|  y los especifica   |
|  completamente      |
+---------------------+
       |
       v
  Suite final consolidada
```

Si CrewAI falla, el servicio hace fallback automático a generación directa con LLM. Cada ejecución queda trazada en Opik con spans individuales por agente y tiempos reales de LLM.

---

## Observabilidad (Opik)

El módulo `backend/observability/` implementa trazabilidad distribuida de nivel enterprise sobre [Opik](https://www.comet.com/site/products/opik/).

### Jerarquía de spans por endpoint

```
generate_agents_stream_request  (root trace)
├── request_validation
├── rag_pipeline                (si use_rag=true)
│   ├── embedding_generation
│   └── chromadb_query
├── response_stream
│   └── crew_pipeline
│       ├── agent_1_generador
│       │   ├── llm_call_generador
│       │   └── llm_json_parse
│       ├── agent_2_revisor
│       │   └── llm_call_revisor
│       └── agent_3_optimizador
│           └── llm_call_optimizador
└── response_serialization

evaluate_request  (root trace)
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

Cada respuesta de `/generate*` incluye `generation_trace_id`. Al pasarlo en `EvaluateRequest.source_generation_trace_id`, la traza de evaluación queda vinculada a la de generación en el dashboard de Opik.

```json
// 1. Generar
POST /generate/agents
→ { "generation_trace_id": "abc123..." }

// 2. Evaluar con correlación
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

Si `OPIK_API_KEY` no está definida, las trazas se desactivan silenciosamente sin afectar el funcionamiento.

---

## Métricas de evaluación (DeepEval)

| Métrica | Descripción |
|---|---|
| **Coverage** | Cobertura de caminos: happy path, negativos, edge cases y no-funcionales |
| **Relevancy** | Los casos son pertinentes a la historia de usuario evaluada |
| **Consistency** | Coherencia interna: lógica, precondiciones y nomenclatura consistente |
| **Specificity** | Datos de prueba concretos (no genéricos como "usuario cualquiera") |
| **Non-Functional Balance** | Proporción de casos no-funcionales entre 25% y 30% de la suite |

La evaluación usa un modelo LLM distinto al de generación para evitar sesgo de auto-evaluación.

---

## Corpus RAG

| Archivo | Contenido |
|---|---|
| `qa_best_practices.md` | Principios QA, técnicas de diseño (partición equivalencia, valores límite, tablas de decisión) |
| `owasp_testing_guide.md` | OWASP Testing Guide v4.2 adaptado: autenticación, autorización, sesiones, validación de entrada |
| `performance_testing_principles.md` | Load, stress, endurance, spike y soak testing con métricas y umbrales |
| `ieee_829_test_case_template.md` | Estándar IEEE 829-2008: estructura, campos obligatorios y formato de IDs |

---

## Scripts

```bash
# Construir índice RAG manualmente
python scripts/build_index.py

# Ejecutar demo completo (3 historias, agentes + evaluación)
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
pytest tests/

# Con cobertura
pytest tests/ --cov=backend
```

Los tests cubren: health check, modelos, generación (validación + reparación JSON), RAG (chunking + búsqueda semántica), agentes (parseo + pipeline + fallback) y streaming SSE.

---

© 2026 Arnol Ferney Perez & Jesus Andres Cabezas. Todos los derechos reservados.  
Proyecto desarrollado con fines académicos en el marco de la materia Deep Learning.
