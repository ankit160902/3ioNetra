"""Unit tests for memory_reader — the synchronous read path for the
dynamic memory system.

Covers spec §10.1-§10.6 unit requirements from the design doc:
scoring function shape, importance floor, recency decay, tone-aware
filter, mode gate, top-k cut, absolute score floor, profile load
(cached / mongo / empty), access boost.

No real Redis, no real Mongo, no real RAG.
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from models.memory_context import RelationalProfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=None)
    cache.flush_prefix = AsyncMock(return_value=0)
    return cache


@pytest.fixture
def mock_rag():
    rag = MagicMock()
    rag.generate_embeddings = AsyncMock(
        return_value=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    )
    return rag


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.user_memories.find.return_value = iter([])
    db.user_memories.update_many = MagicMock(
        return_value=MagicMock(modified_count=0)
    )
    db.user_profiles.find_one = MagicMock(return_value=None)
    return db


@pytest.fixture
def reader(monkeypatch, mock_cache, mock_rag, mock_db):
    from services import memory_reader
    monkeypatch.setattr(memory_reader, "get_cache_service", lambda: mock_cache)
    monkeypatch.setattr(memory_reader, "get_rag_pipeline", lambda: mock_rag)
    monkeypatch.setattr(memory_reader, "get_db", lambda: mock_db)
    return memory_reader


def _make_session(turn_count: int = 5):
    s = MagicMock()
    s.turn_count = turn_count
    return s


def _make_memory(
    _id: str = "mem1",
    text: str = "User is a software engineer",
    importance: int = 5,
    sensitivity: str = "personal",
    tone_marker: str = "neutral",
    valid_at: datetime | None = None,
    last_accessed_at: datetime | None = None,
    embedding_vec: list | None = None,
):
    return {
        "_id": _id,
        "user_id": "u1",
        "text": text,
        "embedding": embedding_vec if embedding_vec is not None else [1.0, 0.0, 0.0, 0.0],
        "importance": importance,
        "sensitivity": sensitivity,
        "tone_marker": tone_marker,
        "valid_at": valid_at or datetime.utcnow(),
        "last_accessed_at": last_accessed_at,
        "invalid_at": None,
        "created_at": valid_at or datetime.utcnow(),
    }


# ---------------------------------------------------------------------------
# TestScoringFunction
# ---------------------------------------------------------------------------

class TestScoringFunction:
    def test_returns_float(self, reader):
        m = _make_memory()
        score = reader._score_memory(
            m, np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), datetime.utcnow()
        )
        assert isinstance(score, float)

    def test_higher_importance_scores_higher_all_else_equal(self, reader):
        now = datetime.utcnow()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        low = _make_memory(importance=3, valid_at=now)
        high = _make_memory(importance=9, valid_at=now)
        assert reader._score_memory(high, q, now) > reader._score_memory(low, q, now)

    def test_more_relevant_scores_higher_all_else_equal(self, reader):
        now = datetime.utcnow()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        close = _make_memory(valid_at=now, embedding_vec=[1.0, 0.0, 0.0, 0.0])
        far = _make_memory(valid_at=now, embedding_vec=[0.0, 1.0, 0.0, 0.0])
        assert reader._score_memory(close, q, now) > reader._score_memory(far, q, now)

    def test_recent_scores_higher_than_old(self, reader):
        now = datetime.utcnow()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        recent = _make_memory(importance=5, valid_at=now)
        old = _make_memory(importance=5, valid_at=now - timedelta(days=365))
        assert reader._score_memory(recent, q, now) > reader._score_memory(old, q, now)

    def test_importance_floor_prevents_high_importance_decay(self, reader):
        """Importance ≥ 8 memories stay retrievable even after years."""
        now = datetime.utcnow()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        ancient_important = _make_memory(
            importance=9, valid_at=now - timedelta(days=365 * 3)
        )
        ancient_trivial = _make_memory(
            importance=3, valid_at=now - timedelta(days=365 * 3)
        )
        s_imp = reader._score_memory(ancient_important, q, now)
        s_triv = reader._score_memory(ancient_trivial, q, now)
        # High-importance ancient memory keeps a meaningful recency floor
        assert s_imp > s_triv
        # Recency component is floored, not zeroed
        from config import settings
        assert s_imp >= settings.MEMORY_IMPORTANCE_FLOOR_VALUE * settings.MEMORY_WEIGHT_RECENCY

    def test_recency_decay_half_life_shape(self, reader):
        """After one half-life, raw recency should be about 0.5 (for
        importance below the floor threshold)."""
        from config import settings
        now = datetime.utcnow()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        zero_relevance_zero_importance = _make_memory(
            importance=1, valid_at=now - timedelta(days=settings.MEMORY_HALF_LIFE_DAYS),
            embedding_vec=[0.0, 1.0, 0.0, 0.0],  # orthogonal to query
        )
        # importance contribution: (1/10)^1.5 ≈ 0.0316
        # relevance: 0
        # recency: 0.5 after one half-life (importance well below the floor)
        # total ≈ 0.5 * 0.5 + 1.0 * 0.0316 + 1.0 * 0 ≈ 0.2816
        s = reader._score_memory(zero_relevance_zero_importance, q, now)
        expected_recency = 0.5
        importance_component = (1 / 10.0) ** 1.5
        expected = (
            settings.MEMORY_WEIGHT_RECENCY * expected_recency
            + settings.MEMORY_WEIGHT_IMPORTANCE * importance_component
        )
        assert abs(s - expected) < 0.01

    def test_coerces_iso_string_datetime(self, reader):
        """Legacy memories stored with ISO string dates must score, not crash."""
        now = datetime.utcnow()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        m = _make_memory()
        m["valid_at"] = (now - timedelta(days=10)).isoformat()
        m["created_at"] = m["valid_at"]
        s = reader._score_memory(m, q, now)
        assert isinstance(s, float)
        assert s > 0


# ---------------------------------------------------------------------------
# TestToneFilter
# ---------------------------------------------------------------------------

class TestToneFilter:
    def test_grief_memory_surfaces_for_grief_turn(self, reader):
        assert reader._tone_aligned("grief", "anxiety") is True  # both heavy family

    def test_grief_memory_does_not_surface_for_joy_turn(self, reader):
        assert reader._tone_aligned("grief", "joy") is False

    def test_same_tone_aligned(self, reader):
        assert reader._tone_aligned("gratitude", "gratitude") is True

    def test_empty_tone_never_aligned(self, reader):
        assert reader._tone_aligned("", "grief") is False
        assert reader._tone_aligned("grief", "") is False

    def test_unknown_tone_treated_as_unaligned(self, reader):
        assert reader._tone_aligned("aliens", "grief") is False

    def test_recovering_and_heavy_are_distinct_families(self, reader):
        assert reader._tone_aligned("healing", "grief") is False


# ---------------------------------------------------------------------------
# TestInferCurrentTone
# ---------------------------------------------------------------------------

class TestInferCurrentTone:
    def test_emotion_in_analysis_wins(self, reader):
        tone = reader._infer_current_tone({"emotion": "anxiety"}, "teaching")
        assert tone == "anxiety"

    def test_neutral_emotion_falls_back_to_mode_default(self, reader):
        tone = reader._infer_current_tone({"emotion": "neutral"}, "presence_first")
        assert tone == "grief"  # heavy-family default for presence_first

    def test_missing_emotion_falls_back_to_mode_default(self, reader):
        tone = reader._infer_current_tone({}, "teaching")
        assert tone == "curiosity"

    def test_unknown_mode_defaults_to_neutral(self, reader):
        tone = reader._infer_current_tone({}, "bogus_mode")
        assert tone == "neutral"


# ---------------------------------------------------------------------------
# TestModeGate
# ---------------------------------------------------------------------------

class TestModeGate:
    def test_practical_first_skips(self, reader):
        assert reader._should_skip_retrieval("practical_first", turn_count=10) is True

    def test_closure_skips(self, reader):
        assert reader._should_skip_retrieval("closure", turn_count=10) is True

    def test_presence_first_early_turns_skip(self, reader):
        assert reader._should_skip_retrieval("presence_first", turn_count=1) is True
        assert reader._should_skip_retrieval("presence_first", turn_count=2) is True

    def test_presence_first_later_turns_run(self, reader):
        assert reader._should_skip_retrieval("presence_first", turn_count=3) is False

    def test_teaching_runs(self, reader):
        assert reader._should_skip_retrieval("teaching", turn_count=1) is False

    def test_exploratory_runs(self, reader):
        assert reader._should_skip_retrieval("exploratory", turn_count=1) is False


# ---------------------------------------------------------------------------
# TestRetrieveEpisodicIntegration
# ---------------------------------------------------------------------------

class TestRetrieveEpisodicIntegration:
    @pytest.mark.asyncio
    async def test_skips_for_practical_first_without_embedding_call(
        self, reader, mock_rag
    ):
        result = await reader.retrieve_episodic(
            user_id="u1",
            query="anything",
            response_mode="practical_first",
            analysis={"emotion": "neutral"},
            session=_make_session(turn_count=5),
        )
        assert result == []
        mock_rag.generate_embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_for_closure(self, reader, mock_rag):
        result = await reader.retrieve_episodic(
            user_id="u1", query="thanks", response_mode="closure",
            analysis={}, session=_make_session(),
        )
        assert result == []
        mock_rag.generate_embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_for_early_presence_first(self, reader, mock_rag):
        result = await reader.retrieve_episodic(
            user_id="u1", query="i'm sad", response_mode="presence_first",
            analysis={"emotion": "grief"}, session=_make_session(turn_count=1),
        )
        assert result == []
        mock_rag.generate_embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_anonymous_user_returns_empty(self, reader, mock_rag):
        result = await reader.retrieve_episodic(
            user_id="", query="hi", response_mode="teaching",
            analysis={}, session=_make_session(),
        )
        assert result == []
        mock_rag.generate_embeddings.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_top_k_scored_memories(self, reader, mock_db):
        now = datetime.utcnow()
        mock_db.user_memories.find.return_value = iter([
            _make_memory(_id="a", importance=9, valid_at=now),
            _make_memory(_id="b", importance=5, valid_at=now),
            _make_memory(_id="c", importance=3, valid_at=now),
            _make_memory(_id="d", importance=2, valid_at=now),
            _make_memory(_id="e", importance=1, valid_at=now),
        ])
        result = await reader.retrieve_episodic(
            user_id="u1", query="software", response_mode="teaching",
            analysis={"emotion": "curiosity"}, session=_make_session(),
        )
        from config import settings
        assert len(result) <= settings.MEMORY_EPISODIC_TOP_K
        # Results are sorted by score descending
        scores = [sm.score for sm in result]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_score_floor_filters_weak_matches(self, reader, mock_db, monkeypatch):
        """All memories orthogonal to query AND low importance AND ancient →
        every score falls below the floor → empty result."""
        from config import settings
        monkeypatch.setattr(settings, "MEMORY_SCORE_FLOOR", 0.9)
        mock_db.user_memories.find.return_value = iter([
            _make_memory(
                _id="weak1", importance=1,
                valid_at=datetime.utcnow() - timedelta(days=365),
                embedding_vec=[0.0, 1.0, 0.0, 0.0],
            ),
        ])
        result = await reader.retrieve_episodic(
            user_id="u1", query="x", response_mode="teaching",
            analysis={}, session=_make_session(),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_crisis_memories_filtered_out(self, reader, mock_db):
        mock_db.user_memories.find.return_value = iter([
            _make_memory(_id="c1", sensitivity="crisis", tone_marker="despair"),
            _make_memory(_id="ok1", sensitivity="personal"),
        ])
        result = await reader.retrieve_episodic(
            user_id="u1", query="anything", response_mode="teaching",
            analysis={}, session=_make_session(),
        )
        kept_ids = [sm.memory["_id"] for sm in result]
        assert "c1" not in kept_ids
        assert "ok1" in kept_ids

    @pytest.mark.asyncio
    async def test_sensitive_memory_gated_by_tone(self, reader, mock_db):
        """Sensitive grief memory is dropped when current tone is joy."""
        mock_db.user_memories.find.return_value = iter([
            _make_memory(
                _id="grief1", sensitivity="sensitive",
                tone_marker="grief", importance=8,
            ),
        ])
        result = await reader.retrieve_episodic(
            user_id="u1", query="anything",
            response_mode="teaching",
            analysis={"emotion": "joy"},  # warm family
            session=_make_session(),
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_sensitive_memory_surfaces_when_tone_aligned(self, reader, mock_db):
        mock_db.user_memories.find.return_value = iter([
            _make_memory(
                _id="grief1", sensitivity="sensitive",
                tone_marker="grief", importance=8,
            ),
        ])
        result = await reader.retrieve_episodic(
            user_id="u1", query="anything",
            response_mode="presence_first",  # defaults to grief
            analysis={"emotion": "anxiety"},  # heavy family
            session=_make_session(turn_count=5),  # past the early-turn gate
        )
        assert len(result) == 1
        assert result[0].memory["_id"] == "grief1"

    @pytest.mark.asyncio
    async def test_personal_memory_not_tone_filtered(self, reader, mock_db):
        """Personal-tier memories bypass the tone filter entirely."""
        mock_db.user_memories.find.return_value = iter([
            _make_memory(
                _id="p1", sensitivity="personal",
                tone_marker="anxiety", importance=6,
            ),
        ])
        result = await reader.retrieve_episodic(
            user_id="u1", query="anything", response_mode="teaching",
            analysis={"emotion": "joy"},  # opposite family
            session=_make_session(),
        )
        assert len(result) == 1
        assert result[0].memory["_id"] == "p1"


# ---------------------------------------------------------------------------
# TestLoadRelationalProfile
# ---------------------------------------------------------------------------

class TestLoadRelationalProfile:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_rehydrated(self, reader, mock_cache, mock_db):
        mock_cache.get.return_value = {
            "user_id": "u1",
            "relational_narrative": "A warm seeker",
            "spiritual_themes": ["bhakti"],
        }
        profile = await reader.load_relational_profile("u1")
        assert profile.relational_narrative == "A warm seeker"
        assert profile.spiritual_themes == ["bhakti"]
        # MongoDB not touched when cache hits
        mock_db.user_profiles.find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_reads_mongo(self, reader, mock_cache, mock_db):
        mock_cache.get.return_value = None
        mock_db.user_profiles.find_one.return_value = {
            "user_id": "u1",
            "relational_narrative": "From mongo",
            "spiritual_themes": [],
            "ongoing_concerns": ["work stress"],
        }
        profile = await reader.load_relational_profile("u1")
        assert profile.relational_narrative == "From mongo"
        assert profile.ongoing_concerns == ["work stress"]
        mock_db.user_profiles.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_miss_and_mongo_empty_returns_empty_profile(
        self, reader, mock_cache, mock_db
    ):
        mock_cache.get.return_value = None
        mock_db.user_profiles.find_one.return_value = None
        profile = await reader.load_relational_profile("u1")
        assert profile.user_id == "u1"
        assert profile.relational_narrative == ""
        assert profile.to_prompt_text() == ""

    @pytest.mark.asyncio
    async def test_anonymous_user_returns_empty_without_db_call(
        self, reader, mock_cache, mock_db
    ):
        profile = await reader.load_relational_profile("")
        assert profile.relational_narrative == ""
        mock_cache.get.assert_not_called()
        mock_db.user_profiles.find_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_mongo_error_falls_back_to_empty(
        self, reader, mock_cache, mock_db
    ):
        mock_cache.get.return_value = None
        mock_db.user_profiles.find_one.side_effect = RuntimeError("mongo down")
        profile = await reader.load_relational_profile("u1")
        assert profile.user_id == "u1"
        assert profile.relational_narrative == ""

    @pytest.mark.asyncio
    async def test_cache_get_error_falls_through_to_mongo(
        self, reader, mock_cache, mock_db
    ):
        mock_cache.get.side_effect = RuntimeError("redis down")
        mock_db.user_profiles.find_one.return_value = {
            "user_id": "u1", "relational_narrative": "mongo still works",
        }
        profile = await reader.load_relational_profile("u1")
        assert profile.relational_narrative == "mongo still works"


# ---------------------------------------------------------------------------
# TestLoadAndRetrieve
# ---------------------------------------------------------------------------

class TestLoadAndRetrieve:
    @pytest.mark.asyncio
    async def test_returns_both_profile_and_episodic(self, reader, mock_cache, mock_db):
        mock_cache.get.return_value = {
            "user_id": "u1", "relational_narrative": "cached",
        }
        mock_db.user_memories.find.return_value = iter([
            _make_memory(_id="e1", importance=7),
        ])
        result = await reader.load_and_retrieve(
            user_id="u1", query="tell me more",
            response_mode="teaching",
            analysis={"emotion": "curiosity"},
            session=_make_session(turn_count=3),
        )
        assert isinstance(result.profile, RelationalProfile)
        assert result.profile.relational_narrative == "cached"
        assert len(result.episodic) >= 1

    @pytest.mark.asyncio
    async def test_profile_load_failure_returns_empty_profile(
        self, reader, mock_cache, mock_db
    ):
        mock_cache.get.side_effect = RuntimeError("redis down")
        mock_db.user_profiles.find_one.side_effect = RuntimeError("mongo down")
        mock_db.user_memories.find.return_value = iter([])
        result = await reader.load_and_retrieve(
            user_id="u1", query="hello",
            response_mode="teaching", analysis={}, session=_make_session(),
        )
        # Profile defaults gracefully; episodic also empty
        assert result.profile.relational_narrative == ""
        assert result.episodic == []


# ---------------------------------------------------------------------------
# TestAccessBoost
# ---------------------------------------------------------------------------

class TestAccessBoost:
    @pytest.mark.asyncio
    async def test_bump_access_updates_retrieved_ids(self, reader, mock_db):
        await reader._bump_access(["a", "b", "c"])
        mock_db.user_memories.update_many.assert_called_once()
        args, _ = mock_db.user_memories.update_many.call_args
        filter_arg, update_arg = args
        assert filter_arg["_id"]["$in"] == ["a", "b", "c"]
        assert "last_accessed_at" in update_arg["$set"]
        assert update_arg["$inc"]["access_count"] == 1

    @pytest.mark.asyncio
    async def test_bump_access_empty_ids_is_noop(self, reader, mock_db):
        await reader._bump_access([])
        mock_db.user_memories.update_many.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieval_schedules_access_boost_task(
        self, reader, mock_db, monkeypatch
    ):
        now = datetime.utcnow()
        mock_db.user_memories.find.return_value = iter([
            _make_memory(_id="hit1", importance=8, valid_at=now),
        ])
        dispatched = []
        orig_create_task = asyncio.create_task

        def capturing_create_task(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched.append(task)
            return task

        monkeypatch.setattr(
            "services.memory_reader.asyncio.create_task", capturing_create_task
        )
        result = await reader.retrieve_episodic(
            user_id="u1", query="software", response_mode="teaching",
            analysis={"emotion": "curiosity"}, session=_make_session(),
        )
        assert len(result) == 1
        assert len(dispatched) == 1
        await dispatched[0]
        mock_db.user_memories.update_many.assert_called_once()
