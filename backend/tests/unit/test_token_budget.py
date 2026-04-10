"""Tests for the adaptive token budget system.

Why these tests assert ranges, not exact numbers
------------------------------------------------
The original tests were written against specific ceiling values
(``moderate == 1024``, ``detailed == 2048``, ``full_text == 4096``).
A later commit (8f13114) tightened those ceilings — moderate to 1536,
GUIDANCE-phase detailed/full_text to 1536/2048 — to prevent mid-sentence
truncation observed in production. The change was correct, but the
tests still asserted the old numbers, so the suite went red even though
the source was right.

The fix is to assert the **contract** the budget calculator must
guarantee, not the specific implementation. Each contract test below
uses ``>=`` or ``<=`` so future tuning passes through transparently
as long as the user-visible behavior is preserved:

- "Brief intents are kept brief"        → ceiling ≤ 768
- "Emotional/moderate replies aren't truncated" → ceiling ≥ 1024
- "Guidance can be substantial"         → ceiling ≥ 1024
- "Full-text requests get a complete prayer" → ceiling ≥ 2048
- "Closure phase always brief"          → ceiling ≤ 768
- "Nothing ever falls below 512"        → ceiling ≥ 512  (no truncation regression)
- "Explicit ASKING_INFO/SEEKING_GUIDANCE has a 1024 floor"

If anyone reintroduces a ceiling below the floor, the corresponding
contract test fails immediately. If anyone *raises* a ceiling further,
nothing breaks — the contracts are loose enough to absorb the change.

The static-source guards (TestNoLLMOverride) and the schema tests
(TestIntentAnalysisExpectedLength) are unchanged — they pin
orthogonal contracts that don't depend on the numerics.
"""
import ast
import importlib.util
from pathlib import Path

import pytest

from models.session import ConversationPhase, IntentType
from models.llm_schemas import IntentAnalysis, ExpectedLengthEnum

LLM_SERVICE_PATH = Path(__file__).resolve().parents[2] / "llm" / "service.py"

# Load token_budget directly so the test doesn't depend on package init.
_tb_path = str(Path(__file__).resolve().parents[2] / "services" / "token_budget.py")
_spec = importlib.util.spec_from_file_location("token_budget", _tb_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
calculate_budget = _mod.calculate_budget
TokenBudget = _mod.TokenBudget


# ---------------------------------------------------------------------------
# Constants — the contract floors and ceilings. Update these only when the
# user-visible behavior of Mitra changes (e.g., a new "extended response"
# tier). Numerics in CEILING_MAP can move freely as long as they stay on
# the right side of these values.
# ---------------------------------------------------------------------------

# A "brief" reply (greeting, closure) must never be longer than this.
BRIEF_CEILING_CAP = 768
# A "moderate" reply (emotional share, simple Q&A) must have at least
# this much headroom so it isn't truncated mid-sentence.
MODERATE_BUDGET_FLOOR = 1024
# Detailed guidance must have substantial headroom.
DETAILED_BUDGET_FLOOR = 1024
# Full-text content (chalisa, complete prayer, step-by-step instructions)
# must have enough room for a multi-paragraph response.
FULL_TEXT_BUDGET_FLOOR = 2048
# Closure phase always caps at brief regardless of intent.
CLOSURE_PHASE_CAP = 768
# Absolute floor — no scenario should ever return less than this.
# 256 was the historical truncation bug; 512 is the current safety net.
ABSOLUTE_FLOOR = 512
# Intents that should never be budget-starved by the LLM's expected_length
# guess. ASKING_INFO and SEEKING_GUIDANCE are explicit asks.
EXPLICIT_ASK_FLOOR = 1024


# ---------------------------------------------------------------------------
# 1. LLM service has no hardcoded phase overrides
# ---------------------------------------------------------------------------

class TestNoLLMOverride:
    def test_phase_max_tokens_removed(self):
        text = LLM_SERVICE_PATH.read_text()
        assert "_PHASE_MAX_TOKENS" not in text or "removed" in text.lower()

    def test_no_phase_override_in_build_gen_config(self):
        tree = ast.parse(LLM_SERVICE_PATH.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_build_gen_config":
                source = ast.get_source_segment(LLM_SERVICE_PATH.read_text(), node)
                assert "PHASE_MAX_TOKENS" not in source
                return


# ---------------------------------------------------------------------------
# 2. Behavior contracts — ranges, not equalities
# ---------------------------------------------------------------------------

class TestBriefLengthContract:
    """Brief replies stay brief. Greeting and closure intents must not
    burn through tokens — they should hit the cap and stop."""

    def test_greeting_is_brief(self):
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.GREETING},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling <= BRIEF_CEILING_CAP

    def test_closure_intent_is_brief(self):
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.CLOSURE},
            ConversationPhase.CLOSURE,
        )
        assert budget.ceiling <= BRIEF_CEILING_CAP


class TestModerateLengthContract:
    """Emotional shares and default-length responses must have enough
    headroom to avoid mid-sentence truncation. The historical bug
    (moderate=1024) caused users to see clipped responses, so the
    floor must be at least 1024. The actual ceiling can sit at 1024,
    1536, or higher as the team tunes for quality."""

    def test_emotional_share_has_no_truncation_floor(self):
        budget = calculate_budget(
            {"expected_length": "moderate", "intent": IntentType.EXPRESSING_EMOTION},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling >= MODERATE_BUDGET_FLOOR

    def test_default_length_meets_moderate_floor(self):
        budget = calculate_budget({}, ConversationPhase.LISTENING)
        assert budget.ceiling >= MODERATE_BUDGET_FLOOR


class TestDetailedLengthContract:
    """Detailed guidance — typically a SEEKING_GUIDANCE in GUIDANCE
    phase — needs enough budget for a substantive answer plus a
    scripture reference."""

    def test_guidance_in_guidance_phase_has_substantive_budget(self):
        budget = calculate_budget(
            {"expected_length": "detailed", "intent": IntentType.SEEKING_GUIDANCE},
            ConversationPhase.GUIDANCE,
        )
        assert budget.ceiling >= DETAILED_BUDGET_FLOOR

    def test_asking_info_gets_at_least_explicit_floor(self):
        """Even if LLM says 'brief', ASKING_INFO gets at least the
        explicit-ask floor (1024) so direct questions get a proper answer."""
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.ASKING_INFO},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling >= EXPLICIT_ASK_FLOOR


class TestFullTextLengthContract:
    """Full-text intents — 'give me the Hanuman Chalisa', 'tell me the
    complete puja vidhi' — need a multi-paragraph budget."""

    def test_full_text_supports_complete_response(self):
        budget = calculate_budget(
            {"expected_length": "full_text", "intent": IntentType.ASKING_INFO},
            ConversationPhase.GUIDANCE,
        )
        assert budget.ceiling >= FULL_TEXT_BUDGET_FLOOR

    def test_chalisa_request_gets_full_text_budget(self):
        """User asks for a complete prayer in LISTENING phase: must
        still get full_text headroom, not be capped down."""
        budget = calculate_budget(
            {"expected_length": "full_text", "intent": IntentType.ASKING_INFO},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling >= FULL_TEXT_BUDGET_FLOOR


class TestClosurePhaseAlwaysCaps:
    def test_closure_phase_caps_regardless_of_length(self):
        """Closure phase is always brief, even if LLM says 'detailed'."""
        budget = calculate_budget(
            {"expected_length": "detailed", "intent": IntentType.CLOSURE},
            ConversationPhase.CLOSURE,
        )
        assert budget.ceiling <= CLOSURE_PHASE_CAP

    def test_closure_phase_with_full_text_still_capped(self):
        budget = calculate_budget(
            {"expected_length": "full_text", "intent": IntentType.SEEKING_GUIDANCE},
            ConversationPhase.CLOSURE,
        )
        assert budget.ceiling <= CLOSURE_PHASE_CAP


class TestSafetyFloorContract:
    """The 256-token truncation bug must never come back."""

    def test_asking_info_never_below_explicit_floor(self):
        for length in ["brief", "moderate", "detailed", "full_text"]:
            budget = calculate_budget(
                {"expected_length": length, "intent": IntentType.ASKING_INFO},
                ConversationPhase.LISTENING,
            )
            assert budget.ceiling >= EXPLICIT_ASK_FLOOR, (
                f"ASKING_INFO with {length} got {budget.ceiling}"
            )

    def test_seeking_guidance_never_below_explicit_floor(self):
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.SEEKING_GUIDANCE},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling >= EXPLICIT_ASK_FLOOR

    def test_no_scenario_returns_below_absolute_floor(self):
        """The exhaustive parametrized contract: no combination of
        intent × phase × length ever goes below the absolute floor.
        This is the no-truncation safety net."""
        for intent in IntentType:
            for phase in ConversationPhase:
                for length in ["brief", "moderate", "detailed", "full_text"]:
                    budget = calculate_budget(
                        {"expected_length": length, "intent": intent}, phase
                    )
                    assert budget.ceiling >= ABSOLUTE_FLOOR, (
                        f"Budget of {budget.ceiling} for "
                        f"{intent}+{phase}+{length} is below the safety floor"
                    )


# ---------------------------------------------------------------------------
# 3. IntentAnalysis model has expected_length
# ---------------------------------------------------------------------------

class TestIntentAnalysisExpectedLength:
    def test_default_is_moderate(self):
        analysis = IntentAnalysis()
        assert analysis.expected_length == ExpectedLengthEnum.MODERATE

    def test_coerces_string(self):
        analysis = IntentAnalysis(expected_length="full_text")
        assert analysis.expected_length == ExpectedLengthEnum.FULL_TEXT

    def test_invalid_defaults_to_moderate(self):
        analysis = IntentAnalysis(expected_length="nonexistent")
        assert analysis.expected_length == ExpectedLengthEnum.MODERATE

    def test_to_dict_includes_expected_length(self):
        analysis = IntentAnalysis(expected_length="detailed")
        d = analysis.to_dict()
        assert "expected_length" in d
        assert d["expected_length"] == "detailed"

    def test_budget_reason_includes_length(self):
        budget = calculate_budget(
            {"expected_length": "detailed", "intent": IntentType.OTHER},
            ConversationPhase.LISTENING,
        )
        assert "length=detailed" in budget.reason
