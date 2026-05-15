"""Unit tests for memory_writer (MemoryUpdater) — Gemini call #2 for the
dynamic memory system.

All tests use mocked LLM, RAG pipeline, prompt manager, and MongoDB — no
real external calls. Live Gemini tests for this module live under
``tests/integration/test_memory_live.py`` (opt-in).
"""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from models.llm_schemas import (
    ExtractedMemory,
    ExtractionResult,
    MemoryUpdateDecision,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_service():
    svc = MagicMock()
    svc.available = True
    svc.complete_json = AsyncMock()
    return svc


@pytest.fixture
def mock_prompt_manager():
    pm = MagicMock()
    pm.get_prompt = MagicMock(
        return_value=(
            "NEW FACT: {new_fact_text} ({new_fact_importance}/"
            "{new_fact_sensitivity}/{new_fact_tone})\n"
            "SIMILAR:\n{similar_memories_block}"
        )
    )
    return pm


@pytest.fixture
def mock_rag_pipeline():
    rag = MagicMock()
    rag.generate_embeddings = AsyncMock(
        return_value=np.array([0.1] * 8, dtype=np.float32)
    )
    return rag


@pytest.fixture
def mock_db():
    """A MongoDB-like mock with user_memories and user_profiles collections.

    ``user_memories.find`` returns an empty iterable by default so each test
    can override via ``mock_db.user_memories.find.return_value = [...]``.
    """
    db = MagicMock()
    db.user_memories.find.return_value = iter([])
    db.user_memories.insert_one = MagicMock(
        return_value=MagicMock(inserted_id="new_doc_id")
    )
    db.user_memories.update_one = MagicMock(
        return_value=MagicMock(modified_count=1)
    )
    db.user_profiles.update_one = MagicMock(
        return_value=MagicMock(modified_count=1, upserted_id=None)
    )
    return db


@pytest.fixture
def writer(monkeypatch, mock_llm_service, mock_prompt_manager, mock_rag_pipeline, mock_db):
    """Memory writer module with all lazy accessors monkeypatched."""
    from services import memory_writer

    monkeypatch.setattr(memory_writer, "get_llm_service", lambda: mock_llm_service)
    monkeypatch.setattr(memory_writer, "get_prompt_manager", lambda: mock_prompt_manager)
    monkeypatch.setattr(memory_writer, "get_rag_pipeline", lambda: mock_rag_pipeline)
    monkeypatch.setattr(memory_writer, "get_db", lambda: mock_db)
    return memory_writer


def _make_extraction(
    text: str = "User is a software engineer",
    importance: int = 6,
    sensitivity: str = "personal",
    tone_marker: str = "neutral",
) -> ExtractionResult:
    return ExtractionResult(
        facts=[
            ExtractedMemory(
                text=text,
                importance=importance,
                sensitivity=sensitivity,
                tone_marker=tone_marker,
            )
        ]
    )


def _make_similar_doc(
    _id: str = "abc123",
    text: str = "User works in tech",
    importance: int = 5,
    sensitivity: str = "personal",
    tone_marker: str = "neutral",
    embedding_dim: int = 8,
):
    return {
        "_id": _id,
        "user_id": "u1",
        "text": text,
        "embedding": [0.1] * embedding_dim,
        "importance": importance,
        "sensitivity": sensitivity,
        "tone_marker": tone_marker,
        "valid_at": datetime(2026, 3, 1),
    }


# ---------------------------------------------------------------------------
# TestDecideOperationPaths
# ---------------------------------------------------------------------------

class TestDecideOperationPaths:
    @pytest.mark.asyncio
    async def test_add_path_inserts_fresh_doc(self, writer, mock_llm_service, mock_db):
        """ADD decision → one insert_one, no update_one on user_memories."""
        mock_llm_service.complete_json.return_value = (
            '{"operation": "ADD", "target_memory_id": null, '
            '"updated_text": null, "reason": "new info"}'
        )
        decisions = await writer.update_memories_from_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            extraction=_make_extraction(),
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "ADD"
        assert mock_db.user_memories.insert_one.call_count == 1
        assert mock_db.user_memories.update_one.call_count == 0

        inserted_doc = mock_db.user_memories.insert_one.call_args.args[0]
        assert inserted_doc["user_id"] == "u1"
        assert inserted_doc["text"] == "User is a software engineer"
        assert inserted_doc["importance"] == 6
        assert inserted_doc["sensitivity"] == "personal"
        assert inserted_doc["invalid_at"] is None
        assert inserted_doc["source"] == "extracted"
        assert inserted_doc["access_count"] == 0
        assert inserted_doc["provenance"]["session_id"] == "s1"
        assert inserted_doc["provenance"]["turn_number"] == 1

    @pytest.mark.asyncio
    async def test_update_path_invalidates_old_and_inserts_merged(
        self, writer, mock_llm_service, mock_db
    ):
        """UPDATE → update_one sets invalid_at on old, insert_one adds merged."""
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439011", text="User is grieving father"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "UPDATE", '
            '"target_memory_id": "507f1f77bcf86cd799439011", '
            '"updated_text": "User is slowly healing from father\'s death", '
            '"reason": "evolution"}'
        )
        decisions = await writer.update_memories_from_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=5,
            extraction=_make_extraction(
                text="User is slowly healing",
                importance=8,
                sensitivity="sensitive",
                tone_marker="healing",
            ),
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "UPDATE"
        # Old record invalidated
        assert mock_db.user_memories.update_one.call_count == 1
        update_call = mock_db.user_memories.update_one.call_args
        assert "invalid_at" in update_call.args[1]["$set"]
        # Merged text inserted as fresh doc
        assert mock_db.user_memories.insert_one.call_count == 1
        inserted_doc = mock_db.user_memories.insert_one.call_args.args[0]
        assert inserted_doc["text"] == "User is slowly healing from father's death"

    @pytest.mark.asyncio
    async def test_delete_path_invalidates_without_insert(
        self, writer, mock_llm_service, mock_db
    ):
        """DELETE → update_one sets invalid_at on old, NO insert."""
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439012", text="User enjoys pranayama"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "DELETE", '
            '"target_memory_id": "507f1f77bcf86cd799439012", '
            '"updated_text": null, "reason": "user correction"}'
        )
        decisions = await writer.update_memories_from_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=3,
            extraction=_make_extraction(
                text="User no longer does pranayama", importance=4,
            ),
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "DELETE"
        assert mock_db.user_memories.update_one.call_count == 1
        assert mock_db.user_memories.insert_one.call_count == 0

    @pytest.mark.asyncio
    async def test_noop_path_bumps_access_count_only(
        self, writer, mock_llm_service, mock_db
    ):
        """NOOP → $inc access_count + $set last_accessed_at on target."""
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439013"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "NOOP", '
            '"target_memory_id": "507f1f77bcf86cd799439013", '
            '"updated_text": null, "reason": "redundant"}'
        )
        decisions = await writer.update_memories_from_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=2,
            extraction=_make_extraction(),
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "NOOP"
        assert mock_db.user_memories.insert_one.call_count == 0
        assert mock_db.user_memories.update_one.call_count == 1
        update_call = mock_db.user_memories.update_one.call_args
        update_body = update_call.args[1]
        assert "$inc" in update_body
        assert update_body["$inc"]["access_count"] == 1
        assert "$set" in update_body
        assert "last_accessed_at" in update_body["$set"]


# ---------------------------------------------------------------------------
# TestBiTemporalInvariant
# ---------------------------------------------------------------------------

class TestBiTemporalInvariant:
    @pytest.mark.asyncio
    async def test_update_preserves_old_via_invalid_at(
        self, writer, mock_llm_service, mock_db
    ):
        """UPDATE must never hard-delete. Old record gets invalid_at, not removed."""
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439014"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "UPDATE", '
            '"target_memory_id": "507f1f77bcf86cd799439014", '
            '"updated_text": "merged text", "reason": "evolved"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        # Exactly one update_one call (the invalidation) — no delete_one.
        assert mock_db.user_memories.delete_one.call_count == 0
        assert mock_db.user_memories.delete_many.call_count == 0
        update_body = mock_db.user_memories.update_one.call_args.args[1]
        assert update_body["$set"]["invalid_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_preserves_old_via_invalid_at(
        self, writer, mock_llm_service, mock_db
    ):
        """DELETE is a soft delete — invalid_at set, record preserved."""
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439015"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "DELETE", '
            '"target_memory_id": "507f1f77bcf86cd799439015", '
            '"updated_text": null, "reason": "no longer true"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        assert mock_db.user_memories.delete_one.call_count == 0
        assert mock_db.user_memories.delete_many.call_count == 0

    @pytest.mark.asyncio
    async def test_add_does_not_touch_existing_records(
        self, writer, mock_llm_service, mock_db
    ):
        """ADD must never modify an existing record."""
        mock_llm_service.complete_json.return_value = (
            '{"operation": "ADD", "target_memory_id": null, '
            '"updated_text": null, "reason": "new"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        # No update_one on user_memories (only insert_one + possibly profile upsert)
        assert mock_db.user_memories.update_one.call_count == 0
        assert mock_db.user_memories.insert_one.call_count == 1


# ---------------------------------------------------------------------------
# TestSafetyDefaults
# ---------------------------------------------------------------------------

class TestSafetyDefaults:
    @pytest.mark.asyncio
    async def test_invalid_json_defaults_to_add(
        self, writer, mock_llm_service, mock_db
    ):
        """Malformed decision JSON → ADD (spec §9.3: safer to duplicate)."""
        mock_llm_service.complete_json.return_value = "not json at all"
        decisions = await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "ADD"
        assert mock_db.user_memories.insert_one.call_count == 1

    @pytest.mark.asyncio
    async def test_llm_raises_defaults_to_add(
        self, writer, mock_llm_service, mock_db
    ):
        """Gemini exception → ADD. Never lose a potentially valuable fact."""
        mock_llm_service.complete_json.side_effect = RuntimeError("gemini boom")
        decisions = await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "ADD"
        assert mock_db.user_memories.insert_one.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_operation_coerces_to_add(
        self, writer, mock_llm_service, mock_db
    ):
        """Unknown op string coerced by Pydantic validator → ADD."""
        mock_llm_service.complete_json.return_value = (
            '{"operation": "WEIRD_OP", "target_memory_id": null, '
            '"updated_text": null, "reason": "?"}'
        )
        decisions = await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "ADD"
        assert mock_db.user_memories.insert_one.call_count == 1

    @pytest.mark.asyncio
    async def test_update_without_valid_target_falls_back_to_add(
        self, writer, mock_llm_service, mock_db
    ):
        """UPDATE with garbage target_memory_id → falls through to ADD."""
        mock_llm_service.complete_json.return_value = (
            '{"operation": "UPDATE", "target_memory_id": "not_an_oid", '
            '"updated_text": "merged", "reason": "evolved"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        # No invalidation happened, but the new text still got inserted
        assert mock_db.user_memories.update_one.call_count == 0
        assert mock_db.user_memories.insert_one.call_count == 1


# ---------------------------------------------------------------------------
# TestCrisisShortCircuit
# ---------------------------------------------------------------------------

class TestCrisisShortCircuit:
    @pytest.mark.asyncio
    async def test_crisis_fact_never_reaches_decider(
        self, writer, mock_llm_service, mock_db
    ):
        """A crisis-tier fact must never hit the LLM or MongoDB writes.

        Crisis meta-facts are exclusively the domain of the companion_engine
        crisis hook (commit 10), not the extraction pipeline.
        """
        extraction = _make_extraction(
            text="crisis-placeholder-text",
            importance=10,
            sensitivity="crisis",
            tone_marker="despair",
        )
        decisions = await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=2, extraction=extraction,
        )
        assert decisions == []
        mock_llm_service.complete_json.assert_not_called()
        assert mock_db.user_memories.insert_one.call_count == 0
        assert mock_db.user_memories.update_one.call_count == 0
        assert mock_db.user_profiles.update_one.call_count == 0

    @pytest.mark.asyncio
    async def test_mixed_batch_drops_crisis_keeps_personal(
        self, writer, mock_llm_service, mock_db
    ):
        """In a batch with a crisis + a personal fact, the personal is kept."""
        extraction = ExtractionResult(
            facts=[
                ExtractedMemory(
                    text="crisis placeholder", importance=10,
                    sensitivity="crisis", tone_marker="despair",
                ),
                ExtractedMemory(
                    text="User is a software engineer", importance=6,
                    sensitivity="personal", tone_marker="neutral",
                ),
            ]
        )
        mock_llm_service.complete_json.return_value = (
            '{"operation": "ADD", "target_memory_id": null, '
            '"updated_text": null, "reason": "new"}'
        )
        decisions = await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=2, extraction=extraction,
        )
        assert len(decisions) == 1
        assert decisions[0].operation == "ADD"
        assert mock_db.user_memories.insert_one.call_count == 1


# ---------------------------------------------------------------------------
# TestReflectionCounterBump
# ---------------------------------------------------------------------------

class TestReflectionCounterBump:
    @pytest.mark.asyncio
    async def test_add_bumps_counter_by_importance(
        self, writer, mock_llm_service, mock_db
    ):
        mock_llm_service.complete_json.return_value = (
            '{"operation": "ADD", "target_memory_id": null, '
            '"updated_text": null, "reason": "new"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(importance=7),
        )
        # user_profiles.update_one called with $inc importance_since_reflection=7
        assert mock_db.user_profiles.update_one.call_count == 1
        profile_call = mock_db.user_profiles.update_one.call_args
        update_body = profile_call.args[1]
        assert update_body["$inc"]["importance_since_reflection"] == 7
        assert profile_call.kwargs.get("upsert") is True

    @pytest.mark.asyncio
    async def test_update_bumps_counter_by_importance(
        self, writer, mock_llm_service, mock_db
    ):
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439016"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "UPDATE", '
            '"target_memory_id": "507f1f77bcf86cd799439016", '
            '"updated_text": "merged", "reason": "evolved"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(importance=8),
        )
        assert mock_db.user_profiles.update_one.call_count == 1
        inc = mock_db.user_profiles.update_one.call_args.args[1]["$inc"]
        assert inc["importance_since_reflection"] == 8

    @pytest.mark.asyncio
    async def test_delete_does_not_bump_counter(
        self, writer, mock_llm_service, mock_db
    ):
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439017"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "DELETE", '
            '"target_memory_id": "507f1f77bcf86cd799439017", '
            '"updated_text": null, "reason": "correction"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        assert mock_db.user_profiles.update_one.call_count == 0

    @pytest.mark.asyncio
    async def test_noop_does_not_bump_counter(
        self, writer, mock_llm_service, mock_db
    ):
        mock_db.user_memories.find.return_value = iter([
            _make_similar_doc(_id="507f1f77bcf86cd799439018"),
        ])
        mock_llm_service.complete_json.return_value = (
            '{"operation": "NOOP", '
            '"target_memory_id": "507f1f77bcf86cd799439018", '
            '"updated_text": null, "reason": "redundant"}'
        )
        await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        assert mock_db.user_profiles.update_one.call_count == 0


# ---------------------------------------------------------------------------
# TestEarlyExits
# ---------------------------------------------------------------------------

class TestEarlyExits:
    @pytest.mark.asyncio
    async def test_empty_extraction_is_noop(self, writer, mock_llm_service, mock_db):
        decisions = await writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=ExtractionResult(facts=[]),
        )
        assert decisions == []
        mock_llm_service.complete_json.assert_not_called()
        assert mock_db.user_memories.insert_one.call_count == 0

    @pytest.mark.asyncio
    async def test_anonymous_user_is_noop(self, writer, mock_llm_service, mock_db):
        decisions = await writer.update_memories_from_extraction(
            user_id="", session_id="s1", conversation_id=None,
            turn_number=1, extraction=_make_extraction(),
        )
        assert decisions == []
        mock_llm_service.complete_json.assert_not_called()
        assert mock_db.user_memories.insert_one.call_count == 0


# ---------------------------------------------------------------------------
# TestExtractionWiring — integration with memory_extractor._extract_with_timeout
# ---------------------------------------------------------------------------

class TestExtractionWiring:
    @pytest.fixture
    def extractor_prompt_manager(self):
        """Prompt manager that returns a minimal extract template.

        Distinct from the update-decision template in the shared
        ``mock_prompt_manager`` fixture — the extractor needs placeholders
        that match memory_extractor.extract_memories() .format() kwargs.
        """
        pm = MagicMock()
        pm.get_prompt = MagicMock(
            return_value=(
                "Context: {relational_profile_text}\n"
                "Turn {turn_number} of session {session_id}\n"
                "USER: {user_message}\n"
                "MITRA: {assistant_response}"
            )
        )
        return pm

    @pytest.mark.asyncio
    async def test_extract_with_timeout_calls_writer_when_facts_present(
        self, monkeypatch, mock_llm_service, extractor_prompt_manager
    ):
        """The extractor should invoke memory_writer when extraction returns facts."""
        from services import memory_extractor, memory_writer

        # Patch the extractor dependencies
        monkeypatch.setattr(
            memory_extractor, "get_llm_service", lambda: mock_llm_service
        )
        monkeypatch.setattr(
            memory_extractor, "get_prompt_manager", lambda: extractor_prompt_manager
        )
        mock_llm_service.complete_json.return_value = (
            '{"facts": [{"text": "User meditates daily", "importance": 5, '
            '"sensitivity": "personal", "tone_marker": "neutral"}]}'
        )

        # Spy on memory_writer.update_memories_from_extraction
        calls = []

        async def fake_update(**kwargs):
            calls.append(kwargs)
            return []

        monkeypatch.setattr(
            memory_writer, "update_memories_from_extraction", fake_update
        )

        await memory_extractor._extract_with_timeout(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="I meditated this morning",
            assistant_response="beautiful practice",
        )

        assert len(calls) == 1
        assert calls[0]["user_id"] == "u1"
        assert calls[0]["session_id"] == "s1"
        assert calls[0]["turn_number"] == 1
        assert len(calls[0]["extraction"].facts) == 1
        assert calls[0]["extraction"].facts[0].text == "User meditates daily"

    @pytest.mark.asyncio
    async def test_extract_with_timeout_skips_writer_when_no_facts(
        self, monkeypatch, mock_llm_service, extractor_prompt_manager
    ):
        """Zero facts → writer never called (common case, every greeting turn)."""
        from services import memory_extractor, memory_writer

        monkeypatch.setattr(
            memory_extractor, "get_llm_service", lambda: mock_llm_service
        )
        monkeypatch.setattr(
            memory_extractor, "get_prompt_manager", lambda: extractor_prompt_manager
        )
        mock_llm_service.complete_json.return_value = '{"facts": []}'

        calls = []

        async def fake_update(**kwargs):
            calls.append(kwargs)
            return []

        monkeypatch.setattr(
            memory_writer, "update_memories_from_extraction", fake_update
        )

        await memory_extractor._extract_with_timeout(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="hi",
            assistant_response="hello",
        )

        assert len(calls) == 0
