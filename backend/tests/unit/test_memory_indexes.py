"""Tests for MongoDB index creation in LongTermMemoryService.

The dynamic memory system (Apr 2026) adds new indexes on user_memories
and a new user_profiles collection. These tests verify the index-creation
pass uses a mocked Mongo client — no real database needed.
"""
from unittest.mock import MagicMock

import pytest

from services.memory_service import LongTermMemoryService


@pytest.fixture
def mock_db():
    """Mock MongoDB client with user_memories and user_profiles collections."""
    db = MagicMock()
    db.user_memories = MagicMock()
    db.user_profiles = MagicMock()
    return db


@pytest.fixture
def service_with_mock(mock_db, monkeypatch):
    """LongTermMemoryService with mocked MongoDB client."""
    monkeypatch.setattr(
        "services.memory_service.get_mongo_client",
        lambda: mock_db,
    )
    return LongTermMemoryService()


class TestMemoryIndexes:
    def test_legacy_user_memories_indexes_still_created(self, service_with_mock, mock_db):
        """Existing indexes must survive the extension — backward compat."""
        calls = [c.args for c in mock_db.user_memories.create_index.call_args_list]
        # First call: plain user_id index
        assert ("user_id",) in calls or any(
            isinstance(c[0], str) and c[0] == "user_id" for c in calls
        )

    def test_user_memories_invalid_at_index_created(self, service_with_mock, mock_db):
        """New bi-temporal filter index: (user_id, invalid_at)."""
        calls = [c.args[0] for c in mock_db.user_memories.create_index.call_args_list]
        assert [("user_id", 1), ("invalid_at", 1)] in calls

    def test_user_memories_importance_index_created(self, service_with_mock, mock_db):
        """New top-k-by-importance index: (user_id, importance DESC)."""
        calls = [c.args[0] for c in mock_db.user_memories.create_index.call_args_list]
        assert [("user_id", 1), ("importance", -1)] in calls

    def test_user_memories_sensitivity_index_created(self, service_with_mock, mock_db):
        """New tier-filter index: (user_id, sensitivity)."""
        calls = [c.args[0] for c in mock_db.user_memories.create_index.call_args_list]
        assert [("user_id", 1), ("sensitivity", 1)] in calls

    def test_user_profiles_unique_index_created(self, service_with_mock, mock_db):
        """New collection gets a unique index on user_id."""
        # Unique index is passed as kwarg
        calls = mock_db.user_profiles.create_index.call_args_list
        assert len(calls) >= 1
        # Find the one with unique=True
        found_unique = any(
            c.kwargs.get("unique") is True
            and c.args[0] == [("user_id", 1)]
            for c in calls
        )
        assert found_unique, (
            f"Expected create_index([('user_id', 1)], unique=True) on user_profiles. "
            f"Got: {calls}"
        )

    def test_index_creation_is_idempotent_on_error(self, monkeypatch):
        """Failure of one index shouldn't prevent others — degrades gracefully."""
        db = MagicMock()

        # First create_index raises, rest succeed
        error_count = [0]
        def sometimes_fail(*args, **kwargs):
            error_count[0] += 1
            if error_count[0] == 1:
                raise RuntimeError("index already exists")
            return None

        db.user_memories.create_index.side_effect = sometimes_fail
        db.user_profiles.create_index = MagicMock()

        monkeypatch.setattr(
            "services.memory_service.get_mongo_client",
            lambda: db,
        )
        # Should NOT raise
        LongTermMemoryService()

    def test_no_db_is_safe(self, monkeypatch):
        """If MongoDB is unavailable, init must still succeed (degraded mode)."""
        monkeypatch.setattr(
            "services.memory_service.get_mongo_client",
            lambda: None,
        )
        service = LongTermMemoryService()
        assert service.db is None
