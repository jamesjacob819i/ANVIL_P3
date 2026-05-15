import os
import uuid
import functools
from datetime import datetime, timezone

OMIUM_API_KEY = os.getenv("OMIUM_API_KEY", "")

try:
    from omium import OmiumClient
    _client = OmiumClient(api_key=OMIUM_API_KEY) if OMIUM_API_KEY else None
except ImportError:
    _client = None


class TraceContext:
    def __init__(self, trace_id: str = ""):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.spans: list[dict] = []

    def add_span(self, name: str, span_type: str, duration_ms: float, metadata: dict = None):
        span = {
            "trace_id": self.trace_id,
            "span_id": str(uuid.uuid4()),
            "name": name,
            "type": span_type,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self.spans.append(span)
        if _client:
            try:
                _client.report_span(span)
            except Exception:
                pass
        return span


_current_trace: TraceContext | None = None


def get_trace() -> TraceContext:
    global _current_trace
    if _current_trace is None:
        _current_trace = TraceContext()
    return _current_trace


def set_trace(trace_id: str):
    global _current_trace
    _current_trace = TraceContext(trace_id=trace_id)


def reset_trace():
    global _current_trace
    _current_trace = None


def trace(name: str = None, span_type: str = "agent_step"):
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_ctx = get_trace()
            start = datetime.now(timezone.utc)
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                trace_ctx.add_span(
                    name=name or func.__name__,
                    span_type=span_type,
                    duration_ms=duration,
                    metadata={"args": str(args), "kwargs": str(kwargs)},
                )
                return result
            except Exception as e:
                duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                trace_ctx.add_span(
                    name=name or func.__name__,
                    span_type="error",
                    duration_ms=duration,
                    metadata={"error": str(e)},
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            trace_ctx = get_trace()
            start = datetime.now(timezone.utc)
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                trace_ctx.add_span(
                    name=name or func.__name__,
                    span_type=span_type,
                    duration_ms=duration,
                )
                return result
            except Exception as e:
                duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                trace_ctx.add_span(
                    name=name or func.__name__,
                    span_type="error",
                    duration_ms=duration,
                    metadata={"error": str(e)},
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


import asyncio
