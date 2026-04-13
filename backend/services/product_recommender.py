"""Product recommendation service.

Extracted from CompanionEngine — owns the recommend() entry point,
search helpers, and session dedup logic.
"""
import logging
from typing import Dict, List

from models.session import SessionState, IntentType

logger = logging.getLogger(__name__)


class ProductRecommender:
    """Handles all product recommendation logic.

    Depends on: ProductService (via port injection).
    """

    def __init__(self, product_service, panchang_service=None):
        self.product_service = product_service
        self.panchang_service = panchang_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def recommend(
        self,
        session: SessionState,
        message: str,
        analysis: Dict,
        turn_topics: List[str],
        is_ready_for_wisdom: bool,
        life_domain: str = "unknown",
    ) -> List[Dict]:
        """Single entry point for product recommendations.

        Handles: rejection detection, explicit requests, intent-recommended,
        proactive inference, filtering, recording.
        """
        intent = analysis.get("intent")

        # Read the structured ProductSignal (falls back to legacy boolean)
        product_signal = analysis.get("product_signal", {})

        # Validate the signal — catches emotion conflicts, follow-up context,
        # adversarial exploitation, negative sentiment, and Turn 1 leaks.
        # Only suppresses, never triggers. The IntentAgent remains the sole
        # positive authority for product recommendations.
        from services.product_validator import validate_product_signal
        product_signal = validate_product_signal(product_signal, analysis, message, session)

        product_intent = product_signal.get("intent", "none")
        type_filter_raw = product_signal.get("type_filter", "any")
        type_filter = None if type_filter_raw == "any" else type_filter_raw.replace("_only", "")
        max_results = product_signal.get("max_results", 0)

        # Detect rejection from the signal AND from message text
        self._detect_product_rejection(session, message, analysis)

        is_explicit = (
            "Product Inquiry" in turn_topics
            or intent == IntentType.PRODUCT_SEARCH
            or product_intent == "explicit_search"
        )

        products = []

        # Path 1: Explicit user request — bypasses all gates except crisis.
        # Uses split counter (explicit_product_count) with generous cap (10).
        if is_explicit:
            products = await self._search_explicit(
                session, message, analysis, life_domain,
                product_type=type_filter,
                limit=max_results or 5,
            )
            if products:
                session.explicit_product_count += 1

        # Path 2: Contextual need — IntentAgent says items are needed
        elif product_intent == "contextual_need" and max_results > 0:
            products = await self._search_intent_recommended(
                session, analysis, life_domain,
                product_type=type_filter,
                limit=max_results or 3,
            )
            if products:
                session.product_event_count += 1

        # Path 2b: Casual mention — show at most 1-2 products
        elif product_intent == "casual_mention" and max_results > 0:
            products = await self._search_intent_recommended(
                session, analysis, life_domain,
                product_type=type_filter,
                limit=min(max_results, 2),
            )
            if products:
                session.product_event_count += 1

        # All other cases (none, negative): no products

        # Post-processing: filter already-shown + record
        if products:
            products = self._filter_shown(session, products)
            self._record_shown(session, products)

        return products

    # ------------------------------------------------------------------
    # Internal: search paths
    # ------------------------------------------------------------------

    async def _search_explicit(self, session, message, analysis, life_domain,
                               product_type=None, limit=5) -> List[Dict]:
        """Explicit product request — bypasses all gates except crisis."""
        if self._should_suppress(session, analysis, is_explicit_request=True):
            return []

        search_terms = self._build_search_query(analysis, session, message)
        products = await self.product_service.search_products(
            search_terms, life_domain=life_domain,
            emotion=analysis.get("emotion", ""),
            deity=self._get_conversation_deity(session, analysis),
            product_type=product_type,
            limit=limit,
        )
        if not products:
            products = await self.product_service.get_recommended_products(
                category=life_domain if life_domain != "unknown" else None)
        if products:
            session.product_event_count += 1
        return products

    async def _search_intent_recommended(self, session, analysis, life_domain,
                                         product_type=None, limit=3) -> List[Dict]:
        """Intent agent recommended products — two-stage search.

        Stage 1: Text search using signal_keywords from ProductSignal.
                 Matches product names directly (e.g. "mala" → "Rudraksha Mala").
        Stage 2: Metadata search using enriched fields (practices, deities, etc.).
                 Catches products tagged with relevant attributes.
        Results are merged (text search preferred, metadata supplements).
        """
        if self._should_suppress(session, analysis, is_explicit_request=False):
            return []

        product_signal = analysis.get("product_signal", {})
        signal_keywords = product_signal.get("search_keywords", [])

        practices = self._detect_practices_from_context(session, analysis)
        deity = self._get_conversation_deity(session, analysis)
        emotion = analysis.get("emotion", "") if analysis else ""

        logger.info(f"Intent-recommended search: signal_kw={signal_keywords} practices={practices} deity={deity} domain={life_domain} emotion={emotion} type={product_type}")

        products = []

        # Stage 1: Text search with signal_keywords (direct product name matching)
        if signal_keywords:
            keyword_query = " ".join(signal_keywords[:6])
            products = await self.product_service.search_products(
                keyword_query, life_domain=life_domain,
                emotion=emotion, deity=deity,
                product_type=product_type,
                limit=limit,
            )

        # Stage 2: Metadata search (enriched field matching)
        if len(products) < limit:
            metadata_products = await self.product_service.search_by_metadata(
                practices=practices if practices else None,
                deities=[deity] if deity else None,
                emotions=[emotion] if emotion else None,
                life_domains=[life_domain.lower()] if life_domain and life_domain != "unknown" else None,
                product_type=product_type,
                limit=limit,
            )
            # Merge: supplement with metadata results, deduped by ID
            existing_ids = {p.get("_id") for p in products}
            for mp in metadata_products:
                if mp.get("_id") not in existing_ids and len(products) < limit:
                    products.append(mp)
                    existing_ids.add(mp.get("_id"))

        if products:
            session.last_proactive_product_turn = session.turn_count
        return products

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _filter_shown(self, session, products):
        """Filter already-shown products by ID AND name (handles duplicates)."""
        shown_names = {p.get("name", "").lower() for p in session.recent_products}
        return [
            p for p in products
            if p.get("_id") not in session.shown_product_ids
            and p.get("name", "").lower() not in shown_names
        ]

    def _record_shown(self, session, products):
        """Record products as shown in this session.

        Maintains two parallel structures:
          * ``shown_product_ids`` (Set[str]) — fast O(1) dedupe gate for
            ``_filter_shown``.
          * ``recent_products`` (List[Dict]) — FIFO of last 5 products with
            name + category metadata, surfaced to the LLM via the user
            profile so follow-up questions like "how do I use that mala?"
            land on the actual recommended item. Added Apr 2026.
        """
        for p in products:
            pid = p.get("_id")
            if not pid:
                continue
            session.shown_product_ids.add(pid)
            # Skip if already in recent_products (within-batch + cross-turn dedupe).
            if any(rp.get("_id") == pid for rp in session.recent_products):
                continue
            session.recent_products.append({
                "_id": pid,
                "name": p.get("name", ""),
                "category": p.get("category", ""),
                "position": len(session.recent_products) + 1,
                "amount": p.get("amount", 0),
                "currency": p.get("currency", "INR"),
                "description_snippet": (p.get("description") or "")[:150],
                "product_type": p.get("product_type", "physical"),
            })
        # FIFO cap — keep only the last 10 products visible to the LLM.
        if len(session.recent_products) > 10:
            session.recent_products = session.recent_products[-10:]
