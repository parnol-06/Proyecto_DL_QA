# Guía de Proyecto — Materia: Deep Learning
## QA Test Case Generator con LLMs Locales, Agentes CrewAI y Evaluación DeepEval

**Programa:** Ingeniería Mecatrónica / Electrónica
**Equipo:** Arnol Ferney Pérez & Jesus Andres Cabezas
**Modalidad:** Equipo de 2 personas
**Plataforma de entrega:** BlackBoard
**Corte 1:** 25 de abril de 2026 (35 %)
**Corte 2:** ~23 de mayo de 2026 (65 %)

---

## 1. Descripción del Proyecto

**QA Test Case Generator** es una aplicación inteligente que recibe una historia de usuario en lenguaje natural y genera, de forma automática, una suite completa de casos de prueba estructurados en JSON. Emplea dos modelos LLM locales servidos por Ollama, un pipeline RAG sobre un corpus de buenas prácticas QA, un sistema de dos agentes CrewAI (Generador + Revisor de Calidad) y métricas de evaluación automática con DeepEval. Todas las ejecuciones quedan registradas en Opik para trazabilidad y análisis comparativo.

**Caso de uso real:** Un QA engineer ingresa la user story "Como usuario quiero iniciar sesión con email y contraseña" y obtiene en segundos 12+ casos de prueba (happy path, negativos, seguridad, rendimiento, usabilidad, compatibilidad), escenarios límite y bugs potenciales, exportables en JSON / CSV / Markdown / XLSX.

---

## 2. Stack Tecnológico Real del Proyecto

| Categoría | Tecnología | Estado |
|---|---|---|
| Ejecución LLMs | **Ollama** (llama3.2 + mistral) | ✅ Implementado |
| Embeddings | **nomic-embed-text** vía Ollama | ✅ Implementado |
| Vector Store | **ChromaDB** (persistente, `chroma_db/`) | ✅ Implementado |
| Agentes IA | **CrewAI** — 2 agentes: Generador + Revisor | ✅ Implementado |
| Observabilidad | **Opik** (trazas en llm_service y agent_service) | ✅ Implementado |
| Evaluación | **DeepEval** — 5 métricas GEval personalizadas | ✅ Implementado |
| Backend | **FastAPI** + Uvicorn + streaming SSE | ✅ Implementado |
| Frontend | SPA vanilla JS (api.js / app.js / render.js) | ✅ Implementado |
| Contenedores | Docker + docker-compose (ollama + app) | ✅ Implementado |
| Experimento | `scripts/run_experiment.py` (10 US × 2 configs) | ✅ Implementado |
| Notebook formal | `experiments/corte2_evaluacion.ipynb` | ❌ **PENDIENTE** |
| 3° agente CrewAI | Agente Optimizador / Sintetizador | ❌ **PENDIENTE** |

---

## 3. Arquitectura Real del Sistema

```
Usuario
  │
  ▼
Frontend SPA (frontend/)
  ├── index.html
  ├── css/styles.css
  └── js/
      ├── api.js        ← fetch calls, SSE reader
      ├── app.js        ← UI logic, streaming, agentes, export, batch
      └── render.js     ← renderizado de cards TC / edge / bugs
  │
  ▼ HTTP / SSE
FastAPI (backend/main.py)
  ├── /generate           → llm_service.generate_test_cases()
  ├── /generate/stream    → llm_service.stream_generate_test_cases() [SSE]
  ├── /generate/agents    → agent_service.run_agent_pipeline() [CrewAI]
  ├── /regenerate-tc      → regenera 1 TC puntual
  ├── /evaluate           → eval_service → evaluator/metrics.py [DeepEval]
  ├── /rag/status         → rag_service.is_index_built()
  ├── /models             → ollama.list()
  └── /health             → liveness probe
  │
  ├── backend/services/
  │   ├── llm_service.py    ← Ollama chat + Opik trace + _parse_llm_output
  │   ├── rag_service.py    ← ChromaDB + nomic-embed-text + semantic_search
  │   ├── agent_service.py  ← CrewAI (Generador + Revisor) + Opik trace
  │   └── eval_service.py   ← DeepEval runner
  │
  ├── evaluator/metrics.py  ← 5 GEval: Coverage, Relevancy, Consistency,
  │                            Specificity, Non-Functional Balance
  │
  ├── corpus/               ← Documentos indexados por RAG
  │   └── qa_best_practices.md
  │
  ├── chroma_db/            ← Vector store persistente (ChromaDB)
  │
  └── scripts/
      ├── build_index.py    ← Indexa corpus/ en ChromaDB
      └── run_experiment.py ← Experimento 10 US × 2 configs → experiments/results.json
  │
  ▼
Ollama (http://localhost:11434)
  ├── llama3.2      ← Config A (sin RAG)
  ├── mistral       ← Config B (con RAG)
  └── nomic-embed-text ← embeddings RAG
```

---

## 4. Estado Actual vs. Requerimientos Académicos

### 4.1 Corte 1 (25 abr 2026) — 35 %

| Requisito | Estado | Evidencia |
|---|---|---|
| ≥ 2 LLMs en Ollama (distinto tamaño/cuantización) | ✅ | llama3.2 + mistral en `config.py` y `run_experiment.py` |
| Embeddings locales + Vector Store | ✅ | `rag_service.py` — nomic-embed-text + ChromaDB |
| Pipeline RAG sobre corpus propio | ✅ | `rag_service.semantic_search()` + `corpus/qa_best_practices.md` |
| ≥ 1 agente IA (ideal 2-3 con roles diferenciados) | ✅ 2 agentes | `agent_service.py` — Generador + Revisor CrewAI |
| Observabilidad Opik | ✅ | Trazas en `llm_service.py` y `agent_service.py` |
| Evaluación DeepEval | ✅ | 5 métricas GEval en `evaluator/metrics.py` |
| Backend Python (FastAPI) | ✅ | `backend/main.py` + routes/ |
| Frontend con UI | ✅ | SPA con streaming, filtros, export, batch mode |
| **BRECHA: 3° agente** | ❌ | La guía pide "ideal 2-3 agentes con roles diferenciados". Falta un 3° agente (Optimizador) |
| **BRECHA: más corpus** | ⚠️ | Solo 1 archivo en `corpus/`. Agregar 3-5 documentos más |

### 4.2 Corte 2 (~23 may 2026) — 65 %

| Requisito | Estado | Evidencia |
|---|---|---|
| Experimento formal (8-15 user stories, 2 configs en Opik) | ✅ script | `run_experiment.py` tiene 10 US × 2 configs, pero falta ejecutarlo y documentarlo |
| Notebook `corte2_evaluacion.ipynb` | ❌ | **No existe** — debe crearse con análisis estadístico |
| DeepEval integrado en experimento | ❌ | `run_experiment.py` no llama a `evaluate_test_cases()` — los scores no se registran |
| Dashboard / visualización de métricas | ⚠️ | Existe en UI pero el notebook debe incluir gráficas Python |

---

## 5. Brechas Técnicas y Roadmap

### Brechas Críticas (bloquean entrega)

1. **Notebook de experimento** (`experiments/corte2_evaluacion.ipynb`) — no existe
2. **DeepEval en run_experiment.py** — el script genera TCs pero no los evalúa con métricas
3. **3° agente CrewAI** — la guía lo pide como "ideal" y suma puntos

### Brechas Menores

4. Corpus RAG con solo 1 documento — enriquecer con 3-5 fuentes adicionales
5. Timing de agentes hardcodeado (65%/35%) en `agent_service.py` — estimación, no medición real
6. JSON repair en `_parse_llm_output` es frágil — agregar validación con pydantic
7. CORS en `main.py` solo permite localhost — agregar `*` o el host Docker en dev

---

## 6. Planificación de Sprints

### Sprint 0 — Base funcional (COMPLETADO)
**Objetivo:** Backend + Frontend operativo con LLM, RAG, agentes y observabilidad.

| Feature | Estado |
|---|---|
| FastAPI + Ollama streaming SSE | ✅ |
| RAG ChromaDB + nomic-embed-text | ✅ |
| 2 agentes CrewAI (Generador + Revisor) | ✅ |
| DeepEval 5 métricas GEval | ✅ |
| Opik trazas llm_service + agent_service | ✅ |
| Frontend SPA completo (batch, export, filtros) | ✅ |
| Docker + docker-compose | ✅ |

---

### Sprint 1 — 3° Agente + Corpus enriquecido
**Fechas:** 18 abr — 21 abr 2026
**Objetivo:** Agregar un 3° agente CrewAI (Optimizador de Cobertura) y enriquecer el corpus RAG.

**Tareas:**

1. **Agente Optimizador** en `agent_service.py`:
   - Rol: "QA Coverage Optimizer"
   - Objetivo: recibe la suite del Generador + el veredicto del Revisor y produce una lista priorizada de los 3 casos de prueba críticos faltantes
   - Tarea: `task_optimize` con `context=[task_generate, task_review]`
   - Output: `{"priority_gaps": [...], "added_cases": [...]}`

2. **Ampliar corpus** (`corpus/`):
   - Agregar: `owasp_testing_guide.md`, `ieee_829_template.md`, `performance_testing_principles.md`
   - Re-ejecutar `python scripts/build_index.py` para re-indexar

3. **Actualizar schema** `AgentGenerateResponse` para incluir `optimizer_output: dict`

**Criterios de aceptación:**
- `POST /generate/agents` retorna `agent_trace` con 3 entradas (Generador, Revisor, Optimizador)
- ChromaDB reporta ≥ 50 chunks después del re-indexado
- UI muestra las 3 trazas en el panel "Agentes"

---

### Sprint 2 — DeepEval en Experimento + Dataset
**Fechas:** 22 abr — 24 abr 2026
**Objetivo:** Integrar evaluación DeepEval en `run_experiment.py` y ejecutar el experimento completo antes del Corte 1.

**Tareas:**

1. **Modificar `run_experiment.py`** — agregar paso de evaluación:
   ```python
   from evaluator.metrics import evaluate_test_cases
   # Después de run_single(), llamar:
   eval_result = evaluate_test_cases(us["story"], resp_dict, cfg["model"])
   result["deepeval_scores"] = eval_result
   ```

2. **Registrar métricas en Opik** desde el experimento:
   - Crear un `opik.Experiment` con nombre `"corte1-config-a"` y `"corte1-config-b"`
   - Loguear `overall_score`, `coverage`, `relevancy` por user story

3. **Ejecutar experimento completo** (2 × 10 = 20 inferencias):
   ```bash
   python scripts/run_experiment.py
   ```
   - Guardar `experiments/results.json` con scores DeepEval incluidos

**Criterios de aceptación:**
- `experiments/results.json` contiene campo `deepeval_scores` en cada entrada
- En Opik dashboard se ven 2 experimentos con 10 trazas cada uno
- `avg_overall_score` por config está calculado en el summary

---

### Sprint 3 — Notebook de Análisis Formal (Corte 2)
**Fechas:** 25 abr — 10 may 2026
**Objetivo:** Crear `experiments/corte2_evaluacion.ipynb` con análisis estadístico y visualizaciones.

**Tareas:**

1. **Estructura del notebook** (mínimo 6 secciones):
   - Sección 1: Introducción y configuración experimental
   - Sección 2: Carga de `experiments/results.json`
   - Sección 3: Estadísticos descriptivos por configuración (media, std, min/max)
   - Sección 4: Gráficas de comparación (barplot matplotlib o seaborn)
     - Overall score: Config A vs Config B
     - Score por métrica DeepEval (heatmap)
     - Tiempo de generación por modelo
   - Sección 5: Análisis cuantitativo — ¿RAG mejora la cobertura?
   - Sección 6: Conclusiones y limitaciones

2. **Métricas a reportar** (mínimo):
   - `avg_coverage`, `avg_relevancy`, `avg_consistency`, `avg_specificity`, `avg_nfb`
   - `avg_tc_count`, `avg_elapsed_s`
   - `delta_overall = Config_B.overall - Config_A.overall`

3. **Tests estadísticos** (para rigor académico):
   - t-test o Wilcoxon entre overall scores de Config A vs B

**Criterios de aceptación:**
- Notebook ejecuta Run All sin errores
- ≥ 4 gráficas incluidas
- Conclusión explica si RAG mejora o no mejora las métricas y por qué

---

### Sprint 4 — Refactor y calidad de código (Corte 2)
**Fechas:** 10 may — 18 may 2026
**Objetivo:** Limpiar deuda técnica antes de la entrega final.

**Tareas:**

1. **Robustecer JSON parsing** en `llm_service._parse_llm_output`:
   - Usar `json_repair` library o strategy de reintentos con prompt distinto
   - Agregar validación pydantic del dict antes de `_build_response()`

2. **CORS fix** en `backend/main.py`:
   - Agregar `allow_origins=["*"]` en modo dev o leer `ALLOWED_ORIGINS` desde `.env`

3. **Timing real de agentes** en `agent_service.py`:
   - Medir `t_generate` y `t_review` individualmente con `time.monotonic()` entre tareas

4. **Ampliar tests** en `tests/`:
   - Agregar `test_rag_service.py` — prueba `build_index` con corpus mock
   - Agregar `test_agent_service.py` — prueba fallback cuando CrewAI falla

**Criterios de aceptación:**
- `pytest` pasa con ≥ 8 tests
- `_parse_llm_output` maneja mal-JSON del modelo sin lanzar excepción al usuario
- Timing por agente reportado correctamente en `agent_trace`

---

### Sprint 5 — Entrega y presentación (Corte 2)
**Fechas:** 18 may — 23 may 2026
**Objetivo:** Documentación final, demostración funcional y limpieza del repo.

**Tareas:**

1. **README.md final** con:
   - Diagrama de arquitectura
   - Instrucciones de instalación local (venv + Ollama)
   - Instrucciones Docker (`docker compose up`)
   - Descripción de endpoints API

2. **Demo script** — `scripts/demo.py`:
   - Ejecuta 3 user stories seleccionadas, genera TCs con agentes + RAG, evalúa y muestra scores

3. **Limpieza repo**:
   - Eliminar `__pycache__` del repositorio (agregar a `.gitignore`)
   - Eliminar `.venv` del repositorio (ya en `.gitignore`)

**Criterios de aceptación:**
- `docker compose up` levanta todo y la UI es accesible en `http://localhost:8000`
- Demo script corre sin errores con ambos modelos
- Repo limpio: sin `__pycache__`, sin `.venv`

---

## 7. Despliegue con Docker

### Arquitectura de Contenedores

```
docker-compose.yml
  ┌─────────────────┐   ┌──────────────────┐
  │   ollama         │   │   app (FastAPI)  │
  │  :11434          │◄──│  :8000           │
  │  llama3.2        │   │  llm_service     │
  │  mistral         │   │  rag_service     │
  │  nomic-embed-text│   │  agent_service   │
  │  [ollama_data]   │   │  [chroma_data]   │
  └─────────────────┘   └──────────────────┘
```

### Cómo Levantar

```bash
# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env con OPIK_API_KEY, OPIK_WORKSPACE, etc.

# 2. Construir y levantar
docker compose up --build

# 3. El entrypoint.sh automáticamente:
#    - Espera a que Ollama esté listo (healthcheck)
#    - Descarga llama3.2 si no está
#    - Descarga nomic-embed-text si no está
#    - Configura Opik (non-interactive, force=True)
#    - Inicia uvicorn en :8000

# 4. Acceder a la UI
# http://localhost:8000
```

### Construir el Índice RAG (primera vez)

```bash
# En local con venv activo:
python scripts/build_index.py

# Verificar:
curl http://localhost:8000/rag/status
# {"built": true, "chunk_count": XX}
```

### Variables de Entorno (`.env`)

```env
OLLAMA_MODEL=llama3.2
OLLAMA_TEMPERATURE=0.25
OLLAMA_CONTEXT_SIZE=8192
APP_PORT=8000
OPIK_API_KEY=tu_api_key_aqui
OPIK_WORKSPACE=tu_workspace
OPIK_PROJECT_NAME=Qa_trace
```

### Problemas Comunes

| Problema | Causa | Solución |
|---|---|---|
| `ConnectionRefusedError` al iniciar | Ollama no listo | Esperar healthcheck; ver logs `ollama` |
| `model 'llama3.2' not found` | Modelo no descargado | entrypoint.sh lo descarga automáticamente |
| RAG retorna vacío | Índice no construido | Ejecutar `python scripts/build_index.py` |
| ChromaDB error en Docker | Permisos de volumen | `docker compose down -v && docker compose up --build` |
| Opik no registra trazas | API key faltante | Verificar `OPIK_API_KEY` en `.env` |

---

## 8. Criterios de Evaluación Académica

### Corte 1 (35 %)

| Criterio | Peso | Estado |
|---|---|---|
| 2 LLMs locales en Ollama funcionando | 20 % | ✅ llama3.2 + mistral |
| Pipeline RAG operativo con búsqueda semántica | 20 % | ✅ ChromaDB + nomic-embed-text |
| ≥ 2 agentes IA con roles diferenciados | 20 % | ✅ Generador + Revisor |
| Observabilidad Opik (trazas visibles) | 15 % | ✅ |
| DeepEval ejecutando métricas | 15 % | ✅ 5 métricas GEval |
| Interfaz funcional | 10 % | ✅ SPA completa |

### Corte 2 (65 %)

| Criterio | Peso | Estado |
|---|---|---|
| 3° agente CrewAI (Optimizador) | 15 % | ❌ Pendiente Sprint 1 |
| Experimento formal (10 US × 2 configs) ejecutado | 20 % | ⚠️ Script listo, falta ejecutar |
| DeepEval integrado en experimento | 15 % | ❌ Pendiente Sprint 2 |
| Notebook análisis estadístico | 25 % | ❌ Pendiente Sprint 3 |
| Refactor + tests | 15 % | ⚠️ Parcial |
| Documentación y demo | 10 % | ⚠️ Pendiente Sprint 5 |

---

## 9. Guía Rápida de Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/generate` | Generación sync (sin streaming) |
| `POST` | `/generate/stream` | Generación con streaming SSE |
| `POST` | `/generate/agents` | Pipeline CrewAI (Generador + Revisor) |
| `POST` | `/regenerate-tc` | Regenera un único test case por ID |
| `POST` | `/evaluate` | Evalúa TCs con 5 métricas DeepEval |
| `GET` | `/rag/status` | Estado del índice ChromaDB |
| `GET` | `/models` | Modelos disponibles en Ollama |
| `GET` | `/health` | Health check + estado Ollama |
| `GET` | `/model-status?model=X` | Si el modelo X está cargado en memoria |
