"""Tests for CompanionEngine dependency injection.

Verifies that:
1. Constructor accepts port kwargs (llm, intent_agent, memory_service, etc.)
2. Injected ports are used instead of singleton factories
3. Existing no-args constructor signature is preserved (backwards compat)
"""
import ast
from pathlib import Path

ENGINE_PATH = Path(__file__).resolve().parents[2] / "services" / "companion_engine.py"


def test_constructor_accepts_port_kwargs():
    """CompanionEngine.__init__ should accept keyword-only port parameters."""
    tree = ast.parse(ENGINE_PATH.read_text(), filename="companion_engine.py")

    init_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CompanionEngine":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    init_node = item
                    break
            break

    assert init_node is not None, "CompanionEngine.__init__ not found"

    # Collect all parameter names (excluding self)
    args = init_node.args
    all_params = set()
    for arg in args.args[1:]:  # skip self
        all_params.add(arg.arg)
    for arg in args.kwonlyargs:
        all_params.add(arg.arg)

    expected_ports = {"llm", "intent_agent", "memory_service", "product_service"}
    for port in expected_ports:
        assert port in all_params, (
            f"CompanionEngine.__init__ missing '{port}' parameter. "
            f"Found: {all_params}"
        )


def test_constructor_ports_are_keyword_only():
    """Port parameters should be keyword-only (after *)."""
    tree = ast.parse(ENGINE_PATH.read_text(), filename="companion_engine.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CompanionEngine":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    kwonly_names = {a.arg for a in item.args.kwonlyargs}
                    for port in ("llm", "intent_agent", "memory_service", "product_service"):
                        assert port in kwonly_names, (
                            f"'{port}' should be keyword-only (after *). "
                            f"Keyword-only args: {kwonly_names}"
                        )
                    return

    assert False, "CompanionEngine.__init__ not found"


def test_constructor_ports_default_to_none():
    """All port parameters should default to None (lazy factory fallback)."""
    tree = ast.parse(ENGINE_PATH.read_text(), filename="companion_engine.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CompanionEngine":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    defaults = item.args.kw_defaults
                    kwonly = item.args.kwonlyargs
                    for i, arg in enumerate(kwonly):
                        default = defaults[i] if i < len(defaults) else None
                        assert default is not None and isinstance(default, ast.Constant) and default.value is None, (
                            f"kwarg '{arg.arg}' should default to None, got {ast.dump(default) if default else 'no default'}"
                        )
                    return

    assert False, "CompanionEngine.__init__ not found"


def test_backwards_compat_rag_pipeline_positional():
    """rag_pipeline should still be accepted as the first positional arg."""
    tree = ast.parse(ENGINE_PATH.read_text(), filename="companion_engine.py")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CompanionEngine":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    positional_args = [a.arg for a in item.args.args]
                    assert "rag_pipeline" in positional_args, (
                        "rag_pipeline must remain a positional arg for backwards compat"
                    )
                    return

    assert False, "CompanionEngine.__init__ not found"


def test_conditional_factory_fallback():
    """When port is None, the constructor should call the singleton factory."""
    text = ENGINE_PATH.read_text()
    # Check that conditional patterns exist for fallback
    assert "if llm is not None" in text, "Missing conditional for llm port injection"
    assert "if intent_agent is not None" in text or "intent_agent if intent_agent" in text, (
        "Missing conditional for intent_agent port injection"
    )
    assert "get_intent_agent()" in text, "Factory fallback for intent_agent missing"
    assert "get_product_service()" in text, "Factory fallback for product_service missing"
    assert "get_memory_service" in text, "Factory fallback for memory_service missing"
