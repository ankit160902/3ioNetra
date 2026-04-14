# Bug Report Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 bugs from `backend/BUG_REPORT.md` — type_filter mismatch, metadata fallback missing practices, test expectation alignment, and session GET 404 — with structural root-cause fixes.

**Architecture:** All fixes are targeted changes to existing files with no new files created. Bug #1 and #2 modify the product recommender. Bug #3 updates test expectations. Bug #4 hardens the session serialization round-trip and error propagation in the session manager.

**Tech Stack:** Python 3.11, FastAPI, pytest, asyncio, Redis, MongoDB

**Spec:** `docs/superpowers/specs/2026-04-14-bug-report-fixes-design.md`

---

### Task 1: Bug #1 — Fix type_filter `_only` suffix mismatch (CRITICAL)

**Files:**
- Modify: `backend/services/product_recommender.py:152`
- Test: `backend/tests/unit/test_product_recommender.py`

- [ ] **Step 1: Write failing test for type_filter normalization**

Add this test to `backend/tests/unit/test_product_recommender.py` at the end of the `TestLLMAuthority` class:

```python
    @pytest.mark.asyncio
    async def test_type_filter_strips_only_suffix(self):
        """Bug #1: type_filter 'physical_only' must be normalized to 'physical'."""
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[
            {"_id": "p1", "name": "Krishna Murti", "product_type": "physical"}
        ])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        analysis = {
            "urgency": "normal",
            "product_signal": _make_signal("contextual_need", ["krishna", "murti"], 3, type_filter="physical_only"),
        }

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            result = await pr.recommend(session, "I want a Krishna murti", analysis)

        # Verify search_products was called with "physical", not "physical_only"
        mock_service.search_products.assert_called_once()
        call_kwargs = mock_service.search_products.call_args
        assert call_kwargs.kwargs.get("product_type") == "physical" or \
               call_kwargs[1].get("product_type") == "physical", \
               f"Expected product_type='physical', got {call_kwargs}"
        assert len(result) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestLLMAuthority::test_type_filter_strips_only_suffix -v`

Expected: FAIL — `search_products` is called with `product_type="physical_only"` instead of `"physical"`.

- [ ] **Step 3: Implement the fix**

In `backend/services/product_recommender.py`, replace line 152:

```python
# Before:
        type_filter = signal.get("type_filter", "any")
# After:
        type_filter_raw = signal.get("type_filter", "any")
        type_filter = "any" if type_filter_raw == "any" else type_filter_raw.replace("_only", "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestLLMAuthority::test_type_filter_strips_only_suffix -v`

Expected: PASS

- [ ] **Step 5: Run full test_product_recommender suite to check for regressions**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/product_recommender.py backend/tests/unit/test_product_recommender.py
git commit -m "fix: strip _only suffix from type_filter before MongoDB query

The IntentAgent returns type_filter values like 'physical_only' but
MongoDB products store product_type as 'physical'. The _only suffix
was being passed through unstripped, causing all filtered product
searches to return 0 results.

Restores the mapping that existed before commit f17b342."
```

---

### Task 2: Bug #2 — Pass practices to metadata fallback

**Files:**
- Modify: `backend/services/product_recommender.py:167-182`
- Test: `backend/tests/unit/test_product_recommender.py`

- [ ] **Step 1: Write failing test for practices pass-through**

Add this test class to `backend/tests/unit/test_product_recommender.py`:

```python
class TestMetadataFallback:

    @pytest.mark.asyncio
    async def test_practices_passed_to_metadata_fallback(self):
        """Bug #2: practices from entities must be passed to search_by_metadata."""
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        # Text search returns 0 results to trigger metadata fallback
        mock_service.search_products = AsyncMock(return_value=[])
        mock_service.search_by_metadata = AsyncMock(return_value=[
            {"_id": "p1", "name": "Puja Thali Set", "product_type": "physical"}
        ])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        analysis = {
            "urgency": "normal",
            "life_domain": "spiritual",
            "emotion": "neutral",
            "entities": {"ritual": "puja", "deity": "Ganesh"},
            "product_signal": _make_signal("contextual_need", ["puja", "thali"], 3),
        }

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            result = await pr.recommend(session, "I need puja items for Ganesh puja", analysis)

        mock_service.search_by_metadata.assert_called_once()
        call_kwargs = mock_service.search_by_metadata.call_args[1]
        assert call_kwargs.get("practices") is not None, \
            f"practices not passed to search_by_metadata. Got kwargs: {call_kwargs}"
        assert "puja" in call_kwargs["practices"], \
            f"Expected 'puja' in practices, got {call_kwargs['practices']}"

    @pytest.mark.asyncio
    async def test_practice_terms_extracted_from_keywords(self):
        """Bug #2: practice terms in search_keywords should also be passed."""
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[])
        mock_service.search_by_metadata = AsyncMock(return_value=[])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        analysis = {
            "urgency": "normal",
            "life_domain": "spiritual",
            "emotion": "neutral",
            "entities": {},
            "product_signal": _make_signal("contextual_need", ["meditation", "cushion"], 3),
        }

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            await pr.recommend(session, "I need something for meditation", analysis)

        mock_service.search_by_metadata.assert_called_once()
        call_kwargs = mock_service.search_by_metadata.call_args[1]
        assert call_kwargs.get("practices") is not None
        assert "meditation" in call_kwargs["practices"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestMetadataFallback -v`

Expected: FAIL — `practices` is not in the `search_by_metadata` call kwargs.

- [ ] **Step 3: Implement the fix**

In `backend/services/product_recommender.py`, replace lines 167-182 (the `if len(products) < max_results:` block) with:

```python
        if len(products) < max_results:
            try:
                _life_domain = analysis.get("life_domain")
                _emotion = analysis.get("emotion")
                _entities = analysis.get("entities") or {}

                # Extract practices from entities and search keywords
                _practices = []
                for key in ("ritual", "item", "practice"):
                    val = _entities.get(key)
                    if val:
                        _practices.extend(val if isinstance(val, list) else [val])
                _practice_terms = {"puja", "japa", "meditation", "yoga", "mantra", "aarti",
                                   "abhishekam", "havan", "yagna", "pranayama", "dhyana"}
                for kw in keywords:
                    if kw.lower() in _practice_terms:
                        _practices.append(kw.lower())
                _practices = list(set(_practices)) or None

                meta_products = await self.product_service.search_by_metadata(
                    life_domains=[_life_domain] if _life_domain and _life_domain != "unknown" else None,
                    emotions=[_emotion] if _emotion and _emotion not in ("neutral", "unknown") else None,
                    deities=_entities.get("deity") if isinstance(_entities.get("deity"), list) else (
                        [_entities["deity"]] if _entities.get("deity") else None
                    ),
                    practices=_practices,
                    limit=max_results - len(products),
                )
                seen_ids = {str(p.get("_id", "")) for p in products}
                for mp in meta_products:
                    if str(mp.get("_id", "")) not in seen_ids:
                        products.append(mp)
            except Exception as e:
                logger.warning(f"Metadata search failed: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestMetadataFallback -v`

Expected: PASS

- [ ] **Step 5: Run full test_product_recommender suite**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/product_recommender.py backend/tests/unit/test_product_recommender.py
git commit -m "fix: pass practices to metadata fallback in product recommender

The metadata fallback search was missing the practices parameter,
which is the strongest signal (+3 score) in search_by_metadata.
Extracts practices from IntentAgent entities (ritual, item, practice
keys) and from search_keywords matching known practice terms."
```

---

### Task 3: Bug #4 — Fix SessionState serialization round-trip

**Files:**
- Modify: `backend/models/session.py:132-201`
- Test: `backend/tests/unit/test_product_recommender.py` (reusing file for session tests is fine, or a new focused test)

- [ ] **Step 1: Write failing test for suggested_verses round-trip**

Add to `backend/tests/unit/test_product_recommender.py` (or create focused test — using existing file for simplicity since it already imports SessionState):

```python
class TestSessionSerialization:

    def test_suggested_verses_survives_round_trip(self):
        """Bug #4: suggested_verses must be in to_dict/from_dict."""
        session = _make_session()
        session.suggested_verses = [
            {"turn": 1, "mantras": ["Om Namah Shivaya"], "references": ["BG 2.47"]}
        ]
        data = session.to_dict()
        assert "suggested_verses" in data, "suggested_verses missing from to_dict()"

        restored = SessionState.from_dict(data)
        assert restored.suggested_verses == session.suggested_verses, \
            f"suggested_verses lost in round-trip: {restored.suggested_verses}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestSessionSerialization::test_suggested_verses_survives_round_trip -v`

Expected: FAIL — `"suggested_verses" not in data` because `to_dict()` doesn't include it.

- [ ] **Step 3: Fix to_dict — add suggested_verses**

In `backend/models/session.py`, in the `to_dict()` method, add `suggested_verses` before the `memory` line. Replace:

```python
            "readiness_trigger": self.readiness_trigger,
            "memory": self.memory.to_dict() if self.memory else None
```

with:

```python
            "readiness_trigger": self.readiness_trigger,
            "suggested_verses": self.suggested_verses,
            "memory": self.memory.to_dict() if self.memory else None
```

- [ ] **Step 4: Fix from_dict — read suggested_verses**

In `backend/models/session.py`, in the `from_dict()` method, add `suggested_verses` before the `memory` line. Replace:

```python
            readiness_trigger=data.get("readiness_trigger", "listening"),
            memory=ConversationMemory.from_dict(data.get("memory", {}))
```

with:

```python
            readiness_trigger=data.get("readiness_trigger", "listening"),
            suggested_verses=data.get("suggested_verses", []),
            memory=ConversationMemory.from_dict(data.get("memory", {}))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestSessionSerialization -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/models/session.py backend/tests/unit/test_product_recommender.py
git commit -m "fix: include suggested_verses in SessionState serialization

suggested_verses was missing from to_dict/from_dict, causing data
loss on round-trip through Redis/Mongo session storage. This is a
latent bug in the same serialization path as Bug #4."
```

---

### Task 4: Bug #4 — Harden Redis session manager error handling

**Files:**
- Modify: `backend/services/session_manager.py:219-245`

- [ ] **Step 1: Write failing test for error propagation**

Add to `backend/tests/unit/test_product_recommender.py`:

```python
class TestRedisSessionManager:

    @pytest.mark.asyncio
    async def test_update_session_propagates_error(self):
        """Bug #4: update_session must not silently swallow errors."""
        import json
        from services.session_manager import RedisSessionManager

        with patch("services.session_manager.redis.Redis") as MockRedis:
            mock_instance = AsyncMock()
            mock_instance.ping = AsyncMock(return_value=True)
            mock_instance.setex = AsyncMock(side_effect=Exception("Redis write failed"))
            MockRedis.return_value = mock_instance

            manager = RedisSessionManager.__new__(RedisSessionManager)
            manager._redis = mock_instance
            manager._ttl_seconds = 3600

            session = _make_session()
            with pytest.raises(Exception, match="Redis write failed"):
                await manager.update_session(session)

    @pytest.mark.asyncio
    async def test_get_session_logs_deserialization_errors(self):
        """Bug #4: get_session must log actual error, not just 'error'."""
        from services.session_manager import RedisSessionManager

        with patch("services.session_manager.redis.Redis") as MockRedis:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=b'{"invalid": "missing required fields"}')
            MockRedis.return_value = mock_instance

            manager = RedisSessionManager.__new__(RedisSessionManager)
            manager._redis = mock_instance
            manager._ttl_seconds = 3600

            with patch("services.session_manager.logger") as mock_logger:
                result = await manager.get_session("test-id")
                assert result is None
                mock_logger.error.assert_called_once()
                log_msg = mock_logger.error.call_args[0][0]
                assert "test-id" in log_msg or "KeyError" in log_msg, \
                    f"Error log should include session_id or error type, got: {log_msg}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestRedisSessionManager -v`

Expected: FAIL — `update_session` does not raise (it swallows the exception). `get_session` log message may not include session_id.

- [ ] **Step 3: Fix update_session — re-raise errors**

In `backend/services/session_manager.py`, replace the `update_session` method (lines 232-245):

```python
    async def update_session(self, session: SessionState) -> None:
        import json
        session.last_activity = datetime.utcnow()
        data = session.to_dict()
        
        try:
            # Store as JSON with TTL
            await self._redis.setex(
                f"session:{session.session_id}",
                self._ttl_seconds,
                json.dumps(data)
            )
        except Exception as e:
            logger.error(f"Redis update_session error for {session.session_id}: {e}")
            raise
```

- [ ] **Step 4: Fix get_session — log with session_id and error type**

In `backend/services/session_manager.py`, replace the `get_session` method (lines 219-230):

```python
    async def get_session(self, session_id: str) -> Optional[SessionState]:
        import json
        try:
            data = await self._redis.get(f"session:{session_id}")
            if not data:
                return None
            
            session_dict = json.loads(data)
            return SessionState.from_dict(session_dict)
        except Exception as e:
            logger.error(f"Redis get_session error for {session_id}: {type(e).__name__}: {e}")
            return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_product_recommender.py::TestRedisSessionManager -v`

Expected: PASS

- [ ] **Step 6: Run full unit test suite to check for regressions**

Run: `cd backend && python -m pytest tests/unit/ -v --timeout=30`

Expected: All existing tests PASS. Some tests that previously mocked `update_session` may need adjustment if they expected it not to raise — check for failures and fix any mocks that need `side_effect=None` set explicitly.

- [ ] **Step 7: Commit**

```bash
git add backend/services/session_manager.py backend/tests/unit/test_product_recommender.py
git commit -m "fix: propagate Redis session write errors, improve error logging

update_session now re-raises exceptions instead of silently swallowing
them, so create_session callers know when storage failed. get_session
logs the session_id and exception type for diagnosability."
```

---

### Task 5: Bug #3 — Update test expectations for emotional product scenarios

**Files:**
- Modify: `backend/tests/test_product_recommendations.py:93-156` (scenarios A1, A2, A3, A5)

- [ ] **Step 1: Update scenario A1 to not expect products**

In `backend/tests/test_product_recommendations.py`, replace the A1 scenario (lines 92-104):

```python
    Scenario(
        id="A1",
        name="Anxiety + Career",
        category="emotion",
        persona={"name": "Ravi Test", "gender": "male", "profession": "Manager", "age_group": "30-40"},
        messages=[
            "Namaste, I am going through a very difficult time",
            "I have severe anxiety about losing my job, I can't sleep at night",
            "The constant fear of layoffs is making me physically sick",
            "Can you suggest something that might help me find peace?",
        ],
        expect_products=False,
        must_not_have_products=True,
    ),
```

- [ ] **Step 2: Update scenario A2 to not expect products**

Replace the A2 scenario (lines 106-117):

```python
    Scenario(
        id="A2",
        name="Grief + Spiritual",
        category="emotion",
        persona={"name": "Meera Test", "gender": "female", "profession": "Homemaker", "age_group": "50-60"},
        messages=[
            "Namaste, my father passed away last month",
            "I feel so lost without him, he was my spiritual guide",
            "I want to do something for his soul, some spiritual ritual",
            "Please suggest how I can honour his memory spiritually",
        ],
        expect_products=False,
        must_not_have_products=True,
    ),
```

- [ ] **Step 3: Update scenario A3 to not expect products**

Replace the A3 scenario (lines 118-130):

```python
    Scenario(
        id="A3",
        name="Anger + Family",
        category="emotion",
        persona={"name": "Amit Test", "gender": "male", "profession": "Business Owner", "age_group": "40-50"},
        messages=[
            "I have a terrible anger problem",
            "My anger is destroying my family, my children are scared of me",
            "I shout at everyone and then feel terrible afterwards",
            "I need help controlling this, suggest something please",
        ],
        expect_products=False,
        must_not_have_products=True,
    ),
```

- [ ] **Step 4: Update scenario A5 to not expect products**

Replace the A5 scenario (lines 144-156):

```python
    Scenario(
        id="A5",
        name="Sadness + Loneliness",
        category="emotion",
        persona={"name": "Sita Test", "gender": "female", "profession": "Retired", "age_group": "60+"},
        messages=[
            "I feel so alone these days",
            "My children are all abroad, I have no friends nearby",
            "The loneliness is crushing me, I feel so sad",
            "Is there anything that can bring some peace to my heart?",
        ],
        expect_products=False,
        must_not_have_products=True,
    ),
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_product_recommendations.py
git commit -m "fix: align product test expectations with empathy-first design

Scenarios A1, A2, A3, A5 involve deep emotional distress. The
IntentAgent correctly returns intent='none' per its design rule:
'If someone is hurting, you LISTEN. You do not hand them a catalog.'
Updated tests to expect no products for these emotional scenarios."
```

---

### Task 6: Final verification

- [ ] **Step 1: Run the full unit test suite**

Run: `cd backend && python -m pytest tests/unit/ -v --timeout=30`

Expected: All tests PASS, including the new tests added in Tasks 1-4.

- [ ] **Step 2: Verify no import errors or syntax issues**

Run: `cd backend && python -c "from services.product_recommender import ProductRecommender; from services.session_manager import RedisSessionManager; from models.session import SessionState; print('All imports OK')"`

Expected: `All imports OK`

- [ ] **Step 3: Commit any remaining fixes if needed**

Only if Step 1 or 2 revealed issues.
