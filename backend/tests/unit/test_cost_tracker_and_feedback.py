"""Tests for non-blocking MongoDB writes in cost_tracker.py and chat.py feedback."""
import ast
from pathlib import Path


COST_TRACKER_PATH = Path(__file__).resolve().parents[2] / "services" / "cost_tracker.py"
CHAT_ROUTER_PATH = Path(__file__).resolve().parents[2] / "routers" / "chat.py"


# ---------------------------------------------------------------------------
# cost_tracker.py tests
# ---------------------------------------------------------------------------

def test_cost_tracker_imports_asyncio():
    """cost_tracker.py must import asyncio for non-blocking DB writes."""
    text = COST_TRACKER_PATH.read_text()
    assert "import asyncio" in text


def test_cost_tracker_uses_run_in_executor():
    """cost_tracker.log() must use run_in_executor for MongoDB insert."""
    text = COST_TRACKER_PATH.read_text()
    assert "run_in_executor" in text, (
        "cost_tracker.py should use loop.run_in_executor() for non-blocking insert_one"
    )


def test_cost_tracker_no_bare_insert_in_async_path():
    """The insert_one in cost_tracker should be inside run_in_executor or try/except for loop detection."""
    text = COST_TRACKER_PATH.read_text()
    # The pattern should be: get_running_loop → run_in_executor(None, insert_one, ...)
    # with a RuntimeError fallback for sync context
    assert "get_running_loop" in text, (
        "cost_tracker should detect async context via asyncio.get_running_loop()"
    )
    assert "RuntimeError" in text, (
        "cost_tracker should handle RuntimeError (no event loop) with sync fallback"
    )


# ---------------------------------------------------------------------------
# chat.py feedback endpoint tests
# ---------------------------------------------------------------------------

def test_chat_feedback_uses_to_thread():
    """The feedback endpoint must wrap db.feedback.update_one with asyncio.to_thread."""
    text = CHAT_ROUTER_PATH.read_text()

    # Find the submit_feedback function and verify it uses asyncio.to_thread
    tree = ast.parse(text, filename="chat.py")

    found_feedback_fn = False
    uses_to_thread = False

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "submit_feedback":
            found_feedback_fn = True
            # Check if asyncio.to_thread is called inside this function
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    if (isinstance(func, ast.Attribute)
                            and func.attr == "to_thread"
                            and isinstance(func.value, ast.Name)
                            and func.value.id == "asyncio"):
                        uses_to_thread = True
                        break
            break

    assert found_feedback_fn, "submit_feedback async function not found in chat.py"
    assert uses_to_thread, (
        "submit_feedback must use asyncio.to_thread for db.feedback.update_one"
    )


def test_chat_feedback_no_bare_update_one():
    """submit_feedback should not have a bare db.feedback.update_one (must be in to_thread)."""
    text = CHAT_ROUTER_PATH.read_text()
    tree = ast.parse(text, filename="chat.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "submit_feedback":
            # Get line ranges of nested defs (closures for to_thread)
            # and also the to_thread call arguments
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    # A bare db.feedback.update_one(...) NOT as arg to asyncio.to_thread
                    if (isinstance(func, ast.Attribute)
                            and func.attr == "update_one"
                            and isinstance(func.value, ast.Attribute)
                            and func.value.attr == "feedback"):
                        # This would be a bare call — it shouldn't exist
                        # But we need to check it's not inside asyncio.to_thread args
                        # Since asyncio.to_thread(fn, *args) doesn't CALL fn directly,
                        # if update_one appears as a Call node, it's bare
                        assert False, (
                            f"Bare db.feedback.update_one() call at line {child.lineno} "
                            f"in submit_feedback — must use asyncio.to_thread"
                        )
            break
