"""Contract tests for the logging configuration.

These tests would have caught the original Bug #1 — a CorrelationFilter
attached to the root logger via `addFilter()` instead of to the handler,
which silently fails for log records propagated up from child loggers
(uvicorn.error, httpx, google.genai). The tests below verify the contract
of `logging_config.configure()` end-to-end through the real logging stack.
"""
from __future__ import annotations

import io
import logging
from logging.config import dictConfig
from typing import Iterator

import pytest

from logging_config import build_logging_config
from services.observability import (
    CorrelationFilter,
    _correlation_id,
    set_correlation_id,
)


def _reset_correlation_id() -> None:
    """Reset the correlation context to its default empty value.

    `set_correlation_id("")` does NOT clear the cid — it falls through the
    `cid or uuid4()` guard and generates a fresh UUID. To actually clear,
    we set the contextvar directly.
    """
    _correlation_id.set("")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def captured_stream() -> Iterator[io.StringIO]:
    """Apply LOGGING_CONFIG with a StringIO sink and yield it.

    This installs the same dictConfig structure as production but redirects
    every handler's stream to the StringIO. Restores the previous root
    logger config on teardown so tests don't pollute each other.
    """
    sink = io.StringIO()

    # Snapshot the current root logger handlers so we can restore them.
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_filters = list(root.filters)

    # Start each test with a clean correlation context — see helper above.
    _reset_correlation_id()

    config = build_logging_config(level="DEBUG")
    # Override the stream of the console handler to write to our sink.
    config["handlers"]["console"]["stream"] = sink
    dictConfig(config)

    yield sink

    # Restore — drop our handlers and reinstate snapshot.
    root.handlers = saved_handlers
    root.level = saved_level
    root.filters = saved_filters
    _reset_correlation_id()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCorrelationFilterPropagation:
    """The bug: filters on the root LOGGER do not run for records propagated
    up from child loggers — only filters on the root HANDLER do.

    These tests verify the filter is attached at the handler level so every
    record from any logger gets a correlation_id attribute before formatting.
    """

    def test_uvicorn_error_logger_does_not_raise_keyerror(self, captured_stream):
        """Records from uvicorn.error must format cleanly even with no cid set.

        This is the exact failure mode that produced 239 tracebacks per
        session: uvicorn.error.info() → propagated to root → handler with
        format string requiring correlation_id → KeyError because the
        filter was on the wrong attachment point.
        """
        _reset_correlation_id()  # no correlation ID set for this record
        log = logging.getLogger("uvicorn.error")
        log.info("startup complete")
        output = captured_stream.getvalue()
        assert "KeyError" not in output, output
        assert "Logging error" not in output, output
        assert "startup complete" in output
        # Default sentinel from CorrelationFilter when no cid is set:
        assert "[-]" in output

    def test_httpx_logger_does_not_raise_keyerror(self, captured_stream):
        """Same contract for any third-party child logger."""
        _reset_correlation_id()
        log = logging.getLogger("httpx")
        log.info("HTTP Request: POST https://example.com")
        output = captured_stream.getvalue()
        assert "KeyError" not in output
        assert "[-]" in output
        assert "POST https://example.com" in output

    def test_google_genai_logger_does_not_raise_keyerror(self, captured_stream):
        """Same contract for the Gemini SDK's logger."""
        _reset_correlation_id()
        log = logging.getLogger("google.genai")
        log.info("API call complete")
        output = captured_stream.getvalue()
        assert "KeyError" not in output
        assert "[-]" in output

    def test_arbitrary_descendant_logger_does_not_raise_keyerror(
        self, captured_stream
    ):
        """Future loggers must work too — not just the ones we know about."""
        _reset_correlation_id()
        log = logging.getLogger("some.future.library.module")
        log.info("hello")
        output = captured_stream.getvalue()
        assert "KeyError" not in output
        assert "[-]" in output


class TestCorrelationIdValueInjection:
    """Once a correlation ID is set, it must appear in formatted log lines
    from any logger — proving the filter chain runs end-to-end.
    """

    def test_set_id_appears_in_root_logger_output(self, captured_stream):
        set_correlation_id("abc123def456")
        logging.getLogger().info("root log line")
        assert "[abc123def456]" in captured_stream.getvalue()

    def test_set_id_appears_in_application_child_logger_output(
        self, captured_stream
    ):
        set_correlation_id("xyz789")
        logging.getLogger("services.companion_engine").info("engine line")
        assert "[xyz789]" in captured_stream.getvalue()

    def test_set_id_appears_in_uvicorn_logger_output(self, captured_stream):
        set_correlation_id("req-001")
        logging.getLogger("uvicorn.error").info("uvicorn line")
        output = captured_stream.getvalue()
        assert "[req-001]" in output


class TestFilterIsAttachedToHandlerNotLogger:
    """Direct structural assertion — the bug was about WHERE the filter was
    attached. This test pins it to the handler so a future refactor that
    accidentally moves the filter back to the logger fails immediately.
    """

    def test_console_handler_has_correlation_filter(self, captured_stream):
        root = logging.getLogger()
        # Find the handler we configured (it writes to our captured stream).
        our_handlers = [h for h in root.handlers if getattr(h, "stream", None) is captured_stream]
        assert our_handlers, "configured handler not found on root logger"
        handler = our_handlers[0]
        filter_classes = [type(f).__name__ for f in handler.filters]
        assert "CorrelationFilter" in filter_classes, (
            f"CorrelationFilter must be attached to the HANDLER, not the logger. "
            f"Handler filters: {filter_classes}"
        )


class TestNoBasicConfigInProductionPath:
    """Guard against regression: nobody should reintroduce basicConfig in
    main.py. basicConfig is a no-op when handlers already exist (which they
    do under uvicorn) — making it silently broken.
    """

    def test_main_py_does_not_call_basic_config(self):
        from pathlib import Path

        main_py = Path(__file__).resolve().parents[2] / "main.py"
        source = main_py.read_text()
        assert "basicConfig" not in source, (
            "main.py must not call logging.basicConfig — use "
            "logging_config.configure() so dictConfig owns the entire "
            "handler chain."
        )
