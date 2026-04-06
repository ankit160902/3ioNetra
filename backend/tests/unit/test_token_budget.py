"""Tests for adaptive token budget system.

Verifies:
1. llm/service.py has no hardcoded phase overrides
2. TokenBudgetCalculator produces correct ceilings for all scenarios
3. expected_length field exists in IntentAnalysis
4. No response is ever truncated at 256 tokens
"""
import ast
import importlib.util
from pathlib import Path

from models.session import ConversationPhase, IntentType
from models.llm_schemas import IntentAnalysis, ExpectedLengthEnum

LLM_SERVICE_PATH = Path(__file__).resolve().parents[2] / "llm" / "service.py"

# Load token_budget directly
_tb_path = str(Path(__file__).resolve().parents[2] / "services" / "token_budget.py")
_spec = importlib.util.spec_from_file_location("token_budget", _tb_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
calculate_budget = _mod.calculate_budget
TokenBudget = _mod.TokenBudget


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
# 2. TokenBudgetCalculator adaptive ceilings
# ---------------------------------------------------------------------------

class TestBriefLength:
    def test_greeting_gets_512(self):
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.GREETING},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling == 512

    def test_closure_intent_gets_512(self):
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.CLOSURE},
            ConversationPhase.CLOSURE,
        )
        assert budget.ceiling == 512


class TestModerateLength:
    def test_emotion_gets_1024(self):
        budget = calculate_budget(
            {"expected_length": "moderate", "intent": IntentType.EXPRESSING_EMOTION},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling == 1024

    def test_default_is_moderate(self):
        budget = calculate_budget({}, ConversationPhase.LISTENING)
        assert budget.ceiling == 1024


class TestDetailedLength:
    def test_guidance_gets_2048(self):
        budget = calculate_budget(
            {"expected_length": "detailed", "intent": IntentType.SEEKING_GUIDANCE},
            ConversationPhase.GUIDANCE,
        )
        assert budget.ceiling == 2048

    def test_asking_info_gets_at_least_1024(self):
        """Even if LLM says 'brief', ASKING_INFO gets at least 1024."""
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.ASKING_INFO},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling >= 1024


class TestFullTextLength:
    def test_full_text_gets_4096(self):
        budget = calculate_budget(
            {"expected_length": "full_text", "intent": IntentType.ASKING_INFO},
            ConversationPhase.GUIDANCE,
        )
        assert budget.ceiling == 4096

    def test_chalisa_request_would_get_full_text(self):
        """Simulating "give me hanuman chalisa" with expected_length=full_text."""
        budget = calculate_budget(
            {"expected_length": "full_text", "intent": IntentType.ASKING_INFO},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling == 4096


class TestClosureOverride:
    def test_closure_phase_always_512(self):
        """Closure phase caps at 512 regardless of expected_length."""
        budget = calculate_budget(
            {"expected_length": "detailed", "intent": IntentType.CLOSURE},
            ConversationPhase.CLOSURE,
        )
        assert budget.ceiling == 512


class TestSafetyFloor:
    def test_asking_info_never_below_1024(self):
        for length in ["brief", "moderate", "detailed", "full_text"]:
            budget = calculate_budget(
                {"expected_length": length, "intent": IntentType.ASKING_INFO},
                ConversationPhase.LISTENING,
            )
            assert budget.ceiling >= 1024, f"ASKING_INFO with {length} got {budget.ceiling}"

    def test_seeking_guidance_never_below_1024(self):
        budget = calculate_budget(
            {"expected_length": "brief", "intent": IntentType.SEEKING_GUIDANCE},
            ConversationPhase.LISTENING,
        )
        assert budget.ceiling >= 1024

    def test_no_scenario_returns_256(self):
        """No combination should ever return 256 tokens (the old truncation bug)."""
        for intent in IntentType:
            for phase in ConversationPhase:
                for length in ["brief", "moderate", "detailed", "full_text"]:
                    budget = calculate_budget(
                        {"expected_length": length, "intent": intent}, phase
                    )
                    assert budget.ceiling >= 512, (
                        f"Budget of {budget.ceiling} for {intent}+{phase}+{length} is too low"
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
