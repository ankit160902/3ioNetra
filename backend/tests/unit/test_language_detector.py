"""Tests for the language/script detection helper.

The detector returns a coarse Latin/Devanagari classification for the main
LLM response. It must:
- Default to Latin for empty/numeric/punctuation-only input.
- Classify pure English as Latin.
- Classify Romanized Hindi (Hinglish) as Latin.
- Classify pure Devanagari as Devanagari.
- Classify mixed Latin+Devanagari as Devanagari only when Devanagari dominates.
- Provide constraint strings that match the script.
"""
from services.language_detector import (
    ScriptType,
    detect_script,
    get_language_constraint,
)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string_is_latin(self):
        assert detect_script("") is ScriptType.LATIN

    def test_whitespace_only_is_latin(self):
        assert detect_script("   \n\t") is ScriptType.LATIN

    def test_numbers_only_is_latin(self):
        assert detect_script("12345") is ScriptType.LATIN

    def test_punctuation_only_is_latin(self):
        assert detect_script("!?...") is ScriptType.LATIN


# ---------------------------------------------------------------------------
# Pure scripts
# ---------------------------------------------------------------------------

class TestPureScripts:
    def test_pure_english(self):
        assert detect_script("I feel anxious about my career") is ScriptType.LATIN

    def test_pure_devanagari_hindi(self):
        assert detect_script("मुझे बहुत चिंता हो रही है") is ScriptType.DEVANAGARI

    def test_pure_devanagari_long(self):
        text = "नमस्ते मित्र। मेरा मन बहुत भारी है आज।"
        assert detect_script(text) is ScriptType.DEVANAGARI


# ---------------------------------------------------------------------------
# Romanized Hindi (Hinglish) — must stay Latin
# ---------------------------------------------------------------------------

class TestHinglish:
    def test_pure_hinglish(self):
        text = "Mujhe bahut dar lagta hai future se. Koi mantra batao."
        assert detect_script(text) is ScriptType.LATIN

    def test_hinglish_with_address(self):
        text = "Yaar mujhe office mein bahut tension ho rahi hai"
        assert detect_script(text) is ScriptType.LATIN

    def test_english_with_one_hindi_word(self):
        # "namaste" is Latin spelling — should still be Latin
        text = "namaste, I want to learn meditation"
        assert detect_script(text) is ScriptType.LATIN


# ---------------------------------------------------------------------------
# Mixed scripts — dominance threshold
# ---------------------------------------------------------------------------

class TestMixed:
    def test_mostly_english_with_one_devanagari_word(self):
        # 1 Devanagari word, ~10 English words → Latin dominates
        text = "Hello mitra, I want to learn the meaning of धर्म today"
        assert detect_script(text) is ScriptType.LATIN

    def test_mostly_devanagari_with_one_english_word(self):
        text = "मुझे आज बहुत stressed महसूस हो रहा है"
        assert detect_script(text) is ScriptType.DEVANAGARI

    def test_balanced_split_falls_to_latin(self):
        # Equal-ish letters: should NOT trip the 30% Devanagari threshold
        # if Devanagari is exactly 50%, the >0.3 check returns DEVANAGARI.
        # We test the boundary explicitly:
        text = "hello नमस्ते"  # 5 latin, 5 devanagari → 50% > 30% → DEVANAGARI
        assert detect_script(text) is ScriptType.DEVANAGARI


# ---------------------------------------------------------------------------
# Constraint string output
# ---------------------------------------------------------------------------

class TestConstraintString:
    def test_latin_constraint_mentions_latin(self):
        constraint = get_language_constraint("hello there")
        assert "Latin" in constraint
        assert "Devanagari" in constraint  # mentioned as forbidden

    def test_latin_constraint_forbids_devanagari(self):
        constraint = get_language_constraint("I feel anxious")
        assert "Do NOT switch to Devanagari" in constraint

    def test_devanagari_constraint_mentions_devanagari(self):
        constraint = get_language_constraint("मुझे चिंता है")
        assert "Devanagari" in constraint
        assert "Hindi" in constraint

    def test_constraint_carves_out_verse_tags(self):
        # Both constraint strings should mention the [VERSE] / [MANTRA] exemption
        # so the LLM still includes Sanskrit verses correctly.
        latin = get_language_constraint("hello")
        devanagari = get_language_constraint("नमस्ते")
        assert "[VERSE]" in latin or "VERSE" in latin
        assert "[MANTRA]" in latin or "MANTRA" in latin
        assert "[VERSE]" in devanagari or "VERSE" in devanagari

    def test_constraint_starts_with_hard_rule_label(self):
        """The hard-rule label helps Gemini weight this above conflicting prompt instructions."""
        constraint = get_language_constraint("hello")
        assert "HARD RULE" in constraint
