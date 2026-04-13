"""Product recommendation service — LLM-as-sole-authority.

The IntentAgent emits a ``product_signal`` dict with intent, keywords, and
max_results.  This module trusts that signal completely:

  1. Hard safety rails (crisis, opted-out user) → empty.
  2. LLM says none/negative → empty (with opt-out bookkeeping).
  3. Otherwise search with the LLM's keywords and return results.

No hardcoded maps, no proactive inference, no emotion heuristics.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Set

from models.session import SessionState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers (profile I/O)
# ---------------------------------------------------------------------------

async def load_relational_profile(user_id: str):
    """Load RelationalProfile from memory reader (Redis-cached)."""
    from services.memory_reader import load_relational_profile as _load
    return await _load(user_id)


async def update_product_interaction(user_id: str, field_updates: dict):
    """Write product interaction fields to the user_profiles document."""
    from services.auth_service import get_mongo_client
    db = get_mongo_client()
    if db is None:
        return
    await asyncio.to_thread(
        db.user_profiles.update_one,
        {"user_id": user_id},
        {"$set": field_updates},
        upsert=True,
    )


# ---------------------------------------------------------------------------
# ProductRecommender
# ---------------------------------------------------------------------------

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
    ) -> List[Dict]:
        """LLM-as-sole-authority product recommendation.

        Three steps:
        1. Hard safety: crisis -> empty, opted_out -> empty
        2. Trust the LLM: intent none/negative -> empty
        3. Search and return: use LLM's keywords to find products
        """
        signal = analysis.get("product_signal") or {}
        intent = signal.get("intent", "none")
        user_id = getattr(session.memory, "user_id", None) or getattr(session, "user_id", None)

        # Step 1: Hard safety
        if analysis.get("urgency") == "crisis":
            return []

        profile = None
        if user_id:
            try:
                profile = await load_relational_profile(user_id)
            except Exception as e:
                logger.warning(f"Failed to load product profile: {e}")

        if profile and profile.product_preference == "opted_out":
            if intent == "explicit_search":
                logger.info(f"User {user_id} opted out but explicitly asked — re-engaging")
                try:
                    await update_product_interaction(user_id, {"product_preference": "neutral"})
                except Exception:
                    pass
            else:
                return []

        # Step 2: Trust the LLM
        if intent == "negative":
            if user_id:
                try:
                    updates = {
                        "product_rejection_count": (profile.product_rejection_count + 1) if profile else 1,
                        "product_last_rejected_at": datetime.utcnow().isoformat(),
                    }
                    _hard_phrases = {
                        "stop suggesting products", "stop recommending",
                        "no more products", "don't show products",
                        "dont show products", "i hate your products",
                    }
                    if any(p in message.lower() for p in _hard_phrases):
                        updates["product_preference"] = "opted_out"
                    await update_product_interaction(user_id, updates)
                except Exception as e:
                    logger.warning(f"Failed to update rejection: {e}")
            return []

        if intent == "none":
            return []

        # Step 3: Search and return
        keywords = signal.get("search_keywords", [])
        max_results = signal.get("max_results", 3)
        type_filter = signal.get("type_filter", "any")

        if not keywords:
            return []

        try:
            products = await self.product_service.search_products(
                query_text=" ".join(keywords),
                limit=max_results + 2,
                product_type=type_filter if type_filter != "any" else None,
            )
        except Exception as e:
            logger.warning(f"Product search failed: {e}")
            return []

        if len(products) < max_results:
            try:
                meta_products = await self.product_service.search_by_metadata(
                    practices=keywords,
                    limit=max_results - len(products),
                )
                seen_ids = {str(p.get("_id", "")) for p in products}
                for mp in meta_products:
                    if str(mp.get("_id", "")) not in seen_ids:
                        products.append(mp)
            except Exception as e:
                logger.warning(f"Metadata search failed: {e}")

        products = self._filter_shown(session, products)
        products = products[:max_results]

        if products:
            self._record_shown(session, products)
            if user_id:
                try:
                    shown_count = (profile.product_shown_count + 1) if profile else 1
                    await update_product_interaction(user_id, {
                        "product_shown_count": shown_count,
                        "product_last_shown_at": datetime.utcnow().isoformat(),
                    })
                except Exception as e:
                    logger.warning(f"Failed to update product shown: {e}")

        return products

    # ------------------------------------------------------------------
    # Internal: session dedup
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
          * ``shown_product_ids`` (Set[str]) -- fast O(1) dedupe gate for
            ``_filter_shown``.
          * ``recent_products`` (List[Dict]) -- FIFO of last 10 products with
            name + category metadata, surfaced to the LLM via the user
            profile so follow-up questions like "how do I use that mala?"
            land on the actual recommended item.
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
        # FIFO cap -- keep only the last 10 products visible to the LLM.
        if len(session.recent_products) > 10:
            session.recent_products = session.recent_products[-10:]
