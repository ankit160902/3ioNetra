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

    Uses a hybrid authority model:
    - LLM decides WHEN to show products (product_signal.intent)
    - Purpose-built code refines WHAT to search for (catalog-aligned keywords)
    """

    # Small lookup: practice name → product search terms
    _PRACTICE_SEARCH_TERMS = {
        "japa": ["mala", "rudraksha"],
        "puja": ["thali", "diya", "incense", "puja box"],
        "meditation": ["incense", "bracelet", "mala"],
        "havan": ["ghee", "havan", "samagri"],
        "aarti": ["diya", "deep", "bell", "aarti"],
        "abhishek": ["kalash", "puja thali"],
        "yoga": ["bracelet", "mala"],
    }

    # Nouns that appear in product names — used to extract
    # catalog-aligned terms from natural language messages.
    _PRODUCT_NOUNS = frozenset({
        "murti", "idol", "mala", "bracelet", "yantra", "frame", "lamp",
        "thali", "diya", "deep", "incense", "agarbatti", "dhoop",
        "rudraksha", "crystal", "stone", "book", "chalisa", "photo",
        "bell", "kalash", "box", "combo", "chain", "pendant",
    })

    # Known deity names for extraction from messages/history
    _DEITY_NAMES = frozenset({
        "krishna", "shiva", "hanuman", "ganesh", "ganesha", "lakshmi",
        "durga", "saraswati", "rama", "ram", "vishnu", "kali",
        "parvati", "radha", "sita", "surya", "shrinathji", "balaji",
        "mahadev", "bajrangbali", "hanumanji", "ganapati",
    })

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
            # Record rejection on session (drives cooldown + 2-rejection auto-opt-out)
            session.product_rejection_count += 1
            session.product_rejection_turn = session.turn_count

            # Widened hard-phrase detection (English + Hindi/Hinglish natural language).
            # Two triggers auto-opt-out: (a) any hard phrase, (b) 2+ rejections in session.
            _hard_phrases = {
                # Original explicit phrases
                "stop suggesting products", "stop recommending",
                "no more products", "don't show products",
                "dont show products", "i hate your products",
                # English natural language
                "not interested in products", "don't need products",
                "dont need products", "no thanks", "no thank you",
                "please stop", "stop showing", "don't want products",
                "dont want products", "enough products",
                # Hindi / Hinglish
                "nahi chahiye", "band karo", "mat dikhao",
                "product nahi chahiye", "bas karo",
            }
            msg_lower = message.lower()
            hard_phrase_hit = any(p in msg_lower for p in _hard_phrases)
            auto_opt_out = hard_phrase_hit or session.product_rejection_count >= 2

            if auto_opt_out:
                session.user_dismissed_products = True

            if user_id:
                try:
                    set_fields = {"product_last_rejected_at": datetime.utcnow().isoformat()}
                    if auto_opt_out:
                        set_fields["product_preference"] = "opted_out"
                    await update_product_interaction(
                        user_id, set_fields,
                        increments={"product_rejection_count": 1},
                    )
                except Exception as e:
                    logger.warning(f"Failed to update rejection: {e}")

            logger.info(
                f"REJECTION session={session.session_id} count={session.product_rejection_count} "
                f"hard_phrase={hard_phrase_hit} opted_out={auto_opt_out}"
            )
            return []

        if intent == "none":
            return []

        # Session-level hard kill: respect prior opt-out
        if session.user_dismissed_products and intent != "explicit_search":
            logger.info(f"Session {session.session_id} opted out locally — suppressing")
            return []

        # Session cap: max 3 proactive/contextual products per session.
        # Explicit searches bypass (user is actively asking — respect that).
        PROACTIVE_SESSION_CAP = 3
        if intent != "explicit_search" and session.product_event_count >= PROACTIVE_SESSION_CAP:
            logger.info(
                f"Session {session.session_id} hit proactive cap "
                f"({session.product_event_count}/{PROACTIVE_SESSION_CAP}) — suppressing"
            )
            return []

        # Cooldown: no back-to-back proactive products (min 2-turn gap).
        # Explicit searches bypass.
        COOLDOWN_TURNS = 2
        if intent != "explicit_search" and session.last_proactive_product_turn >= 0:
            turns_since = session.turn_count - session.last_proactive_product_turn
            if turns_since < COOLDOWN_TURNS:
                logger.info(
                    f"Session {session.session_id} in cooldown "
                    f"(last={session.last_proactive_product_turn}, now={session.turn_count}) — suppressing"
                )
                return []

        # Step 3: Search and return
        llm_keywords = signal.get("search_keywords", [])
        max_results = signal.get("max_results", 3)
        type_filter_raw = signal.get("type_filter", "any")
        type_filter = "any" if type_filter_raw == "any" else type_filter_raw.replace("_only", "")

        if not llm_keywords:
            return []

        # Refine LLM keywords into catalog-aligned search terms
        deity = self._extract_deity(analysis, session, message)
        practices = self._extract_practices(message, session)
        refined = self._refine_keywords(llm_keywords, message, deity, practices)

        logger.info(f"KEYWORD_REFINE llm={llm_keywords} → refined={refined} deity={deity} practices={practices}")

        _emotion = analysis.get("emotion")
        products = []

        # Deity-first strategy: only when deity is the PRIMARY ask
        # (deity mentioned in the current message, not just in conversation
        # history). This prevents japa/puja queries from pulling deity
        # products when a deity was mentioned earlier in the conversation.
        _deity_in_current_msg = deity and deity in message.lower()

        if _deity_in_current_msg:
            # Deity IS the primary ask → metadata-first (guarantees deity products)
            try:
                products = await self.product_service.search_by_metadata(
                    deities=[deity],
                    practices=practices if practices else None,
                    emotions=[_emotion] if _emotion and _emotion not in ("neutral", "unknown") else None,
                    limit=max_results + 2,
                )
            except Exception as e:
                logger.warning(f"Deity metadata search failed: {e}")

            if len(products) < max_results:
                try:
                    text_products = await self.product_service.search_products(
                        query_text=" ".join(refined),
                        limit=max_results + 2,
                        product_type=type_filter if type_filter != "any" else None,
                    )
                    seen_ids = {str(p.get("_id", "")) for p in products}
                    for tp in text_products:
                        if str(tp.get("_id", "")) not in seen_ids and len(products) < max_results + 2:
                            products.append(tp)
                except Exception as e:
                    logger.warning(f"Text search supplement failed: {e}")
        else:
            # No deity → text-first strategy (original behavior)
            try:
                products = await self.product_service.search_products(
                    query_text=" ".join(refined),
                    limit=max_results + 2,
                    product_type=type_filter if type_filter != "any" else None,
                )
            except Exception as e:
                logger.warning(f"Product search failed: {e}")
                return []

            # Metadata fallback (includes deity from history for boosting)
            if len(products) < max_results:
                try:
                    meta_products = await self.product_service.search_by_metadata(
                        deities=[deity] if deity else None,
                        practices=practices if practices else None,
                        emotions=[_emotion] if _emotion and _emotion not in ("neutral", "unknown") else None,
                        limit=max_results - len(products),
                    )
                    seen_ids = {str(p.get("_id", "")) for p in products}
                    for mp in meta_products:
                        if str(mp.get("_id", "")) not in seen_ids:
                            products.append(mp)
                except Exception as e:
                    logger.warning(f"Metadata search failed: {e}")

        logger.info(f"PRODUCT_SEARCH_RESULT pre_filter={len(products)} refined={refined} llm={llm_keywords}")

        products = self._filter_shown(session, products)
        products = products[:max_results]

        if products:
            self._record_shown(session, products)
            # Session-level throttling bookkeeping
            if intent != "explicit_search":
                session.product_event_count += 1
                session.last_proactive_product_turn = session.turn_count
            else:
                session.explicit_product_count += 1
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
    # Internal: keyword refinement (hybrid authority)
    # ------------------------------------------------------------------

    def _refine_keywords(
        self, llm_keywords: List[str], message: str,
        deity: str, practices: List[str],
    ) -> List[str]:
        """Refine LLM-generated keywords into catalog-aligned search terms.

        The LLM decides WHEN to show products. This method improves WHAT
        we search for by extracting deity names, practice-specific product
        terms, and product-type nouns that match actual catalog names.
        """
        refined: List[str] = []

        # 1. Deity name (strongest signal for product name matching)
        if deity:
            refined.append(deity)

        # 2. Practice → product search terms
        for practice in practices:
            for term in self._PRACTICE_SEARCH_TERMS.get(practice, []):
                if term not in refined:
                    refined.append(term)

        # 3. Product-type nouns from the user's message
        msg_words = set(message.lower().split())
        for noun in msg_words & self._PRODUCT_NOUNS:
            if noun not in refined:
                refined.append(noun)

        # 4. Keep short LLM keywords (≤2 words) that align with catalog
        for kw in llm_keywords:
            if len(kw.split()) <= 2 and kw.lower() not in refined:
                refined.append(kw.lower())

        # Dedup preserving order, cap at 8
        seen = set()
        unique = []
        for term in refined:
            if term not in seen:
                seen.add(term)
                unique.append(term)
        return unique[:8] if unique else [kw.split()[0] for kw in llm_keywords[:3]]

    def _extract_deity(self, analysis: Dict, session: SessionState, message: str) -> str:
        """Extract the primary deity from analysis entities, message, or history."""
        # From IntentAgent entities
        entities = analysis.get("entities") or {}
        deity_val = entities.get("deity", "")
        if isinstance(deity_val, list) and deity_val:
            deity_val = deity_val[0]
        if deity_val and deity_val.lower() in self._DEITY_NAMES:
            return deity_val.lower()

        # From user's message
        msg_words = set(message.lower().split())
        for d in self._DEITY_NAMES:
            if d in msg_words:
                return d

        # From conversation history (last 6 messages)
        for msg in reversed((session.conversation_history or [])[-6:]):
            words = set(msg.get("content", "").lower().split())
            for d in self._DEITY_NAMES:
                if d in words:
                    return d

        # From user profile
        preferred = getattr(session.memory, "preferred_deity", "") or ""
        if preferred.lower() in self._DEITY_NAMES:
            return preferred.lower()

        return ""

    def _extract_practices(self, message: str, session: SessionState) -> List[str]:
        """Extract practice names from message and recent history."""
        practices = set()
        practice_names = set(self._PRACTICE_SEARCH_TERMS.keys())

        # From current message
        msg_lower = message.lower()
        for practice in practice_names:
            if practice in msg_lower:
                practices.add(practice)

        # From recent conversation history
        for msg in (session.conversation_history or [])[-6:]:
            text = msg.get("content", "").lower()
            for practice in practice_names:
                if practice in text:
                    practices.add(practice)

        return list(practices)

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
