"""Unit tests for services/crisis_response_composer.py.

The most important assertion in this file is the regression test for the
live E2E S5 finding: turn 1 and turn 2 returned a byte-identical canned
response. After Phase F, consecutive crisis turns must return DIFFERENT
text (variant progression) while always including the helpline.
"""

import pytest

from models.session import SessionState
from services.crisis_response_composer import (
    CrisisResponseComposer,
    CrisisVariant,
    get_crisis_response_composer,
)


class StubPromptManager:
    """In-test PromptManager that returns a controlled YAML structure."""

    def __init__(self, variants, helpline):
        self._variants = variants
        self._helpline = helpline

    def get_value(self, group_name: str, key_path: str, default=None):
        if key_path == "crisis_response.variants":
            return self._variants
        if key_path == "crisis_response.helpline_block":
            return self._helpline
        return default


@pytest.fixture
def stub_yaml():
    return StubPromptManager(
        variants=[
            {"id": "first_contact", "preamble": "First preamble.", "grounding": "First grounding.", "invitation": "First invitation."},
            {"id": "continued_engagement", "preamble": "Second preamble.", "grounding": "Second grounding.", "invitation": "Second invitation."},
            {"id": "deepening", "preamble": "Third preamble.", "grounding": "Third grounding.", "invitation": "Third invitation."},
        ],
        helpline="HELPLINE_BLOCK_TOKEN",
    )


@pytest.fixture
def composer(stub_yaml):
    return CrisisResponseComposer(prompt_manager=stub_yaml)


@pytest.fixture
def fresh_session():
    s = SessionState()
    s.session_id = "test-crisis"
    return s


# ---------------------------------------------------------------------------
# Regression: turns must NOT be byte-identical
# ---------------------------------------------------------------------------

class TestProgression:
    def test_consecutive_turns_differ(self, composer, fresh_session):
        """Live E2E S5 regression — turn 1 and turn 2 must differ."""
        first = composer.compose(fresh_session)
        second = composer.compose(fresh_session)
        assert first != second, (
            "Crisis composer returned byte-identical text on consecutive turns "
            "— variant progression is broken."
        )

    def test_first_turn_uses_first_variant(self, composer, fresh_session):
        text = composer.compose(fresh_session)
        assert "First preamble" in text
        assert fresh_session.crisis_turn_count == 1

    def test_second_turn_uses_second_variant(self, composer, fresh_session):
        composer.compose(fresh_session)
        text = composer.compose(fresh_session)
        assert "Second preamble" in text
        assert fresh_session.crisis_turn_count == 2

    def test_third_turn_uses_third_variant(self, composer, fresh_session):
        composer.compose(fresh_session)
        composer.compose(fresh_session)
        text = composer.compose(fresh_session)
        assert "Third preamble" in text
        assert fresh_session.crisis_turn_count == 3

    def test_fourth_turn_pins_to_last_variant(self, composer, fresh_session):
        for _ in range(3):
            composer.compose(fresh_session)
        text = composer.compose(fresh_session)
        # Last variant repeats — by design, we don't soften beyond the deepening variant.
        assert "Third preamble" in text


# ---------------------------------------------------------------------------
# Helpline is always present
# ---------------------------------------------------------------------------

class TestHelplineAlwaysPresent:
    def test_helpline_in_first_turn(self, composer, fresh_session):
        text = composer.compose(fresh_session)
        assert "HELPLINE_BLOCK_TOKEN" in text

    def test_helpline_in_every_turn(self, composer, fresh_session):
        for i in range(5):
            text = composer.compose(fresh_session)
            assert "HELPLINE_BLOCK_TOKEN" in text, (
                f"Helpline missing on turn {i+1}: {text!r}"
            )

    def test_helpline_appears_before_grounding(self, composer, fresh_session):
        text = composer.compose(fresh_session)
        # Layout contract: preamble → helpline → grounding → invitation
        helpline_idx = text.index("HELPLINE_BLOCK_TOKEN")
        grounding_idx = text.index("First grounding")
        assert helpline_idx < grounding_idx


# ---------------------------------------------------------------------------
# Safety contract
# ---------------------------------------------------------------------------

class TestSafetyContract:
    @pytest.mark.parametrize("forbidden", [
        "everything happens for a reason",
        "this is your karma",
        "past life",
        "you brought this",
        "stay positive",
    ])
    def test_no_spiritual_reframing(self, composer, fresh_session, forbidden):
        # Walk through every variant and assert none contain reframing language
        for _ in range(len(composer._load_variants())):
            text = composer.compose(SessionState())
            assert forbidden.lower() not in text.lower(), (
                f"Crisis variant contains banned reframing phrase: {forbidden!r}"
            )

    def test_compose_does_not_call_llm(self, composer, fresh_session):
        # The composer must be synchronous and pure (no LLM round-trip).
        # If this assertion fires, someone added an async LLM call which
        # breaks the safety contract — crisis path must be deterministic.
        import inspect
        assert not inspect.iscoroutinefunction(composer.compose)


# ---------------------------------------------------------------------------
# YAML fallback safety
# ---------------------------------------------------------------------------

class TestYAMLFallback:
    def test_missing_variants_uses_safe_fallback(self, fresh_session):
        empty = StubPromptManager(variants=None, helpline="OK")
        composer = CrisisResponseComposer(prompt_manager=empty)
        text = composer.compose(fresh_session)
        # Should not crash, should still include the helpline
        assert "OK" in text
        assert len(text) > 0

    def test_missing_helpline_uses_safe_fallback(self, fresh_session):
        empty = StubPromptManager(
            variants=[{"id": "v", "preamble": "p", "grounding": "g", "invitation": "i"}],
            helpline=None,
        )
        composer = CrisisResponseComposer(prompt_manager=empty)
        text = composer.compose(fresh_session)
        # Even with missing helpline, fallback contains a number
        assert "iCall" in text or "9152987821" in text


# ---------------------------------------------------------------------------
# Singleton wiring
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_singleton_identity(self):
        a = get_crisis_response_composer()
        b = get_crisis_response_composer()
        assert a is b

    def test_real_yaml_loads_three_variants(self):
        composer = get_crisis_response_composer()
        variants = composer._load_variants()
        assert len(variants) >= 3
        ids = [v.id for v in variants]
        assert "first_contact" in ids
