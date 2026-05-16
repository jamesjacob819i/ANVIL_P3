import os
import uuid
import functools
from datetime import datetime, timezone
import asyncio

OMIUM_API_KEY = os.getenv("OMIUM_API_KEY", "")

try:
    import omium
    if OMIUM_API_KEY:
        omium.init(api_key=OMIUM_API_KEY)
    else:
        omium.init() # Use default env var if set
    _omium_available = True
except Exception as e:
    _omium_available = False
    print(f"Failed to initialize omium: {e}")


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
    # If omium is available, we can use it to wrap our functions.
    # We still keep the original TraceContext for our own DB logging if necessary.
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_ctx = get_trace()
            start = datetime.now(timezone.utc)
            try:
                if _omium_available:
                    # Use omium directly inside if needed or just use the decorator pattern
                    pass
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
        
        # Determine if we should wrap with omium
        if _omium_available:
            wrapped_func = omium.trace(name or func.__name__)(async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper)
            return wrapped_func
            
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator

