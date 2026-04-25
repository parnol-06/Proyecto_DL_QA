"""
Experimento comparativo: Configuración A (llama3.2 sin RAG) vs Configuración B (mistral con RAG).
Ejecutar desde la raíz:
    python scripts/run_experiment.py
Resultados en experiments/results.json
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from backend.schemas.models import GenerateRequest
from backend.services.llm_service import generate_test_cases

# DeepEval — evaluación automática de métricas
try:
    from evaluator.metrics import evaluate_test_cases as _run_deepeval
    _DEEPEVAL_AVAILABLE = True
except Exception as _de_err:
    _DEEPEVAL_AVAILABLE = False
    print(f"[AVISO] DeepEval no disponible: {_de_err}")

# Opik — trazabilidad del experimento
_OPIK_ENABLED = False
try:
    import opik
    _OPIK_API_KEY = os.getenv("OPIK_API_KEY", "")
    _OPIK_PROJECT = os.getenv("OPIK_PROJECT_NAME", "Qa_trace")
    _OPIK_WORKSPACE = os.getenv("OPIK_WORKSPACE", "")
    if _OPIK_API_KEY:
        opik.configure(api_key=_OPIK_API_KEY, workspace=_OPIK_WORKSPACE or None, force=True)
        _OPIK_ENABLED = True
except Exception:
    pass

USER_STORIES = [
    {
        "id": "US-01",
        "title": "Login con email y contraseña",
        "story": (
            "Como usuario registrado quiero iniciar sesión con mi email y contraseña "
            "para acceder a mi cuenta personal. El sistema debe bloquear la cuenta "
            "tras 3 intentos fallidos y enviar un correo de restablecimiento."
        ),
    },
    {
        "id": "US-02",
        "title": "Registro de nuevo usuario",
        "story": (
            "Como visitante quiero registrarme con nombre, email y contraseña "
            "para crear una cuenta. El email debe ser único y la contraseña tener "
            "mínimo 8 caracteres con mayúsculas, números y símbolos."
        ),
    },
    {
        "id": "US-03",
        "title": "Búsqueda de productos en e-commerce",
        "story": (
            "Como comprador quiero buscar productos por nombre, categoría o precio "
            "para encontrar lo que necesito. Los resultados deben cargarse en menos "
            "de 2 segundos y mostrarse paginados con 20 ítems por página."
        ),
    },
    {
        "id": "US-04",
        "title": "Agregar producto al carrito",
        "story": (
            "Como cliente quiero agregar productos al carrito de compras seleccionando "
            "cantidad y variante (talla/color) para comprarlos. El stock debe actualizarse "
            "en tiempo real y no permitir cantidades mayores al inventario disponible."
        ),
    },
    {
        "id": "US-05",
        "title": "Proceso de pago con tarjeta",
        "story": (
            "Como cliente quiero pagar mi pedido con tarjeta de crédito/débito "
            "ingresando número, fecha de vencimiento y CVV para completar la compra. "
            "La transacción debe procesarse de forma segura con cifrado TLS."
        ),
    },
    {
        "id": "US-06",
        "title": "Recuperación de contraseña olvidada",
        "story": (
            "Como usuario que olvidó su contraseña quiero solicitar un enlace de "
            "restablecimiento a mi email para recuperar acceso a mi cuenta. "
            "El enlace debe expirar en 24 horas y solo puede usarse una vez."
        ),
    },
    {
        "id": "US-07",
        "title": "Carga de archivos a la nube",
        "story": (
            "Como usuario quiero subir documentos PDF e imágenes JPG/PNG de hasta 10 MB "
            "a mi espacio en la nube para almacenarlos y compartirlos. El sistema debe "
            "mostrar progreso de carga y notificar si el archivo supera el límite."
        ),
    },
    {
        "id": "US-08",
        "title": "API REST de gestión de tareas",
        "story": (
            "Como desarrollador quiero una API REST para crear, listar, actualizar y "
            "eliminar tareas con título, descripción, prioridad y fecha límite. "
            "Todos los endpoints deben requerir autenticación JWT y retornar JSON."
        ),
    },
    {
        "id": "US-09",
        "title": "Notificaciones push en móvil",
        "story": (
            "Como usuario móvil quiero recibir notificaciones push cuando ocurran "
            "eventos importantes en mi cuenta para estar informado sin abrir la app. "
            "Debo poder desactivar notificaciones por categoría desde ajustes."
        ),
    },
    {
        "id": "US-10",
        "title": "Dashboard de métricas en tiempo real",
        "story": (
            "Como administrador quiero ver un dashboard con métricas de uso en tiempo real "
            "(usuarios activos, transacciones por minuto, tasa de errores) para monitorear "
            "la salud del sistema. Los datos deben actualizarse cada 5 segundos."
        ),
    },
]

CONFIGS = [
    {
        "name": "Config-A",
        "description": "llama3.2 sin RAG",
        "model": "llama3.2",
        "use_rag": False,
        "temperature": 0.25,
    },
    {
        "name": "Config-B",
        "description": "mistral con RAG",
        "model": "mistral",
        "use_rag": True,
        "temperature": 0.25,
    },
]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "experiments")
RESULTS_FILE = os.path.join(RESULTS_DIR, "results.json")


def _count_categories(test_cases: list) -> dict:
    cats = {}
    for tc in test_cases:
        cat = tc.get("category", "unknown")
        cats[cat] = cats.get(cat, 0) + 1
    return cats


async def run_single(story_id: str, story_text: str, cfg: dict) -> dict:
    # a) Iniciar traza Opik
    opik_trace = None
    if _OPIK_ENABLED:
        try:
            _client = opik.Opik()
            opik_trace = _client.trace(
                name=f"exp_{cfg['name']}_{story_id}",
                input={
                    "story_id": story_id,
                    "config": cfg["name"],
                    "model": cfg["model"],
                    "use_rag": cfg["use_rag"],
                    "user_story": story_text[:200],
                },
                project_name=_OPIK_PROJECT,
            )
        except Exception:
            pass

    req = GenerateRequest(
        user_story=story_text,
        model=cfg["model"],
        context="",
        temperature=cfg["temperature"],
        use_rag=cfg["use_rag"],
    )
    t0 = time.monotonic()
    tc_list = []
    resp = None
    try:
        resp = await generate_test_cases(req)
        elapsed = round(time.monotonic() - t0, 2)
        tc_list = resp.test_cases if isinstance(resp.test_cases, list) else []
        result = {
            "story_id": story_id,
            "config": cfg["name"],
            "status": "ok",
            "elapsed_s": elapsed,
            "tc_count": len(tc_list),
            "categories": _count_categories(tc_list),
            "coverage_summary": resp.coverage_summary if isinstance(resp.coverage_summary, dict) else {},
            "raw_tc": tc_list[:3],
        }
    except Exception as exc:
        elapsed = round(time.monotonic() - t0, 2)
        result = {
            "story_id": story_id,
            "config": cfg["name"],
            "status": "error",
            "elapsed_s": elapsed,
            "error": str(exc),
            "tc_count": 0,
            "categories": {},
            "coverage_summary": {},
            "raw_tc": [],
        }

    # b) Evaluación DeepEval (solo si la generación fue exitosa)
    deepeval_scores = {}
    if result["status"] == "ok" and _DEEPEVAL_AVAILABLE:
        try:
            resp_dict = {
                "test_cases": tc_list,
                "edge_scenarios": resp.edge_scenarios if isinstance(resp.edge_scenarios, list) else [],
                "potential_bugs": resp.potential_bugs if isinstance(resp.potential_bugs, list) else [],
                "coverage_summary": resp.coverage_summary if isinstance(resp.coverage_summary, dict) else {},
            }
            eval_result = _run_deepeval(
                user_story=story_text,
                generated_output=resp_dict,
                model_name=cfg["model"],
            )
            deepeval_scores = {
                "overall": round(eval_result.get("overall_score", 0.0), 3),
                "coverage": round(eval_result.get("metrics", {}).get("Test Coverage", {}).get("score", 0.0), 3),
                "relevancy": round(eval_result.get("metrics", {}).get("Test Relevancy", {}).get("score", 0.0), 3),
                "consistency": round(eval_result.get("metrics", {}).get("Test Consistency", {}).get("score", 0.0), 3),
                "specificity": round(eval_result.get("metrics", {}).get("Step Specificity", {}).get("score", 0.0), 3),
                "nfb": round(eval_result.get("metrics", {}).get("Non-Functional Balance", {}).get("score", 0.0), 3),
                "all_passed": eval_result.get("all_passed", False),
            }
            result["deepeval_scores"] = deepeval_scores
            print(f" | DeepEval overall={deepeval_scores['overall']:.2f}", end="")
        except Exception as eval_exc:
            result["deepeval_scores"] = {"error": str(eval_exc)}
            print(f" | DeepEval ERROR: {str(eval_exc)[:40]}", end="")
    else:
        result["deepeval_scores"] = {}

    # c) Cerrar traza Opik
    if opik_trace:
        try:
            opik_trace.end(output={
                "story_id": story_id,
                "config": cfg["name"],
                "tc_count": result.get("tc_count", 0),
                "elapsed_s": result.get("elapsed_s", 0),
                "deepeval_overall": deepeval_scores.get("overall", 0.0),
                "deepeval_coverage": deepeval_scores.get("coverage", 0.0),
                "deepeval_relevancy": deepeval_scores.get("relevancy", 0.0),
                "status": result.get("status", "error"),
            })
        except Exception:
            pass

    return result


async def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("=" * 60)
    print("  Experimento Comparativo — QA Test Case Generator")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"\nHistorias de usuario: {len(USER_STORIES)}")
    print(f"Configuraciones:      {len(CONFIGS)}")
    print(f"Total ejecuciones:    {len(USER_STORIES) * len(CONFIGS)}\n")

    if _DEEPEVAL_AVAILABLE:
        print(f"[AVISO] DeepEval activado — cada evaluación tarda ~30-90s.")
        print(f"        Tiempo estimado total: {len(USER_STORIES) * len(CONFIGS) * 2} - {len(USER_STORIES) * len(CONFIGS) * 4} minutos")
        print(f"        Para desactivar: comentar 'from evaluator.metrics import ...' al inicio del script")
    else:
        print(f"[AVISO] DeepEval no disponible — solo se generarán TCs sin evaluación.")
        print(f"        Instalar: pip install -r requirements-eval.txt")

    all_results = []
    summary_by_config: dict[str, list] = {cfg["name"]: [] for cfg in CONFIGS}

    for cfg in CONFIGS:
        print(f"\n{'─'*50}")
        print(f"  {cfg['name']}: {cfg['description']}")
        print(f"{'─'*50}")

        for us in USER_STORIES:
            print(f"  [{us['id']}] {us['title']} ... ", end="", flush=True)
            result = await run_single(us["id"], us["story"], cfg)
            all_results.append(result)
            summary_by_config[cfg["name"]].append(result)

            if result["status"] == "ok":
                print(f"✓  {result['tc_count']} casos | {result['elapsed_s']}s")
            else:
                print(f"✗  ERROR: {result.get('error', '')[:60]}")

    # Estadísticas por configuración
    stats = {}
    for cfg_name, results in summary_by_config.items():
        ok = [r for r in results if r["status"] == "ok"]
        stats[cfg_name] = {
            "total_runs": len(results),
            "successful": len(ok),
            "avg_tc_count": round(sum(r["tc_count"] for r in ok) / len(ok), 1) if ok else 0,
            "avg_elapsed_s": round(sum(r["elapsed_s"] for r in ok) / len(ok), 2) if ok else 0,
            "total_categories": {},
        }
        for r in ok:
            for cat, cnt in r["categories"].items():
                d = stats[cfg_name]["total_categories"]
                d[cat] = d.get(cat, 0) + cnt

        # Calcular promedios DeepEval
        de_keys = ["overall", "coverage", "relevancy", "consistency", "specificity", "nfb"]
        de_ok = [r for r in ok if r.get("deepeval_scores") and "error" not in r["deepeval_scores"]]
        de_avgs = {}
        for key in de_keys:
            vals = [r["deepeval_scores"].get(key, 0.0) for r in de_ok if r["deepeval_scores"].get(key) is not None]
            de_avgs[f"avg_deepeval_{key}"] = round(sum(vals) / len(vals), 3) if vals else 0.0

        stats[cfg_name].update(de_avgs)
        stats[cfg_name]["deepeval_evaluated"] = len(de_ok)

    output = {
        "experiment_date": datetime.now().isoformat(),
        "configs": CONFIGS,
        "user_stories": [{"id": us["id"], "title": us["title"]} for us in USER_STORIES],
        "results": all_results,
        "stats_by_config": stats,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("  RESUMEN ESTADÍSTICO")
    print(f"{'='*60}")
    for cfg_name, s in stats.items():
        desc = next(c["description"] for c in CONFIGS if c["name"] == cfg_name)
        print(f"\n  {cfg_name} ({desc})")
        print(f"    Exitosos:        {s['successful']}/{s['total_runs']}")
        print(f"    Prom. TC:        {s['avg_tc_count']}")
        print(f"    Prom. tiempo:    {s['avg_elapsed_s']}s")
        cats = sorted(s["total_categories"].items(), key=lambda x: -x[1])
        print(f"    Categorías top: {cats[:5]}")
        de = {k: v for k, v in s.items() if k.startswith("avg_deepeval")}
        if de:
            print(f"    DeepEval overall:    {de.get('avg_deepeval_overall', 0):.3f}")
            print(f"    DeepEval coverage:   {de.get('avg_deepeval_coverage', 0):.3f}")
            print(f"    DeepEval relevancy:  {de.get('avg_deepeval_relevancy', 0):.3f}")
            print(f"    DeepEval evaluated:  {s.get('deepeval_evaluated', 0)}/{s['total_runs']}")

    print(f"\n  Resultados guardados en: {RESULTS_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
