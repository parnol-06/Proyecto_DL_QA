# Sprints Roadmap — QA Test Case Generator

**Fecha de creacion:** 2026-04-18  
**Version:** 1.0  
**Estado general:** Pre-desarrollo (todas las funciones pendientes)

---

## Tabla de sprints

| Sprint | Duracion | Funciones incluidas | Objetivo principal |
|--------|----------|---------------------|--------------------|
| Sprint 1 | Semana 1 | F-04, F-01, F-03, F-11 | Mejoras de UX frontend visibles de inmediato, cero cambios de backend |
| Sprint 2 | Semana 2 | F-02, F-05, F-13, F-16 | Filtros avanzados, health-check real de Ollama y temperatura configurable |
| Sprint 3 | Semana 3 | F-06, F-07 | Workspace persistente: historial de sesiones y exportacion XLSX |
| Sprint 4 | Semana 4 | F-09, F-10 | Mejoras de calidad asistidas por IA: regeneracion individual y nuevas metricas |
| Sprint 5 | Semana 5 | F-08, F-12 | Productividad en escala: modo batch y categorizacion configurable |
| Post-MVP | Futuro | F-14, F-15, F-17, F-18, F-19, F-20 | Infraestructura avanzada, integraciones externas y CI real |

---

## Sprint 1 — Frontend puro (Semana 1)

**Objetivo:** Entregar cuatro mejoras de UX visibles e independientes sin tocar el backend. El usuario percibe el valor al instante.

### Orden de implementacion recomendado

1. F-04 (contador de tiempo) — una sola funcion en `app.js`, sin dependencias
2. F-11 (templates) — objeto de datos + elemento HTML, no depende de resultados renderizados
3. F-01 (exportar Markdown) — requiere conocer la estructura de `data.test_cases`
4. F-03 (busqueda por texto) — depende de que el renderizado de tarjetas ya exista

---

### [ ] F-04 · Contador de tiempo de generacion visible

**Descripcion:** Temporizador junto al spinner que muestra los segundos transcurridos ("Generando... 23s"). Al terminar, el toast muestra el tiempo total ("15 casos generados en 47s").

**Archivos a modificar:**
- `frontend/js/app.js` — capturar `const t0 = Date.now()` al inicio de `generate()`, iniciar `setInterval` que actualiza el texto del boton cada segundo, limpiar el interval en el bloque `finally`

**Criterios de aceptacion:**
- [ ] El boton muestra "Generando... Xs" donde X se incrementa cada segundo mientras el LLM responde
- [ ] Al completarse, el toast incluye el tiempo total en segundos
- [ ] El contador se resetea correctamente en generaciones consecutivas
- [ ] Si ocurre un error, el interval se limpia y el boton vuelve a su estado original

---

### [ ] F-01 · Exportar a Markdown

**Descripcion:** Boton "Descargar .md" en la `exportBar` que genera un archivo Markdown estructurado con todos los TC agrupados por categoria (encabezados H2), pasos como lista numerada y resultado esperado en blockquote.

**Archivos a modificar:**
- `frontend/js/app.js` — funcion `downloadMarkdown()` que mapea `data.test_cases` a bloques Markdown y usa `Blob` + `URL.createObjectURL` para la descarga
- `frontend/index.html` — agregar boton "Descargar .md" junto a los botones existentes de exportacion en `exportBar`

**Criterios de aceptacion:**
- [ ] El boton aparece unicamente cuando hay resultados disponibles
- [ ] El archivo descargado tiene extension `.md` y nombre basado en la fecha o titulo del requisito
- [ ] Cada categoria aparece como encabezado H2 (`## Happy Path`)
- [ ] Cada TC tiene titulo H3, pasos como lista numerada y resultado esperado en blockquote (`>`)
- [ ] El archivo se puede pegar directamente en GitHub, Notion o Confluence sin reformatear

---

### [ ] F-03 · Busqueda por texto en TC

**Descripcion:** Input de busqueda sobre el panel de Test Cases que filtra en tiempo real los TC cuyo titulo, pasos o resultado esperado contengan el texto ingresado.

**Archivos a modificar:**
- `frontend/index.html` — agregar `<input id="tcSearch">` encima de `#tc-list`
- `frontend/js/app.js` — listener `oninput` que compara el texto del input con `.innerText.toLowerCase()` de cada `.tc-card` y aplica `display: none` a las que no coinciden
- `frontend/css/styles.css` — estilos para el input de busqueda (consistente con el diseno actual)

**Criterios de aceptacion:**
- [ ] El input de busqueda aparece solo cuando hay resultados renderizados
- [ ] El filtrado ocurre en tiempo real sin debounce perceptible (menos de 50ms)
- [ ] La busqueda es case-insensitive
- [ ] Limpiar el input restaura todos los TC visibles
- [ ] Si ningun TC coincide, se muestra un mensaje "Sin resultados para la busqueda"
- [ ] Es compatible con el filtro de categorias de F-02 (logica AND cuando ambos esten activos)

---

### [ ] F-11 · Templates de historias de usuario predefinidas

**Descripcion:** Dropdown "Cargar ejemplo" con 8-10 plantillas comunes que pre-llenan el textarea al seleccionarlas.

**Archivos a modificar:**
- `frontend/js/app.js` — objeto `TEMPLATES` con al menos 8 entradas `{label, story, context}` y funcion `loadTemplate(key)` que asigna los valores al textarea y al campo de contexto
- `frontend/index.html` — `<select>` con `onchange="loadTemplate(this.value)"` y opcion vacia por defecto ("Cargar ejemplo...")
- `frontend/css/styles.css` — estilos para el select (consistente con el sidebar actual)

**Templates minimos requeridos:** Login, Registro, Checkout, Busqueda, Upload de archivo, Recuperacion de contrasena, CRUD de entidad, API REST autenticada

**Criterios de aceptacion:**
- [ ] El select tiene una opcion vacia por defecto que no modifica el textarea
- [ ] Al seleccionar un template, el textarea y el campo de contexto se rellenan con el contenido de `TEMPLATES[key]`
- [ ] Despues de cargar un template, el select vuelve a la opcion vacia para permitir cargar otro
- [ ] Los templates son editables por el usuario despues de cargarse (no son readonly)
- [ ] Hay al menos 8 templates cubriendo casos comunes del dominio QA

---

## Sprint 2 — Frontend + Backend leve (Semana 2)

**Objetivo:** Agregar filtros interactivos sobre los resultados, hacer que el health-check refleje el estado real de Ollama, indicar si el modelo esta cargado en memoria y exponer la temperatura desde la UI.

### Orden de implementacion recomendado

1. F-16 (slider de temperatura) — cambio mas pequeno en backend y frontend, buena entrada al sprint
2. F-05 (health-check Ollama real) — modifica `generate.py` y `api.js` de forma aislada
3. F-13 (indicador de carga del modelo) — requiere que F-05 este listo para reutilizar el patron de llamada a Ollama
4. F-02 (filtros de categoria/prioridad) — el mas costoso del sprint, va al final cuando los demas esten validados

---

### [ ] F-16 · Ajuste de temperatura desde la UI

**Descripcion:** Slider (rango 0.0–1.0, paso 0.05, default 0.25) en el sidebar para ajustar la temperatura del LLM. El valor se envía en el body del POST.

**Archivos a modificar:**
- `backend/schemas/models.py` — agregar campo `temperature: float = Field(0.25, ge=0.0, le=1.0)` en `GenerateRequest`
- `backend/services/llm_service.py` — reemplazar la constante de temperatura por `req.temperature` al construir la llamada a Ollama
- `frontend/index.html` — `<input type="range">` con min=0, max=1, step=0.05, value=0.25 y etiqueta que muestre el valor actual
- `frontend/js/app.js` — leer el valor del slider e incluirlo en el body del `fetch` a `/generate`

**Criterios de aceptacion:**
- [ ] El slider aparece en el sidebar junto al selector de modelo
- [ ] La etiqueta muestra el valor en tiempo real al mover el slider ("Temperatura: 0.35")
- [ ] El valor por defecto es 0.25 (comportamiento actual preservado)
- [ ] El backend valida que el valor este en [0.0, 1.0] y devuelve 422 si no
- [ ] El valor del slider persiste en `localStorage` entre recargas de pagina

---

### [ ] F-05 · Health-check con estado real de Ollama

**Descripcion:** Extender `GET /health` para reportar si Ollama esta realmente disponible, cuantos modelos hay cargados y si hay un modelo activo. El `statusDot` muestra ambar si FastAPI responde pero Ollama no.

**Archivos a modificar:**
- `backend/routes/generate.py` — en el endpoint `GET /health`, envolver `await ollama.list()` en `try/except` y devolver `{"status": "ok"|"degraded", "ollama": true|false, "models_count": N}`
- `frontend/js/api.js` — actualizar la funcion que consume `/health` para leer el campo `ollama` y asignar color verde (ok), ambar (degraded) o rojo (error de red) al `statusDot`

**Criterios de aceptacion:**
- [ ] Cuando Ollama esta corriendo: `statusDot` verde, `status: "ok"`
- [ ] Cuando FastAPI corre pero Ollama no responde: `statusDot` ambar, `status: "degraded"`, `ollama: false`
- [ ] Cuando FastAPI no responde: `statusDot` rojo (comportamiento existente)
- [ ] El health-check periodico existente (cada 30s) sigue funcionando con la nueva logica
- [ ] El campo `models_count` refleja la cantidad real de modelos disponibles en Ollama

---

### [ ] F-13 · Indicador de carga del modelo Ollama

**Descripcion:** Mostrar junto al selector de modelo si esta cargado en memoria (con uso de RAM/VRAM via `/api/ps` de Ollama) o si aun no esta cargado (cold start esperado).

**Archivos a modificar:**
- `backend/routes/generate.py` — nuevo endpoint `GET /model-status?model={name}` que llama a `ollama.ps()` y devuelve `{"loaded": true|false, "size_vram": N}` para el modelo solicitado
- `frontend/js/api.js` — funcion `fetchModelStatus(modelName)` que llama a `GET /model-status`
- `frontend/index.html` — badge junto al `<select>` de modelos que muestre "En memoria" (verde) o "Cold start" (gris) segun la respuesta

**Criterios de aceptacion:**
- [ ] Al cambiar el modelo en el select, el badge se actualiza con una llamada a `/model-status`
- [ ] Si el modelo esta cargado, muestra "En memoria" con indicador verde
- [ ] Si el modelo no esta cargado, muestra "Cold start" con indicador gris y tooltip "Primera generacion tardara mas"
- [ ] Si `/model-status` falla, el badge no se muestra (no bloquea la UI)
- [ ] La consulta no bloquea la interaccion del usuario mientras carga

---

### [ ] F-02 · Filtrado de TC por categoria y prioridad

**Descripcion:** Chips/badges clicables encima de `#tc-list` para filtrar por categoria (`happy_path`, `negativo`, `seguridad`, etc.) y prioridad (`alto`, `medio`, `bajo`).

**Archivos a modificar:**
- `frontend/js/render.js` — agregar atributos `data-category` y `data-priority` en cada `.tc-card` al momento de renderizar
- `frontend/js/app.js` — funcion `filterTC(category, priority)` con estado global `_activeCategory` y `_activePriority`; chips generados dinamicamente segun las categorias presentes en los resultados actuales
- `frontend/index.html` — contenedor `<div id="tcFilters">` encima de `#tc-list`
- `frontend/css/styles.css` — estilos para chips activos/inactivos (clases `.chip`, `.chip--active`)

**Criterios de aceptacion:**
- [ ] Los chips de categoria se generan dinamicamente con las categorias que realmente aparecen en los resultados (no un set fijo)
- [ ] Al hacer clic en un chip de categoria, solo se muestran los TC de esa categoria; clic de nuevo lo desactiva
- [ ] Los filtros de categoria y prioridad se combinan con logica AND
- [ ] Un contador muestra cuantos TC son visibles vs el total ("Mostrando 5 de 15")
- [ ] Los chips se limpian al generar nuevos resultados
- [ ] Compatible con la busqueda por texto de F-03 (todos los filtros activos se aplican juntos)

---

## Sprint 3 — Workspace persistente (Semana 3)

**Objetivo:** Convertir la herramienta en un workspace real donde el usuario pueda navegar entre generaciones anteriores y exportar resultados a Excel con formato profesional.

### Orden de implementacion recomendado

1. F-06 (historial de sesiones) — la persistencia del historial es prerequisito para F-15 (comparador) en el futuro
2. F-07 (exportar XLSX) — independiente, pero se beneficia de tener historial para exportar cualquier entrada guardada

---

### [ ] F-06 · Historial de sesiones con navegacion

**Descripcion:** Panel que lista las ultimas 10 generaciones con timestamp, fragmento del requisito y cantidad de TC. Permite cargar cualquier resultado anterior con un clic.

**Archivos a modificar:**
- `frontend/js/app.js` — array `_history` gestionado en `localStorage` como `qaHistory`; al cada generacion exitosa: `_history.unshift({id, timestamp, story_preview, tc_count, result})`; limitar a 10 entradas; funcion `loadHistoryEntry(id)`
- `frontend/js/render.js` — funcion `renderHistoryPanel(history)` que genera la lista de entradas del historial
- `frontend/index.html` — `<div id="historyPanel">` accesible desde el header (boton o icono); cada entrada con timestamp, preview del requisito (primeros 80 caracteres) y cantidad de TC
- `frontend/css/styles.css` — estilos para el panel de historial (slide-in lateral o dropdown)

**Criterios de aceptacion:**
- [ ] Cada generacion exitosa se guarda automaticamente en `qaHistory` con `id` unico (timestamp ms)
- [ ] El historial persiste entre recargas de pagina
- [ ] Se conservan como maximo 10 entradas; la mas antigua se elimina al superar el limite
- [ ] Al hacer clic en una entrada del historial, `renderResult(entry.result)` carga los resultados sin hacer una nueva llamada al backend
- [ ] Cada entrada muestra: timestamp formateado, preview del requisito (80 chars + "..."), cantidad de TC generados
- [ ] Hay un boton para eliminar entradas individuales del historial
- [ ] El panel puede cerrarse sin perder el resultado actualmente visible

---

### [ ] F-07 · Exportar a XLSX con hojas separadas por categoria

**Descripcion:** Boton "Descargar .xlsx" que genera un Excel con cuatro hojas: "Test Cases", "Edge Scenarios", "Potential Bugs" y "Coverage". Celdas coloreadas por prioridad.

**Archivos a modificar:**
- `frontend/index.html` — agregar CDN de SheetJS (`<script src="https://cdn.sheetjs.com/xlsx-latest/package/dist/xlsx.full.min.js">`) y boton "Descargar .xlsx" en `exportBar`
- `frontend/js/app.js` — funcion `downloadXLSX()` que usa `XLSX.utils.json_to_sheet()` para cada seccion de datos y `XLSX.utils.book_append_sheet()` para armar el workbook; no incluir logica de estilo condicional si SheetJS Community no la soporta

**Criterios de aceptacion:**
- [ ] El boton aparece unicamente cuando hay resultados disponibles
- [ ] El archivo descargado tiene extension `.xlsx` y nombre con fecha
- [ ] Hoja "Test Cases": columnas ID, Titulo, Categoria, Prioridad, Pasos (uno por celda o separados por salto de linea), Resultado Esperado
- [ ] Hoja "Edge Scenarios": columnas Escenario, Descripcion
- [ ] Hoja "Potential Bugs": columnas Bug, Severidad, Descripcion
- [ ] Hoja "Coverage": columnas Categoria, Cantidad de TC, Porcentaje
- [ ] El archivo se abre correctamente en Excel y LibreOffice Calc sin errores de formato
- [ ] Los pasos de cada TC no quedan concatenados en una sola cadena ilegible

---

## Sprint 4 — IA y calidad (Semana 4)

**Objetivo:** Permitir mejorar TC individuales sin regenerar toda la suite, y agregar metricas de calidad que detecten pasos genericos o suites mal balanceadas.

### Orden de implementacion recomendado

1. F-09 (regenerar TC individual) — modifica backend y frontend de forma acotada; resultado visible e inmediato
2. F-10 (metricas adicionales DeepEval) — requiere trabajo en `evaluator/metrics.py` y propagacion por schemas; va al final del sprint para no bloquear F-09

---

### [ ] F-09 · Regenerar un TC individual

**Descripcion:** Boton de refresh en cada tarjeta de TC que reenvía solo ese caso al LLM con instruccion de mejorar o variar el caso especifico, manteniendo categoria y requisito original.

**Archivos a modificar:**
- `backend/routes/generate.py` — nuevo endpoint `POST /regenerate-tc` con body `{user_story, context, tc_to_improve, model, temperature}`; system prompt corto enfocado en mejorar el TC recibido sin cambiar la categoria
- `backend/services/llm_service.py` — funcion `regenerate_single_tc(req)` separada del flujo principal
- `backend/schemas/models.py` — nuevo schema `RegenerateTCRequest` y `RegenerateTCResponse`
- `frontend/js/render.js` — agregar boton de refresh en cada `.tc-header` con spinner individual por tarjeta
- `frontend/js/app.js` — funcion `regenerateTC(tcId)` que llama a `POST /regenerate-tc`, reemplaza el TC en `data.test_cases` y re-renderiza solo esa tarjeta

**Criterios de aceptacion:**
- [ ] Cada tarjeta de TC tiene un boton de refresh visible (icono, no texto largo)
- [ ] Al hacer clic, solo esa tarjeta muestra spinner; el resto de la UI permanece usable
- [ ] El backend devuelve un TC con la misma categoria y formato JSON que los TC originales
- [ ] Al recibir la respuesta, el TC anterior se reemplaza en el array `data.test_cases` y la tarjeta se re-renderiza sin recargar toda la lista
- [ ] Si el endpoint falla, se muestra un toast de error y el TC original permanece
- [ ] El boton de regenerar no esta disponible si no hay un resultado activo

---

### [ ] F-10 · Metricas de calidad adicionales en DeepEval

**Descripcion:** Dos nuevas metricas GEval: "Specificity" (penaliza pasos genericos) y "Non-Functional Balance" (proporcion adecuada de casos funcionales vs no funcionales).

**Archivos a modificar:**
- `evaluator/metrics.py` — funciones `make_specificity_metric()` y `make_nf_balance_metric()` siguiendo el patron de `make_coverage_metric()` existente
- `backend/schemas/models.py` — nuevos campos opcionales `specificity: float | None` y `nf_balance: float | None` en `EvaluateResponse`
- `backend/services/eval_service.py` — incluir las nuevas metricas en el pipeline de evaluacion existente
- `frontend/index.html` — agregar dos nuevas celdas en la tabla o grilla de metricas del tab "Cobertura"
- `frontend/js/render.js` — renderizar los valores de `specificity` y `nf_balance` cuando esten presentes en la respuesta

**Criterios de aceptacion:**
- [ ] `make_specificity_metric()` devuelve un objeto `GEval` con criterio que penaliza pasos que contienen frases genericas como "navegar a la pagina" o "hacer clic en el boton"
- [ ] `make_nf_balance_metric()` devuelve un objeto `GEval` con criterio que valida que al menos el 30% de los TC sean de categorias no funcionales (seguridad, rendimiento, usabilidad, compatibilidad)
- [ ] Ambas metricas aparecen en la respuesta de `POST /evaluate` con valores entre 0 y 1
- [ ] La UI muestra los nuevos valores junto a las metricas existentes con su nombre y valor formateado
- [ ] Si las metricas no estan disponibles (campo `None`), la UI no muestra error

---

## Sprint 5 — Batch + Configuracion (Semana 5)

**Objetivo:** Escalar la herramienta para equipos que procesan multiples historias de usuario a la vez y dar control sobre que categorias se generan.

### Orden de implementacion recomendado

1. F-12 (configuracion de categorias) — modifica el prompt dinamicamente; sienta base para F-08 donde tambien se puede aplicar esta configuracion
2. F-08 (generacion por lotes) — el mas complejo del sprint; requiere que la configuracion de categorias ya este disponible

---

### [ ] F-12 · Configuracion de categorias a incluir

**Descripcion:** Checkboxes en la UI para elegir que categorias incluir en la generacion. El system prompt se genera dinamicamente segun la seleccion.

**Archivos a modificar:**
- `backend/schemas/models.py` — campo `categories: list[str] | None` en `GenerateRequest`; si es `None` o vacio, se usan las 7 categorias por defecto
- `backend/services/llm_service.py` — el system prompt se construye con `build_system_prompt(categories)` que reemplaza la lista fija de categorias por la lista recibida
- `frontend/index.html` — grupo de checkboxes en el sidebar con las 7 categorias (todas marcadas por defecto): happy_path, edge_cases, negativo, seguridad, rendimiento, usabilidad, compatibilidad
- `frontend/js/app.js` — leer los checkboxes seleccionados e incluirlos en el body del POST como array `categories`

**Criterios de aceptacion:**
- [ ] Los 7 checkboxes aparecen marcados por defecto
- [ ] Se puede desmarcar cualquier combinacion de categorias
- [ ] El backend recibe la lista de categorias seleccionadas y solo genera TC para esas categorias
- [ ] Si se desmarcan todas, se usa el set completo por defecto (no se permite enviar un array vacio)
- [ ] El system prompt resultante menciona explicitamente solo las categorias seleccionadas
- [ ] La seleccion de categorias persiste en `localStorage` entre sesiones

---

### [ ] F-08 · Generacion por lotes

**Descripcion:** Modo batch donde el usuario separa multiples historias de usuario con `---`. El sistema las procesa en secuencia y consolida una suite completa con IDs prefijados (`A-TC-001`, `B-TC-001`).

**Archivos a modificar:**
- `backend/routes/generate.py` — nuevo endpoint `POST /generate/batch` con schema `BatchGenerateRequest`; procesa las historias en secuencia (no en paralelo para respetar el semaforo existente `_llm_semaphore`) y devuelve un array de resultados
- `backend/schemas/models.py` — schema `BatchGenerateRequest` con `stories: list[str]`, `model: str`, `context: str | None`, `temperature: float`; schema `BatchGenerateResponse` con `results: list[GenerateResponse]`
- `frontend/js/app.js` — al detectar `---` en el textarea, activar modo batch: mostrar indicador "Procesando historia 2 de 5...", llamar a `POST /generate/batch` con el array de historias separadas; al recibir respuesta consolidar los TC con prefijos de letra
- `frontend/index.html` — indicador de progreso para modo batch visible durante la generacion

**Criterios de aceptacion:**
- [ ] Si el textarea contiene al menos un `---`, el frontend activa el modo batch automaticamente
- [ ] El indicador de progreso muestra la historia actual y el total ("Procesando historia 2 de 5...")
- [ ] Los TC de cada historia tienen prefijo de letra (`A-TC-001`, `B-TC-001`, etc.)
- [ ] La vista final consolida todos los TC en una sola lista, con una seccion por historia
- [ ] Si una historia del lote falla, las demas se siguen procesando y el error se muestra junto a esa historia
- [ ] El modo batch respeta la configuracion de categorias de F-12 si esta activa

---

## Post-MVP — Futuro

| ID | Funcion | Razon del diferimiento |
|----|---------|------------------------|
| F-14 | Modo claro / oscuro con toggle | Valor bajo respecto al esfuerzo de mantener dos temas en CSS |
| F-15 | Comparador de dos generaciones | Requiere F-06 (historial) implementado y estabilizado primero |
| F-17 | Persistencia en SQLite | Introduce `aiosqlite`, migraciones y nueva capa de datos; riesgo alto para MVP |
| F-18 | Integracion con Jira / GitHub Issues | Requiere gestion de tokens, multi-tenant config y manejo de errores de APIs externas |
| F-19 | Evaluacion asincrona con polling | Requiere store de jobs en memoria o DB; amplifica complejidad del backend |
| F-20 | Tests de integracion CI contra Ollama real | Requiere runner con GPU o tiempo de pull de modelo; no critico hasta estabilizar la suite |

---

## Dependencias entre sprints

```
Sprint 1 (frontend puro)
  └─ No bloquea ni depende de ningun otro sprint

Sprint 2 (filtros + backend leve)
  ├─ F-16 es independiente de F-05 y F-13
  ├─ F-13 depende logicamente de F-05 (ambos tocan el estado de Ollama)
  └─ F-02 depende de que los TC renderizados tengan atributos data-; no depende de Sprint 1
       pero F-03 (Sprint 1) debe ser compatible con F-02 al implementarse

Sprint 3 (workspace persistente)
  └─ F-06 es prerequisito de F-15 (Post-MVP: comparador)

Sprint 4 (IA y calidad)
  ├─ F-09 no depende de ningun sprint anterior
  └─ F-10 no bloquea ni es bloqueado por F-09; pueden desarrollarse en paralelo

Sprint 5 (batch + configuracion)
  ├─ F-12 es recomendable antes de F-08 para que el batch respete la config de categorias
  └─ F-08 se beneficia de F-06 (Sprint 3) si se quiere guardar resultados batch en historial

Post-MVP
  ├─ F-15 requiere F-06 completado (Sprint 3)
  ├─ F-17 puede reemplazar la logica de F-06 si se implementa; coordinacion necesaria
  └─ F-19 es independiente pero se beneficia de F-17 (persistencia de jobs)
```

---

## Riesgos tecnicos por sprint

### Sprint 1

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| El `setInterval` de F-04 no se limpia en todos los flujos de error | Media | Bajo | Usar variable de closure y limpiar siempre en bloque `finally` |
| SheetJS no disponible aun en Sprint 1 (va en Sprint 3) | N/A | N/A | F-01 usa solo `Blob` nativo, sin dependencias externas |
| Los templates de F-11 pre-llenan el textarea pero el usuario no los ve como editables | Baja | Bajo | No usar `readonly` ni desactivar el textarea tras cargar un template |

### Sprint 2

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| `ollama.ps()` (F-13) no esta disponible en todas las versiones de Ollama | Media | Medio | Envolver en `try/except`, degradar silenciosamente si falla |
| El health-check extendido (F-05) aumenta la latencia del endpoint `/health` | Media | Bajo | Agregar timeout de 2s a la llamada a Ollama en el health-check |
| El slider de temperatura (F-16) recibe valores fuera de rango por manipulacion del DOM | Baja | Bajo | Validacion `ge=0.0, le=1.0` ya definida en el schema de Pydantic |
| Los chips de F-02 generados dinamicamente pueden producir duplicados si las categorias tienen variantes de nombre | Media | Medio | Normalizar `category.toLowerCase().replace(/ /g, '_')` antes de generar chips |

### Sprint 3

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| `localStorage` supera el limite de ~5MB con historial de 10 generaciones grandes | Media | Alto | Guardar solo `story_preview` (80 chars) y `tc_count` en el indice; el resultado completo solo si hay espacio; si falla, mostrar advertencia al usuario |
| SheetJS CDN no disponible en entornos offline (uso local) | Media | Medio | Documentar en README la posibilidad de servir SheetJS localmente desde `frontend/js/` |
| La hoja "Test Cases" del XLSX tiene pasos mal formateados si el LLM devuelve listas con formatos variables | Alta | Medio | Normalizar los pasos a array de strings en `downloadXLSX()` antes de escribir al sheet |

### Sprint 4

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| El endpoint `POST /regenerate-tc` devuelve JSON mal formado con mayor frecuencia que `/generate` (prompt mas corto = menos contexto) | Alta | Medio | Reutilizar la logica de reparacion de JSON existente en `main.py`; si falla el parse, devolver 422 con mensaje claro |
| Las metricas GEval de F-10 producen valores inconsistentes con el modelo local usado | Alta | Medio | Documentar que las metricas requieren un modelo con buen razonamiento; agregar nota en la UI si el score es < 0.3 |
| La evaluacion con las dos nuevas metricas duplica el tiempo de `POST /evaluate` | Media | Bajo | Las metricas son independientes; si el tiempo supera 120s, considerar devolverlas como campos opcionales con flag de activacion |

### Sprint 5

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| `POST /generate/batch` bloquea el semaforo `_llm_semaphore` durante toda la secuencia batch | Alta | Alto | Procesar cada historia del batch de forma secuencial liberando y reacquiriendo el semaforo entre llamadas |
| El prompt dinamico de F-12 con pocas categorias produce TC que ignoran las categorias seleccionadas | Alta | Medio | Incluir en el prompt dinamico instruccion explicita: "SOLO genera casos de las categorias: [lista]" y validar en el parseo |
| El frontend detecta `---` en el texto como separador batch cuando el usuario tiene `---` dentro de una historia (linea horizontal Markdown) | Media | Medio | Requerir `---` en linea propia con lineas en blanco antes y despues, o usar un separador menos ambiguo como `===` |

---

## Tabla de progreso

| ID | Nombre | Estado | Sprint | Notas |
|----|--------|--------|--------|-------|
| F-01 | Exportar a Markdown | ✅ Completado | Sprint 1 | `downloadMarkdown()` en `app.js` |
| F-02 | Filtrado por categoria y prioridad | ✅ Completado | Sprint 2 | `filterTC()` en `app.js`, chips dinamicos |
| F-03 | Busqueda por texto en TC | ✅ Completado | Sprint 1 | `searchTC()` en `app.js` |
| F-04 | Contador de tiempo de generacion | ✅ Completado | Sprint 1 | Timer integrado en streaming SSE |
| F-05 | Health-check con estado Ollama real | ✅ Completado | Sprint 2 | `GET /health` devuelve `ollama: true/false` |
| F-06 | Historial de sesiones con navegacion | ✅ Completado | Sprint 3 | `localStorage qaHistory` en `app.js` |
| F-07 | Exportar a XLSX por categoria | Pendiente | Sprint 3 | — |
| F-08 | Generacion por lotes | Pendiente | Sprint 5 | — |
| F-09 | Regenerar un TC individual | Pendiente | Sprint 4 | — |
| F-10 | Metricas adicionales en DeepEval | Pendiente | Sprint 4 | — |
| F-11 | Templates de historias predefinidas | ✅ Completado | Sprint 1 | Objeto `TEMPLATES` con 8 entradas en `app.js` |
| F-12 | Configuracion de categorias a incluir | Pendiente | Sprint 5 | — |
| F-13 | Indicador de carga del modelo Ollama | ✅ Completado | Sprint 2 | `GET /model-status` + badge en sidebar |
| F-14 | Modo claro / oscuro con toggle | Pendiente | Post-MVP | — |
| F-15 | Comparador de dos generaciones | Pendiente | Post-MVP | Requiere F-06 ✅ |
| F-16 | Ajuste de temperatura desde la UI | ✅ Completado | Sprint 2 | Slider en sidebar, incluido en POST body |
| F-17 | Persistencia en SQLite | Pendiente | Post-MVP | — |
| F-18 | Integracion con Jira / GitHub Issues | Pendiente | Post-MVP | — |
| F-19 | Evaluacion asincrona con polling | Pendiente | Post-MVP | — |
| F-20 | CI con tests de integracion contra Ollama real | Pendiente | Post-MVP | — |
| **A-01** | **Integracion Opik (trazas backend)** | **✅ Completado** | **Sprint Acad. 0** | `@opik.track` en `llm_service.py` |
| **A-02** | **Notebook Corte 1 (prototipo + evidencias)** | Pendiente | Sprint Acad. 0 | `notebooks/corte1_prototipo.ipynb` |
| **A-03** | **RAG Pipeline + ChromaDB** | Pendiente | Sprint Acad. 1 | `backend/services/rag_service.py` |
| **A-04** | **Agentes CrewAI (Generador + Revisor)** | Pendiente | Sprint Acad. 2 | `backend/services/agent_service.py` |
| **A-05** | **Experimento formal (8-15 casos + Corte 2)** | Pendiente | Sprint Acad. 3 | `notebooks/corte2_evaluacion.ipynb` |
