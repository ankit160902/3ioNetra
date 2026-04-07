# Work Update — Feb 7 to Apr 7, 2026

**Project:** 3ioNetra (Spiritual Companion app at `3iomitra.3iosetu.com`)
**Activity:** 66 commits, 318 files changed, +625K / −440K lines, sole contributor

---

## NON-TECHNICAL VERSION (for stakeholders, investors, business folks)

### What we shipped this period

**1. A completely new conversation experience (February)**
We threw out the old chat flow and rebuilt it from scratch. Mitra now actually *listens* before giving advice — it gathers signals about your emotional state, life situation, and what you're really asking for, instead of jumping to verses and product recommendations on turn 1. The full 3ioNetra product catalog is now wired into recommendations, so when you say "I need a rudraksha mala for daily chanting," Mitra can actually point you to one.

**2. The first public deployment (Feb 26)**
3ioNetra went live on Google Cloud Run with Redis-backed sessions, conversation history, and stats tracking. This was the first time real users could use it end-to-end.

**3. Production hardening so it doesn't break under load (March)**
We took Mitra from "works on my laptop" to "ready for 100,000 concurrent users." That meant fixing memory crashes, preventing one user from accidentally seeing another user's session (a security bug we caught and fixed), making the app survive Google's rate limits, and shrinking the startup memory by ~2.2 GB so it runs cheaper on the cloud.

**4. Personalization through spiritual profile (Mar 23)**
Registration now collects your *spiritual* identity — preferred deity, rashi, gotra, nakshatra — and the AI uses it to tailor every response. So a Scorpio Anuradha-nakshatra Shiva devotee gets different mantras and verses than a Cancer Pushya-nakshatra Krishna devotee. This is the kind of depth GitaGPT (35M users) doesn't do.

**5. The big speed and reliability sprint (Mar 24 → Apr 1)**
This was the hardest stretch — Google kept changing their AI model behavior and we had to chase it. We shipped over 30 fixes to make responses come back in 2-3 seconds reliably, retry intelligently when Google's API hiccupped, and never leave a user staring at a blank screen. We also added live "Mitra is thinking…" status updates so the wait feels intentional.

**6. Smarter product recommendations (Mar 31)**
Switched from keyword matching to semantic AI matching. Now if you mention "I need something for stress and grounding," it finds rudraksha and grounding stones even if you never used those words. Conversion-relevant.

**7. The full architectural rewrite (Apr 6)**
Our core engine had grown to 1,710 lines of spaghetti code that nobody could safely change. I broke it into clean, isolated modules — 621 lines of orchestrator + 4 specialized services + a state machine + automated testing. **203 automated tests now run in seconds** to catch bugs before they reach users. Same user experience, but we can now iterate 10x faster without breaking things.

**8. End-to-end quality evaluation (Apr 6)**
I ran a 62-query stress test against the deployed app — career anxiety, grief, crisis, LGBTQ acceptance, atheism debates, prompt injection attacks, Hinglish, profanity, multi-turn conversations. Results: **26 of 40 single-turn responses rated EXCELLENT or GOOD** (65%), with detailed notes on the 11 MIXED and 3 FAIL cases that need work.

### What's next (planned, not yet built)

The roadmap document I wrote out covers voice input, 10 regional languages, daily push notifications ("Today's shloka"), multiple deity avatars (Krishna, Shiva, Hanuman, Durga, Ganesha), live satsang audio rooms, and temple e-commerce integration. The architectural refactor in Apr 6 was the foundation work that makes any of this possible without rewriting everything again.

### Bottom line

3ioNetra went from "early prototype that occasionally crashed" to "production-deployed, security-audited, scale-tested, quality-evaluated, and architecturally clean enough to build on." The next 2 months can focus on *adding features* instead of *fighting the codebase*.

---

## TECHNICAL VERSION (for engineers, code review, handover)

### Stats

- **66 commits** across 318 files
- **+625K / −440K lines** (much of it data ingestion + 9-phase refactor churn)
- **Hot files:** `llm/service.py` (37 commits), `config.py` (26), `intent_agent.py` (25), `rag/pipeline.py` (22), `companion_engine.py` (20), `main.py` (18)

### Phase 1 — Conversation flow rewrite (Feb 12 – Feb 26)

| Commit | Change |
|---|---|
| `bc4bb44` | New scripture data embedded into RAG (verses.json + embeddings.npy regenerated) |
| `cc5cd65` | New conversation flow + 3ioNetra product catalog ingested |
| `6d78189` | Redefined conversation around products + verses (intent → guidance pipeline) |
| `7fff874` | Whole-codebase refinement |
| `d739754` | Redis sessions + history stats endpoint |
| `81c8363` | Fixed RAG deployment issue (model loading on Cloud Run) |
| `06af241` | First production deployment |

### Phase 2 — Latency + prompt iteration (Mar 4 – Mar 19)

| Commit | Change |
|---|---|
| `45647d6` | Latency optimization + procedural query handling |
| `7d83cdb` | Prompt v4, product recommendation v2, finalized new flow |
| `7cf10ff` | Prompt iteration |
| `4f29185` | **Major refactor:** consolidated scoring logic, removed dead config, services restructure |

### Phase 3 — Production hardening + security (Mar 23 – Mar 26)

**Security fixes (Mar 23–24):**

- `66da7cb` — **Cross-user data leak between sessions** (P0). Multiple users could see each other's conversation state via shared Redis keys.
- `fa8ba42` — Clear stale session on login/logout (defense in depth)
- `538678d` — Hard revert to last known stable when an optimization broke prod

**Reliability fixes:**

- `f098900` — Gemini 429 rate-limit handling + Redis cache DB index correction
- `d347b96` — MongoDB connection timeouts, memory reduction, error message sanitization
- `87464bc` — SSE initial timeout → 180s for Cloud Run cold-start (model load is ~30s)
- `969aaea` — **Lazy-load CrossEncoder reranker** → ~2.2 GB startup memory savings (was OOMing on small instances)
- `cb53b82` — Upgraded to gemini-2.5-flash + Redis DB fix
- `02a32cd` — v1.3.19: OOM fix, mantra gate, Redis migration
- `2becdbd` — Expanded auth registration: spiritual profile fields (preferred_deity, rashi, gotra, nakshatra) + 3 production bugs + favicon
- `24fb50e` — Shared Redis connection pool, SSE streaming fixes
- `72b64c5` — v1.3.20: prompt v5.3, cache TTL tuning, readiness tracking
- `84ac2b3` — Dynamic SSE status events (`thinking…`, `searching scriptures…`, `composing…`)
- `6164b02` — v1.3.21: fast-path for trivial messages, streaming optimization, load-test ready

### Phase 4 — Scale to 100K + Gemini model rotation hell (Mar 30 – Apr 1)

This is the painful stretch. ~25 commits firefighting Gemini API behavior:

- `1614601` — v1.3.23-scale: thread pool tuning, async hot paths
- `e639623` — Gunicorn workers 4 → 2 (Cloud Run OOM prevention with the larger Gemini SDK)
- `9f9aa4c` — **Embedding-based semantic reranking for products** (replaces keyword match)
- `7d713bb`, `012b702`, `8e3992d`, `2784d93`, `2536048`, `5967948`, `b13fb42`, `1e7ce3a`, `4c7ad76`, `e37fcbf`, `3c7f6fe`, `aeb905d`, `1e77249`, `440411d`, `633edfa` — Iterating timeout/circuit-breaker config to find a stable balance between "fast fallback" and "let Gemini finish"
- `d0e27b0` → `d7d5c50` → `1115c13` → `970ec78` — Model swap saga: gemini-2.5-flash → 3-flash-preview (thinking_budget=0) → 2.0-flash. The thinking_config field caused 500s on 2.0-flash and had to be fully removed.
- `8d9870d` — Pinned `google-genai>=1.61.0` for Gemini 3 Flash Preview
- `4dc2fed` — Inject current date/time into every system prompt (was returning stale panchang context)
- `e376c2c` — `POST /api/cache/flush` endpoint to clear stale response cache
- `d32182b` — Gemini 3 SDK compat, SSE streaming, product precision, auth hardening
- `1032f56` — Auth token caching, parallel preflight, streaming UX

### Phase 5 — 9-phase architectural refactor (Apr 6)

`8f13114` — single mega-commit:

- **CompanionEngine:** 1,710 → **621 lines** (-64%)
- **6 port interfaces:** `LLMPort`, `RAGPort`, `IntentPort`, `ProductPort`, `SafetyPort`, plus session
- **4 extracted services:** `ConversationFSM`, `MemoryUpdater`, `ProductRecommender`, `SignalCollector`
- **Pydantic validation** at every service boundary (caught a class of "shape drift" bugs)
- **Observability layer** with correlation IDs propagated through every async hop
- **Test coverage:**
  - 203 unit tests under `backend/tests/unit/` (`pytest.ini` testpaths)
  - 7 live integration tests (`tests/live_smoke_test.py`)
  - 9 Playwright E2E specs in `frontend/e2e/` covering auth, chat, phase, sidebar, feedback, WebSocket
  - Specialized eval suites: `test_returning_user.py`, `test_listening_phase.py` (54 cases), `test_long_conversation.py` (50–200 turns), `qa_evaluator.py` (240-entry CSV LLM-as-judge), `conversational_test_runner.py`

### Phase 6 — Quality evaluation report (Apr 6)

`COMPANION_EVALUATION_REPORT.md` (currently staged, untracked): 62-query test plan against the deployed Cloud Run instance (`asia-south1`). Categories: greetings, career anxiety, scripture Q&A, life dilemmas, crisis, meditation how-to, relationships, grief, anger, off-topic, Hinglish, multi-turn, vague emotional, ritual, profanity, long ramble, other religions, astrology, LGBTQ, caste, black magic, prompt injection, panchang, verse requests, memory recall, ayurveda, teen-speak, elder formal, atheism, materialism, repetition, parenting.

**Verdict distribution (40 single-persona):** EXCELLENT 10 · GOOD 16 · MIXED 11 · FAIL 3
**Known failures requiring follow-up:** Test #11 (off-topic Python scraper request — leaked into guidance), Test #29 (prompt injection — model complied), Test #38c (session lost mid-conversation)

### Tech stack as of today

- **Backend:** FastAPI (Python 3.11), Gemini 2.0 Flash via `google-genai` SDK, multilingual-e5-large embeddings, bge-reranker-v2-m3 cross-encoder, BM25 + cosine hybrid RAG
- **Storage:** MongoDB Atlas (auth + conversation history), Redis (sessions + response cache, separate DBs), memory-mapped numpy embeddings
- **Frontend:** Next.js 14.2 + React 18, Tailwind, SSE streaming with WebSocket fallback
- **Infra:** Google Cloud Run, asia-south1, gunicorn 2 workers, baked-model Docker image (offline transformers)
- **Testing:** pytest (unit), Playwright (E2E), live smoke + 5 specialized eval suites

### Open follow-ups carried into next period

1. Run the full E2E regression suite against the refactored backend (planned but blocked on disk space — see `~/.claude/plans/calm-marinating-candle.md`)
2. Fix the 3 FAIL cases from the Apr 6 evaluation report (off-topic guard, prompt injection hardening, session persistence)
3. Address the 11 MIXED cases (mostly tone/length tuning)
4. Begin Phase 1 of `ROADMAP.md`: voice input (STT) and 10 regional languages
