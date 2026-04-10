"""Contract tests for the model router's enabled/disabled split.

The original Bug A2: when ``MODEL_ROUTING_ENABLED=False``, the docstring
promised "all calls go to settings.GEMINI_MODEL", but the implementation
called ``TIER_MODELS[ModelTier.PREMIUM]`` which silently routed every
conversation to gemini-2.5-pro instead of the configured GEMINI_MODEL.
Recent commits had switched GEMINI_MODEL to gemini-2.0-flash for "2-3s
responses" — the bug made those commits dead config.

These tests pin the contract:
- routing disabled  ⇒ every (intent × phase) returns settings.GEMINI_MODEL
- routing enabled   ⇒ tier mapping is honored and matches TIER_MODELS
- the resolution helper is the only function that touches TIER_MODELS

If anyone reintroduces ``TIER_MODELS[tier]`` directly in ``_make_decision``,
the parametrized "disabled" test fails for every intent — making the
regression impossible to land silently.
"""
from __future__ import annotations

import itertools

import pytest

from config import settings
from models.session import (
    ConversationPhase,
    IntentType,
    SessionState,
)
from services.model_router import (
    ModelTier,
    TIER_MODELS,
    _make_decision,
    get_model_for_tier,
    route,
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_session() -> SessionState:
    """A minimal SessionState that satisfies route()'s expectations."""
    s = SessionState(session_id="test")
    s.signals_collected = {}
    s.conversation_history = []
    s.turn_count = 0
    return s


@pytest.fixture
def routing_disabled(monkeypatch):
    """Force MODEL_ROUTING_ENABLED=False and a recognizable GEMINI_MODEL.

    Uses two markers — `gemini-test-flash` for GEMINI_MODEL and
    `gemini-test-pro-WRONG` for MODEL_PREMIUM — so any leak from the tier
    map is loud (the test would receive 'WRONG' instead of 'flash').
    """
    monkeypatch.setattr(settings, "MODEL_ROUTING_ENABLED", False)
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test-flash")
    monkeypatch.setattr(settings, "MODEL_PREMIUM", "gemini-test-pro-WRONG")
    monkeypatch.setattr(settings, "MODEL_STANDARD", "gemini-test-std-WRONG")
    monkeypatch.setattr(settings, "MODEL_ECONOMY", "gemini-test-eco-WRONG")
    # TIER_MODELS is captured at module-import time, so refresh it.
    monkeypatch.setitem(TIER_MODELS, ModelTier.ECONOMY, "gemini-test-eco-WRONG")
    monkeypatch.setitem(TIER_MODELS, ModelTier.STANDARD, "gemini-test-std-WRONG")
    monkeypatch.setitem(TIER_MODELS, ModelTier.PREMIUM, "gemini-test-pro-WRONG")
    yield


@pytest.fixture
def routing_enabled(monkeypatch):
    """Force routing on with distinct tier model names."""
    monkeypatch.setattr(settings, "MODEL_ROUTING_ENABLED", True)
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-test-default-WRONG")
    monkeypatch.setattr(settings, "MODEL_PREMIUM", "gemini-test-pro")
    monkeypatch.setattr(settings, "MODEL_STANDARD", "gemini-test-std")
    monkeypatch.setattr(settings, "MODEL_ECONOMY", "gemini-test-eco")
    monkeypatch.setitem(TIER_MODELS, ModelTier.ECONOMY, "gemini-test-eco")
    monkeypatch.setitem(TIER_MODELS, ModelTier.STANDARD, "gemini-test-std")
    monkeypatch.setitem(TIER_MODELS, ModelTier.PREMIUM, "gemini-test-pro")
    yield


# ---------------------------------------------------------------------------
# Routing disabled — single source of truth contract
# ---------------------------------------------------------------------------


class TestRoutingDisabledHonorsGeminiModel:
    """When MODEL_ROUTING_ENABLED=False, every code path must return
    settings.GEMINI_MODEL — never any of the tier-specific models.
    """

    def test_get_model_for_tier_premium(self, routing_disabled):
        assert get_model_for_tier(ModelTier.PREMIUM) == "gemini-test-flash"

    def test_get_model_for_tier_standard(self, routing_disabled):
        assert get_model_for_tier(ModelTier.STANDARD) == "gemini-test-flash"

    def test_get_model_for_tier_economy(self, routing_disabled):
        assert get_model_for_tier(ModelTier.ECONOMY) == "gemini-test-flash"

    def test_make_decision_premium(self, routing_disabled):
        d = _make_decision(ModelTier.PREMIUM, "test", ConversationPhase.LISTENING)
        assert d.model_name == "gemini-test-flash"

    def test_make_decision_standard(self, routing_disabled):
        d = _make_decision(ModelTier.STANDARD, "test", ConversationPhase.GUIDANCE)
        assert d.model_name == "gemini-test-flash"

    def test_make_decision_economy(self, routing_disabled):
        d = _make_decision(ModelTier.ECONOMY, "test", ConversationPhase.CLOSURE)
        assert d.model_name == "gemini-test-flash"

    @pytest.mark.parametrize(
        "intent,phase",
        list(itertools.product(IntentType, [
            ConversationPhase.LISTENING,
            ConversationPhase.CLARIFICATION,
            ConversationPhase.SYNTHESIS,
            ConversationPhase.GUIDANCE,
            ConversationPhase.CLOSURE,
        ])),
    )
    def test_route_returns_gemini_model_for_every_intent_phase(
        self, routing_disabled, empty_session, intent, phase
    ):
        """The exhaustive contract: no combination of intent and phase
        can ever bypass the routing-disabled gate. This is the test that
        makes the original Bug A2 impossible to reintroduce.
        """
        empty_session.signals_collected = {}
        intent_analysis = {
            "intent": intent,
            "urgency": "normal",
            "needs_direct_answer": False,
            "expected_length": "moderate",
        }
        decision = route(intent_analysis, phase, empty_session, has_rag_context=False)
        assert decision.model_name == "gemini-test-flash", (
            f"intent={intent} phase={phase} leaked to {decision.model_name}; "
            f"routing-disabled mode must always return GEMINI_MODEL"
        )

    def test_route_with_rag_context_still_uses_gemini_model(
        self, routing_disabled, empty_session
    ):
        """Edge case: even with rag context, the disabled gate holds."""
        intent_analysis = {
            "intent": IntentType.SEEKING_GUIDANCE,
            "urgency": "normal",
            "needs_direct_answer": True,
            "expected_length": "detailed",
        }
        decision = route(
            intent_analysis,
            ConversationPhase.GUIDANCE,
            empty_session,
            has_rag_context=True,
        )
        assert decision.model_name == "gemini-test-flash"

    def test_route_with_crisis_urgency_still_uses_gemini_model(
        self, routing_disabled, empty_session
    ):
        """Crisis urgency must NOT bypass the routing-disabled gate.

        With routing enabled, crisis → premium tier. With routing disabled,
        the 'premium' resolution still maps to GEMINI_MODEL. We test crisis
        because it's the most likely path to silently leak in a refactor.
        """
        intent_analysis = {
            "intent": IntentType.EXPRESSING_EMOTION,
            "urgency": "crisis",
            "needs_direct_answer": False,
            "expected_length": "moderate",
        }
        decision = route(
            intent_analysis,
            ConversationPhase.LISTENING,
            empty_session,
            has_rag_context=False,
        )
        assert decision.model_name == "gemini-test-flash"

    def test_routing_disabled_logs_routing_disabled_reason(
        self, routing_disabled, empty_session, caplog
    ):
        """The log line should explicitly say `reason=routing_disabled`
        so an operator scanning logs knows the routing flag is off.
        """
        import logging

        intent_analysis = {
            "intent": IntentType.GREETING,
            "urgency": "normal",
            "expected_length": "brief",
        }
        with caplog.at_level(logging.INFO, logger="services.model_router"):
            route(intent_analysis, ConversationPhase.LISTENING, empty_session)
        log_text = " ".join(r.message for r in caplog.records)
        assert "routing_disabled" in log_text
        assert "gemini-test-flash" in log_text


# ---------------------------------------------------------------------------
# Routing enabled — tier mapping contract
# ---------------------------------------------------------------------------


class TestRoutingEnabledUsesTierModels:
    """Mirror contract: when routing IS enabled, the tier mapping is the
    source of truth and GEMINI_MODEL is NOT consulted.
    """

    def test_get_model_for_tier_premium_uses_tier_setting(self, routing_enabled):
        assert get_model_for_tier(ModelTier.PREMIUM) == "gemini-test-pro"

    def test_get_model_for_tier_standard_uses_tier_setting(self, routing_enabled):
        assert get_model_for_tier(ModelTier.STANDARD) == "gemini-test-std"

    def test_get_model_for_tier_economy_uses_tier_setting(self, routing_enabled):
        assert get_model_for_tier(ModelTier.ECONOMY) == "gemini-test-eco"

    def test_routing_enabled_does_not_leak_gemini_model(
        self, routing_enabled, empty_session
    ):
        """GEMINI_MODEL is set to a marker; the test passes only if no
        decision returns it (i.e., routing IS using the tier map)."""
        intent_analysis = {
            "intent": IntentType.GREETING,
            "urgency": "normal",
            "expected_length": "brief",
        }
        decision = route(
            intent_analysis,
            ConversationPhase.LISTENING,
            empty_session,
            has_rag_context=False,
        )
        # GREETING → economy
        assert decision.model_name == "gemini-test-eco"
        assert decision.model_name != "gemini-test-default-WRONG"

    def test_routing_enabled_greeting_maps_to_economy(
        self, routing_enabled, empty_session
    ):
        decision = route(
            {"intent": IntentType.GREETING, "urgency": "normal"},
            ConversationPhase.LISTENING,
            empty_session,
        )
        assert decision.tier == ModelTier.ECONOMY
        assert decision.model_name == "gemini-test-eco"

    def test_routing_enabled_crisis_maps_to_premium(
        self, routing_enabled, empty_session
    ):
        decision = route(
            {"intent": IntentType.EXPRESSING_EMOTION, "urgency": "crisis"},
            ConversationPhase.LISTENING,
            empty_session,
        )
        assert decision.tier == ModelTier.PREMIUM
        assert decision.model_name == "gemini-test-pro"


# ---------------------------------------------------------------------------
# Structural guard — _make_decision must not bypass get_model_for_tier
# ---------------------------------------------------------------------------


class TestMakeDecisionUsesHelper:
    """The original bug was a direct ``TIER_MODELS[tier]`` lookup inside
    ``_make_decision``. This AST-based guard ensures that the only place
    in the module that subscripts ``TIER_MODELS`` is inside
    ``get_model_for_tier``. Anywhere else (including a future
    ``_make_decision`` refactor) breaks the routing-disabled contract.

    Using AST instead of substring matching means the test ignores
    occurrences in docstrings, comments, or string literals — only real
    subscript expressions are flagged.
    """

    def test_only_get_model_for_tier_subscripts_tier_models(self):
        import ast
        from pathlib import Path

        source = Path(
            "/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/services/model_router.py"
        ).read_text()
        tree = ast.parse(source)

        # Walk the tree and collect every Subscript expression whose value
        # is the Name 'TIER_MODELS'. For each one, walk back up to find
        # the enclosing function (if any). Track which functions perform
        # the subscript.
        offenders: list[tuple[int, str]] = []

        class TierModelsVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self._fn_stack: list[str] = []

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._fn_stack.append(node.name)
                self.generic_visit(node)
                self._fn_stack.pop()

            def visit_AsyncFunctionDef(
                self, node: ast.AsyncFunctionDef
            ) -> None:
                self._fn_stack.append(node.name)
                self.generic_visit(node)
                self._fn_stack.pop()

            def visit_Subscript(self, node: ast.Subscript) -> None:
                if (
                    isinstance(node.value, ast.Name)
                    and node.value.id == "TIER_MODELS"
                ):
                    enclosing = (
                        self._fn_stack[-1] if self._fn_stack else "<module>"
                    )
                    if enclosing != "get_model_for_tier":
                        offenders.append((node.lineno, enclosing))
                self.generic_visit(node)

        TierModelsVisitor().visit(tree)
        assert not offenders, (
            f"TIER_MODELS subscripted outside get_model_for_tier: {offenders}. "
            f"Use get_model_for_tier(tier) instead — direct indexing breaks "
            f"the MODEL_ROUTING_ENABLED=False contract."
        )
