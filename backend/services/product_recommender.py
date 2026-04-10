"""Product recommendation service.

Extracted from CompanionEngine — owns all product maps, gating logic,
rejection detection, proactive inference, and the recommend() entry point.
"""
import logging
from typing import Dict, List, Optional

from config import settings
from models.session import SessionState, IntentType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static product maps (moved from CompanionEngine class body)
# ---------------------------------------------------------------------------

PRACTICE_PRODUCT_MAP = {
    "japa": {
        "detect": ["japa", "jaap", "jap ", "chant", "chanting", "recite", "108 times", "11 times", "21 times"],
        "search_keywords": ["rudraksha mala", "mala"],
    },
    "puja": {
        "detect": ["puja", "pooja", "aarti"],
        "search_keywords": ["puja thali", "incense", "diya", "Kalash", "agardan", "kamandal", "Panch Patra", "chokra"],
    },
    "meditation": {
        "detect": ["meditation", "meditate", "dhyana", "dhyan", "sit quietly"],
        "search_keywords": ["incense", "Loban", "agarbatti", "Amethyst"],
    },
    "diya": {
        "detect": ["diya", "deep ", "jyoti", "light a lamp", "light a diya", "akhand"],
        "search_keywords": ["deep", "ghee", "diya", "akhand"],
    },
    "yoga": {
        "detect": ["yoga", "asana", "pranayama", "surya namaskar"],
        "search_keywords": ["yoga", "bracelet"],
    },
    "tilak": {
        "detect": ["tilak", "sindoor", "kumkum", "chandan"],
        "search_keywords": ["sindoor", "kumkum", "puja thali"],
    },
    "abhishek": {
        "detect": ["abhishek", "abhishekam"],
        "search_keywords": ["abhishek", "Kalash", "puja thali", "ghee"],
    },
    "havan": {
        "detect": ["havan", "hawan", "homam", "yajna", "yagna", "yagya"],
        "search_keywords": ["havan", "ghee", "yagya"],
    },
    "deity_worship": {
        "detect": ["murti", "idol", "statue", "bhagwan"],
        "search_keywords": ["murti", "brass idol"],
    },
    "home_temple": {
        "detect": ["mandir", "home temple", "puja room", "spiritual corner", "altar"],
        "search_keywords": ["puja box", "3D lamp", "deep", "bell", "aarti", "paduka", "photo frame"],
    },
    "crystal_healing": {
        "detect": ["crystal", "gemstone", "stone", "healing stone"],
        "search_keywords": ["bracelet", "crystal"],
    },
    "seva": {
        "detect": ["seva", "temple service", "pind daan", "ganga aarti", "shraddha"],
        "search_keywords": ["seva", "pind daan", "ganga aarti"],
    },
    "consultation": {
        "detect": ["consult", "consultation", "expert", "astrologer", "jyotish", "kundli", "kundali", "horoscope", "birth chart", "numerology", "ank shastra"],
        "search_keywords": ["consultation", "astrology", "Astro List", "Book-now"],
    },
    "vrat": {
        "detect": ["vrat", "fast", "fasting", "upvas", "ekadashi"],
        "search_keywords": ["puja thali", "incense", "diya"],
    },
    "sankalpa": {
        "detect": ["sankalpa", "intention", "resolve", "pledge", "commitment"],
        "search_keywords": ["mala", "Rudraksha", "yantra"],
    },
    "temple_seva": {
        "detect": ["temple donation", "temple seva", "prasad delivery", "darshan booking"],
        "search_keywords": ["seva", "puja", "Mangal"],
    },
    "workshop": {
        "detect": ["workshop", "session", "webinar", "retreat", "training", "course"],
        "search_keywords": ["members-form", "Bhajan Clubbing"],
    },
    "kundli": {
        "detect": ["kundli", "kundali", "birth chart", "natal chart", "janam patri"],
        "search_keywords": ["consultation", "Astro List", "Book-now"],
    },
}

# OLD HARDCODED MAPS REMOVED:
# - DEITY_PRODUCT_MAP — replaced by product enrichment {"deities": ["shiva"]}
# - DOMAIN_PRODUCT_MAP — replaced by product enrichment {"life_domains": ["career"]}
# - CONCEPT_PRODUCT_MAP — was dead code (never called)
# - EMOTION_PRODUCT_MAP — replaced by EMOTION_BENEFIT_BRIDGE in ProductService
# - DOMAIN_NORMALIZE — no longer needed (enriched fields handle variations)

# Deity names for conversation scanning
_DEITY_NAMES = {
    "hanuman", "krishna", "shiva", "ganesh", "ganesha", "durga", "lakshmi",
    "saraswati", "vishnu", "ram", "rama", "kali", "surya", "shrinathji",
    "naag", "murugan", "bajrang", "mahadev", "parvati", "sita",
}

# Apr 2026 — Adaptive architecture: the two frozensets
# (_SKIP_PROACTIVE_INTENTS, _NO_PRODUCT_INTENTS) and the proactive
# inference Path 3 have been REMOVED. The IntentAgent's
# `recommend_products` boolean is now the SINGLE authority for whether
# products should be recommended. The IntentAgent sees the full
# conversation context (emotion, intent, message content) and makes a
# contextual decision — no hardcoded overrides needed.
#
# Path 1 (explicit PRODUCT_SEARCH) and Path 2 (IntentAgent-recommended)
# are the only product paths that remain.


class ProductRecommender:
    """Handles all product recommendation logic.

    Owns: product maps, 6-gate gatekeeper, rejection detection, proactive inference.
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
    # Suggestion tracking (called from outside after LLM response)
    # ------------------------------------------------------------------

    def record_suggestion(self, session: SessionState, assistant_text: str) -> None:
        """Scan assistant response for practice keywords and record for later product matching."""
        text_lower = assistant_text.lower()
        for practice_name, practice_info in PRACTICE_PRODUCT_MAP.items():
            if any(kw in text_lower for kw in practice_info["detect"]):
                entry = {
                    "turn": session.turn_count,
                    "practice": practice_name,
                    "product_keywords": practice_info["search_keywords"],
                }
                session.last_suggestions.append(entry)
                if len(session.last_suggestions) > 3:
                    session.last_suggestions = session.last_suggestions[-3:]
                break

    async def infer_from_response(
        self,
        session: SessionState,
        response_text: str,
        analysis: Dict,
        life_domain: str = "unknown",
    ) -> List[Dict]:
        """Post-generation product inference — scan the LLM's response for items it mentioned.

        Called AFTER the LLM generates a response. If the response mentions specific items
        (mala, diya, thali, etc.), trigger product search retroactively.

        This solves the timing problem where products are recommended BEFORE the LLM
        responds, so the recommender can't know what the LLM will suggest.
        """
        # Apply full throttling gates — prevents product flooding on every message.
        # The session cap (3), cooldown (7 turns), and emotion suppression ensure
        # products are shown thoughtfully, not on every response that mentions a practice.
        if self._should_suppress(session, analysis or {}):
            return []

        # Skip for short user messages — casual acknowledgments (ok, fine, thanks)
        # shouldn't trigger products even if the LLM response mentions practices.
        _last_user_msg = ""
        if session.conversation_history:
            for msg in reversed(session.conversation_history):
                if msg.get("role") == "user":
                    _last_user_msg = msg.get("content", "")
                    break
        if len(_last_user_msg.split()) <= 3:
            return []

        text_lower = response_text.lower()

        # Detect practices mentioned in the LLM response
        detected_practices = []
        for practice_name, practice_info in PRACTICE_PRODUCT_MAP.items():
            if any(kw in text_lower for kw in practice_info["detect"]):
                detected_practices.append(practice_name)

        # Also detect item keywords for text-based fallback search
        _ITEM_WORDS = {
            "mala", "rudraksha", "tulsi", "diya", "deep", "incense", "agarbatti",
            "dhoop", "thali", "kalash", "bell", "murti", "idol", "yantra",
            "bracelet", "crystal", "ghee", "havan", "samagri",
        }
        detected_items = [w for w in _ITEM_WORDS if w in text_lower]

        if not detected_practices and not detected_items:
            return []

        deity = self._get_conversation_deity(session, analysis)
        emotion = analysis.get("emotion", "") if analysis else ""

        logger.info(f"Post-generation metadata search: practices={detected_practices} items={detected_items} deity={deity}")

        # Primary: metadata search using enriched fields
        products = await self.product_service.search_by_metadata(
            practices=detected_practices if detected_practices else None,
            deities=[deity] if deity else None,
            emotions=[emotion] if emotion else None,
            life_domains=[life_domain.lower()] if life_domain and life_domain != "unknown" else None,
            limit=5,
        )

        # Fallback: text search with detected item keywords (for items not in practice map)
        if not products and detected_items:
            search_query = " ".join(detected_items[:6])
            products = await self.product_service.search_products(
                search_query, life_domain=life_domain,
                emotion=emotion, deity=deity,
            )

        if products:
            session.last_proactive_product_turn = session.turn_count
            session.product_event_count += 1
            # Filter already-shown products
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

    async def _infer_proactive(self, session, message, life_domain, analysis, is_guidance_phase) -> List[Dict]:
        """Proactive product inference — fully gated."""
        if self._should_suppress(session, analysis, is_explicit_request=False):
            return []
        if not is_guidance_phase and not settings.PRODUCT_LISTENING_PROACTIVE_ENABLED:
            return []

        # Path A: Acceptance-based
        if self._is_acceptance(message):
            keywords = self._get_practice_from_history(session)
            if keywords:
                products = await self.product_service.search_products(
                    " ".join(keywords[:6]), life_domain=life_domain,
                    emotion=(analysis.get("emotion", "") if analysis else ""),
                    deity=self._get_conversation_deity(session, analysis),
                )
                if products:
                    session.last_proactive_product_turn = session.turn_count
                    session.product_event_count += 1
                    return products

        # Path B: Context-based (guidance phase only)
        if is_guidance_phase and settings.PRODUCT_GUIDANCE_CONTEXT_ENABLED and analysis:
            entities = analysis.get("entities", {})
            has_item_signal = bool(entities.get("item") or entities.get("ritual"))
            _item_intent_phrases = ["need a", "want a", "buy", "get a", "where can i find", "purchase"]
            has_purchase_intent = any(p in message.lower() for p in _item_intent_phrases)
            _physical_context_words = {
                "puja", "pooja", "havan", "homa", "aarti", "arti", "abhishek",
                "murti", "idol", "statue", "mala", "rudraksha",
                "diya", "deep", "lamp", "agarbatti", "incense", "dhoop",
                "thali", "kalash", "bell", "ghanta", "yantra",
                "prasad", "offering", "samagri",
            }
            has_physical_context = any(w in message.lower() for w in _physical_context_words)

            if has_item_signal or has_purchase_intent or has_physical_context:
                context_terms = self._get_practice_from_history(session) + self._get_user_item_mentions(session)
                if not context_terms and entities.get("ritual"):
                    context_terms = [entities["ritual"]]
                if not context_terms:
                    context_terms = [w for w in message.lower().split() if w in _physical_context_words]
                deity = self._get_conversation_deity(session, analysis)
                if deity and deity.lower() not in [t.lower() for t in context_terms]:
                    context_terms.insert(0, deity)
                if context_terms:
                    products = await self.product_service.search_products(
                        " ".join(context_terms[:6]), life_domain=life_domain,
                        emotion=analysis.get("emotion", ""),
                        deity=self._get_conversation_deity(session, analysis),
                    )
                    if products:
                        session.last_proactive_product_turn = session.turn_count
                        session.product_event_count += 1
                        return products
        return []

    # ------------------------------------------------------------------
    # Internal: gatekeeper + helpers
    # ------------------------------------------------------------------

    def _should_suppress(self, session, analysis=None, is_explicit_request=False) -> bool:
        """Product gatekeeper — returns True to block.

        Checks things the IntentAgent can't see (session state, timing):
        1. Crisis urgency → always block (safety, non-negotiable)
        2. Explicit user request → bypass remaining gates (generous cap 10)
        3. Turn 1 → no products on greeting (non-explicit only)
        4. Post-crisis cooldown → 3 turns after de-escalation
        5. Hard user dismissal ("stop suggesting products")
        6. Session cap → proactive: 3, explicit: 10
        """
        if analysis and analysis.get("urgency") == "crisis":
            return True
        if is_explicit_request:
            # Explicit requests still blocked by crisis and hard dismissal
            if session.user_dismissed_products:
                return True
            if session.explicit_product_count >= 10:
                return True
            return False
        # Non-explicit gates
        if session.turn_count < 1:
            return True  # Never recommend on first message
        if session.crisis_resolved and (session.turn_count - getattr(session, 'crisis_turn_count', 0)) < 3:
            return True  # Post-crisis cooldown
        if session.user_dismissed_products:
            return True
        if session.product_event_count >= settings.PRODUCT_SESSION_CAP:
            return True
        return False

    def _detect_product_rejection(self, session, message, analysis=None):
        """Detect and record product rejection from user message."""
        msg_lower = message.lower().strip()
        hard_dismiss_phrases = [
            "stop suggesting products", "stop recommending", "stop showing products",
            "stop products", "don't show products", "don't recommend products",
            "no more products", "enough products",
        ]
        if any(phrase in msg_lower for phrase in hard_dismiss_phrases):
            session.user_dismissed_products = True
            session.product_rejection_count += 1
            session.product_rejection_turn = session.turn_count
            return

        is_rejection = analysis.get("product_rejection", False) if analysis else False
        soft_rejection_phrases = [
            "don't want products", "no products", "not interested in shopping",
            "no recommendations", "i don't need products", "no need for products",
            "not interested in buying",
        ]
        if any(phrase in msg_lower for phrase in soft_rejection_phrases):
            is_rejection = True
        if is_rejection:
            session.product_rejection_count += 1
            session.product_rejection_turn = session.turn_count
            if session.product_rejection_count >= 2:
                session.user_dismissed_products = True

    @staticmethod
    def _is_acceptance(message: str) -> bool:
        """Check if message is acceptance of a suggestion."""
        msg = message.lower().strip()
        if len(msg.split()) > 30:
            return False
        rejection_keywords = [
            "no", "don't want", "nahi", "not interested", "something else",
            "nah", "don't think", "not now", "later", "not really",
            "don't need", "no need",
        ]
        if any(kw in msg for kw in rejection_keywords):
            return False
        acceptance_keywords = [
            "ok", "okay", "fine", "sure", "alright", "yes", "haan", "theek",
            "accha", "will do", "will try", "thanks", "got it", "sounds good",
            "thank you", "ji", "shukriya", "dhanyavaad",
            "ok i will try", "haan karunga", "haan karungi",
            "zaroor", "bilkul", "thik hai", "i will",
        ]
        return any(kw in msg for kw in acceptance_keywords)

    def _get_practice_from_history(self, session, role="assistant", lookback=2) -> List[str]:
        msgs = [m["content"].lower() for m in session.conversation_history if m.get("role") == role]
        recent = msgs[-lookback:] if len(msgs) >= lookback else msgs
        matched: List[str] = []
        for msg_text in recent:
            for practice_info in PRACTICE_PRODUCT_MAP.values():
                if any(kw in msg_text for kw in practice_info["detect"]):
                    for sk in practice_info["search_keywords"]:
                        if sk not in matched:
                            matched.append(sk)
        return matched

    def _get_user_item_mentions(self, session) -> List[str]:
        return self._get_practice_from_history(session, role="user", lookback=4)

    def _detect_practices_from_context(self, session, analysis=None) -> List[str]:
        """Detect practice NAMES from conversation context for metadata queries.

        Returns practice names like ["japa", "meditation"] — NOT search keywords.
        These are used to query product enrichment: db.products.find({"practices": "japa"})
        """
        detected = set()

        # From intent analysis entities
        if analysis:
            ritual = (analysis.get("entities", {}).get("ritual") or "").lower()
            if ritual:
                # Map ritual name to practice name
                for practice_name, info in PRACTICE_PRODUCT_MAP.items():
                    if any(kw in ritual for kw in info["detect"]):
                        detected.add(practice_name)

        # From recent conversation history
        for msg in (session.conversation_history or [])[-6:]:
            msg_text = msg.get("content", "").lower()
            for practice_name, info in PRACTICE_PRODUCT_MAP.items():
                if any(kw in msg_text for kw in info["detect"]):
                    detected.add(practice_name)

        return list(detected)

    def _get_conversation_deity(self, session, analysis=None) -> str:
        """Detect deity most relevant to current conversation."""
        if analysis:
            d = (analysis.get("entities", {}).get("deity") or "").lower().strip()
            if d:
                return d
        for msg in reversed((session.conversation_history or [])[-6:]):
            words = set(msg.get("content", "").lower().split())
            for deity in _DEITY_NAMES:
                if deity in words:
                    return deity
        # Check panchang festivals
        last_msg = ""
        if session.conversation_history:
            last_msg = session.conversation_history[-1].get("content", "").lower()
        _time_refs = {"tomorrow", "today", "tonight", "kal", "aaj", "festival", "jayanti"}
        if any(ref in last_msg for ref in _time_refs) and self.panchang_service:
            try:
                ps = self.panchang_service
                if ps and getattr(ps, 'available', False):
                    from datetime import datetime
                    panchang = ps.get_enriched_panchang(datetime.now())
                    if panchang:
                        festival_deity = (panchang.get("festival_deity") or "").lower()
                        if festival_deity and festival_deity in _DEITY_NAMES:
                            return festival_deity
                        festival_name = (panchang.get("festival") or "").lower()
                        for deity in _DEITY_NAMES:
                            if deity in festival_name:
                                return deity
            except Exception:
                pass
        return (session.memory.story.preferred_deity or "").lower().strip()

    def _build_search_query(self, analysis, session, fallback=None) -> str:
        """Build product search query from conversation context."""
        terms = []
        terms.extend(self._get_practice_from_history(session))
        terms.extend(self._get_user_item_mentions(session))

        entities = analysis.get("entities", {}) if analysis else {}
        intent = analysis.get("intent") if analysis else None
        has_worship_context = bool(
            entities.get("ritual") or entities.get("item")
            or intent in (IntentType.SEEKING_GUIDANCE, IntentType.PRODUCT_SEARCH)
            or (analysis and analysis.get("recommend_products"))
        )
        deity = self._get_conversation_deity(session, analysis)
        if deity:
            terms.insert(0, deity)
            # Deity name is enough for text search — enriched deities field handles metadata queries

        # Deduplicate preserving order
        seen = set()
        unique = []
        for t in terms:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
        context_terms = unique[:6]

        # Merge with intent keywords
        intent_terms = analysis.get("product_search_keywords", [])
        _seen = {t.lower() for t in context_terms}
        all_terms = context_terms + [t for t in intent_terms if t.lower() not in _seen]

        if all_terms:
            return " ".join(all_terms[:8])
        if fallback is not None:
            return fallback
        return ""

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
