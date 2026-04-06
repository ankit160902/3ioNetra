"""Tests that ProductService wraps all pymongo calls with asyncio.to_thread."""
import ast
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

PRODUCT_SERVICE_PATH = Path(__file__).resolve().parents[2] / "services" / "product_service.py"


# ---------------------------------------------------------------------------
# AST structural test
# ---------------------------------------------------------------------------

def _get_nested_def_line_ranges(async_func_node: ast.AsyncFunctionDef) -> list:
    """Return (start, end) line ranges of all nested regular `def` inside an async def."""
    ranges = []
    for child in ast.walk(async_func_node):
        if isinstance(child, ast.FunctionDef):
            end_line = getattr(child, "end_lineno", child.lineno + 50)
            ranges.append((child.lineno, end_line))
    return ranges


def _line_in_nested_def(lineno: int, ranges: list) -> bool:
    return any(start <= lineno <= end for start, end in ranges)


def _find_bare_mongo_calls(filepath: Path) -> list:
    """Find self.collection.find() directly in async function bodies (not in nested defs)."""
    tree = ast.parse(filepath.read_text(), filename=str(filepath))
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue

        nested_ranges = _get_nested_def_line_ranges(node)

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if (isinstance(func, ast.Attribute)
                    and func.attr == "find"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "collection"):
                if not _line_in_nested_def(child.lineno, nested_ranges):
                    violations.append(
                        f"async def {node.name}() line {child.lineno}: "
                        f"bare self.collection.find()"
                    )
    return violations


def test_no_bare_mongo_find_in_async_methods():
    """All self.collection.find() in async methods must be inside asyncio.to_thread closures."""
    violations = _find_bare_mongo_calls(PRODUCT_SERVICE_PATH)
    assert violations == [], (
        "Found bare pymongo calls in async functions:\n" + "\n".join(violations)
    )


def test_asyncio_import_present():
    """product_service.py must import asyncio."""
    text = PRODUCT_SERVICE_PATH.read_text()
    assert "import asyncio" in text


def test_to_thread_calls_exist():
    """product_service.py must use asyncio.to_thread for DB calls."""
    text = PRODUCT_SERVICE_PATH.read_text()
    count = text.count("asyncio.to_thread")
    assert count >= 4, f"Expected >=4 asyncio.to_thread calls, found {count}"


# ---------------------------------------------------------------------------
# Runtime tests — load module directly from file to avoid package chain
# ---------------------------------------------------------------------------

def _load_product_service():
    """Load product_service.py in isolation with mocked dependencies."""
    import types

    mock_config = types.ModuleType("config")
    mock_config.settings = MagicMock()
    mock_config.settings.PRODUCT_MIN_RELEVANCE_SCORE = 15.0

    mock_auth = types.ModuleType("services.auth_service")
    mock_auth.get_mongo_client = MagicMock(return_value=None)

    # Create a minimal 'services' package so relative imports work
    mock_services_pkg = types.ModuleType("services")
    mock_services_pkg.__path__ = [str(PRODUCT_SERVICE_PATH.parent)]
    mock_services_pkg.auth_service = mock_auth

    saved = {}
    mocks = {
        "config": mock_config,
        "services": mock_services_pkg,
        "services.auth_service": mock_auth,
    }
    for mod_name in mocks:
        saved[mod_name] = sys.modules.get(mod_name)
        sys.modules[mod_name] = mocks[mod_name]

    # Remove any cached product_service module
    sys.modules.pop("services.product_service", None)

    try:
        spec = importlib.util.spec_from_file_location(
            "services.product_service",
            str(PRODUCT_SERVICE_PATH),
            submodule_search_locations=[],
        )
        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = "services"
        sys.modules["services.product_service"] = mod
        spec.loader.exec_module(mod)
        return mod.ProductService
    finally:
        for mod_name, orig in saved.items():
            if orig is None:
                sys.modules.pop(mod_name, None)
            else:
                sys.modules[mod_name] = orig
        sys.modules.pop("services.product_service", None)


async def test_get_all_products_runs_in_thread():
    """get_all_products executes pymongo via asyncio.to_thread (no event loop block)."""
    ProductService = _load_product_service()
    svc = ProductService.__new__(ProductService)
    mock_coll = MagicMock()
    mock_coll.find.return_value = iter([
        {"_id": "obj1", "name": "Rudraksha", "is_active": True},
    ])
    svc.collection = mock_coll

    result = await svc.get_all_products()
    assert len(result) == 1
    assert result[0]["name"] == "Rudraksha"
    mock_coll.find.assert_called_once()


async def test_get_all_products_none_collection():
    """get_all_products returns [] when collection is None."""
    ProductService = _load_product_service()
    svc = ProductService.__new__(ProductService)
    svc.collection = None
    assert await svc.get_all_products() == []


async def test_get_recommended_products_runs_in_thread():
    """get_recommended_products executes via asyncio.to_thread."""
    ProductService = _load_product_service()
    svc = ProductService.__new__(ProductService)
    mock_coll = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = iter([
        {"_id": "1", "name": "Puja Thali", "is_active": True},
    ])
    mock_coll.find.return_value = mock_cursor
    svc.collection = mock_coll

    result = await svc.get_recommended_products(limit=4)
    assert len(result) == 1
    assert result[0]["name"] == "Puja Thali"


async def test_get_recommended_products_fallback():
    """Falls back to all active products if category returns empty."""
    ProductService = _load_product_service()
    svc = ProductService.__new__(ProductService)
    mock_coll = MagicMock()

    call_count = [0]
    def fake_find(query):
        call_count[0] += 1
        cursor = MagicMock()
        if call_count[0] == 1:
            cursor.limit.return_value = iter([])
        else:
            cursor.limit.return_value = iter([
                {"_id": "2", "name": "Default", "is_active": True},
            ])
        return cursor

    mock_coll.find = fake_find
    svc.collection = mock_coll

    result = await svc.get_recommended_products(category="Nonexistent", limit=4)
    assert len(result) == 1
    assert result[0]["name"] == "Default"
    assert call_count[0] == 2  # Primary + fallback
