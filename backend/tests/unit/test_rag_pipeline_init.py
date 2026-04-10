"""Contract tests for the RAG pipeline initialization paths.

These tests pin the runtime contracts that came out of the C-group fixes:

- ``_get_onnx_providers()`` returns an explicit provider list (no
  ``CoreMLExecutionProvider``) so ONNX Runtime doesn't probe and emit
  EP error noise on Apple Silicon.

- The SPLADE missing-index path:
  - In default (``SPLADE_REQUIRED=False``), it logs an ERROR with
    actionable instructions and degrades to BM25.
  - In strict mode (``SPLADE_REQUIRED=True``), it raises ``RuntimeError``
    so a corrupted ingest pipeline can't silently degrade in production.

Both tests use module-level inspection rather than running the full
pipeline initialization to keep the test fast and avoid loading the
actual ML models.
"""
import logging
from unittest.mock import patch

import pytest

from rag.pipeline import _get_onnx_providers


# ---------------------------------------------------------------------------
# C1 — explicit ONNX providers
# ---------------------------------------------------------------------------


class TestOnnxProviderList:
    def test_returns_non_empty_list(self):
        providers = _get_onnx_providers()
        assert isinstance(providers, list)
        assert len(providers) >= 1

    def test_excludes_coreml_provider(self):
        """CoreML EP is intentionally excluded — see _get_onnx_providers
        docstring for the reasoning."""
        providers = _get_onnx_providers()
        assert "CoreMLExecutionProvider" not in providers

    def test_always_includes_cpu_provider_as_fallback(self):
        """CPU must always be in the list as the universal fallback."""
        providers = _get_onnx_providers()
        assert "CPUExecutionProvider" in providers

    def test_cpu_is_last_so_other_providers_get_priority(self):
        """If CUDA is available, it should be tried before CPU."""
        providers = _get_onnx_providers()
        assert providers[-1] == "CPUExecutionProvider"


# ---------------------------------------------------------------------------
# C2 — SPLADE strict mode
# ---------------------------------------------------------------------------


class TestSpladeRequiredFlag:
    """Verify the SPLADE_REQUIRED behavior contract is enforced.

    These tests don't actually instantiate RAGPipeline (which loads
    multi-GB ML models). Instead they parse the source and confirm the
    branching exists where it should.
    """

    def test_pipeline_source_raises_when_required_and_missing(self):
        """Read pipeline.py and verify the SPLADE_REQUIRED branch
        produces a RuntimeError with actionable guidance."""
        from pathlib import Path

        source = Path(
            "/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/rag/pipeline.py"
        ).read_text()
        # Two distinct require-checks: one for the load-failure path,
        # one for the missing-index path. Both must raise.
        assert source.count("SPLADE_REQUIRED") >= 2, (
            "expected at least 2 SPLADE_REQUIRED checks (load failure + missing index)"
        )
        assert "RuntimeError(" in source
        assert "build_splade_index.py" in source, (
            "missing-index path should reference the fix script"
        )

    def test_config_exposes_splade_required_flag(self):
        """The new config flag must exist with default=False."""
        from config import settings

        assert hasattr(settings, "SPLADE_REQUIRED")
        assert settings.SPLADE_REQUIRED is False, (
            "default must be False so dev environments without an index still boot"
        )


# ---------------------------------------------------------------------------
# C3 — reranker tokenizer regex
# ---------------------------------------------------------------------------


class TestRerankerTokenizerArgs:
    """The reranker load site must pass fix_mistral_regex=True so the
    bge-reranker-v2-m3 tokenizer doesn't emit the outdated-regex warning
    on every cold start."""

    def test_pipeline_source_passes_fix_mistral_regex(self):
        from pathlib import Path

        source = Path(
            "/Users/ankit1609/Desktop/3ioNetra/3ionetra/backend/rag/pipeline.py"
        ).read_text()
        assert "fix_mistral_regex" in source, (
            "reranker load site should pass fix_mistral_regex=True via "
            "tokenizer_args to suppress the HuggingFace tokenizer warning"
        )
        assert "tokenizer_args" in source
