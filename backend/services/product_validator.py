"""Product Decision Validator — post-IntentAgent override layer.

Validates the IntentAgent's product_signal using conversation state,
emotion analysis, and adversarial detection. Only SUPPRESSES — never
triggers products. The IntentAgent remains the sole positive authority.

Each rule addresses a structural failure pattern, not a specific message:
  Rule 1: Emotion-product conflict (angry/frustrated + products triggered)
  Rule 2: Follow-up context (asking about already-shown products)
  Rule 3: Adversarial/injection suppression
  Rule 4: Reverse-intent detection (user explicitly says NO products)
  Rule 5: Turn 1 timing guard
"""

import logging
import re
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Phrases that indicate the user is REJECTING/criticizing products, not asking for them.
# These are SUPPRESSION patterns (safety net), not triggering patterns.
_NEGATIVE_PRODUCT_PATTERNS = [
    "do not show", "don't show", "dont show", "stop showing",
    "no products", "not want product", "don't want product", "dont want product",
    "hate shopping", "won't solve", "wont solve",
    "take your product", "take your recommendation",
    "not interested in buy", "not interested in shop",
    "don't need product", "dont need product",
    "no more product", "enough product",
    "overpriced", "waste of money", "broke in", "terrible quality",
    "bad quality", "didn't work", "didnt work", "scam", "fraud",
    "regret buy", "regret purchas",
]

# Adversarial/injection patterns that should suppress products
_ADVERSARIAL_PATTERNS = [
    "system override", "debug mode", "developer mode",
    "pretend i said", "as the developer", "as the creator",
    "enable product", "testing your", "test your product",
    "i'm testing", "im testing",
    "show me products but hide",
    "magic word",
]

# Phrases indicating the user IS seeking products/items despite emotional context.
# Used by Rule 1 to avoid suppressing legitimate product interest during distress.
# Phrase-level matching (not single words) to reduce false positives.
_EXPLICIT_PRODUCT_PHRASES = [
    # English buy/shop intent
    "buy", "purchase", "need to get", "want to get", "show me", "recommend me",
    # English suggestion-seeking (product-eligible)
    "suggest product", "suggest something", "suggest some", "recommend product",
    "recommend something", "what product", "which product",
    "help me find", "is there anything", "something that can help",
    "something that might help", "anything that can",
    # Hindi / Hinglish
    "kuch suggest", "kuch batao", "kuch recommend", "product batao",
    "kya mil sakta", "kuch chahiye",
]

# Follow-up reference words (user is talking ABOUT shown products, not requesting NEW ones)
_FOLLOWUP_INDICATORS = [
    "first one", "second one", "third one", "fourth one", "fifth one",
    "that one", "which one", "this one",
    "the one you", "you showed", "you recommended", "you suggested",
    "compare", "comparison", "cheaper", "cheapest", "expensive",
    "better", "best", "difference between",
    "tell me more about", "more about the", "details about",
    "how do i use", "how to use",
]


def validate_product_signal(
    product_signal: Dict[str, Any],
    analysis: Dict[str, Any],
    message: str,
    session,
) -> Dict[str, Any]:
    """Validate and potentially override the IntentAgent's product signal.

    Returns a (possibly modified) product_signal dict. Only ever SUPPRESSES
    products — never changes "none" to something else.

    Args:
        product_signal: The IntentAgent's product_signal dict
        analysis: Full IntentAgent analysis dict
        message: The user's raw message
        session: Current SessionState (for turn_count, recent_products, etc.)
    """
    intent = product_signal.get("intent", "none")

    # If IntentAgent already says no products, nothing to validate
    if intent in ("none", "negative"):
        return product_signal

    msg_lower = message.lower().strip()

    # ── Rule 1: Emotion-Product Conflict ──
    # If user is angry/frustrated/grieving AND products triggered,
    # but there's no explicit buy/purchase intent → suppress.
    # The phrase list covers natural language patterns in English and Hindi
    # so that users who say "suggest something that might help" during
    # emotional distress are not blocked.
    emotion = (analysis.get("emotion") or "neutral").lower()
    conflict_emotions = {"anger", "frustration", "grief", "despair", "shame", "disgust"}
    if emotion in conflict_emotions:
        has_explicit_buy = any(w in msg_lower for w in _EXPLICIT_PRODUCT_PHRASES)
        if not has_explicit_buy:
            logger.info(f"ProductValidator Rule 1: emotion={emotion} + no explicit buy → suppressed")
            return _suppress(product_signal, "emotion_conflict")

    # ── Rule 2: Follow-Up Context ──
    # If products were shown recently and this message references them,
    # it's a follow-up question — don't trigger new product search.
    if session.recent_products:
        is_followup = any(indicator in msg_lower for indicator in _FOLLOWUP_INDICATORS)
        if not is_followup:
            # Also check if message references a recently shown product by name
            for p in session.recent_products[-5:]:
                pname = (p.get("name") or "").lower()
                if pname and len(pname) > 5 and pname[:12] in msg_lower:
                    is_followup = True
                    break
        if is_followup:
            logger.info(f"ProductValidator Rule 2: follow-up about existing products → suppressed")
            return _suppress(product_signal, "followup_context")

    # ── Rule 3: Adversarial/Injection Suppression ──
    if any(p in msg_lower for p in _ADVERSARIAL_PATTERNS):
        logger.info(f"ProductValidator Rule 3: adversarial pattern detected → suppressed")
        return _suppress(product_signal, "adversarial")

    # ── Rule 4: Reverse-Intent Detection ──
    # User explicitly says "no products" / "don't show" / criticizes quality
    if any(p in msg_lower for p in _NEGATIVE_PRODUCT_PATTERNS):
        logger.info(f"ProductValidator Rule 4: negative product sentiment → suppressed")
        return _suppress(product_signal, "negative_sentiment")

    # ── Rule 5: Turn 1 Timing Guard ──
    # Non-explicit products on Turn 1 should be suppressed.
    # turn_count is already incremented before this runs, so check <= 1.
    if intent != "explicit_search" and session.turn_count <= 1:
        logger.info(f"ProductValidator Rule 5: Turn 1 non-explicit → suppressed")
        return _suppress(product_signal, "turn1_guard")

    # All rules passed — signal is valid
    return product_signal


def _suppress(signal: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Create a suppressed copy of the product signal."""
    return {
        "intent": "none",
        "confidence": 0.0,
        "type_filter": signal.get("type_filter", "any"),
        "search_keywords": [],
        "max_results": 0,
        "sensitivity_note": f"suppressed:{reason}",
    }
