"""Unit tests for services/response_validator.py.

The most important assertion in this file is the regression test for the
S6-turn-4 scratchpad leak from the live E2E run — any future change that
removes scratchpad detection will fail this suite immediately.
"""

import pytest

from services.response_validator import (
    ResponseValidator,
    Severity,
    check_formulaic_endings,
    check_hollow_phrases,
    check_length,
    check_prompt_context_leak,
    check_scratchpad_leak,
    check_verse_tags,
    get_response_validator,
)


# ---------------------------------------------------------------------------
# Scratchpad regression — exact string from live E2E S6-turn-4
# ---------------------------------------------------------------------------

# Verbatim leak captured during the pre-fix E2E run. If a future SDK change
# reintroduces this kind of meta-text, this test fails immediately.
LIVE_LEAK = (
    'rule":*\n'
    ' Previous response suggested Om Shri Lakshminarayanaya Namah. '
    'This one suggests Om Dum Durgayai Namah. Good.\n\n'
    ' Final check on "No \'Tonight\'":\n'
    ' Used "This Tuesday morning". Good.\n\n'
    ' *Final check'
)


class TestScratchpadDetection:
    def test_live_leak_is_caught(self):
        result = check_scratchpad_leak(LIVE_LEAK)
        assert not result.passed
        assert result.severity == Severity.HIGH
        assert "scratchpad" in result.reason.lower() or "meta" in result.reason.lower()

    def test_normal_response_passes(self):
        text = (
            "That feeling of being abandoned is perhaps the loneliest part of grief. "
            "When the one person who gave you life is gone, it is natural to ask why."
        )
        result = check_scratchpad_leak(text)
        assert result.passed

    @pytest.mark.parametrize("snippet", [
        "*Final check on length",
        'rule":*',
        "Previous response suggested Om Namah Shivaya",
        '*Critique: tone too harsh:',
        "thinking:\n the user is asking about",
    ])
    def test_individual_markers_caught(self, snippet):
        result = check_scratchpad_leak(snippet)
        assert not result.passed, f"Failed to detect scratchpad in: {snippet!r}"


# ---------------------------------------------------------------------------
# Length check
# ---------------------------------------------------------------------------

class TestLengthCheck:
    def test_within_bounds_passes(self):
        text = " ".join(["word"] * 50)
        result = check_length(text, min_words=20, max_words=100)
        assert result.passed

    def test_too_long_fails_high(self):
        text = " ".join(["word"] * 250)
        result = check_length(text, min_words=20, max_words=100)
        assert not result.passed
        assert result.severity == Severity.HIGH
        assert "250" in result.reason
        assert "100" in result.reason

    def test_too_short_fails_low(self):
        text = "Yes, take rest."
        result = check_length(text, min_words=20, max_words=100)
        assert not result.passed
        assert result.severity == Severity.LOW

    def test_verse_blocks_excluded_from_count(self):
        # Surrounding prose: 8 words. Verse content: many words. Should pass
        # under a 20-word ceiling because the verse doesn't count.
        text = (
            "Krishna offers this guidance for your situation today.\n"
            "[VERSE]\n"
            "yada yada hi dharmasya glanir bhavati bharata "
            "abhyutthanam adharmasya tadatmanam srjamy aham\n"
            "[/VERSE]"
        )
        result = check_length(text, min_words=5, max_words=20)
        assert result.passed, f"Verse content should be excluded; got {result.reason}"


# ---------------------------------------------------------------------------
# Hollow / formulaic phrases
# ---------------------------------------------------------------------------

class TestHollowPhrases:
    @pytest.mark.parametrize("phrase", [
        "I hear you, that must be hard.",
        "It sounds like you are struggling.",
        "I understand how that feels.",
    ])
    def test_banned_phrases_caught(self, phrase):
        result = check_hollow_phrases(phrase)
        assert not result.passed
        assert result.severity == Severity.MEDIUM

    def test_clean_response_passes(self):
        result = check_hollow_phrases(
            "Krishna teaches that anger clouds judgment. Pause and breathe."
        )
        assert result.passed


class TestFormulaicEndings:
    @pytest.mark.parametrize("ending", [
        "Try this practice. Does this resonate?",
        "Sit with this verse. How does that sound?",
        "Shall I continue?",
    ])
    def test_formulaic_endings_caught(self, ending):
        result = check_formulaic_endings(ending)
        assert not result.passed

    def test_natural_ending_passes(self):
        result = check_formulaic_endings(
            "Carry this verse with you tomorrow morning. Krishna is with you."
        )
        assert result.passed


# ---------------------------------------------------------------------------
# Verse auto-wrap (no hardcoded vocabulary)
# ---------------------------------------------------------------------------

class TestVerseAutoWrap:
    def test_unwrapped_devanagari_is_wrapped(self):
        text = "Krishna says यदा यदा हि धर्मस्य ग्लानिर्भवति भारत which means..."
        result = check_verse_tags(text)
        assert not result.passed
        assert result.severity == Severity.MEDIUM
        assert result.repaired_text is not None
        assert "[VERSE]" in result.repaired_text
        assert "[/VERSE]" in result.repaired_text
        assert "यदा यदा हि धर्मस्य" in result.repaired_text

    def test_already_wrapped_devanagari_is_left_alone(self):
        text = "[VERSE]\nयदा यदा हि धर्मस्य\n[/VERSE]"
        result = check_verse_tags(text)
        assert result.passed
        assert result.repaired_text is None

    def test_no_devanagari_passes(self):
        result = check_verse_tags("Just plain English with no Sanskrit.")
        assert result.passed

    def test_short_devanagari_run_skipped(self):
        # Single short word — could be inline transliteration, not a verse.
        result = check_verse_tags("ॐ", min_chars=8)
        assert result.passed


# ---------------------------------------------------------------------------
# Orchestration via ResponseValidator
# ---------------------------------------------------------------------------

class TestResponseValidatorOrchestration:
    def test_clean_response_passes_all_checks(self):
        v = get_response_validator()
        text = (
            "Krishna offers a beautiful teaching for this moment. When anger rises, "
            "the mind clouds and judgment falters. Take three slow breaths and let "
            "the heat soften before you speak. The pause itself is the practice."
        )
        report = v.validate(text, phase="guidance")
        assert report.passed, [r.name for r in report.results if not r.passed]

    def test_live_leak_fails_aggregate(self):
        v = get_response_validator()
        report = v.validate(LIVE_LEAK, phase="guidance")
        assert not report.passed
        assert report.needs_regeneration

    def test_too_long_fails_aggregate(self):
        v = get_response_validator()
        text = " ".join(["word"] * 300)
        report = v.validate(text, phase="guidance")
        assert not report.passed
        assert report.needs_regeneration

    def test_verse_repair_does_not_block(self):
        v = get_response_validator()
        text = "Krishna says यदा यदा हि धर्मस्य ग्लानिर्भवति भारत — pause and remember."
        report = v.validate(text, phase="guidance")
        # In-place repair: aggregate should pass, repaired text in report.text
        assert "[VERSE]" in report.text
        assert report.passed or not report.needs_regeneration

    def test_correction_hints_present_when_failing(self):
        v = get_response_validator()
        text = " ".join(["word"] * 250)
        report = v.validate(text, phase="guidance")
        assert any("250" in h or "110" in h for h in report.correction_hints)

    def test_unknown_phase_falls_back_to_guidance(self):
        v = get_response_validator()
        text = " ".join(["word"] * 50)  # would pass guidance
        report = v.validate(text, phase="nonsense_phase")
        assert report.passed


# ---------------------------------------------------------------------------
# Prompt-context regurgitation regression — exact string from live screenshot
# ---------------------------------------------------------------------------

# Verbatim leak captured Apr 2026 from a live panchang query — Gemini echoed
# the curated_concept context block (text + reference) into the user-facing
# reply. Root cause: 216 curated_concepts entries in verses.json have full
# 3,300-char markdown documents stored in their text/reference fields, which
# get piped into the prompt RESOURCES block at llm/service.py:1107-1112 and
# then echoed by the LLM. Fixed by truncating curated_concept text in the
# prompt + adding this validator as defense in depth.
LIVE_PROMPT_LEAK = (
    "Today, Krishna Saptami in Mula nakshatra is auspicious for new beginnings. "
    "Offer water to the Sun at sunrise.\n\n"
    "SOURCES: SANATAN SCRIPTURES SANATAN SCRIPTURES CURATED_CONCEPTS_GENERATED."
    "## NANDI BULL SYMBOLISM\n\n**1. Sanskrit/Hindi Term and Meaning:**\n\n"
    "नन्दी (Nandi) - The bull who serves as the vahana (vehicle) of Lord Shiva..."
)


class TestPromptContextLeakDetection:
    def test_live_sources_block_is_caught(self):
        result = check_prompt_context_leak(LIVE_PROMPT_LEAK)
        assert not result.passed
        assert result.severity == Severity.HIGH
        assert "RESOURCES" in result.reason or "SOURCES" in result.reason

    def test_normal_response_with_scripture_mention_passes(self):
        text = (
            "The Bhagavad Gita 2.47 reminds us that you have the right to action "
            "but never to its fruits. Try chanting Om Namah Shivaya before bed "
            "tonight — it will quiet the storm in your mind."
        )
        result = check_prompt_context_leak(text)
        assert result.passed, f"Clean response wrongly flagged: {result.reason}"

    @pytest.mark.parametrize("snippet", [
        "SOURCES: SANATAN scripts",
        "RESOURCE 1 [BEST MATCH]:",
        "Source: curated_concepts_generated",
        'ORIGINAL TEXT (Sanskrit/Hindi/Procedural): "...',
        "Type: SCRIPTURE | 📖",
    ])
    def test_individual_leak_markers_caught(self, snippet):
        result = check_prompt_context_leak(snippet)
        assert not result.passed, f"Failed to detect prompt leak in: {snippet!r}"

    def test_validator_orchestration_includes_prompt_leak_check(self):
        """The aggregate validate() must run the prompt-leak detector and
        surface it as needs_regeneration when triggered."""
        v = get_response_validator()
        report = v.validate(LIVE_PROMPT_LEAK, phase="guidance")
        assert not report.passed
        assert report.needs_regeneration, "HIGH severity prompt leak must trigger regen"
        # Confirm the named check appears in the results list
        names = [r.name for r in report.results]
        assert "prompt_context_leak" in names


class TestSingleton:
    def test_singleton_identity(self):
        a = get_response_validator()
        b = get_response_validator()
        assert a is b
