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
        Apply all 6 gates in a single pass.  Returns a clean, ranked list.
        Context verses (from parent-child expansion) bypass the gates and are
        re-attached only if their parent doc survives filtering.
        """
        if not docs:
            return []

        n_before = len(docs)

        # Separate context verses from primary docs
        context_verses = [d for d in docs if d.get("is_context_verse")]
        primary_docs = [d for d in docs if not d.get("is_context_verse")]

        if not primary_docs:
            return []

        # Pre-compute gate parameters once
        meditation_interest = bool(query) and any(kw in query.lower() for kw in _MEDITATION_EXACT_KEYWORDS)

        # Gate 1 setup: relevance threshold
        top_score = max(get_doc_score(d) for d in primary_docs)
        if intent == IntentType.EXPRESSING_EMOTION:
            ratio = settings.RELEVANCE_RATIO_EMOTIONAL
        elif intent == IntentType.ASKING_INFO:
            ratio = settings.RELEVANCE_RATIO_CITATION
        elif intent == IntentType.SEEKING_GUIDANCE:
            ratio = settings.RELEVANCE_RATIO_GUIDANCE
        else:
            ratio = settings.RELEVANCE_RATIO_DEFAULT
        effective_min = max(min_score, top_score * ratio)

        # Gate 4 setup: scripture allowlist
        allowed_lower = {s.lower() for s in allowed_scriptures} if allowed_scriptures else None

        # Gate 3 setup
        is_howto = intent in {IntentType.SEEKING_GUIDANCE, IntentType.ASKING_INFO} if intent else False

        # Tracking for diversity gates
        source_counts: Dict[str, int] = {}
        tradition_counts: Dict[str, int] = {}
        max_per_tradition = settings.MAX_DOCS_PER_TRADITION

        # Single-pass filter
        kept = []
        scripture_fallback_needed = False
        for doc in primary_docs:
            # Gate 1: Relevance
            if get_doc_score(doc) < effective_min:
                continue

            # Gate 2: Content quality
            text = (
                doc.get("text") or doc.get("meaning") or doc.get("translation") or
                doc.get("hindi") or doc.get("sanskrit") or ""
            ).strip()
            if text.lower() in _CONTENT_PLACEHOLDERS or len(text) < settings.MIN_CONTENT_LENGTH:
                continue

            # Gate 3: Type appropriateness
            if intent:
                doc_type = (doc.get("type") or "scripture").lower()
                doc_text = (doc.get("text", "") + " " + doc.get("reference", "")).lower()
                doc_scripture_name = (doc.get("scripture") or "").lower()
                doc_source = (doc.get("source") or "").lower()

                is_spatial = doc_type == "temple" or any(m in doc_text for m in _SPATIAL_MARKERS)
                if is_spatial and not temple_interest:
                    continue

                is_meditation_template = (
                    "meditation" in doc_scripture_name and "mindfulness" in doc_scripture_name
                ) or doc_source == "meditation_template"
                if is_meditation_template and not meditation_interest:
                    continue

            # Gate 4: Scripture allowlist
            if allowed_lower:
                if (doc.get("scripture") or "").lower() not in allowed_lower:
                    scripture_fallback_needed = True
                    continue

            doc_source_key = (doc.get("source") or "").lower()
            is_curated = doc_source_key in _CURATED_EXEMPT_SOURCES

            # Gate 5: Source diversity
            if not is_curated:
                src = (doc.get("scripture") or "unknown").lower()
                if source_counts.get(src, 0) >= max_per_source:
                    continue
                source_counts[src] = source_counts.get(src, 0) + 1

            # Gate 6: Tradition diversity
            if not is_curated:
                tradition = (doc.get("tradition") or "general").lower()
                if tradition != "general":
                    if tradition_counts.get(tradition, 0) >= max_per_tradition:
                        continue
                    tradition_counts[tradition] = tradition_counts.get(tradition, 0) + 1

            # For how-to queries: boost procedural docs to front
            if is_howto and (doc.get("type") or "").lower() == "procedural":
                kept.insert(0, doc)
            else:
                kept.append(doc)

            if len(kept) >= max_docs:
                break

        # Scripture gate fallback: if allowlist filtered everything, re-run without it
        if not kept and scripture_fallback_needed and primary_docs:
            logger.warning(f"Scripture gate: allowlist {allowed_scriptures} matched nothing — retrying without filter")
            return self.validate(
                docs, intent=intent, allowed_scriptures=None, temple_interest=temple_interest,
                query=query, min_score=min_score, max_per_source=max_per_source, max_docs=max_docs,
            )

        if not kept and n_before > 0:
            logger.warning(
                f"ContextValidator: ALL {n_before} docs filtered out | "
                f"intent={intent} | allowed={allowed_scriptures} | "
                f"min_score={min_score} | query='{query[:80]}'"
            )

        # Re-attach context verses only if their parent survived
        if context_verses:
            surviving_refs = {d.get("reference") for d in kept}
            final_docs = []
            for d in kept:
                final_docs.append(d)
                for cv in context_verses:
                    if cv.get("context_parent_ref") in surviving_refs and cv.get("context_parent_ref") == d.get("reference"):
                        final_docs.append(cv)
        else:
            final_docs = kept

        n_after = len(final_docs)
        logger.info(
            f"ContextValidator: {n_before} → {n_after} docs "
            f"({len(context_verses)} context verse(s)) | "
            f"intent={intent} | allowed={allowed_scriptures} | min_score={min_score}"
        )
        return final_docs



# ---------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------

_context_validator: Optional["ContextValidator"] = None


def get_context_validator() -> "ContextValidator":
    global _context_validator
    if _context_validator is None:
        _context_validator = ContextValidator()
    return _context_validator
