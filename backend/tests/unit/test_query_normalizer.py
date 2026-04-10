"""Unit tests for services/query_normalizer.py.

The most important assertion in this file is the regression test for the
"How → homa" / "Give → gita" mangling that the previous Levenshtein-based
spell corrector caused. Any change that reintroduces token substitution will
fail this suite immediately.

The normalizer is intentionally narrow — NFKC + whitespace only. There is
no hardcoded dharmic vocabulary, no English→Sanskrit dictionary, and no
spell correction. Bilingual / synonym handling is the IntentAgent's job.
"""

import unicodedata

import pytest

from services.query_normalizer import (
    NormalizedQuery,
    QueryNormalizer,
    get_query_normalizer,
)


@pytest.fixture
def normalizer() -> QueryNormalizer:
    return QueryNormalizer()


# ---------------------------------------------------------------------------
# Regression tests — these enforce the C3 fix
# ---------------------------------------------------------------------------

class TestEnglishQueriesAreNeverMangled:
    """The legacy spell corrector replaced 'How' with 'homa' and 'Give' with
    'gita' because it operated on whole strings against a dharmic vocabulary.
    These tests assert that NO token in the user's question is ever replaced.
    """

    @pytest.mark.parametrize(
        "query",
        [
            "How to write Python code for a web scraper",
            "Give me a chicken biryani recipe",
            "how do I find peace when I can't change the situation",
            "What is the stock market prediction for tomorrow",
            "Tell me about Taylor Swift latest album",
            "Who won the cricket match yesterday",
        ],
    )
    def test_user_tokens_preserved(self, normalizer: QueryNormalizer, query: str):
        result = normalizer.normalize(query)
        # Every original word must still be present in the normalized query.
        for original_token in query.split():
            assert original_token in result.normalized, (
                f"Token {original_token!r} was lost or substituted. "
                f"Original={query!r}, normalized={result.normalized!r}"
            )

    def test_homa_substitution_never_happens(self, normalizer: QueryNormalizer):
        result = normalizer.normalize("How to write Python code")
        assert "homa" not in result.normalized.lower(), (
            f"Got {result.normalized!r} — 'How' must never be replaced with 'homa'"
        )

    def test_gita_substitution_never_happens(self, normalizer: QueryNormalizer):
        result = normalizer.normalize("Give me a chicken biryani recipe")
        assert "gita" not in result.normalized.lower(), (
            f"Got {result.normalized!r} — 'Give' must never be replaced with 'gita'"
        )

    def test_normalizer_has_no_hardcoded_vocabulary(self):
        """Defense-in-depth: the module must not import or define any
        dharmic vocabulary set or English→Sanskrit dictionary. If anyone
        adds one back, this test fails immediately.
        """
        import services.query_normalizer as qn
        forbidden_names = (
            "_DHARMIC_VOCABULARY",
            "_ENGLISH_TO_SANSKRIT",
            "KNOWN_DHARMIC_TERMS",
            "_augment_english_concepts",
            "_correct_spelling",
            "_correct_word",
            "_levenshtein_distance",
        )
        for name in forbidden_names:
            assert not hasattr(qn, name), (
                f"query_normalizer.py must not define {name}. "
                "Domain knowledge belongs in IntentAgent, not in normalization."
            )


# ---------------------------------------------------------------------------
# Core normalization
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_returns_normalized_query_dataclass(self, normalizer: QueryNormalizer):
        result = normalizer.normalize("hello world")
        assert isinstance(result, NormalizedQuery)
        assert result.original == "hello world"
        assert result.normalized == "hello world"

    def test_collapses_whitespace(self, normalizer: QueryNormalizer):
        result = normalizer.normalize("   what   is    karma   ")
        assert result.normalized == "what is karma"

    def test_nfkc_unicode_normalization(self, normalizer: QueryNormalizer):
        # ﬁ (U+FB01) is a ligature; NFKC decomposes it to "fi"
        result = normalizer.normalize("ﬁnd peace")
        assert result.normalized == "find peace"
        assert result.normalized == unicodedata.normalize("NFKC", result.normalized)

    def test_devanagari_passthrough(self, normalizer: QueryNormalizer):
        # Hindi should pass through unchanged (after NFKC).
        result = normalizer.normalize("मुझे शांति चाहिए")
        assert result.normalized == "मुझे शांति चाहिए"

    def test_empty_input_safe(self, normalizer: QueryNormalizer):
        result = normalizer.normalize("")
        assert result.original == ""
        assert result.normalized == ""

    def test_none_input_safe(self, normalizer: QueryNormalizer):
        result = normalizer.normalize(None)  # type: ignore[arg-type]
        assert result.original == ""

    def test_language_hint_preserved(self, normalizer: QueryNormalizer):
        result = normalizer.normalize("hello", language="en")
        assert result.language == "en"


# ---------------------------------------------------------------------------
# Singleton wiring
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_query_normalizer_returns_singleton(self):
        a = get_query_normalizer()
        b = get_query_normalizer()
        assert a is b

    def test_singleton_normalizes_correctly(self):
        result = get_query_normalizer().normalize("How to find peace")
        assert "How" in result.normalized
        assert "peace" in result.normalized
        assert "homa" not in result.normalized.lower()
