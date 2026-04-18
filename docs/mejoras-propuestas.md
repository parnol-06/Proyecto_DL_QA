# Propuestas de Mejora — Proyecto_DL_QA

Planificación de mejoras organizadas en sprints de ~1 semana cada uno, ordenados de menor a mayor complejidad. Cada sprint es independiente y entregable por sí solo.

---

## Resumen de sprints

| Sprint | Nombre | Enfoque | Esfuerzo estimado |
|--------|--------|---------|-------------------|
| Sprint 1 | Fundamentos | Higiene del proyecto | 2–3 horas |
| Sprint 2 | Robustez | Validación, seguridad y logging | 4–6 horas |
| Sprint 3 | UX rápida | Mejoras de frontend sin tocar backend | 4–5 horas |
| Sprint 4 | Arquitectura | Refactorización y tests | 6–8 horas |
| Sprint 5 | Funcionalidad avanzada | Evaluador real + SSE | 8–12 horas |
| Sprint 6 | DevOps | Docker y CI/CD | 4–6 horas |

---

## Sprint 1 — Fundamentos
> **Meta**: Dejar el repositorio en estado profesional básico. Sin tocar lógica de negocio.

### S1-1 · Crear `.gitignore`
**Situación actual**: No existe; `venv/`, `__pycache__/` y `.env` pueden subirse accidentalmente.  
**Acción**: Crear `.gitignore` estándar para Python.

```gitignore
venv/
__pycache__/
*.pyc
.env
.DS_Store
```

**Criterio de aceptación**: `git status` no muestra archivos de entorno ni caché.

---

### S1-2 · Variables de entorno con `.env`
**Situación actual**: Puerto (`8000`), modelo (`llama3:8b`), temperatura (`0.25`) y contexto (`8192`) hardcodeados en `main.py` líneas ~15-20.  
**Acción**: Instalar `python-dotenv`, crear `.env` y leer desde `main.py`.

```env
OLLAMA_MODEL=llama3.2
OLLAMA_TEMPERATURE=0.25
OLLAMA_CONTEXT_SIZE=8192
APP_PORT=8000
```

**Archivos afectados**: `backend/main.py`, nuevo `.env`, nuevo `.env.example`  
**Criterio de aceptación**: Cambiar el modelo en `.env` sin modificar código produce resultados con el modelo correcto.

---

## Sprint 2 — Robustez
> **Meta**: Que la aplicación falle de forma predecible y controlada.

### S2-1 · Validación de input en Pydantic
**Situación actual**: `requirement` acepta strings vacíos o de miles de caracteres sin error.  
**Acción**: Agregar restricciones en el esquema de `GenerateRequest` en `main.py`.

```python
requirement: str = Field(..., min_length=20, max_length=3000,
                         description="Historia de usuario o requisito a testear")
context: str | None = Field(None, max_length=1000)
```

**Criterio de aceptación**: Request con `requirement=""` devuelve `422 Unprocessable Entity` con mensaje claro.

---

### S2-2 · Restringir CORS
**Situación actual**: `allow_origins=["*"]` — innecesario para uso local.  
**Acción**: Cambiar en `main.py` a orígenes locales explícitos.

```python
allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"]
```

**Criterio de aceptación**: Petición desde un origen externo recibe error CORS; desde `localhost:8000` funciona normal.

---

### S2-3 · Logging estructurado
**Situación actual**: Errores del LLM y del parseo JSON se capturan con `try/except` sin registro.  
**Acción**: Añadir `logging` estándar de Python en `backend/main.py`.

```python
import logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)
```

Registrar: tiempo de respuesta del LLM, modelo usado, errores de parseo JSON con fragmento fallido.

**Criterio de aceptación**: Al generar casos de prueba aparece en consola el modelo y tiempo de respuesta; al forzar un JSON inválido se ve el fragmento que falló.

---

### S2-4 · Rate limiting básico
**Situación actual**: Múltiples requests concurrentes pueden saturar Ollama.  
**Acción**: Usar un semáforo asyncio en `main.py` para serializar llamadas al LLM (sin dependencias extra).

```python
import asyncio
_llm_semaphore = asyncio.Semaphore(1)

async def generate(...):
    async with _llm_semaphore:
        # llamada a Ollama
```

**Criterio de aceptación**: Dos requests simultáneos al `/generate` no producen errores; el segundo espera a que termine el primero.

---

## Sprint 3 — UX rápida
> **Meta**: Mejoras visibles para el usuario final que no requieren cambios en el backend.

### S3-1 · Persistencia con `localStorage`
**Situación actual**: Los resultados desaparecen al recargar la página.  
**Acción**: En `frontend/index.html`, guardar el resultado en `localStorage` al recibirlo y restaurarlo al cargar.

```js
// Al recibir resultado
localStorage.setItem('lastResult', JSON.stringify(data));

// Al cargar la página
const saved = localStorage.getItem('lastResult');
if (saved) renderResult(JSON.parse(saved));
```

**Criterio de aceptación**: Recargar la página muestra el último resultado generado.

---

### S3-2 · Exportación de resultados
**Situación actual**: No hay forma de sacar los casos generados del navegador.  
**Acción**: Añadir botones en la UI (cero cambios en backend):

1. **Copiar JSON** — `navigator.clipboard.writeText(JSON.stringify(data, null, 2))`
2. **Descargar `.json`** — `Blob` + `URL.createObjectURL`
3. **Descargar `.csv`** — transformar casos a filas CSV en JS antes de exportar

**Criterio de aceptación**: Los tres botones funcionan; el CSV abre correctamente en Excel/LibreOffice con columnas: ID, Categoría, Título, Pasos, Resultado esperado, Prioridad.

---

### S3-3 · Feedback visual durante la generación
**Situación actual**: El botón "Generar" se deshabilita y no hay indicación de progreso.  
**Acción**: Añadir etapas de progreso animadas en JS con mensajes fijos por tiempo:

```
0s  → "Conectando con el modelo..."
3s  → "Analizando el requisito..."
8s  → "Generando casos de prueba..."
20s → "Validando estructura del output..."
```

**Criterio de aceptación**: El usuario ve texto de progreso cambiante durante la espera, sin cambios en backend.

---

## Sprint 4 — Arquitectura
> **Meta**: Hacer el código mantenible a largo plazo. No añade funcionalidad nueva, solo reorganiza.

### S4-1 · Separar frontend en archivos estáticos
**Situación actual**: `frontend/index.html` tiene 774 líneas mezclando HTML, CSS y JS.  
**Acción**: Separar en módulos, FastAPI ya soporta `StaticFiles`.

```
frontend/
├── index.html
├── css/
│   └── styles.css
└── js/
    ├── api.js       # fetch al backend
    ├── render.js    # renderizado de tarjetas, tabs, badges
    └── app.js       # inicialización, eventos, localStorage
```

**Criterio de aceptación**: La UI funciona idéntico; `index.html` queda en <50 líneas.

---

### S4-2 · Refactorizar `backend/main.py`
**Situación actual**: 188 líneas mezclan configuración, rutas, servicios y parseo.  
**Acción**: Separar en capas.

```
backend/
├── main.py              # App FastAPI, registro de rutas, CORS, static files
├── routes/
│   └── generate.py      # POST /generate, GET /models, GET /health
├── services/
│   └── llm_service.py   # Construcción del prompt, llamada Ollama, parseo/reparación JSON
└── schemas/
    └── models.py         # GenerateRequest, TestCase, GenerateResponse (Pydantic)
```

**Criterio de aceptación**: Todos los endpoints funcionan igual; `services/llm_service.py` es testeable en aislamiento.

---

### S4-3 · Suite de tests con pytest
**Situación actual**: No existe ningún test automatizado.  
**Dependencia**: Requiere S4-2 (refactorización) para que los servicios sean testeables en aislamiento.  
**Acción**: Crear `tests/` con pytest + httpx.

```
tests/
├── test_health.py        # GET /health → 200
├── test_models.py        # GET /models con Ollama disponible/no disponible
└── test_generate.py      # POST /generate: input válido, vacío, muy largo, JSON roto del LLM
```

Instalar: `pip install pytest httpx pytest-asyncio`

**Criterio de aceptación**: `pytest tests/` pasa en verde; el caso de JSON roto del LLM verifica que la reparación funciona.

---

## Sprint 5 — Funcionalidad avanzada
> **Meta**: Añadir las características de mayor valor diferencial del proyecto.

### S5-1 · Streaming de respuesta con SSE
**Situación actual**: El usuario espera en silencio 30-60 segundos sin feedback real.  
**Acción**: Implementar `StreamingResponse` en FastAPI usando el modo streaming de Ollama.

```python
from fastapi.responses import StreamingResponse

async def stream_generation(requirement, model):
    async for chunk in ollama_client.chat(model=model, stream=True, ...):
        yield f"data: {chunk['message']['content']}\n\n"

@router.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    return StreamingResponse(stream_generation(...), media_type="text/event-stream")
```

En frontend: `EventSource` para consumir el stream y renderizar parcialmente.

**Criterio de aceptación**: El texto del LLM aparece en pantalla palabra por palabra; el usuario puede ver que algo está pasando desde el primer segundo.

---

### S5-2 · Integrar evaluador DeepEval al backend
**Situación actual**: `evaluator/metrics.py` es standalone; las métricas de la UI son mock.  
**Acción**: Añadir endpoint `POST /evaluate` que ejecute métricas GEval reales.

```python
@router.post("/evaluate")
async def evaluate(req: EvaluateRequest):
    # req contiene: requirement (str) + test_cases (list)
    # Ejecutar en background task para no bloquear
    scores = await run_deepeval_metrics(req.requirement, req.test_cases)
    return {"coverage": scores[0], "relevancy": scores[1], "consistency": scores[2]}
```

> DeepEval puede tardar ~30-60s. Usar `BackgroundTasks` de FastAPI o un endpoint de polling.

**Criterio de aceptación**: La UI muestra scores reales (0.0–1.0) de Coverage, Relevancy y Consistency al hacer clic en "Evaluar".

---

## Sprint 6 — DevOps
> **Meta**: Que cualquier persona pueda correr el proyecto con un comando y que el CI proteja la rama principal.

### S6-1 · Docker + docker-compose
**Situación actual**: Setup manual con múltiples pasos (Ollama, Python, venv, pip).  
**Acción**: Crear `Dockerfile` para la app y `docker-compose.yml` con ambos servicios.

```yaml
# docker-compose.yml
services:
  app:
    build: .
    ports: ["8000:8000"]
    depends_on: [ollama]
    env_file: .env

  ollama:
    image: ollama/ollama
    volumes: ["ollama_data:/root/.ollama"]
```

**Criterio de aceptación**: `docker-compose up` levanta la app en `localhost:8000` sin instalación manual.

---

### S6-2 · CI con GitHub Actions
**Situación actual**: No hay pipeline de integración continua.  
**Dependencia**: Requiere S4-3 (tests).  
**Acción**: Crear `.github/workflows/ci.yml`.

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
```

**Criterio de aceptación**: Cada push a `main` ejecuta los tests automáticamente; un test fallido bloquea el merge.

---

## Dependencias entre sprints

```
Sprint 1 ──► Sprint 2 ──► Sprint 4 ──► Sprint 5
                               │
                               └──► Sprint 6

Sprint 3  (independiente, puede hacerse en cualquier momento)
```

- **Sprint 3** no depende de nada; se puede implementar en paralelo con cualquier otro sprint.
- **Sprint 5-S5-2** (evaluador real) depende de S4-2 (refactorización) para poder importar `llm_service` limpiamente.
- **Sprint 6-S6-2** (CI) depende de S4-3 (tests) para tener algo que ejecutar.
