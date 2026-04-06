"""Tests verifying FSM integration into CompanionEngine."""
import ast
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parents[2] / "services" / "companion_engine.py"


def test_assess_readiness_removed():
    """_assess_readiness() method should no longer exist in CompanionEngine."""
    tree = ast.parse(ENGINE_PATH.read_text(), filename="companion_engine.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CompanionEngine":
            method_names = set()
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.add(item.name)

            assert "_assess_readiness" not in method_names, (
                "_assess_readiness should be removed — replaced by ConversationFSM"
            )
            return

    assert False, "CompanionEngine class not found"


def test_fsm_import_present():
    """ConversationFSM should be imported in companion_engine.py."""
    text = ENGINE_PATH.read_text()
    assert "from services.conversation_fsm import ConversationFSM" in text


def test_fsm_used_in_preamble():
    """process_message_preamble should use ConversationFSM.evaluate()."""
    tree = ast.parse(ENGINE_PATH.read_text(), filename="companion_engine.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "process_message_preamble":
            source = ast.get_source_segment(ENGINE_PATH.read_text(), node)
            assert "ConversationFSM" in source, (
                "process_message_preamble must use ConversationFSM"
            )
            assert "fsm.evaluate" in source or "evaluate(analysis" in source, (
                "process_message_preamble must call fsm.evaluate()"
            )
            return

    assert False, "process_message_preamble not found"


def test_fsm_used_in_stream():
    """generate_response_stream should use ConversationFSM.evaluate()."""
    tree = ast.parse(ENGINE_PATH.read_text(), filename="companion_engine.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "generate_response_stream":
            source = ast.get_source_segment(ENGINE_PATH.read_text(), node)
            assert "ConversationFSM" in source, (
                "generate_response_stream must use ConversationFSM"
            )
            return

    assert False, "generate_response_stream not found"
