"""Shared fixtures for unit tests.

These tests do NOT require running services (Redis, MongoDB, Gemini).
All external dependencies are mocked.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

# Ensure backend/ is on sys.path so `from config import ...` works
_backend_dir = str(Path(__file__).resolve().parents[2])
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from tests.unit.mocks import MockLLM, MockRAG, MockIntent, MockMemory, MockProduct, MockSafety


# ---------------------------------------------------------------------------
# MongoDB mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mongo_collection():
    """A MagicMock that behaves like a pymongo Collection."""
    coll = MagicMock()
    coll.find.return_value = iter([])
    coll.find_one.return_value = None
    coll.insert_one.return_value = MagicMock(inserted_id="fake_id")
    coll.update_one.return_value = MagicMock(modified_count=1)
    coll.delete_one.return_value = MagicMock(deleted_count=1)
    coll.count_documents.return_value = 0
    return coll


@pytest.fixture
def mock_mongo_db(mock_mongo_collection):
    """A MagicMock that behaves like a pymongo Database."""
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=mock_mongo_collection)
    db.feedback = mock_mongo_collection
    db.products = mock_mongo_collection
    db.model_cost_logs = mock_mongo_collection
    return db


# ---------------------------------------------------------------------------
# Port mock fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    return MockLLM()


@pytest.fixture
def mock_rag():
    return MockRAG()


@pytest.fixture
def mock_intent():
    return MockIntent()


@pytest.fixture
def mock_memory():
    return MockMemory()


@pytest.fixture
def mock_product():
    return MockProduct()


@pytest.fixture
def mock_safety():
    return MockSafety()
