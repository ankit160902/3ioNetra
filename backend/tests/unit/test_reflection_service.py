"""Unit tests for reflection_service — threshold-triggered consolidation
and LLM-driven pruning for the dynamic memory system.

All tests use mocked LLM, prompt manager, and MongoDB. The per-user
in-flight lock is reset between tests via a fixture to prevent leakage.
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.llm_schemas import ReflectionResult, ReflectionProfilePatch


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
        return_value="PROFILE:\n{current_profile_text}\n\nMEMORIES:\n{memories_block}"
    )
    return pm


@pytest.fixture
def mock_db():
    db = MagicMock()
    # user_profiles: one document with counter=35 (above threshold)
    db.user_profiles.find_one = MagicMock(
        return_value={
            "user_id": "u1",
            "relational_narrative": "Prior narrative",
            "spiritual_themes": ["bhakti"],
            "ongoing_concerns": [],
            "tone_preferences": [],
            "people_mentioned": [],
            "prior_crisis_flag": False,
            "prior_crisis_context": None,
            "prior_crisis_count": 0,
            "importance_since_reflection": 35,
            "reflection_count": 0,
        }
    )
    db.user_profiles.update_one = MagicMock(
        return_value=MagicMock(modified_count=1, upserted_id=None)
    )
    # user_memories: a small set of valid memories
    now = datetime.utcnow()
    default_memories = [
        {
            "_id": "507f1f77bcf86cd799439011",
            "text": "User is grieving father",
            "importance": 9,
            "sensitivity": "sensitive",
            "tone_marker": "grief",
            "valid_at": now - timedelta(days=2),
            "created_at": now - timedelta(days=2),
        },
        {
            "_id": "507f1f77bcf86cd799439012",
            "text": "User is a software engineer",
            "importance": 5,
            "sensitivity": "personal",
            "tone_marker": "neutral",
            "valid_at": now - timedelta(days=1),
            "created_at": now - timedelta(days=1),
        },
    ]
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = default_memories
    db.user_memories.find.return_value = cursor
    db.user_memories.update_many = MagicMock(
        return_value=MagicMock(modified_count=1)
    )
    return db


@pytest.fixture(autouse=True)
def reset_inflight():
    """Reset the per-user in-flight set between tests so they don't leak."""
    from services import reflection_service
    reflection_service._inflight_users.clear()
    yield
    reflection_service._inflight_users.clear()


@pytest.fixture
def reflection(monkeypatch, mock_llm_service, mock_prompt_manager, mock_db):
    from services import reflection_service
    monkeypatch.setattr(reflection_service, "get_llm_service", lambda: mock_llm_service)
    monkeypatch.setattr(
        reflection_service, "get_prompt_manager", lambda: mock_prompt_manager
    )
    monkeypatch.setattr(reflection_service, "get_db", lambda: mock_db)

    # Also silence the cache invalidation side-effect
    async def noop_invalidate(user_id):
        return None

    monkeypatch.setattr(
        reflection_service, "_invalidate_profile_cache", noop_invalidate
    )
    return reflection_service


# ---------------------------------------------------------------------------
# TestMaybeTriggerReflection
# ---------------------------------------------------------------------------

class TestMaybeTriggerReflection:
    @pytest.mark.asyncio
    async def test_dispatches_when_counter_above_threshold(
        self, reflection, mock_llm_service, mock_db
    ):
        # Gemini returns a valid reflection so run_reflection completes
        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {"relational_narrative": "New narrative", '
            '"spiritual_themes": ["bhakti", "seva"], "ongoing_concerns": [], '
            '"tone_preferences": [], "people_mentioned": []}, "prune_ids": []}'
        )
        dispatched = []
        orig_create_task = asyncio.create_task

        def capture(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched.append(task)
            return task

        import services.reflection_service as rs
        rs.asyncio.create_task = capture
        try:
            result = await reflection.maybe_trigger_reflection("u1")
            assert result is True
            assert len(dispatched) == 1
            await dispatched[0]
        finally:
            rs.asyncio.create_task = orig_create_task

    @pytest.mark.asyncio
    async def test_skips_when_counter_below_threshold(
        self, reflection, mock_db
    ):
        mock_db.user_profiles.find_one.return_value = {
            "user_id": "u1", "importance_since_reflection": 10,
        }
        result = await reflection.maybe_trigger_reflection("u1")
        assert result is False

    @pytest.mark.asyncio
    async def test_skips_when_no_profile_doc_yet(
        self, reflection, mock_db
    ):
        mock_db.user_profiles.find_one.return_value = None
        result = await reflection.maybe_trigger_reflection("u1")
        assert result is False

    @pytest.mark.asyncio
    async def test_skips_when_anonymous(self, reflection, mock_db):
        result = await reflection.maybe_trigger_reflection("")
        assert result is False
        mock_db.user_profiles.find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_already_in_flight(self, reflection, mock_db):
        # Manually claim the slot — simulate a concurrent reflection
        reflection._inflight_users.add("u1")
        result = await reflection.maybe_trigger_reflection("u1")
        assert result is False

    @pytest.mark.asyncio
    async def test_db_read_failure_returns_false(self, reflection, mock_db):
        mock_db.user_profiles.find_one.side_effect = RuntimeError("mongo down")
        result = await reflection.maybe_trigger_reflection("u1")
        assert result is False


# ---------------------------------------------------------------------------
# TestRunReflection
# ---------------------------------------------------------------------------

class TestRunReflection:
    @pytest.mark.asyncio
    async def test_successful_reflection_writes_updated_profile(
        self, reflection, mock_llm_service, mock_db
    ):
        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {'
            '"relational_narrative": "A warm seeker on a grief arc", '
            '"spiritual_themes": ["bhakti", "grief"], '
            '"ongoing_concerns": ["healing"], '
            '"tone_preferences": ["gentle pacing"], '
            '"people_mentioned": ["father (deceased)"]'
            '}, "prune_ids": []}'
        )
        result = await reflection.run_reflection("u1")
        assert result is not None
        assert result.updated_profile.relational_narrative == "A warm seeker on a grief arc"

        # Profile doc was written with updated narrative and reset counter
        mock_db.user_profiles.update_one.assert_called_once()
        args = mock_db.user_profiles.update_one.call_args
        filter_arg, update_body = args.args[0], args.args[1]
        assert filter_arg == {"user_id": "u1"}
        set_doc = update_body["$set"]
        assert set_doc["relational_narrative"] == "A warm seeker on a grief arc"
        assert set_doc["importance_since_reflection"] == 0
        assert set_doc["reflection_count"] == 1
        assert set_doc["user_id"] == "u1"
        assert args.kwargs.get("upsert") is True

    @pytest.mark.asyncio
    async def test_empty_memories_resets_counter_and_returns(
        self, reflection, mock_llm_service, mock_db
    ):
        # Make the cursor yield no memories
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.limit.return_value = []
        mock_db.user_memories.find.return_value = cursor

        result = await reflection.run_reflection("u1")
        assert result is None
        # Counter reset, LLM never called
        mock_llm_service.complete_json.assert_not_called()
        # _reset_counter uses update_one with $set importance_since_reflection=0
        assert mock_db.user_profiles.update_one.call_count == 1
        update_body = mock_db.user_profiles.update_one.call_args.args[1]
        assert update_body["$set"]["importance_since_reflection"] == 0

    @pytest.mark.asyncio
    async def test_invalid_llm_json_leaves_profile_untouched(
        self, reflection, mock_llm_service, mock_db
    ):
        mock_llm_service.complete_json.return_value = "not valid json"
        result = await reflection.run_reflection("u1")
        assert result is None
        # Profile was NEVER written — failure leaves the counter intact
        # so the next ADD will retry
        mock_db.user_profiles.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_exception_leaves_profile_untouched(
        self, reflection, mock_llm_service, mock_db
    ):
        mock_llm_service.complete_json.side_effect = RuntimeError("gemini down")
        result = await reflection.run_reflection("u1")
        assert result is None
        mock_db.user_profiles.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_anonymous_user_is_noop(self, reflection, mock_db):
        result = await reflection.run_reflection("")
        assert result is None
        mock_db.user_profiles.find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_reflection_count_is_incremented_on_success(
        self, reflection, mock_llm_service, mock_db
    ):
        mock_db.user_profiles.find_one.return_value = {
            "user_id": "u1",
            "relational_narrative": "Existing",
            "spiritual_themes": [],
            "ongoing_concerns": [],
            "tone_preferences": [],
            "people_mentioned": [],
            "prior_crisis_flag": False,
            "prior_crisis_context": None,
            "prior_crisis_count": 0,
            "importance_since_reflection": 40,
            "reflection_count": 3,  # already reflected 3 times
        }
        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {"relational_narrative": "v4", '
            '"spiritual_themes": [], "ongoing_concerns": [], '
            '"tone_preferences": [], "people_mentioned": []}, '
            '"prune_ids": []}'
        )
        await reflection.run_reflection("u1")
        update_body = mock_db.user_profiles.update_one.call_args.args[1]
        assert update_body["$set"]["reflection_count"] == 4


# ---------------------------------------------------------------------------
# TestPruneSafetyFloor
# ---------------------------------------------------------------------------

class TestPruneSafetyFloor:
    @pytest.mark.asyncio
    async def test_prune_ids_applied_with_importance_safety_floor(
        self, reflection, mock_llm_service, mock_db
    ):
        """The update_many prune filter must include importance < 8."""
        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {"relational_narrative": "n", '
            '"spiritual_themes": [], "ongoing_concerns": [], '
            '"tone_preferences": [], "people_mentioned": []}, '
            '"prune_ids": ["507f1f77bcf86cd799439010", '
            '"507f1f77bcf86cd799439011"]}'
        )
        await reflection.run_reflection("u1")

        mock_db.user_memories.update_many.assert_called_once()
        filter_arg, update_arg = mock_db.user_memories.update_many.call_args.args
        assert filter_arg["user_id"] == "u1"
        assert filter_arg["importance"] == {"$lt": 8}
        assert filter_arg["invalid_at"] is None
        assert "_id" in filter_arg and "$in" in filter_arg["_id"]
        # Bi-temporal — set invalid_at, not a hard delete
        assert "invalid_at" in update_arg["$set"]

    @pytest.mark.asyncio
    async def test_prune_skipped_when_llm_returns_empty_list(
        self, reflection, mock_llm_service, mock_db
    ):
        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {"relational_narrative": "n", '
            '"spiritual_themes": [], "ongoing_concerns": [], '
            '"tone_preferences": [], "people_mentioned": []}, '
            '"prune_ids": []}'
        )
        await reflection.run_reflection("u1")
        mock_db.user_memories.update_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_prune_bad_oids_are_silently_dropped(
        self, reflection, mock_llm_service, mock_db
    ):
        """LLM hallucinating non-hex ids should not crash the reflection."""
        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {"relational_narrative": "n", '
            '"spiritual_themes": [], "ongoing_concerns": [], '
            '"tone_preferences": [], "people_mentioned": []}, '
            '"prune_ids": ["garbage_id_1", "also_garbage"]}'
        )
        result = await reflection.run_reflection("u1")
        assert result is not None
        # update_many should not have been called because no valid oids
        mock_db.user_memories.update_many.assert_not_called()


# ---------------------------------------------------------------------------
# TestCacheInvalidation
# ---------------------------------------------------------------------------

class TestCacheInvalidation:
    @pytest.mark.asyncio
    async def test_successful_reflection_invalidates_cache(
        self, monkeypatch, mock_llm_service, mock_prompt_manager, mock_db
    ):
        """After a successful profile write, the Redis cache must be busted
        so the next turn sees the new narrative."""
        from services import reflection_service

        monkeypatch.setattr(
            reflection_service, "get_llm_service", lambda: mock_llm_service
        )
        monkeypatch.setattr(
            reflection_service, "get_prompt_manager", lambda: mock_prompt_manager
        )
        monkeypatch.setattr(reflection_service, "get_db", lambda: mock_db)

        invalidated = []

        async def capture_invalidate(user_id):
            invalidated.append(user_id)

        monkeypatch.setattr(
            reflection_service, "_invalidate_profile_cache", capture_invalidate
        )

        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {"relational_narrative": "new", '
            '"spiritual_themes": [], "ongoing_concerns": [], '
            '"tone_preferences": [], "people_mentioned": []}, '
            '"prune_ids": []}'
        )
        await reflection_service.run_reflection("u1")
        assert invalidated == ["u1"]


# ---------------------------------------------------------------------------
# TestInFlightLock
# ---------------------------------------------------------------------------

class TestInFlightLock:
    @pytest.mark.asyncio
    async def test_claim_and_release_slot(self, reflection):
        assert await reflection._claim_slot("u1") is True
        assert await reflection._claim_slot("u1") is False
        await reflection._release_slot("u1")
        assert await reflection._claim_slot("u1") is True

    @pytest.mark.asyncio
    async def test_different_users_can_run_in_parallel(self, reflection):
        """Per-user lock — multiple users can reflect concurrently."""
        assert await reflection._claim_slot("u1") is True
        assert await reflection._claim_slot("u2") is True
        assert await reflection._claim_slot("u3") is True
        # But u1 cannot double-claim
        assert await reflection._claim_slot("u1") is False

    @pytest.mark.asyncio
    async def test_slot_released_after_run_completes(
        self, reflection, mock_llm_service
    ):
        """After _run_and_release finishes, the slot must be free again."""
        mock_llm_service.complete_json.return_value = (
            '{"updated_profile": {"relational_narrative": "n", '
            '"spiritual_themes": [], "ongoing_concerns": [], '
            '"tone_preferences": [], "people_mentioned": []}, '
            '"prune_ids": []}'
        )
        await reflection._run_and_release("u1")
        assert "u1" not in reflection._inflight_users

    @pytest.mark.asyncio
    async def test_slot_released_even_when_run_raises(
        self, reflection, mock_llm_service
    ):
        """If run_reflection has an uncaught error, the slot MUST still release."""
        # Inject a raising run_reflection
        import services.reflection_service as rs

        async def boom(user_id):
            raise RuntimeError("simulated failure")

        original = rs.run_reflection
        rs.run_reflection = boom
        try:
            # _run_and_release catches via finally — the error may or may not
            # propagate. We just care that the slot is released.
            try:
                await reflection._run_and_release("u1")
            except RuntimeError:
                pass
            assert "u1" not in reflection._inflight_users
        finally:
            rs.run_reflection = original


# ---------------------------------------------------------------------------
# TestMemoryWriterIntegration — verify memory_writer actually calls the trigger
# ---------------------------------------------------------------------------

class TestMemoryWriterIntegration:
    @pytest.mark.asyncio
    async def test_memory_writer_triggers_reflection_after_add(
        self, monkeypatch
    ):
        """An ADD decision should cause memory_writer to call
        maybe_trigger_reflection once, regardless of whether it actually
        dispatches."""
        from services import memory_writer, reflection_service
        from models.llm_schemas import ExtractedMemory, ExtractionResult

        import numpy as np

        mock_llm = MagicMock()
        mock_llm.available = True
        mock_llm.complete_json = AsyncMock(
            return_value='{"operation": "ADD", "target_memory_id": null, '
                         '"updated_text": null, "reason": "new"}'
        )

        mock_pm = MagicMock()
        mock_pm.get_prompt = MagicMock(
            return_value="NEW: {new_fact_text}/{new_fact_importance}/"
                         "{new_fact_sensitivity}/{new_fact_tone}\n"
                         "SIM:\n{similar_memories_block}"
        )
        mock_rag = MagicMock()
        mock_rag.generate_embeddings = AsyncMock(
            return_value=np.array([0.1] * 8, dtype=np.float32)
        )
        mock_db = MagicMock()
        mock_db.user_memories.find.return_value = iter([])
        mock_db.user_memories.insert_one = MagicMock(
            return_value=MagicMock(inserted_id="new")
        )
        mock_db.user_profiles.update_one = MagicMock(
            return_value=MagicMock(modified_count=1)
        )

        monkeypatch.setattr(memory_writer, "get_llm_service", lambda: mock_llm)
        monkeypatch.setattr(memory_writer, "get_prompt_manager", lambda: mock_pm)
        monkeypatch.setattr(memory_writer, "get_rag_pipeline", lambda: mock_rag)
        monkeypatch.setattr(memory_writer, "get_db", lambda: mock_db)

        triggers = []

        async def fake_trigger(user_id):
            triggers.append(user_id)
            return False

        monkeypatch.setattr(
            reflection_service, "maybe_trigger_reflection", fake_trigger
        )

        extraction = ExtractionResult(
            facts=[
                ExtractedMemory(
                    text="User meditates daily", importance=6,
                    sensitivity="personal", tone_marker="neutral",
                )
            ]
        )
        await memory_writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=extraction,
        )
        assert triggers == ["u1"]

    @pytest.mark.asyncio
    async def test_memory_writer_does_not_trigger_on_noop_only(
        self, monkeypatch
    ):
        """NOOP decisions don't bump the counter, so no reflection trigger."""
        from services import memory_writer, reflection_service
        from models.llm_schemas import ExtractedMemory, ExtractionResult

        import numpy as np

        mock_llm = MagicMock()
        mock_llm.available = True
        mock_llm.complete_json = AsyncMock(
            return_value='{"operation": "NOOP", '
                         '"target_memory_id": "507f1f77bcf86cd799439020", '
                         '"updated_text": null, "reason": "redundant"}'
        )
        mock_pm = MagicMock()
        mock_pm.get_prompt = MagicMock(
            return_value="NEW: {new_fact_text}/{new_fact_importance}/"
                         "{new_fact_sensitivity}/{new_fact_tone}\n"
                         "SIM:\n{similar_memories_block}"
        )
        mock_rag = MagicMock()
        mock_rag.generate_embeddings = AsyncMock(
            return_value=np.array([0.1] * 8, dtype=np.float32)
        )
        mock_db = MagicMock()
        mock_db.user_memories.find.return_value = iter([
            {
                "_id": "507f1f77bcf86cd799439020", "user_id": "u1",
                "text": "User meditates", "embedding": [0.1] * 8,
                "importance": 5, "sensitivity": "personal",
                "tone_marker": "neutral",
            }
        ])
        mock_db.user_memories.update_one = MagicMock(
            return_value=MagicMock(modified_count=1)
        )

        monkeypatch.setattr(memory_writer, "get_llm_service", lambda: mock_llm)
        monkeypatch.setattr(memory_writer, "get_prompt_manager", lambda: mock_pm)
        monkeypatch.setattr(memory_writer, "get_rag_pipeline", lambda: mock_rag)
        monkeypatch.setattr(memory_writer, "get_db", lambda: mock_db)

        triggers = []

        async def fake_trigger(user_id):
            triggers.append(user_id)
            return False

        monkeypatch.setattr(
            reflection_service, "maybe_trigger_reflection", fake_trigger
        )

        extraction = ExtractionResult(
            facts=[
                ExtractedMemory(
                    text="User meditates daily", importance=5,
                    sensitivity="personal", tone_marker="neutral",
                )
            ]
        )
        await memory_writer.update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=extraction,
        )
        assert triggers == []
