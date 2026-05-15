"""Tests for the small response-shaping helpers in routers/chat.py.

Covers:
- _compute_is_complete: phase + emotional context → completion hint
- _build_sources: RAG context_docs → SourceReference list

These helpers used to be inlined into the request handlers as magic literals
(`is_complete=True`, `is_complete=False`). Extracting them lets the logic be
unit-tested without spinning up the full FastAPI handler.
"""
import pytest
from models.session import SessionState, ConversationPhase
from models.memory_context import ConversationMemory, UserStory
from models.api_schemas import SourceReference
from routers.chat import _compute_is_complete, _build_sources


def _session(turn_count: int = 0, emotional_state: str = "") -> SessionState:
    session = SessionState()
    session.turn_count = turn_count
    session.memory = ConversationMemory(story=UserStory(emotional_state=emotional_state))
    return session


# ---------------------------------------------------------------------------
# _compute_is_complete
# ---------------------------------------------------------------------------

class TestComputeIsCompleteByPhase:
    def test_closure_phase_is_always_complete(self):
        session = _session(turn_count=1, emotional_state="grief")
        assert _compute_is_complete(session, ConversationPhase.CLOSURE) is True

    def test_listening_phase_is_never_complete(self):
        session = _session(turn_count=5, emotional_state="")
        assert _compute_is_complete(session, ConversationPhase.LISTENING) is False

    def test_guidance_phase_neutral_is_complete(self):
        session = _session(turn_count=3, emotional_state="curiosity")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is True


class TestComputeIsCompleteEmotionGate:
    """For GUIDANCE phase: heavy emotion + early turn → keep open."""

    def test_grief_turn_one_stays_open(self):
        session = _session(turn_count=1, emotional_state="grief")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is False

    def test_anxiety_turn_two_stays_open(self):
        session = _session(turn_count=2, emotional_state="anxiety")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is False

    def test_anger_turn_three_is_complete(self):
        """After turn 2, the user has had room to be heard — guidance can close."""
        session = _session(turn_count=3, emotional_state="anger")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is True

    def test_loneliness_turn_one_stays_open(self):
        session = _session(turn_count=1, emotional_state="loneliness")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is False

    def test_neutral_emotion_turn_one_is_complete(self):
        session = _session(turn_count=1, emotional_state="curiosity")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is True

    def test_empty_emotion_turn_one_is_complete(self):
        session = _session(turn_count=1, emotional_state="")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is True

    def test_emotion_case_insensitive(self):
        session = _session(turn_count=1, emotional_state="GRIEF")
        assert _compute_is_complete(session, ConversationPhase.GUIDANCE) is False


# ---------------------------------------------------------------------------
# _build_sources
# ---------------------------------------------------------------------------

class TestBuildSources:
    def test_empty_list(self):
        assert _build_sources([]) == []

    def test_none(self):
        assert _build_sources(None) == []

    def test_single_doc(self):
        doc = {
            "scripture": "Bhagavad Gita",
            "reference": "2.47",
            "text": "कर्मण्येवाधिकारस्ते...",
            "meaning": "You have the right to action, but never to its fruits.",
            "score": 0.876543,
        }
        result = _build_sources([doc])
        assert len(result) == 1
        assert isinstance(result[0], SourceReference)
        assert result[0].scripture == "Bhagavad Gita"
        assert result[0].reference == "2.47"
        assert "right to action" in result[0].context_text
        assert result[0].relevance_score == 0.877

    def test_multiple_docs(self):
        docs = [
            {"scripture": "Gita", "reference": "2.47", "meaning": "do duty", "score": 0.9},
            {"scripture": "Yoga Sutras", "reference": "1.2", "meaning": "still the mind", "score": 0.8},
        ]
        result = _build_sources(docs)
        assert len(result) == 2
        assert result[0].scripture == "Gita"
        assert result[1].scripture == "Yoga Sutras"

    def test_truncates_long_context_text(self):
        long_text = "x" * 500
        doc = {"scripture": "Gita", "reference": "1.1", "meaning": long_text, "score": 0.5}
        result = _build_sources([doc])
        assert len(result[0].context_text) <= 240

    def test_falls_back_to_text_when_no_meaning(self):
        doc = {"scripture": "Gita", "reference": "2.47", "text": "raw verse text", "score": 0.5}
        result = _build_sources([doc])
        assert "raw verse text" in result[0].context_text

    def test_falls_back_to_source_when_no_reference(self):
        doc = {"scripture": "Gita", "source": "2_shloka", "meaning": "x", "score": 0.5}
        result = _build_sources([doc])
        assert result[0].reference == "2_shloka"

    def test_falls_back_to_metadata_score(self):
        doc = {"scripture": "Gita", "reference": "2.47", "meaning": "x", "_metadata_score": 0.65}
        result = _build_sources([doc])
        assert result[0].relevance_score == 0.65

    def test_unknown_scripture_default(self):
        doc = {"reference": "1.1", "meaning": "x", "score": 0.5}
        result = _build_sources([doc])
        assert result[0].scripture == "Unknown"

    def test_skips_malformed_doc(self):
        docs = [
            {"scripture": "Gita", "reference": "2.47", "meaning": "good", "score": 0.9},
            {"scripture": "Bad", "reference": "1.1", "meaning": "x", "score": "not_a_number"},
            {"scripture": "Yoga Sutras", "reference": "1.2", "meaning": "good", "score": 0.7},
        ]
        result = _build_sources(docs)
        # Malformed doc skipped, others kept.
        assert len(result) == 2
        assert result[0].scripture == "Gita"
        assert result[1].scripture == "Yoga Sutras"
