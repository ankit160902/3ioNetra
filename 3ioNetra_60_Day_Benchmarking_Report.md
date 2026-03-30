# 3ioNetra — 60-Day Benchmarking Report (20-Day Intervals)

**Period:** Jan 29, 2026 → Mar 30, 2026 | **Total Commits:** 56 | **Version:** 1.0.0 → 1.1.3
**Live:** https://3iomitra.3iosetu.com | https://3io-netra.vercel.app
**Stack:** FastAPI + Next.js + MongoDB + Redis + Qdrant + Google Gemini 2.5 Pro

---

## Window 1: Jan 29 – Feb 18 (Days 1–20) — Foundation & Session Stability

### What Was Built
- Core session persistence (in-memory → Redis > MongoDB > InMemory fallback)
- Auth system (register, login, PBKDF2 hashing, 30-day tokens)
- Full conversational memory (UserStory, emotional arc, user quotes)
- Temple data ingestion & RAG schema definition
- Model upgrade: baseline → Gemini 3.0 Pro Preview
- 25-file cleanup removing 3,135 lines of dead documentation

### Parameters Established (Baseline)

| Parameter | Value | Notes |
|-----------|-------|-------|
| GEMINI_MODEL | gemini-3.0-pro-preview | First upgrade |
| RETRIEVAL_TOP_K | 7 | Initial setting |
| RERANK_TOP_K | 3 | Initial setting |
| MIN_SIMILARITY_SCORE | 0.15 | Permissive threshold |
| EMBEDDING_MODEL | paraphrase-multilingual-mpnet-base-v2 | 768-dim |
| RERANKER_MODEL | ms-marco-MiniLM-L-6-v2 | English-focused |
| RERANKER_WEIGHT | 0.7 | Semantic vs BM25 blend |
| SESSION_TTL_MINUTES | 60 | Session expiry |
| MIN_SIGNALS_THRESHOLD | 2 | Signals for phase transition |
| RESPONSE_MAX_TOKENS | 300 | LLM output cap |
| History Window | 4 messages (2 turns) | Context for LLM |
| MONGO_MAX_POOL_SIZE | 50 | Multi-worker setup |
| MONGO_MIN_POOL_SIZE | 5 | Idle connections |

### Benchmarks

**No formal benchmarking yet.** This window focused on getting the system functional — session bugs, Vercel deployment fixes, MongoDB serialization issues. 21 commits, mostly firefighting.

### Key Milestones
- Session persistence working (Redis + Mongo fallback)
- User auth & conversation storage
- Conversational memory (UserStory, emotional arc)
- Temple data schema defined
- Dead documentation cleanup (3,135 lines removed)

---

## Window 2: Feb 18 – Mar 10 (Days 21–40) — RAG Pipeline, Products & Latency

### What Was Built
- 118MB+ spiritual corpus embedded (hip_main.dat with 96,448 verses)
- Product catalog ingested (2,502-line products.json)
- Intent agent (9-field LLM classifier)
- Product service with recommendation throttling
- Redis integration (docker-compose, session caching)
- Prompt v4.0 (language mirroring, domain compass, few-shot examples)
- TTS button, Phase indicator UI components
- E2E test suite (Playwright), QA evaluator (731 lines), CSV evaluator (955 lines)
- 5 LLM provider backends (Claude, OpenAI, Gemini variants) for eval

### Parameters Tuned

| Parameter | Before (W1) | After (W2) | Rationale |
|-----------|-------------|------------|-----------|
| GEMINI_MODEL | gemini-3.0-pro-preview | gemini-2.0-flash | Stability + latency |
| EMBEDDING_MODEL | mpnet-base (768-dim) | **intfloat/multilingual-e5-large (1024-dim)** | 0.840 vs 0.784 validation score |
| RERANKER_MODEL | ms-marco-MiniLM-L-6-v2 | **BAAI/bge-reranker-v2-m3** | Multilingual Hindi/English |
| CANDIDATE_POOL_KEYWORD | — | 25 | New: adaptive per-intent |
| CANDIDATE_POOL_DEFAULT | — | 40 | New: adaptive per-intent |
| CANDIDATE_POOL_THEMATIC | — | 50 | New: emotional queries |
| CANDIDATE_POOL_COMPARATIVE | — | 60 | New: broad retrieval |
| PRODUCT_SESSION_CAP | — | 3 | New: throttling |
| PRODUCT_COOLDOWN_TURNS | — | 5 | New: throttling |
| PRODUCT_MIN_TURN_FOR_PROACTIVE | — | 3 | New: min turn gate |
| Prompt Version | — | 4.0 | 20 life domains, verse grounding |

### Benchmarks — First Formal Evaluation

**QA Performance Report (Mar 4 baseline):**
- Test set: 250 queries, latency verification
- `verify_rag_relevance.py` script created (86 lines)
- Retrieval accuracy testing began

**Prompt v4.0 Evaluation:**
- Response anatomy: acknowledge → substance → landing
- Domain compass: 20 life domains → specific dharmic concepts, mantras, anchors
- Language mirroring: Hindi/Hinglish/English detection

### Key Milestones
- 96,448 verses indexed with 1024-dim multilingual embeddings
- Hybrid search operational: 70% semantic + 30% BM25
- Intent-based classification (9 fields)
- Product recommendation engine with throttling
- Redis session caching deployed
- Evaluation infrastructure built (QA + CSV + intent + multi-model evaluators)

---

## Window 3: Mar 10 – Mar 30 (Days 41–60) — Production Hardening & Optimization

### What Was Built
- Retrieval judge service (552 lines) — validation gate
- Concept ontology service (554 lines) — dharmic concept mapping
- Prompt v5.0 → v5.1 → v5.2 → **v5.3** (current)
- Shared Redis pool, SSE streaming
- Lazy-loaded reranker (2.2GB memory savings)
- Response cache, HyDE, parent-child verse retrieval
- Dynamic SSE status events for frontend loading indicators
- Security fix: cross-user data leak between sessions
- Production rollback & stabilization (commit 538678d)

### Parameters Tuned

| Parameter | Before (W2) | After (W3) | Rationale |
|-----------|-------------|------------|-----------|
| GEMINI_MODEL | gemini-2.0-flash | **gemini-2.5-pro** | Quality upgrade |
| GEMINI_FAST_MODEL | — | **gemini-2.5-flash** | Intent/query expansion |
| RETRIEVAL_TOP_K | 7 | **5** | Hit@5 = Hit@7 (no accuracy loss) |
| MIN_SIMILARITY_SCORE | 0.15 | **0.28** | Stricter relevance filter |
| RERANKER_WEIGHT | 0.7 | **0.75** | Per RAKS report Section 8 |
| RESPONSE_MAX_TOKENS | 300 | **200** | Latency optimization |
| History Window | 4 messages | **8 messages** | Doubled context |
| CANDIDATE_POOL_KEYWORD | 25 | **10** | 60% reduction, faster reranking |
| CANDIDATE_POOL_DEFAULT | 40 | **15** | 60% reduction |
| CANDIDATE_POOL_THEMATIC | 50 | **20** | 60% reduction |
| CANDIDATE_POOL_COMPARATIVE | 60 | **25** | 60% reduction |
| MONGO_MAX_POOL_SIZE | 50 | **10** | Cloud Run single-worker |
| MONGO_MIN_POOL_SIZE | 5 | **1** | Minimal idle connections |
| CACHE_REDIS_DB | 1 | **0** | Cloud Run only supports DB 0 |
| READINESS_POST_GUIDANCE | — | **0.3** | New: readiness reset after guidance |
| Prompt Version | 4.0 | **5.3** | Major rewrite (see below) |

### New Parameters Introduced in W3

| Parameter | Value | Purpose |
|-----------|-------|---------|
| GEMINI_CACHE_TTL | 21600 (6h) | Context caching for system instruction |
| RESPONSE_CACHE_ENABLED | True | 5–15s savings on repeat patterns |
| RESPONSE_CACHE_TTL | 21600 (6h) | Response cache lifetime |
| RESPONSE_CACHE_SIMILARITY_THRESHOLD | 0.92 | Cache hit threshold |
| HYDE_ENABLED | True | Hypothetical document embeddings |
| HYDE_COUNT | 2 | Synthetic documents per query |
| HYDE_CACHE_TTL | 86400 (24h) | HyDE cache lifetime |
| PARENT_CHILD_ENABLED | True | Verse context expansion |
| SKIP_RERANK_THRESHOLD | 0.75 | Skip reranker if top candidate decisive |
| SKIP_RERANK_GAP | 0.15 | Gap threshold for reranker skip |
| JUDGE_MIN_SCORE | 4 | Retrieval judge quality gate |
| GROUNDING_MIN_CONFIDENCE | 0.5 | Grounding verification threshold |
| LONG_QUERY_THRESHOLD | 15 words | Trigger summarization |
| MEMORY_DEDUP_THRESHOLD | 0.85 | Cosine similarity for dedup |
| INTENT_WEIGHT_SCALE | 0.3 | Intent-based score adjustment |
| SOFT_FLOOR_RATIO | 0.75 | Dynamic min_score floor |
| TRADITION_BONUS | 0.05 | Scripture affinity boost |

### Retrieval Accuracy Benchmark (Mar 17, 2026 — 100 queries, 27 categories)

| Metric | Score |
|--------|-------|
| MRR (Mean Reciprocal Rank) | **0.900** |
| Hit@1 | **83.0%** |
| Hit@3 | **98.0%** |
| Hit@5 | **98.0%** |
| Hit@7 | **98.0%** |
| Precision@3 | **0.683** |
| Recall@3 | **0.491** |
| Recall@7 | **0.678** |
| Scripture Accuracy@3 | **73.7%** |
| Avg Latency | **1,419ms/query** |
| Pipeline Size | **96,448 verses** |
| Embedding Dim | **1024** |

### Retrieval by Language

| Language | Queries | MRR | Hit@3 | P@3 | R@3 | Scripture Acc@3 |
|----------|---------|-----|-------|-----|-----|-----------------|
| English | 56 | 0.866 | 98.2% | 0.613 | 0.454 | 76.8% |
| Hindi | 22 | 0.932 | 95.5% | 0.833 | 0.562 | 71.9% |
| Transliterated | 22 | 0.955 | 100.0% | 0.712 | 0.515 | 67.7% |

### Top-Performing Categories (MRR = 1.0)
Death, Ayurveda, Anger, Love, Soul/Atman

### Weakest Categories
Off-topic (0.0 MRR — expected), Self-worth (0.5), Parenting (0.5)

### Contamination Analysis
- Temple contamination: **0/93** non-temple queries
- Meditation template noise: **1/100** queries (pranayama edge case)

### Ablation Test Results

| Test | Finding |
|------|---------|
| min_score 0.05 → 0.25 | All equal MRR=0.875 — threshold robust |
| top_k 3 → 10 | Hit@3 plateaus at k=5 — confirms RETRIEVAL_TOP_K=5 optimal |
| Intent weighting off | MRR drops 0.875 → 0.867 — small but consistent benefit |

### QA Evaluation (Mar 18, 260 questions, 21 categories)

| Dimension | Score (/5) |
|-----------|-----------|
| Tone Match | **4.89** |
| Conversational Flow | **4.72** |
| Dharmic Integration | **4.30** |
| Overall Quality | **4.56** |
| Practice Specificity | **4.06** |
| Format Compliance | **100%** |
| Safety/Helpline Compliance | **51%** |

### Latency by Language

| Language | Avg Latency |
|----------|------------|
| English | 926.6ms |
| Transliterated | 2,010.8ms |
| Hindi | 2,079.4ms |

### Prompt Evolution: v4.0 → v5.3

| Version | Date | Key Changes |
|---------|------|-------------|
| 4.0 | ~Mar 4 | Language mirroring, 20-domain compass, few-shot examples |
| 5.0 | Mar 14 | Tag enforcement ([MANTRA]/[VERSE]), hook self-check, 2-tier helpline, banned hollow phrases |
| 5.1 | Mar 14+ | Marriage sub-scenarios, 20 edge cases |
| 5.2 | ~Mar 16 | Anger/conflict, addiction, friendship compass enrichment |
| 5.3 | Mar 26 | Marriage dharmic naming rule, global naming check, strengthened hooks, helpline format rule, expanded Tier 2 |

### Key Milestones
- Retrieval benchmark: MRR 0.900, Hit@3 98%
- QA composite score: 4.56/5
- Lazy reranker: 2.2GB memory savings
- Candidate pools: 60% reduction (no accuracy loss)
- Response cache: 5–15s savings on repeat queries
- Security: Cross-user data leak patched
- Cloud Run optimized (MongoDB pools, Redis DB, SSE timeouts)

---

## Parameter Evolution Summary (All 3 Windows)

### LLM Model Journey
```
W1: gemini-3.0-pro-preview
W2: gemini-2.0-flash
W3: gemini-2.5-pro (primary) + gemini-2.5-flash (fast)
```

### Embedding Model Journey
```
W1: paraphrase-multilingual-mpnet-base-v2 (768-dim)
W2: intfloat/multilingual-e5-large (1024-dim)  —  validation: 0.840 vs 0.784
W3: same (stable)
```

### Reranker Journey
```
W1: ms-marco-MiniLM-L-6-v2 (English, ~50ms)
W2: BAAI/bge-reranker-v2-m3 (multilingual, ~200ms)
W3: same + lazy-loaded (2.2GB memory savings at startup)
```

### RAG Retrieval Tuning

| Parameter | W1 | W2 | W3 |
|-----------|----|----|-----|
| RETRIEVAL_TOP_K | 7 | 7 | **5** |
| MIN_SIMILARITY_SCORE | 0.15 | 0.15 | **0.28** |
| RERANKER_WEIGHT | 0.7 | 0.7 | **0.75** |
| Candidate Pools | — | 25–60 | **10–25** (60% reduction) |

### Response Quality Tuning

| Parameter | W1 | W2 | W3 |
|-----------|----|----|-----|
| MAX_TOKENS | 300 | 300 | **200** |
| History Window | 4 msgs | 4 msgs | **8 msgs** |
| Prompt Version | — | v4.0 | **v5.3** |

### Infrastructure Hardening

| Parameter | W1 | W2 | W3 |
|-----------|----|----|-----|
| MongoDB Pool (max/min) | 50/5 | 50/5 | **10/1** |
| Redis DB | 0 | 0 | **0** (reverted from 1) |
| Reranker Loading | Eager | Eager | **Lazy** (2.2GB saved) |
| Caching | None | None | **Response + HyDE + RAG + Gemini context** |

---

## Domain-Scripture Affinity Map (Introduced W3)

80+ domain-to-scripture affinity pairs with boost weights:

| Domain | Primary Scripture (weight) | Secondary (weight) | Tertiary (weight) |
|--------|---------------------------|--------------------|--------------------|
| Health | Charaka Samhita (0.6) | Atharva Veda (0.3) | Patanjali Yoga (0.2) |
| Karma | Bhagavad Gita (0.4) | Patanjali Yoga (0.3) | — |
| Meditation | Patanjali Yoga (0.5) | Bhagavad Gita (0.2) | — |
| Grief | Bhagavad Gita (0.3) | Ramayana (0.3) | — |
| Anxiety | Patanjali Yoga (0.5) | Bhagavad Gita (0.3) | — |
| Depression | Bhagavad Gita (0.4) | Patanjali Yoga (0.3) | Ramayana (0.2) |
| Relationships | Ramayana (0.3) | Bhagavad Gita (0.2) | Mahabharata (0.2) |
| Parenting | Ramayana (0.4) | Mahabharata (0.2) | — |
| Self-worth | Bhagavad Gita (0.5) | Ramayana (0.2) | — |
| Anger | Bhagavad Gita (0.3) | Patanjali Yoga (0.2) | Mahabharata (0.2) |
| Addiction | Bhagavad Gita (0.4) | Patanjali Yoga (0.3) | — |

---

## Product Recommendation Throttling (Introduced W2, Tuned W3)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| PRODUCT_SESSION_CAP | 3 | Max proactive product events per session |
| PRODUCT_COOLDOWN_TURNS | 5 | Min turns between proactive events |
| PRODUCT_COOLDOWN_AFTER_REJECTION | 10 | Cooldown after user rejects products |
| PRODUCT_MIN_TURN_FOR_PROACTIVE | 3 | No products before turn 3 |
| PRODUCT_SUPPRESS_EMOTIONS | grief, despair, hopelessness, crisis, shame | Never recommend during distress |
| PRODUCT_LISTENING_PROACTIVE_ENABLED | False | Suppress in listening phase |

---

## Context Validation: 5-Gate Filter (W3)

| Gate | Threshold | Purpose |
|------|-----------|---------|
| 1. Relevance Gate | min_score = 0.28 | Drop below similarity floor |
| 2. Content Gate | min_length = 10 chars | Drop empty/placeholder text |
| 3. Type Gate | Intent-dependent | Exclude spatial docs for emotional intents |
| 4. Scripture Gate | Allowlist-based | Hard-filter to relevant scriptures |
| 5. Diversity Gate | max 2 docs/source | Prevent echo-chamber |

Dynamic relevance ratios by intent:

| Intent | Relevance Ratio |
|--------|----------------|
| EXPRESSING_EMOTION | 0.40 |
| SEEKING_GUIDANCE | 0.45 |
| ASKING_INFO | 0.55 |
| COMPARATIVE | 0.25 |
| Default | 0.50 |

---

## Safety & Compliance

| Check | Status |
|-------|--------|
| Crisis keyword detection | Active |
| Helpline numbers (iCall, Vandrevala, NIMHANS) | Required in crisis responses |
| Helpline compliance rate | 51% (area for improvement) |
| Product suppression during distress | Active |
| Cross-user data isolation | Fixed (Mar 24) |
| Distress emotions triggering extra listening | Active for: shame, grief, guilt, fear, humiliation, trauma, panic |

---

## Caching Strategy (Introduced W3)

| Cache Layer | TTL | Savings |
|-------------|-----|---------|
| Gemini Context Cache | 6 hours | Avoids re-sending system instruction |
| Response Cache | 6 hours (similarity 0.92) | 5–15s on repeat patterns |
| HyDE Cache | 24 hours | Skip hypothetical doc generation |
| RAG Search Cache | 1 hour | Skip embedding + reranking |
| Retrieval Judge Cache | 24 hours | Skip judge LLM calls |

---

## Evaluation Infrastructure

| Tool | Path | Purpose |
|------|------|---------|
| Retrieval Accuracy Test | `backend/tests/retrieval_accuracy_test.py` | 100-query benchmark (Hit@K, MRR, NDCG) |
| Benchmark Runner | `backend/tests/retrieval_benchmark_runner.py` | Unified 250-query runner with ablation |
| Hybrid RAG Benchmark | `backend/tests/benchmark_hybrid_rag.py` | Baseline vs enhanced comparison |
| QA Evaluator | `backend/tests/qa_evaluator.py` | 240-question LLM-as-judge scoring |
| CSV Dataset Evaluator | `backend/tests/csv_dataset_evaluator.py` | Bulk dataset evaluation |
| Intent Evaluator | `backend/tests/intent_evaluator.py` | Intent classification accuracy |
| Multi-Model Evaluator | `backend/tests/multi_model_evaluator.py` | Cross-model comparison |
| Prompt A/B Tester | `backend/tests/prompt_ab_tester.py` | Prompt version comparison |
| Data Quality Report | `backend/scripts/data_quality_report.py` | Verse/embedding integrity check |

---

## How to Run Benchmarks

```bash
cd backend

# Retrieval accuracy (100 queries, ~2.5 min)
python3 tests/retrieval_accuracy_test.py

# Full benchmark suite (250 queries, baseline + hybrid + ablation)
python3 tests/retrieval_benchmark_runner.py \
    --benchmark tests/benchmarks/retrieval_benchmark_250.json \
    --mode full \
    --output-dir tests/benchmark_results/

# QA evaluation (240 questions, requires Gemini API key)
python3 tests/qa_evaluator.py

# Data quality check
python3 scripts/data_quality_report.py

# Intent classification evaluation
python3 tests/intent_evaluator.py
```

---

## Current Production State (v1.1.3 — Mar 26, 2026)

| Component | Value |
|-----------|-------|
| API Version | 1.1.3 |
| Gemini Model (primary) | gemini-2.5-pro |
| Gemini Model (fast) | gemini-2.5-flash |
| Prompt Version | 5.3 |
| Embedding Model | intfloat/multilingual-e5-large (1024-dim) |
| Reranker Model | BAAI/bge-reranker-v2-m3 (lazy-loaded) |
| Pipeline Size | 96,448 verses |
| RETRIEVAL_TOP_K | 5 |
| RERANK_TOP_K | 3 |
| MIN_SIMILARITY_SCORE | 0.28 |
| MongoDB Pool | 10 max / 1 min |
| Redis DB | 0 |
| Session TTL | 60 min |
| MRR | 0.900 |
| Hit@3 | 98.0% |
| QA Composite Score | 4.56/5 |
| Avg Retrieval Latency | 1,419ms |

---

*Report generated: March 30, 2026*
*Data source: Git history (56 commits), retrieval_accuracy_results.json, qa_performance_report.md*
