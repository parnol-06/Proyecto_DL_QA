# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Descripción del Proyecto

Generador local de casos de prueba impulsado por IA. Toma historias de usuario/requisitos y produce 12-15+ casos de prueba estructurados en español, cubriendo 7 categorías (happy path, edge cases, negativo, seguridad, rendimiento, usabilidad, compatibilidad), junto con escenarios borde, bugs potenciales y métricas de cobertura.

**Stack**: FastAPI + Uvicorn (backend), Ollama (LLM local), DeepEval/GEval (evaluación), HTML/CSS/JS vanilla (frontend).

## Comandos

### Configuración inicial
```bash
# Instalar Ollama desde https://ollama.ai, luego descargar un modelo
ollama pull llama3.2

# Instalar dependencias Python
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Ejecutar la aplicación
```bash
cd backend
uvicorn main:app --reload --port 8000
# Abrir http://localhost:8000
```

### Ejecutar el evaluador standalone
```bash
cd evaluator
python metrics.py
```

## Arquitectura

### Estructura de archivos clave
- `backend/main.py` — Toda la lógica backend: app FastAPI, rutas, prompt del sistema, parseo JSON, servicio de archivos estáticos
- `frontend/index.html` — SPA completa (774 líneas): layout, JS, CSS en un solo archivo
- `evaluator/metrics.py` — Wrapper `OllamaEvalModel` sobre DeepEval; métricas GEval (Coverage/Relevancy/Consistency)

### Flujo de datos
1. Frontend envía `POST /generate` con `{requirement, model, context}`
2. `main.py` construye el prompt del sistema (líneas 26-79) y llama a Ollama con temperatura 0.25
3. Respuesta JSON del LLM se parsea y repara con regex si es necesario
4. Frontend renderiza tabs: Casos de Prueba, Escenarios Borde, Bugs, Cobertura

### Decisiones de diseño importantes
- **Sin base de datos**: La API es completamente stateless; no hay persistencia
- **Sin autenticación**: Diseñado exclusivamente para uso local
- **Temperatura 0.25**: Baja creatividad para maximizar consistencia en el output
- **Reparación de JSON**: `main.py` incluye lógica de fallback con regex para corregir JSON mal formado del LLM
- **Métricas mock en frontend**: La cobertura mostrada en UI se calcula localmente; las métricas reales de DeepEval solo corren en `evaluator/metrics.py`

### Prompt del sistema (crítico)
El comportamiento del LLM está controlado por 9 instrucciones obligatorias en `main.py` líneas 26-79. Cualquier cambio en categorías, idioma, o formato de output debe modificarse ahí.

### API endpoints
| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/generate` | Genera casos de prueba |
| `GET` | `/models` | Lista modelos Ollama disponibles |
| `GET` | `/health` | Health check |
| `GET` | `/` | Sirve `frontend/index.html` |
