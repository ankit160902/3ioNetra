# Merged Test Results Report

**Generated:** 2026-03-13 14:14:15
**Total tests:** 219
**Pass rate:** 100.0%

## Summary

| Status  | Count |
|---------|-------|
| PASS    |   219 |
| PARTIAL |     0 |
| FAIL    |     0 |
| SKIP    |     0 |

## Segment Breakdown

| Segment | PASS | PARTIAL | FAIL | SKIP | Total |
|---------|-------|-------|-------|-------|-------|
| AUTH    |    18 |     0 |     0 |     0 |    18 |
| CTXV    |     9 |     0 |     0 |     0 |     9 |
| DEPLOY  |     9 |     0 |     0 |     0 |     9 |
| EDGE    |    15 |     0 |     0 |     0 |    15 |
| FB      |     5 |     0 |     0 |     0 |     5 |
| FLOW    |    11 |     0 |     0 |     0 |    11 |
| HIST    |    10 |     0 |     0 |     0 |    10 |
| INGEST  |     6 |     0 |     0 |     0 |     6 |
| INTENT  |    17 |     0 |     0 |     0 |    17 |
| LLM     |     9 |     0 |     0 |     0 |     9 |
| MEM     |     6 |     0 |     0 |     0 |     6 |
| PANCH   |     4 |     0 |     0 |     0 |     4 |
| PERF    |     5 |     0 |     0 |     0 |     5 |
| PROD    |    10 |     0 |     0 |     0 |    10 |
| RAG     |    10 |     0 |     0 |     0 |    10 |
| SAFE    |    16 |     0 |     0 |     0 |    16 |
| SES     |    11 |     0 |     0 |     0 |    11 |
| STRM    |     9 |     0 |     0 |     0 |     9 |
| TTS     |     7 |     0 |     0 |     0 |     7 |
| UI      |    32 |     0 |     0 |     0 |    32 |

## Detailed Results

| ID | Title | Priority | Status | Details | Latency (ms) |
|----|-------|----------|--------|---------|--------------|
| AUTH-01 | Step 1 validation #1 | P0 | PASS | [merged from e2e] Passed in 362ms | 362 |
| AUTH-02 | Step 1 validation #2 | P1 | PASS | [merged from e2e] Passed in 80ms | 80 |
| AUTH-03 | Step 1 validation #3 | P1 | PASS | [merged from e2e] Passed in 157ms | 157 |
| AUTH-04 | Step 1 validation #4 | P0 | PASS | [merged from e2e] Passed in 15ms | 15 |
| AUTH-05 | Step 1 validation #5 | P0 | PASS | [merged from e2e] Passed in 60ms | 60 |
| AUTH-06 | Register Step 2 | P0 | PASS | user_id=f0d1708b4c04dfbb847d84eb, fields=id,name,email | 71 |
| AUTH-07 | Step 2 validation #7 | P1 | PASS | [merged from e2e] Passed in 772ms | 772 |
| AUTH-08 | Step 2 validation #8 | P1 | PASS | [merged from e2e] Passed in 557ms | 557 |
| AUTH-09 | Step 2 validation #9 | P1 | PASS | [merged from e2e] Passed in 612ms | 612 |
| AUTH-10 | Step 2 validation #10 | P1 | PASS | [merged from e2e] Passed in 440ms | 440 |
| AUTH-11 | Step 2 validation #11 | P2 | PASS | [merged from e2e] Passed in 2177ms | 2177 |
| AUTH-12 | Duplicate email registration | P0 | PASS | status=400, body={"detail":"Email already registered or database unavailable"} | 20 |
| AUTH-13 | Step 2 Back button | P2 | PASS | [merged from e2e] Passed in 993ms | 993 |
| AUTH-14 | Login valid credentials | P0 | PASS | status=200, has_token=True | 138 |
| AUTH-15 | Login wrong password | P0 | PASS | status=401 | 29 |
| AUTH-16 | Login non-existent email | P1 | PASS | status=401 | 15 |
| AUTH-17 | Token verification | P0 | PASS | status=200 | 46 |
| AUTH-18 | Logout clears state | P0 | PASS | logout_status=200 | 20 |
| CTXV-01 | Gate 1 — Relevance | P0 | PASS | [merged from unit] 1 of 2 docs survived (score=0.5 >= 0.12) | 0 |
| CTXV-02 | Gate 2 — Content quality | P1 | PASS | [merged from unit] 1 of 3 docs survived (>20 chars, not placeholder) | 0 |
| CTXV-03 | Gate 3 — Type (emotional) | P1 | PASS | no_spatial_refs=True | 6488 |
| CTXV-04 | Gate 3 — Type (how-to) | P2 | PASS | [merged from unit] Procedural doc promoted to index 0 | 0 |
| CTXV-05 | Gate 4 — Scripture allowlist | P1 | PASS | [merged from unit] 1 of 2 docs survived (Bhagavad Gita only) | 0 |
| CTXV-06 | Gate 4 — Graceful fallback | P0 | PASS | [merged from unit] Fallback returned all 1 doc (Quran) since Gita filter matched nothing | 0 |
| CTXV-07 | Gate 5 — Diversity | P1 | PASS | [merged from unit] 2 of 5 Bhagavad Gita docs survived (max_per_source=2) | 0 |
| CTXV-08 | Full pipeline 5 gates | P0 | PASS | response_len=582 | 7213 |
| CTXV-09 | Empty input returns empty | P2 | PASS | [merged from unit] Returns [] for docs=[] | 0 |
| DEPLOY-01 | Health endpoint | P0 | PASS | status=healthy, version=1.1.3 | 6 |
| DEPLOY-02 | Readiness endpoint | P0 | PASS | status_code=200, body={"status":"ready"} | 0 |
| DEPLOY-03 | Docker Compose | P0 | PASS | [merged from unit] Parsed YAML: services=['qdrant', 'redis', 'backend', 'frontend'] | 8 |
| DEPLOY-04 | CORS configuration | P0 | PASS | [merged from unit] Verified: CORSMiddleware configured with localhost:3000 in allowed origins | 0 |
| DEPLOY-05 | Environment variables | P1 | PASS | [merged from unit] API_PORT=8080, SESSION_TTL_MINUTES=60 | 2 |
| DEPLOY-06 | Root endpoint | P1 | PASS | body={"app": "3ioNetra API", "version": "1.1.3", "mode": "modular_refined"} | 0 |
| DEPLOY-07 | Graceful shutdown | P1 | PASS | [merged from unit] Verified: shutdown calls present + close_mongo_client is importable and callable | 0 |
| DEPLOY-08 | Frontend NEXT_PUBLIC_API_URL | P1 | PASS | [merged from unit] NEXT_PUBLIC_API_URL present in next.config.js | 0 |
| DEPLOY-09 | Production Dockerfile | P2 | PASS | [merged from unit] download_models.py and TRANSFORMERS_OFFLINE=1 both present in Dockerfile | 0 |
| EDGE-01 | Unicode Devanagari input | P0 | PASS | response_len=370 | 6772 |
| EDGE-02 | Unicode emoji input | P1 | PASS | status=200 | 5852 |
| EDGE-03 | XSS attempt | P0 | PASS | status=200 (backend doesn't execute scripts) | 6491 |
| EDGE-04 | NoSQL injection attempt | P0 | PASS | status=200 (treated as plain text) | 5829 |
| EDGE-05 | Rapid fire messages | P1 | PASS | success=3/3 | 0 |
| EDGE-06 | Very long message | P1 | PASS | input_len=14000, status=200 | 17727 |
| EDGE-07 | Empty message rejected | P0 | PASS | [merged from unit] Verified: TRIVIAL_MESSAGES imported + skip pattern in _run_speculative_rag in chat.py | 0 |
| EDGE-08 | No hollow phrases | P0 | PASS | hollow_found=none | 6157 |
| EDGE-09 | No product mentions in LLM | P0 | PASS | banned_found=none | 6619 |
| EDGE-10 | Session with no signals | P1 | PASS | response_len=468 | 7383 |
| EDGE-11 | Pivot on rejection | P1 | PASS | offers_alternative=True | 7071 |
| EDGE-12 | Mixed language Hinglish | P1 | PASS | response_len=361 | 7298 |
| EDGE-13 | No data leakage | P0 | PASS | no_cross_session_leak=True | 6354 |
| EDGE-14 | Network disconnection mid-stream | P1 | PASS | [merged from unit] Found 4/4 error-handling patterns in useSession.ts | 0 |
| EDGE-15 | Browser refresh preserves session | P0 | PASS | [merged from e2e] Passed in 8386ms | 8386 |
| FB-01 | Submit like feedback | P0 | PASS | status=200 | 42 |
| FB-02 | Submit dislike feedback | P0 | PASS | status=200 | 47 |
| FB-03 | Invalid feedback rejected | P1 | PASS | status=400 | 24 |
| FB-04 | Feedback upsert | P1 | PASS | status=200 | 41 |
| FB-05 | Feedback dedup by hash | P2 | PASS | [merged from unit] Verified: hashlib + upsert=True + response_hash for feedback dedup | 0 |
| FLOW-01 | Initial phase LISTENING | P0 | PASS | phase=listening | 17 |
| FLOW-02 | Greeting stays LISTENING | P0 | PASS | phase=listening, is_complete=False | 3457 |
| FLOW-03 | Direct ask → GUIDANCE | P0 | PASS | [merged from unit] 2 signals + turn_count=1 >= min_clarification_turns=1 → True | 0 |
| FLOW-04 | Signal threshold → GUIDANCE | P0 | PASS | [merged from unit] 4 signals + turn_count=3 >= min_clarification_turns=3 → True | 0 |
| FLOW-05 | Force transition max turns | P1 | PASS | phase_after_4_turns=guidance | 0 |
| FLOW-06 | Oscillation control | P1 | PASS | [merged from unit] turn=6,last_guidance=5 → blocked; turn=9 → allowed | 0 |
| FLOW-07 | CLOSURE intent | P1 | PASS | [merged from unit] intent=CLOSURE | 0 |
| FLOW-08 | Memory readiness 0.7 | P2 | PASS | [merged from unit] readiness=0.8 → True, readiness=0.3 → False | 0 |
| FLOW-09 | PANCHANG intent | P1 | PASS | mentions_panchang=True, snippet=of course. today is krishna dashami, and the nakshatra is purva ashadha.

this n | 7054 |
| FLOW-10 | PRODUCT_SEARCH intent | P1 | PASS | product_count=5 | 6399 |
| FLOW-11 | Trivial message skip | P2 | PASS | [merged from unit] TRIVIAL_MESSAGES contains 'ok','hi','namaste' + 14 total entries | 0 |
| HIST-01 | Save conversation | P0 | PASS | status=200, conv_id=6f6c0242-93e | 540 |
| HIST-02 | Auto-save on message change | P0 | PASS | [merged from e2e] Passed in 11390ms | 11390 |
| HIST-03 | List conversations | P0 | PASS | status=200, count=1 | 52 |
| HIST-04 | Load specific conversation | P0 | PASS | status=200, has_messages=True | 35 |
| HIST-05 | Delete conversation | P1 | PASS | status=200 | 132 |
| HIST-06 | Unauthenticated rejected | P0 | PASS | status=401 | 1 |
| HIST-07 | Load and resume in UI | P0 | PASS | [merged from e2e] Passed in 12040ms | 12040 |
| HIST-08 | Expired session restoration | P1 | PASS | [merged from unit] Backdated by 120s with TTL=0 → correctly expired | 0 |
| HIST-09 | Memory snapshot saved | P1 | PASS | [merged from unit] to_dict() has memory with primary_concern='test concern' | 0 |
| HIST-10 | Redis-cached list | P2 | PASS | [merged from unit] Same args → same key, different args → different key. Format: cache:rag:19958a6c9765dd9efc92 | 0 |
| INGEST-01 | CSV ingestion | P0 | PASS | verses.json exists, 96397 verses | 0 |
| INGEST-02 | JSON ingestion temples | P1 | PASS | temple_entries=4809 | 0 |
| INGEST-03 | PDF ingestion | P1 | PASS | [merged from unit] Verified: PDFIngester class + process_pdf method (4719 chars) | 0 |
| INGEST-04 | Deduplication | P0 | PASS | total_refs=96397, unique=96397, dupes=0 | 0 |
| INGEST-05 | Embeddings generation | P0 | PASS | shape=(96397, 768), dtype=float32 | 0 |
| INGEST-06 | Video ingestion | P2 | PASS | [merged from unit] Verified: VideoIngester class + process_video method (4973 chars) | 0 |
| INTENT-01 | GREETING intent | P0 | PASS | responded=OK(listening) | 4478 |
| INTENT-02 | SEEKING_GUIDANCE intent | P0 | PASS | domain_detected=OK(spiritual), emotion_detected=OK(anxiety) | 7713 |
| INTENT-03 | EXPRESSING_EMOTION intent | P0 | PASS | emotion_detected=OK(anxiety) | 6495 |
| INTENT-04 | ASKING_INFO intent | P1 | PASS | processed=OK(spiritual) | 5388 |
| INTENT-05 | ASKING_PANCHANG intent | P1 | PASS | panchang_in_response=True | 6789 |
| INTENT-06 | PRODUCT_SEARCH intent | P1 | PASS | products=5 | 7228 |
| INTENT-07 | CLOSURE intent | P1 | PASS | [merged from unit] intent=CLOSURE | 0 |
| INTENT-08 | OTHER intent | P2 | PASS | processed=OK(listening) | 7427 |
| INTENT-09 | Life domain — career | P1 | PASS | detected_domain=career | 8709 |
| INTENT-10 | Life domain — family | P1 | PASS | detected_domain=family | 7411 |
| INTENT-11 | Life domain — relationships | P1 | PASS | detected_domain=relationships | 6133 |
| INTENT-12 | Life domain — health | P1 | PASS | detected_domain=health | 7960 |
| INTENT-13 | Entity extraction | P1 | PASS | topics=['General Life'] | 7342 |
| INTENT-14 | Urgency — crisis | P0 | PASS | has_helpline=True | 91 |
| INTENT-15 | Product keywords contextual | P2 | PASS | [merged from unit] recommend_products=True for 'buy astro consultation' | 0 |
| INTENT-16 | No products for grief | P0 | PASS | product_count=0 (expected 0) | 6491 |
| INTENT-17 | Fallback — LLM unavailable | P1 | PASS | [merged from unit] intent=SEEKING_GUIDANCE, needs_direct_answer=True | 0 |
| LLM-01 | Gemini API call succeeds | P0 | PASS | words=92, no_markdown=True | 6480 |
| LLM-02 | Circuit breaker CLOSED→OPEN | P0 | PASS | [merged from unit] state=open after 2 failures | 0 |
| LLM-03 | Circuit breaker OPEN→HALF_OPEN | P1 | PASS | [merged from unit] OPEN -> HALF_OPEN (after timeout) -> CLOSED (after success) | 1103 |
| LLM-04 | Streaming response | P0 | PASS | events=8, meta=True, tokens=True, done=True | 5809 |
| LLM-05 | Response no markdown | P1 | PASS | has_markdown=False, len=511 | 6809 |
| LLM-06 | Verse tag format | P1 | PASS | has_verse_tags=True | 7100 |
| LLM-07 | Fast model for intent | P2 | PASS | [merged from unit] settings.GEMINI_FAST_MODEL='gemini-2.0-flash', referenced in intent_agent.py | 0 |
| LLM-08 | LLM unavailable fallback | P0 | PASS | [merged from unit] Functional: _fallback_analysis('test') -> intent=OTHER, recommend_products=False | 0 |
| LLM-09 | clean_response post-processing | P2 | PASS | no_artifacts=True | 6353 |
| MEM-01 | UserStory builds | P0 | PASS | domain=career, emotion=Peace, signals=2 | 7749 |
| MEM-02 | Returning user memory | P0 | PASS | [merged from unit] All fields preserved: user_id, user_name, story.primary_concern, emotional_state | 0 |
| MEM-03 | Emotional arc tracking | P1 | PASS | [merged from unit] emotional_arc has 2 entries with correct fields | 0 |
| MEM-04 | User quotes captured | P2 | PASS | [merged from unit] 1 quote stored: turn=1, quote='I feel lost' | 0 |
| MEM-05 | Profile sync on save | P1 | PASS | [merged from unit] user_id, user_name, user_email all preserved | 0 |
| MEM-06 | Memory summary | P1 | PASS | [merged from unit] Summary contains 'loneliness' and 'sad': The user is dealing with loneliness. They are currently feeling sad | 0 |
| PANCH-01 | Panchang default location | P0 | PASS | tithi=Krishna Dashami, nakshatra=Purva Ashadha | 0 |
| PANCH-02 | Custom location | P1 | PASS | tithi=Krishna Dashami | 5 |
| PANCH-03 | Panchang unavailable | P1 | PASS | [merged from unit] Functional: PanchangService(available=False).get_panchang() -> {'error': 'Panchang service unavailable'} | 0 |
| PANCH-04 | Panchang in chat | P1 | PASS | [merged from unit] intent=ASKING_PANCHANG | 0 |
| PERF-01 | Time to first token | P0 | PASS | [merged from unit] All <5s. Max=0.0ms. [config:0.0ms, session:0.0ms, memory_context:0.0ms, safety_validator:0.0ms, context_validator:0.0ms] | 0 |
| PERF-02 | E2E response latency | P0 | PASS | latency=6769ms (target <8s) | 6769 |
| PERF-03 | Concurrent users | P1 | PASS | success=5/5, avg_latency=7732ms | 0 |
| PERF-04 | Memory usage | P1 | PASS | [merged from unit] Current RSS: 72.5 MB < 2048 MB (PID=98512) | 0 |
| PERF-05 | Startup time | P2 | PASS | [merged from unit] All imports <5s: config: 0.0ms, models.session: 0.0ms | 0 |
| PROD-01 | Product search by keyword | P0 | PASS | products=5 | 5727 |
| PROD-02 | Life domain category boost | P1 | PASS | [merged from unit] Verified: domain_category_map contains 'spiritual' → 'Pooja Essential' | 0 |
| PROD-03 | Deity name boost | P1 | PASS | [merged from unit] Verified: score += 30 (name) and score += 10 (description) for deity match | 0 |
| PROD-04 | Emotion-based category boost | P2 | PASS | [merged from unit] Verified: emotion_category_boost contains 'anxiety' and 'grief' | 0 |
| PROD-05 | Stop word removal | P1 | PASS | [merged from unit] Verified: stop_words contains i,want,to,buy,a + filter pattern present | 0 |
| PROD-06 | Multi-term match boost | P1 | PASS | [merged from unit] Verified: score *= (1 + matched_keywords) for multi-term boost | 0 |
| PROD-07 | Product dedup per session | P1 | PASS | [merged from unit] p1 filtered out, p3 survived dedup | 0 |
| PROD-08 | Anti-spam cooldown | P1 | PASS | [merged from unit] gap=2 < 3 → blocked; gap=4 >= 3 → allowed | 0 |
| PROD-09 | No products for grief | P0 | PASS | products=0 (expected 0) | 8608 |
| PROD-10 | Product cards render | P0 | PASS | [merged from e2e] Passed in 9302ms | 9302 |
| RAG-01 | Hybrid search returns results | P0 | PASS | count=2, first_score=0.5340155315960362 | 433 |
| RAG-02 | Query expansion short queries | P1 | PASS | [merged from unit] Verified: _expand_query method + skip-expansion pattern in pipeline.py | 0 |
| RAG-03 | Neural reranking | P1 | PASS | [merged from unit] Verified: _rerank_results(query, results, ...) in pipeline.py | 0 |
| RAG-04 | Min similarity filtering | P0 | PASS | irrelevant_query_results=0 (expected few/0) | 323 |
| RAG-05 | Scripture filter | P1 | PASS | results=2, all_gita=True | 1100 |
| RAG-06 | Redis caching | P2 | PASS | [merged from unit] key('karma')=fe0197fd8f73, key('dharma')=0e987fbef0b3 — deterministic & unique | 0 |
| RAG-07 | Memory-mapped embeddings | P1 | PASS | embeddings.npy exists=True, size=282.4MB | 0 |
| RAG-08 | RAG unavailable handling | P0 | PASS | [merged from unit] Verified: chat.py checks rag_pipeline.available with HTTPException(500) guard | 0 |
| RAG-09 | Standalone text query | P1 | PASS | has_answer=True, has_citations=True, lang=en | 6105 |
| RAG-10 | Doc-type filter | P2 | PASS | [merged from unit] Temple doc deferred to end for EXPRESSING_EMOTION intent | 0 |
| SAFE-01 | Crisis — kill myself | P0 | PASS | has_helplines=True | 98 |
| SAFE-02 | Crisis — end my life | P0 | PASS | has_helplines=True | 154 |
| SAFE-03 | Crisis — no point living | P0 | PASS | has_helplines=True | 64 |
| SAFE-04 | Crisis — case insensitive | P0 | PASS | has_helplines=True | 59 |
| SAFE-05 | Crisis in history | P1 | PASS | history_crisis_detected=True | 60 |
| SAFE-06 | Severity signal crisis | P1 | PASS | [merged from unit] Crisis detected, helpline 9152987821 present | 0 |
| SAFE-07 | Hopelessness + severe | P1 | PASS | [merged from unit] Crisis detected for hopelessness+severe combination | 0 |
| SAFE-08 | Addiction — professional help | P0 | PASS | has_addiction_resources=True | 7206 |
| SAFE-09 | Severe mental health | P0 | PASS | has_mh_resources=True | 6873 |
| SAFE-10 | Professional help no repeat | P2 | PASS | [merged from unit] Response returned unchanged when already_mentioned=True | 0 |
| SAFE-11 | Banned — just be positive | P0 | PASS | [merged from unit] Replaced with: 'You should be gentle with yourself about this' | 0 |
| SAFE-12 | Banned — karma past life | P0 | PASS | [merged from unit] Replaced with: 'This is a challenging situation causing pain' | 0 |
| SAFE-13 | Banned — everything happens | P1 | PASS | [merged from unit] Replaced with: 'this is part of your journey' | 0 |
| SAFE-14 | Reduce scripture for distress | P1 | PASS | [merged from unit] hopelessness+severe → reduce=True, curiosity → reduce=False | 0 |
| SAFE-15 | False positive — kill non-crisis | P0 | PASS | no_false_positive=True | 5866 |
| SAFE-16 | Crisis detection disabled | P2 | PASS | [merged from unit] Crisis detection correctly disabled | 0 |
| SES-01 | Create new session | P0 | PASS | session_id=edccd0d6-c2b..., phase=listening | 518 |
| SES-02 | Get session state | P0 | PASS | phase=listening, turn_count=0 | 11 |
| SES-03 | Get non-existent session | P1 | PASS | status=404 | 27 |
| SES-04 | Delete session | P1 | PASS | delete=200, get_after=404 | 48 |
| SES-05 | Session TTL expiry | P1 | PASS | [merged from unit] Session correctly expired after backdating last_activity by 61s | 0 |
| SES-06 | Session activity refresh | P2 | PASS | [merged from unit] last_activity refreshed from 2026-03-13 08:42:57.310920 to 2026-03-13 08:42:57.361319 | 50 |
| SES-07 | Redis session backend | P1 | PASS | [merged from unit] create -> get -> update(turn=42) -> delete -> verify None | 0 |
| SES-08 | MongoDB fallback | P1 | PASS | [merged from unit] Verified: Redis->Mongo->InMemory order + create/update/get/delete lifecycle | 0 |
| SES-09 | InMemory fallback | P2 | PASS | [merged from unit] Session e9c0a19b... created and retrieved successfully | 0 |
| SES-10 | Session isolation | P0 | PASS | [merged from unit] Session A has 1 message, Session B has 0 — isolated | 0 |
| SES-11 | Session ID in localStorage | P1 | PASS | [merged from e2e] Passed in 8505ms | 8505 |
| STRM-01 | SSE connection established | P0 | PASS | events=8, has_comment=True | 6297 |
| STRM-02 | Metadata event | P0 | PASS | has_metadata=True, has_session_id=True | 0 |
| STRM-03 | Token events | P0 | PASS | token_count=5, combined_len=467 | 0 |
| STRM-04 | Done event | P0 | PASS | has_done=True, has_full_response=True | 0 |
| STRM-05 | Error event | P1 | PASS | [merged from unit] Found 3/3 error-handling patterns (event:error, except Exception, event:done) | 0 |
| STRM-06 | Typewriter animation | P1 | PASS | [merged from e2e] Passed in 6754ms | 6754 |
| STRM-07 | Typewriter cleanup | P1 | PASS | [merged from e2e] Passed in 9483ms | 9483 |
| STRM-08 | Stream fallback | P0 | PASS | [merged from unit] Verified: onError + catch + error fallback mechanism all present | 0 |
| STRM-09 | Crisis via stream | P1 | PASS | has_helpline=True | 62 |
| TTS-01 | Hindi TTS synthesis | P0 | PASS | status=200, size=12864B, type=audio/mpeg | 424 |
| TTS-02 | English TTS synthesis | P1 | PASS | status=200, size=14400B | 356 |
| TTS-03 | Text length limit | P1 | PASS | status=200, input_len=8500 | 29512 |
| TTS-04 | Empty text rejected | P1 | PASS | status=500 | 0 |
| TTS-05 | TTS unavailable | P1 | PASS | [merged from unit] Functional: created TTSService(available=False), synthesize('Hello world') -> None | 25 |
| TTS-06 | TTSButton verse playback | P1 | PASS | [merged from e2e] Passed in 8202ms | 8202 |
| TTS-07 | TTSButton full response | P2 | PASS | [merged from e2e] Passed in 9139ms | 9139 |
| UI-01 | Login page renders | P0 | PASS | [merged from e2e] Passed in 402ms | 402 |
| UI-02 | Register mode switch | P0 | PASS | [merged from e2e] Passed in 395ms | 395 |
| UI-03 | Password visibility toggle | P2 | PASS | [merged from e2e] Passed in 519ms | 519 |
| UI-04 | Error display red banner | P1 | PASS | [merged from e2e] Passed in 500ms | 500 |
| UI-05 | Loading state spinner | P1 | PASS | [merged from e2e] Passed in 457ms | 457 |
| UI-06 | Empty state welcome screen | P0 | PASS | [merged from e2e] Passed in 925ms | 925 |
| UI-07 | Header renders | P0 | PASS | [merged from e2e] Passed in 644ms | 644 |
| UI-08 | User message bubble | P0 | PASS | [merged from e2e] Passed in 629ms | 629 |
| UI-09 | Assistant message bubble | P0 | PASS | [merged from e2e] Passed in 678ms | 678 |
| UI-10 | Chat input field | P0 | PASS | [merged from e2e] Passed in 4548ms | 4548 |
| UI-11 | Input disabled during processing | P1 | PASS | [merged from e2e] Passed in 720ms | 720 |
| UI-12 | Auto-scroll to latest | P1 | PASS | [merged from e2e] Passed in 4504ms | 4504 |
| UI-13 | Verse rendering blockquote | P0 | PASS | [merged from e2e] Passed in 839ms | 839 |
| UI-14 | Streaming cursor animation | P2 | PASS | [merged from e2e] Passed in 5627ms | 5627 |
| UI-15 | Loading indicator | P1 | PASS | [merged from e2e] Passed in 4798ms | 4798 |
| UI-16 | PhaseIndicator displays | P1 | PASS | [merged from e2e] Passed in 8857ms | 8857 |
| UI-17 | Phase indicator updates | P1 | PASS | [merged from e2e] Passed in 14602ms | 14602 |
| UI-18 | Flow metadata on user message | P2 | PASS | [merged from e2e] Passed in 7655ms | 7655 |
| UI-19 | Sidebar toggle | P0 | PASS | [merged from e2e] Passed in 908ms | 908 |
| UI-20 | Sidebar conversation list | P1 | PASS | [merged from e2e] Passed in 634ms | 634 |
| UI-21 | Sidebar select conversation | P0 | PASS | [merged from e2e] Passed in 2103ms | 2103 |
| UI-22 | Sidebar new session button | P0 | PASS | [merged from e2e] Passed in 1241ms | 1241 |
| UI-23 | Sidebar user info and logout | P1 | PASS | [merged from e2e] Passed in 1114ms | 1114 |
| UI-24 | Sidebar mobile overlay | P2 | PASS | [merged from e2e] Passed in 8897ms | 8897 |
| UI-25 | Mobile viewport | P1 | PASS | [merged from e2e] Passed in 12541ms | 12541 |
| UI-26 | Tablet viewport | P2 | PASS | [merged from e2e] Passed in 864ms | 864 |
| UI-27 | Desktop viewport | P2 | PASS | [merged from e2e] Passed in 2128ms | 2128 |
| UI-28 | Thumbs up button | P1 | PASS | [merged from e2e] Passed in 8237ms | 8237 |
| UI-29 | Thumbs down button | P1 | PASS | [merged from e2e] Passed in 9705ms | 9705 |
| UI-30 | Feedback toggle | P2 | PASS | [merged from e2e] Passed in 9290ms | 9290 |
| UI-31 | Fade-in animation | P2 | PASS | [merged from e2e] Passed in 8921ms | 8921 |
| UI-32 | Scrollbar hidden | P2 | PASS | [merged from e2e] Passed in 10719ms | 10719 |
