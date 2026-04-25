"""
DeepEval Metrics for QA Test Case Generator
Evaluates: Coverage, Relevancy, Consistency
"""

from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models.base_model import DeepEvalBaseLLM
import ollama
import json
import os
from typing import Generator, Optional

_DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


# ─────────────────────────────────────────────
# 1. Wrap Ollama as a DeepEval-compatible model
# ─────────────────────────────────────────────
class OllamaEvalModel(DeepEvalBaseLLM):
    def __init__(self, model_name: str = _DEFAULT_MODEL):
        self.model_name = model_name

    def load_model(self):
        return self.model_name

    def generate(self, prompt: str) -> str:
        response = ollama.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )
        return response["message"]["content"]

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

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
# 3. Main evaluation runner
# ─────────────────────────────────────────────
def evaluate_test_cases(
    user_story: str,
    generated_output: dict,
    model_name: str = _DEFAULT_MODEL,
) -> dict:
    """
    Runs DeepEval metrics on the generated test cases.
    Returns a dict with scores and verdicts.
    """
    eval_model = OllamaEvalModel(model_name)

    actual_output = json.dumps(generated_output, indent=2)

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

    results = {}

    for metric in metrics:
        try:
            metric.measure(test_case)
            results[metric.name] = {
                "score": round(metric.score, 3),
                "passed": metric.is_successful(),
                "threshold": metric.threshold,
                "reason": getattr(metric, "reason", "N/A"),
            }
        except Exception as e:
            results[metric.name] = {
                "score": 0.0,
                "passed": False,
                "threshold": 0.0,
                "reason": f"Evaluation error: {str(e)}",
            }

    overall = sum(r["score"] for r in results.values()) / len(results) if results else 0
    all_passed = all(r["passed"] for r in results.values())

    return {
        "metrics": results,
        "overall_score": round(overall, 3),
        "all_passed": all_passed,
        "model_used": f"ollama/{model_name}",
    }


# ─────────────────────────────────────────────
# 4. Streaming evaluation runner (yields one result per metric)
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
) -> Generator[dict, None, None]:
    """
    Same as evaluate_test_cases but yields each metric result as it completes.
    Yields dicts with keys: metric, name, score, passed, threshold, reason, step, total.
    Final yield: {"done": True, "overall": float}.
    """
    eval_model = OllamaEvalModel(model_name)
    actual_output = json.dumps(generated_output, indent=2)
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

    for step, factory in enumerate(factories, start=1):
        metric = factory(eval_model)
        try:
            metric.measure(test_case)
            score = round(metric.score, 3)
            passed = metric.is_successful()
            reason = getattr(metric, "reason", "N/A")
        except Exception as exc:
            score = 0.0
            passed = False
            reason = f"Error: {exc}"

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
        }

    overall = round(sum(scores) / len(scores), 3) if scores else 0.0
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
