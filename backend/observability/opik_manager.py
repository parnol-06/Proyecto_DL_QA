"""
opik_manager.py — Enterprise-grade Opik distributed tracing.

Architecture decisions:
────────────────────────────────────────────────────────────────────────────
FIX 1  parent.span() → _client.span(trace_id=..., parent_span_id=...)
       Confirmed public API; avoids silent failures in Opik v2.x.

FIX 2  ContextVars store actual Opik .id values, not custom UUIDs.

FIX 3  Exception log level DEBUG → WARNING for better diagnosability.

FIX 4  opik.flush_tracker() called AFTER trace.end() so the trace-end event
       itself is included in the flush — calling it before left the final
       event in the SDK queue undelivered, causing traces never to appear.

FIX 5  RAG spans always inside root_trace so _cv_opik_trace_id is populated.

FIX 6  @tracer.track() replaced with explicit root_trace() in all endpoints
       so child_span() always resolves the parent trace without relying on
       the fragile _try_opik_context_ids() fallback.

NEW    request_id, pipeline_id, source_trace_id propagated via ContextVars.
NEW    record_error() sets status="failed" with structured exception info.
NEW    Specialized spans: request_validation, response_build, stream_lifecycle,
       llm_inference (for CrewAI agent LLM calls), service_span.
NEW    log_pipeline_feedback() for batch feedback score registration.
NEW    Auto-enrichment: every root_trace() includes request_id, pipeline_id,
       pipeline name, and source_trace_id (Generate → Evaluate correlation).
────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
import time
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generator, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# ── Module singletons ─────────────────────────────────────────────────────────
_client: Optional[Any] = None
_enabled: bool = False
_project_name: str = "Qa_trace"

# ── Core trace/span ContextVars ───────────────────────────────────────────────
# Stores actual Opik .id values so _client.span(trace_id=..., parent_span_id=...)
# always receives the correct server-side IDs.
# asyncio.run_in_executor copies the current Context to every submitted thread
# (Python 3.7+), so these propagate transparently to CrewAI, DeepEval, and
# Ollama threads without any explicit passing.
_cv_opik_trace_id: ContextVar[str] = ContextVar("opik_trace_id", default="")
_cv_opik_span_id: ContextVar[str]  = ContextVar("opik_span_id",  default="")
_cv_trace_obj: ContextVar[Optional[Any]] = ContextVar("opik_trace_obj", default=None)
_cv_span_obj:  ContextVar[Optional[Any]] = ContextVar("opik_span_obj",  default=None)

# ── Cross-cutting observability ContextVars ───────────────────────────────────
# These propagate HTTP context through the entire request lifecycle.
_cv_request_id: ContextVar[str]    = ContextVar("obs_request_id",     default="")
_cv_pipeline_id: ContextVar[str]   = ContextVar("obs_pipeline_id",    default="")
_cv_source_trace: ContextVar[str]  = ContextVar("obs_source_trace_id", default="")


# ─────────────────────────────────────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────────────────────────────────────

def init_tracer(
    api_key: str,
    workspace: str = "",
    project_name: str = "Qa_trace",
) -> bool:
    global _client, _enabled, _project_name
    if _enabled:
        return True
    if not api_key:
        logger.warning("OPIK_API_KEY not set — distributed tracing disabled")
        return False
    try:
        import opik
        opik.configure(api_key=api_key, workspace=workspace or None, force=True)
        _client = opik.Opik()
        _project_name = project_name or "Qa_trace"
        _enabled = True
        logger.info(
            "Opik tracer ready",
            extra={"event": "tracer_init", "project": _project_name, "workspace": workspace or "default"},
        )
        return True
    except ImportError:
        logger.warning("opik package not installed — tracing disabled")
    except Exception as exc:
        logger.warning("Opik init failed: %s", exc)
    return False


def is_enabled() -> bool:
    return _enabled


# ─────────────────────────────────────────────────────────────────────────────
# Context accessors — public API
# ─────────────────────────────────────────────────────────────────────────────

def get_trace_id() -> str:
    return _cv_opik_trace_id.get()

def get_current_trace() -> Optional[Any]:
    return _cv_trace_obj.get()

def get_current_span() -> Optional[Any]:
    return _cv_span_obj.get()

def get_active_parent() -> Optional[Any]:
    return _cv_span_obj.get() or _cv_trace_obj.get()

def get_request_id() -> str:
    return _cv_request_id.get()

def get_pipeline_id() -> str:
    return _cv_pipeline_id.get()

def get_source_trace_id() -> str:
    return _cv_source_trace.get()


# ─────────────────────────────────────────────────────────────────────────────
# Context setters — called by middleware and route handlers
# ─────────────────────────────────────────────────────────────────────────────

def set_request_id(rid: str) -> None:
    _cv_request_id.set(rid)

def set_source_trace_id(tid: str) -> None:
    _cv_source_trace.set(tid)


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def track(name: str, **kwargs):
    """
    Lightweight no-op-safe wrapper around opik.track.
    Prefer explicit root_trace() + child_span() for complex pipelines;
    use this only for simple utility functions with no nested child spans.
    """
    if not _enabled:
        def _noop(fn):
            return fn
        return _noop
    try:
        from opik import track as _opik_fn
        return _opik_fn(name=name, **kwargs)
    except Exception:
        def _noop(fn):
            return fn
        return _noop


def _try_opik_context_ids() -> tuple[str, Optional[str]]:
    """
    Reads trace_id and parent_span_id from Opik's internal @opik_track ContextVar.
    Fallback used by child_span() when _cv_opik_trace_id is empty.
    """
    for mod_name in ("opik.context_storage", "opik._context_storage",
                     "opik.api_objects.helpers.context_storage"):
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            for fn_name in ("get_current_span", "get_current_span_data"):
                if hasattr(mod, fn_name):
                    span = getattr(mod, fn_name)()
                    if span:
                        tid = str(getattr(span, "trace_id", None) or "")
                        sid_raw = getattr(span, "id", None) or getattr(span, "span_id", None)
                        if tid:
                            return tid, (str(sid_raw) if sid_raw else None)
            for fn_name in ("get_current_trace", "get_current_trace_data"):
                if hasattr(mod, fn_name):
                    trace = getattr(mod, fn_name)()
                    if trace:
                        tid = str(getattr(trace, "id", None) or getattr(trace, "trace_id", None) or "")
                        if tid:
                            return tid, None
        except Exception:
            continue
    return "", None


def _flush() -> None:
    if not _enabled:
        return
    try:
        import opik
        opik.flush_tracker()
    except Exception as exc:
        logger.debug("flush_tracker: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Core span operations
# ─────────────────────────────────────────────────────────────────────────────

def update_span(
    obj: Optional[Any],
    output: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> None:
    if obj is None or not _enabled:
        return
    try:
        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        if kwargs:
            obj.update(**kwargs)
    except Exception as exc:
        logger.warning("update_span failed (%s): %s", type(obj).__name__, exc)


def log_feedback_score(
    obj: Optional[Any],
    name: str,
    value: float,
    category_name: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    if obj is None or not _enabled:
        return
    clamped = max(0.0, min(1.0, float(value)))
    try:
        obj.log_feedback_score(
            name=name,
            value=clamped,
            category_name=category_name,
            reason=reason,
        )
    except Exception as exc:
        logger.warning("log_feedback_score '%s' failed: %s", name, exc)


def log_pipeline_feedback(
    obj: Optional[Any],
    scores: dict[str, tuple],
) -> None:
    """
    Batch-register multiple feedback scores.

    scores format:
        { "score_name": (value, category, reason) }
        { "score_name": (value, category) }
        { "score_name": (value,) }
    """
    for name, args in scores.items():
        if not isinstance(args, (list, tuple)):
            args = (args,)
        value    = args[0] if len(args) > 0 else 0.0
        category = args[1] if len(args) > 1 else None
        reason   = args[2] if len(args) > 2 else None
        log_feedback_score(obj, name, value, category, reason)


def record_error(
    exc: Exception,
    target: Optional[Any] = None,
    component: str = "",
    pipeline: str = "",
    agent: str = "",
) -> None:
    """
    Attach exception details to target (or deepest active context).
    Marks the span/trace as status='failed' with full structured context.
    """
    obj = target or _cv_span_obj.get() or _cv_trace_obj.get()
    if obj is None or not _enabled:
        return
    tb = traceback.format_exc()
    try:
        obj.update(
            metadata={
                "status": "failed",
                "error": True,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:600],
                "stacktrace": tb[:3000] if tb and tb.strip() != "NoneType: None" else "",
                "component": component or "unknown",
                "pipeline": pipeline or _cv_pipeline_id.get() or "unknown",
                "agent": agent or "",
                "request_id": _cv_request_id.get(),
            }
        )
    except Exception:
        pass


def _safe_end(
    obj: Optional[Any],
    output: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> None:
    if obj is None:
        return
    try:
        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        obj.end(**kwargs)
    except Exception as exc:
        logger.warning("_safe_end failed (%s): %s", type(obj).__name__, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Root trace — auto-enriched with request context
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def root_trace(
    name: str,
    input_data: Optional[dict] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
    pipeline: Optional[str] = None,
) -> Generator[Optional[Any], None, None]:
    """
    Creates a root-level Opik trace for one request / pipeline.

    Auto-enriches metadata with:
    - request_id (from HTTP middleware)
    - pipeline_execution_id (generated per trace)
    - pipeline (logical pipeline name)
    - source_trace_id (cross-pipeline correlation: Generate → Evaluate)

    Guarantees child spans are rooted by setting _cv_opik_trace_id to the
    actual trace.id from Opik — not a custom UUID.

    Calls _flush() before trace.end() to drain background span queue.
    """
    if not _enabled or _client is None:
        yield None
        return

    request_id   = _cv_request_id.get()
    source_tid   = _cv_source_trace.get()
    pipeline_id  = uuid4().hex[:12]
    pipeline_name = pipeline or name

    enriched_meta: dict[str, Any] = {
        **(metadata or {}),
        "request_id": request_id,
        "pipeline_execution_id": pipeline_id,
        "pipeline": pipeline_name,
    }
    if source_tid:
        enriched_meta["source_trace_id"] = source_tid

    _trace = None
    t0 = time.perf_counter()
    try:
        _trace = _client.trace(
            name=name,
            input=input_data or {},
            project_name=_project_name,
            tags=tags or [],
            metadata=enriched_meta,
        )
    except Exception as exc:
        logger.warning("root_trace create failed for '%s': %s", name, exc)
        yield None
        return

    tok_trace_id  = _cv_opik_trace_id.set(_trace.id)
    tok_span_id   = _cv_opik_span_id.set("")
    tok_trace     = _cv_trace_obj.set(_trace)
    tok_span      = _cv_span_obj.set(None)
    tok_pipeline  = _cv_pipeline_id.set(pipeline_id)

    exc_caught: Optional[BaseException] = None
    try:
        yield _trace
    except Exception as exc:
        exc_caught = exc
        record_error(exc, target=_trace, pipeline=pipeline_name)
    finally:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        status = "failed" if exc_caught else "ok"
        update_span(
            _trace,
            metadata={
                "total_duration_ms": elapsed_ms,
                "status": status,
                "pipeline": pipeline_name,
                "request_id": request_id,
                "pipeline_execution_id": pipeline_id,
            },
        )
        if exc_caught:
            _safe_end(_trace, output={"error": str(exc_caught)[:500]})
        else:
            _safe_end(_trace)
        _flush()  # AFTER trace.end() — flushes the trace-end event itself
        _cv_opik_trace_id.reset(tok_trace_id)
        _cv_opik_span_id.reset(tok_span_id)
        _cv_trace_obj.reset(tok_trace)
        _cv_span_obj.reset(tok_span)
        _cv_pipeline_id.reset(tok_pipeline)

    if exc_caught is not None:
        raise exc_caught


# ─────────────────────────────────────────────────────────────────────────────
# Child span — the building block for all component spans
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def child_span(
    name: str,
    span_type: str = "general",
    input_data: Optional[dict] = None,
    metadata: Optional[dict] = None,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    """
    Creates a child span using _client.span(trace_id=..., parent_span_id=...).

    Resolution order for parent:
    1. explicit_parent (passed directly)
    2. _cv_opik_trace_id + _cv_opik_span_id (set by root_trace / parent child_span)
    3. _try_opik_context_ids() — reads Opik @opik_track ContextVar as fallback

    If no trace context is found, yields None (no-op) without raising.
    """
    if not _enabled or _client is None:
        yield None
        return

    if explicit_parent is not None:
        if hasattr(explicit_parent, "trace_id"):
            trace_id       = explicit_parent.trace_id
            parent_span_id: Optional[str] = explicit_parent.id
        else:
            trace_id       = explicit_parent.id
            parent_span_id = None
    else:
        trace_id       = _cv_opik_trace_id.get()
        raw_span_id    = _cv_opik_span_id.get()
        parent_span_id = raw_span_id if raw_span_id else None

    if not trace_id:
        trace_id, parent_span_id = _try_opik_context_ids()

    if not trace_id:
        yield None
        return

    # Auto-enrich every span with cross-cutting context
    enriched_meta: dict[str, Any] = {
        **(metadata or {}),
        "request_id": _cv_request_id.get(),
        "pipeline_id": _cv_pipeline_id.get(),
        "pipeline": _cv_pipeline_id.get() or "",
    }

    _span = None
    t0 = time.perf_counter()
    try:
        _span = _client.span(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            type=span_type,
            input=input_data or {},
            metadata=enriched_meta,
            project_name=_project_name,
        )
    except Exception as exc:
        logger.warning("child_span create failed for '%s': %s", name, exc)
        yield None
        return

    tok_span_id = _cv_opik_span_id.set(_span.id)
    tok_span    = _cv_span_obj.set(_span)

    exc_caught: Optional[BaseException] = None
    try:
        yield _span
    except Exception as exc:
        exc_caught = exc
        record_error(exc, target=_span)
    finally:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        status = "failed" if exc_caught else "ok"
        if exc_caught:
            _safe_end(
                _span,
                output={"error": str(exc_caught)[:500]},
                metadata={"duration_ms": elapsed_ms, "status": status},
            )
        else:
            update_span(_span, metadata={"duration_ms": elapsed_ms, "status": status})
            _safe_end(_span)
        _cv_opik_span_id.reset(tok_span_id)
        _cv_span_obj.reset(tok_span)

    if exc_caught is not None:
        raise exc_caught


# ─────────────────────────────────────────────────────────────────────────────
# Specialized span helpers — domain-specific wrappers around child_span()
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def llm_span(
    name: str,
    model: str,
    system_prompt: str = "",
    user_prompt: str = "",
    temperature: float = 0.25,
    num_ctx: int = 8192,
    num_predict: int = 4096,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    input_tokens = estimate_tokens(system_prompt + user_prompt)
    with child_span(
        name=name,
        span_type="llm",
        input_data={
            "messages": [
                {"role": "system", "content": system_prompt[:300] if system_prompt else ""},
                {"role": "user",   "content": user_prompt[:400]},
            ]
        },
        metadata={
            "model": model,
            "provider": "ollama",
            "component": "ollama",
            "operation": "chat",
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "tokens_input_estimated": input_tokens,
            "usage": {"prompt_tokens": input_tokens, "completion_tokens": 0, "total_tokens": input_tokens},
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def llm_inference_span(
    agent_name: str,
    model: str,
    task_description: str = "",
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    """LLM call span for a CrewAI agent kickoff — captures timing + model."""
    with child_span(
        name=f"llm_call_{agent_name.lower()}",
        span_type="llm",
        input_data={
            "agent": agent_name,
            "task_preview": task_description[:200],
        },
        metadata={
            "component": "ollama_via_crewai",
            "operation": "agent_llm_call",
            "model": model,
            "agent_name": agent_name,
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def service_span(
    service_name: str,
    pipeline: str = "",
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    """Top-level span for a service function call — groups sub-spans."""
    with child_span(
        name=service_name,
        span_type="tool",
        input_data={},
        metadata={
            "component": "service",
            "operation": service_name,
            "pipeline": pipeline or _cv_pipeline_id.get(),
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def request_validation_span(
    endpoint: str,
    explicit_parent: Optional[Any] = None,
    **fields: Any,
) -> Generator[Optional[Any], None, None]:
    """Span for FastAPI request validation — marks entry point."""
    with child_span(
        name="request_validation",
        span_type="tool",
        input_data={"endpoint": endpoint, **fields},
        metadata={
            "component": "fastapi",
            "operation": "validate_request",
            "endpoint": endpoint,
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def response_build_span(
    tc_count: int = 0,
    edge_count: int = 0,
    bug_count: int = 0,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    """Span for response serialization — marks output assembly."""
    with child_span(
        name="response_serialization",
        span_type="tool",
        input_data={"tc_count": tc_count, "edge_count": edge_count, "bug_count": bug_count},
        metadata={"component": "fastapi", "operation": "serialize_response"},
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def stream_lifecycle_span(
    model: str,
    pipeline: str,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    """Span wrapping a full SSE streaming session — captures TTFT and chunk count."""
    with child_span(
        name="response_stream",
        span_type="tool",
        input_data={"model": model, "pipeline": pipeline},
        metadata={"component": "sse_stream", "operation": "stream_response", "model": model},
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def rag_span(
    query: str,
    k: int = 3,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name="rag_pipeline",
        span_type="tool",
        input_data={"query": query[:300], "k": k},
        metadata={
            "component": "chromadb",
            "operation": "semantic_search",
            "embed_model": "nomic-embed-text",
            "vector_store": "chromadb",
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def embed_span(
    text_preview: str,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name="embedding_generation",
        span_type="llm",
        input_data={"text_preview": text_preview[:200]},
        metadata={"model": "nomic-embed-text", "component": "ollama_embed", "operation": "embed"},
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def crew_pipeline_span(
    tc_count: int,
    model: str,
    use_rag: bool = False,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name="crew_pipeline",
        span_type="tool",
        input_data={"tc_count": tc_count, "model": model, "use_rag": use_rag},
        metadata={
            "component": "crewai",
            "operation": "pipeline",
            "agent_count": 3,
            "model": model,
            "rag_enabled": use_rag,
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def agent_span(
    agent_name: str,
    agent_role: str,
    step: int,
    total: int,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name=f"agent_{step}_{agent_name.lower()}",
        span_type="tool",
        input_data={"agent": agent_name, "role": agent_role, "step": f"{step}/{total}"},
        metadata={
            "component": "crewai",
            "operation": "agent_kickoff",
            "agent_name": agent_name,
            "agent_role": agent_role,
            "pipeline_step": step,
            "pipeline_total": total,
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def deepeval_span(
    metric_count: int,
    eval_model: str,
    test_case_count: int,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name="deepeval_evaluation",
        span_type="tool",
        input_data={"metric_count": metric_count, "test_case_count": test_case_count},
        metadata={
            "component": "deepeval",
            "operation": "evaluate",
            "eval_model": eval_model,
            "metric_count": metric_count,
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def parse_span(
    content_chars: int,
    component: str = "json_parser",
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name="llm_json_parse",
        span_type="tool",
        input_data={"content_chars": content_chars},
        metadata={"component": component, "operation": "parse_json"},
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def prompt_span(
    tc_count: int,
    categories: list,
    rag_chars: int = 0,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name="prompt_compilation",
        span_type="tool",
        input_data={"tc_count": tc_count, "categories": categories, "rag_chars": rag_chars},
        metadata={"component": "prompt_builder", "operation": "build"},
        explicit_parent=explicit_parent,
    ) as s:
        yield s


@contextmanager
def metric_span(
    metric_name: str,
    threshold: float,
    eval_model: str,
    explicit_parent: Optional[Any] = None,
) -> Generator[Optional[Any], None, None]:
    with child_span(
        name=f"metric_{metric_name.lower().replace(' ', '_')}",
        span_type="tool",
        input_data={"metric": metric_name, "threshold": threshold},
        metadata={
            "component": "deepeval",
            "operation": "metric_measure",
            "metric_name": metric_name,
            "threshold": threshold,
            "eval_model": eval_model,
        },
        explicit_parent=explicit_parent,
    ) as s:
        yield s
