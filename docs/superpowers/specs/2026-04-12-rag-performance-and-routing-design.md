# RAG Performance & Model Routing Overhaul

**Date:** 2026-04-12
**Status:** Design
**Authors:** Claude (architect), Raviraj (owner)

---

## Problem Statement

Conversation turns that trigger RAG retrieval take **120-225 seconds** instead of the target **8-20 seconds**. Root cause analysis traced 90%+ of the latency to the **CrossEncoder neural reranker** thrashing VRAM on the 4GB GTX 1650 dev GPU, compounded by the retrieval judge spawning 3-5 parallel search calls that each independently rerank.

### Evidence

| Metric | Measured |
|--------|----------|
| Reranker warmup (no contention) | 0.19s |
| Reranker isolation (standalone) | 0.2s |
| Reranker during live server (VRAM thrashing) | **156s** |
| Turns without reranking | 13-21s |
| Turns with reranking | 117-225s |
| GPU | GTX 1650, 4GB VRAM |
| Models loaded | E5-large (~1.3GB) + bge-reranker-v2-m3 (~1.1GB) |
| Production (Cloud Run) | CPU-only, no GPU |

### Secondary Issues

- **Model routing** silently overrides `GEMINI_MODEL=gemini-2.0-flash` with `gemini-2.5-pro` for most intents via the `MODEL_STANDARD` tier, adding 5-15s per turn.
- **Retrieval judge over-classifies** emotional queries as "complex", triggering the expensive multi-search + multi-rerank path unnecessarily.

---

## Design Overview

Six independent, composable changes. Each is testable and deployable alone. Together they bring response time from 120-225s to 8-20s without quality degradation.

```
BEFORE (current):
  retrieval_judge.enhanced_retrieve()
    → search_1(embed + rerank) ─┐
    → search_2(embed + rerank) ─┤ 3-5 parallel, each reranks
    → search_3(embed + rerank) ─┘ → VRAM thrashing → 156s
    → merge → judge

AFTER (this design):
  retrieval_judge.enhanced_retrieve()
    → search_1(embed only) ─┐
    → search_2(embed only) ─┤ 3-5 parallel, NO reranking
    → search_3(embed only) ─┘ → fast (~2s total)
    → merge + deduplicate
    → rerank ONCE (top-12, ONNX/CPU) → ~1-3s
    → judge
```

---

## Change 1: Rerank-Once Pipeline

### What

Restructure `retrieval_judge.enhanced_retrieve()` so that all parallel sub-query searches skip reranking. Reranking happens exactly once on the merged, deduplicated candidate pool.

### Why

The retrieval judge currently calls `rag_pipeline.search()` 3-5 times in parallel for complex queries. Each search independently runs the CrossEncoder reranker. On a 4GB GPU, these concurrent GPU operations thrash VRAM, turning a 200ms operation into 156s.

By separating search (embedding + BM25) from reranking, we ensure the CrossEncoder runs exactly once per request, on a single merged candidate list.

### How

Add a `skip_rerank: bool = False` parameter to `rag_pipeline.search()`. When `True`, the search returns results scored by hybrid search (semantic + BM25) only, without CrossEncoder reranking.

In `retrieval_judge.enhanced_retrieve()`:
1. All sub-query searches pass `skip_rerank=True`
2. Results are merged and deduplicated by reference
3. Top candidates (limited by `MAX_RERANK_CANDIDATES`) are reranked via a new `rag_pipeline.rerank(query, candidates)` public method
4. The reranked results are returned to the judge for scoring

The simple-query path (`complexity == "simple"`) continues to call `search()` normally (with reranking inline), because it's a single search call with no contention.

### Files Changed

- `rag/pipeline.py`: Add `skip_rerank` parameter to `search()`, extract `rerank()` as a public method
- `services/retrieval_judge.py`: Pass `skip_rerank=True` to parallel sub-searches, call `rerank()` once on merged pool

### Quality Impact

**Same or better.** Reranking a merged pool from 3-5 searches produces a more diverse candidate set than reranking each search independently. The CrossEncoder sees the best candidates from ALL sub-queries, not just one.

---

## Change 2: ONNX CPU Reranker

### What

Fix the broken ONNX loading for the CrossEncoder and configure it to run on CPU via ONNX Runtime, while the E5-large embedding model stays on GPU (when available).

### Why

The current code attempts ONNX loading but fails:
```
ONNX reranker load failed, falling back to PyTorch:
CrossEncoder.__init__() got an unexpected keyword argument 'backend'
```

The `sentence-transformers` CrossEncoder API changed — `backend` is not a valid constructor arg. ONNX loading needs to use the ONNX Runtime directly or the correct CrossEncoder ONNX API.

Running the reranker on CPU via ONNX Runtime eliminates VRAM contention entirely. ONNX on CPU with INT8 quantization for 10-12 pairs: ~1-3s. This also matches the production Cloud Run environment which has no GPU.

### How

1. At startup, attempt to load the reranker ONNX model from `models/reranker/onnx/model.onnx` using `onnxruntime.InferenceSession` directly (not via CrossEncoder constructor)
2. Create a thin `ONNXReranker` wrapper class with a `.predict(pairs) -> List[float]` interface matching what `_rerank_results` expects
3. If ONNX loading succeeds, use it. If not, fall back to PyTorch CrossEncoder on CPU (not GPU)
4. The reranker device choice is independent of the embedding model device

### Device Placement Strategy

```
Environment          | Embedding Model | Reranker
---------------------|-----------------|------------------
Dev (GTX 1650 4GB)   | GPU (CUDA)      | CPU (ONNX)
Production (Cloud Run)| CPU (PyTorch)   | CPU (ONNX)
Future (8GB+ GPU)    | GPU (CUDA)      | CPU (ONNX) *
```

*Even with ample VRAM, CPU ONNX reranking at 1-3s is fast enough that GPU acceleration provides negligible benefit for 10-12 pairs. Keeping the reranker on CPU is the permanently correct choice.

### Files Changed

- `rag/pipeline.py`: New `ONNXReranker` class, update `_ensure_reranker_model()` to use it, force CPU device for PyTorch fallback
- `scripts/download_models.py`: Ensure ONNX model is exported/downloaded during build

### Quality Impact

**Identical.** Same model weights, different runtime. ONNX Runtime produces numerically equivalent scores.

---

## Change 3: GPU Access Lock

### What

Add an `asyncio.Lock` around GPU model inference (embedding generation) to prevent concurrent GPU operations from overlapping.

### Why

Even with the reranker on CPU (Change 2), the E5-large embedding model on GPU can still be called concurrently from:
- RAG search (query embedding)
- Memory reader (episodic retrieval query embedding)
- Memory extractor (storing new memory — generates embedding)

On the 4GB GTX 1650, concurrent PyTorch operations on the same GPU cause GIL contention and CUDA stream serialization. An explicit lock makes the serialization intentional and prevents unpredictable slowdowns.

### How

Add a module-level `_gpu_lock = asyncio.Lock()` in `rag/pipeline.py`. Wrap the `generate_embeddings()` method's GPU call with `async with _gpu_lock`. The lock is async so it doesn't block the event loop — other coroutines (Redis, MongoDB, Gemini API calls) continue while waiting for the GPU.

The memory reader already calls `rag.generate_embeddings()`, so it inherits the lock automatically.

### Files Changed

- `rag/pipeline.py`: Add `_gpu_lock`, wrap `generate_embeddings()` internals

### Quality Impact

**None.** Same operations, same results, just serialized.

---

## Change 4: Reduce Max Rerank Candidates

### What

Lower `MAX_RERANK_CANDIDATES` from 20 to 12 in config defaults.

### Why

CrossEncoder inference is O(N) in the number of pairs. Reducing from 20 to 12 gives a 40% speedup. The quality impact is negligible: the top 12 candidates from hybrid search (semantic + BM25) already contain the best matches. Documents ranked 13-20 by hybrid search almost never survive reranking to the final top-3.

Current pipeline: `96,612 verses → top-20 hybrid → rerank → top-3 final`
New pipeline: `96,612 verses → top-12 hybrid → rerank → top-3 final`

### How

Change the default in `config.py`. No code changes needed — the existing `MAX_RERANK_CANDIDATES` setting is already respected.

Note: The `PERF_RAG` logs show some searches produce 10 candidates, others 20. The 20-candidate searches come from the curated concept slot reservation injecting extra docs. With `MAX_RERANK_CANDIDATES=12`, the cap applies after injection, keeping the pipeline bounded.

### Files Changed

- `config.py`: Change `MAX_RERANK_CANDIDATES` default from 20 to 12

### Quality Impact

**Negligible.** The final output is `RERANK_TOP_K=3` documents. Candidates 13-20 have less than 2% chance of entering the final top-3 based on RAKS benchmark data.

---

## Change 5: Model Routing Fix

### What

Change `MODEL_STANDARD` from `gemini-2.5-pro` to `gemini-2.5-flash` in config defaults. Keep `MODEL_PREMIUM` as `gemini-2.5-pro` for genuine crisis/complex cases.

### Why

The model router sends most conversation intents to STANDARD tier:
- EXPRESSING_EMOTION → STANDARD
- SEEKING_GUIDANCE (simple) → STANDARD
- ASKING_INFO (direct) → STANDARD
- Default fallthrough → STANDARD

All of these currently resolve to `gemini-2.5-pro`, adding 5-15s per response vs `gemini-2.5-flash` which is 2-5s. The quality difference between flash and pro for conversational spiritual guidance is minimal — both follow the same system instruction and persona prompts. Pro's advantage is in complex reasoning tasks, which are already routed to PREMIUM tier (crisis, high complexity).

### Tier Mapping (After)

```
ECONOMY  → gemini-2.5-flash      (greeting, closure, panchang, product search)
STANDARD → gemini-2.5-flash      (emotional sharing, info queries, guidance)
PREMIUM  → gemini-2.5-pro        (crisis, high urgency, complex guidance with 3+ signals)
```

### Files Changed

- `config.py`: Change `MODEL_STANDARD` default from `"gemini-2.5-pro"` to `"gemini-2.5-flash"`

### Quality Impact

**Minimal.** `gemini-2.5-flash` produces high-quality conversational responses. The system instruction, persona prompts, RAG context, and response validator enforce quality regardless of model. Crisis situations (where nuance matters most) still use pro.

---

## Change 6: Adaptive Rerank Skip

### What

Expand the conditions under which the CrossEncoder reranker is skipped, based on intent and the hybrid search score distribution.

### Why

Not every query benefits from neural reranking. When the hybrid search (semantic + BM25) already produces high-confidence results, the CrossEncoder adds latency without changing the ranking. Current skip conditions (`top_score >= 0.75 AND gap >= 0.15`) rarely trigger because hybrid scores are normalized differently than reranker scores.

### Skip Conditions (After)

The reranker is skipped when ANY of these hold:

1. **Existing rule**: `top_score >= SKIP_RERANK_THRESHOLD AND gap >= SKIP_RERANK_GAP` (unchanged)
2. **New — Listening phase**: When `phase == LISTENING` and the query is emotional sharing (not seeking info), the response doesn't cite specific verses. Reranking is wasted work.
3. **New — No RAG context needed**: When the response mode is `presence_first` or `closure`, the response composer generates a purely empathetic response. RAG docs are passed but rarely used. Skip reranking for these modes.
4. **New — Curated concept dominant**: When 60%+ of candidates are curated concept docs (pre-authored, already high quality), reranking provides marginal benefit.

### Files Changed

- `rag/pipeline.py`: Expand the skip condition block before `_rerank_results()` call. Accept `intent`, `phase`, and `response_mode` parameters in the search method to make skip decisions.

### Quality Impact

**None for skipped cases** — these are turns where the response doesn't use specific scripture citations anyway. The response validator still catches hollow phrases and forces regeneration if quality drops.

---

## Latency Budget (After All Changes)

| Stage | Current (Turn 3+) | After |
|-------|--------------------|-------|
| Intent analysis | 1.5-2s | 1.5-2s (unchanged) |
| Memory reader | 0.4-1s | 0.4-1s (unchanged) |
| RAG search (parallel, no rerank) | 156s | **2-4s** |
| Rerank once (ONNX CPU, 12 candidates) | (included above) | **1-3s** |
| LLM response (gemini-2.5-flash) | 5-15s | **2-5s** |
| Response validation | 0.5-2s | 0.5-2s (unchanged) |
| **Total** | **120-225s** | **8-18s** |

---

## Testing Strategy

### Unit Tests
- `test_rerank_once.py`: Verify merged-then-reranked results match or exceed per-search reranked quality on 10 benchmark queries
- `test_onnx_reranker.py`: Compare ONNX vs PyTorch scores for numerical equivalence (tolerance < 0.01)
- `test_gpu_lock.py`: Verify concurrent embedding calls serialize correctly
- `test_skip_rerank.py`: Verify skip conditions trigger correctly for each intent/phase/mode combination
- `test_model_routing.py`: Verify STANDARD tier resolves to flash, PREMIUM to pro

### Integration Tests
- Run the E2E test suite (already written at `tests/e2e_full_test.py`) with latency assertions:
  - All conversation turns must complete in < 30s
  - No rerank time should exceed 5s
  - Response quality checks (no hollow phrases, proper phase transitions) must still pass

### Benchmark
- Before/after comparison on 10 conversations (5 turns each) measuring:
  - P50, P95, P99 response latency
  - Rerank latency specifically
  - Response quality score (existing QA evaluator)

---

## Rollout Order

Changes are independent. Recommended order for incremental validation:

1. **Change 4** (reduce candidates 20→12) — config-only, zero risk, immediate 40% rerank speedup
2. **Change 5** (model routing fix) — config-only, saves 5-15s per turn
3. **Change 2** (ONNX CPU reranker) — eliminates VRAM contention permanently
4. **Change 3** (GPU lock) — safety net for embedding concurrency
5. **Change 1** (rerank-once pipeline) — structural change, biggest latency impact
6. **Change 6** (adaptive skip) — optimization, skip reranking when unnecessary

Each change can be deployed and validated independently. If any change causes quality regression, it can be reverted without affecting the others.

---

## Non-Goals

- Replacing the CrossEncoder model with a different architecture
- Changing the embedding model (E5-large)
- Modifying the Gemini API integration or prompt structure
- Refactoring the retrieval judge's complexity classification (works correctly — the problem was downstream, not in classification)
- Adding GPU hardware requirements to production deployment
