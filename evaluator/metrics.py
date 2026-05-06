"""
DeepEval Metrics for QA Test Case Generator
Evaluates: Coverage, Relevancy, Consistency, Step Specificity, Non-Functional Balance
"""

import os
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPEVAL_ERROR_REPORTING_OPT_OUT", "YES")

from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models.base_model import DeepEvalBaseLLM
import json
import logging
import math
import re
import time
from typing import Generator, Optional

import ollama

logger = logging.getLogger(__name__)


def _measure_metric(metric, test_case) -> tuple[float, bool, str, float]:
    """
    Run metric.measure() and return (score, passed, reason, elapsed_ms).
    Logs start/end/failure for every metric invocation.
    """
    name = metric.name
    t0 = time.perf_counter()
    logger.debug("metric started", extra={"event": "metric_start", "metric": name})

    try:
        metric.measure(test_case)
        score: float = round(metric.score, 3)
        passed: bool = metric.is_successful()
        reason: str = getattr(metric, "reason", "N/A") or "N/A"
        elapsed = round((time.perf_counter() - t0) * 1000)

        # Detect anomalous scores
        if score is None or (isinstance(score, float) and math.isnan(score)):
            logger.error(
                "metric returned invalid score",
                extra={
                    "event": "metric_invalid_score",
                    "metric": name,
                    "score": str(score),
                    "elapsed_ms": elapsed,
                },
            )
            return 0.0, False, "Invalid score (NaN/None)", elapsed

        level = logging.INFO if passed else logging.WARNING
        logger.log(
            level,
            "metric completed",
            extra={
                "event": "metric_done",
                "metric": name,
                "score": score,
                "threshold": metric.threshold,
                "passed": passed,
                "reason": reason[:200] if reason else "N/A",
                "elapsed_ms": elapsed,
            },
        )
        return score, passed, reason, elapsed

    except Exception as exc:
        elapsed = round((time.perf_counter() - t0) * 1000)
        logger.error(
            "metric execution error",
            exc_info=True,
            extra={
                "event": "metric_error",
                "metric": name,
                "error": str(exc),
                "elapsed_ms": elapsed,
            },
        )
        return 0.0, False, f"Error: {exc}", elapsed

_DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
_EVAL_MODEL    = os.getenv("OLLAMA_EVAL_MODEL", "llama3.2")


# ─────────────────────────────────────────────
# 1. JSON output cleaner
# ─────────────────────────────────────────────
def _clean_json_output(text: str) -> str:
    """
    Extract the first valid JSON object from noisy LLM output.
    Handles: markdown code fences, leading/trailing prose, multiple blocks.
    Called on every model response before DeepEval parses it.
    """
    if not text:
        return text
    text = text.strip()

    # Fast path — already valid JSON
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Strip ```json { ... } ``` or ``` { ... } ``` markdown fences
    md = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if md:
        candidate = md.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Walk the string to extract the first balanced { } block
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        try:
                            from json_repair import repair_json
                            repaired = repair_json(candidate)
                            if isinstance(repaired, str) and repaired:
                                json.loads(repaired)  # validate before returning
                                return repaired
                        except Exception:
                            pass
                    break  # first block tried — don't scan further

    return text  # fallback: return as-is, let DeepEval surface the error


# ─────────────────────────────────────────────
# 2. Wrap Ollama as a DeepEval-compatible model
# ─────────────────────────────────────────────
class OllamaEvalModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str = _DEFAULT_MODEL):
        self.model_name = model_name

    def load_model(self):
        return self.model_name

    def _raw_call(self, prompt: str) -> str:
        """Single contact point with Ollama; always returns cleaned output."""
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )
        return _clean_json_output(response["message"]["content"])

    # ── Old DeepEval interface (still called by some metric internals) ──
    def generate(self, prompt: str, **kwargs) -> str:
        return self._raw_call(prompt)

    async def a_generate(self, prompt: str, **kwargs) -> str:
        return self._raw_call(prompt)

    # ── New DeepEval interface (required by versions that call *_raw_response) ──
    def generate_raw_response(self, prompt: str, **kwargs) -> str:
        return self._raw_call(prompt)

    async def a_generate_raw_response(self, prompt: str, **kwargs) -> str:
        return self._raw_call(prompt)

    def get_model_name(self) -> str:
        return f"ollama/{self.model_name}"


# ─────────────────────────────────────────────
# 2. Custom G-Eval Metrics
# ─────────────────────────────────────────────
def make_coverage_metric(model: DeepEvalBaseLLM) -> GEval:
    """Does the output cover the key scenarios from the requirement?"""
    return GEval(
        name="Test Coverage",
        criteria="""Evaluate if the generated test cases provide comprehensive coverage of the user story.
        Consider:
        - Happy path scenarios are included
        - Negative/error scenarios are covered  
        - Edge cases relevant to the requirement are identified
        - Security and performance considerations are mentioned if applicable
        Score 1-10, where 10 means excellent coverage of all scenarios.""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.6,
    )


def make_relevancy_metric(model: DeepEvalBaseLLM) -> GEval:
    """Are the test cases relevant to the actual requirement?"""
    return GEval(
        name="Test Relevancy",
        criteria="""Evaluate if ALL generated test cases, edge scenarios, and bug reports are 
        directly relevant to the input user story.
        Penalize if:
        - Test cases describe unrelated functionality
        - Edge scenarios are generic and not specific to the requirement
        - Potential bugs have no connection to the described feature
        Score 1-10, where 10 means every item is highly relevant.""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.7,
    )


def make_consistency_metric(model: DeepEvalBaseLLM) -> GEval:
    """Are the test cases internally consistent and well-structured?"""
    return GEval(
        name="Test Consistency",
        criteria="""Evaluate the internal consistency and quality of the generated test cases.
        Check:
        - Steps logically lead to the expected result
        - Preconditions are appropriate for each test case
        - Priority levels are correctly assigned (critical flows = high priority)
        - Test IDs follow a consistent format
        - No contradictions between test cases
        Score 1-10, where 10 means fully consistent and professionally structured.""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.65,
    )


def make_specificity_metric(model: DeepEvalBaseLLM) -> GEval:
    """¿Los pasos de los test cases son específicos o genéricos?"""
    return GEval(
        name="Step Specificity",
        criteria="""Evalúa si los pasos de cada caso de prueba son específicos y accionables.
        Penaliza pasos genéricos como 'Ir a la página', 'Hacer clic en el botón', 'Verificar el resultado'.
        Premia pasos que incluyen: datos concretos (valores, URLs, credenciales de prueba),
        acciones precisas (campo exacto, botón nombrado), y condiciones medibles en el resultado esperado.
        Puntúa 1-10, donde 10 es completamente específico y libre de pasos genéricos.""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.6,
    )


def make_nonfunctional_balance_metric(model: DeepEvalBaseLLM) -> GEval:
    """¿Hay un balance adecuado entre casos funcionales y no funcionales?"""
    return GEval(
        name="Non-Functional Balance",
        criteria="""Evalúa si la suite de casos de prueba incluye un balance adecuado entre:
        - Pruebas funcionales (happy_path, negativo, caso_limite)
        - Pruebas no funcionales (rendimiento con métricas numéricas, seguridad con vector de ataque,
          usabilidad con criterios de UX, compatibilidad con dispositivos/browsers)
        Penaliza si los casos no funcionales tienen criterios vagos sin valores cuantitativos.
        Puntúa 1-10, donde 10 significa ≥30% no funcionales con criterios medibles.""",
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.55,
    )


# ─────────────────────────────────────────────
# 3. Validación estructural del output
# ─────────────────────────────────────────────
def _validate_generated_output(output: dict) -> dict:
    """Valida estructura mínima antes de evaluar. Lanza ValueError si falta algo crítico."""
    if not isinstance(output, dict):
        msg = f"generated_output debe ser dict, recibido: {type(output)}"
        logger.error("output validation failed", extra={"event": "validation_error", "reason": msg})
        raise ValueError(msg)
    test_cases = output.get("test_cases", [])
    if not isinstance(test_cases, list) or len(test_cases) == 0:
        msg = "generated_output debe tener al menos un test_case en 'test_cases'"
        logger.error("output validation failed", extra={"event": "validation_error", "reason": msg})
        raise ValueError(msg)
    required = {"id", "title", "category", "steps", "expected_result"}
    missing = required - set(test_cases[0].keys())
    if missing:
        msg = f"test_cases[0] falta campos requeridos: {missing}"
        logger.error("output validation failed", extra={"event": "validation_error", "reason": msg, "missing_fields": sorted(missing)})
        raise ValueError(msg)
    logger.debug(
        "output validation passed",
        extra={"event": "validation_ok", "test_case_count": len(test_cases)},
    )
    return output


# ─────────────────────────────────────────────
# 4. Main evaluation runner
# ─────────────────────────────────────────────
def evaluate_test_cases(
    user_story: str,
    generated_output: dict,
    model_name: str = _DEFAULT_MODEL,
    eval_model_name: str | None = None,
) -> dict:
    """
    Runs DeepEval metrics on the generated test cases.
    Uses eval_model_name (default: OLLAMA_EVAL_MODEL) for evaluation to avoid self-evaluation bias.
    Returns a dict with scores and verdicts.
    """
    validated = _validate_generated_output(generated_output)
    effective_eval = eval_model_name or _EVAL_MODEL
    if effective_eval == model_name:
        logger.warning(
            "El modelo de evaluación (%s) coincide con el de generación — posible sesgo de auto-evaluación",
            model_name,
        )
    eval_model = OllamaEvalModel(effective_eval)

    actual_output = json.dumps(validated, indent=2)

    test_case = LLMTestCase(
        input=user_story,
        actual_output=actual_output,
    )

    metrics = [
        make_coverage_metric(eval_model),
        make_relevancy_metric(eval_model),
        make_consistency_metric(eval_model),
        make_specificity_metric(eval_model),
        make_nonfunctional_balance_metric(eval_model),
    ]

    logger.info(
        "deepeval run started",
        extra={
            "event": "deepeval_start",
            "eval_model": effective_eval,
            "generation_model": model_name,
            "metric_count": len(metrics),
            "test_case_count": len(validated.get("test_cases", [])),
        },
    )
    t_run = time.perf_counter()
    results = {}

    for metric in metrics:
        score, passed, reason, elapsed_ms = _measure_metric(metric, test_case)
        results[metric.name] = {
            "score": score,
            "passed": passed,
            "threshold": metric.threshold,
            "reason": reason,
            "elapsed_ms": elapsed_ms,
        }

    total_ms = round((time.perf_counter() - t_run) * 1000)
    overall = sum(r["score"] for r in results.values()) / len(results) if results else 0
    all_passed = all(r["passed"] for r in results.values())

    logger.info(
        "deepeval run completed",
        extra={
            "event": "deepeval_done",
            "overall_score": round(overall, 3),
            "all_passed": all_passed,
            "duration_ms": total_ms,
            "per_metric": {k: {"score": v["score"], "passed": v["passed"]} for k, v in results.items()},
        },
    )

    return {
        "metrics": results,
        "overall_score": round(overall, 3),
        "all_passed": all_passed,
        "model_used": f"ollama/{effective_eval}",
    }


# ─────────────────────────────────────────────
# 5. Streaming evaluation runner (yields one result per metric)
# ─────────────────────────────────────────────
_METRIC_KEY_MAP = {
    "Test Coverage":         "coverage",
    "Test Relevancy":        "relevancy",
    "Test Consistency":      "consistency",
    "Step Specificity":      "specificity",
    "Non-Functional Balance": "nonfunctional_balance",
}

def stream_evaluate_test_cases(
    user_story: str,
    generated_output: dict,
    model_name: str = _DEFAULT_MODEL,
    eval_model_name: str | None = None,
) -> Generator[dict, None, None]:
    """
    Same as evaluate_test_cases but yields each metric result as it completes.
    Uses eval_model_name (default: OLLAMA_EVAL_MODEL) to avoid self-evaluation bias.
    Yields dicts with keys: metric, name, score, passed, threshold, reason, step, total.
    Final yield: {"done": True, "overall": float}.
    """
    validated = _validate_generated_output(generated_output)
    effective_eval = eval_model_name or _EVAL_MODEL
    eval_model = OllamaEvalModel(effective_eval)
    actual_output = json.dumps(validated, indent=2)
    test_case = LLMTestCase(input=user_story, actual_output=actual_output)

    factories = [
        make_coverage_metric,
        make_relevancy_metric,
        make_consistency_metric,
        make_specificity_metric,
        make_nonfunctional_balance_metric,
    ]
    total = len(factories)
    scores = []

    logger.info(
        "deepeval stream started",
        extra={
            "event": "deepeval_stream_start",
            "eval_model": effective_eval,
            "metric_count": total,
        },
    )
    t_stream = time.perf_counter()

    for step, factory in enumerate(factories, start=1):
        metric = factory(eval_model)
        score, passed, reason, elapsed_ms = _measure_metric(metric, test_case)
        scores.append(score)
        yield {
            "metric": _METRIC_KEY_MAP.get(metric.name, metric.name.lower()),
            "name": metric.name,
            "score": score,
            "passed": passed,
            "threshold": metric.threshold,
            "reason": reason,
            "step": step,
            "total": total,
            "elapsed_ms": elapsed_ms,
        }

    overall = round(sum(scores) / len(scores), 3) if scores else 0.0
    total_ms = round((time.perf_counter() - t_stream) * 1000)
    logger.info(
        "deepeval stream completed",
        extra={
            "event": "deepeval_stream_done",
            "overall_score": overall,
            "duration_ms": total_ms,
        },
    )
    yield {"done": True, "overall": overall}


# ─────────────────────────────────────────────
# 5. CLI runner for standalone testing
# ─────────────────────────────────────────────
if __name__ == "__main__":
    sample_story = """
    As a user, I want to log in to the application using my email and password,
    so that I can access my personal dashboard. The system should lock the account
    after 3 failed attempts and send a password reset email.
    """

    sample_output = {
        "test_cases": [
            {
                "id": "TC-001",
                "title": "Successful login with valid credentials",
                "category": "happy_path",
                "priority": "high",
                "preconditions": ["User has a registered account", "Account is not locked"],
                "steps": ["Navigate to login page", "Enter valid email", "Enter valid password", "Click Login"],
                "expected_result": "User is redirected to personal dashboard",
                "test_type": "functional",
            }
        ],
        "edge_scenarios": [],
        "potential_bugs": [],
        "coverage_summary": {
            "total_test_cases": 1,
            "categories_covered": ["happy_path"],
            "estimated_coverage_percent": 20,
            "missing_areas": ["account lockout", "password reset flow"],
        },
    }

    print("Running DeepEval metrics...\n")
    results = evaluate_test_cases(sample_story, sample_output)
    print(json.dumps(results, indent=2))
