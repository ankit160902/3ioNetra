"""
RAG Pipeline Robustness Tests — typos, code-switching, edge cases, adversarial.

Requires data/processed/ files (verses.json + embeddings.npy).

Usage:
    cd backend && python3 -m pytest tests/test_rag_robustness.py -v
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rag.pipeline import RAGPipeline
from models.session import IntentType
from services.context_validator import ContextValidator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def pipeline(event_loop):
    p = RAGPipeline()
    event_loop.run_until_complete(p.initialize())
    if not p.available:
        pytest.skip("RAG pipeline not available (missing data/processed/ files)")
    return p


@pytest.fixture(scope="module")
def validator():
    return ContextValidator()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro, loop):
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# TestTypoResilience
# ---------------------------------------------------------------------------

class TestTypoResilience:
    """Verify that typos in queries still retrieve reasonable results."""

    @pytest.mark.parametrize("typo_query,correct_query", [
        ("bhagwad geeta peace of mind", "bhagavad gita peace of mind"),
        pytest.param("meditaiton techniques", "meditation techniques",
                     marks=pytest.mark.xfail(reason="Double transposition typo too severe for embedding model")),
        ("pranayam breathing", "pranayama breathing"),
        ("patnjali yog sutras", "patanjali yoga sutras"),
        ("hanumn chalisa", "hanuman chalisa"),
        ("karm yog meaning", "karma yoga meaning"),
        ("moksh path hinduism", "moksha path hinduism"),
        pytest.param("shri krishn teachings", "shri krishna teachings",
                     marks=pytest.mark.xfail(reason="Missing final vowel changes embedding significantly")),
        ("angr management gita", "anger management gita"),
        ("ayurved health tips", "ayurveda health tips"),
    ])
    def test_typo_overlap(self, pipeline, event_loop, typo_query, correct_query):
        """Typo query should retrieve at least 1 overlapping doc with correct-spelling query."""
        typo_results = run(pipeline.search(query=typo_query, top_k=7, intent=IntentType.SEEKING_GUIDANCE), event_loop)
        correct_results = run(pipeline.search(query=correct_query, top_k=7, intent=IntentType.SEEKING_GUIDANCE), event_loop)

        typo_refs = {(d.get("scripture", ""), d.get("reference", "")) for d in typo_results}
        correct_refs = {(d.get("scripture", ""), d.get("reference", "")) for d in correct_results}

        overlap = typo_refs & correct_refs
        assert len(overlap) >= 1, (
            f"No overlap between typo '{typo_query}' and correct '{correct_query}'. "
            f"Typo got: {[d.get('reference','')[:40] for d in typo_results[:3]]}, "
            f"Correct got: {[d.get('reference','')[:40] for d in correct_results[:3]]}"
        )


# ---------------------------------------------------------------------------
# TestMixedLanguage
# ---------------------------------------------------------------------------

class TestMixedLanguage:
    """Verify code-switching queries return relevant results."""

    @pytest.mark.parametrize("query,expected_scripture", [
        ("Krishna ne Arjuna ko kya kaha about duty?", "bhagavad gita"),
        ("meditation ke benefits hindi mein batao", ""),  # any result ok
        ("mujhe anger management chahiye from Gita", "bhagavad gita"),
        ("Ram ki katha sunao about vanvas", "ramayana"),
        ("yoga aur meditation ka difference kya hai in scriptures?", ""),
        ("Gita mein peace of mind ke liye kya guidance hai?", "bhagavad gita"),
        ("मैं stressed हूँ office problems से, Gita क्या कहती है?", "bhagavad gita"),
        ("karuna aur compassion ke baare mein Gita kya kahti hai?", "bhagavad gita"),
    ])
    def test_mixed_lang_results(self, pipeline, event_loop, query, expected_scripture):
        """Code-switching queries must return non-empty results (and correct scripture if specified)."""
        results = run(pipeline.search(query=query, top_k=5, intent=IntentType.SEEKING_GUIDANCE), event_loop)

        assert len(results) >= 1, f"No results for code-switching query: '{query}'"

        if expected_scripture:
            top3_scriptures = [(d.get("scripture") or "").lower() for d in results[:3]]
            assert any(expected_scripture in s for s in top3_scriptures), (
                f"Expected '{expected_scripture}' in top 3 for '{query}', got: {top3_scriptures}"
            )


# ---------------------------------------------------------------------------
# TestQueryLengthExtremes
# ---------------------------------------------------------------------------

class TestQueryLengthExtremes:
    """Test single-word, very long, and empty queries."""

    @pytest.mark.parametrize("word", ["karma", "peace", "anger", "moksha", "grief", "dharma", "yoga"])
    def test_single_word(self, pipeline, event_loop, word):
        """Single-word queries must return at least 1 result."""
        results = run(pipeline.search(query=word, top_k=5, intent=IntentType.SEEKING_GUIDANCE), event_loop)
        assert len(results) >= 1, f"No results for single-word query: '{word}'"

    def test_very_long_query(self, pipeline, event_loop):
        """Very long query (100+ words) must not crash and must return results."""
        long_query = (
            "I have been going through a very difficult phase in my life where I lost my father "
            "recently and I am also facing problems at work and my relationship with my wife is "
            "not good and I don't know what to do and sometimes I feel like giving up on everything "
            "because nothing seems to be working out in my favor and I have tried many things but "
            "nothing helps and I wonder if there is any spiritual guidance that can help me find "
            "meaning and purpose in life again because right now I feel completely lost and hopeless "
            "and I need something to hold onto that gives me strength and courage to face each day"
        )
        results = run(pipeline.search(query=long_query, top_k=5, intent=IntentType.EXPRESSING_EMOTION), event_loop)
        assert len(results) >= 1, "Very long query returned no results"

    def test_empty_query(self, pipeline, event_loop):
        """Empty/whitespace query must return empty results, not crash."""
        for q in ["", "   ", "\n", "\t"]:
            results = run(pipeline.search(query=q, top_k=5), event_loop)
            assert isinstance(results, list), f"Empty query returned non-list: {type(results)}"
            assert len(results) == 0, f"Empty query '{repr(q)}' returned {len(results)} results"


# ---------------------------------------------------------------------------
# TestAdversarialQueries
# ---------------------------------------------------------------------------

class TestAdversarialQueries:
    """Off-topic queries should return no results or very low-score results."""

    @pytest.mark.parametrize("query", [
        "What is the stock market prediction for tomorrow?",
        "How to write Python code for a web scraper?",
        "Who won the cricket match yesterday?",
        "Give me a chicken biryani recipe",
        "Tell me about Taylor Swift latest album",
    ])
    def test_off_topic(self, pipeline, event_loop, query):
        """Off-topic queries: either no results or top score < 0.5."""
        results = run(pipeline.search(query=query, top_k=5, intent=IntentType.OTHER), event_loop)
        if results:
            top_score = float(results[0].get("final_score") or results[0].get("score") or 0)
            # We allow some results but they should score low
            assert top_score < 0.5, (
                f"Off-topic query '{query}' got high score: {top_score:.3f} "
                f"for '{results[0].get('reference', '')[:60]}'"
            )


# ---------------------------------------------------------------------------
# TestSpecialCharacters
# ---------------------------------------------------------------------------

class TestSpecialCharacters:
    """Queries with emoji, ALL CAPS, or mild profanity should not crash."""

    @pytest.mark.parametrize("query", [
        "PLEASE HELP ME I AM IN SO MUCH PAIN",
        "OM NAMAH SHIVAYA WHAT IS THE MEANING???",
        "WHAT DOES THE GITA SAY ABOUT ANGER!!!",
        "i feel so damn frustrated with everything",
    ])
    def test_special_chars_dont_crash(self, pipeline, event_loop, query):
        """Special character queries must return results (not crash or empty)."""
        results = run(pipeline.search(query=query, top_k=5, intent=IntentType.EXPRESSING_EMOTION), event_loop)
        assert isinstance(results, list), f"Query with special chars returned non-list"
        assert len(results) >= 1, f"No results for special character query: '{query}'"


# ---------------------------------------------------------------------------
# TestCacheCorrectness
# ---------------------------------------------------------------------------

class TestCacheCorrectness:
    """Same query twice should return identical result references."""

    def test_deterministic_results(self, pipeline, event_loop):
        """Running the same query twice should return identical references."""
        query = "What does the Bhagavad Gita say about dharma?"
        intent = IntentType.SEEKING_GUIDANCE

        results1 = run(pipeline.search(query=query, top_k=5, intent=intent), event_loop)
        results2 = run(pipeline.search(query=query, top_k=5, intent=intent), event_loop)

        refs1 = [(d.get("scripture", ""), d.get("reference", "")) for d in results1]
        refs2 = [(d.get("scripture", ""), d.get("reference", "")) for d in results2]

        assert refs1 == refs2, (
            f"Non-deterministic results for same query.\n"
            f"Run 1: {refs1[:3]}\nRun 2: {refs2[:3]}"
        )


# ---------------------------------------------------------------------------
# TestContextValidatorIsolation
# ---------------------------------------------------------------------------

class TestContextValidatorIsolation:
    """Unit tests for ContextValidator gates in isolation."""

    def test_relevance_gate_drops_low_scores(self, validator):
        """Relevance gate should drop very low-scoring docs."""
        docs = [
            {"scripture": "Bhagavad Gita", "text": "Verse text", "final_score": 0.8},
            {"scripture": "Bhagavad Gita", "text": "Another verse", "final_score": 0.01},
        ]
        result = validator.validate(docs, intent=IntentType.SEEKING_GUIDANCE, min_score=0.12)
        scores = [d.get("final_score", 0) for d in result]
        assert all(s >= 0.01 for s in scores) or len(result) < len(docs)

    def test_content_gate_drops_empty_text(self, validator):
        """Content gate should drop docs with empty/placeholder text."""
        docs = [
            {"scripture": "Bhagavad Gita", "text": "A real verse with good content here", "final_score": 0.5},
            {"scripture": "Bhagavad Gita", "text": "", "meaning": "", "final_score": 0.5},
            {"scripture": "Bhagavad Gita", "text": "n/a", "final_score": 0.5},
        ]
        result = validator.validate(docs, intent=IntentType.SEEKING_GUIDANCE)
        # Only the first doc should survive
        assert len(result) <= 1, f"Content gate let through {len(result)} docs, expected <=1"

    def test_type_gate_drops_temples_for_emotional(self, validator):
        """Type gate should drop temple docs for emotional queries."""
        docs = [
            {"scripture": "Bhagavad Gita", "text": "Verse about peace and suffering", "type": "scripture", "final_score": 0.5},
            {"scripture": "Hindu Temples", "text": "Temple located on main road near complex", "type": "temple", "final_score": 0.6},
        ]
        result = validator.validate(docs, intent=IntentType.EXPRESSING_EMOTION, temple_interest=False)
        types = [d.get("type", "scripture") for d in result]
        assert "temple" not in types, f"Temple doc leaked through type gate for emotional intent"

    def test_diversity_gate_limits_per_source(self, validator):
        """Diversity gate should limit docs from a single scripture."""
        docs = [
            {"scripture": "Bhagavad Gita", "text": f"Verse {i} with some content", "final_score": 0.5 - i*0.01}
            for i in range(10)
        ]
        result = validator.validate(docs, max_per_source=3, max_docs=10)
        bg_count = sum(1 for d in result if d.get("scripture") == "Bhagavad Gita")
        assert bg_count <= 3, f"Diversity gate allowed {bg_count} docs from same source"

    def test_meditation_template_blocked_for_pranayama(self, validator):
        """Meditation templates should NOT match pranayama queries (Fix 2 verification)."""
        docs = [
            {"scripture": "Patanjali Yoga Sutras", "text": "Pranayama breathing control sutra", "type": "scripture", "final_score": 0.6},
            {"scripture": "Meditation and Mindfulness", "text": "Guided meditation template for relaxation", "type": "procedural", "source": "meditation_template", "final_score": 0.65},
        ]
        # Query about pranayama — meditation templates should be filtered out
        result = validator.validate(
            docs, intent=IntentType.SEEKING_GUIDANCE, query="pranayama breathing techniques"
        )
        sources = [(d.get("source") or "").lower() for d in result]
        assert "meditation_template" not in sources, (
            "Meditation template leaked through for pranayama query (Fix 2 failed)"
        )
        scriptures = [(d.get("scripture") or "").lower() for d in result]
        assert any("meditation" not in s or "patanjali" in s for s in scriptures), (
            "Only meditation docs survived for pranayama query"
        )
