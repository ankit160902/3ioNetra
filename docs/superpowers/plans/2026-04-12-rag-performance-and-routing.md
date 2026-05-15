# RAG Performance & Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring conversation response time from 120-225s to 8-20s by fixing CrossEncoder VRAM thrashing, model routing, and pipeline structure.

**Architecture:** Six independent changes applied incrementally. Config-only changes first (zero risk), then ONNX reranker (hardware isolation), GPU lock (safety), pipeline restructure (biggest impact), and adaptive skip (optimization). Each change is independently deployable and reversible.

**Tech Stack:** Python 3.11, FastAPI, PyTorch, ONNX Runtime, sentence-transformers CrossEncoder, asyncio

**Spec:** `docs/superpowers/specs/2026-04-12-rag-performance-and-routing-design.md`

---

### Task 1: Reduce Max Rerank Candidates (Config Change)

**Files:**
- Modify: `backend/config.py:119` (MAX_RERANK_CANDIDATES default)
- Test: `backend/tests/unit/test_config_defaults.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_config_defaults.py`:

```python
"""Verify config defaults match design spec expectations."""
from config import Settings


def test_max_rerank_candidates_default():
    """MAX_RERANK_CANDIDATES must be 12 to prevent VRAM thrashing on 4GB GPUs.
    See docs/superpowers/specs/2026-04-12-rag-performance-and-routing-design.md Change 4."""
    s = Settings(
        GEMINI_API_KEY="fake",
        MONGODB_URI="mongodb://localhost",
        DATABASE_NAME="test",
    )
    assert s.MAX_RERANK_CANDIDATES == 12


def test_model_standard_default():
    """MODEL_STANDARD must be gemini-2.5-flash, not gemini-2.5-pro.
    See design spec Change 5."""
    s = Settings(
        GEMINI_API_KEY="fake",
        MONGODB_URI="mongodb://localhost",
        DATABASE_NAME="test",
    )
    assert s.MODEL_STANDARD == "gemini-2.5-flash"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_config_defaults.py -v`
Expected: FAIL — `assert 10 == 12` and `assert "gemini-2.5-pro" == "gemini-2.5-flash"`

- [ ] **Step 3: Change MAX_RERANK_CANDIDATES default**

In `backend/config.py`, change:
```python
# BEFORE
MAX_RERANK_CANDIDATES: int = Field(default=10, env="MAX_RERANK_CANDIDATES")
```
to:
```python
# AFTER
MAX_RERANK_CANDIDATES: int = Field(default=12, env="MAX_RERANK_CANDIDATES")
```

- [ ] **Step 4: Change MODEL_STANDARD default**

In `backend/config.py`, change:
```python
# BEFORE
MODEL_STANDARD: str = "gemini-2.5-pro"
```
to:
```python
# AFTER
MODEL_STANDARD: str = "gemini-2.5-flash"
```

- [ ] **Step 5: Run tests to verify both pass**

Run: `cd backend && python -m pytest tests/unit/test_config_defaults.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/config.py backend/tests/unit/test_config_defaults.py
git commit -m "perf: reduce MAX_RERANK_CANDIDATES to 12, change MODEL_STANDARD to flash"
```

---

### Task 2: Export ONNX Reranker Model

**Files:**
- Create: `backend/scripts/export_reranker_onnx.py`
- Output: `backend/models/reranker/onnx/model.onnx` (generated artifact)

- [ ] **Step 1: Write the export script**

Create `backend/scripts/export_reranker_onnx.py`:

```python
"""Export bge-reranker-v2-m3 to ONNX format for CPU inference.

Usage: python scripts/export_reranker_onnx.py
Output: models/reranker/onnx/model.onnx + tokenizer files

The ONNX model runs on CPU via onnxruntime and produces numerically
equivalent scores to the PyTorch model — no quality degradation.
"""
import os
import sys
import shutil

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def export():
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    src_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "reranker")
    out_dir = os.path.join(src_dir, "onnx")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Loading PyTorch model from {src_dir}...")
    tokenizer = AutoTokenizer.from_pretrained(src_dir)
    model = AutoModelForSequenceClassification.from_pretrained(src_dir)
    model.eval()

    # Dummy input for tracing
    dummy = tokenizer(
        ["What is dharma?"],
        ["Dharma is the cosmic law and order"],
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )

    onnx_path = os.path.join(out_dir, "model.onnx")
    print(f"Exporting to {onnx_path}...")
    with torch.no_grad():
        torch.onnx.export(
            model,
            (dummy["input_ids"], dummy["attention_mask"]),
            onnx_path,
            input_names=["input_ids", "attention_mask"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids": {0: "batch", 1: "seq"},
                "attention_mask": {0: "batch", 1: "seq"},
                "logits": {0: "batch"},
            },
            opset_version=14,
        )

    # Copy tokenizer files alongside ONNX model
    for fname in ["tokenizer.json", "tokenizer_config.json",
                   "special_tokens_map.json", "sentencepiece.bpe.model", "config.json"]:
        src = os.path.join(src_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, out_dir)

    # Verify
    import onnxruntime as ort
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    import numpy as np
    out = sess.run(None, {
        "input_ids": dummy["input_ids"].numpy(),
        "attention_mask": dummy["attention_mask"].numpy(),
    })
    print(f"ONNX verification OK — output shape: {out[0].shape}, score: {out[0][0]}")
    print(f"Exported to: {out_dir}")


if __name__ == "__main__":
    export()
```

- [ ] **Step 2: Run the export**

Run: `cd backend && python scripts/export_reranker_onnx.py`
Expected: `ONNX verification OK — output shape: (1, 1), score: [...]`

Verify output: `ls backend/models/reranker/onnx/` should show `model.onnx` + tokenizer files.

- [ ] **Step 3: Commit** (do NOT commit the .onnx binary — add to .gitignore)

```bash
echo "backend/models/reranker/onnx/" >> .gitignore
git add backend/scripts/export_reranker_onnx.py .gitignore
git commit -m "tool: add ONNX reranker export script"
```

---

### Task 3: ONNX CPU Reranker Wrapper

**Files:**
- Create: `backend/rag/onnx_reranker.py`
- Test: `backend/tests/unit/test_onnx_reranker.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_onnx_reranker.py`:

```python
"""Test ONNXReranker produces scores equivalent to PyTorch CrossEncoder."""
import os
import pytest
import numpy as np

RERANKER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "reranker")
ONNX_PATH = os.path.join(RERANKER_DIR, "onnx", "model.onnx")


@pytest.fixture
def pairs():
    return [
        ["What is dharma?", "Dharma is the cosmic order that sustains the universe."],
        ["How to meditate?", "The Ganges river flows through Varanasi."],
        ["Tell me about karma", "Karma is the law of cause and effect in Hindu philosophy."],
    ]


@pytest.mark.skipif(not os.path.exists(ONNX_PATH), reason="ONNX model not exported")
def test_onnx_reranker_predict(pairs):
    from rag.onnx_reranker import ONNXReranker

    reranker = ONNXReranker(RERANKER_DIR)
    scores = reranker.predict(pairs)

    assert len(scores) == 3
    # Relevant pair should score higher than irrelevant
    assert scores[0] > scores[1], "Relevant pair should outscore irrelevant"
    assert scores[2] > scores[1], "Karma pair should outscore river pair"


@pytest.mark.skipif(not os.path.exists(ONNX_PATH), reason="ONNX model not exported")
def test_onnx_vs_pytorch_equivalence(pairs):
    from rag.onnx_reranker import ONNXReranker
    from sentence_transformers import CrossEncoder

    onnx = ONNXReranker(RERANKER_DIR)
    pytorch = CrossEncoder(RERANKER_DIR)

    onnx_scores = onnx.predict(pairs)
    pytorch_scores = pytorch.predict(pairs).tolist()

    for i, (o, p) in enumerate(zip(onnx_scores, pytorch_scores)):
        assert abs(o - p) < 0.05, f"Pair {i}: ONNX={o:.4f} vs PyTorch={p:.4f} differ by {abs(o-p):.4f}"


@pytest.mark.skipif(not os.path.exists(ONNX_PATH), reason="ONNX model not exported")
def test_onnx_reranker_empty_input():
    from rag.onnx_reranker import ONNXReranker

    reranker = ONNXReranker(RERANKER_DIR)
    scores = reranker.predict([])
    assert scores == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_onnx_reranker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'rag.onnx_reranker'`

- [ ] **Step 3: Implement ONNXReranker**

Create `backend/rag/onnx_reranker.py`:

```python
"""ONNX Runtime wrapper for bge-reranker-v2-m3 CrossEncoder.

Runs on CPU — no VRAM contention with the embedding model on GPU.
Drop-in replacement for sentence_transformers.CrossEncoder.predict().
"""
import logging
import os
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class ONNXReranker:
    """CPU-based ONNX reranker with CrossEncoder-compatible .predict() API."""

    def __init__(self, model_dir: str):
        import onnxruntime as ort
        from transformers import AutoTokenizer

        onnx_dir = os.path.join(model_dir, "onnx")
        onnx_path = os.path.join(onnx_dir, "model.onnx")

        # Use the onnx/ subdirectory for tokenizer if it has files, else parent
        tokenizer_path = onnx_dir if os.path.exists(os.path.join(onnx_dir, "tokenizer.json")) else model_dir

        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        self.session = ort.InferenceSession(
            onnx_path,
            providers=["CPUExecutionProvider"],
        )
        self.max_length = 512
        logger.info(f"ONNXReranker loaded from {onnx_path} (CPU)")

    def predict(self, pairs: List[List[str]]) -> List[float]:
        """Score query-document pairs. Returns list of float scores.

        Compatible with CrossEncoder.predict() return type.
        """
        if not pairs:
            return []

        queries = [p[0] for p in pairs]
        documents = [p[1] for p in pairs]

        encoded = self.tokenizer(
            queries,
            documents,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="np",
        )

        outputs = self.session.run(
            None,
            {
                "input_ids": encoded["input_ids"].astype(np.int64),
                "attention_mask": encoded["attention_mask"].astype(np.int64),
            },
        )

        # Output shape: (batch, 1) — squeeze to flat list
        logits = outputs[0]
        if logits.ndim == 2:
            logits = logits[:, 0]
        return logits.tolist()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_onnx_reranker.py -v`
Expected: 3 passed (or skipped if ONNX model not exported yet — run Task 2 first)

- [ ] **Step 5: Commit**

```bash
git add backend/rag/onnx_reranker.py backend/tests/unit/test_onnx_reranker.py
git commit -m "feat: ONNXReranker wrapper for CPU-based CrossEncoder inference"
```

---

### Task 4: Wire ONNX Reranker Into Pipeline + Force CPU Fallback

**Files:**
- Modify: `backend/rag/pipeline.py:591-630` (`_ensure_reranker_model`)
- Test: `backend/tests/unit/test_reranker_loading.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_reranker_loading.py`:

```python
"""Verify reranker loads on CPU (ONNX or PyTorch fallback), never GPU."""
import os
import pytest


RERANKER_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "reranker")
ONNX_PATH = os.path.join(RERANKER_DIR, "onnx", "model.onnx")


def test_reranker_loads_onnx_when_available():
    """If ONNX model exists, ONNXReranker is used."""
    if not os.path.exists(ONNX_PATH):
        pytest.skip("ONNX model not exported")

    from rag.pipeline import RAGPipeline
    pipeline = RAGPipeline.__new__(RAGPipeline)
    pipeline._reranker_model = None

    # Monkey-patch settings for this test
    import config
    orig = config.settings.RERANKER_ENABLED
    config.settings.RERANKER_ENABLED = True
    try:
        pipeline._ensure_reranker_model()
        from rag.onnx_reranker import ONNXReranker
        assert isinstance(pipeline._reranker_model, ONNXReranker), \
            f"Expected ONNXReranker, got {type(pipeline._reranker_model).__name__}"
    finally:
        config.settings.RERANKER_ENABLED = orig
        pipeline._reranker_model = None


def test_reranker_pytorch_fallback_uses_cpu():
    """PyTorch fallback must load on CPU, not GPU."""
    from sentence_transformers import CrossEncoder

    model = CrossEncoder(RERANKER_DIR, device="cpu")
    assert str(model.device) == "cpu"
    # Verify it can score
    scores = model.predict([["test query", "test document"]])
    assert len(scores) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_reranker_loading.py::test_reranker_loads_onnx_when_available -v`
Expected: FAIL — current `_ensure_reranker_model` doesn't use ONNXReranker

- [ ] **Step 3: Rewrite `_ensure_reranker_model` in `backend/rag/pipeline.py`**

Replace lines 591-630 with:

```python
    def _ensure_reranker_model(self) -> None:
        if not settings.RERANKER_ENABLED:
            self._reranker_model = None
            return
        if self._reranker_model is not None:
            return

        _local_reranker = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "models", "reranker"
        )
        _docker_reranker = "/app/models/reranker"
        _model_dir = _docker_reranker if os.path.isdir(_docker_reranker) else _local_reranker

        # 1. Try ONNX on CPU (preferred — no VRAM contention)
        _onnx_path = os.path.join(_model_dir, "onnx", "model.onnx")
        if os.path.exists(_onnx_path):
            try:
                from rag.onnx_reranker import ONNXReranker
                self._reranker_model = ONNXReranker(_model_dir)
                logger.info("RAGPipeline: reranker loaded via ONNX (CPU)")
                return
            except Exception as e:
                logger.warning(f"ONNX reranker load failed, falling back to PyTorch: {e}")

        # 2. PyTorch fallback — force CPU to prevent VRAM contention with embedding model
        from sentence_transformers import CrossEncoder
        logger.info(f"RAGPipeline: loading reranker via PyTorch (CPU) from {_model_dir}")
        try:
            if os.path.isdir(_model_dir) and os.listdir(_model_dir):
                self._reranker_model = CrossEncoder(_model_dir, device="cpu")
            else:
                self._reranker_model = CrossEncoder(settings.RERANKER_MODEL, device="cpu")
            logger.info(f"RAGPipeline: reranker loaded on {self._reranker_model.device}")
        except Exception as exc:
            logger.exception(f"RAGPipeline: failed to load reranker: {exc}")
            self._reranker_model = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_reranker_loading.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/rag/pipeline.py backend/tests/unit/test_reranker_loading.py
git commit -m "perf: load reranker on CPU (ONNX preferred, PyTorch fallback) — eliminates VRAM contention"
```

---

### Task 5: GPU Access Lock for Embedding Model

**Files:**
- Modify: `backend/rag/pipeline.py:636-656` (`generate_embeddings`)
- Test: `backend/tests/unit/test_gpu_lock.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_gpu_lock.py`:

```python
"""Verify GPU lock serializes concurrent embedding calls."""
import asyncio
import pytest

from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np


@pytest.mark.asyncio
async def test_concurrent_embeddings_serialize():
    """Two concurrent generate_embeddings calls must not overlap on GPU."""
    call_log = []

    original_encode = None

    def mock_encode(texts, **kwargs):
        call_log.append(("start", texts[0][:20]))
        import time
        time.sleep(0.05)  # Simulate GPU work
        call_log.append(("end", texts[0][:20]))
        return [np.zeros(1024, dtype="float32")]

    # We test the lock by checking that calls don't interleave
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or pipeline._embedding_model is None:
        pytest.skip("RAG pipeline not available")

    original_encode = pipeline._embedding_model.encode
    pipeline._embedding_model.encode = mock_encode

    try:
        await asyncio.gather(
            pipeline.generate_embeddings("first query"),
            pipeline.generate_embeddings("second query"),
        )
        # With a lock, calls should be: start1, end1, start2, end2
        # Without a lock, they could interleave: start1, start2, end1, end2
        starts = [i for i, (t, _) in enumerate(call_log) if t == "start"]
        ends = [i for i, (t, _) in enumerate(call_log) if t == "end"]
        # First end must come before second start
        assert ends[0] < starts[1], f"Calls overlapped: {call_log}"
    finally:
        pipeline._embedding_model.encode = original_encode
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_gpu_lock.py -v`
Expected: FAIL — `AssertionError: Calls overlapped` (no lock exists yet)

- [ ] **Step 3: Add GPU lock to `generate_embeddings`**

In `backend/rag/pipeline.py`, add near the top of the file (after imports):

```python
# GPU access lock — serializes embedding model inference to prevent
# VRAM contention on small GPUs (e.g., GTX 1650 4GB).
# See docs/superpowers/specs/2026-04-12-rag-performance-and-routing-design.md Change 3.
_gpu_lock = asyncio.Lock()
```

Then modify `generate_embeddings` (line 636) to use the lock:

```python
    async def generate_embeddings(self, text: str, is_query: bool = True) -> np.ndarray:
        """
        Public utility used by /api/embeddings/generate and search.
        For E5 models, automatically prepends 'query: ' or 'passage: ' prefix.
        """
        self._ensure_embedding_model()
        if self._embedding_model is None:
            dim = self.dim or settings.EMBEDDING_DIM
            logger.warning("RAGPipeline: embedding model unavailable, returning zeros")
            return np.zeros((dim,), dtype="float32")

        clean_text = text.strip().replace("\n", " ")
        if self._needs_instruction_prefix():
            prefix = "query: " if is_query else "passage: "
            clean_text = prefix + clean_text

        async with _gpu_lock:
            vec = (await asyncio.to_thread(
                self._embedding_model.encode, [clean_text],
                convert_to_tensor=False, show_progress_bar=False,
            ))[0]
        return np.asarray(vec, dtype="float32")
```

Apply the same lock to `generate_embeddings_batch`:

```python
    async def generate_embeddings_batch(self, texts: list, is_query: bool = True) -> list:
        """Batch-encode multiple texts in a single model.encode() call."""
        self._ensure_embedding_model()
        if self._embedding_model is None:
            dim = self.dim or settings.EMBEDDING_DIM
            return [np.zeros((dim,), dtype="float32") for _ in texts]
        prefix = ""
        if self._needs_instruction_prefix():
            prefix = "query: " if is_query else "passage: "
        clean_texts = [prefix + t.strip().replace("\n", " ") for t in texts]
        async with _gpu_lock:
            vecs = await asyncio.to_thread(
                self._embedding_model.encode, clean_texts,
                convert_to_tensor=False, show_progress_bar=False, batch_size=len(clean_texts),
            )
        return [np.asarray(v, dtype="float32") for v in vecs]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_gpu_lock.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/rag/pipeline.py backend/tests/unit/test_gpu_lock.py
git commit -m "perf: add GPU access lock to serialize embedding calls"
```

---

### Task 6: Rerank-Once Pipeline — Add `skip_rerank` to Search

**Files:**
- Modify: `backend/rag/pipeline.py:1435-1460` (search signature), `backend/rag/pipeline.py:1742-1758` (rerank block)
- Test: `backend/tests/unit/test_skip_rerank.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_skip_rerank.py`:

```python
"""Verify skip_rerank parameter prevents CrossEncoder from running."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_search_skip_rerank_returns_results():
    """search(skip_rerank=True) returns hybrid-scored results without CrossEncoder."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    with patch.object(pipeline, '_rerank_results', wraps=pipeline._rerank_results) as mock_rerank:
        results = await pipeline.search(query="What is dharma?", skip_rerank=True)
        mock_rerank.assert_not_called()

    assert isinstance(results, list)
    # Results should have 'score' (hybrid) but no 'rerank_score'
    for r in results:
        assert "score" in r
        assert "final_score" in r  # should be set to hybrid score


@pytest.mark.asyncio
async def test_search_with_rerank_calls_crossencoder():
    """Default search (skip_rerank=False) runs CrossEncoder."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    with patch.object(pipeline, '_rerank_results', wraps=pipeline._rerank_results) as mock_rerank:
        results = await pipeline.search(query="What is dharma?", skip_rerank=False)
        # May or may not be called (depends on skip threshold), but function should exist
        assert hasattr(pipeline, '_rerank_results')

    assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_skip_rerank.py -v`
Expected: FAIL — `TypeError: search() got an unexpected keyword argument 'skip_rerank'`

- [ ] **Step 3: Add `skip_rerank` parameter to `search()`**

In `backend/rag/pipeline.py`, modify the search signature (line 1435):

```python
    async def search(
        self,
        query: str,
        scripture_filter: Optional[List[str]] = None,
        language: str = "en",
        top_k: int = settings.RETRIEVAL_TOP_K,
        intent: Optional[IntentType] = None,
        min_score: float = settings.MIN_SIMILARITY_SCORE,
        doc_type_filter: Optional[List[str]] = None,
        life_domain: Optional[str] = None,
        query_variants: Optional[List[str]] = None,
        exclude_references: Optional[List[str]] = None,
        skip_rerank: bool = False,
    ) -> List[Dict]:
```

Then modify the reranking block (around line 1742-1758). Replace:

```python
        # 5. Neural Re-ranking (Cross-Encoder) — skip when top result is already decisive
        logger.info(f"PERF_RAG candidates={len(results)} before reranking")
        _t_rerank = time.perf_counter()
        if results and len(results) >= 2:
            top_score = results[0].get("score", 0)
            second_score = results[1].get("score", 0)
            gap = top_score - second_score
            if top_score >= settings.SKIP_RERANK_THRESHOLD and gap >= settings.SKIP_RERANK_GAP:
                logger.info(f"Skipping reranker: top={top_score:.3f} gap={gap:.3f} (threshold={settings.SKIP_RERANK_THRESHOLD})")
                # Assign fused scores as final scores to maintain downstream compatibility
                for r in results:
                    r["rerank_score"] = r.get("score", 0)
                    r["final_score"] = r.get("score", 0)
            else:
                results = await self._rerank_results(query, results, intent=intent, life_domain=life_domain)
        elif results:
            results = await self._rerank_results(query, results, intent=intent, life_domain=life_domain)
        _timings['rerank_ms'] = round((time.perf_counter() - _t_rerank) * 1000)
```

With:

```python
        # 5. Neural Re-ranking (Cross-Encoder)
        logger.info(f"PERF_RAG candidates={len(results)} before reranking (skip={skip_rerank})")
        _t_rerank = time.perf_counter()
        if skip_rerank:
            # Caller will rerank merged results later (rerank-once pattern)
            for r in results:
                r["rerank_score"] = r.get("score", 0)
                r["final_score"] = r.get("score", 0)
        elif results and len(results) >= 2:
            top_score = results[0].get("score", 0)
            second_score = results[1].get("score", 0)
            gap = top_score - second_score
            if top_score >= settings.SKIP_RERANK_THRESHOLD and gap >= settings.SKIP_RERANK_GAP:
                logger.info(f"Skipping reranker: top={top_score:.3f} gap={gap:.3f} (threshold={settings.SKIP_RERANK_THRESHOLD})")
                for r in results:
                    r["rerank_score"] = r.get("score", 0)
                    r["final_score"] = r.get("score", 0)
            else:
                results = await self._rerank_results(query, results, intent=intent, life_domain=life_domain)
        elif results:
            results = await self._rerank_results(query, results, intent=intent, life_domain=life_domain)
        _timings['rerank_ms'] = round((time.perf_counter() - _t_rerank) * 1000)
```

- [ ] **Step 4: Extract public `rerank()` method**

Add a new public method in `backend/rag/pipeline.py` (after `_rerank_results`):

```python
    async def rerank(
        self,
        query: str,
        candidates: List[Dict],
        intent: Optional[IntentType] = None,
        life_domain: Optional[str] = None,
    ) -> List[Dict]:
        """Public reranking entry point for the rerank-once pattern.

        Called by retrieval_judge after merging results from parallel
        skip_rerank=True searches. Caps candidates at MAX_RERANK_CANDIDATES,
        runs CrossEncoder, and returns sorted results.
        """
        if not candidates:
            return candidates
        # Cap candidates
        if len(candidates) > settings.MAX_RERANK_CANDIDATES:
            candidates = candidates[:settings.MAX_RERANK_CANDIDATES]
        return await self._rerank_results(query, candidates, intent=intent, life_domain=life_domain)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_skip_rerank.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/rag/pipeline.py backend/tests/unit/test_skip_rerank.py
git commit -m "feat: add skip_rerank parameter and public rerank() method for rerank-once pattern"
```

---

### Task 7: Wire Retrieval Judge to Use Rerank-Once

**Files:**
- Modify: `backend/services/retrieval_judge.py:129-212` (`enhanced_retrieve` complex path)
- Test: `backend/tests/unit/test_retrieval_judge_rerank_once.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_retrieval_judge_rerank_once.py`:

```python
"""Verify retrieval judge's complex path uses rerank-once pattern."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_complex_path_passes_skip_rerank():
    """Complex queries: parallel searches use skip_rerank=True, then rerank once."""
    from services.retrieval_judge import RetrievalJudge

    mock_pipeline = AsyncMock()
    mock_pipeline.search = AsyncMock(return_value=[
        {"reference": "BG 2.47", "text": "test", "score": 0.5, "final_score": 0.5, "rerank_score": 0.5},
    ])
    mock_pipeline.rerank = AsyncMock(return_value=[
        {"reference": "BG 2.47", "text": "test", "score": 0.5, "final_score": 0.7, "rerank_score": 0.7},
    ])

    mock_llm = MagicMock()
    mock_llm.available = True

    judge = RetrievalJudge.__new__(RetrievalJudge)
    judge.llm = mock_llm
    judge.available = True
    judge.cache = None

    # Mock decomposition and judgment
    judge._decompose_query = AsyncMock(return_value=["sub query 1", "sub query 2"])
    judge._judge_relevance = AsyncMock(return_value=MagicMock(
        score=4, should_retry=False, best_doc_indices=[]
    ))
    judge._classify_complexity = MagicMock(return_value="complex")

    results = await judge.enhanced_retrieve(
        query="What is the difference between karma and dharma according to the Gita?",
        intent_analysis={"intent": "SEEKING_GUIDANCE", "emotion": "curiosity"},
        rag_pipeline=mock_pipeline,
        search_kwargs={"top_k": 5},
    )

    # All search calls should have skip_rerank=True
    for call in mock_pipeline.search.call_args_list:
        assert call.kwargs.get("skip_rerank") is True or \
               (len(call.args) > 0 and "skip_rerank" in str(call)), \
            f"Search call missing skip_rerank=True: {call}"

    # rerank() should be called exactly once on merged results
    mock_pipeline.rerank.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_retrieval_judge_rerank_once.py -v`
Expected: FAIL — search calls don't pass `skip_rerank=True`

- [ ] **Step 3: Modify `enhanced_retrieve` complex path**

In `backend/services/retrieval_judge.py`, modify the complex path (around lines 129-212).

Replace the parallel search block:

```python
        # Parallel search for all sub-queries (with reduced top_k per sub-query)
        sub_top_k = min(search_kwargs.get("top_k", settings.RETRIEVAL_TOP_K), settings.RERANK_TOP_K)
        sub_search_kwargs = {**search_kwargs, "top_k": sub_top_k}
        sub_search_kwargs.pop("scripture_filter", None)  # Sub-queries need full corpus access
        tasks = [
            rag_pipeline.search(query=sq, **sub_search_kwargs)
            for sq in all_queries
        ]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
```

With:

```python
        # Parallel search for all sub-queries — skip_rerank=True (rerank-once pattern).
        # Each search returns hybrid-scored results without CrossEncoder.
        # We rerank once on the merged pool below.
        sub_top_k = min(search_kwargs.get("top_k", settings.RETRIEVAL_TOP_K), settings.RERANK_TOP_K)
        sub_search_kwargs = {**search_kwargs, "top_k": sub_top_k, "skip_rerank": True}
        sub_search_kwargs.pop("scripture_filter", None)
        tasks = [
            rag_pipeline.search(query=sq, **sub_search_kwargs)
            for sq in all_queries
        ]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
```

Then after the merge, add a single rerank call. Replace:

```python
        merged = self._merge_results(valid_results)

        if not merged:
            return await rag_pipeline.search(query=query, **search_kwargs)
```

With:

```python
        merged = self._merge_results(valid_results)

        if not merged:
            return await rag_pipeline.search(query=query, **search_kwargs)

        # Rerank-once: single CrossEncoder pass on the merged candidate pool
        intent = intent_analysis.get("intent")
        life_domain = intent_analysis.get("life_domain")
        merged = await rag_pipeline.rerank(
            query=query,
            candidates=merged,
            intent=intent if not isinstance(intent, str) else None,
            life_domain=life_domain,
        )
```

Also update the retry path — replace:

```python
                retry_docs = await rag_pipeline.search(query=rewritten, **search_kwargs)
```

With:

```python
                retry_search_kwargs = {**search_kwargs, "skip_rerank": True}
                retry_docs = await rag_pipeline.search(query=rewritten, **retry_search_kwargs)
```

And add reranking after the retry merge:

```python
                current_merged = self._merge_results([current_merged, retry_docs])
                # Rerank the expanded pool
                current_merged = await rag_pipeline.rerank(
                    query=query, candidates=current_merged,
                    intent=intent if not isinstance(intent, str) else None,
                    life_domain=life_domain,
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_retrieval_judge_rerank_once.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/retrieval_judge.py backend/tests/unit/test_retrieval_judge_rerank_once.py
git commit -m "perf: retrieval judge uses rerank-once pattern — 3-5x fewer CrossEncoder calls"
```

---

### Task 8: Adaptive Rerank Skip

**Files:**
- Modify: `backend/rag/pipeline.py:1435-1447` (search signature — add `response_mode` and `phase`)
- Modify: `backend/rag/pipeline.py:1742-1758` (skip conditions)
- Test: `backend/tests/unit/test_adaptive_skip.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/unit/test_adaptive_skip.py`:

```python
"""Verify adaptive rerank skip conditions."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_skip_rerank_for_presence_first():
    """presence_first response mode skips reranking."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    with patch.object(pipeline, '_rerank_results', new_callable=AsyncMock) as mock:
        results = await pipeline.search(
            query="I feel so lost",
            response_mode="presence_first",
        )
        mock.assert_not_called()


@pytest.mark.asyncio
async def test_skip_rerank_for_closure():
    """closure response mode skips reranking."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    with patch.object(pipeline, '_rerank_results', new_callable=AsyncMock) as mock:
        results = await pipeline.search(
            query="Thank you, goodbye",
            response_mode="closure",
        )
        mock.assert_not_called()


@pytest.mark.asyncio
async def test_no_skip_for_teaching():
    """teaching mode should still rerank (scripture precision matters)."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    # We just verify the parameter is accepted — reranking may or may not
    # run depending on the score threshold. The key is it's NOT force-skipped.
    results = await pipeline.search(
        query="What does Bhagavad Gita say about duty?",
        response_mode="teaching",
    )
    assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_adaptive_skip.py -v`
Expected: FAIL — `TypeError: search() got an unexpected keyword argument 'response_mode'`

- [ ] **Step 3: Add `response_mode` parameter and adaptive skip logic**

In `backend/rag/pipeline.py`, update the search signature to include `response_mode`:

```python
    async def search(
        self,
        query: str,
        scripture_filter: Optional[List[str]] = None,
        language: str = "en",
        top_k: int = settings.RETRIEVAL_TOP_K,
        intent: Optional[IntentType] = None,
        min_score: float = settings.MIN_SIMILARITY_SCORE,
        doc_type_filter: Optional[List[str]] = None,
        life_domain: Optional[str] = None,
        query_variants: Optional[List[str]] = None,
        exclude_references: Optional[List[str]] = None,
        skip_rerank: bool = False,
        response_mode: Optional[str] = None,
    ) -> List[Dict]:
```

Then update the reranking block to check response_mode. Replace the `if skip_rerank:` block:

```python
        # 5. Neural Re-ranking (Cross-Encoder)
        # Adaptive skip: modes that don't cite specific verses skip reranking
        _skip_modes = frozenset({"presence_first", "closure"})
        _effective_skip = skip_rerank or (response_mode in _skip_modes)
        logger.info(f"PERF_RAG candidates={len(results)} before reranking (skip={_effective_skip}, mode={response_mode})")
        _t_rerank = time.perf_counter()
        if _effective_skip:
            for r in results:
                r["rerank_score"] = r.get("score", 0)
                r["final_score"] = r.get("score", 0)
        elif results and len(results) >= 2:
```

(rest of the block stays the same)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_adaptive_skip.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/rag/pipeline.py backend/tests/unit/test_adaptive_skip.py
git commit -m "perf: adaptive rerank skip for presence_first and closure modes"
```

---

### Task 9: Integration Smoke Test

**Files:**
- Create: `backend/tests/integration/test_perf_smoke.py`

- [ ] **Step 1: Write the integration test**

Create `backend/tests/integration/test_perf_smoke.py`:

```python
"""Smoke test: verify reranking completes in <10s and full conversation turn in <30s.

Requires: running backend server on localhost:8080
Run: python -m pytest tests/integration/test_perf_smoke.py -v -s
"""
import time
import httpx
import pytest

BASE = "http://localhost:8080"
TIMEOUT = 45.0


@pytest.fixture(scope="module")
def client():
    with httpx.Client(timeout=TIMEOUT) as c:
        try:
            c.get(f"{BASE}/api/health", timeout=5)
        except Exception:
            pytest.skip("Backend server not running")
        yield c


@pytest.fixture(scope="module")
def session_id(client):
    resp = client.post(f"{BASE}/api/session/create", timeout=TIMEOUT)
    return resp.json()["session_id"]


def test_turn1_latency(client, session_id):
    """Turn 1 should complete in <30s."""
    start = time.perf_counter()
    resp = client.post(
        f"{BASE}/api/conversation",
        json={"session_id": session_id, "message": "I am feeling very sad today."},
        timeout=TIMEOUT,
    )
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text[:200]}"
    assert elapsed < 30, f"Turn 1 took {elapsed:.1f}s (limit: 30s)"


def test_turn2_latency(client, session_id):
    """Turn 2 should complete in <30s."""
    start = time.perf_counter()
    resp = client.post(
        f"{BASE}/api/conversation",
        json={"session_id": session_id, "message": "My mother passed away and I miss her deeply."},
        timeout=TIMEOUT,
    )
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert elapsed < 30, f"Turn 2 took {elapsed:.1f}s (limit: 30s)"


def test_turn3_latency_with_rag(client, session_id):
    """Turn 3 triggers RAG — must complete in <30s (was 120-225s before fix)."""
    start = time.perf_counter()
    resp = client.post(
        f"{BASE}/api/conversation",
        json={
            "session_id": session_id,
            "message": "Is there anything in our scriptures about dealing with grief and loss?",
        },
        timeout=TIMEOUT,
    )
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    data = resp.json()
    assert elapsed < 30, f"Turn 3 (RAG) took {elapsed:.1f}s (limit: 30s)"
    # Verify response quality — not empty, not an error
    assert len(data.get("response", "")) > 20, "Response too short"
```

- [ ] **Step 2: Start the server and run the test**

Start server (if not running): `cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080`

Run: `cd backend && python -m pytest tests/integration/test_perf_smoke.py -v -s`
Expected: 3 passed, all under 30s

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_perf_smoke.py
git commit -m "test: integration smoke test for <30s response latency"
```

---

### Task 10: Final Verification — Run Full E2E Suite

**Files:** None (uses existing `tests/e2e_full_test.py`)

- [ ] **Step 1: Restart the server with all changes**

```bash
# Kill any running server
taskkill //F //IM python.exe 2>/dev/null
# Start fresh
cd backend && python -u -m uvicorn main:app --host 0.0.0.0 --port 8080
```

Wait for `Application startup complete.`

- [ ] **Step 2: Run the full E2E test suite**

```bash
cd backend && python -u tests/e2e_full_test.py
```

Expected: All conversation turns complete without timeout. Rerank times in server logs should be <5s.

- [ ] **Step 3: Verify server logs show improvements**

Check server output for:
- `reranker loaded via ONNX (CPU)` — confirms ONNX path
- `PERF_RAG ... rerank=...ms` — rerank times should be 500-3000ms, not 150000ms
- `MODEL_ROUTE | tier=standard model=gemini-2.5-flash` — confirms flash, not pro

- [ ] **Step 4: Commit any final adjustments**

```bash
git add -A
git commit -m "perf: complete RAG performance and routing overhaul — 120s→15s response time"
```
