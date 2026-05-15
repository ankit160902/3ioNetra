"""
OffTopicDetector — single source of truth for "is this query out of scope?".

Background
----------
The previous codebase relied on a single similarity threshold
(``MIN_SIMILARITY_SCORE``) to reject off-topic queries. That approach failed
in two directions:

* The threshold was set differently in three places (``.env=0.12``,
  ``config.py=0.28``, ``CLAUDE.md=0.15``) so production behavior depended on
  whichever value won at startup.
* Cosine similarity is a coarse signal — embedding models trained on broad
  corpora will happily return ``0.6+`` matches for "stock market prediction"
  against a Gita verse about acting without attachment to outcome.

The clean architectural fix is **not** another threshold. The IntentAgent
already runs an LLM call per turn that returns a structured ``is_off_topic``
boolean (see ``services/intent_agent.py`` field 13 in INTENT_PROMPT). That's
the correct authority — semantic, context-aware, and zero hardcoded
vocabulary. This module is a thin wrapper that:

    1. Reads the LLM verdict from the analysis dict
    2. Returns a polite redirect message sourced from YAML
    3. Provides a single import surface so callers don't have to know which
       dict key holds the boolean — refactoring the IntentAgent contract
       only changes one file.

For the standalone ``/text/query`` endpoint that does NOT go through
IntentAgent, the detector exposes a ``classify_async`` helper that runs
IntentAgent on demand. This keeps the contract uniform across both call
paths without duplicating logic.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OffTopicDetector:
    """Stateless detector. Construct once at startup, share via singleton."""

    def __init__(self, prompt_manager=None, intent_agent=None):
        if prompt_manager is None:
            from services.prompt_manager import get_prompt_manager
            prompt_manager = get_prompt_manager()
        self._pm = prompt_manager
        # IntentAgent is loaded lazily so the detector module doesn't pull
        # in the LLM service at import time (matters for unit tests).
        self._intent_agent = intent_agent
        self._redirect_cache: Optional[str] = None

    def _load_intent_agent(self):
        if self._intent_agent is None:
            from services.intent_agent import get_intent_agent
            self._intent_agent = get_intent_agent()
        return self._intent_agent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def is_off_topic(analysis: dict) -> bool:
        """Check an existing IntentAgent analysis dict for the off-topic flag.

        Use this in the conversational pipeline where IntentAgent has already
        run. Returns False if the key is missing — never raises, never blocks
        a real conversation because of a missing field.
        """
        if not isinstance(analysis, dict):
            return False
        return bool(analysis.get("is_off_topic", False))

    async def classify_async(self, query: str, *, context: str = "") -> bool:
        """Run IntentAgent on a raw query and return its off-topic verdict.

        For the standalone ``/text/query`` endpoint that doesn't otherwise
        invoke IntentAgent. The shared LLM call is cached internally by
        IntentAgent's LRU so two calls with the same text are cheap.
        """
        agent = self._load_intent_agent()
        if not agent.available:
            # If the LLM isn't available, fail open — let RAG handle the
            # query. This avoids blocking users when Gemini is down.
            return False
        try:
            analysis = await agent.classify(query, context=context)
        except Exception as exc:
            logger.warning(f"OffTopicDetector classify_async failed: {exc} — failing open")
            return False
        return self.is_off_topic(analysis)

    def get_redirect_message(self) -> str:
        """Return the user-facing redirect message from YAML.

        Cached after first read because the YAML is loaded once at startup
        and mutating it requires a process restart anyway.
        """
        if self._redirect_cache is not None:
            return self._redirect_cache
        raw = self._pm.get_value(
            "spiritual_mitra", "off_topic.redirect_message", default=""
        )
        if not raw:
            logger.error(
                "OffTopicDetector: off_topic.redirect_message missing in YAML — "
                "using a minimal hardcoded fallback."
            )
            raw = (
                "That's not really my area, my friend. I'm here for life's "
                "deeper questions. Is there something on your mind I can help with?"
            )
        self._redirect_cache = raw.strip()
        return self._redirect_cache


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_instance: Optional[OffTopicDetector] = None


def get_off_topic_detector() -> OffTopicDetector:
    global _instance
    if _instance is None:
        _instance = OffTopicDetector()
    return _instance
