# Adaptive Product Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggressive, hardcoded product recommendation system with an LLM-as-sole-authority model where the IntentAgent decides when to recommend based on social intelligence, cross-session memory, and a "friend who knows a shop" persona.

**Architecture:** Delete all programmatic product triggering (keyword maps, 6-gate suppression, post-gen inference). Keep the search engine intact. Add product interaction fields to RelationalProfile for cross-session memory. Enrich the IntentAgent prompt with product history context and a persona-based instruction. Simplify ProductRecommender to 3 steps: hard safety check, trust LLM, search and return.

**Tech Stack:** FastAPI (Python 3.11), MongoDB (RelationalProfile), Google Gemini (IntentAgent), pytransitions (FSM)

**Spec:** `docs/superpowers/specs/2026-04-13-adaptive-product-recommendations-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/models/memory_context.py` | Modify | Add product interaction fields to RelationalProfile, add `to_product_context()` |
| `backend/services/product_recommender.py` | Rewrite | Delete hardcoded maps/dead code, simplify `recommend()` to 3-step flow |
| `backend/services/intent_agent.py` | Modify | Replace product_signal rules with persona prompt, simplify fallback |
| `backend/services/companion_engine.py` | Modify | Update `recommend()` call sites for new signature |
| `backend/routers/chat.py` | Modify | Remove `record_suggestion()` call, wire product context |
| `backend/config.py` | Modify | Remove 4 dead product throttling settings |
| `backend/tests/unit/test_product_recommender.py` | Create | Tests for simplified recommender |
| `backend/tests/unit/test_product_memory.py` | Create | Tests for RelationalProfile product fields |

---

### Task 1: Add Product Interaction Fields to RelationalProfile

**Files:**
- Modify: `backend/models/memory_context.py:300-319`
- Create: `backend/tests/unit/test_product_memory.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_product_memory.py`:

```python
"""Tests for RelationalProfile product interaction fields and serialization."""
import pytest
from models.memory_context import RelationalProfile


class TestProductFields:
    """Product interaction fields exist with correct defaults."""

    def test_default_product_preference_is_neutral(self):
        profile = RelationalProfile()
        assert profile.product_preference == "neutral"

    def test_default_product_shown_count_is_zero(self):
        profile = RelationalProfile()
        assert profile.product_shown_count == 0

    def test_default_product_rejection_count_is_zero(self):
        profile = RelationalProfile()
        assert profile.product_rejection_count == 0

    def test_default_product_purchased_items_is_empty(self):
        profile = RelationalProfile()
        assert profile.product_purchased_items == []


class TestProductContext:
    """to_product_context() serializes product history for LLM prompt."""

    def test_neutral_with_no_history(self):
        profile = RelationalProfile()
        ctx = profile.to_product_context()
        assert "shown 0 times" in ctx
        assert "preference: neutral" in ctx

    def test_opted_out_user(self):
        profile = RelationalProfile()
        profile.product_preference = "opted_out"
        profile.product_last_rejected_at = "2026-04-10"
        ctx = profile.to_product_context()
        assert "opted out" in ctx
        assert "Do not recommend" in ctx

    def test_user_with_history(self):
        profile = RelationalProfile()
        profile.product_shown_count = 4
        profile.product_last_shown_at = "2026-04-10"
        profile.product_rejection_count = 1
        ctx = profile.to_product_context()
        assert "shown 4 times" in ctx
        assert "2026-04-10" in ctx
        assert "rejected 1 time" in ctx

    def test_receptive_user(self):
        profile = RelationalProfile()
        profile.product_preference = "receptive"
        profile.product_shown_count = 3
        ctx = profile.to_product_context()
        assert "preference: receptive" in ctx


class TestProductFieldSerialization:
    """Product fields survive to_dict/from_dict roundtrip."""

    def test_roundtrip_preserves_product_fields(self):
        profile = RelationalProfile()
        profile.product_preference = "opted_out"
        profile.product_shown_count = 5
        profile.product_last_shown_at = "2026-04-10"
        profile.product_rejection_count = 2
        profile.product_last_rejected_at = "2026-04-08"
        profile.product_purchased_items = ["Rudraksha Mala"]

        data = profile.to_dict()
        restored = RelationalProfile.from_dict(data)

        assert restored.product_preference == "opted_out"
        assert restored.product_shown_count == 5
        assert restored.product_last_shown_at == "2026-04-10"
        assert restored.product_rejection_count == 2
        assert restored.product_last_rejected_at == "2026-04-08"
        assert restored.product_purchased_items == ["Rudraksha Mala"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/unit/test_product_memory.py -v
```

Expected: FAIL — `AttributeError: 'RelationalProfile' object has no attribute 'product_preference'`

- [ ] **Step 3: Add product fields to RelationalProfile**

In `backend/models/memory_context.py`, add these fields to the `RelationalProfile` dataclass
after the existing `updated_at` field (line 319):

```python
    # Product interaction memory (cross-session)
    product_preference: str = "neutral"
    product_shown_count: int = 0
    product_last_shown_at: Optional[str] = None
    product_last_rejected_at: Optional[str] = None
    product_rejection_count: int = 0
    product_purchased_items: List[str] = field(default_factory=list)
```

- [ ] **Step 4: Add `to_product_context()` method**

Add this method to the RelationalProfile class, after the existing `to_prompt_text()` method:

```python
    def to_product_context(self) -> str:
        """Serialize product interaction history as a one-line LLM context string."""
        if self.product_preference == "opted_out":
            return (
                f"Product history: user opted out of product suggestions "
                f"on {self.product_last_rejected_at}. Do not recommend products."
            )
        parts = [f"shown {self.product_shown_count} times across sessions"]
        if self.product_last_shown_at:
            parts.append(f"last on {self.product_last_shown_at}")
        if self.product_rejection_count > 0:
            parts.append(f"rejected {self.product_rejection_count} time(s)")
        parts.append(f"preference: {self.product_preference}")
        return "Product history: " + ", ".join(parts) + "."
```

- [ ] **Step 5: Update `to_dict()` and `from_dict()` to include product fields**

In the existing `to_dict()` method of RelationalProfile, add the product fields to the
returned dict. In `from_dict()`, read them with safe defaults. Follow the exact pattern
used by the existing fields (check the method bodies for the convention — they use
`data.get("field", default)`).

Add to `to_dict()` return dict:
```python
            "product_preference": self.product_preference,
            "product_shown_count": self.product_shown_count,
            "product_last_shown_at": self.product_last_shown_at,
            "product_last_rejected_at": self.product_last_rejected_at,
            "product_rejection_count": self.product_rejection_count,
            "product_purchased_items": self.product_purchased_items,
```

Add to `from_dict()` constructor call:
```python
            product_preference=data.get("product_preference", "neutral"),
            product_shown_count=data.get("product_shown_count", 0),
            product_last_shown_at=data.get("product_last_shown_at"),
            product_last_rejected_at=data.get("product_last_rejected_at"),
            product_rejection_count=data.get("product_rejection_count", 0),
            product_purchased_items=data.get("product_purchased_items", []),
```

- [ ] **Step 6: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_product_memory.py -v
```

Expected: All 9 tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/models/memory_context.py backend/tests/unit/test_product_memory.py
git commit -m "feat: add product interaction fields to RelationalProfile"
```

---

### Task 2: Delete Hardcoded Maps and Dead Code from ProductRecommender

**Files:**
- Modify: `backend/services/product_recommender.py`

This task is pure deletion. Remove all hardcoded maps, dead methods, and programmatic
gating code. The file will be left in a temporarily broken state (the `recommend()`
method will be rewritten in Task 3).

- [ ] **Step 1: Delete `PRACTICE_PRODUCT_MAP`**

Delete lines 19-92 (the entire `PRACTICE_PRODUCT_MAP` dict).

- [ ] **Step 2: Delete `_DEITY_NAMES`**

Delete lines 102-106 (the `_DEITY_NAMES` frozenset). Also delete any
`_HARD_DISMISSAL_PHRASES` or similar frozensets defined near it that are only used by
the deleted methods.

- [ ] **Step 3: Delete dead methods**

Delete these methods from the ProductRecommender class:
- `record_suggestion()` (~lines 221-234)
- `infer_from_response()` (~lines 236-316) — includes the inline `_ITEM_WORDS` set
- `_infer_proactive()` (~lines 398-453)
- `_should_suppress()` (~lines 459-488)
- `_detect_product_rejection()` (~lines 490-517)
- `_is_acceptance()` (~lines 518-538)
- `_get_practice_from_history()` (~lines 540-550)
- `_get_user_item_mentions()` (~lines 552-553)
- `_detect_practices_from_context()` (~lines 555-579)
- `_get_conversation_deity()` (~lines 581-613)
- `_build_search_query()` (~lines 615-651)
- `validate_product_signal()` (~lines 120-134, if it exists as a standalone method)

- [ ] **Step 4: Keep these methods intact**

Verify these are NOT deleted — they are needed by the new recommend() flow:
- `__init__()` 
- `_search_explicit()` (~lines 322-341)
- `_search_intent_recommended()` (~lines 343-396)
- `_filter_shown()` (~lines 653-660)
- `_record_shown()` (~lines 662-693)

- [ ] **Step 5: Verify the file parses**

```bash
cd backend && python -c "import ast; ast.parse(open('services/product_recommender.py').read()); print('Parses OK')"
```

Expected: `Parses OK` (the file may have broken method calls in recommend() — that's
fine, Task 3 rewrites it).

- [ ] **Step 6: Commit**

```bash
git add backend/services/product_recommender.py
git commit -m "refactor: delete hardcoded product maps and dead recommendation code

Removed: PRACTICE_PRODUCT_MAP (92 entries), _DEITY_NAMES, _ITEM_WORDS,
infer_from_response, record_suggestion, _should_suppress (6-gate),
_detect_product_rejection, and 8 other helper methods.

ProductRecommender.recommend() will be rewritten in the next commit."
```

---

### Task 3: Rewrite ProductRecommender.recommend()

**Files:**
- Modify: `backend/services/product_recommender.py`
- Create: `backend/tests/unit/test_product_recommender.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_product_recommender.py`:

```python
"""Tests for the simplified ProductRecommender (LLM-as-sole-authority)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from models.session import SessionState
from models.memory_context import ConversationMemory, RelationalProfile


def _make_session():
    session = SessionState()
    session.memory = ConversationMemory()
    session.shown_product_ids = set()
    session.recent_products = []
    return session


def _make_signal(intent="none", keywords=None, max_results=0, type_filter="any"):
    return {
        "intent": intent,
        "confidence": 0.8,
        "search_keywords": keywords or [],
        "max_results": max_results,
        "type_filter": type_filter,
        "sensitivity_note": "",
    }


class TestHardSafetyRails:

    @pytest.mark.asyncio
    async def test_crisis_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        analysis = {"urgency": "crisis", "product_signal": _make_signal("explicit_search", ["mala"], 3)}

        result = await pr.recommend(session, "help me", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_opted_out_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("explicit_search", ["mala"], 3)}

        with patch("services.product_recommender.load_relational_profile") as mock_load:
            profile = RelationalProfile()
            profile.product_preference = "opted_out"
            mock_load.return_value = profile
            result = await pr.recommend(session, "buy a mala", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_opted_out_overridden_by_explicit_search(self):
        """User who opted out but now explicitly asks for products gets re-engaged."""
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[{"_id": "p1", "name": "Mala"}])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("explicit_search", ["mala"], 3)}

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction") as mock_update:
            profile = RelationalProfile()
            profile.product_preference = "opted_out"
            mock_load.return_value = profile
            result = await pr.recommend(session, "where can I buy a mala?", analysis)

        assert len(result) > 0


class TestLLMAuthority:

    @pytest.mark.asyncio
    async def test_intent_none_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        analysis = {"urgency": "normal", "product_signal": _make_signal("none")}

        result = await pr.recommend(session, "I feel sad", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_intent_negative_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("negative")}

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction") as mock_update:
            mock_load.return_value = RelationalProfile()
            result = await pr.recommend(session, "stop suggesting products", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_contextual_need_triggers_search(self):
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[
            {"_id": "p1", "name": "Rudraksha Mala", "amount": 499}
        ])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("contextual_need", ["mala"], 2)}

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            result = await pr.recommend(session, "I need a mala for japa", analysis)

        assert len(result) == 1
        assert result[0]["name"] == "Rudraksha Mala"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/unit/test_product_recommender.py -v
```

Expected: FAIL — import or method signature errors.

- [ ] **Step 3: Rewrite `recommend()` and add helper imports**

Rewrite `backend/services/product_recommender.py`. The file should contain:

1. Imports (logging, typing, datetime)
2. The `ProductRecommender` class with:
   - `__init__(self, product_service, panchang_service=None)` — keep existing
   - `async def recommend(self, session, message, analysis) -> List[Dict]` — NEW simplified 3-step flow
   - `_filter_shown()` — keep existing
   - `_record_shown()` — keep existing (modified to also update RelationalProfile)
3. Two module-level async helpers:
   - `async def load_relational_profile(user_id)` — loads profile from memory_reader
   - `async def update_product_interaction(user_id, field_updates)` — writes product fields to MongoDB

The new `recommend()` method:

```python
    async def recommend(self, session: SessionState, message: str, analysis: Dict) -> List[Dict]:
        """LLM-as-sole-authority product recommendation.

        Three steps:
        1. Hard safety: crisis → empty, opted_out → empty
        2. Trust the LLM: intent none/negative → empty
        3. Search and return: use LLM's keywords to find products
        """
        signal = analysis.get("product_signal") or {}
        intent = signal.get("intent", "none")
        user_id = getattr(session.memory, "user_id", None) or getattr(session, "user_id", None)

        # Step 1: Hard safety
        if analysis.get("urgency") == "crisis":
            return []

        # Load cross-session profile for opted_out check and context
        profile = None
        if user_id:
            try:
                profile = await load_relational_profile(user_id)
            except Exception as e:
                logger.warning(f"Failed to load product profile: {e}")

        if profile and profile.product_preference == "opted_out":
            # Exception: explicit search re-engages the user
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
            # Record rejection in cross-session memory
            if user_id:
                try:
                    from datetime import datetime
                    updates = {
                        "product_rejection_count": (profile.product_rejection_count + 1) if profile else 1,
                        "product_last_rejected_at": datetime.utcnow().isoformat(),
                    }
                    # Check for hard dismissal in message
                    _hard_phrases = {"stop suggesting products", "stop recommending", "no more products",
                                     "don't show products", "dont show products", "i hate your products"}
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
                query=" ".join(keywords),
                limit=max_results + 2,  # fetch extra for dedup headroom
                product_type=type_filter if type_filter != "any" else None,
            )
        except Exception as e:
            logger.warning(f"Product search failed: {e}")
            return []

        # Metadata backfill if text search didn't find enough
        if len(products) < max_results:
            try:
                meta_products = await self.product_service.search_by_metadata(
                    keywords=keywords,
                    limit=max_results - len(products),
                )
                # Merge, dedup by _id
                seen_ids = {str(p.get("_id", "")) for p in products}
                for mp in meta_products:
                    if str(mp.get("_id", "")) not in seen_ids:
                        products.append(mp)
            except Exception as e:
                logger.warning(f"Metadata search failed: {e}")

        # Session dedup and recording
        products = self._filter_shown(session, products)
        products = products[:max_results]

        if products:
            self._record_shown(session, products)
            # Update cross-session interaction memory
            if user_id:
                try:
                    from datetime import datetime
                    shown_count = (profile.product_shown_count + 1) if profile else 1
                    await update_product_interaction(user_id, {
                        "product_shown_count": shown_count,
                        "product_last_shown_at": datetime.utcnow().isoformat(),
                    })
                except Exception as e:
                    logger.warning(f"Failed to update product shown: {e}")

        return products
```

The two module-level helpers:

```python
async def load_relational_profile(user_id: str):
    """Load RelationalProfile from memory reader (Redis-cached)."""
    from services.memory_reader import load_relational_profile as _load
    return await _load(user_id)


async def update_product_interaction(user_id: str, field_updates: dict):
    """Write product interaction fields to the user_profiles document."""
    from services.auth_service import get_mongo_client
    import asyncio
    db = get_mongo_client()
    if db is None:
        return
    await asyncio.to_thread(
        db.user_profiles.update_one,
        {"user_id": user_id},
        {"$set": field_updates},
        upsert=True,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd backend && python -m pytest tests/unit/test_product_recommender.py -v
```

Expected: All 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/services/product_recommender.py backend/tests/unit/test_product_recommender.py
git commit -m "feat: rewrite ProductRecommender with LLM-as-sole-authority

3-step flow: hard safety (crisis/opted_out) → trust LLM (none/negative
→ empty) → search with LLM's keywords. Cross-session rejection tracking
via RelationalProfile. ~120 lines down from ~700."
```

---

### Task 4: Update IntentAgent Prompt and Fallback

**Files:**
- Modify: `backend/services/intent_agent.py:74-131` (product signal rules in INTENT_PROMPT)
- Modify: `backend/services/intent_agent.py:440-523` (fallback analysis)

- [ ] **Step 1: Replace product signal rules in INTENT_PROMPT**

In `backend/services/intent_agent.py`, find the product signal rules section within
`INTENT_PROMPT` (lines 74-131). Replace that entire section with:

```
## Product Awareness

You are a friend who happens to know a shop (my3ionetra.com). You never bring up
products unless the moment genuinely calls for it. Here is how you think about it:

- If someone is hurting, you LISTEN. You do not hand them a catalog.
- If someone is exploring spirituality casually, you talk. You do not sell.
- If someone has been discussing a practice across several turns and naturally
  reaches the point where they would need something (e.g. "I want to start doing
  japa daily"), THAT is when you might mention you know where to find a mala.
- If someone directly asks "do you have products?" or "where can I buy X?",
  you help them find it immediately.
- If someone has told you before that they do not want product suggestions,
  you respect that permanently.

The bar is: would a thoughtful human friend mention a product here, or would
it feel forced? When in doubt, set intent to "none".

You will receive the user's product interaction history (how many times they have
been shown products, whether they have rejected them, their preference). Use this
to calibrate. A user who has been shown products 5 times this month needs a higher
bar than a new user.

product_signal output rules:
- "explicit_search": user's PRIMARY intent is buying/finding a product. confidence 0.8-1.0, max_results 3-5.
- "contextual_need": the conversation has naturally reached a point where a product genuinely helps. confidence 0.5-0.7, max_results 1-2.
- "casual_mention": products relevant but not primary ask. confidence 0.2-0.4, max_results 1.
- "negative": user rejects or criticizes products. confidence 0.8-1.0, max_results 0.
- "none": DEFAULT. No product interest detected. This includes emotional sharing, advice-seeking, scripture questions, greetings, closures, and any turn where recommending would feel forced. confidence 0.0, max_results 0.
```

Keep the type_filter rules (lines 123-127) and the JSON output schema unchanged.

- [ ] **Step 2: Simplify the fallback analysis**

In the `_fallback_analysis()` method (lines 440-523), find the product-related
fallback logic (around lines 454-486). Replace it with a simplified version that
only detects:

```python
        # Product signal — minimal fallback (LLM handles the real logic)
        _buy_words = {"buy", "purchase", "order", "shop", "shopping", "price", "cost"}
        _reject_phrases = {"stop suggesting products", "stop recommending", "no more products",
                          "don't show products", "dont show products"}
        msg_lower = message.lower()

        if any(p in msg_lower for p in _reject_phrases):
            product_signal = {
                "intent": "negative", "confidence": 1.0, "type_filter": "any",
                "search_keywords": [], "max_results": 0, "sensitivity_note": "",
            }
        elif any(w in msg_lower.split() for w in _buy_words):
            product_signal = {
                "intent": "explicit_search", "confidence": 0.6, "type_filter": "any",
                "search_keywords": [w for w in msg_lower.split() if len(w) > 3 and w not in _buy_words],
                "max_results": 3, "sensitivity_note": "",
            }
        else:
            product_signal = {
                "intent": "none", "confidence": 0.0, "type_filter": "any",
                "search_keywords": [], "max_results": 0, "sensitivity_note": "",
            }
```

Remove any practice-keyword scanning, deity detection, or domain mapping from the
fallback. The fallback should be conservative — when the LLM is unavailable, default
to no products unless the user explicitly asks.

- [ ] **Step 3: Verify imports and syntax**

```bash
cd backend && python -c "from services.intent_agent import get_intent_agent; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/intent_agent.py
git commit -m "feat: replace product signal rules with persona-based LLM prompt

IntentAgent now uses 'friend who knows a shop' persona instead of
structured classification rules. Fallback simplified to detect only
explicit buy words and hard rejection phrases."
```

---

### Task 5: Wire Product Context into IntentAgent

**Files:**
- Modify: `backend/services/companion_engine.py:208-210` (where analyze_intent is called)
- Modify: `backend/services/intent_agent.py:350` (analyze_intent signature)

The IntentAgent needs to see the product interaction history and session product count
to make informed decisions. The context_summary parameter already exists — we enrich it.

- [ ] **Step 1: Add product context to the context_summary passed to analyze_intent**

In `backend/services/companion_engine.py`, find where `analyze_intent` is called in
`process_message_preamble()` (around line 208):

```python
        analysis = await self.intent_agent.analyze_intent(
            message, session.memory.get_memory_summary()
        )
```

Change it to build a richer context that includes product history:

```python
        # Build context with product interaction history for LLM
        memory_summary = session.memory.get_memory_summary()
        product_context = ""
        _uid = getattr(session.memory, "user_id", None) or getattr(session, "user_id", None)
        if _uid and hasattr(session, "_product_profile_text"):
            product_context = session._product_profile_text
        elif _uid:
            try:
                from services.memory_reader import load_relational_profile
                _profile = await load_relational_profile(_uid)
                product_context = _profile.to_product_context()
                session._product_profile_text = product_context  # cache for this turn
            except Exception:
                pass

        # Add session-level product count
        _session_products = len(getattr(session, "shown_product_ids", set()))
        if _session_products > 0:
            product_context += f" Products shown this session: {_session_products}."

        context_with_products = memory_summary
        if product_context:
            context_with_products += "\n" + product_context

        analysis = await self.intent_agent.analyze_intent(
            message, context_with_products
        )
```

- [ ] **Step 2: Verify the wiring**

```bash
cd backend && python -c "from services.companion_engine import CompanionEngine; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/companion_engine.py
git commit -m "feat: inject product interaction history into IntentAgent context

LLM now sees cross-session product history (shown count, rejections,
preference) and session product count when classifying intent."
```

---

### Task 6: Update CompanionEngine Call Sites

**Files:**
- Modify: `backend/services/companion_engine.py:390-395, 514-518`

The `recommend()` signature changed: removed `turn_topics`, `is_ready_for_wisdom`,
and `life_domain` parameters.

- [ ] **Step 1: Update guidance-phase call site**

In `backend/services/companion_engine.py`, find the guidance-phase product call
(around line 390-395):

```python
            product_task = asyncio.create_task(
                self.product_recommender.recommend(
                    session, message, analysis, turn_topics,
                    is_ready_for_wisdom=True,
                    life_domain=analysis.get("life_domain", "unknown"),
                )
            )
```

Replace with:

```python
            product_task = asyncio.create_task(
                self.product_recommender.recommend(session, message, analysis)
            )
```

- [ ] **Step 2: Update listening-phase call site**

Find the listening-phase product call (around line 514-518):

```python
        products = await self.product_recommender.recommend(
            session, message, analysis, turn_topics,
            is_ready_for_wisdom=False,
            life_domain=analysis.get("life_domain", "unknown"),
        )
```

Replace with:

```python
        products = await self.product_recommender.recommend(session, message, analysis)
```

- [ ] **Step 3: Also update the streaming path call site**

In `generate_response_stream()` method (earlier in the file), there may be a similar
product recommendation call. Search for `product_recommender.recommend` in the file
and update any remaining call sites to use the new 3-parameter signature.

- [ ] **Step 4: Verify**

```bash
cd backend && python -c "from services.companion_engine import CompanionEngine; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/services/companion_engine.py
git commit -m "refactor: update recommend() call sites for simplified signature

Removed turn_topics, is_ready_for_wisdom, and life_domain parameters.
The LLM-as-sole-authority recommender only needs session, message, and
analysis."
```

---

### Task 7: Clean Up chat.py and config.py

**Files:**
- Modify: `backend/routers/chat.py:477`
- Modify: `backend/config.py:253-256`

- [ ] **Step 1: Remove `record_suggestion()` call from chat.py**

In `backend/routers/chat.py`, find the `record_suggestion` call in
`_postprocess_and_save()` (around line 477):

```python
    # Record practice suggestions for future product inference
    companion_engine.record_suggestion(session, final_text)
```

Delete these two lines (the comment and the call).

- [ ] **Step 2: Remove dead config settings**

In `backend/config.py`, find and delete these four settings (around lines 253-256):

```python
    PRODUCT_SESSION_CAP: int = 3
    PRODUCT_COOLDOWN_TURNS: int = 7
    PRODUCT_COOLDOWN_AFTER_REJECTION: int = 10
    PRODUCT_MIN_TURN_FOR_PROACTIVE: int = 2
```

Also delete any comments above them that describe the removed behavior.

- [ ] **Step 3: Verify no references remain**

```bash
cd backend && grep -rn "PRODUCT_SESSION_CAP\|PRODUCT_COOLDOWN_TURNS\|PRODUCT_COOLDOWN_AFTER_REJECTION\|PRODUCT_MIN_TURN_FOR_PROACTIVE\|record_suggestion" --include="*.py" | grep -v test | grep -v "__pycache__"
```

Expected: No matches (or only in test files that will be updated).

- [ ] **Step 4: Commit**

```bash
git add backend/routers/chat.py backend/config.py
git commit -m "refactor: remove dead product config and record_suggestion call

Removed PRODUCT_SESSION_CAP, PRODUCT_COOLDOWN_TURNS,
PRODUCT_COOLDOWN_AFTER_REJECTION, PRODUCT_MIN_TURN_FOR_PROACTIVE
from config. Removed record_suggestion() call from chat.py
_postprocess_and_save()."
```

---

### Task 8: Run Full Test Suite and E2E Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run all unit tests**

```bash
cd backend && python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass. If any existing tests reference deleted methods or config
settings, fix them by either updating or deleting the test.

- [ ] **Step 2: Start the server**

```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port 8081
```

Wait for "Application startup complete."

- [ ] **Step 3: Run full E2E test suite**

```bash
cd backend && E2E_BASE_URL=http://localhost:8081 python tests/e2e_full_test.py
```

Expected: 112/112 (100%). The product-related E2E tests should still pass because
the IntentAgent will correctly classify explicit product requests and the search
engine is unchanged.

- [ ] **Step 4: Manual smoke test — emotional conversation should show zero products**

```bash
cd backend
python -c "
import httpx, uuid, json
BASE = 'http://localhost:8081'
c = httpx.Client()
email = f'smoke_{uuid.uuid4().hex[:6]}@test.com'
r = c.post(f'{BASE}/api/auth/register', json={'name':'Test','email':email,'password':'TestPass123'})
token = r.json().get('token','')
h = {'Authorization': f'Bearer {token}'}
sid = c.post(f'{BASE}/api/session/create', headers=h).json().get('session_id','')

# Emotional conversation — should have ZERO products
for msg in ['I lost my mother last week', 'I cannot stop crying', 'I feel so alone']:
    r = c.post(f'{BASE}/api/conversation', json={'session_id':sid,'message':msg}, headers=h, timeout=60)
    data = r.json()
    products = data.get('recommended_products', [])
    print(f'Message: {msg[:40]}  Products: {len(products)}  Phase: {data.get(\"phase\")}')
    assert len(products) == 0, f'Got products on emotional turn: {products}'

print('Smoke test PASSED — zero products on emotional turns')
"
```

- [ ] **Step 5: Manual smoke test — explicit product request should return products**

```bash
cd backend
python -c "
import httpx, uuid, json
BASE = 'http://localhost:8081'
c = httpx.Client()
email = f'smoke2_{uuid.uuid4().hex[:6]}@test.com'
r = c.post(f'{BASE}/api/auth/register', json={'name':'Test2','email':email,'password':'TestPass123'})
token = r.json().get('token','')
h = {'Authorization': f'Bearer {token}'}
sid = c.post(f'{BASE}/api/session/create', headers=h).json().get('session_id','')

# Explicit product request — should return products
r = c.post(f'{BASE}/api/conversation', json={'session_id':sid,'message':'Where can I buy a rudraksha mala?'}, headers=h, timeout=60)
data = r.json()
products = data.get('recommended_products', [])
print(f'Explicit request: {len(products)} products returned')
print(f'Product names: {[p.get(\"name\",\"?\") for p in products]}')
assert len(products) > 0, 'Expected products for explicit request'

print('Smoke test PASSED — products returned for explicit request')
"
```

- [ ] **Step 6: Push to feature branch**

```bash
git push origin feature/product-recommendations
```

- [ ] **Step 7: Commit verification results**

```bash
git add backend/tests/e2e_results.json
git commit -m "test: E2E 112/112, smoke tests pass — adaptive product recommendations verified"
git push origin feature/product-recommendations
```
