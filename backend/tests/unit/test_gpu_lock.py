"""GPU access lock — serialization contract tests.

Verifies that concurrent calls to generate_embeddings() and
generate_embeddings_batch() are serialized through _gpu_lock so that
simultaneous inference requests don't cause VRAM contention on small GPUs.

Strategy
--------
We replace the embedding model's .encode() with a *slow* mock (sleeps 0.05s
inside asyncio.to_thread so the event loop actually yields between callers).
We then fire N concurrent calls and record wall-clock overlap: if the lock is
absent, calls run in parallel and the total elapsed time is ≈ sleep_time; if
the lock is present, calls are serialized and total elapsed time is ≈ N *
sleep_time.

We do NOT instantiate a real RAGPipeline (that loads multi-GB ML models).
Instead we patch the singleton instance's ``_embedding_model`` attribute
directly after importing the module so the module-level ``_gpu_lock`` is
always exercised regardless of instance state.
"""
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Ensure backend/ is on sys.path
_backend_dir = str(Path(__file__).resolve().parents[2])
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SLEEP_S = 0.05  # Each fake encode() call sleeps this long
CONCURRENCY = 4  # Number of simultaneous callers


def _make_slow_encode(sleep_s: float, call_log: list):
    """Return a synchronous callable that records start/end times and sleeps.

    This mimics a blocking GPU kernel that takes ``sleep_s`` seconds.
    It is run inside asyncio.to_thread, so time.sleep is appropriate here.
    """
    def _encode(texts, **kwargs):
        start = time.monotonic()
        call_log.append(("start", start))
        time.sleep(sleep_s)
        end = time.monotonic()
        call_log.append(("end", end))
        # Return a list of zero vectors matching input length
        return [np.zeros(4, dtype="float32") for _ in texts]

    return _encode


def _has_overlap(call_log: list) -> bool:
    """Return True if any two encode() calls overlapped in wall-clock time."""
    # Extract (start, end) pairs from interleaved log
    calls = []
    starts = {}
    for event, t in call_log:
        if event == "start":
            # Use position as a key since a call may start multiple times
            calls.append([t, None])
        else:
            # Match end to the most recent unfinished start
            for c in reversed(calls):
                if c[1] is None:
                    c[1] = t
                    break

    # Check every pair for overlap
    for i in range(len(calls)):
        for j in range(i + 1, len(calls)):
            s1, e1 = calls[i]
            s2, e2 = calls[j]
            if e1 is None or e2 is None:
                continue
            # Overlap exists if one started before the other ended
            if s1 < e2 and s2 < e1:
                return True
    return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pipeline_with_mock_model():
    """Import RAGPipeline and attach a fake embedding model to a fresh instance.

    We create a minimal instance that bypasses all real initialization so the
    test doesn't need Redis, MongoDB, or model files.
    """
    # Import here so sys.path manipulation is already in effect
    import rag.pipeline as pipeline_module

    # Build a lightweight RAGPipeline-like object using __new__ to skip __init__
    from rag.pipeline import RAGPipeline
    instance = RAGPipeline.__new__(RAGPipeline)

    # Set the attributes that generate_embeddings() / generate_embeddings_batch() read
    instance._embedding_model = MagicMock()
    instance.dim = 4
    instance._reranker_model = None
    instance._splade_index = None

    # Stub out _ensure_embedding_model so it's a no-op
    instance._ensure_embedding_model = lambda: None

    # Stub _needs_instruction_prefix → False to keep clean_text simple
    instance._needs_instruction_prefix = lambda: False

    return instance, pipeline_module


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGpuLockExists:
    """Structural checks — the lock accessor must exist at module level."""

    def test_gpu_lock_is_defined(self, pipeline_with_mock_model):
        _, pipeline_module = pipeline_with_mock_model
        assert hasattr(pipeline_module, "_gpu_lock"), (
            "_gpu_lock must be a module-level attribute of rag.pipeline"
        )

    @pytest.mark.asyncio
    async def test_gpu_lock_returns_asyncio_lock(self, pipeline_with_mock_model):
        _, pipeline_module = pipeline_with_mock_model
        # _gpu_lock is a callable that returns the loop-bound Lock
        lock = pipeline_module._gpu_lock()
        assert isinstance(lock, asyncio.Lock), (
            "_gpu_lock() must return an asyncio.Lock instance"
        )

    @pytest.mark.asyncio
    async def test_gpu_lock_returns_same_lock_within_loop(self, pipeline_with_mock_model):
        _, pipeline_module = pipeline_with_mock_model
        lock1 = pipeline_module._gpu_lock()
        lock2 = pipeline_module._gpu_lock()
        assert lock1 is lock2, (
            "_gpu_lock() must return the same Lock object when called on the same event loop"
        )


class TestGpuLockSerializesGenerateEmbeddings:
    """Concurrent generate_embeddings() calls must not overlap."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_are_serialized(self, pipeline_with_mock_model):
        instance, pipeline_module = pipeline_with_mock_model
        call_log: list = []

        # Replace model.encode with a slow, logging mock
        instance._embedding_model.encode = _make_slow_encode(SLEEP_S, call_log)

        # Fire CONCURRENCY calls simultaneously
        tasks = [
            asyncio.create_task(instance.generate_embeddings(f"text {i}"))
            for i in range(CONCURRENCY)
        ]
        t_start = time.monotonic()
        await asyncio.gather(*tasks)
        t_end = time.monotonic()

        elapsed = t_end - t_start
        # With serialization: elapsed ≥ CONCURRENCY * SLEEP_S * 0.9 (10% tolerance)
        expected_min = CONCURRENCY * SLEEP_S * 0.9
        assert elapsed >= expected_min, (
            f"Total elapsed {elapsed:.3f}s < expected {expected_min:.3f}s — "
            "calls appear to have run in parallel (lock not in effect)"
        )

        # No two encode() calls should have overlapped
        assert not _has_overlap(call_log), (
            "Two or more encode() calls overlapped — _gpu_lock is not serializing correctly"
        )


class TestGpuLockSerializesGenerateEmbeddingsBatch:
    """Concurrent generate_embeddings_batch() calls must not overlap."""

    @pytest.mark.asyncio
    async def test_concurrent_batch_calls_are_serialized(self, pipeline_with_mock_model):
        instance, pipeline_module = pipeline_with_mock_model
        call_log: list = []

        instance._embedding_model.encode = _make_slow_encode(SLEEP_S, call_log)

        texts_batches = [["text a", "text b"], ["text c", "text d"]] * (CONCURRENCY // 2)
        tasks = [
            asyncio.create_task(instance.generate_embeddings_batch(batch))
            for batch in texts_batches
        ]
        t_start = time.monotonic()
        await asyncio.gather(*tasks)
        t_end = time.monotonic()

        elapsed = t_end - t_start
        expected_min = len(texts_batches) * SLEEP_S * 0.9
        assert elapsed >= expected_min, (
            f"Total elapsed {elapsed:.3f}s < expected {expected_min:.3f}s — "
            "batch calls appear to have run in parallel (lock not in effect)"
        )

        assert not _has_overlap(call_log), (
            "Two or more batch encode() calls overlapped — _gpu_lock is not serializing correctly"
        )


class TestGpuLockSharedAcrossSingleAndBatch:
    """A generate_embeddings() call blocks a concurrent generate_embeddings_batch()."""

    @pytest.mark.asyncio
    async def test_single_and_batch_share_lock(self, pipeline_with_mock_model):
        instance, _ = pipeline_with_mock_model
        call_log: list = []

        instance._embedding_model.encode = _make_slow_encode(SLEEP_S, call_log)

        # Launch one of each simultaneously
        tasks = [
            asyncio.create_task(instance.generate_embeddings("single text")),
            asyncio.create_task(instance.generate_embeddings_batch(["batch a", "batch b"])),
        ]
        await asyncio.gather(*tasks)

        assert not _has_overlap(call_log), (
            "generate_embeddings() and generate_embeddings_batch() ran concurrently — "
            "they must share _gpu_lock"
        )
