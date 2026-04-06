"""Verify langchain is not imported anywhere in the backend."""
import os
from pathlib import Path


def test_no_langchain_imports():
    """Ensure no Python file imports langchain (dead dependency was removed)."""
    backend_dir = Path(__file__).resolve().parents[2]
    violations = []

    for py_file in backend_dir.rglob("*.py"):
        # Skip venv / __pycache__ / this test file itself
        parts = py_file.parts
        if ".venv" in parts or "venv" in parts or "__pycache__" in parts:
            continue
        if py_file.resolve() == Path(__file__).resolve():
            continue

        text = py_file.read_text(errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "import langchain" in stripped or "from langchain" in stripped:
                rel = py_file.relative_to(backend_dir)
                violations.append(f"{rel}:{i}: {stripped}")

    assert violations == [], (
        f"Found langchain imports (should be removed):\n" +
        "\n".join(violations)
    )


def test_langchain_not_in_requirements():
    """Ensure langchain is not listed in requirements.txt."""
    req_file = Path(__file__).resolve().parents[2] / "requirements.txt"
    text = req_file.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "langchain" not in stripped.lower(), (
            f"langchain still in requirements.txt: {stripped}"
        )
