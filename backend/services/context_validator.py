"""
ContextValidator — Rock-solid 6-rule gate that sits between RAG retrieval and LLM prompt construction.

Rules applied in order:
  1. Relevance Gate     – adaptive threshold anchored to top result (ratio varies by intent)
  2. Content Gate       – drop docs with empty/placeholder/too-short text
  3. Type Gate          – exclude doc types that are semantically wrong for this query
  4. Scripture Gate     – hard-filter to allowed_scriptures if specified
  5. Diversity Gate     – max N docs from the same source (prevents LLM echo)
  6. Tradition Gate     – max N docs from the same dharmic tradition
"""

import logging
from typing import List, Dict, Optional

_CURATED_EXEMPT_SOURCES = frozenset({"curated_concept", "curated_narrative"})

from config import settings
from models.session import IntentType
from rag.scoring_utils import get_doc_score

logger = logging.getLogger(__name__)

# Placeholder strings that sneak past empty-string checks
_CONTENT_PLACEHOLDERS = {
    "intermediate", "beginner", "advanced", "none", "null",
    "n/a", "na", "unknown", "undefined", "",
}

_SPATIAL_MARKERS = frozenset({"maidan", "ground", "complex", "road", "street", "near ", "located", "address"})

_MEDITATION_EXACT_KEYWORDS = frozenset({
    "meditation", "meditate", "dhyan", "dhyana", "ध्यान",
    "mindfulness", "mindful", "vipassana",
})
_MEDITATION_ADJACENT_KEYWORDS = frozenset({
    "breathing exercise", "pranayama", "प्राणायाम",
})


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
        query: str = "",
        min_score: float = settings.MIN_SIMILARITY_SCORE,
        max_per_source: int = settings.MAX_DOCS_PER_SOURCE,
        max_docs: int = settings.RERANK_TOP_K,
    ) -> List[Dict]:
        """
        Apply all 5 gates sequentially.  Returns a clean, ranked list.
        Context verses (from parent-child expansion) bypass the gates and are
        re-attached only if their parent doc survives filtering.
        """
        if not docs:
            return []

        n_before = len(docs)

        # Separate context verses from primary docs
        context_verses = [d for d in docs if d.get("is_context_verse")]
        primary_docs = [d for d in docs if not d.get("is_context_verse")]

        meditation_interest = bool(query) and any(kw in query.lower() for kw in _MEDITATION_EXACT_KEYWORDS)
        primary_docs = self._gate_relevance(primary_docs, min_score, intent)
        primary_docs = self._gate_content(primary_docs)
        primary_docs = self._gate_type(primary_docs, intent, temple_interest, meditation_interest)
        primary_docs = self._gate_scripture(primary_docs, allowed_scriptures)
        primary_docs = self._gate_diversity(primary_docs, max_per_source)
        primary_docs = self._gate_tradition_diversity(primary_docs, settings.MAX_DOCS_PER_TRADITION)
        primary_docs = primary_docs[:max_docs]

        if not primary_docs and n_before > 0:
            logger.warning(
                f"ContextValidator: ALL {n_before} docs filtered out | "
                f"intent={intent} | allowed={allowed_scriptures} | "
                f"min_score={min_score} | query='{query[:80]}'"
            )

        # Re-attach context verses only if their parent survived
        if context_verses:
            final_docs = []
            for d in primary_docs:
                final_docs.append(d)
                for cv in context_verses:
                    if cv.get("context_parent_ref") == d.get("reference"):
                        final_docs.append(cv)
        else:
            final_docs = primary_docs

        n_after = len(final_docs)
        logger.info(
            f"ContextValidator: {n_before} → {n_after} docs "
            f"({len(context_verses)} context verse(s)) | "
            f"intent={intent} | allowed={allowed_scriptures} | min_score={min_score}"
        )
        return final_docs

    # ---------------------------------------------------------------
    # Gate 1 – Relevance
    # ---------------------------------------------------------------

    def _gate_relevance(self, docs: List[Dict], min_score: float, intent: Optional[IntentType] = None) -> List[Dict]:
        """Drop documents below a dynamic threshold anchored to the top result.
        The ratio adapts per intent: emotional queries use a looser threshold (0.40)
        so broader results surface; factual/citation queries use a tighter one (0.55).
        """
        if not docs:
            return docs
        top_score = max(get_doc_score(d) for d in docs)

        # Adaptive ratio based on intent type
        if intent == IntentType.EXPRESSING_EMOTION:
            ratio = settings.RELEVANCE_RATIO_EMOTIONAL
        elif intent == IntentType.ASKING_INFO:
            ratio = settings.RELEVANCE_RATIO_CITATION
        elif intent == IntentType.SEEKING_GUIDANCE:
            ratio = settings.RELEVANCE_RATIO_GUIDANCE
        else:
            ratio = settings.RELEVANCE_RATIO_DEFAULT

        effective_min = max(min_score, top_score * ratio)
        kept = [d for d in docs if get_doc_score(d) >= effective_min]
        dropped = len(docs) - len(kept)
        if dropped:
            logger.debug(f"Relevance gate: dropped {dropped} low-score doc(s) (effective_threshold={effective_min:.3f}, top={top_score:.3f}, ratio={ratio})")
        return kept

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
                doc.get("sanskrit") or
                ""
            ).strip()

            if text.lower() in _CONTENT_PLACEHOLDERS:
                logger.debug(f"Content gate: dropped placeholder doc from '{doc.get('scripture')}'")
                continue

            if len(text) < settings.MIN_CONTENT_LENGTH:
                logger.debug(f"Content gate: dropped too-short doc ({len(text)} chars) from '{doc.get('scripture')}'")
                continue

            kept.append(doc)

        return kept

    # ---------------------------------------------------------------
    # Gate 3 – Type appropriateness
    # ---------------------------------------------------------------

    def _gate_type(
        self, docs: List[Dict], intent: Optional[IntentType], temple_interest: bool,
        meditation_interest: bool = False,
    ) -> List[Dict]:
        """
        Remove docs whose type is semantically wrong for this intent.

        Rules:
        - All non-temple intents: hard-drop temple/location docs
          UNLESS temple_interest is True (user wants pilgrimage).
        - Drop generic meditation templates UNLESS query is about meditation.
        - Procedural queries: deprioritize philosophical-only docs
          (they stay but get pushed to the back via sort).
        """
        if not intent:
            return docs

        is_howto = intent in {IntentType.SEEKING_GUIDANCE, IntentType.ASKING_INFO}

        kept = []
        deferred = []  # Added at the end, lower priority

        for doc in docs:
            doc_type = (doc.get("type") or "scripture").lower()
            doc_text = (doc.get("text", "") + " " + doc.get("reference", "")).lower()
            doc_scripture = (doc.get("scripture") or "").lower()
            doc_source = (doc.get("source") or "").lower()

            # Detect spatial/location-only documents
            is_spatial = doc_type == "temple" or any(m in doc_text for m in _SPATIAL_MARKERS)

            # DROP temple docs for any non-temple intent (not just emotional)
            if is_spatial and not temple_interest:
                logger.debug(f"Type gate: DROPPED temple doc: {doc.get('reference', '')}")
                continue  # Hard drop, not deferred

            # DROP generic meditation templates UNLESS query is about meditation
            is_meditation_template = (
                "meditation" in doc_scripture and "mindfulness" in doc_scripture
            ) or doc_source == "meditation_template"
            if is_meditation_template and not meditation_interest:
                logger.debug(f"Type gate: DROPPED meditation template: {doc.get('reference', '')}")
                continue

            # For how-to queries: keep procedural docs first, defer pure philosophy last
            if is_howto and doc_type == "procedural":
                kept.insert(0, doc)  # Boost to front
                continue

            kept.append(doc)

        return kept + deferred

    # ---------------------------------------------------------------
    # Gate 6 – Tradition diversity
    # ---------------------------------------------------------------

    def _gate_tradition_diversity(self, docs: List[Dict], max_per_tradition: int) -> List[Dict]:
        """
        Limit the number of documents from the same dharmic tradition to avoid
        mono-tradition responses (e.g., all vedanta for a practical query).

        Curated concept/narrative documents are exempt from the cap.
        If a doc has no tradition label, it gets 'general' which is uncapped.
        """
        _EXEMPT_SOURCES = _CURATED_EXEMPT_SOURCES
        tradition_counts: Dict[str, int] = {}
        kept = []

        for doc in docs:
            doc_source = (doc.get("source") or "").lower()

            # Curated docs bypass the tradition cap
            if doc_source in _EXEMPT_SOURCES:
                kept.append(doc)
                continue

            tradition = (doc.get("tradition") or "general").lower()

            # 'general' tradition is uncapped (unlabeled docs)
            if tradition == "general":
                kept.append(doc)
                continue

            count = tradition_counts.get(tradition, 0)
            if count < max_per_tradition:
                kept.append(doc)
                tradition_counts[tradition] = count + 1
            else:
                logger.debug(f"Tradition diversity gate: skipped extra doc from tradition '{tradition}' (limit={max_per_tradition})")

        return kept

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

        Curated concept/narrative documents are exempt from the cap since
        they are unique by design and cover distinct topics.
        """
        _EXEMPT_SOURCES = _CURATED_EXEMPT_SOURCES
        source_counts: Dict[str, int] = {}
        kept = []

        for doc in docs:
            doc_source = (doc.get("source") or "").lower()

            # Curated docs bypass the diversity cap
            if doc_source in _EXEMPT_SOURCES:
                kept.append(doc)
                continue

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
