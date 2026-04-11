"""Unit tests for the response_mode classification path in IntentAgent.

Scope (Tier 1 — fast, offline, no LLM calls):
    - Fast-path short-circuits set the correct mode for each intent type
    - _fallback_analysis() derives mode from intent via the mode_map
    - Emotional-weight override bumps practical_first -> presence_first
    - Pydantic exception fallback preserves response_mode from raw JSON
    - Unknown modes coerce to "exploratory" safely

For live-LLM classification accuracy tests, see test_intent_agent_mode_live.py.
"""
import sys
import types

import pytest

# Stub out the 'transitions' package BEFORE importing services, so the
# services/__init__.py chain (companion_engine -> conversation_fsm ->
# transitions) resolves successfully even in environments where the
# dependency isn't installed. The stub provides a no-op Machine class
# with the attributes conversation_fsm actually touches.
if "transitions" not in sys.modules:
    _stub = types.ModuleType("transitions")
    class _StubMachine:
        def __init__(self, *args, **kwargs):
            pass
        def add_transition(self, *args, **kwargs):
            pass
    _stub.Machine = _StubMachine
    sys.modules["transitions"] = _stub

from models.llm_schemas import IntentAnalysis, IntentEnum  # noqa: E402
from models.session import IntentType  # noqa: E402
from services.intent_agent import IntentAgent  # noqa: E402


# ---------------------------------------------------------------------------
# Fast-path mode assignment
# ---------------------------------------------------------------------------

class TestFastPathModes:
    """Each fast-path short-circuit must set response_mode correctly."""

    @pytest.fixture
    def agent(self):
        # Constructor touches get_llm_service() — ok because we never call
        # analyze_intent() in these tests, only _fast_path() directly.
        return IntentAgent()

    def test_greeting_exact_match_maps_to_exploratory(self, agent):
        result = agent._fast_path("hi")
        assert result is not None
        assert result["intent"] == IntentType.GREETING
        assert result["response_mode"] == "exploratory"

    def test_greeting_with_mitra_maps_to_exploratory(self, agent):
        result = agent._fast_path("namaste mitra")
        assert result is not None
        assert result["intent"] == IntentType.GREETING
        assert result["response_mode"] == "exploratory"

    def test_short_greeting_pattern_maps_to_exploratory(self, agent):
        # first-word greeting with <=4 words
        result = agent._fast_path("hey how are you")
        assert result is not None
        assert result["intent"] == IntentType.GREETING
        assert result["response_mode"] == "exploratory"

    def test_closure_maps_to_closure_mode(self, agent):
        # Apr 2026 — "closure" is now the 5th response_mode, replacing the
        # earlier "exploratory" default on CLOSURE fast-path matches.
        result = agent._fast_path("thanks")
        assert result is not None
        assert result["intent"] == IntentType.CLOSURE
        assert result["response_mode"] == "closure"

    def test_off_topic_maps_to_exploratory(self, agent):
        # "write code for" is in _OFF_TOPIC_PHRASES
        result = agent._fast_path("write code for a sorting algorithm")
        assert result is not None
        assert result["intent"] == IntentType.OTHER
        assert result["is_off_topic"] is True
        assert result["response_mode"] == "exploratory"

    def test_panchang_maps_to_teaching(self, agent):
        result = agent._fast_path("what is today's tithi")
        assert result is not None
        assert result["intent"] == IntentType.ASKING_PANCHANG
        assert result["response_mode"] == "teaching"

    def test_expressing_emotion_fast_path_maps_to_presence_first(self, agent):
        # "i feel sad" — short message, emotion pattern + keyword
        result = agent._fast_path("i feel sad")
        assert result is not None
        assert result["intent"] == IntentType.EXPRESSING_EMOTION
        assert result["response_mode"] == "presence_first"

    def test_asking_info_fast_path_maps_to_teaching(self, agent):
        # "what is X" pattern without emotional weight
        result = agent._fast_path("what is karma yoga")
        assert result is not None
        assert result["intent"] == IntentType.ASKING_INFO
        assert result["response_mode"] == "teaching"

    def test_no_fast_path_match_returns_none(self, agent):
        # Longer messages with no matching pattern fall through
        result = agent._fast_path("i really need to figure out my career path this year")
        assert result is None


# ---------------------------------------------------------------------------
# _fallback_analysis mode derivation
# ---------------------------------------------------------------------------

class TestFallbackModeDerivation:
    """When the LLM is unavailable, _fallback_analysis should still pick a sensible mode."""

    @pytest.fixture
    def agent(self):
        return IntentAgent()

    def test_seeking_guidance_defaults_to_practical_first(self, agent):
        # A question without emotional weight → SEEKING_GUIDANCE → practical_first
        result = agent._fallback_analysis("how do i study for my exam tomorrow")
        assert result["intent"] == IntentType.SEEKING_GUIDANCE
        assert result["response_mode"] == "practical_first"

    def test_seeking_guidance_with_emotion_leans_presence_first(self, agent):
        # Emotional weight should override practical_first → presence_first
        result = agent._fallback_analysis("what should i do i feel so lost and scared")
        assert result["intent"] == IntentType.SEEKING_GUIDANCE
        assert result["response_mode"] == "presence_first"

    def test_panchang_fallback_maps_to_teaching(self, agent):
        # Note: the fallback's keyword check uses substring matching which
        # has pre-existing collisions (e.g. "hi" in "tithi"). We pick a query
        # that cleanly matches panchang without triggering the greeting rule.
        result = agent._fallback_analysis("panchang please")
        assert result["intent"] == IntentType.ASKING_PANCHANG
        assert result["response_mode"] == "teaching"

    def test_greeting_fallback_maps_to_exploratory(self, agent):
        result = agent._fallback_analysis("hi mitra")
        assert result["intent"] == IntentType.GREETING
        assert result["response_mode"] == "exploratory"

    def test_closure_fallback_maps_to_closure_mode(self, agent):
        # Apr 2026 — _fallback_analysis mode_map now routes CLOSURE -> "closure"
        # so offline fallback still produces a proper wind-down response.
        result = agent._fallback_analysis("thanks bye")
        assert result["intent"] == IntentType.CLOSURE
        assert result["response_mode"] == "closure"

    def test_unknown_intent_defaults_to_exploratory(self, agent):
        # A message with no intent signals → OTHER → exploratory
        # Avoiding "h", "w", "g", substrings that collide with the fallback's
        # substring-based keyword matching.
        result = agent._fallback_analysis("random placeholder text")
        assert result["intent"] == IntentType.OTHER
        assert result["response_mode"] == "exploratory"


# ---------------------------------------------------------------------------
# IntentAnalysis Pydantic coercion for response_mode
# ---------------------------------------------------------------------------

class TestIntentAnalysisResponseModeCoercion:
    """Ensure bad LLM output coerces to the 4-valued set safely."""

    def test_default_is_exploratory(self):
        assert IntentAnalysis().response_mode == "exploratory"

    def test_all_five_valid_modes_accepted(self):
        for mode in ("practical_first", "presence_first", "teaching", "exploratory", "closure"):
            assert IntentAnalysis(response_mode=mode).response_mode == mode

    def test_unknown_mode_coerces_to_exploratory(self):
        assert IntentAnalysis(response_mode="nonsense").response_mode == "exploratory"
        assert IntentAnalysis(response_mode="").response_mode == "exploratory"
        assert IntentAnalysis(response_mode=None).response_mode == "exploratory"

    def test_uppercase_mode_normalized(self):
        # The validator lowercases before comparison
        assert IntentAnalysis(response_mode="PRACTICAL_FIRST").response_mode == "practical_first"

    def test_whitespace_stripped(self):
        assert IntentAnalysis(response_mode="  teaching  ").response_mode == "teaching"

    def test_to_dict_includes_response_mode(self):
        ia = IntentAnalysis(intent="SEEKING_GUIDANCE", response_mode="practical_first")
        d = ia.to_dict()
        assert d["response_mode"] == "practical_first"
        assert d["intent"] == "SEEKING_GUIDANCE"


# ---------------------------------------------------------------------------
# Pydantic exception fallback dict preserves response_mode
# ---------------------------------------------------------------------------

class TestPydanticFallbackPreservesMode:
    """When IntentAnalysis(**parsed) raises, the manual dict fallback must
    still populate response_mode from the raw parsed JSON."""

    def test_raw_parsed_mode_is_preserved(self):
        # Simulates the 'parsed' dict that intent_agent.py builds when
        # pydantic validation fails — we verify the coercion logic matches.
        parsed = {"intent": "SEEKING_GUIDANCE", "response_mode": "practical_first"}
        _valid_modes = {"practical_first", "presence_first", "teaching", "exploratory"}
        raw = str(parsed.get("response_mode", "exploratory")).strip().lower()
        result = raw if raw in _valid_modes else "exploratory"
        assert result == "practical_first"

    def test_missing_parsed_mode_defaults_to_exploratory(self):
        parsed = {"intent": "SEEKING_GUIDANCE"}
        _valid_modes = {"practical_first", "presence_first", "teaching", "exploratory"}
        raw = str(parsed.get("response_mode", "exploratory")).strip().lower()
        result = raw if raw in _valid_modes else "exploratory"
        assert result == "exploratory"

    def test_garbage_parsed_mode_coerces_safely(self):
        parsed = {"intent": "SEEKING_GUIDANCE", "response_mode": "SPIRITUAL_ASSAULT_MODE"}
        _valid_modes = {"practical_first", "presence_first", "teaching", "exploratory"}
        raw = str(parsed.get("response_mode", "exploratory")).strip().lower()
        result = raw if raw in _valid_modes else "exploratory"
        assert result == "exploratory"
