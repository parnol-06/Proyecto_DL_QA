"""
Structured logging with automatic correlation-ID injection.

Setup (call once at startup):
    from backend.utils.logging_config import configure_logging
    configure_logging()

Inject IDs per-request:
    from backend.utils.logging_config import set_request_id, set_evaluation_id
    set_request_id(str(uuid4()))
    set_evaluation_id(str(uuid4()))

ENV vars:
    LOG_FORMAT = json (default) | text
    LOG_LEVEL  = INFO (default) | DEBUG | WARNING | ERROR
"""

import json
import logging
import os
from contextvars import ContextVar
from datetime import datetime, timezone

# ── Correlation ContextVars ────────────────────────────────────────────────
# asyncio copies the current context when spawning tasks / running in executor,
# so IDs set in a request handler are visible in all downstream coroutines and
# ThreadPoolExecutor threads automatically.
evaluation_id_var: ContextVar[str] = ContextVar("evaluation_id", default="-")
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_evaluation_id() -> str:
    return evaluation_id_var.get()


def set_evaluation_id(eid: str) -> None:
    evaluation_id_var.set(eid)


def get_request_id() -> str:
    return request_id_var.get()


def set_request_id(rid: str) -> None:
    request_id_var.set(rid)


# ── Filter: injects IDs into every log record ──────────────────────────────
class CorrelationFilter(logging.Filter):
    """Stamps evaluation_id + request_id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.evaluation_id = evaluation_id_var.get()
        record.request_id = request_id_var.get()
        return True


# ── JSON formatter ─────────────────────────────────────────────────────────
_STDLIB_KEYS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
    "evaluation_id", "request_id",
})


class JSONFormatter(logging.Formatter):
    """Emits each record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "evaluation_id": getattr(record, "evaluation_id", "-"),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        # Merge caller-supplied extra={} fields
        for k, v in record.__dict__.items():
            if k not in _STDLIB_KEYS and not k.startswith("_"):
                entry[k] = v
        return json.dumps(entry, default=str)


# ── Public setup ───────────────────────────────────────────────────────────
def configure_logging() -> None:
    """Replace root logger with structured output. Call once at app startup."""
    use_json = os.getenv("LOG_FORMAT", "json").lower() != "text"
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.addFilter(CorrelationFilter())
    handler.setFormatter(
        JSONFormatter()
        if use_json
        else logging.Formatter(
            "%(asctime)s | %(levelname)-8s"
            " | eval=%(evaluation_id)s | req=%(request_id)s"
            " | %(name)s | %(message)s"
        )
    )
    root.addHandler(handler)

    # Quiet third-party loggers that produce noise
    for name in ("httpx", "httpcore", "ollama", "deepeval", "chromadb", "crewai"):
        logging.getLogger(name).setLevel(logging.WARNING)
