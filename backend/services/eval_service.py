import logging
import sys
from pathlib import Path

from backend.schemas.models import EvaluateRequest, EvaluateResponse

logger = logging.getLogger(__name__)

_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from evaluator.metrics import evaluate_test_cases as _run_deepeval
    _EVALUATOR_AVAILABLE = True
except Exception as e:
    logger.warning("DeepEval no disponible: %s", str(e))
    _EVALUATOR_AVAILABLE = False


async def run_evaluation(req: EvaluateRequest) -> EvaluateResponse:
    if not _EVALUATOR_AVAILABLE:
        raise RuntimeError(
            "DeepEval no está disponible. Verifica que deepeval esté instalado y configurado."
        )

    logger.info("Iniciando evaluación DeepEval | modelo=%s", req.model)

    raw = _run_deepeval(
        user_story=req.requirement,
        generated_output=req.generated_output,
        model_name=req.model,
    )

    metrics = raw.get("metrics", {})

    def score(key: str) -> float:
        return round(metrics.get(key, {}).get("score", 0.0), 3)

    return EvaluateResponse(
        coverage=score("Test Coverage"),
        relevancy=score("Test Relevancy"),
        consistency=score("Test Consistency"),
        specificity=score("Step Specificity"),
        nonfunctional_balance=score("Non-Functional Balance"),
        overall=round(raw.get("overall_score", 0.0), 3),
        model_used=raw.get("model_used", f"ollama/{req.model}"),
    )
