# QA Test Case Generator

> Genera suites de casos de prueba a partir de historias de usuario usando LLMs locales, RAG y agentes CrewAI.

**Backend:** FastAPI + Python 3.11 &nbsp;|&nbsp; **LLMs:** Ollama (llama3.2 / mistral) &nbsp;|&nbsp; **Agentes:** CrewAI &nbsp;|&nbsp; **Evaluación:** DeepEval &nbsp;|&nbsp; **Vector DB:** ChromaDB &nbsp;|&nbsp; **Observabilidad:** Opik

---

## Descripcion

QA Test Case Generator es una aplicacion academica de Deep Learning que recibe una historia de usuario y produce automaticamente una suite de casos de prueba estructurada. El sistema combina recuperacion semantica de contexto QA (RAG), generacion con modelos de lenguaje locales y un pipeline de tres agentes especializados que generan, revisan y optimizan los casos antes de entregarlos al usuario.

El proyecto incluye un experimento comparativo que evalua dos configuraciones con cinco metricas personalizadas de DeepEval y registra cada ejecucion en Opik para trazabilidad completa.

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

## Instalacion local (sin Docker)

### Requisitos previos

- Python 3.11+
- [Ollama](https://ollama.com/download) instalado y corriendo

### Paso 1 — Descargar los modelos requeridos

```bash
ollama pull llama3.2
ollama pull mistral
ollama pull nomic-embed-text
```

### Paso 2 — Clonar el repositorio y configurar variables de entorno

```bash
git clone <repo-url>
cd Proyecto_DL_QA
cp .env.example .env
# Editar .env con tu OPIK_API_KEY si deseas observabilidad (opcional)
```

### Paso 3 — Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f #Ejecutar en PowerShell para darle permiso de rutas largas al programa

pip install -r requirements.txt
pip install -r requirements-eval.txt   # Necesario solo para evaluacion DeepEval
```

### Paso 4 — Construir el indice RAG

```bash
python scripts/build_index.py
```

### Paso 5 — Levantar el servidor

```bash
uvicorn backend.main:app --reload --port 8000
```

Abre el navegador en **http://localhost:8000**.

---

## Instalacion con Docker

### Paso 1 — Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tu OPIK_API_KEY (opcional)
```

### Paso 2 — Construir e iniciar los contenedores

```bash
docker compose up --build
```

El `entrypoint.sh` se encarga automaticamente de:

1. Esperar a que Ollama este listo
2. Descargar `llama3.2`, `mistral` y `nomic-embed-text` si no estan presentes
3. Configurar Opik (si `OPIK_API_KEY` esta definida)
4. Construir el indice RAG desde `corpus/` si no existe
5. Iniciar el servidor FastAPI en `:8000`

La primera ejecucion tarda entre 10 y 20 minutos segun la conexion (descarga de modelos). Las siguientes arrancan en segundos gracias a los volumenes persistentes `ollama_data` y `chroma_data`.

La UI queda disponible en **http://localhost:8000**.

### Comandos utiles

```bash
# Ver logs en tiempo real
docker compose logs -f app

# Ejecutar el experimento comparativo
docker compose exec app python scripts/run_experiment.py

# Ejecutar el demo rapido
docker compose exec app python scripts/demo.py

# Reconstruir el indice RAG manualmente
docker compose exec app python scripts/build_index.py

# Apagar (conserva modelos y vector store)
docker compose down

# Apagar y borrar volumenes (reset completo)
docker compose down -v
```

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

## Metricas DeepEval

La evaluacion se ejecuta via el endpoint `/evaluate` o de forma masiva con `run_experiment.py`. Se aplican cinco metricas GEval personalizadas definidas en `evaluator/metrics.py`.

| Metrica | Umbral minimo | Descripcion |
|---|---|---|
| Test Coverage | 0.60 | Los TCs cubren todos los escenarios del requerimiento |
| Test Relevancy | 0.70 | Los TCs son relevantes al requisito dado |
| Test Consistency | 0.65 | Los TCs son internamente consistentes |
| Step Specificity | 0.60 | Los pasos son especificos y accionables |
| Non-Functional Balance | 0.55 | Existe balance entre casos funcionales y no funcionales |

---

## Endpoints API

| Metodo | Ruta | Descripcion |
|---|---|---|
| POST | `/generate` | Generacion directa (sincrona) |
| POST | `/generate/stream` | Generacion con streaming SSE |
| POST | `/generate/agents` | Pipeline completo de 3 agentes CrewAI |
| POST | `/regenerate-tc` | Regenera un caso de prueba individual |
| POST | `/evaluate` | Ejecuta las 5 metricas DeepEval |
| GET | `/rag/status` | Estado del indice ChromaDB |
| GET | `/models` | Modelos disponibles en Ollama |
| GET | `/health` | Health check |
| GET | `/model-status?model=X` | Verifica si el modelo X esta cargado |

### Ejemplo de request

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "user_story": "Como usuario quiero iniciar sesion con email y contrasena para acceder a mi cuenta",
    "model": "llama3.2",
    "use_rag": true
  }'
```

La documentacion interactiva de la API esta disponible en **http://localhost:8000/docs** (Swagger UI).

---

## Experimento comparativo

El script `run_experiment.py` ejecuta 10 historias de usuario con dos configuraciones y evalua cada resultado con las 5 metricas DeepEval.

| | Config A | Config B |
|---|---|---|
| Modelo | llama3.2 | mistral |
| RAG | No | Si |

```bash
# Tiempo estimado: 40-80 minutos
python scripts/run_experiment.py

# Resultados guardados en:
# experiments/results.json
```

---

## Demo rapido

Ejecuta 3 historias de usuario con el pipeline de agentes y evaluacion en una sola llamada:

```bash
python scripts/demo.py
```

---

## Tests

Los tests requieren que el backend este corriendo, o que uses los mocks incluidos en el directorio `tests/`.

```bash
pytest tests/ -v
# 23 tests en total
```

---

## Variables de entorno

Copia `.env.example` a `.env` y ajusta los valores segun tu entorno.

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.2` | Modelo LLM principal |
| `OLLAMA_TEMPERATURE` | `0.25` | Temperatura de generacion |
| `OLLAMA_CONTEXT_SIZE` | `8192` | Tamano de contexto del modelo |
| `OPIK_API_KEY` | — | API key de Opik (observabilidad, opcional) |
| `OPIK_WORKSPACE` | — | Workspace de Opik |
| `OPIK_PROJECT_NAME` | `Qa_trace` | Nombre del proyecto en Opik |
| `ALLOWED_ORIGINS` | `["*"]` | Origenes CORS permitidos |

---

## Autores

**Arnol Ferney Perez** & **Jesus Andres Cabezas**  
Materia: Deep Learning — Ingenieria Mecatronica / Electronica

---

## Copyright

© 2026 Arnol Ferney Perez & Jesus Andres Cabezas. Todos los derechos reservados.  
Proyecto desarrollado con fines academicos en el marco de la materia Deep Learning.
