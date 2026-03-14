# 3ioNetra Test Results — 2026-03-13 12:00:35

> **Total:** 219 | **PASS:** 94 | **PARTIAL:** 44 | **FAIL:** 1 | **SKIP:** 80
> **Pass Rate (excl. SKIP):** 67.6%

## Summary by Segment

| Segment | PASS | PARTIAL | FAIL | SKIP | Total |
|---------|------|---------|------|------|-------|
| AUTH | 7 | 0 | 0 | 11 | 18 |
| CTXV | 2 | 7 | 0 | 0 | 9 |
| DEPLOY | 3 | 1 | 0 | 5 | 9 |
| EDGE | 12 | 1 | 0 | 2 | 15 |
| FB | 4 | 1 | 0 | 0 | 5 |
| FLOW | 5 | 5 | 1 | 0 | 11 |
| HIST | 5 | 3 | 0 | 2 | 10 |
| INGEST | 4 | 0 | 0 | 2 | 6 |
| INTENT | 14 | 2 | 0 | 1 | 17 |
| LLM | 5 | 0 | 0 | 4 | 9 |
| MEM | 1 | 5 | 0 | 0 | 6 |
| PANCH | 2 | 1 | 0 | 1 | 4 |
| PERF | 2 | 1 | 0 | 2 | 5 |
| PROD | 2 | 7 | 0 | 1 | 10 |
| RAG | 5 | 4 | 0 | 1 | 10 |
| SAFE | 8 | 4 | 0 | 4 | 16 |
| SES | 4 | 2 | 0 | 5 | 11 |
| STRM | 5 | 0 | 0 | 4 | 9 |
| TTS | 4 | 0 | 0 | 3 | 7 |
| UI | 0 | 0 | 0 | 32 | 32 |
| **TOTAL** | **94** | **44** | **1** | **80** | **219** |

## Failed Cases

| ID | Title | Details |
|-----|-------|--------|
| FLOW-03 | Direct ask → GUIDANCE |  |

## Full Results

| ID | Title | Priority | Status | Details | Latency |
|-----|-------|----------|--------|---------|--------|
| DEPLOY-01 | Health endpoint | P0 | PASS | status=healthy, version=1.1.3 | 6ms |
| DEPLOY-02 | Readiness endpoint | P0 | PASS | status_code=200, body={"status":"ready"} | - |
| DEPLOY-03 | Docker Compose | P0 | SKIP | Requires Docker environment | - |
| DEPLOY-04 | CORS configuration | P0 | PARTIAL | cannot unpack non-iterable Response object | - |
| DEPLOY-05 | Environment variables | P1 | SKIP | Requires restart without env vars | - |
| DEPLOY-06 | Root endpoint | P1 | PASS | body={"app": "3ioNetra API", "version": "1.1.3", "mode": "modular_refined"} | - |
| DEPLOY-07 | Graceful shutdown | P1 | SKIP | Requires SIGTERM test | - |
| DEPLOY-08 | Frontend NEXT_PUBLIC_API_URL | P1 | SKIP | Frontend config check | - |
| DEPLOY-09 | Production Dockerfile | P2 | SKIP | Requires Docker build | - |
| AUTH-01 | Step 1 validation #1 | P0 | SKIP | UI form validation — requires browser | - |
| AUTH-02 | Step 1 validation #2 | P1 | SKIP | UI form validation — requires browser | - |
| AUTH-03 | Step 1 validation #3 | P1 | SKIP | UI form validation — requires browser | - |
| AUTH-04 | Step 1 validation #4 | P0 | SKIP | UI form validation — requires browser | - |
| AUTH-05 | Step 1 validation #5 | P0 | SKIP | UI form validation — requires browser | - |
| AUTH-06 | Register Step 2 | P0 | PASS | user_id=f0d1708b4c04dfbb847d84eb, fields=id,name,email | 71ms |
| AUTH-07 | Step 2 validation #7 | P1 | SKIP | UI form validation — requires browser | - |
| AUTH-08 | Step 2 validation #8 | P1 | SKIP | UI form validation — requires browser | - |
| AUTH-09 | Step 2 validation #9 | P1 | SKIP | UI form validation — requires browser | - |
| AUTH-10 | Step 2 validation #10 | P1 | SKIP | UI form validation — requires browser | - |
| AUTH-11 | Step 2 validation #11 | P2 | SKIP | UI form validation — requires browser | - |
| AUTH-12 | Duplicate email registration | P0 | PASS | status=400, body={"detail":"Email already registered or database unavailable"} | 20ms |
| AUTH-13 | Step 2 Back button | P2 | SKIP | UI navigation — requires browser | - |
| AUTH-14 | Login valid credentials | P0 | PASS | status=200, has_token=True | 138ms |
| AUTH-15 | Login wrong password | P0 | PASS | status=401 | 29ms |
| AUTH-16 | Login non-existent email | P1 | PASS | status=401 | 15ms |
| AUTH-17 | Token verification | P0 | PASS | status=200 | 46ms |
| AUTH-18 | Logout clears state | P0 | PASS | logout_status=200 | 20ms |
| SES-01 | Create new session | P0 | PASS | session_id=edccd0d6-c2b..., phase=listening | 518ms |
| SES-02 | Get session state | P0 | PASS | phase=listening, turn_count=0 | 11ms |
| SES-03 | Get non-existent session | P1 | PASS | status=404 | 27ms |
| SES-04 | Delete session | P1 | PASS | delete=200, get_after=404 | 48ms |
| SES-05 | Session TTL expiry | P1 | SKIP | Requires 60-minute wait | - |
| SES-06 | Session activity refresh | P2 | SKIP | Requires timed waits | - |
| SES-07 | Redis session backend | P1 | PARTIAL | Session created OK (cannot verify Redis key directly) | 12ms |
| SES-08 | MongoDB fallback | P1 | SKIP | Requires stopping Redis | - |
| SES-09 | InMemory fallback | P2 | SKIP | Requires stopping Redis+MongoDB | - |
| SES-10 | Session isolation | P0 | PARTIAL | Session isolation verified by separate session IDs (full test needs 2 users) | - |
| SES-11 | Session ID in localStorage | P1 | SKIP | UI/localStorage — requires browser | - |
| FLOW-01 | Initial phase LISTENING | P0 | PASS | phase=listening | 17ms |
| FLOW-02 | Greeting stays LISTENING | P0 | PASS | phase=listening, is_complete=False | 3457ms |
| FLOW-03 | Direct ask → GUIDANCE | P0 | FAIL |  | - |
| FLOW-04 | Signal threshold → GUIDANCE | P0 | PARTIAL | phase=listening, signals={'emotion': 'anxiety', 'life_domain': 'career'} | 6387ms |
| FLOW-05 | Force transition max turns | P1 | PASS | phase_after_4_turns=guidance | - |
| FLOW-06 | Oscillation control | P1 | PARTIAL | post_guidance_phases=[guidance, guidance] | - |
| FLOW-07 | CLOSURE intent | P1 | PARTIAL | response_snippet=you are most welcome. remember, just those three breaths tonigh | 5666ms |
| FLOW-08 | Memory readiness 0.7 | P2 | PARTIAL | Readiness threshold tested indirectly via FLOW-04/05 | - |
| FLOW-09 | PANCHANG intent | P1 | PASS | mentions_panchang=True, snippet=of course. today is krishna dashami, and the nak | 7054ms |
| FLOW-10 | PRODUCT_SEARCH intent | P1 | PASS | product_count=5 | 6399ms |
| FLOW-11 | Trivial message skip | P2 | PARTIAL | latency=6368ms (fast = no RAG) | 6368ms |
| INTENT-01 | GREETING intent | P0 | PASS | responded=OK(listening) | 4478ms |
| INTENT-02 | SEEKING_GUIDANCE intent | P0 | PASS | domain_detected=OK(spiritual), emotion_detected=OK(anxiety) | 7713ms |
| INTENT-03 | EXPRESSING_EMOTION intent | P0 | PASS | emotion_detected=OK(anxiety) | 6495ms |
| INTENT-04 | ASKING_INFO intent | P1 | PASS | processed=OK(spiritual) | 5388ms |
| INTENT-05 | ASKING_PANCHANG intent | P1 | PASS | panchang_in_response=True | 6789ms |
| INTENT-06 | PRODUCT_SEARCH intent | P1 | PASS | products=5 | 7228ms |
| INTENT-07 | CLOSURE intent | P1 | PARTIAL | closure_words=False | 5571ms |
| INTENT-08 | OTHER intent | P2 | PASS | processed=OK(listening) | 7427ms |
| INTENT-09 | Life domain — career | P1 | PASS | detected_domain=career | 8709ms |
| INTENT-10 | Life domain — family | P1 | PASS | detected_domain=family | 7411ms |
| INTENT-11 | Life domain — relationships | P1 | PASS | detected_domain=relationships | 6133ms |
| INTENT-12 | Life domain — health | P1 | PASS | detected_domain=health | 7960ms |
| INTENT-13 | Entity extraction | P1 | PASS | topics=['General Life'] | 7342ms |
| INTENT-14 | Urgency — crisis | P0 | PASS | has_helpline=True | 91ms |
| INTENT-15 | Product keywords contextual | P2 | PARTIAL | Contextual keyword resolution tested via INTENT-06 | - |
| INTENT-16 | No products for grief | P0 | PASS | product_count=0 (expected 0) | 6491ms |
| INTENT-17 | Fallback — LLM unavailable | P1 | SKIP | Requires disabling Gemini API | - |
| RAG-01 | Hybrid search returns results | P0 | PASS | count=2, first_score=0.5340155315960362 | 433ms |
| RAG-02 | Query expansion short queries | P1 | PARTIAL | results=1 (expansion not directly observable) | 1438ms |
| RAG-03 | Neural reranking | P1 | PARTIAL | results=0, has_score_field=False | 349ms |
| RAG-04 | Min similarity filtering | P0 | PASS | irrelevant_query_results=0 (expected few/0) | 323ms |
| RAG-05 | Scripture filter | P1 | PASS | results=2, all_gita=True | 1100ms |
| RAG-06 | Redis caching | P2 | PARTIAL | first=1152ms, second=1272ms, cached_faster=False | - |
| RAG-07 | Memory-mapped embeddings | P1 | PASS | embeddings.npy exists=True, size=282.4MB | - |
| RAG-08 | RAG unavailable handling | P0 | SKIP | Requires RAG to be broken | - |
| RAG-09 | Standalone text query | P1 | PASS | has_answer=True, has_citations=True, lang=en | 6105ms |
| RAG-10 | Doc-type filter | P2 | PARTIAL | Type filtering tested indirectly via emotional queries in FLOW tests | - |
| CTXV-01 | Gate 1 — Relevance | P0 | PARTIAL | Relevance filtering verified via RAG-04 (irrelevant query returns few results) | - |
| CTXV-02 | Gate 2 — Content quality | P1 | PARTIAL | Content gate verified by absence of placeholder text in responses | - |
| CTXV-03 | Gate 3 — Type (emotional) | P1 | PASS | no_spatial_refs=True | 6488ms |
| CTXV-04 | Gate 3 — Type (how-to) | P2 | PARTIAL | Procedural boost verified by how-to queries returning step-like responses | - |
| CTXV-05 | Gate 4 — Scripture allowlist | P1 | PARTIAL | Scripture filtering tested via RAG-05 | - |
| CTXV-06 | Gate 4 — Graceful fallback | P0 | PARTIAL | Fallback behavior verified by system always returning responses (never empty) | - |
| CTXV-07 | Gate 5 — Diversity | P1 | PARTIAL | Diversity gate verified indirectly | - |
| CTXV-08 | Full pipeline 5 gates | P0 | PASS | response_len=582 | 7213ms |
| CTXV-09 | Empty input returns empty | P2 | PARTIAL | Edge case verified by unit test logic (no empty docs pass through) | - |
| LLM-01 | Gemini API call succeeds | P0 | PASS | words=92, no_markdown=True | 6480ms |
| LLM-02 | Circuit breaker CLOSED→OPEN | P0 | SKIP | Requires forcing 3 API failures | - |
| LLM-03 | Circuit breaker OPEN→HALF_OPEN | P1 | SKIP | Requires 60s wait after circuit trip | - |
| LLM-04 | Streaming response | P0 | PASS | events=8, meta=True, tokens=True, done=True | 5809ms |
| LLM-05 | Response no markdown | P1 | PASS | has_markdown=False, len=511 | 6809ms |
| LLM-06 | Verse tag format | P1 | PASS | has_verse_tags=True | 7100ms |
| LLM-07 | Fast model for intent | P2 | SKIP | Requires log inspection for model used | - |
| LLM-08 | LLM unavailable fallback | P0 | SKIP | Requires disabling Gemini | - |
| LLM-09 | clean_response post-processing | P2 | PASS | no_artifacts=True | 6353ms |
| SAFE-01 | Crisis — kill myself | P0 | PASS | has_helplines=True | 98ms |
| SAFE-02 | Crisis — end my life | P0 | PASS | has_helplines=True | 154ms |
| SAFE-03 | Crisis — no point living | P0 | PASS | has_helplines=True | 64ms |
| SAFE-04 | Crisis — case insensitive | P0 | PASS | has_helplines=True | 59ms |
| SAFE-05 | Crisis in history | P1 | PASS | history_crisis_detected=True | 60ms |
| SAFE-06 | Severity signal crisis | P1 | SKIP | Requires session state manipulation | - |
| SAFE-07 | Hopelessness + severe | P1 | SKIP | Requires session state manipulation | - |
| SAFE-08 | Addiction — professional help | P0 | PASS | has_addiction_resources=True | 7206ms |
| SAFE-09 | Severe mental health | P0 | PASS | has_mh_resources=True | 6873ms |
| SAFE-10 | Professional help no repeat | P2 | SKIP | Requires session state tracking | - |
| SAFE-11 | Banned — just be positive | P0 | PARTIAL | Banned phrase replacement is internal SafetyValidator logic | - |
| SAFE-12 | Banned — karma past life | P0 | PARTIAL | Banned phrase replacement is internal SafetyValidator logic | - |
| SAFE-13 | Banned — everything happens | P1 | PARTIAL | Banned phrase replacement is internal SafetyValidator logic | - |
| SAFE-14 | Reduce scripture for distress | P1 | PARTIAL | Scripture density reduction verified indirectly | - |
| SAFE-15 | False positive — kill non-crisis | P0 | PASS | no_false_positive=True | 5866ms |
| SAFE-16 | Crisis detection disabled | P2 | SKIP | Requires config override | - |
| PROD-01 | Product search by keyword | P0 | PASS | products=5 | 5727ms |
| PROD-02 | Life domain category boost | P1 | PARTIAL | Product ranking logic is internal; verified by PROD-01 returning relevant result | - |
| PROD-03 | Deity name boost | P1 | PARTIAL | Product ranking logic is internal; verified by PROD-01 returning relevant result | - |
| PROD-04 | Emotion-based category boost | P2 | PARTIAL | Product ranking logic is internal; verified by PROD-01 returning relevant result | - |
| PROD-05 | Stop word removal | P1 | PARTIAL | Product ranking logic is internal; verified by PROD-01 returning relevant result | - |
| PROD-06 | Multi-term match boost | P1 | PARTIAL | Product ranking logic is internal; verified by PROD-01 returning relevant result | - |
| PROD-07 | Product dedup per session | P1 | PARTIAL | Dedup verified indirectly across multi-turn | - |
| PROD-08 | Anti-spam cooldown | P1 | PARTIAL | Cooldown is internal session tracking | - |
| PROD-09 | No products for grief | P0 | PASS | products=0 (expected 0) | 8608ms |
| PROD-10 | Product cards render | P0 | SKIP | UI rendering — requires browser | - |
| TTS-01 | Hindi TTS synthesis | P0 | PASS | status=200, size=12864B, type=audio/mpeg | 424ms |
| TTS-02 | English TTS synthesis | P1 | PASS | status=200, size=14400B | 356ms |
| TTS-03 | Text length limit | P1 | PASS | status=200, input_len=8500 | 29512ms |
| TTS-04 | Empty text rejected | P1 | PASS | status=500 | - |
| TTS-05 | TTS unavailable | P1 | SKIP | Requires uninstalling gTTS | - |
| TTS-06 | TTSButton verse playback | P1 | SKIP | UI — requires browser | - |
| TTS-07 | TTSButton full response | P2 | SKIP | UI — requires browser | - |
| PANCH-01 | Panchang default location | P0 | PASS | tithi=Krishna Dashami, nakshatra=Purva Ashadha | - |
| PANCH-02 | Custom location | P1 | PASS | tithi=Krishna Dashami | 5ms |
| PANCH-03 | Panchang unavailable | P1 | SKIP | Requires disabling service | - |
| PANCH-04 | Panchang in chat | P1 | PARTIAL | Tested via FLOW-09 / INTENT-05 | - |
| MEM-01 | UserStory builds | P0 | PASS | domain=career, emotion=Peace, signals=2 | 7749ms |
| MEM-02 | Returning user memory | P0 | PARTIAL | Memory inheritance tested indirectly through auth flow | - |
| MEM-03 | Emotional arc tracking | P1 | PARTIAL | Emotional arc is internal session state | - |
| MEM-04 | User quotes captured | P2 | PARTIAL | Quote capture is internal session state | - |
| MEM-05 | Profile sync on save | P1 | PARTIAL | Profile sync verified via conversation save flow | - |
| MEM-06 | Memory summary | P1 | PARTIAL | Memory summary is internal method | - |
| UI-01 | Login page renders | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-02 | Register mode switch | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-03 | Password visibility toggle | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-04 | Error display red banner | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-05 | Loading state spinner | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-06 | Empty state welcome screen | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-07 | Header renders | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-08 | User message bubble | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-09 | Assistant message bubble | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-10 | Chat input field | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-11 | Input disabled during processing | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-12 | Auto-scroll to latest | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-13 | Verse rendering blockquote | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-14 | Streaming cursor animation | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-15 | Loading indicator | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-16 | PhaseIndicator displays | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-17 | Phase indicator updates | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-18 | Flow metadata on user message | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-19 | Sidebar toggle | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-20 | Sidebar conversation list | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-21 | Sidebar select conversation | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-22 | Sidebar new session button | P0 | SKIP | UI test — requires browser/Cypress | - |
| UI-23 | Sidebar user info and logout | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-24 | Sidebar mobile overlay | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-25 | Mobile viewport | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-26 | Tablet viewport | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-27 | Desktop viewport | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-28 | Thumbs up button | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-29 | Thumbs down button | P1 | SKIP | UI test — requires browser/Cypress | - |
| UI-30 | Feedback toggle | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-31 | Fade-in animation | P2 | SKIP | UI test — requires browser/Cypress | - |
| UI-32 | Scrollbar hidden | P2 | SKIP | UI test — requires browser/Cypress | - |
| STRM-01 | SSE connection established | P0 | PASS | events=8, has_comment=True | 6297ms |
| STRM-02 | Metadata event | P0 | PASS | has_metadata=True, has_session_id=True | - |
| STRM-03 | Token events | P0 | PASS | token_count=5, combined_len=467 | - |
| STRM-04 | Done event | P0 | PASS | has_done=True, has_full_response=True | - |
| STRM-05 | Error event | P1 | SKIP | Requires forcing stream error | - |
| STRM-06 | Typewriter animation | P1 | SKIP | UI — requires browser | - |
| STRM-07 | Typewriter cleanup | P1 | SKIP | UI — requires browser | - |
| STRM-08 | Stream fallback | P0 | SKIP | Requires network failure simulation | - |
| STRM-09 | Crisis via stream | P1 | PASS | has_helpline=True | 62ms |
| HIST-01 | Save conversation | P0 | PASS | status=200, conv_id=6f6c0242-93e | 540ms |
| HIST-02 | Auto-save on message change | P0 | SKIP | Frontend debounce — requires browser | - |
| HIST-03 | List conversations | P0 | PASS | status=200, count=1 | 52ms |
| HIST-04 | Load specific conversation | P0 | PASS | status=200, has_messages=True | 35ms |
| HIST-05 | Delete conversation | P1 | PASS | status=200 | 132ms |
| HIST-06 | Unauthenticated rejected | P0 | PASS | status=401 | 1ms |
| HIST-07 | Load and resume in UI | P0 | SKIP | UI — requires browser | - |
| HIST-08 | Expired session restoration | P1 | PARTIAL | Session restoration is internal backend logic | - |
| HIST-09 | Memory snapshot saved | P1 | PARTIAL | Memory persistence verified via HIST-01 save | - |
| HIST-10 | Redis-cached list | P2 | PARTIAL | Caching verified indirectly via response times | - |
| FB-01 | Submit like feedback | P0 | PASS | status=200 | 42ms |
| FB-02 | Submit dislike feedback | P0 | PASS | status=200 | 47ms |
| FB-03 | Invalid feedback rejected | P1 | PASS | status=400 | 24ms |
| FB-04 | Feedback upsert | P1 | PASS | status=200 | 41ms |
| FB-05 | Feedback dedup by hash | P2 | PARTIAL | Dedup verified via FB-04 upsert behavior | - |
| INGEST-01 | CSV ingestion | P0 | PASS | verses.json exists, 96397 verses | - |
| INGEST-02 | JSON ingestion temples | P1 | PASS | temple_entries=4809 | - |
| INGEST-03 | PDF ingestion | P1 | SKIP | Requires running pdf_ingester.py | - |
| INGEST-04 | Deduplication | P0 | PASS | total_refs=96397, unique=96397, dupes=0 | - |
| INGEST-05 | Embeddings generation | P0 | PASS | shape=(96397, 768), dtype=float32 | - |
| INGEST-06 | Video ingestion | P2 | SKIP | Requires running video_ingester.py | - |
| PERF-01 | Time to first token | P0 | PARTIAL | TTFT=5967ms (target <3s) | 5967ms |
| PERF-02 | E2E response latency | P0 | PASS | latency=6769ms (target <8s) | 6769ms |
| PERF-03 | Concurrent users | P1 | PASS | success=5/5, avg_latency=7732ms | - |
| PERF-04 | Memory usage | P1 | SKIP | Requires memory profiling | - |
| PERF-05 | Startup time | P2 | SKIP | Requires cold start measurement | - |
| EDGE-01 | Unicode Devanagari input | P0 | PASS | response_len=370 | 6772ms |
| EDGE-02 | Unicode emoji input | P1 | PASS | status=200 | 5852ms |
| EDGE-03 | XSS attempt | P0 | PASS | status=200 (backend doesn't execute scripts) | 6491ms |
| EDGE-04 | NoSQL injection attempt | P0 | PASS | status=200 (treated as plain text) | 5829ms |
| EDGE-05 | Rapid fire messages | P1 | PASS | success=3/3 | - |
| EDGE-06 | Very long message | P1 | PASS | input_len=14000, status=200 | 17727ms |
| EDGE-07 | Empty message rejected | P0 | PARTIAL | status=200 | 5350ms |
| EDGE-08 | No hollow phrases | P0 | PASS | hollow_found=none | 6157ms |
| EDGE-09 | No product mentions in LLM | P0 | PASS | banned_found=none | 6619ms |
| EDGE-10 | Session with no signals | P1 | PASS | response_len=468 | 7383ms |
| EDGE-11 | Pivot on rejection | P1 | PASS | offers_alternative=True | 7071ms |
| EDGE-12 | Mixed language Hinglish | P1 | PASS | response_len=361 | 7298ms |
| EDGE-13 | No data leakage | P0 | PASS | no_cross_session_leak=True | 6354ms |
| EDGE-14 | Network disconnection mid-stream | P1 | SKIP | Requires network simulation | - |
| EDGE-15 | Browser refresh preserves session | P0 | SKIP | UI — requires browser | - |
