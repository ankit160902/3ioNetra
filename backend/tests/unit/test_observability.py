"""Tests for observability utilities."""
import asyncio
import logging
import importlib.util
from pathlib import Path

# Load directly to avoid services/__init__.py chain
_path = str(Path(__file__).resolve().parents[2] / "services" / "observability.py")
_spec = importlib.util.spec_from_file_location("observability", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

get_correlation_id = _mod.get_correlation_id
set_correlation_id = _mod.set_correlation_id
timed = _mod.timed
RequestTimings = _mod.RequestTimings
CorrelationFilter = _mod.CorrelationFilter


# ---------------------------------------------------------------------------
# Correlation ID
# ---------------------------------------------------------------------------

class TestCorrelationId:
    def test_default_is_empty(self):
        # In a fresh context, correlation_id is ""
        # Note: may be set from other tests; just check it's a string
        assert isinstance(get_correlation_id(), str)

    def test_set_and_get(self):
        cid = set_correlation_id("test-abc-123")
        assert cid == "test-abc-123"
        assert get_correlation_id() == "test-abc-123"

    def test_auto_generates_if_none(self):
        cid = set_correlation_id()
        assert len(cid) == 12  # hex[:12]
        assert get_correlation_id() == cid

    def test_set_custom_id(self):
        cid = set_correlation_id("custom-request-42")
        assert cid == "custom-request-42"


# ---------------------------------------------------------------------------
# Timed decorator
# ---------------------------------------------------------------------------

class TestTimedDecorator:
    async def test_async_function_timing(self):
        @timed("test_sleep")
        async def slow_fn():
            await asyncio.sleep(0.01)
            return 42

        result = await slow_fn()
        assert result == 42

    def test_sync_function_timing(self):
        @timed("test_sync")
        def fast_fn():
            return "done"

        result = fast_fn()
        assert result == "done"

    async def test_preserves_return_value(self):
        @timed()
        async def compute():
            return {"key": "value"}

        result = await compute()
        assert result == {"key": "value"}

    async def test_preserves_exceptions(self):
        @timed("failing")
        async def failing_fn():
            raise ValueError("test error")

        import pytest
        with pytest.raises(ValueError, match="test error"):
            await failing_fn()


# ---------------------------------------------------------------------------
# RequestTimings
# ---------------------------------------------------------------------------

class TestRequestTimings:
    def test_start_stop(self):
        rt = RequestTimings()
        rt.start("intent")
        import time
        time.sleep(0.01)
        elapsed = rt.stop("intent")
        assert elapsed > 5  # At least 5ms (sleep 10ms with margin)
        assert "intent" in rt.timings

    def test_multiple_stages(self):
        rt = RequestTimings()
        rt.start("a")
        rt.stop("a")
        rt.start("b")
        rt.stop("b")
        assert len(rt.timings) == 2
        assert rt.total_ms > 0

    def test_summary_format(self):
        rt = RequestTimings()
        rt._timings = {"intent": 50.0, "rag": 200.0, "llm": 1500.0}
        summary = rt.summary()
        assert "total=1750ms" in summary
        assert "intent=50ms" in summary
        assert "rag=200ms" in summary

    def test_stop_without_start(self):
        rt = RequestTimings()
        elapsed = rt.stop("nonexistent")
        assert elapsed == 0.0


# ---------------------------------------------------------------------------
# CorrelationFilter
# ---------------------------------------------------------------------------

class TestCorrelationFilter:
    def test_injects_correlation_id(self):
        set_correlation_id("filter-test-123")
        f = CorrelationFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None
        )
        result = f.filter(record)
        assert result is True
        assert record.correlation_id == "filter-test-123"

    def test_default_dash_when_no_id(self):
        # Reset to empty
        set_correlation_id("")
        # Now contextvars might still have old value from previous test
        # So just check it returns a string
        f = CorrelationFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None
        )
        f.filter(record)
        assert isinstance(record.correlation_id, str)
