"""Unit tests for mode-block injection inside LLMService._build_prompt.

Scope (Tier 3 — fast, offline, no LLM calls):
    - _build_prompt() injects the correct mode_prompts.<mode> block when
      response_mode is set
    - It does NOT inject any other mode's block
    - It does NOT contain the deleted 30/70 length hint or the deleted
      _practical_topic_keywords text
    - The mode block is injected LAST (after the phase prompt, just before
      the "Your response:" sentinel), so it is the strongest recent signal
    - When response_mode is None, the ACTIVE RESPONSE MODE header is absent

These tests call _build_prompt() directly with minimal setup and inspect
the returned string. They do NOT call Gemini.
"""
import sys
import types

import pytest

# Stub transitions (same reason as test_intent_agent_mode.py)
if "transitions" not in sys.modules:
    _stub = types.ModuleType("transitions")
    class _StubMachine:
        def __init__(self, *args, **kwargs):
            pass
        def add_transition(self, *args, **kwargs):
            pass
    _stub.Machine = _StubMachine
    sys.modules["transitions"] = _stub

from llm.service import LLMService, UserContext  # noqa: E402
from models.session import ConversationPhase  # noqa: E402


@pytest.fixture(scope="module")
def llm_service():
    """Real LLMService instance — we only call _build_prompt, which is
    pure string assembly and doesn't touch the network."""
    svc = LLMService()
    return svc


@pytest.fixture
def base_context():
    return UserContext()


# ---------------------------------------------------------------------------
# Correct mode block injection
# ---------------------------------------------------------------------------

class TestModeBlockInjection:
    """Each response_mode value must inject the matching YAML block."""

    def test_practical_first_injects_only_that_block(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="i have 6 modules to study by tomorrow",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode="practical_first",
        )
        assert "ACTIVE RESPONSE MODE" in prompt
        assert "MODE: practical_first" in prompt
        # Other mode markers must NOT appear
        assert "MODE: presence_first" not in prompt
        assert "MODE: teaching" not in prompt
        assert "MODE: exploratory" not in prompt

    def test_presence_first_injects_only_that_block(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="i just miss my father so much",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode="presence_first",
        )
        assert "ACTIVE RESPONSE MODE" in prompt
        assert "MODE: presence_first" in prompt
        assert "MODE: practical_first" not in prompt
        assert "MODE: teaching" not in prompt

    def test_teaching_injects_only_that_block(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="what is karma yoga",
            conversation_history=[],
            phase=ConversationPhase.GUIDANCE,
            context=base_context,
            response_mode="teaching",
        )
        assert "ACTIVE RESPONSE MODE" in prompt
        assert "MODE: teaching" in prompt
        assert "MODE: practical_first" not in prompt
        assert "MODE: presence_first" not in prompt

    def test_exploratory_injects_only_that_block(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="i feel lost",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode="exploratory",
        )
        assert "ACTIVE RESPONSE MODE" in prompt
        assert "MODE: exploratory" in prompt
        assert "MODE: practical_first" not in prompt
        assert "MODE: teaching" not in prompt

    def test_closure_injects_only_that_block(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="thank you, that helped",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode="closure",
        )
        assert "ACTIVE RESPONSE MODE" in prompt
        assert "MODE: closure" in prompt
        # Other mode markers must NOT appear
        assert "MODE: practical_first" not in prompt
        assert "MODE: presence_first" not in prompt
        assert "MODE: teaching" not in prompt
        assert "MODE: exploratory" not in prompt
        # Closure block has a distinctive rule
        assert "CURRENT TURN DOMINATES" in prompt or "door closing softly" in prompt


# ---------------------------------------------------------------------------
# No mode_block when response_mode is None
# ---------------------------------------------------------------------------

class TestNoModeBlockWhenUnset:
    """Backward compatibility — callers that don't pass response_mode
    must still produce a valid prompt without the ACTIVE RESPONSE MODE block."""

    def test_no_response_mode_means_no_block(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="tell me about bhakti",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode=None,
        )
        assert "ACTIVE RESPONSE MODE" not in prompt
        # And the prompt should still have the standard sections
        assert "Your response:" in prompt

    def test_default_parameter_is_none(self, llm_service, base_context):
        # Calling without response_mode kwarg
        prompt = llm_service._build_prompt(
            query="tell me about bhakti",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
        )
        assert "ACTIVE RESPONSE MODE" not in prompt


# ---------------------------------------------------------------------------
# Deleted hot-fix cruft must be absent
# ---------------------------------------------------------------------------

class TestDeletedHotFixAbsent:
    """Every built prompt must be free of the deleted 30/70 cruft and
    the hardcoded keyword lists — for any mode, any phase, any query."""

    @pytest.mark.parametrize("mode", [
        "practical_first", "presence_first", "teaching", "exploratory", "closure", None,
    ])
    @pytest.mark.parametrize("query", [
        "i have 6 modules to study by tomorrow",
        "how do i ask my manager for a raise",
        "what is karma yoga",
        "i feel lost",
    ])
    def test_no_30_70_ratio(self, llm_service, base_context, mode, query):
        prompt = llm_service._build_prompt(
            query=query,
            conversation_history=[],
            phase=ConversationPhase.GUIDANCE,
            context=base_context,
            response_mode=mode,
        )
        # Deleted 30/70 length hint text
        assert "30% of your response" not in prompt
        assert "Remaining 70%" not in prompt
        assert "RESPONSE STRUCTURE: The user is asking about a real-world problem" not in prompt

    @pytest.mark.parametrize("mode", [
        "practical_first", "teaching", None,
    ])
    def test_no_practical_topic_keyword_list(self, llm_service, base_context, mode):
        # The old block contained a hardcoded list of keywords like:
        # "job, salary, budget, debt, resume, interview, boss, deadline, ..."
        # If any of that prose leaks into the prompt, the deletion was incomplete.
        prompt = llm_service._build_prompt(
            query="help me with my career",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode=mode,
        )
        # None of these should appear as a prose list in the built prompt.
        # Individual words can still appear (in scripture context, user messages,
        # etc.) so we search for the specific concatenated phrase pattern.
        assert "job, salary, budget, debt" not in prompt
        assert "resume, interview, boss, deadline" not in prompt


# ---------------------------------------------------------------------------
# Injection placement — mode block must be late in the prompt
# ---------------------------------------------------------------------------

class TestModeBlockPlacement:
    """The mode block is injected AFTER the phase prompt and BEFORE
    'Your response:', making it the strongest recent signal."""

    def test_mode_block_before_response_marker(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="i have exams tomorrow",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode="practical_first",
        )
        mode_idx = prompt.find("ACTIVE RESPONSE MODE")
        response_idx = prompt.find("Your response:")
        assert mode_idx != -1, "Mode block missing"
        assert response_idx != -1, "Response marker missing"
        assert mode_idx < response_idx, "Mode block must come BEFORE 'Your response:'"

    def test_mode_block_after_phase_instructions(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="i have exams tomorrow",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode="practical_first",
        )
        mode_idx = prompt.find("ACTIVE RESPONSE MODE")
        phase_idx = prompt.find("YOUR INSTRUCTIONS FOR THIS PHASE")
        assert phase_idx != -1, "Phase instructions marker missing"
        assert phase_idx < mode_idx, "Mode block must come AFTER phase instructions"


# ---------------------------------------------------------------------------
# Unknown mode falls through safely (prompt_manager returns empty)
# ---------------------------------------------------------------------------

class TestUnknownModeSafeFallthrough:
    """If an unknown mode name reaches _build_prompt somehow (e.g. bypass the
    Pydantic validator), the prompt_manager.get_prompt() call will return the
    default empty string and the ACTIVE RESPONSE MODE header will NOT be
    emitted. This is the safe-fallback contract."""

    def test_unknown_mode_emits_no_mode_header(self, llm_service, base_context):
        prompt = llm_service._build_prompt(
            query="anything",
            conversation_history=[],
            phase=ConversationPhase.LISTENING,
            context=base_context,
            response_mode="totally_made_up_mode_name",
        )
        assert "ACTIVE RESPONSE MODE" not in prompt
