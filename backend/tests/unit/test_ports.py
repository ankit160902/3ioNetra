"""Tests for port interface definitions.

Validates that:
1. All port protocols are importable and well-formed
2. Port protocols have the expected method names
3. All methods have type annotations
"""
import ast
import inspect
from pathlib import Path

import pytest


PORTS_DIR = Path(__file__).resolve().parents[2] / "ports"


# ---------------------------------------------------------------------------
# Test that all port files exist and are importable
# ---------------------------------------------------------------------------

PORT_FILES = ["llm.py", "rag.py", "intent.py", "memory.py", "product.py", "safety.py"]


@pytest.mark.parametrize("filename", PORT_FILES)
def test_port_file_exists(filename):
    assert (PORTS_DIR / filename).exists(), f"ports/{filename} missing"


def test_ports_init_imports_all():
    """ports/__init__.py should export all port classes."""
    init_text = (PORTS_DIR / "__init__.py").read_text()
    for name in ["LLMPort", "RAGPort", "IntentPort", "MemoryPort", "ProductPort", "SafetyPort"]:
        assert name in init_text, f"{name} not exported from ports/__init__.py"


# ---------------------------------------------------------------------------
# Test that each port has the expected methods
# ---------------------------------------------------------------------------

EXPECTED_METHODS = {
    "llm.py": {
        "LLMPort": ["generate_response", "generate_response_stream"],
    },
    "rag.py": {
        "RAGPort": ["search", "generate_embeddings"],
    },
    "intent.py": {
        "IntentPort": ["analyze_intent"],
    },
    "memory.py": {
        "MemoryPort": ["store_memory", "retrieve_relevant_memories", "set_rag_pipeline"],
    },
    "product.py": {
        "ProductPort": ["search_products", "get_recommended_products"],
    },
    "safety.py": {
        "SafetyPort": ["check_crisis_signals", "validate_response", "append_professional_help"],
    },
}


@pytest.mark.parametrize("filename,classes", list(EXPECTED_METHODS.items()))
def test_port_has_expected_methods(filename, classes):
    """Each port Protocol should define the expected method signatures."""
    tree = ast.parse((PORTS_DIR / filename).read_text(), filename=filename)

    for class_name, method_names in classes.items():
        # Find the class
        class_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                class_node = node
                break
        assert class_node is not None, f"Class {class_name} not found in {filename}"

        # Check methods exist
        defined_methods = set()
        for item in ast.walk(class_node):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not item.name.startswith("_"):
                    defined_methods.add(item.name)

        for method in method_names:
            assert method in defined_methods, (
                f"{class_name}.{method} not defined in ports/{filename}. "
                f"Found: {defined_methods}"
            )


# ---------------------------------------------------------------------------
# Test that ports use Protocol correctly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", PORT_FILES)
def test_port_uses_protocol(filename):
    """Each port file should define a class inheriting from Protocol."""
    text = (PORTS_DIR / filename).read_text()
    assert "Protocol" in text, f"ports/{filename} does not use Protocol"
    assert "runtime_checkable" in text, f"ports/{filename} should use @runtime_checkable"


@pytest.mark.parametrize("filename", PORT_FILES)
def test_port_methods_have_return_annotations(filename):
    """Every method in a port should have a return type annotation."""
    tree = ast.parse((PORTS_DIR / filename).read_text(), filename=filename)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in ast.walk(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_") and item.name != "__init__":
                        continue
                    # Properties are fine with just ... body
                    assert item.returns is not None or any(
                        isinstance(d, ast.Name) and d.id == "property"
                        for d in item.decorator_list
                    ), (
                        f"{node.name}.{item.name}() in ports/{filename} "
                        f"missing return type annotation"
                    )
