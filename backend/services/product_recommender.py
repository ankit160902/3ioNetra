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
from typing import Dict, List

from models.session import SessionState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers (profile I/O)
# ---------------------------------------------------------------------------

async def load_relational_profile(user_id: str):
    """Load RelationalProfile from memory reader (Redis-cached)."""
    from services.memory_reader import load_relational_profile as _load
    return await _load(user_id)


async def update_product_interaction(
    user_id: str,
    field_updates: dict,
    increments: dict | None = None,
):
    """Write product interaction fields to the user_profiles document.

    Args:
        user_id: The user whose profile to update.
        field_updates: Fields to ``$set`` (timestamps, preference strings).
        increments: Fields to ``$inc`` (counters like shown_count).
    """
    from services.auth_service import get_mongo_client
    db = get_mongo_client()
    if db is None:
        return
    update_ops: dict = {}
    if field_updates:
        update_ops["$set"] = field_updates
    if increments:
        update_ops["$inc"] = increments
    if not update_ops:
        return
    await asyncio.to_thread(
        db.user_profiles.update_one,
        {"user_id": user_id},
        update_ops,
        upsert=True,
    )


# ---------------------------------------------------------------------------
# ProductRecommender
# ---------------------------------------------------------------------------

class ProductRecommender:
    """Handles all product recommendation logic.

    Depends on: ProductService (via port injection).
    """

    def __init__(self, product_service):
        self.product_service = product_service

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

        logger.info(
            f"PRODUCT_REC session={session.session_id} intent={intent} "
            f"keywords={signal.get('search_keywords', [])} max={signal.get('max_results', 0)} "
            f"urgency={analysis.get('urgency')} user={user_id}"
        )

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
                    set_fields = {
                        "product_last_rejected_at": datetime.utcnow().isoformat(),
                    }
                    _hard_phrases = {
                        "stop suggesting products", "stop recommending",
                        "no more products", "don't show products",
                        "dont show products", "i hate your products",
                    }
                    if any(p in message.lower() for p in _hard_phrases):
                        set_fields["product_preference"] = "opted_out"
                    await update_product_interaction(
                        user_id, set_fields,
                        increments={"product_rejection_count": 1},
                    )
                except Exception as e:
                    logger.warning(f"Failed to update rejection: {e}")
            return []

        if intent == "none":
            return []

        # Step 3: Search and return
        keywords = signal.get("search_keywords", [])
        max_results = signal.get("max_results", 3)
        type_filter_raw = signal.get("type_filter", "any")
        type_filter = "any" if type_filter_raw == "any" else type_filter_raw.replace("_only", "")

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
                # Use semantic fields from the analysis for metadata search
                # (life_domain, emotion, entities) rather than product-name
                # keywords which don't match the practices/deities arrays.
                _life_domain = analysis.get("life_domain")
                _emotion = analysis.get("emotion")
                _entities = analysis.get("entities") or {}
                meta_products = await self.product_service.search_by_metadata(
                    life_domains=[_life_domain] if _life_domain and _life_domain != "unknown" else None,
                    emotions=[_emotion] if _emotion and _emotion not in ("neutral", "unknown") else None,
                    deities=_entities.get("deity") if isinstance(_entities.get("deity"), list) else (
                        [_entities["deity"]] if _entities.get("deity") else None
                    ),
                    limit=max_results - len(products),
                )
                seen_ids = {str(p.get("_id", "")) for p in products}
                for mp in meta_products:
                    if str(mp.get("_id", "")) not in seen_ids:
                        products.append(mp)
            except Exception as e:
                logger.warning(f"Metadata search failed: {e}")

        logger.info(f"PRODUCT_SEARCH_RESULT pre_filter={len(products)} keywords={keywords}")

        products = self._filter_shown(session, products)
        products = products[:max_results]

        if products:
            self._record_shown(session, products)
            if user_id:
                try:
                    await update_product_interaction(
                        user_id,
                        {"product_last_shown_at": datetime.utcnow().isoformat()},
                        increments={"product_shown_count": 1},
                    )
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
