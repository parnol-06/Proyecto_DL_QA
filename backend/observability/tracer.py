"""
tracer.py — Public re-export shim.

All logic lives in opik_manager.py. This module preserves backward
compatibility for any code that does `from backend.observability import tracer`.
"""
from backend.observability.opik_manager import (  # noqa: F401
    init_tracer,
    is_enabled,
    get_trace_id,
    get_current_trace,
    get_current_span,
    get_active_parent,
    get_request_id,
    get_pipeline_id,
    get_source_trace_id,
    set_request_id,
    set_source_trace_id,
    estimate_tokens,
    update_span,
    log_feedback_score,
    log_pipeline_feedback,
    record_error,
    track,
    root_trace,
    child_span,
    service_span,
    request_validation_span,
    response_build_span,
    stream_lifecycle_span,
    llm_span,
    llm_inference_span,
    rag_span,
    embed_span,
    parse_span,
    prompt_span,
    crew_pipeline_span,
    agent_span,
    deepeval_span,
    metric_span,
)

__all__ = [
    "init_tracer", "is_enabled",
    "get_trace_id", "get_current_trace", "get_current_span", "get_active_parent",
    "get_request_id", "get_pipeline_id", "get_source_trace_id",
    "set_request_id", "set_source_trace_id",
    "estimate_tokens",
    "update_span", "log_feedback_score", "log_pipeline_feedback",
    "record_error",
    "track",
    "root_trace", "child_span", "service_span",
    "request_validation_span", "response_build_span", "stream_lifecycle_span",
    "llm_span", "llm_inference_span",
    "rag_span", "embed_span",
    "parse_span", "prompt_span",
    "crew_pipeline_span", "agent_span",
    "deepeval_span", "metric_span",
]
