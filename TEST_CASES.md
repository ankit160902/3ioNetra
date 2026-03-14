# 3ioNetra Spiritual Companion — Comprehensive Test Cases

> **Version:** 1.1.3 | **Total Test Cases:** 219 | **Segments:** 20
> **Priority Breakdown:** P0 (54) — Release Blockers | P1 (103) — Important | P2 (62) — Nice-to-have
> **Last Updated:** 2026-03-13

---

## Table of Contents

| # | Segment | ID Prefix | Count |
|---|---------|-----------|-------|
| 1 | [Authentication](#1-authentication-auth) | AUTH | 18 |
| 2 | [Session Management](#2-session-management-ses) | SES | 11 |
| 3 | [Conversation Flow](#3-conversation-flow-flow) | FLOW | 11 |
| 4 | [Intent Classification](#4-intent-classification-intent) | INTENT | 17 |
| 5 | [RAG Pipeline](#5-rag-pipeline-rag) | RAG | 10 |
| 6 | [Context Validation](#6-context-validation-ctxv) | CTXV | 9 |
| 7 | [LLM Integration](#7-llm-integration-llm) | LLM | 9 |
| 8 | [Safety & Crisis](#8-safety--crisis-safe) | SAFE | 16 |
| 9 | [Product Recommendations](#9-product-recommendations-prod) | PROD | 10 |
| 10 | [TTS](#10-text-to-speech-tts) | TTS | 7 |
| 11 | [Panchang](#11-panchang-panch) | PANCH | 4 |
| 12 | [Memory Service](#12-memory-service-mem) | MEM | 6 |
| 13 | [Frontend UI](#13-frontend-ui-ui) | UI | 32 |
| 14 | [Streaming & Typewriter](#14-streaming--typewriter-strm) | STRM | 9 |
| 15 | [Conversation History](#15-conversation-history-hist) | HIST | 10 |
| 16 | [Feedback](#16-feedback-fb) | FB | 5 |
| 17 | [Deployment](#17-deployment-deploy) | DEPLOY | 9 |
| 18 | [Data Ingestion](#18-data-ingestion-ingest) | INGEST | 6 |
| 19 | [Performance](#19-performance-perf) | PERF | 5 |
| 20 | [Edge Cases & Regression](#20-edge-cases--regression-edge) | EDGE | 15 |

---

## 1. Authentication (AUTH)

### Registration — Step 1 (Basic Info)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| AUTH-01 | Register with valid data — Step 1 | Verify Step 1 fields (name, email, password, confirm) validate and advance to Step 2 | App loaded, on login page | 1. Click "Create Account" link. 2. Enter name "Test User". 3. Enter email "test@example.com". 4. Enter password "Test1234". 5. Enter confirm password "Test1234". 6. Click "Next Step". | Form advances to Step 2 (phone, gender, DOB, profession fields appear). Progress indicator shows dot 2 active. | P0 | Functional |
| AUTH-02 | Step 1 — empty name rejected | Name field must not be blank | Register mode active, Step 1 | 1. Leave name empty. 2. Fill email, password, confirm. 3. Click "Next Step". | Red error banner: "Please enter your name". Form stays on Step 1. | P1 | Validation |
| AUTH-03 | Step 1 — invalid email rejected | Email must contain "@" | Register mode, Step 1 | 1. Enter name. 2. Enter email "notanemail". 3. Fill password fields. 4. Click "Next Step". | Error: "Please enter a valid email address". | P1 | Validation |
| AUTH-04 | Step 1 — password < 6 chars rejected | Minimum password length is 6 | Register mode, Step 1 | 1. Enter name, valid email. 2. Enter password "abc". 3. Confirm "abc". 4. Click "Next Step". | Error: "Password must be at least 6 characters". | P0 | Validation |
| AUTH-05 | Step 1 — password mismatch rejected | Confirm password must match | Register mode, Step 1 | 1. Enter password "Test1234". 2. Enter confirm "DifferentPass". 3. Click "Next Step". | Error: "Passwords do not match". | P0 | Validation |

### Registration — Step 2 (Profile)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| AUTH-06 | Register with valid data — Step 2 | Complete registration with all profile fields | Step 1 completed | 1. Enter phone "9876543210". 2. Select gender "Male". 3. Enter DOB "1995-06-15". 4. Select profession "Working Professional". 5. Click "Create Account". | POST `/api/auth/register` returns 200. Response contains `token` and `user` object with id, name, email, phone, gender, age, age_group, profession. User is logged in and redirected to chat UI. `auth_token` and `auth_user` saved in localStorage. | P0 | Functional |
| AUTH-07 | Step 2 — phone < 10 digits rejected | Phone must be at least 10 digits | Step 1 done | 1. Enter phone "12345". 2. Fill other fields. 3. Click "Create Account". | Error: "Please enter a valid phone number". | P1 | Validation |
| AUTH-08 | Step 2 — gender not selected | Gender dropdown required | Step 1 done | 1. Leave gender as "Select Gender". 2. Fill other fields. 3. Click "Create Account". | Error: "Please select your gender". | P1 | Validation |
| AUTH-09 | Step 2 — DOB not entered | Date of birth required | Step 1 done | 1. Leave DOB empty. 2. Fill other fields. 3. Click "Create Account". | Error: "Please enter your date of birth". | P1 | Validation |
| AUTH-10 | Step 2 — profession not selected | Profession dropdown required | Step 1 done | 1. Leave profession as "Select Profession". 2. Fill other fields. 3. Click "Create Account". | Error: "Please select your profession". | P1 | Validation |
| AUTH-11 | Step 2 — DOB age gate (< 13 years) | DOB picker max date is today - 13 years | Step 1 done | 1. Try to select a DOB within the last 13 years. | Date input `max` attribute prevents selecting a date less than 13 years ago. | P2 | Validation |
| AUTH-12 | Duplicate email registration | Backend rejects already-registered emails | App on register page | 1. Register with "existing@email.com" (already in DB). 2. Complete both steps. | Backend returns 400. Frontend shows error: "Email already registered or database unavailable". | P0 | Negative |
| AUTH-13 | Step 2 — Back button returns to Step 1 | "Back" button on Step 2 returns to Step 1 with fields preserved | Step 2 active | 1. Click "Back" button. | Form returns to Step 1. Name, email, password fields retain their values. | P2 | UX |

### Login

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| AUTH-14 | Login with valid credentials | Successful login returns token and user | User exists in DB | 1. Enter valid email. 2. Enter correct password. 3. Click "Sign In". | POST `/api/auth/login` returns 200 with `{user, token}`. `auth_token` and `auth_user` stored in localStorage. Chat UI loads. | P0 | Functional |
| AUTH-15 | Login with wrong password | Backend returns 401 for bad credentials | User exists | 1. Enter correct email. 2. Enter wrong password. 3. Click "Sign In". | 401 response. Error banner: "Invalid email or password". | P0 | Negative |
| AUTH-16 | Login with non-existent email | Email not found returns 401 | No user with that email | 1. Enter "nobody@test.com". 2. Enter any password. 3. Click "Sign In". | 401 response. Error displayed. | P1 | Negative |

### Token & Logout

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| AUTH-17 | Token verification on page load | Stored token is verified via GET `/api/auth/verify` | User previously logged in, token in localStorage | 1. Refresh the page. | Frontend calls `/api/auth/verify` with Bearer header. On 200: user stays logged in with latest user data. On 401: localStorage cleared, login page shown. On 5xx/network error: user stays logged in using cached data (graceful degradation). | P0 | Functional |
| AUTH-18 | Logout clears state | Logout removes token and shows login page | User logged in | 1. Click "Sign Out" in sidebar. | POST `/api/auth/logout` called. `auth_token` and `auth_user` removed from localStorage. Login page shown. | P0 | Functional |

---

## 2. Session Management (SES)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| SES-01 | Create new session | POST `/api/session/create` returns UUID and welcome message | Backend running, RAG ready | 1. POST `/api/session/create`. | 200 response with `session_id` (UUID format), `phase: "listening"`, `message` containing welcome text starting with "Namaste". | P0 | API |
| SES-02 | Get session state | GET `/api/session/{id}` returns current state | Session SES-01 exists | 1. GET `/api/session/{session_id}`. | 200 with `session_id`, `phase`, `turn_count`, `signals_collected` (dict), `created_at` (ISO string). | P0 | API |
| SES-03 | Get non-existent session | GET with invalid UUID returns 404 | Backend running | 1. GET `/api/session/00000000-0000-0000-0000-000000000000`. | 404 "Session not found". | P1 | Negative |
| SES-04 | Delete session | DELETE `/api/session/{id}` removes session | Session exists | 1. DELETE `/api/session/{session_id}`. 2. GET the same session. | DELETE returns `{"message": "Session deleted"}`. Subsequent GET returns 404. | P1 | API |
| SES-05 | Session TTL expiry | Sessions expire after `SESSION_TTL_MINUTES` (60 min default) | Redis or Mongo session backend | 1. Create session. 2. Wait > 60 minutes (or manually set TTL to 1 min for test). 3. GET session. | Session returns null/404 — TTL has expired. | P1 | Functional |
| SES-06 | Session activity refresh | Accessing a session refreshes its `last_activity` timestamp | Active session | 1. Create session. 2. Wait 30 minutes. 3. Send a message. 4. Wait 45 minutes. 5. GET session. | Session is still alive (total elapsed > 60 min but activity refreshed the TTL window). | P2 | Functional |
| SES-07 | Redis session backend | RedisSessionManager stores sessions as JSON with TTL via SETEX | Redis available, `REDIS_HOST` configured | 1. Start app with Redis. 2. Create session. 3. Check Redis key `session:{uuid}`. | Redis key exists with JSON data and TTL matching `SESSION_TTL_MINUTES * 60`. | P1 | Integration |
| SES-08 | MongoDB fallback | MongoSessionManager used when Redis is unavailable | Redis offline, MongoDB configured | 1. Stop Redis. 2. Restart backend. 3. Check logs. 4. Create session. | Logs show "Redis initialization failed" then "Using MongoDB session storage". Session operations work normally. MongoDB `sessions` collection has TTL index on `last_activity`. | P1 | Integration |
| SES-09 | InMemory fallback | InMemorySessionManager used when both Redis and MongoDB are unavailable | Redis and MongoDB offline | 1. Stop Redis and MongoDB. 2. Restart backend. 3. Create session. | Logs show "Using in-memory session storage". Sessions work but are lost on restart. | P2 | Integration |
| SES-10 | Session isolation between users | User A cannot access User B's session | Two authenticated users | 1. User A creates a session and sends messages. 2. User B sends a message with User A's session_id and their own auth token. | Backend detects `session.memory.user_id != user['id']` and creates a new session for User B instead of using User A's session. | P0 | Security |
| SES-11 | Session ID persisted in localStorage | Frontend saves `spiritual_session_id` to localStorage | User sends first message | 1. Send a message. 2. Check `localStorage.getItem('spiritual_session_id')`. | Value matches the `session_id` from the API response. On page refresh, the same session_id is reused. | P1 | Frontend |

---

## 3. Conversation Flow (FLOW)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| FLOW-01 | Initial phase is LISTENING | New session starts in listening phase | Fresh session | 1. Create session. 2. Check phase. | `phase` is `"listening"`. | P0 | Functional |
| FLOW-02 | Greeting message stays in LISTENING | Trivial messages (hi, hello, namaste) don't trigger guidance | Active session | 1. Send "Namaste". | Response phase is `"listening"`. `is_complete` is false. Bot replies with a warm greeting and invites sharing. | P0 | Functional |
| FLOW-03 | Transition to GUIDANCE — direct ask | A direct question with `needs_direct_answer=True` triggers immediate guidance | Active session, turn_count >= 1 | 1. Send "Hi". 2. Send "How should I start my meditation practice?". | Second response has `phase: "guidance"`, `is_complete: true`. Response includes scripture, practices. `flow_metadata.readiness_score` resets to 0.3 after guidance. | P0 | Functional |
| FLOW-04 | Transition to GUIDANCE — signal threshold | Enough emotional signals collected trigger guidance | Session with `min_signals: 2`, `min_turns: 1` | 1. Send an emotional message with life domain: "I'm very anxious about losing my job and my family is suffering". | Intent agent detects emotion (anxiety), life_domain (career/family), urgency. With enough signals and turns met, phase transitions to `"guidance"`. | P0 | Functional |
| FLOW-05 | Force transition at max turns | After `MAX_CLARIFICATION_TURNS` (4), guidance is forced | Session at turn 3, no guidance given yet | 1. Send 4 messages that are emotional but vague. | By turn 4, `should_force_transition()` returns True. Response includes guidance with scriptures. | P1 | Functional |
| FLOW-06 | Oscillation control — cooldown after guidance | At least 2 turns of listening must pass before next guidance | Guidance was given on turn N | 1. Receive guidance on turn 3. 2. Send follow-up on turn 4. 3. Send another on turn 5. | Turns 4 and 5 stay in `"listening"` phase (cooldown). Turn 6+ may transition to guidance again if signals warrant. `last_guidance_turn` is checked: `turn_count - last_guidance_turn < 2` prevents transition. | P1 | Functional |
| FLOW-07 | CLOSURE intent detection | User saying "bye" or "thank you" triggers closure handling | Active session with history | 1. Have a multi-turn conversation. 2. Send "Thank you, bye". | Intent classified as `CLOSURE`. Bot gives a warm closure with blessing. Phase may shift to `"closure"`. | P1 | Functional |
| FLOW-08 | Memory readiness threshold (0.7) | `readiness_for_wisdom >= 0.7` triggers guidance | Session with memory context | 1. Build memory through multi-turn conversation until `readiness_for_wisdom` reaches 0.7. | `is_ready_for_transition()` returns True. Guidance phase is entered. | P2 | Functional |
| FLOW-09 | PANCHANG intent triggers direct answer | Asking about panchang bypasses listening | Active session | 1. Send "What is today's panchang?". | Intent classified as `ASKING_PANCHANG`. Response includes panchang data (tithi, nakshatra). Phase is `"guidance"` with `is_complete: true`. | P1 | Functional |
| FLOW-10 | PRODUCT_SEARCH intent triggers product response | Explicit buy/shop request returns products | Active session, products in DB | 1. Send "I want to buy a Rudraksha mala". | Intent classified as `PRODUCT_SEARCH`. Response includes `recommended_products` array. `flow_metadata.detected_domain` reflects the context. | P1 | Functional |
| FLOW-11 | Speculative RAG skip for trivial messages | Short/trivial messages skip parallel RAG fetch | Active session | 1. Send "ok". | Message is in `TRIVIAL_MESSAGES` frozenset. No RAG search is performed (saves latency). Engine processes message without speculative docs. | P2 | Performance |

---

## 4. Intent Classification (INTENT)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| INTENT-01 | GREETING intent | Obvious greeting detected | LLM available | 1. Call `analyze_intent("Namaste")`. | Fast-path returns `{intent: "GREETING", emotion: "neutral", needs_direct_answer: false}` without LLM call. | P0 | Functional |
| INTENT-02 | SEEKING_GUIDANCE intent | Advice request detected | LLM available | 1. Call `analyze_intent("How should I deal with my anger issues?")`. | Returns `{intent: "SEEKING_GUIDANCE", emotion: "anger", life_domain: "health" or "spiritual", needs_direct_answer: true}`. | P0 | Functional |
| INTENT-03 | EXPRESSING_EMOTION intent | Emotional venting detected | LLM available | 1. Call `analyze_intent("I feel so lost and alone, nothing makes sense anymore")`. | Returns `{intent: "EXPRESSING_EMOTION", emotion: "hopelessness" or "sadness", needs_direct_answer: false}`. | P0 | Functional |
| INTENT-04 | ASKING_INFO intent | Factual question detected | LLM available | 1. Call `analyze_intent("What is the meaning of Om?")`. | Returns `{intent: "ASKING_INFO", needs_direct_answer: true}`. | P1 | Functional |
| INTENT-05 | ASKING_PANCHANG intent | Panchang query detected | LLM available | 1. Call `analyze_intent("What is today's tithi and nakshatra?")`. | Returns `{intent: "ASKING_PANCHANG"}`. | P1 | Functional |
| INTENT-06 | PRODUCT_SEARCH intent | Explicit purchase request | LLM available | 1. Call `analyze_intent("I want to buy a brass Ganesh murti")`. | Returns `{intent: "PRODUCT_SEARCH", recommend_products: true, product_search_keywords: ["brass", "Ganesh", "murti"]}`. | P1 | Functional |
| INTENT-07 | CLOSURE intent | Session ending detected | LLM available | 1. Call `analyze_intent("Thank you for everything, goodbye")`. | Returns `{intent: "CLOSURE"}`. | P1 | Functional |
| INTENT-08 | OTHER intent | Ambiguous message | LLM available | 1. Call `analyze_intent("hmm interesting")`. | Returns `{intent: "OTHER"}`. | P2 | Functional |
| INTENT-09 | Life domain — career | Career-related concern detected | LLM available | 1. Call `analyze_intent("My boss is very toxic and I want to quit my job")`. | Returns `life_domain: "career"`. | P1 | Functional |
| INTENT-10 | Life domain — family | Family concern detected | LLM available | 1. Call `analyze_intent("My parents don't understand me and we fight every day")`. | Returns `life_domain: "family"`. | P1 | Functional |
| INTENT-11 | Life domain — relationships | Relationship concern detected | LLM available | 1. Call `analyze_intent("My partner and I are growing apart")`. | Returns `life_domain: "relationships"`. | P1 | Functional |
| INTENT-12 | Life domain — health | Health concern detected | LLM available | 1. Call `analyze_intent("I can't sleep at night and feel fatigued all day")`. | Returns `life_domain: "health"`. | P1 | Functional |
| INTENT-13 | Entity extraction | Entities (deity, ritual, item) extracted | LLM available | 1. Call `analyze_intent("I want to do Satyanarayan Puja for Lord Vishnu")`. | Returns `entities: {deity: "Vishnu", ritual: "Satyanarayan Puja"}` or similar. | P1 | Functional |
| INTENT-14 | Urgency detection — crisis | Crisis urgency flagged | LLM available | 1. Call `analyze_intent("I don't want to live anymore")`. | Returns `urgency: "crisis"`. | P0 | Functional |
| INTENT-15 | Product keywords — contextual resolution | Product keywords resolved from context | LLM available, puja context | 1. Call `analyze_intent("What essentials do I need?")` with context "User is asking about Satyanarayan Puja". | Returns `product_search_keywords: ["Satyanarayan", "puja samagri", "ghee"]` or similar contextual resolution. | P2 | Functional |
| INTENT-16 | recommend_products=false for emotional venting | No products for pure grief | LLM available | 1. Call `analyze_intent("I lost my mother last week and I'm devastated")`. | Returns `recommend_products: false, product_search_keywords: []`. | P0 | Functional |
| INTENT-17 | Fallback analysis — LLM unavailable | Keyword-based fallback when Gemini is down | LLM service unavailable (`available=false`) | 1. Set LLM unavailable. 2. Call `analyze_intent("How can I find peace?")`. | Returns `{intent: "SEEKING_GUIDANCE"}` via keyword match ("how" present). `needs_direct_answer: true` (question mark present). | P1 | Resilience |

---

## 5. RAG Pipeline (RAG)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| RAG-01 | Hybrid search returns results | Semantic (70%) + BM25 (30%) search returns ranked docs | RAG pipeline initialized, embeddings loaded | 1. Call `rag_pipeline.search(query="What does Bhagavad Gita say about duty?", top_k=5)`. | Returns list of up to 5 docs, each with `scripture`, `reference`, `text`, `meaning`, `score`, `final_score`. Scores are > `MIN_SIMILARITY_SCORE` (0.15). | P0 | Functional |
| RAG-02 | Query expansion for short queries | Queries < 4 words get LLM-generated alternative search terms | RAG pipeline ready, LLM available | 1. Call `rag_pipeline.search(query="karma meaning")`. | Query expansion generates 2 alternative search terms. All 3 queries (original + 2 alternatives) are searched. Results are merged and deduplicated. | P1 | Functional |
| RAG-03 | Neural reranking (CrossEncoder) | CrossEncoder reranks initial results by relevance | RAG initialized with CrossEncoder model | 1. Perform search. 2. Check `rerank_score` on returned docs. | Docs have `rerank_score` from `ms-marco-MiniLM-L-6-v2`. Final ordering uses `final_score` which combines semantic, BM25, and rerank scores. | P1 | Functional |
| RAG-04 | Min similarity threshold filtering | Docs below `MIN_SIMILARITY_SCORE` (0.15) are dropped | RAG initialized | 1. Search for a very obscure/unrelated query like "quantum physics dark matter". | Results list is empty or contains only docs with `score >= 0.15`. Low-relevance noise is filtered out. | P0 | Functional |
| RAG-05 | Scripture filter | Search filtered to specific scripture(s) | RAG initialized | 1. Call `rag_pipeline.search(query="duty", scripture_filter="Bhagavad Gita")`. | All returned docs have `scripture: "Bhagavad Gita"` (case-insensitive match). | P1 | Functional |
| RAG-06 | Redis caching for RAG queries | Identical queries return cached results within TTL | RAG + Redis available | 1. Call `rag_pipeline.query(query="What is dharma?")`. 2. Call same query again within 1 hour. | Second call returns from Redis cache (faster response, no embedding computation). Cache key is MD5 hash of query params. TTL is 1 hour. | P2 | Performance |
| RAG-07 | Memory-mapped embeddings (mmap) | Embeddings loaded via `np.load(mmap_mode='r')` to prevent OOM | `embeddings.npy` exists in `data/processed/` | 1. Start backend. 2. Check memory usage. | Embeddings are memory-mapped, not loaded into RAM entirely. Backend starts without OOM even on constrained instances (< 1 GB RAM). Logs show successful mmap initialization. | P1 | Performance |
| RAG-08 | RAG pipeline unavailable handling | Conversation endpoint returns 500 if RAG not ready | RAG pipeline failed to initialize | 1. POST `/api/conversation` with valid message. | 500 response: "RAG pipeline not available". | P0 | Negative |
| RAG-09 | Standalone text query endpoint | POST `/api/text/query` returns answer with citations | RAG initialized | 1. POST `/api/text/query` with `{query: "What is karma?", language: "en", include_citations: true}`. | Response contains `answer` (string), `citations` (list of dicts with scripture, reference, text, score), `language: "en"`, `confidence` (float). | P1 | API |
| RAG-10 | Doc-type filter in search | Temple/spatial docs excluded for emotional queries | RAG initialized, docs include temple type | 1. Search with emotional context: query="I feel sad", intent=EXPRESSING_EMOTION. | Temple-type docs with spatial markers (address, road, located) are excluded from results unless `temple_interest=true`. | P2 | Functional |

---

## 6. Context Validation (CTXV)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| CTXV-01 | Gate 1 — Relevance | Docs below min_score (0.12) are dropped | ContextValidator instantiated | 1. Pass docs with scores [0.08, 0.15, 0.25, 0.05] and `min_score=0.12`. | Only docs with scores 0.15 and 0.25 survive. 2 docs dropped. | P0 | Unit |
| CTXV-02 | Gate 2 — Content quality | Docs with empty/placeholder/short text removed | ContextValidator ready | 1. Pass docs where text is "intermediate", "", or "abc" (< 20 chars). | All placeholder/short docs removed. Only docs with `len(text) >= 20` and text not in `_CONTENT_PLACEHOLDERS` survive. | P1 | Unit |
| CTXV-03 | Gate 3 — Type appropriateness (emotional) | Temple/spatial docs excluded for emotional intents | ContextValidator ready | 1. Pass docs with `type: "temple"` and intent=`EXPRESSING_EMOTION`, `temple_interest=False`. | Temple docs are deferred (pushed to end of list), not dropped. | P1 | Unit |
| CTXV-04 | Gate 3 — Type appropriateness (how-to) | Procedural docs boosted for guidance intents | ContextValidator ready | 1. Pass docs with `type: "procedural"` and intent=`SEEKING_GUIDANCE`. | Procedural docs are inserted at front of the list (boosted). | P2 | Unit |
| CTXV-05 | Gate 4 — Scripture allowlist (match) | Only allowed scriptures pass | ContextValidator ready | 1. Pass docs from ["Bhagavad Gita", "Ramayana", "Upanishads"] with `allowed_scriptures=["Bhagavad Gita"]`. | Only "Bhagavad Gita" docs remain. Others are dropped. | P1 | Unit |
| CTXV-06 | Gate 4 — Scripture allowlist (graceful fallback) | If allowlist filters everything, all docs returned | ContextValidator ready | 1. Pass docs from ["Ramayana"] with `allowed_scriptures=["Vedas"]`. | No match found. All original docs are returned as fallback (never returns empty). Warning logged. | P0 | Unit |
| CTXV-07 | Gate 5 — Diversity | Max N docs per source | ContextValidator ready | 1. Pass 5 docs all from "Bhagavad Gita" with `max_per_source=2`. | Only 2 "Bhagavad Gita" docs kept. 3 dropped. Prevents echo-chamber RAG. | P1 | Unit |
| CTXV-08 | Full pipeline — 5 gates sequential | All 5 gates applied in order with final `max_docs` cap | ContextValidator ready | 1. Pass 20 docs with mixed scores, types, scriptures. `min_score=0.12`, `max_per_source=2`, `max_docs=5`. | Output has at most 5 docs. All pass relevance, content, type, scripture, and diversity gates. Logs show "ContextValidator: 20 → N docs". | P0 | Integration |
| CTXV-09 | Empty input returns empty | No docs in means no docs out | ContextValidator ready | 1. Call `validator.validate(docs=[])`. | Returns `[]` immediately without error. | P2 | Edge |

---

## 7. LLM Integration (LLM)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| LLM-01 | Gemini API call succeeds | LLMService generates response via Gemini 2.5 Pro | `GEMINI_API_KEY` set, circuit breaker closed | 1. Call `llm.generate_response(query, context_docs, conversation_history, phase=GUIDANCE)`. | Response is a non-empty string. No markdown bullets/headers. Response length 30-100 words. Contains relevant spiritual guidance. | P0 | Functional |
| LLM-02 | Circuit breaker — CLOSED to OPEN | 3 consecutive failures trip the circuit | CircuitBreaker with `failure_threshold=3` | 1. Force 3 consecutive Gemini API failures (e.g., invalid key). | After 3rd failure: state transitions to OPEN. Logs "Circuit {name} TRIPPED to OPEN state". Subsequent calls raise `RuntimeError("Circuit is currently open")` immediately without calling Gemini. | P0 | Resilience |
| LLM-03 | Circuit breaker — OPEN to HALF_OPEN | After `recovery_timeout` (60s), circuit moves to HALF_OPEN | Circuit in OPEN state | 1. Wait > 60 seconds after circuit opened. 2. Make a call. | State transitions to HALF_OPEN. Call is attempted. On success: state returns to CLOSED. On failure: state returns to OPEN. | P1 | Resilience |
| LLM-04 | Streaming response (SSE tokens) | `generate_response_stream` yields tokens | Gemini available | 1. Call streaming endpoint. | Yields individual text tokens via async generator. Each token is a small string fragment. When concatenated, forms a complete response. | P0 | Functional |
| LLM-05 | Response format — no markdown | LLM output contains no bullet points, headers, or numbered lists | Guidance phase response | 1. Get a guidance response. 2. Check for `#`, `*`, `-`, `1.` patterns. | Response is flowing prose only. No markdown formatting. Verse tags use `[VERSE]...[/VERSE]` format only. | P1 | Compliance |
| LLM-06 | Verse tag format | Sanskrit/Hindi verses wrapped in `[VERSE]...[/VERSE]` tags | Guidance response with scripture | 1. Get guidance response that includes a verse. | Original Sanskrit/Hindi text is enclosed in `[VERSE]...[/VERSE]` tags. Maximum one verse per response. | P1 | Compliance |
| LLM-07 | Fast model for intent classification | Intent analysis uses `gemini-2.0-flash` (not 2.5-pro) | Gemini available | 1. Send a message. 2. Check logs for intent analysis model. | IntentAgent uses `settings.GEMINI_FAST_MODEL` ("gemini-2.0-flash"). Response MIME type is `application/json`. | P2 | Performance |
| LLM-08 | LLM unavailable fallback | Companion engine handles LLM being down | `llm.available = false` | 1. Disable Gemini. 2. Send a message via streaming endpoint. | Fallback text returned: "I'm here with you. Could you tell me a little more about what feels most heavy right now?" | P0 | Resilience |
| LLM-09 | clean_response post-processing | `clean_response()` strips unwanted artifacts from LLM output | Response generated | 1. LLM returns response with artifacts. 2. `clean_response()` is called. | Output is cleaned of any raw markdown, excessive whitespace, or formatting artifacts before being sent to the user. | P2 | Functional |

---

## 8. Safety & Crisis (SAFE)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| SAFE-01 | Crisis keyword — "kill myself" | Direct crisis keyword triggers safety response | Crisis detection enabled | 1. Send message: "I want to kill myself". | `check_crisis_signals` returns `(True, crisis_response)`. Response contains iCall (9152987821), Vandrevala (1860-2662-345), NIMHANS (080-46110007). Response includes breathing exercise. No scripture/guidance given. | P0 | Safety |
| SAFE-02 | Crisis keyword — "end my life" | Variant crisis phrase detected | Crisis detection enabled | 1. Send "I want to end my life". | Crisis detected. Same safety response with helpline numbers. | P0 | Safety |
| SAFE-03 | Crisis keyword — "no point living" | Hopelessness phrase detected | Crisis detection enabled | 1. Send "There is no point living anymore". | Crisis detected. Safety response returned. | P0 | Safety |
| SAFE-04 | Crisis keyword — case insensitive | Keywords match regardless of case | Crisis detection enabled | 1. Send "I WANT TO DIE". | `message.lower()` matching catches "want to die". Crisis response returned. | P0 | Safety |
| SAFE-05 | Crisis in conversation history | Past crisis keyword re-triggers safety | Session with history containing crisis keyword | 1. Send normal message, but session history contains a previous "I want to die" message. | `check_crisis_signals` scans history and finds the keyword. Crisis mode remains active. | P1 | Safety |
| SAFE-06 | Severity signal — crisis level | Severity=crisis in signals triggers crisis response | Session with severity signal | 1. Session has `signals_collected[SEVERITY] = Signal(value="crisis")`. 2. Send any message. | Crisis detected via signal check. Safety response returned. | P1 | Safety |
| SAFE-07 | Hopelessness + severe combination | Combined emotion+severity triggers crisis | Session with hopelessness emotion and severe severity | 1. Session has `emotion="hopelessness"` and `severity="severe"`. 2. Send any message. | Combination detected. Crisis response triggered. | P1 | Safety |
| SAFE-08 | Addiction keyword — professional help | Addiction mention appends specialized resources | Crisis detection enabled | 1. Send "I'm addicted to alcohol and can't stop drinking". | `check_needs_professional_help` returns `(True, "addiction")`. Response includes addiction resources: TTK Kolkata (033-22802080), NIMHANS Addiction (080-26995000), AA India (9000099100), NA India (9323010011). | P0 | Safety |
| SAFE-09 | Severe mental health — professional help | Mental health keyword triggers resource append | Crisis detection enabled | 1. Send "I've been diagnosed with severe depression and having panic attacks". | Returns `(True, "mental_health")`. Mental health resources appended: iCall, Vandrevala, NIMHANS. | P0 | Safety |
| SAFE-10 | Professional help — no repeat | Resources not repeated if already shown in session | Session where resources were already appended | 1. Set `already_mentioned=True`. 2. Call `append_professional_help(response, "addiction", True)`. | Original response returned unchanged (no resources appended). | P2 | Functional |
| SAFE-11 | Banned pattern — "just be positive" | Harmful phrase replaced in LLM output | Generated response contains "just be positive" | 1. Pass response text containing "just be positive" to `validate_response()`. | Phrase replaced with "be gentle with yourself". Warning logged. | P0 | Safety |
| SAFE-12 | Banned pattern — "karma from past life" | Harmful spiritual phrase replaced | Response contains "karma from past life" | 1. Pass response to `validate_response()`. | Replaced with "a challenging situation". | P0 | Safety |
| SAFE-13 | Banned pattern — "everything happens for a reason" | Dismissive phrase replaced | Response contains the phrase | 1. Pass to `validate_response()`. | Replaced with "this is part of your journey". | P1 | Safety |
| SAFE-14 | Reduce scripture density for distress | High-distress emotions reduce scripture references | Session with emotion=hopelessness | 1. Call `should_reduce_scripture_density(session)` with `emotion.value="hopelessness"`. | Returns `True`. LLM prompt includes `reduce_scripture=True`, resulting in more direct comfort and fewer verse references. | P1 | Functional |
| SAFE-15 | False positive — "kill" in non-crisis context | "Kill" in gaming/cooking context should NOT trigger crisis | Crisis detection enabled | 1. Send "I need to kill the weeds in my garden". | None of the `CRISIS_KEYWORDS` match (they require multi-word phrases like "kill myself", not standalone "kill"). `check_crisis_signals` returns `(False, None)`. | P0 | Safety |
| SAFE-16 | Crisis detection disabled | Setting `ENABLE_CRISIS_DETECTION=false` skips all checks | Config override | 1. Set `enable_crisis_detection=False`. 2. Send "I want to kill myself". | `check_crisis_signals` returns `(False, None)` immediately. No safety response. (Used for testing environments only.) | P2 | Config |

---

## 9. Product Recommendations (PROD)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| PROD-01 | Product search by keyword | `search_products` finds products matching keywords | Products seeded in MongoDB `products` collection | 1. Call `search_products(query_text="Rudraksha mala")`. | Returns products where name, category, or description match "rudraksha" or "mala" (regex OR). Results sorted by relevance score. Name matches weighted 15x, category 5x, description 1x. | P0 | Functional |
| PROD-02 | Life domain category boosting | Products in domain-relevant categories boosted | Products in DB, spiritual domain | 1. Call `search_products(query_text="puja items", life_domain="spiritual")`. | Products in categories "Pooja Essential", "Spiritual Home", "Pooja Murti", "Seva" get +25 score boost. These appear higher in results. | P1 | Functional |
| PROD-03 | Deity name boost | Products matching user's deity ranked higher | Products with deity names in DB | 1. Call `search_products(query_text="murti", deity="Ganesh")`. | Products with "Ganesh" in name get +30 boost, in description get +10 boost. | P1 | Functional |
| PROD-04 | Emotion-based category boost | Products relevant to emotional state boosted | Products in DB, user emotion detected | 1. Call `search_products(query_text="spiritual help", emotion="anxiety")`. | Products in "Astrostore" category get +15 emotion boost for anxiety. | P2 | Functional |
| PROD-05 | Stop word removal in search | Common words filtered from search keywords | Products in DB | 1. Call `search_products(query_text="I want to buy a mala for my puja")`. | Stop words (I, want, to, buy, a, for, my) removed. Search uses tokens: ["mala", "puja"]. | P1 | Functional |
| PROD-06 | Multi-term match boost | Products matching multiple keywords ranked higher | Products in DB | 1. Call `search_products(query_text="brass Ganesh murti")`. | Products matching all 3 terms (brass, Ganesh, murti) get `score *= (1 + matched_keywords)` multiplier. Appear above single-term matches. | P1 | Functional |
| PROD-07 | Product deduplication per session | Same product not shown twice in a session | Session with `shown_product_ids` tracking | 1. Get product recommendations on turn 2. 2. Get products again on turn 5. | Products shown on turn 2 are excluded from turn 5 results via `shown_product_ids` set on `SessionState`. | P1 | Functional |
| PROD-08 | Anti-spam — proactive product cooldown | Proactive product suggestions have minimum turn gap | Session with `last_proactive_product_turn` tracking | 1. Products proactively suggested on turn 3. 2. Check if products offered on turn 4. | `last_proactive_product_turn` prevents back-to-back product suggestions. Products only re-offered after sufficient turns. | P1 | Functional |
| PROD-09 | No products for pure emotional messages | Products not recommended for grief/venting without ask | User venting, no product intent | 1. Send "I lost my father last month and can't stop crying". | IntentAgent returns `recommend_products: false`. `recommended_products` in response is empty `[]`. No product cards shown in frontend. | P0 | Compliance |
| PROD-10 | Product cards render in frontend | `ProductDisplay` component renders product cards | Response has `recommended_products` with data | 1. Receive response with products. 2. Check rendered UI. | Horizontal scrollable product cards appear below bot response. Each card shows: image (or ShoppingBag icon), name, category, price (currency + amount), "Essential" badge, external link to `product_url`. "Visit Netra Store" card at the end links to `https://my3ionetra.com`. | P0 | UI |

---

## 10. Text-to-Speech (TTS)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| TTS-01 | Hindi TTS synthesis | POST `/api/tts` generates Hindi audio | gTTS installed, TTS service available | 1. POST `/api/tts` with `{text: "ॐ नमः शिवाय", lang: "hi"}`. | Returns `StreamingResponse` with `media_type: "audio/mpeg"`. Content-Disposition: "inline; filename=tts.mp3". Audio is playable MP3. Cache-Control: "public, max-age=3600". | P0 | Functional |
| TTS-02 | English TTS synthesis | TTS works with English text | TTS available | 1. POST `/api/tts` with `{text: "May peace be with you", lang: "en"}`. | Returns valid MP3 audio in English. | P1 | Functional |
| TTS-03 | Text length limit (5000 chars) | Text truncated at 5000 characters | TTS available | 1. POST `/api/tts` with text longer than 5000 chars. | Only first 5000 characters are synthesized (`request.text[:5000]`). No error thrown. | P1 | Boundary |
| TTS-04 | Empty text rejected | Empty/whitespace-only text returns None | TTS available | 1. POST `/api/tts` with `{text: "   ", lang: "hi"}`. | `synthesize()` returns None. Endpoint returns 500 "Synthesis failed". | P1 | Validation |
| TTS-05 | TTS unavailable (gTTS not installed) | Graceful degradation when gTTS missing | gTTS not installed | 1. POST `/api/tts`. | Returns 503 "TTS unavailable". `tts.available` is False. | P1 | Resilience |
| TTS-06 | Frontend TTSButton — verse playback | TTSButton on verse sections plays audio | Message with `[VERSE]` content rendered | 1. Bot response includes a verse. 2. Click TTS play button on the verse block. | Frontend calls POST `/api/tts` with verse text and `lang: "hi"`. Audio plays in browser. Button shows play/pause state. | P1 | UI |
| TTS-07 | Frontend TTSButton — full response playback | "Listen to Full Response" button plays entire response | Bot message rendered | 1. Click "Listen to Full Response" button below a bot message. | Frontend calls POST `/api/tts` with full response text and `lang: "en"`. Audio plays. | P2 | UI |

---

## 11. Panchang (PANCH)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| PANCH-01 | Get today's panchang — default location | GET `/api/panchang/today` returns data for Delhi | PanchangService available, `hip_main.dat` present | 1. GET `/api/panchang/today` (no params, defaults: lat=28.6139, lon=77.2090, tz=5.5). | Returns JSON with tithi, nakshatra, yoga, karana, sunrise, sunset, moonrise. `special_info` field contains any special day info. | P0 | Functional |
| PANCH-02 | Custom location | Panchang for different city | PanchangService available | 1. GET `/api/panchang/today?lat=19.0760&lon=72.8777&tz=5.5` (Mumbai). | Returns panchang data calculated for Mumbai's coordinates. Sunrise/sunset times differ from Delhi defaults. | P1 | Functional |
| PANCH-03 | Panchang service unavailable | Graceful error when service is down | `panchang_service.available = False` | 1. GET `/api/panchang/today`. | Returns 503 "Panchang service unavailable". | P1 | Resilience |
| PANCH-04 | Panchang integrated in chat | Asking about panchang in conversation returns data | Active session, PanchangService available | 1. Send "What is today's tithi?". | IntentAgent classifies as `ASKING_PANCHANG`. CompanionEngine fetches panchang data and includes tithi, nakshatra in the response. | P1 | Integration |

---

## 12. Memory Service (MEM)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| MEM-01 | UserStory builds over conversation | Memory accumulates user's primary concern, emotion, life area | Active session, multi-turn conversation | 1. Send: "I'm feeling very stressed about work". 2. Send: "My boss doesn't respect my efforts". 3. Send: "I want peace in my career". | `session.memory.story` populated: `primary_concern` ~"career stress", `emotional_state` ~"stressed/frustrated", `life_area: "career"`, `trigger` ~"boss/workplace". | P0 | Functional |
| MEM-02 | Returning user memory inheritance | New session inherits memory from latest saved conversation | Authenticated user with saved conversation history | 1. Login as user with past conversations. 2. Create new session. | Session loads with `_populate_session_with_user_context`. Latest conversation's memory snapshot is inherited. `session.is_returning_user = True`. System message added: "RESUMING CONTEXT from previous session...". Profession, gender, rashi, gotra, nakshatra, preferred_deity pre-populated from user record. | P0 | Functional |
| MEM-03 | Emotional arc tracking | Emotion trajectory recorded across turns | Multi-turn session | 1. Send sad message. 2. Send angry message. 3. Send hopeful message. | `session.memory.emotional_arc` contains list of emotion entries with turn numbers. Shows trajectory: sadness → anger → hope. | P1 | Functional |
| MEM-04 | User quotes captured | Significant user quotes stored with turn numbers | Multi-turn session | 1. Share a meaningful personal statement: "My father always said that honesty is the best policy". | `session.memory.user_quotes` contains the quote with the turn number it was said on. | P2 | Functional |
| MEM-05 | Profile sync on conversation save | User profile updated from session memory on save | Authenticated user, active session | 1. During conversation, mention profession, rashi, or gotra. 2. Save conversation (auto-save or manual). | `auth_service.update_user_profile()` called with discovered fields (profession, gender, rashi, gotra, nakshatra, preferred_deity). Global user record updated for future sessions. | P1 | Integration |
| MEM-06 | Memory summary for LLM context | `get_memory_summary()` provides concise context string | Session with populated memory | 1. Build memory over several turns. 2. Call `session.memory.get_memory_summary()`. | Returns a string summarizing: primary concern, emotional state, life area, key entities, relevant dharmic concepts. Used as system message when restoring sessions. | P1 | Functional |

---

## 13. Frontend UI (UI)

### Login Page

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-01 | Login page renders | LoginPage component displays with all fields | App loaded, user not authenticated | 1. Open app. | Login page shows: 3ioNetra logo, "Elevate Your Spirit" tagline, "Welcome Back" header, email input, password input (with show/hide toggle), "Sign In" button, "New here? Create Account" link. | P0 | UI |
| UI-02 | Register mode switch | Clicking "Create Account" switches to register form | Login page visible | 1. Click "Create Account". | Form changes to "Create Account" header. Step 1 shows: name, email, password, confirm password fields. Progress dots (2 dots) appear. "Already a member? Sign In" link shows. | P0 | UI |
| UI-03 | Password visibility toggle | Eye icon toggles password visibility | Login or register form | 1. Enter password. 2. Click eye icon. 3. Click again. | Password toggles between `type="password"` (dots) and `type="text"` (visible). Confirm password follows the same toggle state. | P2 | UX |
| UI-04 | Error display — red banner | Errors show in styled red banner | Validation error triggered | 1. Submit form with validation error. | Red-bordered rounded banner appears with error text in uppercase tracking. Both server errors and client validation errors displayed. | P1 | UI |
| UI-05 | Loading state — spinner | Button shows spinner during API call | Form submitted | 1. Click "Sign In" or "Create Account". | Button shows `Loader2` spinning icon. Button is disabled (`disabled:opacity-50`). | P1 | UI |

### Chat Interface

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-06 | Empty state — welcome screen | Chat shows welcome cards when no messages | Logged in, no messages | 1. Login successfully. | Welcome screen shows: 3ioNetra logo, "Elevate your spirit" tagline, gradient divider. Two cards: "Seek Wisdom" (BookOpen icon) and "Daily Support" (Activity icon) with descriptions. | P0 | UI |
| UI-07 | Header renders | Top navigation bar with controls | Logged in | 1. Check header. | Header shows: History toggle button, 3ioNetra logo + "3ioNetra" text, "New Session" button with RefreshCw icon. Sticky positioning, blurred backdrop. | P0 | UI |
| UI-08 | User message bubble | User messages appear right-aligned with orange gradient | Message sent | 1. Type "Hello" and send. | Message appears on the right side. Orange-to-amber gradient background. White text. Rounded with `rounded-tr-sm`. Timestamp in bottom-right (HH:MM format). | P0 | UI |
| UI-09 | Assistant message bubble | Bot responses appear left-aligned with white background | Response received | 1. Receive bot response. | Message appears on the left. White background with subtle orange border. Gray text. Rounded with `rounded-tl-sm`. Includes: parsed text content, thumbs up/down buttons, TTS button, timestamp. | P0 | UI |
| UI-10 | Chat input field | Input field with send button | Chat UI loaded | 1. Focus input field. 2. Type text. 3. Click send or press Enter. | Input field: placeholder "Share your spiritual journey...", rounded glass-morphism container. Send button: orange gradient, disabled when empty or processing. Shows spinner during processing. | P0 | UI |
| UI-11 | Input disabled during processing | Cannot send while waiting for response | Message being processed | 1. Send a message. 2. Try to type/send another. | Input field is `disabled`. Send button is `disabled:grayscale disabled:opacity-20`. | P1 | UI |
| UI-12 | Auto-scroll to latest message | Chat scrolls down on new messages | Messages in view | 1. Send message. 2. Receive response. | `messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })` called. View scrolls to show latest message. Throttled to max once per 100ms during streaming. | P1 | UX |
| UI-13 | Verse rendering — blockquote style | `[VERSE]...[/VERSE]` tags render as styled blockquote | Bot response with verse | 1. Receive response containing a verse. | Verse appears in: amber left-border (4px), amber-50 background, italic serif font, wrapped in quotes. TTS play button below verse (Hindi). | P0 | UI |
| UI-14 | Streaming cursor animation | Blinking cursor shown during streaming | Message being streamed | 1. Send message. 2. Observe bot response appearing. | Orange 2px blinking cursor (`streaming-cursor` class) appears at the end of the text while streaming. Disappears when streaming completes. | P2 | UI |
| UI-15 | Loading indicator | Bouncing dots with phase label while processing | Processing state | 1. Send message and observe loading state. | Three bouncing dots (orange gradient) with label: "Listening" or "Seeking Essence" based on session phase. Appears when `isProcessing=true` and last message is empty placeholder. | P1 | UI |

### Phase Indicator

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-16 | PhaseIndicator displays | Compact phase badge shows current phase | Active session | 1. Check above chat messages. | `PhaseIndicatorCompact` shows: current phase name, turn count, max turns (6), signals collected count. | P1 | UI |
| UI-17 | Phase indicator updates | Phase badge updates on phase change | Phase transitions | 1. Send messages until phase changes from "listening" to "guidance". | Phase indicator text updates to reflect new phase. | P1 | UI |

### Flow Metadata Display

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-18 | Flow metadata on user message | User messages show detected domain and emotion | Response received with flow_metadata | 1. Send emotional message. 2. Check user message bubble. | `flowMetadata` attached to the last user message shows: `detected_domain`, `emotional_state`, `topics`, `readiness_score`. | P2 | UI |

### Sidebar (Conversation History)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-19 | Sidebar toggle | History button opens/closes sidebar | Logged in | 1. Click History button in header. 2. Click again. | Sidebar slides in from left (`translate-x-0`). Shows "Conversations" header, "New Session" button, conversation list, user info + "Sign Out". Second click slides out (`-translate-x-full`). | P0 | UI |
| UI-20 | Sidebar — conversation list | Past conversations listed with title and date | Conversations saved | 1. Open sidebar. | Each conversation shows: title (truncated), date, message count. Active conversation highlighted with orange background. | P1 | UI |
| UI-21 | Sidebar — select conversation | Clicking a conversation loads it | Conversations exist | 1. Click a conversation in the sidebar. | Messages from that conversation load into the chat. `currentConversationId` updates. Sidebar closes on mobile. | P0 | UI |
| UI-22 | Sidebar — new session button | "New Session" button starts fresh conversation | Active conversation | 1. Click "New Session" in sidebar or header. | Current conversation auto-saved. Messages cleared. Session reset. `currentConversationId` set to null. Feedback state cleared. History refreshed. | P0 | UI |
| UI-23 | Sidebar — user info and logout | User info and sign-out in sidebar footer | Logged in | 1. Open sidebar. | Footer shows: user avatar (orange icon), user name (bold, truncated), "Sign Out" button (orange, uppercase). | P1 | UI |
| UI-24 | Sidebar — mobile overlay | Mobile backdrop closes sidebar on tap | Mobile viewport, sidebar open | 1. Open sidebar on mobile. 2. Tap outside the sidebar. | Semi-transparent backdrop (`bg-black/10 backdrop-blur-sm`) covers main content. Tapping backdrop closes sidebar (`lg:hidden`). | P2 | Responsive |

### Responsive Design

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-25 | Mobile viewport (< 640px) | Chat UI adapts to mobile screens | Mobile browser or dev tools | 1. Resize to 375px width. | Input field has smaller padding (`px-4 py-3`). Message bubbles max-width 85%. "New Session" text hidden (`hidden sm:inline`). Welcome cards stack vertically. Full-height layout (`h-[100dvh]`). | P1 | Responsive |
| UI-26 | Tablet viewport (640-1024px) | Mid-size screen layout | Tablet or dev tools | 1. Resize to 768px width. | Message bubbles max-width 70%. Welcome cards in 2-column grid. Sidebar is lg:relative (attached, not overlay). | P2 | Responsive |
| UI-27 | Desktop viewport (> 1024px) | Full desktop layout | Desktop browser | 1. Use full-width browser. | Content max-width 4xl. Sidebar is relative positioned (not overlay). All features visible. | P2 | Responsive |

### Feedback Buttons

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-28 | Thumbs up button | Like button highlights green on click | Bot message rendered | 1. Click thumbs-up on a bot message. | Button highlights green (`bg-green-100 text-green-600`). API call to `/api/feedback` with `feedback: "like"`. | P1 | UI |
| UI-29 | Thumbs down button | Dislike button highlights red on click | Bot message rendered | 1. Click thumbs-down. | Button highlights red (`bg-red-100 text-red-600`). API call with `feedback: "dislike"`. | P1 | UI |
| UI-30 | Feedback toggle | Clicking same button again is no-op; switching works | Previous feedback given | 1. Click thumbs-up (like). 2. Click thumbs-up again. 3. Click thumbs-down. | Step 2: no-op (same feedback, early return). Step 3: State changes to dislike, new API call sent. | P2 | UI |

### Miscellaneous UI

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| UI-31 | Fade-in animation | Messages and welcome screen animate in | Any page load or new message | 1. Load page or send message. | Elements have `animate-fade-in` class: opacity 0→1, translateY 8px→0, 0.4s cubic-bezier. | P2 | UI |
| UI-32 | Scrollbar hidden | Custom scrollbar-hide class applied | Chat area | 1. Scroll through messages. | No visible scrollbar (`-ms-overflow-style: none; scrollbar-width: none; ::-webkit-scrollbar { display: none }`). Clean aesthetic. | P2 | UI |

---

## 14. Streaming & Typewriter (STRM)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| STRM-01 | SSE connection established | POST `/api/conversation/stream` returns event-stream | Backend running, RAG ready | 1. POST to `/api/conversation/stream` with valid message. | Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`. First event is SSE comment `: connected\n\n`. | P0 | Functional |
| STRM-02 | Metadata event | `event: metadata` sent before tokens | SSE stream active | 1. Parse SSE events from stream. | First real event: `event: metadata\ndata: {"session_id": "...", "phase": "...", "turn_count": N, "signals_collected": {...}}`. | P0 | Functional |
| STRM-03 | Token events | `event: token` sent for each text chunk | SSE stream active | 1. Collect token events. | Multiple `event: token\ndata: {"text": "..."}` events. Each `text` is a small string fragment. Concatenated tokens form the complete response. | P0 | Functional |
| STRM-04 | Done event | `event: done` sent with final data | SSE stream completes | 1. Wait for stream to finish. | Final event: `event: done\ndata: {"full_response": "...", "recommended_products": [...], "flow_metadata": {...}}`. `full_response` is the cleaned, validated text. | P0 | Functional |
| STRM-05 | Error event | `event: error` sent on exception | Stream encounters error | 1. Force an error during stream (e.g., RAG failure mid-stream). | Event: `event: error\ndata: {"message": "..."}`. Frontend `onError` callback is triggered. | P1 | Error |
| STRM-06 | Typewriter animation | Frontend reveals text progressively | Tokens arriving via SSE | 1. Send a message and observe the response. | Text appears character-by-character via `requestAnimationFrame` loop. Speed adapts: 30 chars/frame when >200 remaining, 15 for >80, 6 for >30, 2 for <=30. Smooth reveal effect. | P1 | UI |
| STRM-07 | Typewriter cleanup on unmount | RAF cancelled on component unmount | Navigation or new session during streaming | 1. Start streaming. 2. Click "New Session" mid-stream. | `cancelAnimationFrame(rafIdRef.current)` called. `isStreamingRef.current = false`. Refs reset: `targetTextRef`, `displayedLengthRef`. No memory leak. | P1 | Cleanup |
| STRM-08 | Stream fallback to non-streaming | Failed stream falls back to POST `/api/conversation` | Stream connection fails | 1. Force stream failure (e.g., network error). | `onError` callback: placeholder message removed. Non-streaming `sendMessage()` called. Response rendered normally without typewriter effect. | P0 | Resilience |
| STRM-09 | Crisis response via stream | Crisis messages sent as single token (no streaming needed) | Crisis keyword detected | 1. Send crisis message via stream endpoint. | Metadata event sent. Single token event with full crisis response. Done event with `recommended_products: []`. No streaming effect needed — immediate display. | P1 | Functional |

---

## 15. Conversation History (HIST)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| HIST-01 | Save conversation | POST `/api/user/conversations` persists messages | Authenticated user, active conversation | 1. POST `/api/user/conversations` with `{conversation_id, title, messages}`. | Returns `{"message": "Saved", "conversation_id": "..."}`. Conversation stored in MongoDB with `user_id`, `title`, `messages`, `memory` snapshot. | P0 | API |
| HIST-02 | Auto-save on message change | Frontend auto-saves after 1.5s debounce | Authenticated, 2+ messages | 1. Send a message and receive response. 2. Wait 1.5 seconds. | `saveConversation()` called automatically via `useEffect` with 1500ms `setTimeout`. History sidebar refreshed. Fires only when `isAuthenticated && messages.length >= 2`. | P0 | Frontend |
| HIST-03 | List conversations | GET `/api/user/conversations` returns history | User has saved conversations | 1. GET `/api/user/conversations` with auth header. | Returns `{conversations: [{id, session_id, title, created_at, message_count}, ...]}`. Ordered by recency. | P0 | API |
| HIST-04 | Load specific conversation | GET `/api/user/conversations/{id}` returns full data | Conversation exists for this user | 1. GET `/api/user/conversations/{conversation_id}` with auth header. | Returns full conversation: `session_id`, `title`, `messages` (array of role/content/timestamp), `memory` snapshot, `created_at`. | P0 | API |
| HIST-05 | Delete conversation | DELETE `/api/user/conversations/{id}` removes it | Conversation exists | 1. DELETE `/api/user/conversations/{conversation_id}` with auth header. | Returns `{"message": "Conversation deleted", "conversation_id": "..."}`. Subsequent GET returns 404. | P1 | API |
| HIST-06 | Unauthenticated access rejected | History endpoints require auth | No auth header | 1. GET `/api/user/conversations` without Authorization header. | Returns 401 (user is None → HTTPException). | P0 | Security |
| HIST-07 | Load and resume conversation in UI | Selecting history item loads messages and resumes session | Conversation in history | 1. Open sidebar. 2. Click a past conversation. | Messages populated in chat. `currentConversationId` set to the conversation's session_id. Session state updated. Sidebar closes on mobile. | P0 | UI |
| HIST-08 | Expired session restoration from history | Loading a conversation whose session expired creates a new one | Authenticated user, session expired | 1. Load a conversation whose session has expired from Redis/Mongo. | Backend detects no active session for the ID. Creates a new session. Restores conversation history and memory from the persistent storage. Sets `is_returning_user = true`. Calls `reconstruct_memory()` to rebuild session state. | P1 | Functional |
| HIST-09 | Memory snapshot saved with conversation | Conversation save includes full memory state | Active session with memory context | 1. Have a multi-turn conversation. 2. Save conversation. | `session.memory.to_dict()` saved as `memory` field in conversation document. Includes: UserStory, emotional_arc, user_quotes, relevant_concepts, readiness_for_wisdom. | P1 | Functional |
| HIST-10 | Redis-cached conversation list | Conversation list queries cached in Redis | Redis available, `CacheService` active | 1. Fetch conversation list. 2. Fetch again immediately. | Second call served from Redis cache (CacheService with MD5 key and 1h TTL). Faster response. | P2 | Performance |

---

## 16. Feedback (FB)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| FB-01 | Submit like feedback | POST `/api/feedback` stores "like" | Authenticated or anonymous, bot message exists | 1. POST `/api/feedback` with `{session_id, message_index: 1, response_text: "...", feedback: "like"}`. | Returns `{"message": "Feedback saved", "feedback": "like"}`. MongoDB `feedback` collection has document with `session_id`, `message_index`, `response_hash` (MD5), `feedback: "like"`, `created_at`. | P0 | API |
| FB-02 | Submit dislike feedback | POST `/api/feedback` stores "dislike" | Same as FB-01 | 1. POST with `feedback: "dislike"`. | Feedback saved as "dislike". | P0 | API |
| FB-03 | Invalid feedback value rejected | Only "like" or "dislike" accepted | Backend running | 1. POST `/api/feedback` with `feedback: "meh"`. | Returns 400 "Feedback must be 'like' or 'dislike'". | P1 | Validation |
| FB-04 | Feedback upsert (change vote) | Changing from like to dislike updates existing record | Previous feedback exists | 1. Submit "like". 2. Submit "dislike" for same `session_id + message_index + response_hash`. | MongoDB `update_one` with `upsert=True` updates `feedback` field. Only one document exists (no duplicates). `updated_at` refreshed. | P1 | Functional |
| FB-05 | Feedback dedup by response_hash | Same response at same index only has one feedback record | Multiple feedback submissions | 1. Submit "like" twice for the same message. | `response_hash` (MD5 of `response_text`) used as part of the unique filter. Only one record in DB. Second call updates `updated_at` but doesn't create duplicate. | P2 | Functional |

---

## 17. Deployment (DEPLOY)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| DEPLOY-01 | Health endpoint | GET `/api/health` returns status | Backend running | 1. GET `/api/health`. | Returns `{status: "healthy", timestamp: "...", version: "2.1.0", rag_available: true/false}`. | P0 | API |
| DEPLOY-02 | Readiness endpoint | GET `/api/ready` checks RAG status | Backend running | 1. GET `/api/ready` when RAG is initialized. 2. GET `/api/ready` when RAG is not ready. | Case 1: `{status: "ready"}`. Case 2: 503 "RAG pipeline not ready". | P0 | API |
| DEPLOY-03 | Docker Compose — all services start | `docker compose up` starts 4 services | Docker installed | 1. Run `docker compose up --build`. | Services start: `qdrant` (6333/6334), `redis` (6379), `backend` (8080), `frontend` (3000). Backend depends on qdrant + redis. Frontend depends on backend. | P0 | Deployment |
| DEPLOY-04 | CORS configuration | Allowed origins enforced | Backend running | 1. Make request from `https://3iomitra.3iosetu.com`. 2. Make request from `https://evil.com`. | Request 1: CORS headers present, request succeeds. Request 2: CORS blocked (origin not in allowed list). Allowed origins include: `https://3iomitra.3iosetu.com`, `https://3io-netra.vercel.app`, `http://localhost:3000`, `http://localhost:3001`, `http://localhost:8000`, `http://localhost:8080`, plus any from `ALLOWED_ORIGINS` env var. | P0 | Security |
| DEPLOY-05 | Environment variables | Required env vars are loaded | Backend starting | 1. Start backend without `GEMINI_API_KEY`. 2. Start with all required vars set. | Case 1: LLM service starts with `available=False`. Conversation works with fallback responses. Case 2: Full functionality. All vars from `config.py` loaded via pydantic-settings from `.env` file. | P1 | Config |
| DEPLOY-06 | Root endpoint | GET `/` returns app info | Backend running | 1. GET `/`. | Returns `{app: "3ioNetra API", version: "1.1.3", mode: "modular_refined"}`. | P1 | API |
| DEPLOY-07 | Graceful shutdown | Backend cleans up on shutdown | Backend running | 1. Send SIGTERM to backend process. | Lifespan shutdown runs: `cache_service.close()` (Redis connections), `close_mongo_client()` (MongoDB connections). Logs "3ioNetra Backend Shutdown Complete." | P1 | Deployment |
| DEPLOY-08 | Frontend NEXT_PUBLIC_API_URL | Frontend uses correct API URL | Frontend running | 1. Check frontend API calls. | All API calls use `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8080`). Trailing slash stripped. | P1 | Config |
| DEPLOY-09 | Production Dockerfile — offline models | Production image has baked-in models | Building with `backend/Dockerfile` | 1. Build production Docker image. 2. Run with `TRANSFORMERS_OFFLINE=1`. | Embedding model (`paraphrase-multilingual-mpnet-base-v2`) and reranker model (`ms-marco-MiniLM-L-6-v2`) are pre-downloaded into the image. No network model downloads at runtime. | P2 | Deployment |

---

## 18. Data Ingestion (INGEST)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| INGEST-01 | CSV ingestion | CSV scripture files processed into verses | CSV files in `data/raw/` | 1. Place CSV file with columns (reference, text, meaning, scripture, topic) in `data/raw/`. 2. Run `python scripts/ingest_all_data.py`. | Verses extracted, scripture name inferred, topics assigned. Output in `data/processed/verses.json`. No duplicates by reference. | P0 | Functional |
| INGEST-02 | JSON ingestion (temples) | Temple JSON files converted to verse-like objects | JSON temple files in `data/raw/` | 1. Place temple JSON in `data/raw/`. 2. Run ingestion. | Temples converted to verse objects with `type: "temple"`. Location info preserved. | P1 | Functional |
| INGEST-03 | PDF ingestion via Gemini | PDF files processed via `PDFIngester` using Gemini multimodal | PDF in `data/raw/`, Gemini API key set | 1. Place a scripture PDF in `data/raw/`. 2. Run `python scripts/pdf_ingester.py`. | Gemini extracts structured verses from PDF pages. Output format matches standard verse schema. Verification: `python scripts/verify_pdf_ingestion.py`. | P1 | Functional |
| INGEST-04 | Deduplication by reference | Duplicate verse references are merged, not duplicated | Multiple files with overlapping references | 1. Ingest two CSV files that contain the same verse reference (e.g., "BG 2.47"). | Only one entry for "BG 2.47" in final `verses.json`. Later ingestion may update the existing entry. | P0 | Functional |
| INGEST-05 | Embeddings generation | `embeddings.npy` generated from verses | Verses processed, embedding model available | 1. Run full ingestion pipeline. | `data/processed/embeddings.npy` created. Array shape: `(num_verses, 768)`. dtype: float32. Embeddings pre-normalized (unit vectors for dot-product similarity). | P0 | Functional |
| INGEST-06 | Video ingestion via Gemini Files API | Video files processed via `VideoIngester` | Video in `data/raw/`, Gemini API key | 1. Place a spiritual video in `data/raw/`. 2. Run `python scripts/video_ingester.py`. | Gemini Files API uploads video, extracts segments with timestamps, transcription, and shloka identification. Verification: `python scripts/verify_video_ingestion.py`. | P2 | Functional |

---

## 19. Performance (PERF)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| PERF-01 | Time to first token (TTFT) | First SSE token arrives within acceptable time | Backend running, warm state | 1. Send message via `/api/conversation/stream`. 2. Measure time from request to first `event: token`. | TTFT < 3 seconds for non-trivial messages (includes intent classification + parallel RAG). TTFT < 1 second for trivial messages (fast-path greeting). | P0 | Performance |
| PERF-02 | End-to-end response latency | Full non-streaming response time | Backend running | 1. Send message via `/api/conversation`. 2. Measure total round-trip time. | Response < 8 seconds for guidance phase (intent + RAG + LLM). Response < 3 seconds for listening phase. | P0 | Performance |
| PERF-03 | Concurrent users | Backend handles multiple simultaneous sessions | Backend running, load test tool | 1. Simulate 10 concurrent users each sending messages. | All 10 users receive responses without 500 errors. Response times degrade gracefully (< 2x single-user latency). No session cross-contamination. | P1 | Load |
| PERF-04 | Memory usage | Backend memory stays bounded | Backend running with mmap embeddings | 1. Start backend. 2. Monitor RSS memory over 100 conversations. | Memory stays under 1 GB (embeddings are mmap'd, not loaded into RAM). No memory leaks from session accumulation (TTL cleans up). | P1 | Performance |
| PERF-05 | Startup time | Backend initializes within acceptable time | Cold start | 1. Start backend from scratch. 2. Measure time to "3ioNetra Backend Successfully Initialized!" log. | Startup < 30 seconds (includes embedding model loading, BM25 index building, Redis/MongoDB connections). | P2 | Performance |

---

## 20. Edge Cases & Regression (EDGE)

| ID | Title | Description | Pre-conditions | Test Steps | Expected Result | Priority | Type |
|----|-------|-------------|----------------|------------|-----------------|----------|------|
| EDGE-01 | Unicode — Devanagari input | Hindi/Sanskrit text handled correctly | Backend running | 1. Send "मुझे भगवद गीता के बारे में बताइए". | Message processed correctly. IntentAgent analyzes Hindi text. RAG search handles multi-lingual embeddings. Response may include Hindi content. No encoding errors. | P0 | Compatibility |
| EDGE-02 | Unicode — emoji input | Emojis in messages don't crash backend | Backend running | 1. Send "I feel so happy today! 🙏😊🙏". | Message processed normally. Emojis preserved in conversation history. No JSON serialization errors. | P1 | Compatibility |
| EDGE-03 | XSS attempt in message | Script tags in user input sanitized | Backend running, frontend rendering | 1. Send `<script>alert('xss')</script>`. | Backend stores raw text. Frontend renders via React's default escaping (JSX auto-escapes). No script execution. Text appears literally as `<script>alert('xss')</script>`. | P0 | Security |
| EDGE-04 | SQL/NoSQL injection attempt | Injection payloads don't affect database | Backend running | 1. Send message: `{"$gt": ""}` or `'; DROP TABLE users; --`. | Message treated as plain text. MongoDB queries use parameterized fields (not string interpolation). No data loss or unauthorized access. | P0 | Security |
| EDGE-05 | Rapid fire messages | Multiple messages sent in quick succession | Active session | 1. Send 5 messages within 2 seconds. | Each message processed sequentially per session. Frontend `isProcessing` prevents double-sends from UI. Backend handles concurrent requests to same session gracefully (no race conditions on session state). | P1 | Stress |
| EDGE-06 | Very long message (10000+ chars) | Extremely long input handled | Backend running | 1. Send a message with 10,000+ characters. | Message accepted. IntentAgent processes it (may truncate for LLM context). RAG search uses the message. No timeout or OOM. Response generated normally. | P1 | Boundary |
| EDGE-07 | Empty message rejected | Empty/whitespace-only messages not processed | Frontend loaded | 1. Try to send empty message or spaces only. | Frontend: `!input.trim()` prevents submission. Send button is disabled. No API call made. | P0 | Validation |
| EDGE-08 | Persona compliance — no hollow phrases | Bot never says "I hear you", "I understand", etc. | Guidance response generated | 1. Analyze 20 guidance responses. | None contain banned hollow phrases: "I hear you", "I understand", "It sounds like", "everything happens for a reason", "just be positive", "others have it worse". SafetyValidator catches and replaces any that slip through. | P0 | Compliance |
| EDGE-09 | Persona compliance — no product mentions in LLM text | LLM response text never mentions products, shopping, or URLs | Guidance response with products | 1. Get a response that includes `recommended_products`. 2. Check `response` text. | Response text contains no mentions of "my3ionetra.com", "buy", "shop", "product", or any URL. Products are shown separately via frontend cards only. | P0 | Compliance |
| EDGE-10 | Session with no signals | Conversation where user gives minimal info | Active session | 1. Send only vague messages: "hmm", "okay", "I don't know". | Bot continues to gently probe. After `max_clarification_turns` (4), guidance is force-triggered even with minimal signals. Response is still meaningful (general spiritual guidance). | P1 | Functional |
| EDGE-11 | Pivot on rejection | Bot offers alternative when suggestion rejected | Guidance given, user rejects | 1. Receive meditation suggestion. 2. Reply "I don't believe in meditation". | Bot does NOT just empathize ("I understand"). Instead, immediately offers an alternative spiritual path (e.g., mantra chanting, temple visit, pranayama). | P1 | Compliance |
| EDGE-12 | Mixed language input (Hinglish) | Hindi-English mixed text processed | Backend running | 1. Send "Mujhe bahut tension ho raha hai about my career". | IntentAgent correctly identifies: emotion (tension/anxiety), life_domain (career). Response is contextually appropriate. Multi-lingual embedding model handles Hinglish. | P1 | Compatibility |
| EDGE-13 | Concurrent sessions — no data leakage | User A's data never appears in User B's session | Two users with active sessions | 1. User A shares personal details (name, profession). 2. User B starts a new session. | User B's session has no trace of User A's data. Session isolation enforced by `session_id` and `user_id` checks. Memory is per-session. | P0 | Security |
| EDGE-14 | Network disconnection mid-stream | Frontend handles connection drop during SSE | Streaming active | 1. Start SSE stream. 2. Kill network connection mid-stream. | Frontend `onError` callback fires. Stream fallback engaged (non-streaming `sendMessage`). If fallback also fails, error message displayed: "I apologize, but I encountered an error. Please try again." RAF cleanup runs. | P1 | Resilience |
| EDGE-15 | Browser refresh during conversation | Refreshing page preserves session context | Active conversation, authenticated | 1. Have a multi-turn conversation. 2. Refresh the page. | `session_id` restored from `localStorage` (`spiritual_session_id` key). Auth token verified via `/api/auth/verify`. If authenticated, conversation history available via sidebar. New messages sent with the restored session_id. Backend recovers session from Redis/MongoDB/persistent storage. | P0 | Resilience |

---

## User Persona Test Matrix

Maps 6 user personas to the test cases most relevant for their journey.

| Persona | Description | Critical Test IDs |
|---------|-------------|-------------------|
| **New User** | First-time visitor, registers and explores | AUTH-01, AUTH-06, AUTH-14, SES-01, FLOW-01, FLOW-02, FLOW-03, UI-01, UI-02, UI-06, UI-08, UI-09, UI-10, STRM-01, STRM-06, EDGE-07 |
| **Returning User** | Previously registered, has past conversations | AUTH-17, MEM-02, MEM-05, HIST-03, HIST-04, HIST-07, HIST-08, UI-19, UI-20, UI-21, EDGE-15 |
| **Crisis User** | User expressing self-harm or crisis thoughts | SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-06, SAFE-07, SAFE-08, SAFE-09, SAFE-14, INTENT-14, STRM-09 |
| **Curious Learner** | Asks factual spiritual questions | INTENT-04, INTENT-05, RAG-01, RAG-05, RAG-09, CTXV-05, LLM-01, LLM-06, PANCH-01, PANCH-04, FLOW-09, TTS-01 |
| **Devoted Practitioner** | Regularly performs pujas, wants products and rituals | INTENT-06, INTENT-15, PROD-01, PROD-02, PROD-03, PROD-06, PROD-09, PROD-10, FLOW-10, UI-13, TTS-06 |
| **Multilingual User** | Communicates in Hindi, Hinglish, or Sanskrit | EDGE-01, EDGE-12, TTS-01, TTS-02, RAG-02, LLM-01, UI-13 |

---

## Recommended Execution Order

### Phase 1 — Smoke Test (8 tests, ~15 min)
Run these first to validate the system is functional:

| Priority | Test ID | What it validates |
|----------|---------|-------------------|
| P0 | DEPLOY-01 | Backend is alive |
| P0 | DEPLOY-02 | RAG is ready |
| P0 | AUTH-14 | Login works |
| P0 | SES-01 | Session creation works |
| P0 | FLOW-02 | Greeting handled |
| P0 | FLOW-03 | Guidance generated |
| P0 | STRM-01 | Streaming works |
| P0 | SAFE-01 | Crisis detection works |

### Phase 2 — P0 Tests (54 tests)
All release blockers. Grouped by segment priority:

1. Safety (SAFE-01 to SAFE-12, SAFE-15) — most critical
2. Authentication (AUTH-01, AUTH-04, AUTH-05, AUTH-06, AUTH-12, AUTH-14, AUTH-15, AUTH-17, AUTH-18)
3. Conversation Flow (FLOW-01 to FLOW-04)
4. Streaming (STRM-01 to STRM-04, STRM-08)
5. LLM (LLM-01, LLM-02, LLM-04, LLM-08)
6. RAG (RAG-01, RAG-04, RAG-08)
7. Context Validation (CTXV-01, CTXV-06, CTXV-08)
8. Intent (INTENT-01 to INTENT-03, INTENT-14, INTENT-16)
9. Frontend (UI-01, UI-02, UI-06 to UI-10, UI-13, UI-19, UI-21, UI-22)
10. History (HIST-01 to HIST-04, HIST-06, HIST-07)
11. Feedback (FB-01, FB-02)
12. Products (PROD-01, PROD-09, PROD-10)
13. TTS (TTS-01)
14. Panchang (PANCH-01)
15. Deployment (DEPLOY-01 to DEPLOY-04)
16. Ingestion (INGEST-01, INGEST-04, INGEST-05)
17. Performance (PERF-01, PERF-02)
18. Edge Cases (EDGE-01, EDGE-03, EDGE-04, EDGE-07 to EDGE-09, EDGE-13, EDGE-15)
19. Memory (MEM-01, MEM-02)
20. Session (SES-01, SES-02, SES-10)

### Phase 3 — P1 Tests (103 tests)
Important but not release-blocking. Run after all P0 pass.

### Phase 4 — P2 Tests (62 tests)
Nice-to-have. Run during dedicated QA sprints.

---

## Summary Table

| Segment | P0 | P1 | P2 | Total |
|---------|----|----|-----|-------|
| AUTH | 5 | 8 | 5 | 18 |
| SES | 3 | 5 | 3 | 11 |
| FLOW | 4 | 5 | 2 | 11 |
| INTENT | 5 | 9 | 3 | 17 |
| RAG | 3 | 5 | 2 | 10 |
| CTXV | 2 | 4 | 3 | 9 |
| LLM | 4 | 3 | 2 | 9 |
| SAFE | 7 | 6 | 3 | 16 |
| PROD | 2 | 5 | 3 | 10 |
| TTS | 1 | 4 | 2 | 7 |
| PANCH | 1 | 3 | 0 | 4 |
| MEM | 2 | 3 | 1 | 6 |
| UI | 8 | 14 | 10 | 32 |
| STRM | 4 | 4 | 1 | 9 |
| HIST | 5 | 3 | 2 | 10 |
| FB | 2 | 2 | 1 | 5 |
| DEPLOY | 3 | 4 | 2 | 9 |
| INGEST | 3 | 2 | 1 | 6 |
| PERF | 2 | 2 | 1 | 5 |
| EDGE | 5 | 7 | 3 | 15 |
| **TOTAL** | **71** | **98** | **50** | **219** |

---

*Generated for 3ioNetra Spiritual Companion v1.1.3. All test IDs reference actual codebase endpoints, services, and configuration values.*
