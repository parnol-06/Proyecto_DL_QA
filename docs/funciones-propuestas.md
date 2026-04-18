# Funciones Propuestas — QA Test Case Generator

**Fecha de análisis:** 2026-04-18  
**Autor del análisis:** Agente de análisis automatizado  
**Estado del proyecto base:** 6 sprints implementados, arquitectura en capas (routes/services/schemas), streaming SSE, DeepEval integrado, Docker disponible.

---

## Estado actual (ya implementado)

Antes de las propuestas, lo que el proyecto ya tiene:

- `POST /generate/stream` con SSE y contador de tokens en tiempo real
- `POST /evaluate` con DeepEval/GEval real (Coverage, Relevancy, Consistency)
- `GET /models` que consulta Ollama dinámicamente
- Semáforo `asyncio` en `_llm_semaphore` para serializar llamadas concurrentes
- `localStorage` para persistir el último resultado entre recargas
- Exportación JSON (descarga + clipboard) y CSV con BOM para Excel
- Expandir/Colapsar todos los TC
- Health-check periódico del `statusDot` cada 30 segundos
- Métricas estimadas locales con `*` + métricas reales via DeepEval
- Botón "Limpiar resultados"
- Dockerfile + docker-compose.yml + entrypoint.sh
- Suite de tests en `tests/` con pytest + httpx

---

## Grupo 1 — Impacto Alto + Esfuerzo Bajo

### F-01 · Exportar a Markdown

**Descripción:** Botón "Descargar .md" en la `exportBar` que genera un archivo Markdown estructurado con todos los TC agrupados por categoría (encabezados H2), pasos como lista numerada y resultado esperado en blockquote.

**Beneficio:** Equipos que usan GitHub, Notion o Confluence pueden pegar el Markdown directamente sin reformatear nada.

**Implementación:** 100% frontend. Función `downloadMarkdown()` en `app.js` que mapea `data.test_cases` a bloques Markdown.

**Archivos:** `frontend/js/app.js`, `frontend/index.html`  
**Dificultad:** Baja | **Categoría:** Frontend

---

### F-02 · Filtrado de TC por categoría y prioridad

**Descripción:** Chips/badges clicables encima de `#tc-list` para filtrar por categoría (`happy_path`, `negativo`, `seguridad`, etc.) y prioridad (`alto`, `medio`, `bajo`). Los TC que no coinciden se ocultan.

**Beneficio:** Con 15+ casos, los testers solo quieren ver los de seguridad o los de prioridad alta. Hoy tienen que scrollear manualmente.

**Implementación:** Atributos `data-category` y `data-priority` en cada `.tc-card`. Función `filterTC(category, priority)` en `app.js` con estado global `_activeCategory` / `_activePriority`.

**Archivos:** `frontend/js/render.js`, `frontend/js/app.js`, `frontend/index.html`, `frontend/css/styles.css`  
**Dificultad:** Baja | **Categoría:** Frontend

---

### F-03 · Búsqueda por texto en TC

**Descripción:** Input de búsqueda sobre el panel de Test Cases que filtra en tiempo real los TC cuyo título, pasos o resultado esperado contengan el texto ingresado. Compatible con el filtro de categorías (lógica AND).

**Beneficio:** En suites grandes, encontrar el TC de "bloqueo de cuenta" entre 15 casos requiere leer todos.

**Implementación:** Listener `oninput` en `app.js` sobre `<input id="tcSearch">` que compara `.innerText.toLowerCase()`.

**Archivos:** `frontend/index.html`, `frontend/js/app.js`, `frontend/css/styles.css`  
**Dificultad:** Baja | **Categoría:** Frontend

---

### F-04 · Contador de tiempo de generación visible

**Descripción:** Temporizador visible junto al spinner que muestra los segundos transcurridos ("Generando... 23s"). Al terminar, el toast muestra el tiempo total: "15 casos generados en 47s".

**Beneficio:** El usuario sabe que el proceso no se colgó y puede comparar velocidad entre modelos.

**Implementación:** En `generate()`: `const t0 = Date.now()`, `setInterval` que actualiza `btnText`. Limpiar el interval en `finally`.

**Archivos:** `frontend/js/app.js`  
**Dificultad:** Baja | **Categoría:** Frontend

---

### F-05 · Health-check con estado real de Ollama

**Descripción:** Extender `GET /health` para que reporte si Ollama está realmente disponible, cuántos modelos están cargados y si hay un modelo activo. Si Ollama está caído, el `statusDot` se pone en ámbar (FastAPI ok, Ollama no).

**Beneficio:** Hoy el dot se pone verde si FastAPI responde, no si Ollama responde. El usuario solo descubre el problema al generar y esperar 30+ segundos.

**Implementación:** `ollama.list()` con `try/except` en `health()`. Respuesta: `{"status": "ok|degraded", "ollama": true|false, "models_count": N}`.

**Archivos:** `backend/routes/generate.py`, `frontend/js/api.js`  
**Dificultad:** Baja | **Categoría:** Backend + Frontend

---

### F-11 · Templates de historias de usuario predefinidas

**Descripción:** Dropdown "Cargar ejemplo" con 8-10 plantillas comunes (Login, Checkout, Búsqueda, Upload, Recuperación de contraseña, etc.) que pre-llenan el textarea al seleccionarlas.

**Beneficio:** Reduce la fricción de onboarding. Los templates también sirven como referencia de formato correcto para nuevos usuarios.

**Implementación:** Objeto `TEMPLATES` en `app.js` con entradas `{label, story, context}`. Select HTML con `onchange="loadTemplate(this.value)"`.

**Archivos:** `frontend/index.html`, `frontend/js/app.js`, `frontend/css/styles.css`  
**Dificultad:** Baja | **Categoría:** Frontend

---

## Grupo 2 — Impacto Alto + Esfuerzo Medio/Alto

### F-06 · Historial de sesiones con navegación

**Descripción:** Panel o modal que lista las últimas 10 generaciones con timestamp, fragmento del requisito y cantidad de TC. Permite cargar cualquier resultado anterior con un clic.

**Beneficio:** Hoy `localStorage` solo guarda el ÚLTIMO resultado. Con múltiples historias de usuario se pierden los anteriores. El historial convierte la herramienta en un workspace real.

**Implementación:** Array `_history = []` guardado en `localStorage` como `qaHistory`. Al cada generación exitosa: `_history.unshift({id, timestamp, story_preview, result})`. Nuevo componente `<div id="historyPanel">` en el header. Al clic en entrada: `renderResult(entry.result)`.

**Archivos:** `frontend/index.html`, `frontend/js/app.js`, `frontend/js/render.js`, `frontend/css/styles.css`  
**Dificultad:** Media | **Categoría:** Frontend

---

### F-07 · Exportar a XLSX con hojas separadas por categoría

**Descripción:** Botón "Descargar .xlsx" que genera un Excel con cuatro hojas: "Test Cases", "Edge Scenarios", "Potential Bugs" y "Coverage". Celdas formateadas con colores por prioridad y columnas dedicadas para cada paso.

**Beneficio:** El CSV actual pierde el formato de los pasos al abrirlo en Excel (todo en una celda separado por `|`). El XLSX es lo que los equipos QA realmente usan.

**Implementación:** Librería `SheetJS (xlsx)` via CDN. Función `downloadXLSX()` con `XLSX.utils.json_to_sheet()` por sección y `XLSX.utils.book_append_sheet()`.

**Archivos:** `frontend/index.html` (CDN SheetJS + botón en exportBar), `frontend/js/app.js`  
**Dificultad:** Media | **Categoría:** Frontend

---

### F-08 · Generación por lotes (múltiples historias)

**Descripción:** Modo batch donde el usuario separa múltiples historias de usuario con `---`. El sistema las procesa en secuencia y consolida una suite completa con IDs prefijados (`A-TC-001`, `B-TC-001`).

**Beneficio:** Los equipos que reciben un sprint completo (6-8 historias) hoy tienen que correr el generador 8 veces manualmente y consolidar.

**Implementación:**
- Frontend: detectar `---` en `userStory.value`, activar modo batch con indicador "Procesando historia 2 de 5...".
- Backend: nuevo endpoint `POST /generate/batch` con schema `BatchGenerateRequest`.

**Archivos:** `backend/routes/generate.py`, `backend/schemas/models.py`, `frontend/js/app.js`, `frontend/index.html`  
**Dificultad:** Media | **Categoría:** Backend + Frontend

---

### F-09 · Regenerar un TC individual

**Descripción:** Botón de refresh en cada tarjeta de TC que reenvía solo ese caso al LLM con instrucción de mejorar o variar el caso específico, manteniendo categoría y requisito original.

**Beneficio:** A veces el LLM genera un TC de seguridad genérico. En lugar de regenerar los 15 y perder los 14 buenos, el usuario puede mejorar solo ese uno.

**Implementación:**
- Backend: `POST /regenerate-tc` con body `{user_story, context, tc_to_improve, model}`. System prompt corto y enfocado.
- Frontend: botón en `.tc-header` con spinner individual. Al recibir el TC nuevo, reemplazar en `data.test_cases` y re-renderizar.

**Archivos:** `backend/routes/generate.py`, `backend/services/llm_service.py`, `backend/schemas/models.py`, `frontend/js/render.js`, `frontend/js/app.js`  
**Dificultad:** Media | **Categoría:** Backend + Frontend + IA

---

### F-10 · Métricas de calidad adicionales en DeepEval

**Descripción:** Dos nuevas métricas GEval: "Specificity" (penaliza pasos genéricos como "navegar a la página") y "Non-Functional Balance" (proporción adecuada de casos funcionales vs no funcionales).

**Beneficio:** Las 3 métricas actuales no detectan el problema más común: pasos que no son accionables. "Specificity" lo detecta directamente.

**Implementación:** Funciones `make_specificity_metric()` y `make_nf_balance_metric()` en `evaluator/metrics.py`. Nuevos campos `specificity: float` y `nf_balance: float` en `EvaluateResponse`.

**Archivos:** `evaluator/metrics.py`, `backend/schemas/models.py`, `backend/services/eval_service.py`, `frontend/index.html`, `frontend/js/render.js`  
**Dificultad:** Media | **Categoría:** IA + Backend + Frontend

---

## Grupo 3 — Impacto Medio

### F-12 · Configuración de categorías a incluir

**Descripción:** Checkboxes que permiten elegir qué categorías incluir y cuántos casos mínimos por categoría desea. El system prompt se genera dinámicamente según la selección.

**Beneficio:** Para requisitos simples, generar 3 casos de rendimiento es ruido. El usuario puede desactivar categorías no relevantes.

**Archivos:** `backend/schemas/models.py`, `backend/services/llm_service.py`, `frontend/index.html`, `frontend/js/app.js`  
**Dificultad:** Media | **Categoría:** Backend + Frontend + IA

---

### F-13 · Indicador de carga del modelo Ollama

**Descripción:** Mostrar junto al selector de modelo si está cargado en memoria (con uso de RAM/VRAM via `/api/ps` de Ollama) o si aún no está cargado (cold start, primera generación tardará más).

**Implementación:** `GET /model-status` en backend que llama `ollama.ps()`. Frontend actualiza al cambiar modelo en el select.

**Archivos:** `backend/routes/generate.py`, `frontend/js/api.js`, `frontend/index.html`  
**Dificultad:** Baja | **Categoría:** Backend + Frontend

---

### F-14 · Modo claro / oscuro con toggle

**Descripción:** Botón en el header para alternar entre el tema oscuro actual y un tema claro. Preferencia guardada en `localStorage`.

**Implementación:** Variables CSS bajo `body.light-mode { --bg: #f8f8fc; ... }`. `document.body.classList.toggle('light-mode')` en `app.js`.

**Archivos:** `frontend/css/styles.css`, `frontend/index.html`, `frontend/js/app.js`  
**Dificultad:** Baja | **Categoría:** Frontend

---

### F-15 · Comparador de dos generaciones

**Descripción:** Modo "comparar" que carga dos resultados del historial (F-06) lado a lado, resaltando TC que están en uno pero no en el otro, y diferencias en cobertura de categorías.

**Beneficio:** Un QA lead que quiere elegir entre `llama3.2` vs `mistral` necesita comparar cualitativamente sin abrir dos pestañas.

**Archivos:** `frontend/index.html`, `frontend/js/app.js`, `frontend/js/render.js`, `frontend/css/styles.css`  
**Dificultad:** Media | **Categoría:** Frontend

---

### F-16 · Ajuste de temperatura desde la UI

**Descripción:** Slider (rango 0.0–1.0, default 0.25) en el sidebar para ajustar la temperatura del LLM sin tocar `.env`. El valor se envía en el body del POST.

**Implementación:** Campo `temperature: float` en `GenerateRequest` con `ge=0.0, le=1.0`. `llm_service.py` usa `req.temperature` en lugar de la constante.

**Archivos:** `backend/schemas/models.py`, `backend/services/llm_service.py`, `frontend/index.html`, `frontend/js/app.js`  
**Dificultad:** Baja | **Categoría:** Backend + Frontend

---

## Grupo 4 — Ideas Futuras (Mayor Complejidad)

### F-17 · Persistencia en SQLite

**Descripción:** Reemplazar `localStorage` por `aiosqlite`. Cada generación se guarda con timestamp, modelo, historia y resultado JSON. El historial se convierte en una consulta SQL real con paginación y búsqueda.

**Beneficio:** `localStorage` tiene límite de ~5MB, no es consultable y se borra al limpiar caché. SQLite permite búsqueda histórica y estadísticas de uso por modelo.

**Archivos:** Nuevo `backend/services/db_service.py`, nuevo `backend/routes/history.py`, `backend/main.py`, `requirements.txt`, `frontend/js/app.js`  
**Dificultad:** Alta | **Categoría:** Backend

---

### F-18 · Integración con Jira / GitHub Issues

**Descripción:** Botón "Exportar a Jira" o "Crear Issues en GitHub" que crea los TC seleccionados como issues via API REST. Cada TC se convierte en un issue con labels (categoría) y descripción estructurada.

**Implementación:** Variables en `.env`: `GITHUB_TOKEN`, `GITHUB_REPO`, `JIRA_URL`, `JIRA_TOKEN`, `JIRA_PROJECT`. Endpoints `POST /export/github-issues` y `POST /export/jira-issues`.

**Archivos:** Nuevo `backend/routes/export.py`, nuevo `backend/services/integration_service.py`, `backend/main.py`, `.env.example`, `frontend/index.html`, `frontend/js/app.js`  
**Dificultad:** Alta | **Categoría:** Backend + DevOps

---

### F-19 · Evaluación asíncrona con polling

**Descripción:** `POST /evaluate/start` devuelve un `job_id` inmediatamente. `GET /evaluate/status/{job_id}` devuelve el progreso. Frontend hace polling cada 3s hasta `status: "done"`.

**Beneficio:** La evaluación actual bloquea la conexión HTTP 30-60 segundos. Si el usuario cierra la pestaña, el resultado se pierde. El modelo asíncrono desacopla proceso y cliente.

**Archivos:** `backend/routes/evaluate.py`, `backend/services/eval_service.py`, `frontend/js/app.js`  
**Dificultad:** Alta | **Categoría:** Backend + Frontend

---

### F-20 · Tests de integración CI contra Ollama real

**Descripción:** Job adicional en `.github/workflows/ci.yml` que levanta Ollama en el runner via Docker, descarga `tinyllama`, y corre tests marcados con `@pytest.mark.integration` que validan el parseo JSON del output real del LLM.

**Beneficio:** Los tests actuales mockean Ollama. Un cambio en el system prompt que rompa el parseo JSON no lo detectaría ningún test actual.

**Archivos:** `.github/workflows/ci.yml`, `tests/test_generate.py`, `pytest.ini`  
**Dificultad:** Alta | **Categoría:** DevOps

---

## Tabla resumen

| ID | Nombre | Dificultad | Categoría | Grupo |
|----|--------|------------|-----------|-------|
| F-01 | Exportar a Markdown | Baja | Frontend | Alto impacto, fácil |
| F-02 | Filtrado por categoría y prioridad | Baja | Frontend | Alto impacto, fácil |
| F-03 | Búsqueda por texto en TC | Baja | Frontend | Alto impacto, fácil |
| F-04 | Contador de tiempo de generación | Baja | Frontend | Alto impacto, fácil |
| F-05 | Health-check con estado Ollama real | Baja | Backend + Frontend | Alto impacto, fácil |
| F-11 | Templates de historias predefinidas | Baja | Frontend | Alto impacto, fácil |
| F-06 | Historial de sesiones con navegación | Media | Frontend | Alto impacto, complejo |
| F-07 | Exportar a XLSX por categoría | Media | Frontend | Alto impacto, complejo |
| F-08 | Generación por lotes | Media | Backend + Frontend | Alto impacto, complejo |
| F-09 | Regenerar un TC individual | Media | Backend + Frontend + IA | Alto impacto, complejo |
| F-10 | Métricas adicionales en DeepEval | Media | IA + Backend + Frontend | Alto impacto, complejo |
| F-12 | Configuración de categorías | Media | Backend + Frontend + IA | Impacto medio |
| F-13 | Indicador de carga del modelo | Baja | Backend + Frontend | Impacto medio |
| F-14 | Modo claro / oscuro | Baja | Frontend | Impacto medio |
| F-15 | Comparador de dos generaciones | Media | Frontend | Impacto medio |
| F-16 | Ajuste de temperatura desde la UI | Baja | Backend + Frontend | Impacto medio |
| F-17 | Persistencia en SQLite | Alta | Backend | Ideas futuras |
| F-18 | Integración con Jira / GitHub Issues | Alta | Backend + DevOps | Ideas futuras |
| F-19 | Evaluación asíncrona con polling | Alta | Backend + Frontend | Ideas futuras |
| F-20 | CI con tests de integración reales | Alta | DevOps | Ideas futuras |

---

## Roadmap recomendado por semanas

| Semana | Funciones | Foco |
|--------|-----------|------|
| Semana 1 | F-04, F-01, F-03, F-11 | Mejoras frontend inmediatas y visibles |
| Semana 2 | F-02, F-05, F-13, F-16 | Filtros, health-check real y temperatura desde UI |
| Semana 3 | F-06, F-07 | Historial + XLSX → workspace persistente |
| Semana 4 | F-09, F-10 | IA: regenerar TC individual + métricas adicionales |
| Semana 5 | F-08, F-12 | Modo batch + configuración de categorías |
| Futuro | F-17, F-18, F-19, F-20 | Infraestructura avanzada y persistencia multi-sesión |

---

## Archivos que concentran la mayoría de cambios

- `frontend/js/app.js` — lógica de todos los flujos de UI
- `frontend/js/render.js` — renderizado de resultados
- `backend/routes/generate.py` — endpoints principales
- `backend/services/llm_service.py` — integración con Ollama
- `backend/schemas/models.py` — validación de requests/responses
- `evaluator/metrics.py` — métricas DeepEval/GEval
