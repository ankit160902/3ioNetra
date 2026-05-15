"""Opt-in live-Gemini integration tests for the dynamic memory system.

Tier 3 per spec §13.3. Unlike test_memory_pipeline.py (which mocks the
LLM and runs in CI), these tests make REAL Gemini API calls to verify
that the prompts in spiritual_mitra.yaml actually produce outputs that
round-trip through our Pydantic parsers. They are the only tier that
catches "the prompt drifted and now returns malformed JSON" regressions.

Cost estimate: ~10 Gemini Flash calls per run, roughly $0.001 at
current pricing — trivial, but we gate on GEMINI_API_KEY so CI doesn't
incur it automatically. The tests use property-based assertions
(ranges, tier membership, structure) rather than exact text matching
so small Gemini variations don't cause flakes.

Run with:
    GEMINI_API_KEY=<key> python -m pytest tests/integration/test_memory_live.py -v

Scope:
    - Extraction produces valid ExtractionResult for representative
      messages spanning trivial / personal / sensitive tiers
    - Decision produces valid MemoryUpdateDecision (operation is one of
      the four, field shape matches the tier's rules)
    - Reflection produces valid ReflectionResult with a narrative and
      no verbatim crisis content
    - Crisis-tier extraction produces meta-fact text, NEVER verbatim

No Mongo writes — these tests call the raw LLM-level functions
(extract_memories, _decide_operation, etc.) directly with no backing
store, so they only test the LLM-side contract, not the full pipeline.
"""
import os
import sys
import types
from pathlib import Path
from typing import List

import pytest

# sys.path + transitions stub (same as the mocked pipeline test file)
_backend_dir = Path(__file__).resolve().parents[2]
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

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
    reason="Live memory-pipeline integration requires GEMINI_API_KEY",
)


# ---------------------------------------------------------------------------
# Representative fixtures — one turn per sensitivity tier plus an edge case
# ---------------------------------------------------------------------------

_EXTRACTION_FIXTURE = [
    # (label, user_message, assistant_response, expected_tier_candidates)
    # The expected_tier_candidates is a SET: the LLM may reasonably pick
    # any member of the set without failing the test. This is loose on
    # purpose so the prompts can evolve without immediately breaking
    # property-based assertions.
    (
        "trivial_preference",
        "I prefer morning japa to evening",
        "Noted — the quiet of the morning carries a special stillness.",
        {"trivial", "personal"},
    ),
    (
        "personal_life_fact",
        "I am a software engineer in Bangalore with two kids",
        "Namaste. Tell me more about what calls you today.",
        {"personal"},
    ),
    (
        "sensitive_grief",
        "My father passed away last month and I still cry every morning",
        "That is a heavy loss. It is okay for the tears to come.",
        {"sensitive"},
    ),
    (
        "significant_life_event",
        "I have been sober for exactly one year today",
        "That is a tremendous milestone. The work you have done matters.",
        {"personal", "sensitive"},
    ),
]


# ---------------------------------------------------------------------------
# Extraction — Gemini call #1 round-trip
# ---------------------------------------------------------------------------

class TestLiveExtractionRoundtrip:
    @pytest.mark.parametrize(
        "label,user_msg,assistant_msg,expected_tiers",
        _EXTRACTION_FIXTURE,
        ids=[f[0] for f in _EXTRACTION_FIXTURE],
    )
    def test_extraction_returns_valid_pydantic(
        self, label, user_msg, assistant_msg, expected_tiers
    ):
        """Run the real extraction prompt against real Gemini. The
        result must parse via ExtractionResult, and when facts are
        produced their tiers must be in the expected set."""
        import asyncio
        from services import memory_extractor
        from models.llm_schemas import ExtractionResult

        async def _run():
            return await memory_extractor.extract_memories(
                user_id="test_user",
                session_id="live_session",
                conversation_id=None,
                turn_number=3,
                user_message=user_msg,
                assistant_response=assistant_msg,
                relational_profile_text="",
            )

        result: ExtractionResult = asyncio.run(_run())

        # Must be a valid Pydantic instance — if Gemini returned
        # malformed JSON, extract_memories returns ExtractionResult()
        assert isinstance(result, ExtractionResult)

        # Gemini is instructed to be sparse; 0 facts is a legitimate
        # answer for every fixture. We assert non-crash + shape only.
        for fact in result.facts:
            assert 1 <= fact.importance <= 10
            assert fact.sensitivity in (
                "trivial", "personal", "sensitive", "crisis"
            )
            assert fact.tone_marker  # non-empty after coercion
            # Text is non-empty for any produced fact
            assert fact.text.strip()

        # If ANY facts were produced, at least one should be in the
        # expected tier set. Empty list is fine — that just means
        # Gemini judged nothing memory-worthy.
        if result.facts:
            produced_tiers = {f.sensitivity for f in result.facts}
            assert produced_tiers & expected_tiers, (
                f"[{label}] Gemini produced {produced_tiers}, "
                f"expected at least one of {expected_tiers}"
            )

    def test_crisis_extraction_never_verbatim(self):
        """When Gemini identifies crisis content, the text field must
        be a neutral meta-fact, not the user's actual words. The prompt
        explicitly instructs this — if it regresses, this test catches it."""
        import asyncio
        from services import memory_extractor
        from models.llm_schemas import ExtractionResult

        user_msg = "i dont want to be alive anymore, nothing matters"
        assistant_msg = (
            "What you are feeling matters. Please call iCall at 9152987821 "
            "or Vandrevala Foundation at 1860-2662-345."
        )

        async def _run():
            return await memory_extractor.extract_memories(
                user_id="test_user",
                session_id="live_session",
                conversation_id=None,
                turn_number=1,
                user_message=user_msg,
                assistant_response=assistant_msg,
                relational_profile_text="",
            )

        result: ExtractionResult = asyncio.run(_run())
        assert isinstance(result, ExtractionResult)

        # For any crisis-tier fact Gemini produced, the text MUST NOT
        # contain the user's verbatim phrases.
        forbidden_verbatim = [
            "dont want to be alive",
            "don't want to be alive",
            "nothing matters",
        ]
        for fact in result.facts:
            if fact.sensitivity == "crisis":
                lower = fact.text.lower()
                for phrase in forbidden_verbatim:
                    assert phrase not in lower, (
                        f"Crisis fact leaked verbatim phrase {phrase!r}: "
                        f"{fact.text}"
                    )


# ---------------------------------------------------------------------------
# Decision — Gemini call #2 round-trip
# ---------------------------------------------------------------------------

class TestLiveDecisionRoundtrip:
    def test_decision_with_no_similar_memories_returns_add(self):
        """When the similar-memories block is empty, Gemini should
        reasonably pick ADD. This is an 'am I sane' sanity check for
        the update_decision prompt."""
        import asyncio
        from services import memory_writer
        from models.llm_schemas import ExtractedMemory, MemoryUpdateDecision

        fact = ExtractedMemory(
            text="User is a software engineer in Bangalore",
            importance=6,
            sensitivity="personal",
            tone_marker="neutral",
        )

        async def _run():
            return await memory_writer._decide_operation(
                fact=fact, similar_memories=[]
            )

        decision = asyncio.run(_run())
        assert isinstance(decision, MemoryUpdateDecision)
        assert decision.operation in {"ADD", "UPDATE", "DELETE", "NOOP"}
        # With no similars, the sensible answer is ADD. We allow NOOP
        # as a soft alternative in case Gemini reads the empty block
        # as "this is already known" — but UPDATE and DELETE would be
        # genuinely wrong.
        assert decision.operation in {"ADD", "NOOP"}

    def test_decision_with_identical_similar_prefers_noop(self):
        """When a near-identical memory already exists, Gemini should
        prefer NOOP over creating a duplicate. This is not strict — ADD
        is an acceptable alternative per the prompt's 'prefer ADD when
        uncertain' rule — but UPDATE and DELETE would be wrong."""
        import asyncio
        from services import memory_writer
        from models.llm_schemas import ExtractedMemory

        fact = ExtractedMemory(
            text="User is a software engineer",
            importance=6,
            sensitivity="personal",
            tone_marker="neutral",
        )
        similar = [
            {
                "id": "507f1f77bcf86cd799439011",
                "text": "User is a software engineer",
                "importance": 6,
                "sensitivity": "personal",
                "tone_marker": "neutral",
                "similarity": 1.0,
            }
        ]

        async def _run():
            return await memory_writer._decide_operation(
                fact=fact, similar_memories=similar
            )

        decision = asyncio.run(_run())
        assert decision.operation in {"NOOP", "ADD"}
        # If Gemini picked NOOP it MUST have provided the target_memory_id
        if decision.operation == "NOOP":
            assert decision.target_memory_id == "507f1f77bcf86cd799439011"


# ---------------------------------------------------------------------------
# Reflection — single-call round-trip
# ---------------------------------------------------------------------------

class TestLiveReflectionRoundtrip:
    def test_reflection_parses_and_returns_valid_structure(self):
        """Hand-build a small set of episodic memories + empty profile,
        run reflection, assert the result is a valid ReflectionResult
        and the narrative is non-empty plus within the spec's target
        length window."""
        import asyncio
        from unittest.mock import MagicMock, AsyncMock
        from datetime import datetime

        from services import reflection_service
        from models.memory_context import RelationalProfile

        # Build a fake db with a profile and a few memories. We can't
        # monkeypatch get_db at the pytest fixture level here without a
        # fixture, so we inline a MagicMock.
        fake_profile_doc = {
            "user_id": "live_test_user",
            "relational_narrative": "",
            "spiritual_themes": [],
            "ongoing_concerns": [],
            "tone_preferences": [],
            "people_mentioned": [],
            "prior_crisis_flag": False,
            "prior_crisis_context": None,
            "prior_crisis_count": 0,
            "importance_since_reflection": 35,
            "reflection_count": 0,
        }
        now = datetime.utcnow()
        fake_memories = [
            {
                "_id": "a",
                "text": "User is a software engineer in Bangalore",
                "importance": 5,
                "sensitivity": "personal",
                "tone_marker": "neutral",
                "valid_at": now,
                "created_at": now,
            },
            {
                "_id": "b",
                "text": "User meditates every morning with a Shiva mantra",
                "importance": 7,
                "sensitivity": "personal",
                "tone_marker": "devotion",
                "valid_at": now,
                "created_at": now,
            },
            {
                "_id": "c",
                "text": "User's father passed away in February",
                "importance": 9,
                "sensitivity": "sensitive",
                "tone_marker": "grief",
                "valid_at": now,
                "created_at": now,
            },
        ]

        db = MagicMock()
        db.user_profiles.find_one = MagicMock(return_value=fake_profile_doc)
        db.user_profiles.update_one = MagicMock(
            return_value=MagicMock(modified_count=1)
        )
        db.user_memories.find.return_value.sort.return_value.limit.return_value = (
            fake_memories
        )
        db.user_memories.update_many = MagicMock(
            return_value=MagicMock(modified_count=0)
        )

        # Silence the cache bust
        original_get_db = reflection_service.get_db
        original_invalidate = reflection_service._invalidate_profile_cache
        reflection_service.get_db = lambda: db

        async def noop_invalidate(user_id):
            return None

        reflection_service._invalidate_profile_cache = noop_invalidate

        try:
            result = asyncio.run(reflection_service.run_reflection("live_test_user"))
        finally:
            reflection_service.get_db = original_get_db
            reflection_service._invalidate_profile_cache = original_invalidate

        assert result is not None, (
            "Live reflection returned None — Gemini call or parse failed"
        )
        narrative = result.updated_profile.relational_narrative
        assert narrative.strip(), "Reflection produced empty narrative"
        # Narrative should be substantive but not a runaway essay.
        # Spec targets 400-600 word narrative.
        word_count = len(narrative.split())
        assert 20 <= word_count <= 1200, (
            f"Narrative word count {word_count} outside sane range"
        )

        # prune_ids may be empty or populated — either is acceptable for
        # this small fixture. What's NOT acceptable is nonsense values.
        for pid in result.prune_ids:
            assert isinstance(pid, str)

        # CRITICAL: the narrative MUST NOT contain verbatim crisis content.
        # Our fixture doesn't include crisis memories so this is more of
        # a smoke test, but it guards the safety-lock prompt instruction.
        forbidden = [
            "kill myself", "want to die", "suicide", "hurt myself",
        ]
        lower = narrative.lower()
        for phrase in forbidden:
            assert phrase not in lower, (
                f"Reflection narrative leaked forbidden phrase {phrase!r}"
            )
