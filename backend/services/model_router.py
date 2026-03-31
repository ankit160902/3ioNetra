"""
Multi-Model Routing Engine for 3ioNetra
========================================
Routes cheap models for simple requests, premium models for complex guidance,
reducing cost while maintaining quality.

Feature flag: MODEL_ROUTING_ENABLED=false by default.
When disabled, all calls go to settings.GEMINI_MODEL (current behavior).
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


# Tier → default model mapping
TIER_MODELS = {
    ModelTier.ECONOMY: settings.MODEL_ECONOMY,
    ModelTier.STANDARD: settings.MODEL_STANDARD,
    ModelTier.PREMIUM: settings.MODEL_PREMIUM,
}

# Tier → generation config
TIER_CONFIGS = {
    ModelTier.ECONOMY: {
        "max_output_tokens": 256,
        "thinking_config": {"thinking_budget": 0},
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
        "max_output_tokens": 400,
        "thinking_config": {"thinking_budget": 0},
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
        "max_output_tokens": 512,
        "thinking_config": {"thinking_budget": 0},
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

    # 1. Feature flag
    if not settings.MODEL_ROUTING_ENABLED:
        return RoutingDecision(
            tier=ModelTier.PREMIUM,
            model_name=settings.GEMINI_MODEL,
            config_override=TIER_CONFIGS[ModelTier.PREMIUM],
            reason="routing_disabled",
        )

    intent = intent_analysis.get("intent")
    # Normalize to IntentType enum if string
    if isinstance(intent, str):
        try:
            intent = IntentType(intent)
        except ValueError:
            intent = IntentType.OTHER

    urgency = intent_analysis.get("urgency", "normal")
    needs_direct = intent_analysis.get("needs_direct_answer", False)

    # 2. Crisis / high urgency → PREMIUM
    if urgency in ("high", "crisis"):
        return _make_decision(ModelTier.PREMIUM, "crisis_or_high_urgency", phase)

    # 3. GREETING → ECONOMY
    if intent == IntentType.GREETING:
        return _make_decision(ModelTier.ECONOMY, "greeting", phase)

    # 4. CLOSURE → ECONOMY
    if intent == IntentType.CLOSURE:
        return _make_decision(ModelTier.ECONOMY, "closure", phase)

    # 5. LISTENING phase + short message → ECONOMY
    if phase == ConversationPhase.LISTENING:
        last_msg = ""
        if session.conversation_history:
            user_msgs = [m for m in session.conversation_history if m.get("role") == "user"]
            if user_msgs:
                last_msg = user_msgs[-1].get("content", "")
        if len(last_msg.split()) < 12:
            return _make_decision(ModelTier.ECONOMY, "listening_short_message", phase)

    # 6. ASKING_INFO + direct answer → STANDARD
    if intent == IntentType.ASKING_INFO and needs_direct:
        return _make_decision(ModelTier.STANDARD, "asking_info_direct", phase)

    # 7. EXPRESSING_EMOTION → STANDARD
    if intent == IntentType.EXPRESSING_EMOTION:
        return _make_decision(ModelTier.STANDARD, "expressing_emotion", phase)

    # 7b. ASKING_INFO without needs_direct_answer → ECONOMY (simple info queries)
    if intent == IntentType.ASKING_INFO and not needs_direct:
        return _make_decision(ModelTier.ECONOMY, "asking_info_simple", phase)

    # 8. ASKING_PANCHANG → ECONOMY
    if intent == IntentType.ASKING_PANCHANG:
        return _make_decision(ModelTier.ECONOMY, "asking_panchang", phase)

    # 9. PRODUCT_SEARCH → ECONOMY
    if intent == IntentType.PRODUCT_SEARCH:
        return _make_decision(ModelTier.ECONOMY, "product_search", phase)

    # 10-11. GUIDANCE phase with RAG context
    if phase == ConversationPhase.GUIDANCE and has_rag_context:
        complexity = _compute_complexity_score(intent_analysis, session, has_rag_context)
        signals = session.signals_collected if hasattr(session, "signals_collected") else {}
        if len(signals) >= 3 or complexity >= 4:
            return _make_decision(ModelTier.PREMIUM, f"guidance_rag_complex(score={complexity})", phase)
        if complexity < 3:
            return _make_decision(ModelTier.ECONOMY, f"guidance_rag_simple(score={complexity})", phase)
        return _make_decision(ModelTier.STANDARD, "guidance_rag_standard", phase)

    # 12-13. SEEKING_GUIDANCE
    if intent == IntentType.SEEKING_GUIDANCE:
        complexity = _compute_complexity_score(intent_analysis, session, has_rag_context)
        if complexity >= 4:
            return _make_decision(ModelTier.PREMIUM, f"seeking_guidance_complex(score={complexity})", phase)
        return _make_decision(ModelTier.STANDARD, "seeking_guidance_standard", phase)

    # 14. Default
    return _make_decision(ModelTier.STANDARD, "default", phase)


def _make_decision(tier: ModelTier, reason: str, phase: Optional[ConversationPhase] = None) -> RoutingDecision:
    """Helper to build a RoutingDecision.

    When *phase* is LISTENING, cap max_output_tokens to keep responses concise
    and reduce generation latency (saves 100-300ms).
    """
    model = TIER_MODELS[tier]
    config = TIER_CONFIGS[tier].copy()

    # Reduce token budget for listening phase — only ~150 tokens typically used
    if phase == ConversationPhase.LISTENING:
        if tier == ModelTier.ECONOMY:
            config["max_output_tokens"] = 256   # was 512
        elif tier == ModelTier.STANDARD:
            config["max_output_tokens"] = 512   # was 768

    logger.info(f"MODEL_ROUTE | tier={tier.value} model={model} reason={reason} max_tokens={config.get('max_output_tokens')}")
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
