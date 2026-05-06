# Manual de Uso — QA Test Case Generator

## Requisitos previos

- Python 3.11+
- [Ollama](https://ollama.ai) instalado y ejecutándose
- Git

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd Proyecto_DL_QA

# 2. Crear entorno virtual (en ruta corta en Windows)
python -m venv C:/qa_venv
C:/qa_venv/Scripts/activate        # Windows CMD
# source C:/qa_venv/bin/activate   # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Descargar modelos Ollama
ollama pull llama3.2
ollama pull mistral
ollama pull nomic-embed-text      # Requerido para RAG
```

## Configuración

Copia `.env.example` a `.env` y completa los valores:

```env
OLLAMA_MODEL=llama3.2
OLLAMA_TEMPERATURE=0.25
OLLAMA_CONTEXT_SIZE=8192
APP_PORT=8000

OPIK_API_KEY=tu_api_key_aqui
OPIK_WORKSPACE=tu_workspace
OPIK_PROJECT_NAME=Qa_trace
```

Obtén tu API key de Opik en [comet.com/opik](https://www.comet.com/opik).

## Ejecución local

```bash
# Desde la raíz del proyecto
uvicorn backend.main:app --reload --port 8000
```

Abre el navegador en `http://localhost:8000`.

## Ejecución con Docker

```bash
# Levantar todos los servicios (Ollama + App)
docker compose up --build

# La UI queda disponible en http://localhost:8000
```

Los modelos se descargan automáticamente al iniciar el contenedor.

## Uso de la interfaz

### Generar casos de prueba (modo estándar)

1. Escribe o selecciona una plantilla de historia de usuario en el campo principal.
2. Opcionalmente agrega contexto adicional.
3. Selecciona el modelo LLM y ajusta la temperatura.
4. Haz clic en **Generar casos de prueba**.
5. Los resultados aparecen en tiempo real en las pestañas: *Test Cases*, *Edge Scenarios*, *Potential Bugs* y *Coverage*.

### Modo Agentes (CrewAI)

1. Activa **🤖 Agentes** en el selector de modo (barra lateral).
2. Haz clic en **Generar casos de prueba**.
3. El Agente Generador produce la suite inicial; el Agente Revisor evalúa cobertura y calidad.
4. La traza de ambos agentes aparece en la pestaña **🤖 Agentes** con tiempo y veredicto.

### RAG — Base de conocimiento QA

El RAG enriquece los prompts con buenas prácticas QA extraídas del corpus local.

```bash
# Construir el índice una sola vez
python scripts/build_index.py
```

Una vez construido, activa el checkbox **Base QA** en la barra lateral antes de generar.

### Exportación

Desde la barra de exportación (aparece al generar resultados):

| Botón | Formato | Contenido |
|---|---|---|
| Copiar JSON | Portapapeles | Objeto JSON completo |
| ⬇ JSON | `.json` | Todos los resultados |
| ⬇ CSV | `.csv` | Solo Test Cases |
| ⬇ MD | `.md` | Test Cases por categoría |
| ⬇ XLSX | `.xlsx` | 4 hojas: TC, Edge, Bugs, Coverage |

### Evaluación con DeepEval

1. Genera casos de prueba.
2. Haz clic en **Evaluar** (requiere `pip install -r requirements-eval.txt`).
3. Las métricas Coverage, Relevancy y Consistency aparecen en la barra lateral.

## Experimento comparativo

```bash
# Corre las 10 historias con Config-A y Config-B
python scripts/run_experiment.py

# Resultados en experiments/results.json
```

## Solución de problemas comunes

| Problema | Solución |
|---|---|
| `ollama: connection refused` | Verifica que Ollama esté ejecutándose: `ollama serve` |
| Ruta muy larga en Windows | Crea el venv en `C:/qa_venv` en lugar de dentro del proyecto |
| `opik.configure` pide confirmación | Asegúrate de usar `force=True` en el código |
| RAG checkbox deshabilitado | Ejecuta `python scripts/build_index.py` primero |
| DeepEval no disponible (503) | Instala con `pip install -r requirements-eval.txt` |
