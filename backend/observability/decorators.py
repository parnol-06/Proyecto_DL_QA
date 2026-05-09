"""
decorators.py — Reusable trace decorators for AI pipeline components.

Each decorator creates a named child span around the decorated function,
auto-propagating the current trace context. All decorators are async-safe
and work in both sync and async functions.

Usage:
    @trace_pipeline("rag_retrieval", component="chromadb")
    async def my_rag_function(query: str) -> str:
        ...

    @trace_agent("Generador", role="QA Test Case Generator")
    def run_agent(...):
        ...
"""
from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Callable, Optional

import backend.observability.opik_manager as opik_manager


def _make_decorator(span_builder: Callable, **static_meta: Any):
    """
    Returns a decorator factory that wraps sync or async callables
    with a named child span.

    span_builder is a callable that accepts (name, **meta) and returns
    a context manager (e.g. opik_manager.child_span).
    """
    def decorator(fn: Callable) -> Callable:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                with span_builder(**static_meta) as _s:
                    t0 = time.perf_counter()
                    try:
                        result = await fn(*args, **kwargs)
                        opik_manager.update_span(
                            _s, metadata={"elapsed_ms": round((time.perf_counter() - t0) * 1000)}
                        )
                        return result
                    except Exception as exc:
                        opik_manager.record_error(exc, target=_s)
                        raise
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                with span_builder(**static_meta) as _s:
                    t0 = time.perf_counter()
                    try:
                        result = fn(*args, **kwargs)
                        opik_manager.update_span(
                            _s, metadata={"elapsed_ms": round((time.perf_counter() - t0) * 1000)}
                        )
                        return result
                    except Exception as exc:
                        opik_manager.record_error(exc, target=_s)
                        raise
            return sync_wrapper
    return decorator


def trace_pipeline(name: str, component: str = "", operation: str = ""):
    """
    Decorator that wraps a function with a 'tool' span representing a
    logical pipeline stage (e.g. rag_retrieval, generate_pipeline).
    """
    def _builder(**meta):
        return opik_manager.child_span(
            name=name,
            span_type="tool",
            input_data={},
            metadata={
                "component": component or name,
                "operation": operation or name,
                **meta,
            },
        )
    return _make_decorator(_builder)


def trace_agent(agent_name: str, role: str = "", step: int = 0, total: int = 0):
    """
    Decorator for a single CrewAI agent execution block.
    """
    def _builder(**meta):
        return opik_manager.agent_span(
            agent_name=agent_name,
            agent_role=role or agent_name,
            step=step,
            total=total,
        )
    return _make_decorator(_builder)


def trace_llm(model: str, component: str = "ollama", operation: str = "chat"):
    """
    Decorator for any LLM inference call.
    """
    def _builder(**meta):
        return opik_manager.child_span(
            name=f"llm_{operation}",
            span_type="llm",
            input_data={},
            metadata={
                "model": model,
                "component": component,
                "operation": operation,
                **meta,
            },
        )
    return _make_decorator(_builder)


def trace_rag(component: str = "chromadb", operation: str = "semantic_search"):
    """
    Decorator for RAG retrieval operations.
    """
    def _builder(**meta):
        return opik_manager.child_span(
            name="rag_retrieval",
            span_type="tool",
            input_data={},
            metadata={
                "component": component,
                "operation": operation,
                **meta,
            },
        )
    return _make_decorator(_builder)


def trace_eval(eval_model: str = "", metric_count: int = 0):
    """
    Decorator for DeepEval evaluation functions.
    """
    def _builder(**meta):
        return opik_manager.child_span(
            name="deepeval_run",
            span_type="tool",
            input_data={"metric_count": metric_count},
            metadata={
                "component": "deepeval",
                "operation": "evaluate",
                "eval_model": eval_model,
                **meta,
            },
        )
    return _make_decorator(_builder)
