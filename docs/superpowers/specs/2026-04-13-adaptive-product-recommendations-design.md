# Adaptive Product Recommendations — Design Spec

**Date:** 2026-04-13
**Status:** Approved
**Branch:** `feature/product-recommendations`

---

## Problem

The product recommendation system is too aggressive. It surfaces product cards
too frequently, triggered by programmatic keyword scanning and hardcoded maps
rather than genuine conversational readiness. This makes the companion feel like
a marketing tool rather than a trusted spiritual friend, risking user
disengagement.

Root causes:
1. A 92-entry `PRACTICE_PRODUCT_MAP` injects products whenever the assistant's
   own response mentions practices — the LLM never asked for products.
2. A 6-gate programmatic suppression system second-guesses the LLM's judgment,
   creating a complex rule layer that's hard to maintain and prone to false
   positives.
3. No cross-session memory — the system can't learn that a user dislikes product
   suggestions or has already bought a mala.
4. Listening-phase product recommendations appear even when the user is
   emotionally venting.

## Design Philosophy

**"A friend who happens to know a shop."**

The companion should never feel like a salesperson. Products enter the conversation
the way a thoughtful friend would mention them — only when the moment genuinely
calls for it, never during emotional distress, and with permanent respect for the
user's preferences. The LLM's social intelligence is the sole decision-maker;
programmatic code enforces only hard safety rails.

## Approach: LLM-as-Sole-Authority

All programmatic product triggering logic is removed. The IntentAgent LLM — given
rich context about the conversation, emotional arc, and the user's product
interaction history — decides whether to recommend. Two hard safety rails
(crisis, user opted out) are the only programmatic overrides.

---

## §1 Deletions

All code that injects or triggers products independently of the LLM's decision
is removed.

### From `backend/services/product_recommender.py`:

| Item | Lines | Reason |
|------|-------|--------|
| `PRACTICE_PRODUCT_MAP` | 19–92 | Hardcoded 92-entry keyword→product map. Triggers products based on assistant's own response text, not user intent. |
| `_DEITY_NAMES` | 101–106 | Hardcoded deity scanning for product inference. |
| `_ITEM_WORDS` | 277–281 | Hardcoded item keyword detection for post-gen inference. |
| `infer_from_response()` | 236–316 | Post-generation product scanning. Already disabled Apr 2026, now delete dead code. |
| `record_suggestion()` | 218–234 | Feeds `infer_from_response()`. Dead code. |
| `_detect_practices_from_context()` | 555–578 | Scans conversation for practice keywords using the MAP. |
| `_get_conversation_deity()` | 581–618 | Scans history for deity names using the hardcoded set. |
| `validate_product_signal()` | ~120–134 | 5-rule programmatic validator that overrides LLM decisions. |
| `_should_suppress()` | 459–488 | 6-gate suppression system. Replaced by 2 hard safety rails. |
| `_detect_product_rejection()` | 490–516 | Soft/hard rejection with counters. Replaced by memory-persisted preference. |

### From `backend/routers/chat.py`:

| Item | Line | Reason |
|------|------|--------|
| `record_suggestion()` call | ~477 | Call site for deleted method. |

### From `backend/config.py`:

| Setting | Current Value | Reason |
|---------|---------------|--------|
| `PRODUCT_SESSION_CAP` | 3 | LLM self-regulates via session product count in context. |
| `PRODUCT_COOLDOWN_TURNS` | 7 | LLM judges timing from conversation history. |
| `PRODUCT_COOLDOWN_AFTER_REJECTION` | 10 | Replaced by RelationalProfile memory. |
| `PRODUCT_MIN_TURN_FOR_PROACTIVE` | 2 | LLM understands conversation maturity from history. |

### Retained:

| Item | Why |
|------|-----|
| `ProductService.search_products()` | Search engine — finds products once LLM decides to recommend. |
| `ProductService.search_by_metadata()` | Enriched field search — same role as above. |
| `_filter_shown()` / `_record_shown()` | Session dedup — prevents re-showing same product. |
| `EMOTION_BENEFIT_BRIDGE` in product_service.py | Improves search quality, doesn't trigger recommendations. |
| Enriched MongoDB product fields | Power search, not triggering. |
| `PRODUCT_MIN_RELEVANCE_SCORE` | Search quality threshold. |
| `PRODUCT_RELEVANCE_GAP_RATIO` | Search quality gap filter. |

---

## §2 Simplified ProductRecommender

The `recommend()` method reduces from ~200 lines with 3 paths, 6 gates, and
keyword scanning to ~60 lines with 3 steps.

### New `recommend()` flow:

```
Step 1: Hard Safety Check
  ├── urgency == "crisis" → return []
  └── RelationalProfile.product_preference == "opted_out" → return []

Step 2: Trust the LLM
  └── product_signal.intent in ("none", "negative") → return []

Step 3: Search and Return
  ├── ProductService.search_products(keywords=signal.search_keywords,
  │     type_filter=signal.type_filter)
  ├── ProductService.search_by_metadata() if text search returns < max_results
  ├── _filter_shown() for session dedup
  ├── _record_shown() to track what was shown
  ├── Update RelationalProfile product interaction fields
  └── Return results capped at signal.max_results
```

### Removed from recommender interface:

- `is_ready_for_wisdom` parameter — the LLM handles phase awareness through
  conversation context, the recommender doesn't need to know the phase.
- `turn_topics` parameter — was used for keyword-based product inference. No
  longer needed with LLM-as-authority.
- All practice/deity/item detection helpers.

### Estimated size: ~120 lines (down from ~700).

---

## §3 Enriched IntentAgent Prompt

The IntentAgent prompt replaces ~50 lines of structured classification rules
with a persona-based instruction that leverages the LLM's social intelligence.

### New prompt section (replaces current product_signal rules):

```
## Product Awareness

You are a friend who happens to know a shop (my3ionetra.com). You never bring
up products unless the moment genuinely calls for it. Here's how you think
about it:

- If someone is hurting, you LISTEN. You don't hand them a catalog.
- If someone is exploring spirituality casually, you talk — you don't sell.
- If someone has been discussing a practice across several turns and naturally
  reaches the point where they'd need something ("I want to start doing japa
  daily"), THAT is when you might mention you know where to find a mala.
- If someone directly asks "do you have products?" or "where can I buy X?",
  you help them find it.
- If someone has told you before that they don't want product suggestions,
  you respect that permanently.

The bar is: would a thoughtful human friend mention a product here, or would
it feel forced? When in doubt, don't.
```

### Context injected into the LLM (new additions):

The IntentAgent already receives conversation history and emotional state. The
following are added:

1. **Product interaction history** — serialized from RelationalProfile:
   ```
   Product history: shown 4 times across sessions, last on 2026-04-10
   (Rudraksha Mala). No rejections. Preference: neutral.
   ```

2. **Session product count** — from session state:
   ```
   Products shown this session: 1
   ```

These are appended to the existing context the IntentAgent receives, alongside
the conversation summary.

### Output schema unchanged:

The `product_signal` JSON structure remains:
```json
{
  "intent": "none|explicit_search|contextual_need|casual_mention|negative",
  "confidence": 0.0,
  "type_filter": "any|physical_only|consultation_only|service_only",
  "search_keywords": [],
  "max_results": 0,
  "sensitivity_note": ""
}
```

The LLM fills this based on social reasoning rather than pattern-matching
against enumerated rules.

### Fallback analysis:

The keyword-based fallback (when LLM is unavailable) is simplified to detect
only:
- Explicit buy/purchase words → `explicit_search`
- Hard rejection phrases → `negative` + trigger `opted_out` on profile
- Everything else → `none`

No practice-keyword scanning, no deity detection, no domain mapping.

---

## §4 Memory Integration — Product Interaction Tracking

Cross-session product interaction signals are stored on the existing
`user_profiles` document (RelationalProfile) in MongoDB. No new collections.

### New fields on RelationalProfile:

```python
product_preference: str = "neutral"
    # "neutral"   — no strong signal either way
    # "receptive" — user has engaged positively with products
    # "opted_out" — user explicitly said stop (hard safety rail)

product_shown_count: int = 0
    # Lifetime count of product recommendation events across all sessions.

product_last_shown_at: Optional[str] = None
    # ISO timestamp of the most recent product recommendation.

product_last_rejected_at: Optional[str] = None
    # ISO timestamp of the most recent product rejection.

product_rejection_count: int = 0
    # Lifetime count of product rejections (intent == "negative").

product_purchased_items: List[str] = []
    # Product names the user has engaged with. Future use — populated when
    # frontend sends click/purchase events. Empty for now but the field
    # exists so we don't need a schema migration later.
```

### Update triggers:

| Event | What updates | Where it happens |
|-------|-------------|-----------------|
| Products shown to user | `product_shown_count += 1`, `product_last_shown_at = now` | `_record_shown()` in ProductRecommender |
| LLM returns `intent: "negative"` | `product_rejection_count += 1`, `product_last_rejected_at = now` | `recommend()` in ProductRecommender |
| Hard dismissal phrase detected | `product_preference = "opted_out"` | `recommend()` in ProductRecommender |
| User asks for products after opt-out | `product_preference = "neutral"` (re-engage) | `recommend()` when intent is `explicit_search` and preference was `opted_out` |

### Serialization for LLM context:

A `to_product_context()` method on RelationalProfile produces a one-line
summary:

```python
def to_product_context(self) -> str:
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

This string is injected into the IntentAgent prompt context alongside the
existing relational narrative.

---

## §5 Phase Independence

Product recommendations are not gated by conversation phase. The
`recommend()` call continues to run in both guidance and listening phases,
but the LLM naturally returns `intent: "none"` for emotional/listening turns
because it understands the conversation context.

On the rare occasion a user asks for products during the listening phase
("where can I buy a mala?"), the LLM correctly classifies it and products
appear — no phase-based blocking prevents this.

The `is_ready_for_wisdom` parameter is removed from the `recommend()`
interface. The recommender doesn't need to know the phase.

---

## §6 What Stays Unchanged

| Component | Why |
|-----------|-----|
| `ProductService` (search engine) | Search quality is good. Text search + semantic reranking + metadata search. |
| Enriched MongoDB product schema | `practices`, `deities`, `emotions`, `life_domains`, `benefits`, `product_type` fields power search. |
| `EMOTION_BENEFIT_BRIDGE` | Maps emotions to product benefits for search quality. |
| `_filter_shown()` / `_record_shown()` | Session-level dedup by ID and name. |
| `PRODUCT_MIN_RELEVANCE_SCORE` | Search quality threshold (15.0). |
| `PRODUCT_RELEVANCE_GAP_RATIO` | Gap filter (0.55). |
| Frontend `ProductCard` / `ProductDisplay` | Rendering unchanged — horizontal carousel, lazy images, safe URLs. |
| `product_signal` JSON schema | Same structure, LLM fills it differently. |
| `ConversationalResponse.recommended_products` | API contract unchanged. |

---

## §7 Architecture Diagram

```
User Message
  │
  ▼
IntentAgent (LLM) ◄── Conversation history
  │                ◄── Emotional arc
  │                ◄── Product interaction history (RelationalProfile)
  │                ◄── Session product count
  │                ◄── "Friend who knows a shop" persona
  │
  ▼
product_signal: { intent, confidence, search_keywords, max_results, type_filter }
  │
  ▼
ProductRecommender.recommend()
  ├── Hard safety: crisis → [], opted_out → []
  ├── Trust LLM: "none"/"negative" → []
  └── Search: ProductService with LLM's keywords
       ├── Text search (MongoDB $text + semantic reranking)
       ├── Metadata search (enriched fields, if needed)
       ├── Session dedup (_filter_shown)
       └── Cap at max_results
  │
  ▼
Update RelationalProfile (product_shown_count, timestamps)
  │
  ▼
ConversationalResponse.recommended_products → Frontend ProductDisplay
```

---

## §8 Success Criteria

1. **No products on emotional turns** — When a user is expressing grief, anger,
   anxiety, or other distress, the system never surfaces product cards.

2. **No products without LLM decision** — Every product recommendation traces
   back to the IntentAgent's `product_signal.intent` being something other than
   `"none"`. No programmatic layer injects products independently.

3. **Cross-session memory works** — A user who says "stop suggesting products"
   in session 1 sees zero products in session 2 (until they explicitly ask).

4. **Explicit requests always work** — "Where can I buy a mala?" returns
   relevant products regardless of phase, turn count, or prior rejection
   history.

5. **Zero hardcoded product-triggering lists** — No keyword maps, no deity
   lists, no practice-to-product dictionaries in the codebase.

6. **E2E test suite stays at 112/112** — No regressions.

7. **Existing product search quality preserved** — When products are
   recommended, they're still relevant (semantic reranking, enriched fields,
   relevance gap policy all unchanged).
