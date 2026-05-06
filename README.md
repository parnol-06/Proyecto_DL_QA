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
  |   Frontend   |  SPA Vanilla JS — SSE streaming, export, batch mode
  |              |  WorkflowBar · AgentPipeline · MetricCards · filtros
  +--------------+
         |  HTTP / SSE
         v
  +--------------+     +-------------------+
  |   FastAPI    |---->|  RAG Service      |
  |   Backend    |     |  ChromaDB +       |
  |   (Uvicorn)  |     |  nomic-embed-text |
  +--------------+     +-------------------+
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
  |     Opik     |  Trazas + experimentos (opcional)
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

---

## Estructura del proyecto

```
Proyecto_DL_QA/
├── backend/
│   ├── main.py              # FastAPI app + CORS + archivos estáticos
│   ├── config.py            # Variables de entorno centralizadas
│   ├── routes/
│   │   ├── generate.py      # /generate, /generate/stream, /generate/agents, /generate/agents/stream
│   │   └── evaluate.py      # /evaluate
│   ├── services/
│   │   ├── llm_service.py   # Ollama + Opik + streaming + reparación JSON + budget de tokens
│   │   ├── rag_service.py   # ChromaDB + nomic-embed-text + chunking semántico (500 chars, 50 overlap)
│   │   ├── agent_service.py # CrewAI 3 agentes + Opik + timing real + fallback directo LLM
│   │   └── eval_service.py  # Wrapper DeepEval + streaming por métrica
│   └── schemas/models.py    # Esquemas Pydantic
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
│   ├── conftest.py          # Fixture AsyncClient para tests de integración
│   ├── test_generate.py     # Validación input, reparación JSON, generación
│   ├── test_health.py       # Health check
│   ├── test_models.py       # /models con y sin Ollama disponible
│   ├── test_rag_service.py  # Chunking, búsqueda semántica, construcción de índice
│   ├── test_agent_service.py# Parseo reviewer/optimizer, pipeline CrewAI, fallback
│   └── test_stream.py       # SSE /generate/stream y /generate/agents/stream
├── experiments/             # Resultados del experimento comparativo (JSON)
├── chroma_db/               # Vector store ChromaDB (generado en ejecución)
├── Dockerfile               # Multi-stage build, usuario no-root (appuser:1001)
├── docker-compose.yml
├── entrypoint.sh            # Espera Ollama → descarga modelos → construye RAG → uvicorn
├── requirements.txt         # Dependencias core
├── requirements-eval.txt    # DeepEval (instalación separada, requiere Python ≤ 3.12)
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
| `OLLAMA_TEMPERATURE` | Temperatura del LLM (baja para consistencia) | `0.25` |
| `OLLAMA_CONTEXT_SIZE` | Ventana de contexto en tokens | `8192` |
| `OLLAMA_HOST` | Solo necesario en Docker | `http://ollama:11434` |
| `OPIK_API_KEY` | Trazabilidad Opik (opcional) | — |
| `OPIK_WORKSPACE` | Workspace Opik | — |
| `OPIK_PROJECT_NAME` | Proyecto Opik | — |
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
|  Genera >= 12 TCs   |
|  en JSON cubriendo  |
|  7 categorías       |
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

Si CrewAI falla, el servicio hace fallback automático a generación directa con LLM. Cada ejecución queda registrada en Opik con trazas individuales por agente y tiempos reales de procesamiento.

---

## Métricas de evaluación (DeepEval)

Las 5 métricas GEval personalizadas evalúan distintas dimensiones de la suite generada:

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
