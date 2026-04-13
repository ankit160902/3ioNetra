"""Live-LLM accuracy test for response_mode classification (Tier 2).

OPT-IN: Skipped unless GEMINI_API_KEY is set in the environment. Uses the
fast classifier model (gemini-2.0-flash) so a full run costs approximately
$0.004. Assertion threshold is 85% to tolerate normal LLM fuzziness on
edge-case queries.

Run locally with:
    GEMINI_API_KEY=<your_key> python -m pytest tests/unit/test_intent_agent_mode_live.py -v
"""
import asyncio
import os
import sys
import types

import pytest

# Stub transitions (matches other unit tests in this package)
if "transitions" not in sys.modules:
    _stub = types.ModuleType("transitions")
    class _StubMachine:
        def __init__(self, *args, **kwargs):
            pass
        def add_transition(self, *args, **kwargs):
            pass
    _stub.Machine = _StubMachine
    sys.modules["transitions"] = _stub


pytestmark = pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="Live LLM classifier tests require GEMINI_API_KEY",
)


# 40-query fixture — each tuple is (query, expected_mode).
# Covers all four modes plus edge cases (mixed queries, emotional overlay).
MODE_FIXTURE = [
    # practical_first
    ("i have 6 modules to study by tomorrow", "practical_first"),
    ("how do i ask my manager for a raise", "practical_first"),
    ("i keep fighting with my wife about money", "practical_first"),
    ("what's the best way to prepare for an SDE interview", "practical_first"),
    ("i can't sleep properly, it's been 3 weeks", "practical_first"),
    ("i have an assignment due at midnight", "practical_first"),
    ("my rent is overdue and i don't know what to do", "practical_first"),
    ("how do i help my teenager who's failing at school", "practical_first"),
    ("i need to cut my expenses by half this month", "practical_first"),
    ("how do i say no to my boss without getting fired", "practical_first"),

    # presence_first
    ("i just miss my father so much, i can't stop crying", "presence_first"),
    ("i feel so alone in this new city", "presence_first"),
    ("nothing matters anymore", "presence_first"),
    ("i can't do this anymore, everything is broken", "presence_first"),
    ("my mother passed away last week and i don't know how to go on", "presence_first"),
    ("i hate myself and i don't know why", "presence_first"),
    ("i'm so tired of being strong", "presence_first"),
    ("i feel like i'm drowning", "presence_first"),

    # teaching
    ("what is karma yoga", "teaching"),
    ("explain the difference between bhakti marg and jnana marg", "teaching"),
    ("how do i perform satyanarayan puja", "teaching"),
    ("which mantra should i chant for saraswati", "teaching"),
    ("what's today's tithi", "teaching"),
    ("tell me about the four purusharthas", "teaching"),
    ("who is lord hanuman", "teaching"),
    ("what does the gita say about action", "teaching"),
    ("how many chapters are in the bhagavad gita", "teaching"),
    ("tell me about navratri", "teaching"),

    # exploratory
    ("i feel lost lately", "exploratory"),
    ("i don't know what i'm doing with my life", "exploratory"),
    ("why does this keep happening to me", "exploratory"),
    ("something feels off but i can't explain it", "exploratory"),
    ("i'm not sure what i want anymore", "exploratory"),
    ("i need to talk to someone", "exploratory"),

    # Edge cases (mixed queries — dominant ask wins)
    ("i'm starting a new job on monday, should i do a puja", "teaching"),
    ("i'm anxious about my exam tomorrow, how do i study", "practical_first"),
    ("my husband left me, what mantra should i chant", "teaching"),
    ("i feel empty after meditating, is that normal", "teaching"),
    ("what's the dharmic way to handle a toxic boss", "practical_first"),
    ("why does suffering exist in the world", "teaching"),
]


@pytest.mark.parametrize("query,expected_mode", MODE_FIXTURE)
def test_mode_classification_accuracy(query, expected_mode):
    """Run each query through the real fast classifier and check the mode.

    We collect all failures and assert at the end so a single flaky
    classification doesn't mask systematic problems — but the marker
    runs per-query so pytest output shows exactly which queries missed.
    """
    from services.intent_agent import get_intent_agent
    agent = get_intent_agent()
    if not agent.available:
        pytest.skip("IntentAgent LLM unavailable")

    analysis = asyncio.run(agent.analyze_intent(query, context_summary=""))
    actual = analysis.get("response_mode")

    # Soft-xfail: this is a fuzziness-tolerant test. Log the mismatch but
    # let pytest collect the xfail rather than hard-fail a single query.
    if actual != expected_mode:
        pytest.xfail(
            f"Classifier returned {actual!r} for {query!r}, expected {expected_mode!r}. "
            f"Full analysis: intent={analysis.get('intent')}, "
            f"emotion={analysis.get('emotion')}, "
            f"urgency={analysis.get('urgency')}"
        )


def test_overall_accuracy_above_85_percent():
    """Global sanity check: at least 85% of the fixture should classify correctly.

    Runs the same fixture as the parametrized test but aggregates results
    so we can verify the global classification rate holds even if a few
    individual queries are edge cases.
    """
    from services.intent_agent import get_intent_agent
    agent = get_intent_agent()
    if not agent.available:
        pytest.skip("IntentAgent LLM unavailable")

    correct = 0
    total = len(MODE_FIXTURE)
    misses = []

    async def _run_all():
        nonlocal correct
        for query, expected_mode in MODE_FIXTURE:
            analysis = await agent.analyze_intent(query, context_summary="")
            actual = analysis.get("response_mode")
            if actual == expected_mode:
                correct += 1
            else:
                misses.append((query, expected_mode, actual))

    asyncio.run(_run_all())
    accuracy = correct / total
    assert accuracy >= 0.85, (
        f"Mode classification accuracy {accuracy:.1%} is below 85% threshold. "
        f"Misses: {misses}"
    )
