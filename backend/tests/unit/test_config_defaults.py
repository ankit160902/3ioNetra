"""Unit tests for config.py default values.

Tests are intentionally minimal — they assert specific default values that
were changed as part of the perf overhaul (Task 1):
  - MAX_RERANK_CANDIDATES: 10 → 12  (40% CrossEncoder speedup on 4GB GPU)
  - MODEL_STANDARD: "gemini-2.5-pro" → "gemini-2.5-flash"  (routing fix)
"""
import sys
from pathlib import Path

import pytest

# Ensure backend/ is on sys.path so `from config import ...` works
_backend_dir = str(Path(__file__).resolve().parents[2])
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from config import Settings


def _make_settings(**overrides) -> Settings:
    """Construct a Settings instance with the minimum required fields."""
    defaults = {
        "GEMINI_API_KEY": "fake",
        "MONGODB_URI": "mongodb://localhost",
        "DATABASE_NAME": "test",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_max_rerank_candidates_default():
    """MAX_RERANK_CANDIDATES default must be 12."""
    s = _make_settings()
    assert s.MAX_RERANK_CANDIDATES == 12


def test_model_standard_default():
    """MODEL_STANDARD default must be 'gemini-2.5-flash'."""
    s = _make_settings()
    assert s.MODEL_STANDARD == "gemini-2.5-flash"
