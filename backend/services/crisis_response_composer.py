"""
CrisisResponseComposer — assembles crisis-path responses with progression.

Replaces the static byte-identical ``CRISIS_RESPONSE_TEMPLATE`` constant in
``services.safety_validator`` with a content-team-editable variant system
loaded from ``prompts/spiritual_mitra.yaml`` (key: ``crisis_response``).

Design rules (do not break):
    1. The helpline block is mandatory and non-negotiable. It is appended
       unconditionally to every response, sourced from YAML so the safety
       team can update numbers without code changes.
    2. Variants are chosen by ``crisis_turn_count`` so the user never sees
       the same byte-identical reply twice in a row. The last variant
       repeats indefinitely if the user remains in crisis — this is by
       design (we don't want a fourth-turn variant that's "softer" than
       the third because crisis stays at peak severity).
    3. NO spiritual reframing in this path. The composer never adds
       "everything happens for a reason", "this is karma", or any
       interpretation. It validates the user's feelings, offers breath
       grounding, and routes to professional help.
    4. The composer never invokes the LLM. We trust YAML content to be
       safe — adding an LLM round-trip on the crisis path would risk
       hallucination of unsafe content and add latency at exactly the
       moment the user can least afford to wait.

If a future iteration wants per-message empathetic personalization, that
should be a *separate* opt-in service wrapped in stricter prompt
constraints and validation — not added to this composer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from models.session import SessionState

logger = logging.getLogger(__name__)


@dataclass
class CrisisVariant:
    """One progression step in the crisis response sequence."""
    id: str
    preamble: str
    grounding: str
    invitation: str

    def render(self) -> str:
        # Each block is multi-line YAML with a trailing newline; strip + join
        # so the composed text is consistent regardless of YAML quirks.
        return "\n\n".join(
            block.strip() for block in (self.preamble, self.grounding, self.invitation)
            if block and block.strip()
        )


class CrisisResponseComposer:
    """Composes a crisis response. Stateless apart from the YAML it reads
    via PromptManager. Construct once at app startup."""

    def __init__(self, prompt_manager=None):
        if prompt_manager is None:
            from services.prompt_manager import get_prompt_manager
            prompt_manager = get_prompt_manager()
        self._pm = prompt_manager
        self._variants_cache: Optional[List[CrisisVariant]] = None
        self._helpline_cache: Optional[str] = None

    # ------------------------------------------------------------------
    # YAML loading
    # ------------------------------------------------------------------

    def _load_variants(self) -> List[CrisisVariant]:
        if self._variants_cache is not None:
            return self._variants_cache
        raw = self._pm.get_value(
            "spiritual_mitra", "crisis_response.variants", default=None
        )
        if not isinstance(raw, list) or not raw:
            logger.error(
                "CrisisResponseComposer: crisis_response.variants missing or empty in YAML — "
                "falling back to a single hardcoded variant for safety."
            )
            return [
                CrisisVariant(
                    id="fallback",
                    preamble="What you are feeling right now matters deeply, and you do not have to carry this alone.",
                    grounding="Take one slow breath with me. In, and out.",
                    invitation="When you are ready, please reach out to one of the numbers below.",
                )
            ]
        variants = [
            CrisisVariant(
                id=str(v.get("id", f"variant_{i}")),
                preamble=str(v.get("preamble", "")),
                grounding=str(v.get("grounding", "")),
                invitation=str(v.get("invitation", "")),
            )
            for i, v in enumerate(raw)
            if isinstance(v, dict)
        ]
        self._variants_cache = variants
        return variants

    def _load_helpline(self) -> str:
        if self._helpline_cache is not None:
            return self._helpline_cache
        raw = self._pm.get_value(
            "spiritual_mitra", "crisis_response.helpline_block", default=""
        )
        if not raw:
            logger.error(
                "CrisisResponseComposer: crisis_response.helpline_block missing in YAML — "
                "using a minimal hardcoded fallback (iCall) for safety."
            )
            raw = (
                "Please consider reaching out to iCall at 9152987821 — they "
                "are trained to listen and you do not need to face this alone."
            )
        self._helpline_cache = raw.strip()
        return self._helpline_cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(self, session: SessionState, user_message: str = "") -> str:
        """Build a crisis response and advance the session's crisis counter.

        Args:
            session: SessionState. ``session.crisis_turn_count`` is read and
                then incremented in place. Callers must persist the session
                after this call.
            user_message: The triggering user message. Currently unused but
                accepted so future LLM-personalized variants can use it.
        """
        variants = self._load_variants()
        if not variants:
            return self._load_helpline()  # extreme fallback

        # Use the count BEFORE incrementing so the first crisis turn picks
        # variant 0. min() pins to the last variant for any further turns.
        index = min(session.crisis_turn_count, len(variants) - 1)
        chosen = variants[index]
        session.crisis_turn_count += 1

        body = chosen.render()
        helpline = self._load_helpline()

        logger.warning(
            f"CrisisResponseComposer: session={session.session_id} "
            f"variant={chosen.id} (turn={session.crisis_turn_count}/{len(variants)})"
        )

        # Helpline goes between body and grounding so it stays prominent —
        # the user should see the number even if they only read the first
        # paragraph.
        return f"{chosen.preamble.strip()}\n\n{helpline}\n\n{chosen.grounding.strip()}\n\n{chosen.invitation.strip()}"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_instance: Optional[CrisisResponseComposer] = None


def get_crisis_response_composer() -> CrisisResponseComposer:
    global _instance
    if _instance is None:
        _instance = CrisisResponseComposer()
    return _instance
