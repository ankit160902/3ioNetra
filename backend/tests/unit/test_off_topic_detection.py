"""Tests for off-topic detection across the IntentAgent fast-path,
the IntentAnalysis schema, and the CompanionEngine short-circuit.

The off-topic gate should:
1. Default to False on the IntentAnalysis Pydantic model.
2. Trip via the fast-path for narrow non-spiritual queries (Python, scores, recipes).
3. Be suppressed for messages that mix off-topic phrases with emotional weight,
   so users like "I'm so stressed I can't even cook a recipe" still get heard.
4. Trip the IntentAgent fast-path for an off-topic phrase even when it would
   otherwise look like a question.
"""
import importlib.util
from pathlib import Path

from models.llm_schemas import IntentAnalysis
from models.session import IntentType


# Load IntentAgent directly to avoid services/__init__.py import chain
_path = str(Path(__file__).resolve().parents[2] / "services" / "intent_agent.py")
_spec = importlib.util.spec_from_file_location("intent_agent", _path)
_mod = importlib.util.module_from_spec(_spec)
# IntentAgent imports llm.service, which we don't need for fast-path tests.
# Patch it before exec.
import sys
_fake_llm = type(sys)("llm")
_fake_llm_svc = type(sys)("llm.service")
_fake_llm_svc.get_llm_service = lambda: type("L", (), {"available": False, "client": None})()
_fake_llm.service = _fake_llm_svc
sys.modules.setdefault("llm", _fake_llm)
sys.modules.setdefault("llm.service", _fake_llm_svc)
_spec.loader.exec_module(_mod)
IntentAgent = _mod.IntentAgent


def _agent():
    """Return an IntentAgent instance for fast-path testing only."""
    return IntentAgent()


# ---------------------------------------------------------------------------
# Schema default
# ---------------------------------------------------------------------------

class TestSchemaDefault:
    def test_is_off_topic_defaults_false(self):
        analysis = IntentAnalysis()
        assert analysis.is_off_topic is False

    def test_is_off_topic_can_be_set(self):
        analysis = IntentAnalysis(is_off_topic=True)
        assert analysis.is_off_topic is True


# ---------------------------------------------------------------------------
# Fast-path off-topic detection
# ---------------------------------------------------------------------------

class TestFastPathOffTopic:
    def test_python_code_request_is_off_topic(self):
        agent = _agent()
        result = agent._fast_path("can you help me write python code for a scraper")
        assert result is not None
        assert result["is_off_topic"] is True
        assert result["intent"] == IntentType.OTHER

    def test_javascript_request_is_off_topic(self):
        agent = _agent()
        result = agent._fast_path("how do i fix this javascript bug")
        assert result is not None
        assert result["is_off_topic"] is True

    def test_cricket_score_is_off_topic(self):
        agent = _agent()
        result = agent._fast_path("what is the cricket score today")
        assert result is not None
        assert result["is_off_topic"] is True

    def test_recipe_request_is_off_topic(self):
        agent = _agent()
        result = agent._fast_path("recipe for paneer butter masala please")
        assert result is not None
        assert result["is_off_topic"] is True

    def test_weather_query_is_off_topic(self):
        agent = _agent()
        result = agent._fast_path("temperature today in mumbai")
        assert result is not None
        assert result["is_off_topic"] is True


# ---------------------------------------------------------------------------
# Off-topic detection should NOT fire for spiritual or life-guidance queries
# ---------------------------------------------------------------------------

class TestFastPathOnTopic:
    def test_spiritual_question_not_off_topic(self):
        agent = _agent()
        result = agent._fast_path("what is karma yoga")
        # This may match the ASKING_INFO fast-path; either way, off_topic should be False.
        if result is not None:
            assert result.get("is_off_topic") is False

    def test_emotional_share_with_recipe_word_not_off_topic(self):
        """Mixing off-topic phrases with emotional weight should defer to LLM."""
        agent = _agent()
        result = agent._fast_path(
            "i'm so stressed and overwhelmed i can't even cook a recipe for my family"
        )
        # This is emotionally weighted — fast-path should NOT classify as off-topic.
        if result is not None:
            assert result.get("is_off_topic", False) is False

    def test_namaste_greeting_not_off_topic(self):
        agent = _agent()
        result = agent._fast_path("namaste")
        assert result is not None
        assert result["is_off_topic"] is False
        assert result["intent"] == IntentType.GREETING


# ---------------------------------------------------------------------------
# Emotion-aware INFO suppression
# ---------------------------------------------------------------------------

class TestInfoPrefixEmotionGuard:
    """The fast-path INFO classifier should NOT short-circuit
    needs_direct_answer=True when the message has emotional weight.
    """

    def test_pure_factual_what_is_uses_fast_path(self):
        agent = _agent()
        result = agent._fast_path("what is dharma")
        assert result is not None
        assert result["intent"] == IntentType.ASKING_INFO
        assert result["needs_direct_answer"] is True

    def test_emotional_what_should_i_falls_through(self):
        """When 'what' is followed by emotional content, fast-path should NOT
        return an INFO classification — it should fall through to the LLM
        so the listening-first guard can apply."""
        agent = _agent()
        result = agent._fast_path("what should i do i feel so lost and broken")
        # Either no fast-path match (None), or emotion-detected fall-through.
        # Critically, it must NOT be a clean ASKING_INFO with needs_direct_answer.
        if result is not None and result.get("intent") == IntentType.ASKING_INFO:
            assert False, "Fast-path should not classify emotional message as INFO"

    def test_what_is_when_user_feels_lost_falls_through(self):
        agent = _agent()
        result = agent._fast_path("what is the point i feel so empty inside")
        if result is not None and result.get("intent") == IntentType.ASKING_INFO:
            assert False, "Fast-path should not classify emotional message as INFO"


# ---------------------------------------------------------------------------
# Helper method tests
# ---------------------------------------------------------------------------

class TestEmotionalWeightHelper:
    def test_neutral_message_has_no_emotional_weight(self):
        agent = _agent()
        assert agent._has_emotional_weight("what is the tithi today") is False

    def test_explicit_feeling_word_has_weight(self):
        agent = _agent()
        assert agent._has_emotional_weight("i feel really sad about this") is True

    def test_lost_word_has_weight(self):
        agent = _agent()
        assert agent._has_emotional_weight("i am so lost in life right now") is True

    def test_anxious_word_has_weight(self):
        agent = _agent()
        assert agent._has_emotional_weight("i'm feeling anxious about my future") is True


# ---------------------------------------------------------------------------
# Fallback analysis off-topic and emotion gating
# ---------------------------------------------------------------------------

class TestFallbackAnalysis:
    def test_fallback_includes_is_off_topic_field(self):
        agent = _agent()
        result = agent._fallback_analysis("hello there")
        assert "is_off_topic" in result
        assert result["is_off_topic"] is False

    def test_fallback_emotional_question_not_direct_answer(self):
        agent = _agent()
        # "What should I do" with emotional words should NOT set needs_direct_answer
        result = agent._fallback_analysis("what should i do i feel so lost and hopeless")
        assert result["needs_direct_answer"] is False

    def test_fallback_factual_question_is_direct_answer(self):
        agent = _agent()
        result = agent._fallback_analysis("what is the meaning of dharma")
        assert result["needs_direct_answer"] is True
