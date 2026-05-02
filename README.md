# QA Test Case Generator

> Genera suites de casos de prueba a partir de historias de usuario usando LLMs locales, RAG y agentes CrewAI.

**Backend:** FastAPI + Python 3.11 &nbsp;|&nbsp; **LLMs:** Ollama &nbsp;|&nbsp; **Agentes:** CrewAI &nbsp;|&nbsp; **Evaluación:** DeepEval &nbsp;|&nbsp; **Vector DB:** ChromaDB

---

## Arquitectura

```
Historia de usuario (UI / API)
         |
         v
  +--------------+
  |   Frontend   |  SPA Vanilla JS — SSE streaming, export, batch mode
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
| llama3.2  |    | 3 agentes      |
| mistral   |    | + Opik traces  |
+-----------+    +----------------+
         |
         v
  +--------------+
  | Eval Service |
  | DeepEval     |
  | 5 metricas   |
  | GEval        |
  +--------------+
         |
         v
  +--------------+
  |     Opik     |  Trazas + experimentos
  +--------------+
```

---

## Inicio rápido

**Único comando que necesitas:**
```bash
docker compose up --build
```

Esto se encarga automáticamente de todo:
- Construye la imagen correctamente
- Espera que Ollama esté disponible
- Descarga los modelos necesarios
- Construye el índice RAG desde el corpus
- Inicia el servidor FastAPI

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

# Reset completo (borra volúmenes)
docker compose down -v
```

---

## Funcionalidades

✅ Generación de casos de prueba con streaming en tiempo real
✅ Pipeline de 3 agentes especializados (Generador → Revisor → Optimizador)
✅ RAG con corpus de buenas prácticas QA, OWASP, IEEE 829
✅ Evaluación automática con 5 métricas personalizadas DeepEval
✅ Exportación a JSON, CSV, Markdown y Excel
✅ Modo batch para múltiples historias de usuario
✅ Filtrado por categoría y prioridad
✅ Regeneración individual de casos de prueba

---

## Estructura del proyecto

```
Proyecto_DL_QA/
├── backend/
│   ├── main.py              # FastAPI app + CORS + archivos estaticos
│   ├── config.py            # Variables de entorno centralizadas
│   ├── routes/
│   │   ├── generate.py      # /generate, /generate/stream, /generate/agents
│   │   └── evaluate.py      # /evaluate
│   ├── services/
│   │   ├── llm_service.py   # Ollama + Opik + streaming + reparacion JSON
│   │   ├── rag_service.py   # ChromaDB + nomic-embed-text + busqueda semantica
│   │   ├── agent_service.py # CrewAI 3 agentes + Opik + timing real
│   │   └── eval_service.py  # Wrapper DeepEval
│   └── schemas/models.py    # Esquemas Pydantic
├── evaluator/
│   └── metrics.py           # 5 metricas GEval personalizadas
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js           # fetch + lector SSE
│       ├── app.js           # logica UI, streaming, agentes, export, batch
│       └── render.js        # Renderizado de cards TC / edge / bugs
├── corpus/                  # Corpus RAG
│   ├── qa_best_practices.md
│   ├── owasp_testing_guide.md
│   ├── performance_testing_principles.md
│   └── ieee_829_test_case_template.md
├── scripts/
│   ├── build_index.py       # Indexa corpus/ en ChromaDB
│   ├── run_experiment.py    # Experimento 10 US x 2 configs -> results.json
│   └── demo.py              # Demo: 3 US con agentes + evaluacion
├── tests/
│   ├── test_generate.py
│   ├── test_health.py
│   ├── test_models.py
│   ├── test_rag_service.py
│   └── test_agent_service.py
├── experiments/             # Resultados del experimento comparativo
├── chroma_db/               # Vector store ChromaDB (generado en ejecucion)
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── requirements.txt
├── requirements-eval.txt    # DeepEval (instalacion separada)
└── .env.example
```

---

## Variables de entorno

Copia `.env.example` a `.env` si necesitas configurar:
- `OPIK_API_KEY` para trazabilidad de ejecuciones (opcional)
- Modelo LLM por defecto
- Temperatura de generación
- Orígenes CORS permitidos

---

## Endpoints API

Documentación interactiva Swagger: **http://localhost:8000/docs**

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/generate/stream` | Generación con streaming SSE |
| POST | `/generate/agents` | Pipeline completo de 3 agentes |
| POST | `/evaluate` | Evaluación DeepEval |
| GET  | `/rag/status` | Estado del índice RAG |
| GET  | `/health` | Health check |

---

## Pipeline de 3 agentes CrewAI

Cuando usas el endpoint `/generate/agents`, la historia de usuario pasa por tres agentes especializados en secuencia:

```
Historia de usuario
       |
       v
+---------------------+
|  Agente 1           |
|  Generador          |
|  Genera >= 12 TCs   |
|  en JSON cubriendo  |
|  7 categorias       |
+---------------------+
       |
       v
+---------------------+
|  Agente 2           |
|  Revisor            |
|  Evalua cobertura,  |
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
|  criticos faltantes |
|  y los especifica   |
|  completamente      |
+---------------------+
       |
       v
  Suite final consolidada
```

Cada ejecucion del pipeline queda registrada en Opik con trazas individuales por agente y tiempos reales de procesamiento.

---



© 2026 Arnol Ferney Perez & Jesus Andres Cabezas. Todos los derechos reservados.  
Proyecto desarrollado con fines academicos en el marco de la materia Deep Learning.