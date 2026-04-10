"""Tests verifying observability is wired into the request path."""
import ast
from pathlib import Path

CHAT_ROUTER_PATH = Path(__file__).resolve().parents[2] / "routers" / "chat.py"
MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"
LOGGING_CONFIG_PATH = Path(__file__).resolve().parents[2] / "logging_config.py"


class TestChatRouterObservability:
    def test_imports_observability(self):
        text = CHAT_ROUTER_PATH.read_text()
        assert "from services.observability import" in text
        assert "set_correlation_id" in text

    def test_conversation_endpoint_sets_correlation_id(self):
        """The /conversation endpoint should call set_correlation_id()."""
        tree = ast.parse(CHAT_ROUTER_PATH.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "conversational_query":
                source = ast.get_source_segment(CHAT_ROUTER_PATH.read_text(), node)
                assert "set_correlation_id()" in source
                assert "REQUEST_START" in source
                return
        assert False, "conversational_query endpoint not found"

    def test_conversation_endpoint_logs_elapsed_time(self):
        """The /conversation endpoint should log elapsed time."""
        text = CHAT_ROUTER_PATH.read_text()
        assert "REQUEST_END" in text
        assert "perf_counter" in text

    def test_stream_endpoint_sets_correlation_id(self):
        """The /conversation/stream endpoint should call set_correlation_id()."""
        tree = ast.parse(CHAT_ROUTER_PATH.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "conversational_query_stream":
                source = ast.get_source_segment(CHAT_ROUTER_PATH.read_text(), node)
                assert "set_correlation_id()" in source
                assert "STREAM_START" in source
                return
        assert False, "conversational_query_stream endpoint not found"


class TestLoggingConfigWiring:
    """The original assertions checked for substring patterns inside main.py
    (basicConfig, addFilter, format string). After the A1 refactor, those
    patterns now live in `logging_config.py` and main.py just calls
    `configure()` once at startup. These tests verify the same end-to-end
    intent against the new structure.

    The richer behavioral contract — that records from any logger format
    correctly without KeyError — is enforced by `test_logging_correlation.py`.
    """

    def test_main_imports_logging_configurator(self):
        """main.py must call the centralized configure() instead of
        running its own basicConfig (which is a no-op under uvicorn)."""
        text = MAIN_PATH.read_text()
        assert "from logging_config import" in text
        assert "configure" in text
        # Sanity check: no stray basicConfig — see test_logging_correlation
        # for the AST-level guard that catches reintroductions.
        assert "basicConfig" not in text

    def test_logging_config_declares_correlation_filter(self):
        """logging_config.py must wire CorrelationFilter via dictConfig
        so propagated records from child loggers are filtered too."""
        text = LOGGING_CONFIG_PATH.read_text()
        assert "CorrelationFilter" in text
        assert "correlation_id" in text

    def test_logging_config_format_includes_correlation_id(self):
        """The format string must reference correlation_id so the filter
        chain is required to populate it on every record."""
        text = LOGGING_CONFIG_PATH.read_text()
        assert "%(correlation_id)s" in text

    def test_logging_config_attaches_filter_to_handler_not_logger(self):
        """The original Bug #1 was a logger-level filter. The dictConfig
        must put the filter on the handler so propagated records hit it."""
        text = LOGGING_CONFIG_PATH.read_text()
        # The handler block must list the filter under its 'filters' key.
        # We check for the structural marker rather than executing the
        # config — `test_logging_correlation.py` does the runtime check.
        assert '"filters": ["correlation_id"]' in text or "'filters': ['correlation_id']" in text

    def test_logging_config_covers_uvicorn_loggers(self):
        """Uvicorn ships its own loggers (uvicorn, uvicorn.error,
        uvicorn.access) with their own formatters. logging_config must
        explicitly route them through our handler so we don't get
        parallel log streams without correlation IDs."""
        text = LOGGING_CONFIG_PATH.read_text()
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
            assert f'"{name}"' in text, f"missing logger config for {name}"
