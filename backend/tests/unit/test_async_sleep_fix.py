"""Verify no blocking time.sleep() calls exist in async production code."""
import ast
from pathlib import Path


# Production source directories (exclude tests/ and scripts/)
PRODUCTION_DIRS = ["llm", "services", "routers", "rag", "models"]


def _find_blocking_sleeps_in_file(filepath: Path) -> list:
    """Parse a Python file's AST and find time.sleep() inside async functions."""
    violations = []
    try:
        tree = ast.parse(filepath.read_text(errors="ignore"), filename=str(filepath))
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef,)):
            continue
        # Walk the body of each async function
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                # Match time.sleep(...)
                if (isinstance(func, ast.Attribute)
                        and func.attr == "sleep"
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "time"):
                    violations.append(
                        f"{filepath.name}:{child.lineno} — "
                        f"time.sleep() in async def {node.name}()"
                    )
    return violations


def test_no_blocking_sleep_in_async_production_code():
    """Ensure no production async function uses time.sleep() (should use asyncio.sleep)."""
    backend_dir = Path(__file__).resolve().parents[2]
    all_violations = []

    for dirname in PRODUCTION_DIRS:
        source_dir = backend_dir / dirname
        if not source_dir.exists():
            continue
        for py_file in source_dir.rglob("*.py"):
            all_violations.extend(_find_blocking_sleeps_in_file(py_file))

    # Also check top-level files like main.py
    for py_file in backend_dir.glob("*.py"):
        all_violations.extend(_find_blocking_sleeps_in_file(py_file))

    assert all_violations == [], (
        "Blocking time.sleep() found in async functions "
        "(use 'await asyncio.sleep()' instead):\n" +
        "\n".join(all_violations)
    )
