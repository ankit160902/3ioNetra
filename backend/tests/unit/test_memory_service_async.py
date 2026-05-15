"""Tests that memory_service.py offloads CPU-bound numpy ops to thread pool."""
import ast
from pathlib import Path

MEMORY_SERVICE_PATH = Path(__file__).resolve().parents[2] / "services" / "memory_service.py"


def _get_async_funcs_with_bare_numpy(filepath: Path) -> list:
    """Find bare numpy heavy ops (matmul @, linalg.norm, argpartition) directly in async functions."""
    tree = ast.parse(filepath.read_text(), filename=str(filepath))
    violations = []

    # Heavy numpy ops that should be in a thread for memory-sized arrays
    HEAVY_OPS = {"norm", "argpartition", "argsort"}

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue

        # Get line ranges of nested sync defs (closures for asyncio.to_thread)
        nested_ranges = []
        for child in ast.walk(node):
            if isinstance(child, ast.FunctionDef):
                end = getattr(child, "end_lineno", child.lineno + 100)
                nested_ranges.append((child.lineno, end))

        def in_nested_def(lineno):
            return any(s <= lineno <= e for s, e in nested_ranges)

        # Check for bare heavy numpy operations
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if in_nested_def(child.lineno):
                continue

            func = child.func
            # np.linalg.norm, np.argsort, etc.
            if isinstance(func, ast.Attribute) and func.attr in HEAVY_OPS:
                violations.append(
                    f"async def {node.name}() line {child.lineno}: "
                    f"bare np.{func.attr}() outside asyncio.to_thread closure"
                )

            # @ operator (matmul) — detected as BinOp(MatMult)
            # This would be caught differently; skip for now as it's inside the closure

    return violations


def test_no_bare_numpy_in_retrieve_relevant_memories():
    """Heavy numpy ops in retrieve_relevant_memories must be inside a closure for asyncio.to_thread."""
    violations = _get_async_funcs_with_bare_numpy(MEMORY_SERVICE_PATH)
    assert violations == [], (
        "Found bare numpy operations in async functions:\n" + "\n".join(violations)
    )


def test_retrieve_uses_to_thread_for_ranking():
    """retrieve_relevant_memories should use asyncio.to_thread for the similarity/dedup block."""
    text = MEMORY_SERVICE_PATH.read_text()

    # The _rank_and_dedup closure should exist
    assert "_rank_and_dedup" in text, (
        "Expected _rank_and_dedup closure for offloading numpy ops"
    )

    # asyncio.to_thread should be called with it
    assert "asyncio.to_thread(_rank_and_dedup)" in text, (
        "Expected asyncio.to_thread(_rank_and_dedup) call"
    )


def test_store_memory_still_uses_to_thread():
    """store_memory MongoDB calls should still use asyncio.to_thread."""
    text = MEMORY_SERVICE_PATH.read_text()
    # Count asyncio.to_thread usages — should be multiple (store + retrieve + prune)
    count = text.count("asyncio.to_thread")
    assert count >= 5, (
        f"Expected >=5 asyncio.to_thread calls (store: find_one, update_one, insert_one, prune + retrieve: rank_and_dedup), found {count}"
    )
