"""Tests for verse history tracking and diversity."""
import importlib.util
from pathlib import Path

from models.session import SessionState
from models.memory_context import ConversationMemory, UserStory

_vt_path = str(Path(__file__).resolve().parents[2] / "services" / "verse_tracker.py")
_spec = importlib.util.spec_from_file_location("verse_tracker", _vt_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
extract_verses_from_response = _mod.extract_verses_from_response
record_suggested_verses = _mod.record_suggested_verses
format_verse_history_for_prompt = _mod.format_verse_history_for_prompt
detect_repetition = _mod.detect_repetition


def _make_session():
    s = SessionState()
    s.memory = ConversationMemory(story=UserStory())
    s.turn_count = 1
    return s


class TestExtractVerses:
    def test_extracts_mantra_tags(self):
        text = "Try chanting [MANTRA]Om Namah Shivaya[/MANTRA] 11 times."
        result = extract_verses_from_response(text)
        assert "Om Namah Shivaya" in result["mantras"]

    def test_extracts_multiple_mantras(self):
        text = "[MANTRA]Om Gan Ganapataye Namah[/MANTRA] and also [MANTRA]Om Shanti[/MANTRA]"
        result = extract_verses_from_response(text)
        assert len(result["mantras"]) == 2

    def test_extracts_verse_tags(self):
        text = "The Gita says [VERSE]2.47 Karmanye Vadhikaraste...[/VERSE]"
        result = extract_verses_from_response(text)
        assert len(result["references"]) >= 1

    def test_extracts_verse_references_from_text(self):
        text = "As Bhagavad Gita 2.47 teaches us about karma yoga, and Yoga Sutra 1.12 about practice."
        result = extract_verses_from_response(text)
        assert any("2.47" in r for r in result["references"])

    def test_empty_response(self):
        result = extract_verses_from_response("Just a regular response without mantras.")
        assert result["mantras"] == []
        assert result["references"] == []


class TestRecordSuggestedVerses:
    def test_records_to_session(self):
        s = _make_session()
        record_suggested_verses(s, "Chant [MANTRA]Om Namah Shivaya[/MANTRA] tonight.")
        assert len(s.suggested_verses) == 1
        assert "Om Namah Shivaya" in s.suggested_verses[0]["mantras"]

    def test_doesnt_record_empty(self):
        s = _make_session()
        record_suggested_verses(s, "I understand how you feel.")
        assert len(s.suggested_verses) == 0

    def test_caps_at_max(self):
        s = _make_session()
        for i in range(25):
            s.turn_count = i
            record_suggested_verses(s, f"[MANTRA]Mantra {i}[/MANTRA]")
        assert len(s.suggested_verses) <= 20


class TestFormatForPrompt:
    def test_empty_history_returns_empty(self):
        s = _make_session()
        assert format_verse_history_for_prompt(s) == ""

    def test_formats_history(self):
        s = _make_session()
        s.suggested_verses = [
            {"turn": 2, "mantras": ["Om Namah Shivaya"], "references": ["BG 2.47"]},
            {"turn": 4, "mantras": ["Gayatri Mantra"], "references": []},
        ]
        result = format_verse_history_for_prompt(s)
        assert "PREVIOUSLY SUGGESTED" in result
        assert "Om Namah Shivaya" in result
        assert "Gayatri Mantra" in result
        assert "do NOT repeat" in result


class TestDetectRepetition:
    def test_no_history_returns_empty(self):
        s = _make_session()
        repeats = detect_repetition(s, "[MANTRA]Om Namah Shivaya[/MANTRA]")
        assert repeats == []

    def test_no_repetition(self):
        s = _make_session()
        s.suggested_verses = [
            {"turn": 1, "mantras": ["Om Gan Ganapataye Namah"], "references": []}
        ]
        repeats = detect_repetition(s, "[MANTRA]Om Namah Shivaya[/MANTRA]")
        assert repeats == []

    def test_exact_mantra_repetition_caught(self):
        s = _make_session()
        s.suggested_verses = [
            {"turn": 1, "mantras": ["Om Namah Shivaya"], "references": []}
        ]
        s.turn_count = 2
        repeats = detect_repetition(s, "Try [MANTRA]Om Namah Shivaya[/MANTRA] again.")
        assert "om namah shivaya" in repeats

    def test_case_and_whitespace_normalized(self):
        s = _make_session()
        s.suggested_verses = [
            {"turn": 1, "mantras": ["Om Namah Shivaya"], "references": []}
        ]
        s.turn_count = 2
        # Different casing and trailing space
        repeats = detect_repetition(s, "Chant [MANTRA] OM NAMAH SHIVAYA  [/MANTRA]")
        assert len(repeats) == 1

    def test_verse_reference_repetition_caught(self):
        """Same scripture name + chapter.verse → caught.

        Note: detect_repetition compares normalized strings, so "BG 2.47" and
        "Bhagavad Gita 2.47" are treated as different references. This is a
        deliberate trade-off — telemetry shouldn't try to alias scripture
        names. The extractor pulls "Bhagavad Gita 2.47" from free text via
        the reference regex, so we use that exact form in the prior history.
        """
        s = _make_session()
        s.suggested_verses = [
            {"turn": 1, "mantras": [], "references": ["Bhagavad Gita 2.47"]}
        ]
        s.turn_count = 2
        repeats = detect_repetition(s, "Bhagavad Gita 2.47 says...")
        assert any("2.47" in r for r in repeats)

    def test_different_scripture_naming_not_aliased(self):
        """BG 2.47 vs Bhagavad Gita 2.47 are not aliased (documented limit)."""
        s = _make_session()
        s.suggested_verses = [
            {"turn": 1, "mantras": [], "references": ["BG 2.47"]}
        ]
        s.turn_count = 2
        # Even though the reference points to the same verse, the strings
        # don't match after normalization. detect_repetition is intentionally
        # exact-match; aliasing scripture names belongs to a richer
        # canonicalization layer if we ever need it.
        repeats = detect_repetition(s, "Bhagavad Gita 2.47 says...")
        assert len(repeats) == 0

    def test_multiple_repeats(self):
        s = _make_session()
        s.suggested_verses = [
            {"turn": 1, "mantras": ["Om Namah Shivaya", "Om Gan Ganapataye Namah"], "references": []}
        ]
        s.turn_count = 2
        repeats = detect_repetition(
            s,
            "[MANTRA]Om Namah Shivaya[/MANTRA] and [MANTRA]Om Gan Ganapataye Namah[/MANTRA]"
        )
        assert len(repeats) == 2

    def test_response_without_mantras_returns_empty(self):
        s = _make_session()
        s.suggested_verses = [
            {"turn": 1, "mantras": ["Om Namah Shivaya"], "references": []}
        ]
        repeats = detect_repetition(s, "I hear how hard this is.")
        assert repeats == []
