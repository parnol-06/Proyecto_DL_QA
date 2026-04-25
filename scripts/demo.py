"""
Demo — QA Test Case Generator
Ejecutar desde la raíz del proyecto:
    python scripts/demo.py

Demuestra el pipeline completo:
  1. RAG: búsqueda semántica sobre corpus de buenas prácticas QA
  2. Agentes CrewAI: Generador → Revisor → Optimizador
  3. DeepEval: evaluación automática de 5 métricas
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

# ── Importaciones con manejo de errores ──────────────────────────────────────

try:
    from backend.schemas.models import AgentGenerateRequest
    from backend.services.agent_service import run_agent_pipeline
    from backend.services.rag_service import is_index_built, semantic_search
except ImportError as e:
    print(f"[ERROR] No se pudo importar el backend: {e}")
    print("        Asegúrate de ejecutar desde la raíz del proyecto con el venv activo.")
    sys.exit(1)

_DEEPEVAL_AVAILABLE = False
try:
    from evaluator.metrics import evaluate_test_cases as _run_deepeval
    _DEEPEVAL_AVAILABLE = True
except Exception:
    pass

# ── 3 User Stories de demostración ──────────────────────────────────────────

DEMO_STORIES = [
    {
        "id": "DEMO-01",
        "title": "Login con email y contraseña",
        "story": (
            "Como usuario registrado quiero iniciar sesión con mi email y contraseña "
            "para acceder a mi cuenta personal. El sistema debe bloquear la cuenta "
            "tras 3 intentos fallidos y enviar un correo de restablecimiento."
        ),
        "model": "llama3.2",
        "use_rag": True,
    },
    {
        "id": "DEMO-02",
        "title": "Proceso de pago con tarjeta",
        "story": (
            "Como cliente quiero pagar mi pedido con tarjeta de crédito/débito "
            "ingresando número, fecha de vencimiento y CVV para completar la compra. "
            "La transacción debe procesarse de forma segura con cifrado TLS."
        ),
        "model": "mistral",
        "use_rag": True,
    },
    {
        "id": "DEMO-03",
        "title": "API REST de gestión de tareas",
        "story": (
            "Como desarrollador quiero una API REST para crear, listar, actualizar y "
            "eliminar tareas con título, descripción, prioridad y fecha límite. "
            "Todos los endpoints deben requerir autenticación JWT y retornar JSON."
        ),
        "model": "llama3.2",
        "use_rag": False,
    },
]

# ── Helpers de presentación ───────────────────────────────────────────────────

SEP = "─" * 60

def _header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")

def _section(text: str):
    print(f"\n{SEP}")
    print(f"  {text}")
    print(SEP)

def _print_agent_trace(traces, optimizer_output: dict):
    print("\n  Trazas de agentes:")
    for t in traces:
        bar = "█" * min(int(t.elapsed_s / 5), 20)
        print(f"    [{t.agent:<12}] {t.elapsed_s:>6.1f}s  {bar}")
        print(f"    {'':14}  → {t.summary}")

    if optimizer_output and optimizer_output.get("priority_gaps"):
        print("\n  Brechas identificadas por el Optimizador:")
        for gap in optimizer_output["priority_gaps"]:
            impact_tag = "[ALTO]" if gap.get("impact") == "alto" else "[MEDIO]"
            print(f"    #{gap.get('rank','')} {impact_tag} {gap.get('category','')}: {gap.get('reason','')}")

def _print_deepeval(scores: dict):
    if not scores or "error" in scores:
        err = scores.get("error", "No disponible") if scores else "No disponible"
        print(f"\n  DeepEval: {err}")
        return
    print("\n  Métricas DeepEval:")
    metrics = [
        ("Cobertura",      scores.get("coverage", 0),    0.60),
        ("Relevancia",     scores.get("relevancy", 0),   0.70),
        ("Consistencia",   scores.get("consistency", 0), 0.65),
        ("Especificidad",  scores.get("specificity", 0), 0.60),
        ("Bal. No-Func.",  scores.get("nfb", 0),         0.55),
    ]
    for name, score, threshold in metrics:
        bar_len = int(score * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        status = "✓" if score >= threshold else "✗"
        print(f"    {status} {name:<16} [{bar}] {score:.2f}")
    overall = scores.get("overall", 0)
    print(f"\n    Overall: {overall:.3f}  ({'APROBADO' if scores.get('all_passed') else 'CON OBSERVACIONES'})")

def _print_tc_summary(test_cases: list):
    cats = {}
    for tc in test_cases:
        cat = tc.get("category", "unknown")
        cats[cat] = cats.get(cat, 0) + 1
    print(f"\n  Test cases generados: {len(test_cases)}")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    • {cat:<22} {count} casos")

# ── Pipeline principal ────────────────────────────────────────────────────────

async def run_demo_story(story_data: dict, idx: int, total: int) -> dict:
    _section(f"[{idx}/{total}] {story_data['id']} — {story_data['title']}")
    print(f"\n  Modelo: {story_data['model']}  |  RAG: {'Sí' if story_data['use_rag'] else 'No'}")
    print(f"  Historia: {story_data['story'][:100]}...")

    # RAG context preview
    if story_data["use_rag"]:
        if is_index_built():
            ctx = semantic_search(story_data["story"], k=2)
            print(f"\n  RAG: {len(ctx)} caracteres de contexto recuperados")
        else:
            print("\n  RAG: índice no construido — ejecuta 'python scripts/build_index.py'")

    req = AgentGenerateRequest(
        user_story=story_data["story"],
        model=story_data["model"],
        use_rag=story_data["use_rag"],
        temperature=0.25,
    )

    print("\n  Ejecutando pipeline de 3 agentes CrewAI...")
    t0 = time.monotonic()

    result = await run_agent_pipeline(req)

    elapsed = round(time.monotonic() - t0, 1)
    print(f"  Pipeline completado en {elapsed}s")

    _print_agent_trace(result.agent_trace, result.optimizer_output)
    _print_tc_summary(result.test_cases)

    # Evaluación DeepEval
    deepeval_scores = {}
    if _DEEPEVAL_AVAILABLE:
        print("\n  Evaluando con DeepEval (esto tarda ~30-90s)...")
        try:
            resp_dict = {
                "test_cases": result.test_cases,
                "edge_scenarios": result.edge_scenarios,
                "potential_bugs": result.potential_bugs,
                "coverage_summary": result.coverage_summary,
            }
            eval_result = _run_deepeval(
                user_story=story_data["story"],
                generated_output=resp_dict,
                model_name=story_data["model"],
            )
            deepeval_scores = {
                "overall":     round(eval_result.get("overall_score", 0.0), 3),
                "coverage":    round(eval_result.get("metrics", {}).get("Test Coverage", {}).get("score", 0.0), 3),
                "relevancy":   round(eval_result.get("metrics", {}).get("Test Relevancy", {}).get("score", 0.0), 3),
                "consistency": round(eval_result.get("metrics", {}).get("Test Consistency", {}).get("score", 0.0), 3),
                "specificity": round(eval_result.get("metrics", {}).get("Step Specificity", {}).get("score", 0.0), 3),
                "nfb":         round(eval_result.get("metrics", {}).get("Non-Functional Balance", {}).get("score", 0.0), 3),
                "all_passed":  eval_result.get("all_passed", False),
            }
        except Exception as e:
            deepeval_scores = {"error": str(e)[:80]}
    else:
        print("\n  DeepEval no disponible. Instala: pip install -r requirements-eval.txt")

    _print_deepeval(deepeval_scores)

    return {
        "id": story_data["id"],
        "title": story_data["title"],
        "model": story_data["model"],
        "use_rag": story_data["use_rag"],
        "tc_count": len(result.test_cases),
        "elapsed_s": elapsed,
        "used_fallback": result.used_fallback,
        "deepeval_scores": deepeval_scores,
    }


async def main():
    _header(f"QA Test Case Generator — Demo  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"\n  Historias de demostración: {len(DEMO_STORIES)}")
    print(f"  DeepEval: {'Activado' if _DEEPEVAL_AVAILABLE else 'No disponible (instala requirements-eval.txt)'}")
    print(f"  RAG index: {'Construido' if is_index_built() else 'No construido (ejecuta build_index.py)'}")

    results = []
    for i, story in enumerate(DEMO_STORIES, start=1):
        try:
            r = await run_demo_story(story, i, len(DEMO_STORIES))
            results.append(r)
        except Exception as e:
            print(f"\n  [ERROR] {story['id']}: {e}")
            results.append({"id": story["id"], "title": story["title"], "error": str(e)})

    # Resumen final
    _header("RESUMEN DE LA DEMOSTRACIÓN")
    ok = [r for r in results if "error" not in r]
    print(f"\n  Completadas: {len(ok)}/{len(results)}")
    if ok:
        avg_tc  = round(sum(r["tc_count"] for r in ok) / len(ok), 1)
        avg_t   = round(sum(r["elapsed_s"] for r in ok) / len(ok), 1)
        de_ok   = [r for r in ok if r.get("deepeval_scores") and "error" not in r["deepeval_scores"]]
        avg_de  = round(sum(r["deepeval_scores"]["overall"] for r in de_ok) / len(de_ok), 3) if de_ok else None

        print(f"  Promedio TCs generados: {avg_tc}")
        print(f"  Promedio tiempo/story:  {avg_t}s")
        if avg_de is not None:
            print(f"  DeepEval overall avg:   {avg_de}")

        print(f"\n  {'ID':<10} {'Título':<35} {'TCs':>4} {'Tiempo':>7} {'Overall':>8} {'Fallback':>9}")
        print(f"  {'-'*10} {'-'*35} {'-'*4} {'-'*7} {'-'*8} {'-'*9}")
        for r in results:
            if "error" in r:
                print(f"  {r['id']:<10} {r['title']:<35} {'ERROR':>4}")
                continue
            de_str = f"{r['deepeval_scores'].get('overall', 0):.3f}" if r.get("deepeval_scores") and "error" not in r["deepeval_scores"] else "  N/A"
            fb_str = "Sí" if r.get("used_fallback") else "No"
            print(f"  {r['id']:<10} {r['title']:<35} {r['tc_count']:>4} {r['elapsed_s']:>6.1f}s {de_str:>8} {fb_str:>9}")

    print(f"\n  Demo completada: {datetime.now().strftime('%H:%M:%S')}\n")


if __name__ == "__main__":
    asyncio.run(main())
