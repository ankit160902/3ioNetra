"""Observability utilities for request tracing and performance monitoring.

Provides:
- Request correlation IDs (propagated through async context)
- Async timing decorator for measuring service latency
- Structured log formatter with correlation ID injection
"""
import asyncio
import contextvars
import functools
import inspect
import logging
import time
import uuid
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Correlation ID (request-scoped via contextvars)
# ---------------------------------------------------------------------------

_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def get_correlation_id() -> str:
    """Get current request's correlation ID."""
    return _correlation_id.get()


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID for current request. Auto-generates if not provided."""
    cid = cid or uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


# ---------------------------------------------------------------------------
# Async timing decorator
# ---------------------------------------------------------------------------

def timed(label: Optional[str] = None):
    """Decorator that logs execution time of async/sync functions.

    Usage:
        @timed("intent_analysis")
        async def analyze_intent(...): ...

        @timed()
        def compute_scores(...): ...
    """
    def decorator(fn: Callable) -> Callable:
        fn_label = label or f"{fn.__module__}.{fn.__qualname__}"

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs) -> Any:
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    return result
                finally:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    cid = get_correlation_id()
                    logger.info(
                        f"TIMING | {fn_label} | {elapsed_ms:.1f}ms"
                        + (f" | cid={cid}" if cid else "")
                    )
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs) -> Any:
                start = time.perf_counter()
                try:
                    result = fn(*args, **kwargs)
                    return result
                finally:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    cid = get_correlation_id()
                    logger.info(
                        f"TIMING | {fn_label} | {elapsed_ms:.1f}ms"
                        + (f" | cid={cid}" if cid else "")
                    )
            return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Request timing collector
# ---------------------------------------------------------------------------

class RequestTimings:
    """Collects per-stage timings for a single request."""

    def __init__(self):
        self._timings: Dict[str, float] = {}
        self._starts: Dict[str, float] = {}

    def start(self, label: str) -> None:
        self._starts[label] = time.perf_counter()

    def stop(self, label: str) -> float:
        if label in self._starts:
            elapsed = (time.perf_counter() - self._starts[label]) * 1000
            self._timings[label] = elapsed
            del self._starts[label]
            return elapsed
        return 0.0

    @property
    def timings(self) -> Dict[str, float]:
        return dict(self._timings)

    @property
    def total_ms(self) -> float:
        return sum(self._timings.values())

    def summary(self) -> str:
        parts = [f"{k}={v:.0f}ms" for k, v in self._timings.items()]
        return f"total={self.total_ms:.0f}ms | " + " | ".join(parts)


# ---------------------------------------------------------------------------
# Correlation-aware log filter
# ---------------------------------------------------------------------------

class CorrelationFilter(logging.Filter):
    """Injects correlation_id into log records for structured logging."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True
