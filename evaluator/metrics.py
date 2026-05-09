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
import sys
import time
from contextlib import contextmanager
from typing import Generator, Optional, Tuple

import ollama

logger = logging.getLogger(__name__)

# ── Optional tracer import (no-ops when backend package is unavailable) ───────
try:
    from backend.observability import tracer as _tracer
    _TRACER_AVAILABLE = True
except Exception:
    _tracer = None  # type: ignore[assignment]
    _TRACER_AVAILABLE = False

# ── @opik_track facade (matches reference pattern) ────────────────────────────
try:
    from opik import track as _opik_track
except ImportError:
    def _opik_track(name=None, **kw):  # type: ignore[misc]
        def _dec(fn):
            return fn
        return _dec


@contextmanager
def _noop_ctx():
    """Fallback context manager used when the Opik tracer is unavailable."""
    yield None


def _measure_metric(metric, test_case) -> tuple[float, bool, str, float]:
    """
    Run metric.measure() and return (score, passed, reason, elapsed_ms).
    Creates an Opik child span for each metric when the tracer is available.
    """
    name = metric.name
    eval_model_name = getattr(metric, "model", None)
    eval_model_str = (
        eval_model_name.get_model_name()
        if hasattr(eval_model_name, "get_model_name")
        else str(eval_model_name or "unknown")
    )

    logger.debug("metric started", extra={"event": "metric_start", "metric": name})

    # Open a per-metric span; context manager is a no-op when tracer is unavailable.
    span_ctx = (
        _tracer.metric_span(name, metric.threshold, eval_model_str)
        if _TRACER_AVAILABLE
        else _noop_ctx()
    )

    with span_ctx as s:
        t0 = time.perf_counter()
        try:
            metric.measure(test_case)
            score: float = round(metric.score, 3)
            passed: bool = metric.is_successful()
            reason: str = getattr(metric, "reason", "N/A") or "N/A"
            elapsed = round((time.perf_counter() - t0) * 1000)

            if score is None or (isinstance(score, float) and math.isnan(score)):
                logger.error(
                    "metric returned invalid score",
                    extra={"event": "metric_invalid_score", "metric": name,
                           "score": str(score), "elapsed_ms": elapsed},
                )
                if _TRACER_AVAILABLE:
                    _tracer.update_span(s, output={"score": 0.0, "passed": False},
                                        metadata={"error": "invalid_score"})
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
            if _TRACER_AVAILABLE:
                _tracer.update_span(
                    s,
                    output={"score": score, "passed": passed, "reason": reason[:300]},
                    metadata={"threshold": metric.threshold, "elapsed_ms": elapsed},
                )
                score_key = name.lower().replace(" ", "_").replace("-", "_")
                _tracer.log_feedback_score(
                    s, score_key, score, "deepeval_metric",
                    reason=reason[:200] if reason else None,
                )
            return score, passed, reason, elapsed

        except Exception as exc:
            elapsed = round((time.perf_counter() - t0) * 1000)
            logger.error(
                "metric execution error",
                exc_info=True,
                extra={"event": "metric_error", "metric": name,
                       "error": str(exc), "elapsed_ms": elapsed},
            )
            if _TRACER_AVAILABLE:
                _tracer.update_span(s, output={"score": 0.0, "passed": False},
                                    metadata={"error": str(exc)[:200], "elapsed_ms": elapsed})
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
        raw = response["message"]["content"]
        logger.debug(
            "ollama raw response",
            extra={"model": self.model_name, "raw_length": len(raw), "raw_preview": raw[:300]},
        )
        return _clean_json_output(raw)

    # ── Old DeepEval interface (still called by some metric internals) ──
    def generate(self, prompt: str, **kwargs) -> str:
        return self._raw_call(prompt)

    async def a_generate(self, prompt: str, **kwargs) -> str:
        return self._raw_call(prompt)

    # ── New DeepEval interface (required by versions that call *_raw_response) ──
    def generate_raw_response(self, prompt: str, **kwargs) -> Tuple[str, float]:
        text = self._raw_call(prompt)
        logger.debug("generate_raw_response", extra={"length": len(text), "preview": text[:120]})
        return text, 0.0

    async def a_generate_raw_response(self, prompt: str, **kwargs) -> Tuple[str, float]:
        text = self._raw_call(prompt)
        logger.debug("a_generate_raw_response", extra={"length": len(text), "preview": text[:120]})
        return text, 0.0

    def get_model_name(self) -> str:
        return f"ollama/{self.model_name}"


# ─────────────────────────────────────────────
# 2. Custom G-Eval Metrics
#
# Design rules for local models (llama3.2:8b / mistral):
#  - Use evaluation_steps (not criteria) so GEval skips its steps-generation
#    LLM call and goes straight to scoring — one call instead of two.
#  - Never mention a scoring scale in steps; GEval's template already asks
#    for a float in [0, 1]. Mixing scales produces ~0.2 scores.
#  - Keep each step short and binary so small models can follow it.
# ─────────────────────────────────────────────
def make_coverage_metric(model: DeepEvalBaseLLM) -> GEval:
    """Does the output cover the key scenarios from the requirement?"""
    return GEval(
        name="Test Coverage",
        evaluation_steps=[
            "Check whether the test suite includes at least one happy-path scenario that validates the core feature described in the input.",
            "Check whether at least one negative or error scenario is present (e.g., invalid input, authentication failure, missing data).",
            "Check whether edge cases relevant to the specific requirement are addressed (boundary values, empty states, concurrent access, etc.).",
            "Check whether non-functional concerns (performance, security, accessibility) are mentioned when the requirement implies them.",
            "Assign a higher score when more of these areas are covered, and a lower score when key scenarios are missing.",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.5,
    )


def make_relevancy_metric(model: DeepEvalBaseLLM) -> GEval:
    """Are the test cases relevant to the actual requirement?"""
    return GEval(
        name="Test Relevancy",
        evaluation_steps=[
            "Read the input (user story) and identify the core feature being described.",
            "For each test case, edge scenario, and potential bug in the output, decide whether it directly tests behavior described in the input.",
            "Lower the score if test cases describe functionality that is not mentioned in the input.",
            "Lower the score if edge scenarios are generic and could apply to any feature rather than this specific one.",
            "Assign a high score when every item in the output is clearly traceable to the input requirement.",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.5,
    )


def make_consistency_metric(model: DeepEvalBaseLLM) -> GEval:
    """Are the test cases internally consistent and well-structured?"""
    return GEval(
        name="Test Consistency",
        evaluation_steps=[
            "For each test case, verify that the steps logically lead to the stated expected result.",
            "Check that preconditions listed for each test case are appropriate and sufficient.",
            "Check that priority levels make sense: critical user flows should have high priority.",
            "Check that test IDs or titles follow a consistent naming pattern across the suite.",
            "Lower the score if any test case contradicts another, or if steps and expected results are misaligned.",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.5,
    )


def make_specificity_metric(model: DeepEvalBaseLLM) -> GEval:
    """Are the test steps specific and actionable, or vague and generic?"""
    return GEval(
        name="Step Specificity",
        evaluation_steps=[
            "Read each step in every test case.",
            "Flag steps that are vague: 'Go to the page', 'Click the button', 'Verify the result' without naming the specific page, button, or result.",
            "Give credit for steps that include concrete data values, exact field names, specific URLs, or measurable acceptance criteria.",
            "Give credit for expected results that state a specific, observable outcome rather than a generic success message.",
            "Assign a high score when most steps are concrete and actionable, a low score when steps are mostly generic.",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.45,
    )


def make_nonfunctional_balance_metric(model: DeepEvalBaseLLM) -> GEval:
    """Is there an adequate balance between functional and non-functional test cases?"""
    return GEval(
        name="Non-Functional Balance",
        evaluation_steps=[
            "Count the functional test cases (happy path, negative, edge cases) and the non-functional ones (performance, security, usability, compatibility).",
            "Check whether non-functional test cases include measurable criteria — e.g., response time in milliseconds, specific attack vectors, or named browsers/devices.",
            "Lower the score if non-functional test cases exist but have vague criteria like 'the system should be fast' without a numeric threshold.",
            "Assign a high score if at least 25-30% of the suite covers non-functional concerns with concrete, measurable acceptance criteria.",
            "Assign a low score if all test cases are functional with no non-functional coverage at all.",
        ],
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=model,
        threshold=0.4,
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
# 4. Evaluation input normalizer
# ─────────────────────────────────────────────
def _normalize_for_eval(output: dict) -> str:
    """
    Convert the generated JSON blob into a concise plain-text summary.
    Small local eval models (llama3.2:8b) produce much better scores when
    given structured prose instead of raw nested JSON.
    """
    lines = []
    test_cases = output.get("test_cases", [])
    lines.append(f"TEST SUITE — {len(test_cases)} test case(s)\n")

    for tc in test_cases:
        tc_id    = tc.get("id", "?")
        title    = tc.get("title", "Untitled")
        category = tc.get("category", "unknown").upper()
        priority = tc.get("priority", "")
        steps    = tc.get("steps", [])
        expected = tc.get("expected_result", "")
        test_type = tc.get("test_type", "")

        header = f"[{category}] {tc_id}: {title}"
        if priority:
            header += f"  (priority: {priority})"
        if test_type:
            header += f"  (type: {test_type})"
        lines.append(header)

        if steps:
            # Cap at 8 steps to avoid overwhelming the model
            step_str = " → ".join(str(s) for s in steps[:8])
            lines.append(f"  Steps: {step_str}")

        if expected:
            lines.append(f"  Expected: {expected}")

        preconditions = tc.get("preconditions", [])
        if preconditions:
            lines.append(f"  Preconditions: {'; '.join(str(p) for p in preconditions[:3])}")

        lines.append("")

    edge = output.get("edge_scenarios", [])
    if edge:
        lines.append(f"EDGE SCENARIOS ({len(edge)}):")
        for e in edge[:5]:
            label = e.get("scenario", e.get("title", str(e))) if isinstance(e, dict) else str(e)
            lines.append(f"  - {str(label)[:120]}")
        lines.append("")

    bugs = output.get("potential_bugs", [])
    if bugs:
        lines.append(f"POTENTIAL BUGS ({len(bugs)}):")
        for b in bugs[:5]:
            label = b.get("description", b.get("bug", str(b))) if isinstance(b, dict) else str(b)
            lines.append(f"  - {str(label)[:120]}")
        lines.append("")

    summary = output.get("coverage_summary", {})
    if summary:
        pct      = summary.get("estimated_coverage_percent", "?")
        cats     = summary.get("categories_covered", [])
        missing  = summary.get("missing_areas", [])
        lines.append(f"COVERAGE: {pct}% | Categories covered: {', '.join(cats)}")
        if missing:
            lines.append(f"  Missing areas: {', '.join(missing)}")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# 5. Main evaluation runner
# ─────────────────────────────────────────────
@_opik_track(name="deepeval_evaluate")
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
            "eval model (%s) matches generation model — possible self-evaluation bias",
            model_name,
        )
    eval_model = OllamaEvalModel(effective_eval)

    actual_output = _normalize_for_eval(validated)
    logger.debug(
        "normalized eval input",
        extra={"event": "eval_input_normalized", "length": len(actual_output), "preview": actual_output[:300]},
    )

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
    actual_output = _normalize_for_eval(validated)
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
