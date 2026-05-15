"""
QueryNormalizer — single point of entry for preprocessing user query strings
before they reach RAG retrieval or the LLM.

Replaces a set of helpers that previously lived inside ``rag/pipeline.py``,
including a Levenshtein-based spell corrector that mangled common English
words into Sanskrit terms (e.g. "How" → "homa", "Give" → "gita") because it
operated on whole strings against a hardcoded dharmic vocabulary without a
stopword mask.

**Design principle: zero hardcoded domain knowledge.**

This normalizer is intentionally narrow:
    1. Unicode NFKC normalization
    2. Whitespace cleanup

That's it. There is no dharmic-term lookup, no English→Sanskrit dictionary,
no spell correction. Every form of *semantic* or *bilingual* preprocessing
that the previous implementation tried to do with hardcoded data is now the
responsibility of upstream LLM components:

    * Query variants for bilingual / synonym retrieval → produced by
      ``services.intent_agent.IntentAgent`` and threaded through to
      ``RAGPipeline.search(query_variants=...)`` already.
    * On-topic / dharmic relevance detection → ``IntentAgent.is_dharmic_query``
      (added in the off-topic detector phase).
    * Morphology / fuzzy matching → handled natively by the multilingual E5
      embedding model and the BGE CrossEncoder reranker.

If a downstream caller wants to extend normalization (e.g. add a real
spell-corrector behind a feature flag), build it as a separate service —
do not reintroduce hardcoded vocabulary tables here.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NormalizedQuery:
    """Result of QueryNormalizer.normalize().

    Carries both the original and normalized forms so callers can choose:
        * cache keys → use ``normalized``
        * RAG retrieval → use ``normalized`` (variants come from IntentAgent)
        * UI / logging → show ``original``
    """
    original: str
    normalized: str
    language: Optional[str] = None


def _is_devanagari(text: str) -> bool:
    """True iff text contains any Devanagari codepoint (U+0900–U+097F)."""
    return any("\u0900" <= ch <= "\u097F" for ch in text)


class QueryNormalizer:
    """Stateless normalizer. Construct once and call ``normalize()`` per query.

    The class form is used (rather than module-level functions) so dependency
    injection is straightforward in tests and so a future preprocessing
    backend can be plugged in via the constructor without touching callers.
    """

    def normalize(
        self,
        query: str,
        *,
        language: Optional[str] = None,
    ) -> NormalizedQuery:
        """Normalize a raw user query.

        Args:
            query: Raw user input.
            language: Optional ISO language hint from an upstream detector.
                Currently informational only — preserved on the result for
                downstream consumers that may need it.
        """
        if query is None:
            return NormalizedQuery(original="", normalized="", language=language)

        original = query
        # Unicode normalization first — collapses precomposed and decomposed
        # forms so token comparisons are stable across input methods.
        normalized = unicodedata.normalize("NFKC", query)
        # Whitespace cleanup: collapse runs of whitespace to a single space.
        normalized = " ".join(normalized.split())

        return NormalizedQuery(
            original=original,
            normalized=normalized,
            language=language,
        )


# ---------------------------------------------------------------------------
# Module-level singleton — use ``get_query_normalizer()`` from callers so
# tests can monkeypatch a different instance via dependency injection.
# ---------------------------------------------------------------------------
_instance: Optional[QueryNormalizer] = None


def get_query_normalizer() -> QueryNormalizer:
    global _instance
    if _instance is None:
        _instance = QueryNormalizer()
    return _instance
