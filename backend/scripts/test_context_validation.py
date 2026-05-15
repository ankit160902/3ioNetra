"""
test_context_validation.py — Spot-checks the 5-rule ContextValidator gates
and the end-to-end context selection logic.

Run from backend/:
    python3 scripts/test_context_validation.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.context_validator import ContextValidator

# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def make_doc(
    text="A meaningful spiritual verse about peace and dharma",
    scripture="Bhagavad Gita",
    doc_type="scripture",
    score=0.45,
    reference="2.47"
):
    return {
        "text": text,
        "scripture": scripture,
        "type": doc_type,
        "score": score,
        "reference": reference,
        "meaning": "A verse about acting without attachment to results.",
    }


def run_test(name, fn):
    try:
        fn()
        print(f"  ✅ {name}")
    except AssertionError as e:
        print(f"  ❌ {name}: {e}")


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------

v = ContextValidator()

def test_gate1_relevance_drops_low_score():
    docs = [make_doc(score=0.05), make_doc(score=0.40)]
    out = v.validate(docs, min_score=0.12)
    assert len(out) == 1, f"Expected 1 doc, got {len(out)}"
    assert out[0]["score"] == 0.40

def test_gate1_empty_input():
    out = v.validate([], min_score=0.12)
    assert out == []

def test_gate2_content_drops_placeholder():
    docs = [
        make_doc(text="intermediate"),
        make_doc(text="A valid deep verse about karma and dharma in life."),
    ]
    out = v.validate(docs, min_score=0.0)
    assert len(out) == 1, f"Expected 1 doc after placeholder drop, got {len(out)}"

def test_gate2_content_drops_short():
    docs = [make_doc(text="Hi"), make_doc(text="Long enough spiritual text here for testing")]
    out = v.validate(docs, min_score=0.0)
    assert len(out) == 1, f"Expected 1 doc after short-text drop, got {len(out)}"

def test_gate3_type_defers_temple_for_emotional_intent():
    docs = [
        make_doc(doc_type="temple", text="Sri Ram Temple, Ayodhya, Uttar Pradesh located near Sarayu river."),
        make_doc(doc_type="scripture", text="A verse about grief and compassion from the Ramayana."),
    ]
    out = v.validate(docs, intent="EXPRESSING_EMOTION", temple_interest=False, min_score=0.0)
    # Temple should be deferred to end OR kept if nothing else passes
    # Scripture should come first
    assert out[0]["type"] == "scripture", f"Expected scripture first, got {out[0]['type']}"

def test_gate3_type_keeps_temple_when_temple_interest():
    docs = [
        make_doc(doc_type="temple", text="Mahakaleshwar Jyotirlinga, Ujjain, Madhya Pradesh."),
        make_doc(doc_type="scripture", text="Long enough spiritual verse about pilgrimages."),
    ]
    out = v.validate(docs, intent="EXPRESSING_EMOTION", temple_interest=True, min_score=0.0)
    # Both should be kept since temple_interest is True
    assert len(out) == 2

def test_gate4_scripture_allowlist():
    docs = [
        make_doc(scripture="Bhagavad Gita"),
        make_doc(scripture="Ramayana"),
        make_doc(scripture="Mahabharata"),
    ]
    out = v.validate(docs, allowed_scriptures=["Bhagavad Gita"], min_score=0.0)
    assert len(out) == 1
    assert out[0]["scripture"] == "Bhagavad Gita"

def test_gate4_scripture_allowlist_fallback_when_no_match():
    docs = [
        make_doc(scripture="Mahabharata"),
        make_doc(scripture="Ramayana"),
    ]
    # If allowlist matches nothing → graceful fallback: return all
    out = v.validate(docs, allowed_scriptures=["Bhagavad Gita"], min_score=0.0)
    assert len(out) == 2, "Allowlist fallback should return all docs when no match"

def test_gate5_diversity_max_per_source():
    docs = [
        make_doc(scripture="Bhagavad Gita", score=0.9),
        make_doc(scripture="Bhagavad Gita", score=0.8),
        make_doc(scripture="Bhagavad Gita", score=0.7),
        make_doc(scripture="Ramayana", score=0.6),
    ]
    out = v.validate(docs, max_per_source=2, min_score=0.0)
    gita_count = sum(1 for d in out if d["scripture"] == "Bhagavad Gita")
    assert gita_count <= 2, f"Expected max 2 Gita docs, got {gita_count}"
    # Ramayana should still be present
    ram_count = sum(1 for d in out if d["scripture"] == "Ramayana")
    assert ram_count == 1

def test_gate5_max_docs():
    docs = [make_doc(scripture=f"Source{i}", score=0.5) for i in range(10)]
    out = v.validate(docs, max_docs=3, max_per_source=10, min_score=0.0)
    assert len(out) <= 3

def test_product_search_intent_excludes_scripture():
    """PRODUCT_SEARCH intent should exclude scripture docs in companion_engine."""
    # We test the companion engine helper logic
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from services.companion_engine import CompanionEngine
    engine = CompanionEngine()
    
    exclusions = engine._get_doc_type_exclusions("PRODUCT_SEARCH")
    assert "scripture" in (exclusions or []), f"Expected 'scripture' in exclusions, got {exclusions}"

def test_emotional_intent_excludes_temple():
    from services.companion_engine import CompanionEngine
    engine = CompanionEngine()
    exclusions = engine._get_doc_type_exclusions("EXPRESSING_EMOTION")
    assert "temple" in (exclusions or []), f"Expected 'temple' in exclusions, got {exclusions}"

def test_seeking_guidance_no_exclusions():
    from services.companion_engine import CompanionEngine
    engine = CompanionEngine()
    exclusions = engine._get_doc_type_exclusions("SEEKING_GUIDANCE")
    # Guidance queries can use both scripture and procedural
    assert not exclusions, f"Expected no exclusions for SEEKING_GUIDANCE, got {exclusions}"


# ----------------------------------------------------------------
# Main runner
# ----------------------------------------------------------------

if __name__ == "__main__":
    print("\n🔍 ContextValidator — Gate Tests\n" + "="*45)
    
    print("\n[Gate 1: Relevance]")
    run_test("Drops low-score docs", test_gate1_relevance_drops_low_score)
    run_test("Handles empty input", test_gate1_empty_input)

    print("\n[Gate 2: Content Quality]")
    run_test("Drops placeholder text", test_gate2_content_drops_placeholder)
    run_test("Drops too-short text", test_gate2_content_drops_short)

    print("\n[Gate 3: Type Appropriateness]")
    run_test("Defers temple for emotional intent", test_gate3_type_defers_temple_for_emotional_intent)
    run_test("Keeps temple when temple_interest=True", test_gate3_type_keeps_temple_when_temple_interest)

    print("\n[Gate 4: Scripture Allowlist]")
    run_test("Filters to allowed scriptures", test_gate4_scripture_allowlist)
    run_test("Graceful fallback when allowlist matches nothing", test_gate4_scripture_allowlist_fallback_when_no_match)

    print("\n[Gate 5: Diversity]")
    run_test("Max per source enforced", test_gate5_diversity_max_per_source)
    run_test("Max docs enforced", test_gate5_max_docs)

    print("\n[Intent → doc_type_exclusions]")
    run_test("PRODUCT_SEARCH excludes scripture", test_product_search_intent_excludes_scripture)
    run_test("EXPRESSING_EMOTION excludes temple", test_emotional_intent_excludes_temple)
    run_test("SEEKING_GUIDANCE has no exclusions", test_seeking_guidance_no_exclusions)

    print("\n" + "="*45)
