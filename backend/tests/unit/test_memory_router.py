"""Unit tests for routers/memory.py — the user-facing /api/memory panel.

Tests call the endpoint handlers directly (not through TestClient) to
match the existing project convention. MongoDB and RAG pipeline are
mocked; auth is supplied as a dict kwarg rather than Depends.

Critical invariants this suite protects:
    - Every endpoint requires auth (raises 401 for anonymous)
    - Every query filters by user_id (user cannot touch another user's data)
    - Soft delete is default, hard delete is opt-in
    - Manual POST marks source='manual_user_add' and sets invalid_at=None
    - Profile reset requires explicit confirm flag
    - Crisis sensitivity is never writable via public endpoints
    - Internal fields (embedding, user_id) never leak into responses
    - prior_crisis_context is stripped from profile responses
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from fastapi import HTTPException

from models.api_schemas import (
    MemoryCreateRequest,
    MemoryListResponse,
    MemoryPatchRequest,
    ProfileResetRequest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime.utcnow()


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.user_memories.find.return_value.sort.return_value = []
    db.user_memories.find_one = MagicMock(return_value=None)
    db.user_memories.insert_one = MagicMock(
        return_value=MagicMock(inserted_id="new_oid")
    )
    db.user_memories.update_one = MagicMock(
        return_value=MagicMock(matched_count=1, modified_count=1)
    )
    db.user_memories.update_many = MagicMock(
        return_value=MagicMock(modified_count=0)
    )
    db.user_memories.delete_one = MagicMock(
        return_value=MagicMock(deleted_count=1)
    )
    db.user_profiles.find_one = MagicMock(return_value=None)
    db.user_profiles.update_one = MagicMock(
        return_value=MagicMock(modified_count=1, upserted_id=None)
    )
    return db


@pytest.fixture
def mock_rag():
    rag = MagicMock()
    rag.generate_embeddings = AsyncMock(
        return_value=np.array([0.1] * 8, dtype=np.float32)
    )
    return rag


@pytest.fixture
def router(monkeypatch, mock_db, mock_rag):
    from routers import memory
    from routers import dependencies as router_deps

    # routers/memory.py binds `get_mongo_client` at import time via
    # `from services.auth_service import get_mongo_client`, so the
    # monkeypatch must target the router module's LOCAL reference,
    # not the auth_service source. Same story for get_rag_pipeline
    # which the handlers import function-locally from dependencies.
    monkeypatch.setattr(memory, "get_mongo_client", lambda: mock_db)
    monkeypatch.setattr(router_deps, "get_rag_pipeline", lambda: mock_rag)

    # Silence the cache invalidation hook used in reset_profile
    from services import memory_reader

    async def noop_invalidate(user_id):
        return None

    monkeypatch.setattr(memory_reader, "invalidate_profile_cache", noop_invalidate)
    return memory


_USER = {"id": "u1", "email": "alice@example.com"}


def _make_memory_doc(
    _id: str = "507f1f77bcf86cd799439011",
    user_id: str = "u1",
    text: str = "User is a software engineer",
    importance: int = 5,
    sensitivity: str = "personal",
    invalid_at=None,
    source: str = "extracted",
):
    return {
        "_id": _id,
        "user_id": user_id,
        "text": text,
        "embedding": [0.1] * 8,  # Must NEVER appear in response
        "importance": importance,
        "sensitivity": sensitivity,
        "tone_marker": "neutral",
        "valid_at": _NOW,
        "invalid_at": invalid_at,
        "last_accessed_at": None,
        "access_count": 0,
        "source": source,
        "provenance": {
            "session_id": "s1",
            "conversation_id": "c1",
            "turn_number": 3,
        },
        "created_at": _NOW,
    }


# ---------------------------------------------------------------------------
# Helpers (private module functions)
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_doc_to_list_item_strips_private_fields(self, router):
        doc = _make_memory_doc()
        item = router._doc_to_list_item(doc)
        dumped = item.model_dump()
        # Private fields MUST NOT leak
        assert "embedding" not in dumped
        assert "user_id" not in dumped
        # Public fields are present
        assert dumped["memory_id"] == "507f1f77bcf86cd799439011"
        assert dumped["text"] == "User is a software engineer"
        assert dumped["source"] == "extracted"

    def test_doc_to_list_item_includes_provenance(self, router):
        doc = _make_memory_doc()
        item = router._doc_to_list_item(doc)
        assert item.provenance.session_id == "s1"
        assert item.provenance.conversation_id == "c1"
        assert item.provenance.turn_number == 3

    def test_doc_to_profile_strips_crisis_context(self, router):
        profile_doc = {
            "user_id": "u1",
            "relational_narrative": "A warm seeker",
            "prior_crisis_flag": True,
            "prior_crisis_context": "VERBATIM CRISIS META-FACT — MUST NOT LEAK",
            "prior_crisis_count": 2,
        }
        resp = router._doc_to_profile_response(profile_doc, "u1")
        dumped = resp.model_dump()
        assert dumped["prior_crisis_flag"] is True
        assert dumped["prior_crisis_count"] == 2
        # prior_crisis_context is NEVER exposed
        assert "prior_crisis_context" not in dumped

    def test_doc_to_profile_empty_doc_returns_default(self, router):
        resp = router._doc_to_profile_response(None, "u1")
        assert resp.user_id == "u1"
        assert resp.relational_narrative == ""
        assert resp.prior_crisis_flag is False

    def test_to_object_id_bad_input_returns_none(self, router):
        assert router._to_object_id(None) is None
        assert router._to_object_id("") is None
        assert router._to_object_id("not_hex") is None

    def test_require_auth_anonymous_raises_401(self, router):
        with pytest.raises(HTTPException) as exc_info:
            router._require_auth(None)
        assert exc_info.value.status_code == 401

    def test_require_auth_missing_id_raises_401(self, router):
        with pytest.raises(HTTPException) as exc_info:
            router._require_auth({"email": "alice@example.com"})
        assert exc_info.value.status_code == 401

    def test_require_auth_returns_user_id(self, router):
        assert router._require_auth({"id": "u1"}) == "u1"


# ---------------------------------------------------------------------------
# GET /api/memory
# ---------------------------------------------------------------------------

class TestListMemories:
    @pytest.mark.asyncio
    async def test_requires_auth(self, router):
        with pytest.raises(HTTPException) as exc_info:
            await router.list_memories(include_invalidated=False, user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_valid_memories_by_default(self, router, mock_db):
        mock_db.user_memories.find.return_value.sort.return_value = [
            _make_memory_doc(_id="a"),
            _make_memory_doc(_id="b"),
        ]
        result = await router.list_memories(include_invalidated=False, user=_USER)
        assert isinstance(result, MemoryListResponse)
        assert result.total == 2
        # Verify the find query filters by user_id AND invalid_at=None
        find_call = mock_db.user_memories.find.call_args
        query = find_call.args[0]
        assert query["user_id"] == "u1"
        assert query["invalid_at"] is None

    @pytest.mark.asyncio
    async def test_include_invalidated_removes_invalid_at_filter(
        self, router, mock_db
    ):
        mock_db.user_memories.find.return_value.sort.return_value = []
        await router.list_memories(include_invalidated=True, user=_USER)
        query = mock_db.user_memories.find.call_args.args[0]
        assert query["user_id"] == "u1"
        assert "invalid_at" not in query  # Not filtered when include_invalidated=True

    @pytest.mark.asyncio
    async def test_attaches_profile(self, router, mock_db):
        mock_db.user_memories.find.return_value.sort.return_value = []
        mock_db.user_profiles.find_one.return_value = {
            "user_id": "u1",
            "relational_narrative": "A gentle seeker",
            "spiritual_themes": ["bhakti"],
        }
        result = await router.list_memories(include_invalidated=False, user=_USER)
        assert result.profile.relational_narrative == "A gentle seeker"
        assert "bhakti" in result.profile.spiritual_themes


# ---------------------------------------------------------------------------
# GET /api/memory/profile
# ---------------------------------------------------------------------------

class TestGetProfile:
    @pytest.mark.asyncio
    async def test_requires_auth(self, router):
        with pytest.raises(HTTPException) as exc_info:
            await router.get_profile(user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_empty_profile_for_new_user(self, router, mock_db):
        mock_db.user_profiles.find_one.return_value = None
        resp = await router.get_profile(user=_USER)
        assert resp.user_id == "u1"
        assert resp.relational_narrative == ""

    @pytest.mark.asyncio
    async def test_query_filters_by_user_id(self, router, mock_db):
        await router.get_profile(user=_USER)
        find_call = mock_db.user_profiles.find_one.call_args
        assert find_call.args[0] == {"user_id": "u1"}


# ---------------------------------------------------------------------------
# POST /api/memory
# ---------------------------------------------------------------------------

class TestAddMemory:
    @pytest.mark.asyncio
    async def test_requires_auth(self, router):
        body = MemoryCreateRequest(text="I run daily", importance=5)
        with pytest.raises(HTTPException) as exc_info:
            await router.add_memory(body=body, user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_inserts_manual_user_add_source(self, router, mock_db):
        body = MemoryCreateRequest(text="I run daily", importance=6)
        item = await router.add_memory(body=body, user=_USER)
        assert item.source == "manual_user_add"
        assert item.text == "I run daily"
        assert item.importance == 6
        assert item.invalid_at is None

        # The inserted doc should have user_id and manual_user_add source
        insert_call = mock_db.user_memories.insert_one.call_args
        doc = insert_call.args[0]
        assert doc["user_id"] == "u1"
        assert doc["source"] == "manual_user_add"
        assert doc["invalid_at"] is None
        assert doc["valid_at"] is not None

    @pytest.mark.asyncio
    async def test_crisis_sensitivity_is_coerced_to_personal(self, router, mock_db):
        """Crisis tier must NEVER be writable via the public API."""
        body = MemoryCreateRequest(
            text="anything", importance=5, sensitivity="crisis"
        )
        # The schema validator coerces crisis → personal
        assert body.sensitivity == "personal"
        await router.add_memory(body=body, user=_USER)
        doc = mock_db.user_memories.insert_one.call_args.args[0]
        assert doc["sensitivity"] == "personal"

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_500(self, router, mock_rag):
        mock_rag.generate_embeddings.side_effect = RuntimeError("embed boom")
        body = MemoryCreateRequest(text="hello", importance=5)
        with pytest.raises(HTTPException) as exc_info:
            await router.add_memory(body=body, user=_USER)
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# PATCH /api/memory/{id}
# ---------------------------------------------------------------------------

class TestEditMemory:
    @pytest.mark.asyncio
    async def test_requires_auth(self, router):
        body = MemoryPatchRequest(text="new text")
        with pytest.raises(HTTPException) as exc_info:
            await router.edit_memory(
                memory_id="507f1f77bcf86cd799439011", body=body, user=None
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_bad_oid_returns_400(self, router):
        body = MemoryPatchRequest(text="hello")
        with pytest.raises(HTTPException) as exc_info:
            await router.edit_memory(memory_id="garbage", body=body, user=_USER)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_empty_patch_returns_400(self, router):
        body = MemoryPatchRequest()  # no text, no sensitivity
        with pytest.raises(HTTPException) as exc_info:
            await router.edit_memory(
                memory_id="507f1f77bcf86cd799439011", body=body, user=_USER
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, router, mock_db):
        mock_db.user_memories.update_one.return_value = MagicMock(
            matched_count=0, modified_count=0
        )
        body = MemoryPatchRequest(text="new text")
        with pytest.raises(HTTPException) as exc_info:
            await router.edit_memory(
                memory_id="507f1f77bcf86cd799439011", body=body, user=_USER
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_text_patch_reembeds(self, router, mock_db, mock_rag):
        mock_db.user_memories.find_one.return_value = _make_memory_doc(
            text="new text"
        )
        body = MemoryPatchRequest(text="new text")
        await router.edit_memory(
            memory_id="507f1f77bcf86cd799439011", body=body, user=_USER
        )
        mock_rag.generate_embeddings.assert_called_once_with("new text")
        update_body = mock_db.user_memories.update_one.call_args.args[1]
        assert "text" in update_body["$set"]
        assert "embedding" in update_body["$set"]

    @pytest.mark.asyncio
    async def test_update_query_enforces_user_id_isolation(self, router, mock_db):
        mock_db.user_memories.find_one.return_value = _make_memory_doc()
        body = MemoryPatchRequest(text="new text")
        await router.edit_memory(
            memory_id="507f1f77bcf86cd799439011", body=body, user=_USER
        )
        filter_arg = mock_db.user_memories.update_one.call_args.args[0]
        # The filter MUST include user_id — otherwise a guessed OID could
        # patch another user's memory
        assert filter_arg["user_id"] == "u1"
        assert filter_arg["invalid_at"] is None


# ---------------------------------------------------------------------------
# DELETE /api/memory/{id}
# ---------------------------------------------------------------------------

class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_requires_auth(self, router):
        with pytest.raises(HTTPException) as exc_info:
            await router.delete_memory(
                memory_id="507f1f77bcf86cd799439011", hard=False, user=None
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_bad_oid_returns_400(self, router):
        with pytest.raises(HTTPException) as exc_info:
            await router.delete_memory(memory_id="garbage", hard=False, user=_USER)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_soft_delete_sets_invalid_at(self, router, mock_db):
        result = await router.delete_memory(
            memory_id="507f1f77bcf86cd799439011", hard=False, user=_USER
        )
        assert result.deleted is True
        assert result.hard is False
        # Soft delete uses update_one with invalid_at set
        mock_db.user_memories.update_one.assert_called_once()
        update_body = mock_db.user_memories.update_one.call_args.args[1]
        assert "invalid_at" in update_body["$set"]
        # Hard delete NOT called
        mock_db.user_memories.delete_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_hard_delete_calls_delete_one(self, router, mock_db):
        result = await router.delete_memory(
            memory_id="507f1f77bcf86cd799439011", hard=True, user=_USER
        )
        assert result.deleted is True
        assert result.hard is True
        mock_db.user_memories.delete_one.assert_called_once()
        # Soft delete path NOT called
        mock_db.user_memories.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_query_enforces_user_id_isolation(self, router, mock_db):
        await router.delete_memory(
            memory_id="507f1f77bcf86cd799439011", hard=False, user=_USER
        )
        filter_arg = mock_db.user_memories.update_one.call_args.args[0]
        assert filter_arg["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, router, mock_db):
        mock_db.user_memories.update_one.return_value = MagicMock(
            matched_count=0, modified_count=0
        )
        with pytest.raises(HTTPException) as exc_info:
            await router.delete_memory(
                memory_id="507f1f77bcf86cd799439011", hard=False, user=_USER
            )
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/memory?before=
# ---------------------------------------------------------------------------

class TestBatchInvalidate:
    @pytest.mark.asyncio
    async def test_requires_auth(self, router):
        with pytest.raises(HTTPException) as exc_info:
            await router.batch_invalidate_before(before="2026-01-01", user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_bad_date_returns_400(self, router):
        with pytest.raises(HTTPException) as exc_info:
            await router.batch_invalidate_before(before="not-a-date", user=_USER)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_many_filters_by_user_and_date(self, router, mock_db):
        mock_db.user_memories.update_many.return_value = MagicMock(
            modified_count=5
        )
        result = await router.batch_invalidate_before(
            before="2026-03-01", user=_USER
        )
        assert result.invalidated_count == 5
        filter_arg = mock_db.user_memories.update_many.call_args.args[0]
        assert filter_arg["user_id"] == "u1"
        assert filter_arg["invalid_at"] is None
        assert "created_at" in filter_arg and "$lt" in filter_arg["created_at"]


# ---------------------------------------------------------------------------
# POST /api/memory/profile/reset
# ---------------------------------------------------------------------------

class TestResetProfile:
    @pytest.mark.asyncio
    async def test_requires_auth(self, router):
        body = ProfileResetRequest(confirm=True)
        with pytest.raises(HTTPException) as exc_info:
            await router.reset_profile(body=body, user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_requires_confirm_true(self, router):
        body = ProfileResetRequest(confirm=False)
        with pytest.raises(HTTPException) as exc_info:
            await router.reset_profile(body=body, user=_USER)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_resets_narrative_and_lists(self, router, mock_db):
        body = ProfileResetRequest(confirm=True)
        result = await router.reset_profile(body=body, user=_USER)
        assert result.reset is True
        update_call = mock_db.user_profiles.update_one.call_args
        filter_arg = update_call.args[0]
        update_body = update_call.args[1]
        set_doc = update_body["$set"]
        assert filter_arg == {"user_id": "u1"}
        assert set_doc["relational_narrative"] == ""
        assert set_doc["spiritual_themes"] == []
        assert set_doc["ongoing_concerns"] == []
        assert set_doc["tone_preferences"] == []
        assert set_doc["people_mentioned"] == []
        assert set_doc["importance_since_reflection"] == 0
        assert set_doc["reflection_count"] == 0
        # Crisis flag is NOT reset — it survives profile wipes
        assert "prior_crisis_flag" not in set_doc
        assert "prior_crisis_context" not in set_doc
        assert update_call.kwargs.get("upsert") is True
