"""
ContextValidator — Rock-solid 5-rule gate that sits between RAG retrieval and LLM prompt construction.

Rules applied in order:
  1. Relevance Gate     – drop docs below min_score threshold
  2. Content Gate       – drop docs with empty/placeholder/too-short text
  3. Type Gate          – exclude doc types that are semantically wrong for this query
  4. Scripture Gate     – hard-filter to allowed_scriptures if specified
  5. Diversity Gate     – max N docs from the same source (prevents LLM echo)
"""

import logging
from typing import List, Dict, Optional

from models.session import IntentType

logger = logging.getLogger(__name__)

# Placeholder strings that sneak past empty-string checks
_CONTENT_PLACEHOLDERS = {
    "intermediate", "beginner", "advanced", "none", "null",
    "n/a", "na", "unknown", "undefined", "",
}

EMOTIONAL_HEALING_INTENTS = {IntentType.EXPRESSING_EMOTION, IntentType.OTHER}

_SPATIAL_MARKERS = frozenset({"maidan", "ground", "complex", "road", "street", "near ", "located", "address"})


class ContextValidator:
    """
    Validates and filters a list of RAG-retrieved documents before they reach the LLM.
    
    Usage:
        validator = ContextValidator()
        clean_docs = validator.validate(
            docs=raw_rag_docs,
            intent=IntentType.EXPRESSING_EMOTION,
            allowed_scriptures=["Bhagavad Gita", "Ramayana"],
            temple_interest=False,
            min_score=0.15,
        )
    """

    def validate(
        self,
        docs: List[Dict],
        intent: Optional[IntentType] = None,
        allowed_scriptures: Optional[List[str]] = None,
        temple_interest: bool = False,
        min_score: float = 0.12,
        max_per_source: int = 2,
        max_docs: int = 5,
    ) -> List[Dict]:
        """
        Apply all 5 gates sequentially.  Returns a clean, ranked list.
        """
        if not docs:
            return []

        n_before = len(docs)
        docs = self._gate_relevance(docs, min_score)
        docs = self._gate_content(docs)
        docs = self._gate_type(docs, intent, temple_interest)
        docs = self._gate_scripture(docs, allowed_scriptures)
        docs = self._gate_diversity(docs, max_per_source)
        docs = docs[:max_docs]

        n_after = len(docs)
        logger.info(
            f"ContextValidator: {n_before} → {n_after} docs | "
            f"intent={intent} | allowed={allowed_scriptures} | min_score={min_score}"
        )
        return docs

    # ---------------------------------------------------------------
    # Gate 1 – Relevance
    # ---------------------------------------------------------------

    def _gate_relevance(self, docs: List[Dict], min_score: float) -> List[Dict]:
        """Drop documents below the minimum cosine similarity threshold."""
        kept = [d for d in docs if self._get_score(d) >= min_score]
        dropped = len(docs) - len(kept)
        if dropped:
            logger.debug(f"Relevance gate: dropped {dropped} low-score doc(s) (threshold={min_score})")
        return kept

    def _get_score(self, doc: Dict) -> float:
        """Return the best available score from a doc (final_score > rerank_score > score)."""
        return float(
            doc.get("final_score")
            or doc.get("rerank_score")
            or doc.get("score")
            or 0.0
        )

    # ---------------------------------------------------------------
    # Gate 2 – Content quality
    # ---------------------------------------------------------------

    def _gate_content(self, docs: List[Dict]) -> List[Dict]:
        """Remove docs with empty, too-short, or placeholder text."""
        kept = []
        for doc in docs:
            text = (
                doc.get("text") or
                doc.get("meaning") or
                doc.get("translation") or
                doc.get("hindi") or
                ""
            ).strip()

            if text.lower() in _CONTENT_PLACEHOLDERS:
                logger.debug(f"Content gate: dropped placeholder doc from '{doc.get('scripture')}'")
                continue

            if len(text) < 20:
                logger.debug(f"Content gate: dropped too-short doc ({len(text)} chars) from '{doc.get('scripture')}'")
                continue

            kept.append(doc)

        return kept

    # ---------------------------------------------------------------
    # Gate 3 – Type appropriateness
    # ---------------------------------------------------------------

    def _gate_type(
        self, docs: List[Dict], intent: Optional[IntentType], temple_interest: bool
    ) -> List[Dict]:
        """
        Remove docs whose type is semantically wrong for this intent.

        Rules:
        - Emotional / generic intents: exclude bare temple/location docs
          UNLESS temple_interest is True (user wants pilgrimage).
        - Procedural queries: deprioritize philosophical-only docs
          (they stay but get pushed to the back via sort).
        """
        if not intent:
            return docs

        is_emotional = intent in EMOTIONAL_HEALING_INTENTS
        is_howto = intent in {IntentType.SEEKING_GUIDANCE, IntentType.ASKING_INFO}

        kept = []
        deferred = []  # Added at the end, lower priority

        for doc in docs:
            doc_type = (doc.get("type") or "scripture").lower()
            doc_text = (doc.get("text", "") + " " + doc.get("reference", "")).lower()

            # Detect spatial/location-only documents
            is_spatial = doc_type == "temple" or any(m in doc_text for m in _SPATIAL_MARKERS)

            if is_emotional and is_spatial and not temple_interest:
                logger.debug(
                    f"Type gate: deferred temple/spatial doc from intent={intent}: {doc.get('scripture')}"
                )
                deferred.append(doc)
                continue

            # For how-to queries: keep procedural docs first, defer pure philosophy last
            if is_howto and doc_type == "procedural":
                kept.insert(0, doc)  # Boost to front
                continue

            kept.append(doc)

        return kept + deferred

    # ---------------------------------------------------------------
    # Gate 4 – Scripture allowlist
    # ---------------------------------------------------------------

    def _gate_scripture(
        self, docs: List[Dict], allowed_scriptures: Optional[List[str]]
    ) -> List[Dict]:
        """
        If an allowlist is specified, hard-filter to matching scriptures.
        Falls back to all docs if filtering would leave nothing.
        """
        if not allowed_scriptures:
            return docs

        # Normalise for case-insensitive matching
        allowed_lower = {s.lower() for s in allowed_scriptures}

        filtered = [
            d for d in docs
            if (d.get("scripture") or "").lower() in allowed_lower
        ]

        if not filtered:
            logger.warning(
                f"Scripture gate: allowlist {allowed_scriptures} matched nothing — "
                "returning unfiltered docs."
            )
            return docs  # Graceful fallback: never return empty

        dropped = len(docs) - len(filtered)
        if dropped:
            logger.debug(f"Scripture gate: dropped {dropped} out-of-scope scripture doc(s)")
        return filtered

    # ---------------------------------------------------------------
    # Gate 5 – Source diversity
    # ---------------------------------------------------------------

    def _gate_diversity(self, docs: List[Dict], max_per_source: int) -> List[Dict]:
        """
        Limit the number of documents from the same source to avoid
        echo-chamber RAG (e.g., 5 Bhagavad Gita verses for a health query).
        """
        source_counts: Dict[str, int] = {}
        kept = []

        for doc in docs:
            src = (doc.get("scripture") or "unknown").lower()
            count = source_counts.get(src, 0)

            if count < max_per_source:
                kept.append(doc)
                source_counts[src] = count + 1
            else:
                logger.debug(f"Diversity gate: skipped extra doc from '{src}' (limit={max_per_source})")

        return kept


# ---------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------

_context_validator: Optional["ContextValidator"] = None


def get_context_validator() -> "ContextValidator":
    global _context_validator
    if _context_validator is None:
        _context_validator = ContextValidator()
    return _context_validator
