# 3ioNetra Backend — Architecture Refactoring Documentation

## Executive Summary

The 3ioNetra backend underwent a 9-phase architectural refactoring to transform a **1,710-line monolithic orchestrator** (`CompanionEngine`) into a modular, testable, and observable system.

### Key Results

| Metric | Before | After |
|--------|--------|-------|
| CompanionEngine lines | 1,710 | 621 (**-64%**) |
| Unit tests | 0 | 203 |
| Test execution time | N/A | 0.33s |
| External deps for testing | Gemini + Redis + MongoDB + ML models | **None** (all mocked) |
| Extracted services | 0 | 4 |
| Port interfaces | 0 | 6 |
| Dead dependencies | langchain, langchain-community | Removed |
| Event loop blockers | 8 locations | 0 |
| JSON parsing strategy | Manual regex + balanced-brace | Pydantic validated |
| Request tracing | None | Correlation IDs + timing |

---

## Phase-by-Phase Changelog

### Phase 0: Fix Blockers
**Problem:** Event loop blocking, dead dependencies, unsafe async patterns.

| Change | File | Impact |
|--------|------|--------|
| Remove dead `langchain` + `langchain-community` | `requirements.txt` | Reduced image size, removed 0-import deps |
| Fix `time.sleep(2)` → `await asyncio.sleep(2)` | `llm/service.py` | Unblocked event loop during video analysis |
| Wrap pymongo calls with `asyncio.to_thread()` | `services/product_service.py` | 6 async-unsafe `.find()` calls fixed |
| Non-blocking MongoDB inserts | `services/cost_tracker.py` | `loop.run_in_executor()` for fire-and-forget writes |
| Wrap feedback endpoint | `routers/chat.py` | `asyncio.to_thread` for `db.feedback.update_one` |
| Offload numpy matrix ops to thread pool | `services/memory_service.py` | `_rank_and_dedup()` closure via `asyncio.to_thread` |
| Remove duplicate `pymongo` in requirements | `requirements.txt` | Cleanup |

**Tests added:** 20 (AST-based structural tests + runtime behavior tests)

---

### Phase 1: Hexagonal Architecture (Ports & Adapters)
**Problem:** CompanionEngine directly imported 7+ singletons — impossible to test without live services.

**Created: `backend/ports/` package (7 files)**

| Port | File | Methods | What It Abstracts |
|------|------|---------|-------------------|
| `LLMPort` | `ports/llm.py` | `generate_response`, `generate_response_stream` | Gemini API |
| `RAGPort` | `ports/rag.py` | `search`, `generate_embeddings` | Embedding search + reranking |
| `IntentPort` | `ports/intent.py` | `analyze_intent` | LLM intent classification |
| `MemoryPort` | `ports/memory.py` | `store_memory`, `retrieve_relevant_memories` | Long-term semantic memory |
| `ProductPort` | `ports/product.py` | `search_products`, `get_recommended_products` | Product search |
| `SafetyPort` | `ports/safety.py` | `check_crisis_signals`, `validate_response` | Crisis detection |

**CompanionEngine DI constructor:**
```python
class CompanionEngine:
    def __init__(
        self,
        rag_pipeline=None,
        *,
        llm=None,            # LLMPort
        intent_agent=None,   # IntentPort
        memory_service=None,  # MemoryPort
        product_service=None, # ProductPort
        panchang=None,
        model_router=None,
    ):
```

All parameters default to `None` → falls back to singleton factories → **100% backwards compatible**.

**Mock adapters created:** `tests/unit/mocks.py` — `MockLLM`, `MockRAG`, `MockIntent`, `MockMemory`, `MockProduct`, `MockSafety`

All mocks satisfy their Protocol via `isinstance()` checks (runtime_checkable).

**Tests added:** 43 (port structure + protocol satisfaction + mock behavior)

---

### Phase 2: ConversationFSM (pytransitions)
**Problem:** 87-line `_assess_readiness()` method with 4 overlapping conditions, cooldown logic, distress gates — impossible to reason about or test in isolation.

**Created:** `services/conversation_fsm.py` (276 lines)

**States:** `LISTENING`, `GUIDANCE`, `CLOSURE`

**Transitions (evaluated in priority order):**

```
1. ANY → CLOSURE           (when: intent == CLOSURE)
2. LISTENING → GUIDANCE    (when: explicit request — panchang, product, verse)
3. LISTENING → GUIDANCE    (when: guidance ask + min turns met)
4. LISTENING → GUIDANCE    (when: readiness score ≥ 0.7 + min turns + cooldown passed)
5. LISTENING → GUIDANCE    (when: force transition — max turns reached)
6. LISTENING → LISTENING   (fallback: keep listening)
7. GUIDANCE → LISTENING    (when: return_to_listening() called)
```

**Guard conditions (all testable independently):**
- `is_explicit_request()` — checks intent + turn_topics
- `is_guidance_ask()` — checks intent + needs_direct_answer
- `min_turns_met_for_ask()` — distress-aware (grief/shame/fear → +1 turn)
- `cooldown_passed()` — 3-turn spacing with urgent keyword override
- `readiness_threshold_met()` — readiness_for_wisdom ≥ 0.7
- `should_force_transition()` — delegates to session.should_force_transition()

**Public API:**
```python
fsm = ConversationFSM(session)
is_ready, trigger = fsm.evaluate(analysis, turn_topics)
# Returns: (True, "explicit_request") or (False, "listening")
```

**Integration:** Replaced inline if/else in both `process_message_preamble()` and `generate_response_stream()`. Deleted `_assess_readiness()` entirely.

**Tests added:** 30 (every transition path + every guard condition + cooldown + distress + multi-turn)

---

### Phase 3: God-Class Extraction
**Problem:** CompanionEngine was a 1,710-line god-class owning product maps, memory keyword detection, signal collection, phase transitions, and orchestration.

#### 3a. SignalCollector (56 lines)
**File:** `services/signal_collector.py`

**Extracted from:** Duplicated signal blocks in `process_message_preamble()` and `generate_response_stream()`.

```python
collect_signals_from_analysis(session, analysis)
# Updates: session signals, memory.story fields, dharmic concepts
```

**Tests:** 11

#### 3b. MemoryUpdater (260 lines)
**File:** `services/memory_updater.py`

**Extracted from:** `CompanionEngine._update_memory()` — 290-line keyword-based detection method.

**Detects:** 5 emotion categories, 11 life domains, 7 special intents (verse request, product inquiry, routine, puja guidance, diet plan, temple, pranayama).

```python
turn_topics = update_memory(memory, session, text)
# Returns: ["Anxiety & Fear", "Career & Finance", "Verse Request"]
```

**Tests:** 20 (emotions, domains, special intents, readiness boosters)

#### 3c. ProductRecommender (540 lines)
**File:** `services/product_recommender.py`

**Extracted from:** 5 product maps + 12 methods + 79-line product blocks in both guidance/listening paths.

**Owns:**
- `PRACTICE_PRODUCT_MAP` (18 practices → search keywords)
- `DEITY_PRODUCT_MAP`, `DOMAIN_PRODUCT_MAP`, `EMOTION_PRODUCT_MAP`, `CONCEPT_PRODUCT_MAP`
- 6-gate gatekeeper (`_should_suppress`)
- Rejection detection (hard dismiss + soft rejection)
- Proactive inference (acceptance-based + context-based)
- Shown product deduplication

```python
recommender = ProductRecommender(product_service, panchang_service)
products = await recommender.recommend(
    session, message, analysis, turn_topics,
    is_ready_for_wisdom=True, life_domain="spiritual"
)
```

**Tests:** 20 (gatekeeper gates, rejection, acceptance, recommend paths, product maps)

#### After Extraction
| Metric | Before | After |
|--------|--------|-------|
| CompanionEngine | 1,710 lines | 621 lines |
| Product code in engine | ~500 lines | 5 lines (delegation) |
| Memory detection in engine | ~290 lines | 2 lines (delegation) |
| Signal collection in engine | ~30 lines (duplicated) | 1 line (single call) |

**Total Phase 3 tests:** 51

---

### Phase 4: Pydantic Structured Output
**Problem:** Manual `json.loads()` + `.get()` fallback patterns in IntentAgent and RetrievalJudge. Fragile markdown stripping. 30-line balanced-brace JSON scanner.

**Created:** `models/llm_schemas.py` (199 lines)

**Models:**
- `IntentAnalysis` — 11 fields with enum validators for intent/urgency, coercion for emotion/life_domain
- `QueryRewrite` — single `rewritten_query` field
- `GroundingResult` — `grounded` bool + `confidence` float (clamped 0-1) + `issues` string
- `extract_json()` — unified JSON extractor handling clean JSON, markdown blocks, and embedded JSON with proper string escaping

**Integration:**

| File | Before | After |
|------|--------|-------|
| `services/intent_agent.py` | `json.loads(raw_text)` + markdown strip | `extract_json()` + `IntentAnalysis(**parsed)` |
| `services/retrieval_judge.py` | `_parse_json()` 30-line brace scanner | `extract_json()` + `QueryRewriteSchema`/`GroundingResultSchema` |

**Tests added:** 33 (model validation, enum coercion, JSON extraction edge cases)

---

### Phase 5-6: Observability + Integration Tests
**Problem:** No request tracing, no per-service timing, no way to debug slow requests in production. No integration tests verifying extracted services work together.

**Created:** `services/observability.py` (135 lines)

**Features:**
- **Correlation IDs** — `set_correlation_id()` / `get_correlation_id()` via `contextvars.ContextVar` (request-scoped)
- **`@timed` decorator** — async/sync timing with automatic logging
- **`RequestTimings`** — per-stage timing collector with `.summary()` output
- **`CorrelationFilter`** — injects `%(correlation_id)s` into all log records

**Integration tests:** `tests/unit/test_engine_integration.py`
- Multi-turn conversation flow: greeting → emotion → guidance ask
- Signal collection verification through extracted services
- Memory update integration
- Explicit request triggering guidance
- Closure intent handling

**Tests added:** 20 (observability) + 6 (integration)

---

### Phase 7: Wire Observability into Request Path
**Problem:** Observability utilities existed but weren't connected to actual endpoints.

**Changes:**
- `routers/chat.py` — `/conversation` endpoint: `set_correlation_id()` + `REQUEST_START`/`REQUEST_END` timing logs
- `routers/chat.py` — `/conversation/stream` endpoint: `set_correlation_id()` + `STREAM_START` log
- `main.py` — `CorrelationFilter` added to root logger, format includes `[%(correlation_id)s]`

**Log output example:**
```
2025-04-02 10:30:00 - chat - INFO - [a1b2c3d4e5f6] REQUEST_START | session=abc-123 | msg_len=45
2025-04-02 10:30:02 - chat - INFO - [a1b2c3d4e5f6] REQUEST_END | phase=guidance | 2150ms | turn=3
```

**Tests added:** 6

---

### Phase 8: Final Cleanup
- Removed unused `extract_tokens_from_response` import from `companion_engine.py`
- Verified 203 tests pass

---

## Architecture Overview

### Service Dependency Graph (After Refactoring)

```
Frontend (Next.js)
    │
    ▼
FastAPI Routers (chat.py, auth.py, admin.py)
    │  ┌─ set_correlation_id()
    │  └─ REQUEST_START / REQUEST_END timing
    │
    ▼
CompanionEngine (621 lines — thin orchestrator)
    │
    ├── ConversationFSM ◄── pytransitions state machine
    │   └── evaluate(analysis, turn_topics) → (is_ready, trigger)
    │
    ├── MemoryUpdater ◄── keyword-based signal detection
    │   └── update_memory(memory, session, text) → turn_topics
    │
    ├── SignalCollector ◄── intent analysis → session signals
    │   └── collect_signals_from_analysis(session, analysis)
    │
    ├── ProductRecommender ◄── maps + gates + search
    │   └── recommend(session, msg, analysis, ...) → products
    │
    ├── [LLMPort] ◄── Gemini (or mock)
    │   └── generate_response(), generate_response_stream()
    │
    ├── [IntentPort] ◄── IntentAgent (or mock)
    │   └── analyze_intent() → IntentAnalysis (Pydantic validated)
    │
    ├── [RAGPort] ◄── RAGPipeline (or mock)
    │   └── search(), generate_embeddings()
    │
    ├── [MemoryPort] ◄── LongTermMemoryService (or mock)
    │   └── store_memory(), retrieve_relevant_memories()
    │
    └── [ProductPort] ◄── ProductService (or mock)
        └── search_products(), get_recommended_products()
```

### FSM State Diagram

```
                    ┌──────────────┐
          ┌─────── │  LISTENING    │ ◄──────────────┐
          │        └──────┬───────┘                 │
          │               │                         │
          │    evaluate()  │                         │ return_to_listening()
          │               │                         │
          │    ┌──────────┼──────────┐              │
          │    │ explicit? │ ask+turns│ score≥0.7    │
          │    │ request   │ met?     │ +cooldown?   │
          │    │           │          │              │
          │    ▼           ▼          ▼              │
          │   ┌────────────────────────┐            │
          │   │       GUIDANCE         │ ───────────┘
          │   └────────────────────────┘
          │
          │  intent == CLOSURE
          ▼
    ┌──────────────┐
    │   CLOSURE    │
    └──────────────┘
```

### Observability Flow

```
Request arrives
    │
    ├── set_correlation_id() → "a1b2c3d4e5f6"
    ├── log: REQUEST_START | cid=a1b2c3 | session=... | msg_len=...
    │
    ├── [all internal logs include [a1b2c3d4e5f6] prefix]
    │
    ├── FSM: log: FSM session=...: state=GUIDANCE, trigger=explicit_request
    │
    ├── log: REQUEST_END | cid=a1b2c3 | phase=guidance | 2150ms
    │
    ▼
Response sent
```

---

## New Service Map

| Service | File | Lines | Public API | Dependencies | Test File |
|---------|------|-------|-----------|--------------|-----------|
| ConversationFSM | `services/conversation_fsm.py` | 276 | `evaluate(analysis, topics) → (bool, str)` | SessionState, pytransitions | `test_conversation_fsm.py` (26 tests) |
| ProductRecommender | `services/product_recommender.py` | 540 | `recommend(session, msg, analysis, ...) → List[Dict]` | ProductPort, settings | `test_product_recommender.py` (20 tests) |
| MemoryUpdater | `services/memory_updater.py` | 260 | `update_memory(memory, session, text) → List[str]` | SessionState, ConversationMemory | `test_memory_updater.py` (20 tests) |
| SignalCollector | `services/signal_collector.py` | 56 | `collect_signals_from_analysis(session, analysis)` | SessionState | `test_signal_collector.py` (11 tests) |
| Observability | `services/observability.py` | 135 | `set_correlation_id()`, `@timed`, `RequestTimings`, `CorrelationFilter` | contextvars, logging | `test_observability.py` (14 tests) |
| LLM Schemas | `models/llm_schemas.py` | 199 | `IntentAnalysis`, `GroundingResult`, `extract_json()` | pydantic | `test_llm_schemas.py` (24 tests) |

### Port Interfaces

| Port | File | Lines | Protocol Methods |
|------|------|-------|-----------------|
| LLMPort | `ports/llm.py` | 36 | `available`, `generate_response()`, `generate_response_stream()` |
| RAGPort | `ports/rag.py` | 31 | `available`, `search()`, `generate_embeddings()` |
| IntentPort | `ports/intent.py` | 16 | `available`, `analyze_intent()` |
| MemoryPort | `ports/memory.py` | 23 | `store_memory()`, `retrieve_relevant_memories()`, `set_rag_pipeline()` |
| ProductPort | `ports/product.py` | 23 | `search_products()`, `get_recommended_products()` |
| SafetyPort | `ports/safety.py` | 27 | `check_crisis_signals()`, `validate_response()`, `append_professional_help()` |

---

## Testing Guide

### Running Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/unit/ -v          # All 203 tests
python -m pytest tests/unit/ -v -k "fsm" # FSM tests only
python -m pytest tests/unit/ -v -k "product_recommender"  # Product tests
```

### Test File Map

| File | Tests | What It Covers |
|------|-------|---------------|
| `test_smoke.py` | 2 | Pytest infrastructure works (sync + async) |
| `test_no_langchain.py` | 2 | No langchain imports/deps remain |
| `test_async_sleep_fix.py` | 1 | No `time.sleep` in async production code |
| `test_product_service_async.py` | 7 | pymongo calls wrapped with asyncio.to_thread |
| `test_cost_tracker_and_feedback.py` | 5 | Non-blocking MongoDB writes |
| `test_memory_service_async.py` | 3 | numpy ops offloaded to thread pool |
| `test_ports.py` | 25 | Port files exist, have correct methods, use Protocol |
| `test_companion_engine_di.py` | 5 | Constructor accepts DI kwargs, defaults to None |
| `test_mocks_satisfy_protocols.py` | 13 | Mock adapters satisfy port Protocols |
| `test_conversation_fsm.py` | 26 | All FSM transitions, guards, cooldown, distress |
| `test_fsm_integration.py` | 4 | FSM wired into CompanionEngine |
| `test_signal_collector.py` | 11 | Signal extraction from intent analysis |
| `test_memory_updater.py` | 20 | Emotion/domain/intent detection, readiness boosters |
| `test_product_recommender.py` | 20 | Gatekeeper, rejection, acceptance, recommend paths |
| `test_llm_schemas.py` | 24 | Pydantic models, enum coercion, JSON extraction |
| `test_intent_agent_validation.py` | 4 | IntentAgent uses Pydantic validation |
| `test_retrieval_judge_validation.py` | 5 | RetrievalJudge uses extract_json + Pydantic |
| `test_observability.py` | 14 | Correlation IDs, timing, log filter |
| `test_observability_wiring.py` | 6 | Observability wired into chat router + main.py |
| `test_engine_integration.py` | 6 | Full multi-turn conversation with all mocks |

### Writing Tests with Mock Adapters

```python
from tests.unit.mocks import MockLLM, MockIntent, MockMemory, MockProduct

# Create engine with no external services
engine = CompanionEngine(
    rag_pipeline=MockRAG(),
    llm=MockLLM(response="Peace be with you."),
    intent_agent=MockIntent(analysis={"intent": "GREETING", ...}),
    memory_service=MockMemory(),
    product_service=MockProduct(products=[{"name": "Mala"}]),
    panchang=MagicMock(),
    model_router=MockModelRouter(),
)

# Run conversation
session = SessionState()
async for chunk in engine.generate_response_stream(session, "Hello"):
    print(chunk)
```

---

## Developer Guide

### Adding a New Port/Adapter

1. Create `ports/new_service.py`:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class NewServicePort(Protocol):
    async def do_something(self, input: str) -> str: ...
```

2. Add to `ports/__init__.py`
3. Create mock in `tests/unit/mocks.py`
4. Add as kwarg to `CompanionEngine.__init__`
5. Write tests

### Adding a New FSM State/Transition

Edit `services/conversation_fsm.py`:

```python
# Add state
states = ["LISTENING", "GUIDANCE", "CLOSURE", "NEW_STATE"]

# Add transition
self.machine.add_transition(
    trigger="step",
    source="LISTENING",
    dest="NEW_STATE",
    conditions=["my_guard_condition"],
    before="set_trigger_new_state",
)

# Add guard
def my_guard_condition(self, event=None) -> bool:
    return self._analysis.get("some_field") == "some_value"
```

Test in `tests/unit/test_conversation_fsm.py`.

### Adding a New Extracted Service

1. Create `services/new_service.py` with a pure function or class
2. Write tests in `tests/unit/test_new_service.py` (load via `importlib.util` to avoid `services/__init__.py` chain)
3. Import in `companion_engine.py` and delegate
4. Run full suite: `python -m pytest tests/unit/ -v`

---

## Migration Notes

### What Was Removed

| Item | Location | Replacement |
|------|----------|-------------|
| `langchain`, `langchain-community` | `requirements.txt` | Removed (zero imports) |
| `_assess_readiness()` (87 lines) | `companion_engine.py` | `ConversationFSM.evaluate()` |
| `_update_memory()` (290 lines) | `companion_engine.py` | `memory_updater.update_memory()` |
| 5 product maps (144 lines) | `companion_engine.py` | `product_recommender.py` module-level constants |
| 12 product methods (~350 lines) | `companion_engine.py` | `ProductRecommender` class |
| Duplicated signal blocks (2x ~15 lines) | `companion_engine.py` | `signal_collector.collect_signals_from_analysis()` |
| `_parse_json()` balanced-brace scanner | `retrieval_judge.py` | `llm_schemas.extract_json()` |
| Manual JSON parsing in IntentAgent | `intent_agent.py` | `IntentAnalysis(**parsed)` |

### What Was Renamed

| Old | New |
|-----|-----|
| `self._should_suppress_products()` | `product_recommender._should_suppress()` |
| `self._detect_product_rejection()` | `product_recommender._detect_product_rejection()` |
| `self._infer_proactive_products()` | `product_recommender._infer_proactive()` |
| `self._filter_shown_products()` | `product_recommender._filter_shown()` |
| `self._record_shown_products()` | `product_recommender._record_shown()` |

### Backwards Compatibility

- **CompanionEngine constructor:** All new kwargs default to `None` → falls back to singleton factories
- **`record_suggestion()`:** Thin delegate on CompanionEngine → `self.product_recommender.record_suggestion()`
- **API contract:** Zero changes to request/response schemas
- **Frontend:** No changes needed
- **Docker:** No changes to Dockerfile or docker-compose.yml
- **Environment variables:** No changes

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `transitions` | 0.9.3 | pytransitions FSM library |

### Dependencies Removed

| Package | Reason |
|---------|--------|
| `langchain` | Zero imports across 106 Python files |
| `langchain-community` | Zero imports across 106 Python files |
