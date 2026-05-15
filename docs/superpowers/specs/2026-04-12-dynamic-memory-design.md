# Dynamic Memory System for Mitra

**Date:** 2026-04-12
**Branch:** `dev`
**Status:** Design approved — ready for `writing-plans`
**Related docs:**
- Response-mode spec: `2026-04-11-practical-spiritual-balance-design.md`
- Response-mode E2E test report: `2026-04-12-e2e-test-report.md`

---

## 1 · Problem

The 3ioNetra companion ("Mitra") feels static across conversations. Users describe it as "not actually like a companion — it doesn't remember important things the way you and ChatGPT do." The goal is to give Mitra a **dynamically growing memory** that:

1. Remembers what's important to each user
2. Only surfaces memories when they actually help
3. Evolves over time as the user's spiritual journey evolves
4. Feels like a friend who remembers you, not a surveillance system logging facts about you
5. Still reinforces Mitra's identity as a **spiritual companion rooted in Sanatan Dharma**, not a generic LLM assistant

This is the next major feature after the response-mode system (shipped 2026-04-11/12).

## 2 · The discovery — the current system is not "static," it's not writing at all

During exploration, the critical finding was that **`memory_service.store_memory()` is never called anywhere in the codebase.**

- The method exists, embeds text, and upserts to MongoDB correctly.
- `retrieve_relevant_memories()` IS called on every turn and IS injected into the LLM prompt as `past_memories`.
- But it reads from a collection that nothing writes to. For almost every user, `past_memories` returns an empty list — the prompt section stays blank.

Related dead-code findings:
- `UserStory.trigger_event` and `UserStory.unmet_needs` — defined, serialized, **never populated**
- `ConversationMemory.add_user_quote()` and `ConversationMemory.record_emotion()` — exist, **never called**
- `conversations.conversation_summary` MongoDB field — exists, **rarely set**
- **Zero user-facing memory endpoints** — no way for a user to see, edit, or delete what's remembered about them

The symptom "feels static" is a half-built feature whose bones are in place but whose muscles were never attached. The good news: most of the plumbing we need already exists. We're wiring it up, not rebuilding from scratch.

## 3 · What top LLM products actually do — research summary

Research covered ChatGPT Memory, Claude Memory Tool + Projects, Character.ai, Replika, Pi, and the major papers (MemGPT/Letta, Generative Agents, Mem0, Zep/Graphiti). The consensus architecture for 2025-2026 companion-grade memory:

1. **Two-layer split: relational + episodic.** A small always-in-context **relational profile** (who the user is to the companion) + an **episodic memory stream** (individual facts, retrieved on relevance). ChatGPT, Claude, Character.ai, Nomi, Pi all use some variant.
2. **Nobody does live vector search per turn** — not even OpenAI. ChatGPT pre-computes summaries and injects them directly. Live retrieval per turn is considered too slow, too noisy, too latency-sensitive.
3. **LLM-as-extractor, not keyword rules.** Mem0, MemGPT, Generative Agents, ChatGPT all use an LLM to decide what's worth remembering. Heuristic keyword extraction is universally deprecated.
4. **Writes are asynchronous, post-response.** Never block the user's reply on memory extraction. Queue it after the stream closes.
5. **Mem0's ADD / UPDATE / DELETE / NOOP pattern** is the gold-standard contradiction handling. When a new fact arrives, retrieve top-k similar existing memories and ask the LLM to decide the operation. Only published technique that reliably prevents the "Replika forgets my correction" failure mode.
6. **Generative Agents' scoring function** — `score = recency × importance × relevance` with exponential recency decay — is the cleanest principled ranking. Importance is LLM-assigned at write time.
7. **Zep's bi-temporal validity** — mark memories `invalid_at` instead of hard-deleting. Preserves provenance forever and is essential for emotional evolution ("was grieving in March, healing now").
8. **Reflection / consolidation** — periodic LLM pass that turns low-level events into high-level insights. This is the single most cited technique for making memory feel HUMAN rather than database-like. Generative Agents triggered reflection on a 150-importance-point threshold.
9. **User-visible memory panel is table stakes.** Every major product exposes what's remembered with edit/delete. GDPR and trust both demand it.
10. **Warm ≠ surveillance.** The companions that feel warmest frame memory as "I remember you," not "I log facts about you." The difference is mostly in HOW memories are surfaced, not how they're stored.

## 4 · Goals and constraints

### Goals
1. Mitra remembers what matters about each user across sessions
2. Memory surfaces only when it helps; practical-first queries aren't cluttered with unrelated past facts
3. Contradictions are handled gracefully — corrections supersede old facts without destroying provenance
4. The memory system feels warm and relationship-y, not like a database
5. Users can see, edit, and delete every memory Mitra holds about them
6. Crisis content is handled with care — never referenced verbatim, used only to bias tone
7. The memory system reinforces Mitra's spiritual-companion identity, not dilutes it

### Hard constraints
- **NO hardcoded keyword lists** for extraction, importance, or sensitivity
- **NO hardcoded policy rules** — all salience decisions are LLM-driven
- **NO numeric caps on memory count** — retention is LLM-decided during reflection, not cut off at an arbitrary number
- **NO synchronous memory writes** — extraction never blocks the user response
- **NO verbatim crisis content** stored anywhere — crisis hooks write meta-facts only
- **NO new services** in the architectural sense — everything rides inside the existing `IntentAgent → CompanionEngine → LLMService → ResponseComposer` pipeline
- **NO frontend work** in this sprint — backend API only; UI panel is a clean follow-up
- **The only hardcoded safety floor** in the entire system is `importance ≥ 8` memories are never auto-pruned. This is a gate, not a policy.

## 5 · Differentiation — what makes Mitra's memory different from ChatGPT's

ChatGPT memory is excellent at productivity recall ("user is a software engineer in Berlin, prefers concise code examples"). It's poor at emotional continuity because its extraction prompt is optimized for facts, not for relationship.

Mitra's differentiation comes from five choices that a generic assistant wouldn't make:

1. **Dharma as reasoning spine in the extraction prompt.** The extractor doesn't just list facts — it's instructed to recognize spiritual journey markers (practices started/stopped, deities, concerns about meaning, emotional arcs, devotion patterns) as equally worth remembering as practical facts.
2. **Tone-aware retrieval.** A grief memory only surfaces when the current turn's tone is grief-adjacent. ChatGPT doesn't tone-filter — it injects everything the user "liked the Lakers" worthy of injection. For a spiritual companion, this is the difference between tact and clumsiness.
3. **Crisis memory as meta-fact, never verbatim.** Mitra's crisis path writes "on April 10, user had a crisis moment; helplines provided; user continued engaging" — a flag that biases tone going forward without exposing the specific words. No generic assistant would invest in this.
4. **Reflection emphasizes spiritual journey.** When Mitra consolidates episodic memories into the profile, the prompt asks Gemini to write a second-person narrative about the user's spiritual arc, not a list of preferences. The profile feels like a friend's mental model, not a CRM record.
5. **Everything is user-visible via `/api/memory`.** The user can see, edit, and delete every memory with full provenance ("from your April 3 session, turn 4"). This is the difference between trust and surveillance.

## 6 · Approach — two-layer memory with async writes and LLM-driven everything

**One architecture, three timelines that never block each other:**

1. **Synchronous (user-visible):** user message → memory read (profile always, episodic on-demand + mode-gated) → LLM → response stream. Zero added latency.
2. **Asynchronous post-response:** fire-and-forget task runs memory extraction + Mem0 update decision + MongoDB writes after the response stream closes. User never waits.
3. **Periodic (reflection):** threshold-triggered background task consolidates episodic memories into the relational profile and prunes stale ones. No scheduler, event-driven only.

### 6.1 · The two layers

- **Relational Profile** (per user, 1 MongoDB doc, always in prompt). Slowly-evolving narrative + structured fields (spiritual themes, ongoing concerns, tone preferences, people mentioned). Updated by reflection, not per-turn writes. Target size: 400-600 tokens narrative + ~200 tokens of structured fields = ~800 tokens total.
- **Episodic Memory Stream** (per user, N MongoDB docs, retrieved on-demand). Individual facts with importance, sensitivity, tone, bi-temporal validity. The existing `user_memories` collection, finally used. Retrieved top-3 only when the response mode benefits.

### 6.2 · Mode-gated retrieval

The episodic retrieval respects the response-mode system from `2026-04-11-practical-spiritual-balance-design.md`:

| Mode | Episodic retrieval |
|---|---|
| `practical_first` | Skip entirely — practical queries don't need life-history context |
| `presence_first` (turn ≤ 2) | Skip — user needs presence, not evidence |
| `presence_first` (turn > 2) | Run with tone-aware filtering |
| `teaching` | Run — spiritual questions benefit from past context |
| `exploratory` | Run if life_domain is known |
| `closure` | Skip — closure is a door closing softly, not a moment for evidence |

**The profile loads on EVERY turn regardless of mode.** That's the always-on warmth layer. Only the episodic retrieval is mode-gated.

---

## 7 · Architecture & data flow

```
┌────────────────────────────────────────────────────────────────┐
│  SYNCHRONOUS PATH  —  user-blocking, identical latency profile │
└────────────────────────────────────────────────────────────────┘

 User message
    │
    ▼
┌──────────────────────────┐
│ IntentAgent  (unchanged) │
└──────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────────────────┐
│ MemoryReader  (extends memory_service.py)             │
│                                                        │
│ 1. Load user_profile from user_profiles collection    │
│    (always — Redis-cached 5 min)                      │
│                                                        │
│ 2. Score episodic memories via                         │
│      recency_decay × importance × relevance           │
│    Filter by sensitivity tier + tone alignment         │
│    Return top-3                                        │
│                                                        │
│ 3. Return (relational_profile, episodic_memories)     │
└───────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│ ResponseComposer → LLMService         │
│ profile → user_profile["relational_   │
│            profile"]  (always-in-    │
│            context, ~800 tokens)      │
│ episodic → user_profile["past_        │
│            memories"]  (top-3)        │
└──────────────────────────────────────┘
    │
    ▼
Gemini → response → user
    │
    └─── fire-and-forget task dispatched ───┐
                                              │
                                              ▼
┌────────────────────────────────────────────────────────────────┐
│ ASYNC POST-RESPONSE PATH — never blocks the user              │
└────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ MemoryExtractor  (new, in memory_extractor.py)│
│                                               │
│ Gemini call #1 — EXTRACT                     │
│  Input: user turn + assistant response        │
│         + current relational profile          │
│  Output: 0..N facts, each with:               │
│    • text                                     │
│    • importance (1-10)                        │
│    • sensitivity                              │
│      (trivial|personal|sensitive|crisis)      │
│    • tone_marker                              │
│  If output is 0 facts, stop here              │
└─────────────────────────────────────────────┘
    │
    ▼ (for each extracted fact)
┌─────────────────────────────────────────────┐
│ MemoryUpdater  (new, in memory_updater.py)    │
│                                               │
│ 1. Retrieve top-5 similar existing memories  │
│                                               │
│ 2. Gemini call #2 — DECIDE                    │
│    Input: new fact + top-5 similar            │
│    Output: ADD | UPDATE | DELETE | NOOP       │
│                                               │
│ 3. Execute decision on MongoDB                │
│    (bi-temporal: set invalid_at, no hard     │
│     delete — provenance preserved)            │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ ReflectionTrigger                            │
│                                               │
│ Σ new_importance_since_last_reflection       │
│    > threshold (~30 points)                  │
│  → dispatch reflection task                   │
└─────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ PERIODIC REFLECTION PATH — background consolidation           │
└────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ ReflectionService  (new, in reflection_svc.py)│
│                                               │
│ Gemini call — REFLECT + PRUNE                 │
│  Input: last 20 episodic memories             │
│         + current relational profile          │
│  Output:                                       │
│    • updated relational_narrative             │
│    • updated structured fields                 │
│    • list of memory IDs to invalidate         │
│  Write: user_profiles + user_memories         │
└─────────────────────────────────────────────┘
```

### Where each piece lives in the codebase

| Component | File | Status |
|---|---|---|
| MemoryReader | `backend/services/memory_service.py` | EXTENDS existing |
| MemoryExtractor | `backend/services/memory_extractor.py` | NEW |
| MemoryUpdater | `backend/services/memory_updater.py` | NEW |
| ReflectionService | `backend/services/reflection_service.py` | NEW |
| Memory router | `backend/routers/memory.py` | NEW |
| Extraction output models | `backend/models/llm_schemas.py` | EXTENDS |
| Relational profile dataclass | `backend/models/memory_context.py` | EXTENDS |
| Fire-and-forget dispatch | `backend/routers/chat.py` | EXTENDS |
| Crisis meta-fact hook | `backend/services/companion_engine.py` | EXTENDS |
| Memory prompts | `backend/prompts/spiritual_mitra.yaml` | EXTENDS — new `memory_prompts` section |

No new services in the architectural sense. Three new helper modules inside `backend/services/`, one new router, one new top-level YAML key. Everything else is an extension of existing code.

---

## 8 · Storage schema

### 8.1 · `user_memories` collection (extends existing)

Existing collection preserved. New fields have sensible defaults so old documents remain readable.

```yaml
user_memories:                    # existing, extended
  _id: ObjectId                   # becomes memory_id in the API
  user_id: string                 # (existing)
  text: string                    # (existing) — fact in natural language
  embedding: [float]              # (existing) — 1024-dim vector

  importance: int                 # NEW — 1-10, LLM-assigned at extraction
  sensitivity: string             # NEW — trivial | personal | sensitive | crisis
  tone_marker: string             # NEW — single dominant tone word

  valid_at: datetime              # NEW — when the fact became true
  invalid_at: datetime | null     # NEW — null = still valid; never hard-delete
                                  #       unless user explicitly asks

  provenance:                     # NEW
    session_id: string
    conversation_id: string | null
    turn_number: int

  source: string                  # NEW — extracted | manual_user_add
                                  #       | reflection_insight | migration_backfill

  last_accessed_at: datetime | null  # NEW — set on retrieval for access boost
  access_count: int               # NEW — starts 0

  created_at: datetime            # (existing, becomes datetime not string)
```

**Indexes:**
- `(user_id, 1), (invalid_at, 1)` — primary lookup, filters out invalidated
- `(user_id, 1), (importance, -1)` — top-k by importance
- `(user_id, 1), (sensitivity, 1)` — tier-aware filter

**No numeric cap.** Retention is LLM-driven during reflection (see §9). A once-a-day garbage collector hard-deletes records that are `invalid_at > 1 year ago AND importance < 5`. Nothing important gets auto-pruned — the only hardcoded safety floor in the system is `importance ≥ 8` memories never get auto-pruned.

### 8.2 · `user_profiles` collection (new)

One document per user. Always loaded. Redis-cached.

```yaml
user_profiles:                    # NEW
  _id: ObjectId
  user_id: string                 # unique

  relational_narrative: string    # 400-600 tokens, written by reflection

  spiritual_themes: [string]      # up to 10
  ongoing_concerns: [string]      # up to 10
  tone_preferences: [string]      # up to 10
  people_mentioned: [string]      # up to 10

  prior_crisis_flag: bool
  prior_crisis_context: string | null   # single-line meta-fact, no verbatim
  prior_crisis_count: int

  last_reflection_at: datetime | null
  importance_since_reflection: int      # running sum for threshold trigger
  reflection_count: int

  created_at: datetime
  updated_at: datetime
```

**Indexes:**
- `(user_id, 1)` — unique

**Redis cache:**
- Key: `user_profile:{user_id}`
- TTL: 5 minutes
- Invalidated on any profile write (reflection, crisis hook, manual edit)

**Size validation:**
- `relational_narrative` hard-capped at 800 tokens at write time
- Each list field capped at 10 items

### 8.3 · Pydantic models (`backend/models/llm_schemas.py` extensions)

```python
class ExtractedMemory(BaseModel):
    """One fact extracted from a single user turn."""
    text: str
    importance: int                                 # 1-10, validator clamps
    sensitivity: Literal[
        "trivial", "personal", "sensitive", "crisis"
    ]
    tone_marker: str = "neutral"

    @field_validator("importance", mode="before")
    def _clamp(cls, v):
        try: return max(1, min(10, int(v)))
        except: return 5

class ExtractionResult(BaseModel):
    facts: List[ExtractedMemory] = Field(default_factory=list)

class MemoryUpdateDecision(BaseModel):
    operation: Literal["ADD", "UPDATE", "DELETE", "NOOP"]
    target_memory_id: Optional[str] = None
    updated_text: Optional[str] = None
    reason: str = ""

class ReflectionResult(BaseModel):
    updated_profile: "ReflectionProfilePatch"
    prune_ids: List[str] = Field(default_factory=list)

class ReflectionProfilePatch(BaseModel):
    relational_narrative: str
    spiritual_themes: List[str] = Field(default_factory=list)
    ongoing_concerns: List[str] = Field(default_factory=list)
    tone_preferences: List[str] = Field(default_factory=list)
    people_mentioned: List[str] = Field(default_factory=list)
```

All get tolerant-coercion — bad LLM output defaults to safe values.

### 8.4 · Dataclass (`backend/models/memory_context.py` extension)

```python
@dataclass
class RelationalProfile:
    user_id: str
    relational_narrative: str = ""
    spiritual_themes: List[str] = field(default_factory=list)
    ongoing_concerns: List[str] = field(default_factory=list)
    tone_preferences: List[str] = field(default_factory=list)
    people_mentioned: List[str] = field(default_factory=list)
    prior_crisis_flag: bool = False
    prior_crisis_context: Optional[str] = None
    prior_crisis_count: int = 0
    last_reflection_at: Optional[datetime] = None
    importance_since_reflection: int = 0
    reflection_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_prompt_text(self) -> str:
        """Render the profile as the text block injected into the LLM prompt.

        Narrative first, structured fields as chips below, crisis flag as a
        gentle note at the top if set. Never includes verbatim crisis content.
        """
        ...

    def to_dict(self) -> Dict: ...

    @classmethod
    def from_dict(cls, d: Dict) -> "RelationalProfile": ...

    def apply_reflection(self, patch: "ReflectionProfilePatch") -> "RelationalProfile":
        """Merge a ReflectionResult patch into a new profile instance."""
        ...
```

### 8.5 · Migration and indexes

**No hard migration required.** Old `user_memories` docs without new fields work via safe defaults (`importance=5`, `sensitivity="personal"`, `valid_at=created_at`, `invalid_at=null`).

Index creation runs on first startup:

```python
# In memory_service.py::initialize
await db.user_memories.create_index([("user_id", 1), ("invalid_at", 1)])
await db.user_memories.create_index([("user_id", 1), ("importance", -1)])
await db.user_memories.create_index([("user_id", 1), ("sensitivity", 1)])
await db.user_profiles.create_index([("user_id", 1)], unique=True)
```

---

## 9 · Write pipeline — extraction + Mem0 update decision

### 9.1 · Dispatch point

Two existing call paths in `routers/chat.py` get a fire-and-forget dispatch:

**`chat_sync`** (around line 600, after `_postprocess_and_save`):
```python
asyncio.create_task(dispatch_memory_extraction(
    user_id=session.memory.user_id,
    session_id=session.session_id,
    conversation_id=meta.get("conversation_id"),
    turn_number=session.turn_count,
    user_message=query.message,
    assistant_response=response_text,
    intent_analysis=meta.get("analysis"),
))
return ConversationalResponse(...)
```

**`chat_stream`** (around line 745, after the streaming loop closes):
```python
full_response = "".join(full_text_parts)
asyncio.create_task(dispatch_memory_extraction(
    user_id=session.memory.user_id,
    session_id=session.session_id,
    conversation_id=meta.get("conversation_id"),
    turn_number=session.turn_count,
    user_message=query.message,
    assistant_response=full_response,
    intent_analysis=meta.get("analysis"),
))
yield f"event: done\ndata: {json.dumps({...})}\n\n"
```

Both use the shared helper `dispatch_memory_extraction()` in `memory_extractor.py`.

**Gating inside the helper:**
- Anonymous sessions (no user_id) → no-op
- Trivial intents (GREETING, CLOSURE, OFF_TOPIC) → no-op
- Otherwise → spawn the `_extract_with_timeout` task

### 9.2 · MemoryExtractor — Gemini call #1

**Input:** user turn + Mitra's response + current relational profile (loaded from 5-min Redis cache).

**Output:** `ExtractionResult` containing 0-N `ExtractedMemory` facts.

**Prompt:** `memory_prompts.extract` in `spiritual_mitra.yaml` (pattern matches `mode_prompts`). Key instructions:

- *"BE SPARSE BY DEFAULT. Most turns produce zero facts. A typical good turn produces 0-2 facts. Never more than 3. If uncertain, err toward extracting nothing."*
- Importance scale explicitly anchored: 1-3 trivial preference, 4-6 normal life fact, 7-8 significant, 9-10 defining.
- Sensitivity tiers explicitly defined with examples.
- Crisis-tier facts explicitly instructed to summarize as meta-facts only, never verbatim.
- Tone marker constrained to a single word.

**Model:** `gemini-2.0-flash` (fast model). Cost ~$0.0001 per call.

### 9.3 · MemoryUpdater — Gemini call #2 (per extracted fact)

For each fact returned by the extractor:

1. Embed the new fact via `rag_pipeline.generate_embeddings()`
2. Retrieve top-5 similar still-valid memories (cosine similarity over `user_memories` where `invalid_at IS NULL`)
3. Gemini call #2 with the new fact + top-5 similar → ADD / UPDATE / DELETE / NOOP decision
4. Execute the decision on MongoDB with bi-temporal semantics

**Prompt:** `memory_prompts.update_decision` in `spiritual_mitra.yaml`.

**Operation semantics:**
- **ADD** — new memory, insert as fresh row
- **UPDATE** — target memory is superseded; set `invalid_at=now` on the old record AND insert the new merged text as a fresh row
- **DELETE** — target memory is no longer true; set `invalid_at=now` on the old record; do NOT insert the new text (the new text is a correction, not a fact to preserve)
- **NOOP** — redundant; no write; bump `access_count` on the target memory

**Safety default:** any error in decision parsing → `ADD`. Safer to duplicate than to accidentally delete.

**Reflection counter bump:** after ADD or UPDATE, the profile's `importance_since_reflection` is incremented by the new fact's importance. When the counter crosses the threshold, reflection is dispatched.

### 9.4 · Error handling

| Failure | Behavior |
|---|---|
| Gemini returns invalid JSON for extraction | Log warning, treat as empty, continue |
| Gemini returns error for extraction | Log warning, abort this turn |
| Embedding generation fails | Log warning, abort this turn |
| Gemini returns invalid JSON for update decision | Log warning, default to ADD |
| MongoDB write fails | Log warning, memory lost (response already went out) |
| Task times out (30s hard cap) | Log warning, cancel |

All errors caught in `_extract_with_timeout`. None propagate to the user.

### 9.5 · Async task management

```python
async def dispatch_memory_extraction(...):
    if not user_id: return
    if intent in ("GREETING", "CLOSURE", "OFF_TOPIC"): return
    task = asyncio.create_task(_extract_with_timeout(...))
    task.add_done_callback(_log_task_exceptions)

async def _extract_with_timeout(...):
    try:
        async with asyncio.timeout(30):
            await _do_extraction_and_updates(...)
    except asyncio.TimeoutError:
        logger.warning(f"Memory extraction timed out for user={user_id}")
    except Exception as exc:
        logger.warning(
            f"Memory extraction failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
```

No process-level concurrency cap. At current load, simultaneous extraction tasks across users are fine. Add a semaphore later if needed.

---

## 10 · Read pipeline — scoring, tier filter, injection

### 10.1 · Profile load — always on

```python
async def load_relational_profile(user_id: str) -> RelationalProfile:
    if not user_id:
        return RelationalProfile(user_id="")
    cache = get_cache_service()
    cached = await cache.get("user_profile", key=user_id)
    if cached:
        return RelationalProfile.from_dict(cached)
    doc = await db.user_profiles.find_one({"user_id": user_id})
    profile = RelationalProfile.from_dict(doc) if doc else RelationalProfile(user_id=user_id)
    await cache.set("user_profile", profile.to_dict(), key=user_id, ttl=300)
    return profile
```

Empty profile for new users renders as empty string in the prompt — no crash, no noise.

### 10.2 · Episodic retrieval — mode-gated + scored + tier-filtered

```python
async def retrieve_episodic(
    user_id: str,
    query: str,
    response_mode: str,
    analysis: Dict,
    session: SessionState,
) -> List[ScoredMemory]:
    skip = (
        response_mode in ("practical_first", "closure")
        or (response_mode == "presence_first" and session.turn_count <= 2)
    )
    if skip:
        return []

    query_emb = await rag_pipeline.generate_embeddings(query)
    cursor = db.user_memories.find({
        "user_id": user_id,
        "invalid_at": None,
    })
    memories = await cursor.to_list(length=None)
    if not memories:
        return []

    current_tone = _infer_current_tone(analysis, response_mode)
    scored = []
    now = datetime.utcnow()

    for m in memories:
        if m["sensitivity"] == "sensitive":
            if not _tone_aligned(m["tone_marker"], current_tone):
                continue
        if m["sensitivity"] == "crisis":
            continue  # defensive — crisis never lives in user_memories

        score = _score_memory(m, query_emb, now)
        scored.append(ScoredMemory(memory=m, score=score))

    scored.sort(key=lambda sm: sm.score, reverse=True)
    top = scored[: settings.MEMORY_MAX_RESULTS]
    top = [sm for sm in top if sm.score >= settings.MEMORY_MIN_SCORE]

    asyncio.create_task(_bump_access([sm.memory["_id"] for sm in top]))
    return top
```

### 10.3 · Scoring function

Generative-Agents-style ranking. All weights tunable in `config.py`.

```python
def _score_memory(memory: dict, query_embedding: np.ndarray, now: datetime) -> float:
    last_seen = memory.get("last_accessed_at") or memory.get("valid_at") or memory["created_at"]
    days = max(0.0, (now - last_seen).total_seconds() / 86400)
    raw_recency = math.exp(-math.log(2) * days / settings.MEMORY_HALF_LIFE_DAYS)

    importance = memory.get("importance", 5)
    if importance >= settings.MEMORY_IMPORTANCE_FLOOR_THRESHOLD:  # default 8
        recency = max(raw_recency, settings.MEMORY_IMPORTANCE_FLOOR_VALUE)  # default 0.3
    else:
        recency = raw_recency

    importance_norm = (importance / 10.0) ** 1.5   # slight superlinear

    mem_emb = np.array(memory["embedding"], dtype=np.float32)
    relevance = float(np.dot(query_embedding, mem_emb))

    return (
        settings.MEMORY_WEIGHT_RECENCY * recency
        + settings.MEMORY_WEIGHT_IMPORTANCE * importance_norm
        + settings.MEMORY_WEIGHT_RELEVANCE * relevance
    )
```

**Config defaults:**

```python
MEMORY_HALF_LIFE_DAYS = 30
MEMORY_IMPORTANCE_FLOOR_THRESHOLD = 8
MEMORY_IMPORTANCE_FLOOR_VALUE = 0.3
MEMORY_WEIGHT_RECENCY = 0.5
MEMORY_WEIGHT_IMPORTANCE = 1.0
MEMORY_WEIGHT_RELEVANCE = 1.0
MEMORY_MAX_RESULTS = 3
MEMORY_MIN_SCORE = 0.4
```

These are ranking mechanics on top of LLM-decided inputs. The LLM chose the importance number, sensitivity tier, and tone marker. The formula just ranks by what the LLM already said.

### 10.4 · Tone-aware filtering

```python
_TONE_FAMILIES = {
    "heavy":      {"grief", "despair", "anxiety", "overwhelm", "confusion", "shame", "fear"},
    "recovering": {"resolve", "healing", "hope", "relief"},
    "warm":       {"gratitude", "joy", "devotion", "curiosity"},
    "neutral":    {"neutral", ""},
}

def _tone_aligned(memory_tone: str, current_tone: str) -> bool:
    if not memory_tone or not current_tone:
        return False
    for family in _TONE_FAMILIES.values():
        if memory_tone in family and current_tone in family:
            return True
    return False

def _infer_current_tone(analysis: dict, response_mode: str) -> str:
    emotion = (analysis.get("emotion") or "").lower()
    if emotion and emotion != "neutral":
        return emotion
    return {
        "presence_first": "heavy",
        "teaching": "curiosity",
        "exploratory": "confusion",
        "closure": "gratitude",
        "practical_first": "neutral",
    }.get(response_mode, "neutral")
```

Sensitive memories require a same-family tone match to be retrieved. Personal and trivial memories have no tone filter.

The tone families live in `config.py` as an editable dict, not hardcoded constants.

### 10.5 · Prompt injection

The reader returns two things to `CompanionEngine.process_message_preamble`:

```python
result = await memory_reader.load_and_retrieve(
    user_id=user_id, query=message, response_mode=analysis.get("response_mode"),
    analysis=analysis, session=session,
)
user_profile = build_user_profile(session.memory, session)
user_profile["relational_profile"] = result.profile.to_prompt_text()
user_profile["past_memories"] = [sm.memory["text"] for sm in result.episodic]
```

In the LLM prompt, these render as two distinct sections:

```
═══════════════════════════════════════════════════════════
WHO YOU ARE SPEAKING TO — THE RELATIONSHIP SO FAR:
═══════════════════════════════════════════════════════════
{relational_profile_text}     ← always present if profile exists

═══════════════════════════════════════════════════════════
SPECIFIC THINGS YOU REMEMBER THAT MATTER TO THIS MOMENT:
═══════════════════════════════════════════════════════════
{past_memories_rendered}      ← present only when mode allows
                                retrieval AND top-k returned
                                something above the score floor
```

**Two sections intentionally.** Profile = warmth and continuity (Mitra-knows-who-you-are). Episodic = evidence and specificity (Mitra-remembers-this-specific-thing). A friend does both. The profile is the mental model; the episodic memories are the receipts.

### 10.6 · Access boost (recall strengthens memory)

Every retrieved memory gets `last_accessed_at = now` and `access_count += 1` via a fire-and-forget update. Memories the user keeps coming back to stay fresh; memories that fade stay faded.

---

## 11 · Reflection and pruning

### 11.1 · When it fires

Threshold-triggered. After each successful ADD/UPDATE in the MemoryUpdater, the profile's `importance_since_reflection` counter is incremented by the new fact's importance. When the counter crosses `settings.REFLECTION_THRESHOLD` (default 30), a reflection task is dispatched via `asyncio.create_task()`.

**No scheduler.** No cron, no APScheduler, no background worker. Event-driven only.

### 11.2 · What it does

Single Gemini call (using `gemini-2.5-flash` for slightly higher consolidation quality — affordable at this frequency). Three jobs in one prompt:

1. **Consolidate** the relational profile — update the narrative and structured fields based on recent episodic memories.
2. **Prune** — identify stale / superseded / irrelevant memories and return their IDs for invalidation.
3. **Safety lock** — explicit instruction to never include verbatim crisis content in the narrative. Crisis awareness lives on `prior_crisis_flag` only.

**Prompt:** `memory_prompts.reflect` in `spiritual_mitra.yaml`.

**Execution:**

```python
async def run_reflection(user_id: str) -> None:
    profile = await load_relational_profile(user_id)
    memories = await db.user_memories.find({
        "user_id": user_id, "invalid_at": None,
    }).sort("valid_at", -1).limit(settings.REFLECTION_EPISODIC_WINDOW).to_list(None)

    prompt = prompt_manager.get_prompt(
        "spiritual_mitra", "memory_prompts.reflect",
    ).format(
        current_profile_to_prompt_text=profile.to_prompt_text() or "(no profile yet)",
        memories_block=_format_memories_for_reflection(memories),
    )

    result = await llm_service.complete_json(
        prompt, model=settings.REFLECTION_MODEL,
        response_schema=ReflectionResult,
    )

    updated = profile.apply_reflection(result.updated_profile)
    updated.last_reflection_at = datetime.utcnow()
    updated.importance_since_reflection = 0
    updated.reflection_count += 1
    await db.user_profiles.update_one(
        {"user_id": user_id},
        {"$set": updated.to_dict()},
        upsert=True,
    )
    await cache.delete("user_profile", key=user_id)

    # Prune — LLM-driven, with hardcoded safety floor
    if result.prune_ids:
        await db.user_memories.update_many(
            {"_id": {"$in": result.prune_ids}, "importance": {"$lt": 8}},
            {"$set": {"invalid_at": datetime.utcnow()}},
        )
```

**The `importance < 8` filter on prune is the only hardcoded safety floor in the entire system.** Even if the LLM accidentally suggests pruning a high-importance memory, we refuse. This is a gate, not a policy.

### 11.3 · Failure handling

Failed reflection does not corrupt the profile. The reflection is atomic — it only writes when the full result is valid. If Gemini returns invalid JSON or the task times out, the profile stays unchanged and the counter isn't reset, so reflection will try again on the next write.

---

## 12 · API surface — `backend/routers/memory.py`

All endpoints require authentication via the existing `get_current_user` dependency.

```python
# GET /api/memory
#   Returns all valid memories for the current user + the relational profile.
#   Response: MemoryListResponse { memories: [...], total: int, profile: ... }

# GET /api/memory/profile
#   Returns just the relational profile.
#   Response: RelationalProfileResponse

# POST /api/memory
#   User manually adds a memory.
#   Body: { text: str, importance: int = 5, sensitivity: str = "personal" }
#   Skips Gemini extraction, goes straight to embedding + insert.
#   Response: MemoryListItem

# PATCH /api/memory/{id}
#   Edit text or sensitivity of an existing memory.
#   Body: { text?: str, sensitivity?: str }
#   Response: MemoryListItem

# DELETE /api/memory/{id}?hard=false
#   Soft delete by default (sets invalid_at).
#   ?hard=true hard-deletes. Documented but default is soft.
#   Response: { deleted: bool, memory_id: str }

# DELETE /api/memory?before=2026-03-01
#   Batch invalidate all memories created before a date.
#   Response: { invalidated_count: int }

# POST /api/memory/profile/reset
#   Reset the relational profile to empty. Requires explicit confirmation.
#   Body: { confirm: true }
#   Response: { reset: bool }
```

**Provenance in every GET response.** Users can audit "when did I tell you this?" with full confidence.

**Soft-delete by default.** Nothing is ever silently destroyed. Hard-delete requires the `?hard=true` flag.

---

## 13 · Testing strategy

Four tiers, offline-first.

### 13.1 · Tier 1 — Unit tests (offline, no LLM)

```
backend/tests/unit/test_memory_reader.py
  - Scoring function with fixture memories
  - Importance floor for importance >= 8
  - Recency decay shape (30-day half-life)
  - Tone-aware filter (grief↔grief matches, grief↔joy doesn't)
  - Mode-gate skip (practical_first/closure skip, teaching runs)
  - Top-k cut + absolute score floor

backend/tests/unit/test_memory_updater.py
  - ADD path
  - UPDATE path: old invalidated, new inserted
  - DELETE path: target invalidated, no new insert
  - NOOP path: no changes, access_count bump
  - Bi-temporal invariant: nothing hard-deletes automatically
  - Defensive fallback: bad LLM output → ADD

backend/tests/unit/test_memory_extractor.py
  - Mocked Gemini output parsed via Pydantic
  - Unknown sensitivity → "personal"
  - Importance clamped to 1-10
  - Empty extraction is a valid result
  - Crisis-tier extraction does NOT write to user_memories

backend/tests/unit/test_relational_profile.py
  - to_prompt_text renders correctly
  - Crisis flag renders as bias note, never verbatim
  - Empty profile returns empty string
  - apply_reflection merges fields correctly

backend/tests/unit/test_memory_api.py
  - GET /api/memory auth required
  - DELETE soft vs hard
  - POST manual add skips extraction
  - PATCH updates only allowed fields
```

### 13.2 · Tier 2 — Integration tests (offline, mocked LLM)

```
backend/tests/integration/test_memory_pipeline.py
  - Full turn flow: message → mocked extraction → mocked update →
    memory in MongoDB → next turn retrieves it
  - Mode gating end-to-end: practical_first skips retrieval + extraction
    still runs (memories still get written, just not used for that turn)
  - Crisis path: crisis short-circuit fires the meta-fact writer, sets
    prior_crisis_flag, does NOT write verbatim to user_memories
  - Bi-temporal: UPDATE operation preserves the invalidated record
```

### 13.3 · Tier 3 — Integration tests (live Gemini, opt-in)

```
backend/tests/integration/test_memory_live.py
  - Skipped unless GEMINI_API_KEY is set
  - 10 representative turns covering every sensitivity tier
  - Property-based assertions: facts-count in expected range, sensitivity
    classification correct, tone_marker in a known family
```

### 13.4 · Tier 4 — Dev smoke script

```
backend/scripts/compare_memory_responses.py
  - Runs a series of messages against a live server
  - After each turn, dumps: relational profile, top-k retrieved,
    new extractions, Mem0 decisions
  - Dev tool for eyeballing long-conversation memory behavior
```

Not a merge gate. The user decides when it looks right.

---

## 14 · Rollout and cold start

### 14.1 · Existing users with conversation history

On first login after deployment, a one-time backfill task runs in the background:

```python
if user.conversation_count > 0 and not await _has_profile(user.user_id):
    asyncio.create_task(_backfill_memory(user.user_id))

async def _backfill_memory(user_id: str) -> None:
    recent_convos = await conversation_storage.get_conversations_list(
        user_id, limit=settings.BACKFILL_CONVERSATION_COUNT   # default 10
    )
    for convo in recent_convos:
        full = await conversation_storage.get_conversation(user_id, convo["id"])
        turns = _pair_user_and_assistant_turns(full["messages"])
        for user_turn, assistant_turn in turns:
            await _extract_and_store(
                user_id=user_id,
                session_id=convo["session_id"],
                conversation_id=convo["id"],
                turn_number=...,
                user_message=user_turn,
                assistant_response=assistant_turn,
                intent_analysis={"intent": "OTHER"},
                source="migration_backfill",
            )
    await run_reflection(user_id)
```

**Cost estimate:** ~10 convos × ~10 turns × $0.0002 + 1 reflection × $0.002 ≈ $0.022 per user. 1000 users ≈ $22 one-time.

**Rate-limited:** 1 extraction per second per user to avoid a login-burst Gemini hammer.

### 14.2 · Brand new users

Empty profile, empty memories. First 3-5 sessions populate the profile naturally via reflection firing on the importance threshold.

### 14.3 · Failure handling

Partial backfill is fine. The memories that were already written stay. Next reflection pass fixes any inconsistency.

---

## 15 · Risks and mitigations

### Risk 1 — Extraction is too aggressive, memory fills with noise

**Likelihood:** Medium. Gemini tends toward being helpful and may extract too generously.

**Mitigation:**
- Extraction prompt explicitly says "BE SPARSE BY DEFAULT. Most turns produce 0 facts."
- Scoring function's `MEMORY_MIN_SCORE` floor filters out weak retrievals at query time.
- Reflection pass prunes stale memories based on LLM judgment.
- Hard safety floor: `importance >= 8` never gets auto-pruned.

### Risk 2 — Contradictions accumulate because Mem0 decision picks NOOP too often

**Likelihood:** Medium. The update decision is a subtle judgment and Gemini may be too cautious.

**Mitigation:**
- Prompt explicitly frames UPDATE as the right choice when the user's situation evolves.
- Bi-temporal model means nothing is lost even if NOOP is chosen — the old memory stays, and a future reflection can clean up.
- Tier 4 dev smoke script is designed to catch accumulation patterns.

### Risk 3 — Crisis meta-fact gets written multiple times (prior_crisis_count inflation)

**Likelihood:** Low. The crisis short-circuit fires once per crisis turn.

**Mitigation:**
- `prior_crisis_count` is a real counter — inflation is actually desirable for tone biasing
- `prior_crisis_context` is a single line that gets overwritten on each new crisis, not appended

### Risk 4 — Relational profile becomes too long over time (growing past 800 tokens)

**Likelihood:** Medium. Reflection could produce increasingly elaborate narratives.

**Mitigation:**
- Hard 800-token cap enforced at profile write time.
- Reflection prompt explicitly targets 400-600 tokens for the narrative.
- Each list field capped at 10 items.
- If a reflection output exceeds caps, oldest items in each list are dropped.

### Risk 5 — Gemini API cost escalates unexpectedly

**Likelihood:** Low. Extraction is gated on intent and bounded per-turn.

**Mitigation:**
- Extractor uses `gemini-2.0-flash` at ~$0.0001/call — very cheap
- Reflection uses `gemini-2.5-flash` but only fires on threshold (rare)
- `cost_tracker` tracks memory-pipeline cost per user per day
- If a user's memory cost exceeds a daily budget, extraction is disabled for that user until the next day — add a soft cap later if needed (not in MVP)

### Risk 6 — The read pipeline adds latency

**Likelihood:** Low. Profile load is Redis-cached (sub-ms); episodic retrieval is numpy cosine (sub-ms for <10k memories).

**Mitigation:**
- Mode-gating skips retrieval entirely for half the turns
- Access boost update is fire-and-forget, never blocks
- No regression from the current `retrieve_relevant_memories` performance profile

### Risk 7 — Reflection runs at a bad time (user in the middle of an important moment)

**Likelihood:** Very low. Reflection is background-dispatched and doesn't block anything.

**Mitigation:**
- `asyncio.create_task()` means reflection never blocks the user
- Even if reflection fails mid-run, the profile is unchanged (atomic writes)
- Worst case: reflection runs again on the next threshold crossing

---

## 16 · Out of scope (explicit)

- **No frontend UI.** Backend-only this sprint. The `/api/memory` endpoints are designed so a future UI is a clean follow-up with zero schema changes.
- **No graph memory.** Flat facts + a good profile are enough for the use case.
- **No cross-user memory inference.** No "other users with similar concerns…" — each user's memory is siloed forever.
- **No fine-tuning on user memory.** Gemini stays frozen.
- **No encryption at rest beyond MongoDB defaults.** Memory content is no more sensitive than conversations, which already live in MongoDB without custom encryption.
- **No automated alerts or trends.** "User has been low for 3 days" — no. We read memory into the prompt; we don't generate alerts.
- **No agent-owned memory tools.** Gemini doesn't call `view`/`create`/`delete` mid-response. The system is extraction-based, not tool-based.

---

## 17 · Implementation handoff

This spec is ready for the `writing-plans` skill. Writing-plans should produce tasks covering:

1. **Schema + models** — extend `llm_schemas.py`, extend `memory_context.py` with `RelationalProfile`, add new Pydantic models (`ExtractedMemory`, `ExtractionResult`, `MemoryUpdateDecision`, `ReflectionResult`)
2. **YAML prompts** — new `memory_prompts` section with `extract`, `update_decision`, `reflect` prompts
3. **MemoryExtractor** — new file, Gemini call #1, fire-and-forget dispatch helper
4. **MemoryUpdater** — new file, Gemini call #2, Mem0 ADD/UPDATE/DELETE/NOOP, bi-temporal writes
5. **MemoryReader extension** — scoring function, tier filter, mode gate, top-k cut
6. **ReflectionService** — new file, threshold trigger, Gemini call, profile consolidation, LLM-driven pruning
7. **MongoDB indexes + migration** — index creation on first startup, no hard migration
8. **Crisis meta-fact hook** — extend `companion_engine.py` crisis short-circuit
9. **Chat router dispatch** — add fire-and-forget calls in `chat_sync` and `chat_stream`
10. **Memory router** — new file with `/api/memory` endpoints
11. **Config additions** — scoring weights, thresholds, model choices in `config.py`
12. **Unit tests** — Tier 1 coverage
13. **Integration tests** — Tier 2 mocked + Tier 3 live
14. **Dev smoke script** — Tier 4 comparison tool
15. **Backfill script** — one-time migration for existing users (optional, can run per-user on login)

Each task should have exact file paths, reusable infrastructure references, and verification commands.
