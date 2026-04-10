"""
Multi-Model Routing Engine for 3ioNetra
========================================
Routes cheap models for simple requests, premium models for complex guidance,
reducing cost while maintaining quality.

Feature flag: ``MODEL_ROUTING_ENABLED`` (default: True).

When ``MODEL_ROUTING_ENABLED=False``:
    Every routing decision returns ``settings.GEMINI_MODEL`` regardless of
    intent or phase. This is the canonical "single model" mode — useful for
    cost capping (point everything at gemini-2.0-flash) or for debugging
    (point everything at gemini-2.5-pro). The tier-specific MODEL_PREMIUM /
    MODEL_STANDARD / MODEL_ECONOMY settings are intentionally ignored in
    this mode so there is exactly one source of truth.

When ``MODEL_ROUTING_ENABLED=True``:
    The decision tree below picks a tier per request, and the tier maps to
    one of MODEL_PREMIUM / MODEL_STANDARD / MODEL_ECONOMY. GEMINI_MODEL is
    not consulted in this mode — operators set the three tier models
    independently.

The model resolution itself goes through ``get_model_for_tier(tier)`` so
this contract is enforced in exactly one place. Direct access to
``TIER_MODELS[tier]`` is forbidden — see the helper for why.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from config import settings
from models.session import ConversationPhase, IntentType, SessionState

logger = logging.getLogger(__name__)


class ModelTier(str, Enum):
    ECONOMY = "economy"
    STANDARD = "standard"
    PREMIUM = "premium"


# Tier → tier-specific model mapping. ONLY consulted when
# MODEL_ROUTING_ENABLED=True. Use ``get_model_for_tier(tier)`` instead of
# indexing this dict directly so the routing-disabled path stays in sync.
TIER_MODELS = {
    ModelTier.ECONOMY: settings.MODEL_ECONOMY,
    ModelTier.STANDARD: settings.MODEL_STANDARD,
    ModelTier.PREMIUM: settings.MODEL_PREMIUM,
}


def get_model_for_tier(tier: ModelTier) -> str:
    """Resolve a tier to a concrete Gemini model name.

    This is the **single source of truth** for model selection. When routing
    is disabled, all tiers collapse to ``settings.GEMINI_MODEL`` so the
    operator gets exactly the model they configured in ``.env``. When
    routing is enabled, the tier maps to its dedicated config setting.

    The historical bug this prevents: ``_make_decision`` used to call
    ``TIER_MODELS[tier]`` directly even when routing was disabled, which
    silently overrode ``GEMINI_MODEL`` with whatever ``MODEL_PREMIUM`` was
    set to. Recent commits switched ``GEMINI_MODEL=gemini-2.0-flash`` for
    "2-3s responses" but every conversation kept using gemini-2.5-pro
    because of this leak. Centralizing the resolution in one function
    makes the bug class impossible to reintroduce.
    """
    if not settings.MODEL_ROUTING_ENABLED:
        return settings.GEMINI_MODEL
    return TIER_MODELS[tier]

# Tier → generation config
TIER_CONFIGS = {
    ModelTier.ECONOMY: {
        "max_output_tokens": 1024,
        "temperature": settings.RESPONSE_TEMPERATURE,
        "automatic_function_calling": {"disable": True},
        "safety_settings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    },
    ModelTier.STANDARD: {
        "max_output_tokens": 2048,
        "temperature": settings.RESPONSE_TEMPERATURE,
        "automatic_function_calling": {"disable": True},
        "safety_settings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    },
    ModelTier.PREMIUM: {
        "max_output_tokens": 2048,
        "temperature": settings.RESPONSE_TEMPERATURE,
        "automatic_function_calling": {"disable": True},
        "safety_settings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    },
}


@dataclass
class RoutingDecision:
    """Output of the routing decision engine."""
    tier: ModelTier
    model_name: str
    config_override: Dict
    reason: str


def _compute_complexity_score(
    intent_analysis: Dict,
    session: SessionState,
    has_rag_context: bool,
) -> int:
    """Score 0-6 indicating message complexity for tier escalation."""
    score = 0

    signals = session.signals_collected if hasattr(session, "signals_collected") else {}
    if len(signals) >= 3:
        score += 1

    if session.turn_count >= 5:
        score += 1

    if has_rag_context:
        score += 1

    urgency = intent_analysis.get("urgency", "normal")
    if urgency in ("high", "crisis"):
        score += 1

    emotion = intent_analysis.get("emotion", "neutral")
    if emotion and emotion != "neutral":
        score += 1

    history_len = len(session.conversation_history) if session.conversation_history else 0
    if history_len >= 8:
        score += 1

    return score


# Thread-local storage for current intent analysis (read by _make_decision)
_current_intent_analysis: Dict = {}


def route(
    intent_analysis: Dict,
    phase: ConversationPhase,
    session: SessionState,
    has_rag_context: bool = False,
) -> RoutingDecision:
    """
    Determine which model tier to use for this request.

    Decision tree:
    1. Routing disabled? → PREMIUM (current behavior)
    2. Crisis/high urgency? → PREMIUM
    3. GREETING? → ECONOMY
    4. CLOSURE? → ECONOMY
    5. LISTENING phase + short message? → ECONOMY
    6. ASKING_INFO + needs_direct_answer? → STANDARD
    7. EXPRESSING_EMOTION? → STANDARD
    8. ASKING_PANCHANG? → ECONOMY
    9. PRODUCT_SEARCH? → ECONOMY
    10. GUIDANCE + RAG + signals>=3? → PREMIUM
    11. GUIDANCE + RAG? → STANDARD
    12. SEEKING_GUIDANCE + complex? → PREMIUM
    13. SEEKING_GUIDANCE (simple)? → STANDARD
    14. Default → STANDARD
    """

    global _current_intent_analysis
    _current_intent_analysis = intent_analysis

    intent = intent_analysis.get("intent")
    # Normalize to IntentType enum if string
    if isinstance(intent, str):
        try:
            intent = IntentType(intent)
        except ValueError:
            intent = IntentType.OTHER

    urgency = intent_analysis.get("urgency", "normal")
    needs_direct = intent_analysis.get("needs_direct_answer", False)

    # 1. Feature flag — routing disabled, use PREMIUM but still apply phase token budgets
    if not settings.MODEL_ROUTING_ENABLED:
        return _make_decision(ModelTier.PREMIUM, "routing_disabled", phase, intent=intent)

    # 2. Crisis / high urgency → PREMIUM
    if urgency in ("high", "crisis"):
        return _make_decision(ModelTier.PREMIUM, "crisis_or_high_urgency", phase, intent=intent)

    # 3. GREETING → ECONOMY
    if intent == IntentType.GREETING:
        return _make_decision(ModelTier.ECONOMY, "greeting", phase, intent=intent)

    # 4. CLOSURE → ECONOMY
    if intent == IntentType.CLOSURE:
        return _make_decision(ModelTier.ECONOMY, "closure", phase, intent=intent)

    # 5. LISTENING phase + short message → ECONOMY
    if phase == ConversationPhase.LISTENING:
        last_msg = ""
        if session.conversation_history:
            user_msgs = [m for m in session.conversation_history if m.get("role") == "user"]
            if user_msgs:
                last_msg = user_msgs[-1].get("content", "")
        if len(last_msg.split()) < 12:
            return _make_decision(ModelTier.ECONOMY, "listening_short_message", phase, intent=intent)

    # 6. ASKING_INFO + direct answer → STANDARD
    if intent == IntentType.ASKING_INFO and needs_direct:
        return _make_decision(ModelTier.STANDARD, "asking_info_direct", phase, intent=intent)

    # 7. EXPRESSING_EMOTION → STANDARD
    if intent == IntentType.EXPRESSING_EMOTION:
        return _make_decision(ModelTier.STANDARD, "expressing_emotion", phase, intent=intent)

    # 7b. ASKING_INFO without needs_direct_answer → ECONOMY (simple info queries)
    if intent == IntentType.ASKING_INFO and not needs_direct:
        return _make_decision(ModelTier.ECONOMY, "asking_info_simple", phase, intent=intent)

    # 8. ASKING_PANCHANG → ECONOMY
    if intent == IntentType.ASKING_PANCHANG:
        return _make_decision(ModelTier.ECONOMY, "asking_panchang", phase, intent=intent)

    # 9. PRODUCT_SEARCH → ECONOMY
    if intent == IntentType.PRODUCT_SEARCH:
        return _make_decision(ModelTier.ECONOMY, "product_search", phase, intent=intent)

    # 10-11. GUIDANCE phase with RAG context
    if phase == ConversationPhase.GUIDANCE and has_rag_context:
        complexity = _compute_complexity_score(intent_analysis, session, has_rag_context)
        signals = session.signals_collected if hasattr(session, "signals_collected") else {}
        if len(signals) >= 3 or complexity >= 4:
            return _make_decision(ModelTier.PREMIUM, f"guidance_rag_complex(score={complexity})", phase, intent=intent)
        if complexity < 3:
            return _make_decision(ModelTier.ECONOMY, f"guidance_rag_simple(score={complexity})", phase, intent=intent)
        return _make_decision(ModelTier.STANDARD, "guidance_rag_standard", phase, intent=intent)

    # 12-13. SEEKING_GUIDANCE
    if intent == IntentType.SEEKING_GUIDANCE:
        complexity = _compute_complexity_score(intent_analysis, session, has_rag_context)
        if complexity >= 4:
            return _make_decision(ModelTier.PREMIUM, f"seeking_guidance_complex(score={complexity})", phase, intent=intent)
        return _make_decision(ModelTier.STANDARD, "seeking_guidance_standard", phase, intent=intent)

    # 14. Default
    return _make_decision(ModelTier.STANDARD, "default", phase, intent=intent)


def _make_decision(
    tier: ModelTier,
    reason: str,
    phase: Optional[ConversationPhase] = None,
    intent: Optional[IntentType] = None,
) -> RoutingDecision:
    """Build a RoutingDecision with adaptive, LLM-driven token budget.

    Token budget is delegated to TokenBudgetCalculator.
    llm/service.py respects whatever is set here — no further overrides.
    """
    from services.token_budget import calculate_budget

    # Resolve model via the single helper. When MODEL_ROUTING_ENABLED=False
    # this returns settings.GEMINI_MODEL for ALL tiers — which is what
    # "routing disabled" actually means.
    model = get_model_for_tier(tier)
    config = TIER_CONFIGS[tier].copy()

    # Adaptive token budget — uses LLM's expected_length + phase + intent
    budget = calculate_budget(
        analysis={"expected_length": _current_intent_analysis.get("expected_length", "moderate"),
                  "intent": intent} if _current_intent_analysis else {"intent": intent},
        phase=phase,
    )
    config["max_output_tokens"] = budget.ceiling

    logger.info(f"MODEL_ROUTE | tier={tier.value} model={model} reason={reason} budget={budget.ceiling} ({budget.reason})")
    return RoutingDecision(
        tier=tier,
        model_name=model,
        config_override=config,
        reason=reason,
    )


class ModelRouter:
    """Stateless router — wraps the `route()` function for service injection."""

    def route(
        self,
        intent_analysis: Dict,
        phase: ConversationPhase,
        session: SessionState,
        has_rag_context: bool = False,
    ) -> RoutingDecision:
        return route(intent_analysis, phase, session, has_rag_context)


_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router
