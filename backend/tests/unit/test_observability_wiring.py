"""Tests verifying observability is wired into the request path."""
import ast
from pathlib import Path

CHAT_ROUTER_PATH = Path(__file__).resolve().parents[2] / "routers" / "chat.py"
MAIN_PATH = Path(__file__).resolve().parents[2] / "main.py"


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


class TestMainObservability:
    def test_correlation_filter_in_logging(self):
        """main.py should add CorrelationFilter to root logger."""
        text = MAIN_PATH.read_text()
        assert "CorrelationFilter" in text
        assert "correlation_id" in text

    def test_log_format_includes_correlation_id(self):
        """Log format should include %(correlation_id)s."""
        text = MAIN_PATH.read_text()
        assert "%(correlation_id)s" in text
