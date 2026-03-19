# 3ioNetra RAG Pipeline — Complete Architecture Diagram

> Detailed end-to-end flow from user message to final response, covering every stage of retrieval, reranking, validation, and generation.

---

## End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER MESSAGE (Frontend)                         │
│              POST /api/conversation { session_id, message }            │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     COMPANION ENGINE (Orchestrator)                     │
│                  services/companion_engine.py                           │
│                                                                         │
│   ┌─────────────────────┐  asyncio.gather()  ┌──────────────────────┐  │
│   │   INTENT AGENT      │◄──────────────────►│   MEMORY SERVICE     │  │
│   │ (Gemini 2.0 Flash)  │                    │ (Semantic Recall)    │  │
│   │                     │                    │                      │  │
│   │ Output:             │                    │ Output:              │  │
│   │ • intent            │                    │ • past_memories[]    │  │
│   │ • emotion           │                    │ (cosine > 0.35)     │  │
│   │ • life_domain       │                    │                      │  │
│   │ • entities          │                    └──────────────────────┘  │
│   │ • needs_direct_ans  │                                              │
│   │ • product_keywords  │                                              │
│   └─────────┬───────────┘                                              │
│             │                                                           │
│             ▼                                                           │
│   ┌─────────────────────────────────────────────┐                      │
│   │        READINESS ASSESSMENT                  │                      │
│   │                                              │                      │
│   │  Is user ready for guidance?                 │                      │
│   │  • Direct ask? (needs_direct_answer=True)    │                      │
│   │  • Intent = SEEKING_GUIDANCE / ASKING_INFO?  │                      │
│   │  • Signals >= 2 AND turns >= 1?              │                      │
│   │  • Forced after 4 turns?                     │                      │
│   │  • Cooldown: 2+ turns since last guidance    │                      │
│   └──────────┬────────────────────┬──────────────┘                      │
│         YES  │                    │  NO                                  │
│              ▼                    ▼                                      │
│   ┌──────────────────┐  ┌──────────────────┐                           │
│   │  GUIDANCE PATH   │  │  LISTENING PATH  │                           │
│   │  (RAG + Products)│  │  (Empathetic)    │                           │
│   └────────┬─────────┘  └────────┬─────────┘                           │
└────────────┼─────────────────────┼──────────────────────────────────────┘
             │                     │
             ▼                     │
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                    ╔══════════════════════════════╗                      │
│                    ║   RAG PIPELINE (Core Search) ║                      │
│                    ║   rag/pipeline.py            ║                      │
│                    ╚══════════════════════════════╝                      │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: QUERY TRANSLATION                                      │   │
│  │                                                                  │   │
│  │  Detect Hindi/Devanagari → Gemini Flash translate → English     │   │
│  │  (24h Redis cache)                                               │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: QUERY EXPANSION                                        │   │
│  │                                                                  │   │
│  │  If query < 4 words → Gemini Flash: "generate 2 alternatives"   │   │
│  │  Result: [original, expanded_1, expanded_2]                      │   │
│  │  (24h Redis cache)                                               │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: HYBRID SEARCH (Parallel Execution)                     │   │
│  │                                                                  │   │
│  │  ┌────────────────────────┐    ┌──────────────────────────┐     │   │
│  │  │  SEMANTIC SEARCH       │    │  BM25 KEYWORD SEARCH     │     │   │
│  │  │  (70-90% weight)       │    │  (10-30% weight)         │     │   │
│  │  │                        │    │                          │     │   │
│  │  │  Model: multilingual-  │    │  rank_bm25.BM25Okapi    │     │   │
│  │  │  e5-large (1024-dim)   │    │  on 96k verse corpus    │     │   │
│  │  │                        │    │                          │     │   │
│  │  │  For each expansion:   │    │  Tokenize → score →     │     │   │
│  │  │  encode → dot product  │    │  normalize to [0,1]     │     │   │
│  │  │  with 96k embeddings   │    │                          │     │   │
│  │  │  → max across expns    │    │                          │     │   │
│  │  └───────────┬────────────┘    └────────────┬─────────────┘     │   │
│  │              │          asyncio.gather()     │                   │   │
│  │              ▼                               ▼                   │   │
│  │  ┌───────────────────────────────────────────────────────┐      │   │
│  │  │  ADAPTIVE FUSION                                      │      │   │
│  │  │                                                       │      │   │
│  │  │  If top-10 are >70% Devanagari:                      │      │   │
│  │  │    fused = 0.9 × semantic + 0.1 × BM25               │      │   │
│  │  │  Else:                                                │      │   │
│  │  │    fused = 0.8 × semantic + 0.2 × BM25               │      │   │
│  │  └───────────────────────────┬───────────────────────────┘      │   │
│  └──────────────────────────────┼───────────────────────────────────┘   │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: CANDIDATE RETRIEVAL + CURATED SLOT RESERVATION         │   │
│  │                                                                  │   │
│  │  np.argpartition → top 60 candidates by fused score             │   │
│  │                                                                  │   │
│  │  + Inject top-10 curated concept docs (if score > 0.5)          │   │
│  │    (prevents 60k Mahabharata from drowning out concept docs)    │   │
│  │                                                                  │   │
│  │  Sort merged candidates by fused score                           │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  STEP 5: NEURAL RERANKING + INTENT-BASED WEIGHTING              │   │
│  │                                                                  │   │
│  │  Model: bge-reranker-v2-m3 (CrossEncoder, multilingual)         │   │
│  │                                                                  │   │
│  │  For each candidate:                                             │   │
│  │    rerank_score = CrossEncoder.predict([query, doc.text])        │   │
│  │    norm_rerank = sigmoid(rerank_score) → [0, 1]                 │   │
│  │                                                                  │   │
│  │  Intent-Based Weighting Adjustments:                             │   │
│  │  ┌────────────────────────────────────────────────────────┐     │   │
│  │  │  1. Temple penalty:  -0.8 for non-spatial intents      │     │   │
│  │  │  2. Procedural boost: +0.3 for SEEKING_GUIDANCE        │     │   │
│  │  │  3. Temple boost:    +0.5 for ASKING_INFO + spatial    │     │   │
│  │  │  4. How-to boost:    +0.5 for procedural + how query   │     │   │
│  │  │  5. DOMAIN AFFINITY: +0.2 to +0.7 per scripture match  │     │   │
│  │  │     (33 domain→scripture mappings)                      │     │   │
│  │  │     e.g., "health" → charaka_samhita +0.6              │     │   │
│  │  │          "meditation" → patanjali_yoga_sutras +0.5      │     │   │
│  │  │          "shame" → bhagavad_gita +0.5                   │     │   │
│  │  └────────────────────────────────────────────────────────┘     │   │
│  │                                                                  │   │
│  │  Cap adjustment to [-1.0, +1.0]                                 │   │
│  │                                                                  │   │
│  │  final_score = (0.3 × semantic + 0.7 × norm_rerank)            │   │
│  │                × (1.0 + 0.3 × weighting_adjustment)             │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  STEP 6: POST-SEARCH FILTERS                                    │   │
│  │                                                                  │   │
│  │  Gate A: min_score threshold (0.12) — drop low-scoring docs     │   │
│  │  Gate B: doc_type exclusion — auto-exclude temples for non-     │   │
│  │          temple queries                                          │   │
│  │  Gate C: top_k limit — return top 7 results                     │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 │                                       │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
          ┌───────────────────────┤ (Optional: HYBRID_RAG_ENABLED)
          │                       │
          ▼                       │
┌─────────────────────────┐       │
│  RETRIEVAL JUDGE         │       │
│  (LLM-in-the-Loop)      │       │
│                          │       │
│  Complex queries only:   │       │
│  1. Decompose into       │       │
│     sub-queries          │       │
│  2. Parallel search      │       │
│  3. Merge + deduplicate  │       │
│  4. LLM judges relevance │       │
│  5. If score < 4/5:      │       │
│     rewrite & retry      │       │
└─────────────┬───────────┘       │
              │                    │
              ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    CONTEXT VALIDATOR (5-Gate Filter)                     │
│                    services/context_validator.py                         │
│                                                                         │
│  ┌─────────────┐   ┌───────────┐   ┌──────────┐   ┌──────────────┐   │
│  │ Gate 1:     │   │ Gate 2:   │   │ Gate 3:  │   │ Gate 4:      │   │
│  │ RELEVANCE   │──►│ CONTENT   │──►│ TYPE     │──►│ SCRIPTURE    │   │
│  │             │   │           │   │          │   │ (Allowlist)  │   │
│  │ Drop below  │   │ Drop empty│   │ Drop     │   │              │──►│
│  │ min_score   │   │ text, n/a │   │ temples  │   │ Filter to    │   │
│  │ or 30% of   │   │ placeholdrs│  │ for emo  │   │ allowed set  │   │
│  │ top score   │   │ <10 chars │   │ intents; │   │ (graceful    │   │
│  └─────────────┘   └───────────┘   │ drop med │   │  fallback)   │   │
│                                     │ templates│   └──────────────┘   │
│                                     │ for non- │                      │
│  ┌─────────────┐                   │ meditation│                     │
│  │ Gate 5:     │                   └──────────┘                      │
│  │ DIVERSITY   │                                                      │
│  │             │                                                      │
│  │ Max N docs  │                                                      │
│  │ per source  │                                                      │
│  │ (exempt:    │                                                      │
│  │  curated)   │                                                      │
│  └──────┬──────┘                                                      │
└─────────┼─────────────────────────────────────────────────────────────┘
          │
          ▼  context_docs (3-5 validated verses)
┌─────────────────────────────────────────────────────────────────────────┐
│                     RESPONSE COMPOSER                                    │
│                     services/response_composer.py                        │
│                                                                         │
│  Assembles final LLM prompt from:                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │ User Profile  │ │ Conversation │ │ RAG Context  │ │ Phase        │  │
│  │              │ │ History      │ │ (3-5 docs)   │ │ Instructions │  │

│  │ • name, dob  │ │              │ │              │ │              │  │
│  │ • emotion    │ │ Last 8 msgs  │ │ • scripture  │ │ From YAML:   │  │
│  │ • life_area  │ │ (4 turns)    │ │ • text       │ │ • LISTENING  │  │
│  │ • spiritual  │ │              │ │ • meaning    │ │ • GUIDANCE   │  │
│  │   profile    │ │              │ │ • quality    │ │ • CLOSURE    │  │
│  │ • panchang   │ │              │ │   rating     │ │              │  │
│  │ • memories   │ │              │ │              │ │              │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LLM SERVICE                                      │
│                         llm/service.py                                   │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐      │
│  │  System Instruction: Full persona from spiritual_mitra.yaml   │      │
│  │  (Mitra: warm spiritual friend, no markdown, flowing prose)   │      │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  Structured Prompt:                                            │     │
│  │  § WHO YOU ARE SPEAKING TO (user profile)                      │     │
│  │  § EXTRACTED FACTS & PLANS (signals, rashi, gotra)             │     │
│  │  § WHAT YOU KNOW SO FAR (emotional context)                    │     │
│  │  § RETURNING USER CHECK (if applicable)                        │     │
│  │  § CONVERSATION FLOW (last 4 turns)                            │     │
│  │  § PHASE-SPECIFIC INSTRUCTIONS (listening/guidance/closure)    │     │
│  │  § RESOURCES AVAILABLE (RAG docs with quality ratings)         │     │
│  │  § BEFORE YOU RESPOND (guardrails checklist)                   │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                         │
│  Model: Gemini 2.5 Pro (temp=0.7, thinking_budget=256)                  │
│  Via CircuitBreaker (5 failures → 60s open → half-open)                 │
│                                                                         │
│  Post-processing: clean markdown artifacts, wrap [VERSE]...[/VERSE]     │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     RESPONSE TO FRONTEND                                │
│                                                                         │
│  ConversationalResponse {                                               │
│    session_id, phase, response (text),                                  │
│    signals_collected, turn_count, is_complete,                          │
│    sources: [SourceCitation],    ← scripture references                 │
│    recommended_products: [Product],  ← shown as cards (NOT in text)     │
│    flow_metadata                                                        │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Layer

```
data/processed/
├── verses.json          96,466 verse objects (scripture, reference, text, meaning, type, topic)
│                        Types: scripture (90k), temple (4.8k), procedural (22), curated_concept (54)
│
└── embeddings.npy       96,466 × 1024 float32 (memory-mapped, pre-normalized)
                         Model: intfloat/multilingual-e5-large
```

---

## Models Used

| Model | Purpose | Where |
|-------|---------|-------|
| `intfloat/multilingual-e5-large` | Query + doc embeddings (1024-dim) | Step 3: Semantic Search |
| `bge-reranker-v2-m3` | Neural reranking (CrossEncoder) | Step 5: Reranking |
| `gemini-2.5-pro` | Main response generation | LLM Service |
| `gemini-2.0-flash` | Intent analysis, query translation/expansion | Intent Agent, Steps 1-2 |

---

## Key Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `RETRIEVAL_TOP_K` | 7 | Max results from search |
| `MIN_SIMILARITY_SCORE` | 0.12 | Minimum score gate |
| `candidates_k` | 60 | Candidates for reranking |
| `curated_slots` | 10 | Reserved slots for concept docs |
| Semantic weight | 0.3 in final score | Blended with reranker |
| Reranker weight | 0.7 in final score | Dominates final ranking |
| Intent adjustment | x0.3, capped +/-1.0 | Boosts/penalizes by type |
| `max_per_source` | 3 | Diversity gate cap |

---

## Phase State Machine

```
LISTENING ──────► GUIDANCE ──────► CLOSURE
    ▲                 │
    └── cooldown ─────┘
        (2+ turns)
```

**Transition triggers:** direct ask, signal threshold (2+ signals), forced after 4 turns, memory readiness >= 0.7

---

## Scoring Formula (Step 5)

```
rerank_score    = CrossEncoder.predict([query, doc.text])
norm_rerank     = sigmoid(rerank_score)                    # → [0, 1]
weight_adj      = sum(intent_boosts) capped to [-1.0, +1.0]

final_score     = (0.3 × semantic_score + 0.7 × norm_rerank)
                  × (1.0 + 0.3 × weight_adj)
```

### Domain Affinity Mappings (sample)

| Life Domain / Emotion | Scripture Boosted | Boost |
|----------------------|-------------------|-------|
| health, body | charaka_samhita | +0.6 |
| meditation, mindfulness | patanjali_yoga_sutras | +0.5 |
| shame, guilt | bhagavad_gita | +0.5 |
| relationships, family | ramayana | +0.4 |
| death, grief | kathopanishad | +0.5 |
| purpose, meaning | bhagavad_gita | +0.7 |
| anger, conflict | mahabharata | +0.3 |

---

## Context Validator Gates (Detail)

| Gate | What It Checks | Drop Condition |
|------|---------------|----------------|
| 1. Relevance | Score vs. threshold | Below `min_score` (0.12) OR below 30% of top score |
| 2. Content | Text quality | Empty, "n/a", placeholder, or < 10 chars |
| 3. Type | Doc type vs. intent | Temple docs for emotional intents; meditation templates for non-meditation |
| 4. Scripture | Allowlist filter | Not in allowed scripture set (graceful fallback if all filtered) |
| 5. Diversity | Source distribution | More than 3 docs from same source (curated docs exempt) |
