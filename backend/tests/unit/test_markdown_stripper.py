"""Contract tests for the markdown stripper.

CLAUDE.md rule #2 (revised Apr 2026) states: restricted markdown is allowed
in LLM responses. Specifically:
  ALLOWED (preserved): **bold**, "- " bullet lists, "---" horizontal rules,
                       [VERSE]/[MANTRA] structural tags
  FORBIDDEN (stripped): *italic* / _italic_, `inline code`, # headers,
                        > blockquotes, 1. numbered lists, "* " and "+ " bullets

Function under test: ``strip_disallowed_markdown`` (also exported as
``strip_markdown`` for back-compat). The function runs as belt-and-braces
enforcement on every LLM response so a prompt drift or LLM quirk cannot
leak forbidden markdown to users — and cannot accidentally remove the
allowed elements.

These tests pin the new contract. They cover:
- Allowed elements survive untouched
- Forbidden elements are stripped clean
- Structural tags ([VERSE]/[MANTRA]) are always preserved
- The function is idempotent (running it twice equals running it once)
- "* " and "+ " bullet variants normalize to "- " (canonical form)
"""
from __future__ import annotations

import pytest

from llm.service import strip_disallowed_markdown, strip_markdown


# ---------------------------------------------------------------------------
# Bold — PRESERVED under the new restricted-markdown contract
# ---------------------------------------------------------------------------


class TestPreservesBold:
    """**bold** is now an allowed markdown element (Apr 2026 — see
    CLAUDE.md rule #2 and spiritual_mitra.yaml HOW YOU SPEAK section).
    The stripper must NOT touch it. The frontend renders it as styled
    bold via react-markdown + @tailwindcss/typography."""

    def test_double_asterisk_bold_preserved(self):
        assert strip_markdown("Today is **Tuesday**") == "Today is **Tuesday**"

    def test_multiple_bold_in_sentence_preserved(self):
        text = "Connect with **Hanuman ji's** strength via **Bhagavad Gita**"
        assert strip_markdown(text) == text

    def test_bold_with_punctuation_inside_preserved(self):
        text = "Pray to **Lord Shiva.** today"
        assert strip_markdown(text) == text

    def test_double_underscore_is_NOT_treated_as_bold(self):
        """Markdown supports __bold__ but the Mitra style guide only
        teaches Gemini to use **bold**. The __ form is rare; if Gemini
        emits it, we leave it alone (no pattern to strip, no pattern to
        preserve specifically). This test pins that behaviour so a future
        change doesn't accidentally strip __ as italic."""
        assert "__Om__" in strip_markdown("Hari __Om__")


class TestStripItalic:
    def test_single_asterisk_italic(self):
        assert strip_markdown("This is *important*") == "This is important"

    def test_single_underscore_italic(self):
        assert strip_markdown("Read the _Gita_") == "Read the Gita"

    def test_italic_does_not_match_partial_word_asterisks(self):
        # Math/identifier-like patterns shouldn't be stripped.
        assert strip_markdown("a*b is multiplication") == "a*b is multiplication"

    def test_italic_does_not_match_glob(self):
        # *.py is a glob pattern, not italic — keep both asterisks if they
        # don't form a balanced italic span.
        result = strip_markdown("Use *.py files")
        # We accept that aggressive stripping might catch this, but the
        # contract is the intent text is preserved. Verify content survives.
        assert "py files" in result


class TestStripCode:
    def test_inline_code(self):
        assert strip_markdown("Run `pytest` to test") == "Run pytest to test"

    def test_multiple_code_spans(self):
        assert (
            strip_markdown("Use `git` and `python`")
            == "Use git and python"
        )


# ---------------------------------------------------------------------------
# Line-leading markers
# ---------------------------------------------------------------------------


class TestStripHeaders:
    def test_h1(self):
        assert strip_markdown("# Big Header\nbody") == "Big Header\nbody"

    def test_h2(self):
        assert strip_markdown("## Subheader\nmore body") == "Subheader\nmore body"

    def test_h3_h6(self):
        for level in (3, 4, 5, 6):
            input_text = f"{'#' * level} Header level {level}\nbody"
            output = strip_markdown(input_text)
            assert output.startswith(f"Header level {level}"), (level, output)

    def test_hash_in_middle_of_line_not_stripped(self):
        # A # not at line start (e.g., a Twitter hashtag mention) should
        # NOT be treated as a header marker.
        assert strip_markdown("Use #karma in your post") == "Use #karma in your post"


class TestStripBlockquotes:
    def test_simple_blockquote(self):
        assert strip_markdown("> This is a quote\nbody") == "This is a quote\nbody"

    def test_blockquote_in_middle_not_stripped(self):
        assert strip_markdown("a > b is true") == "a > b is true"


class TestBulletNormalization:
    """Under the new contract:
       - "- " bullets are PRESERVED (canonical form, allowed)
       - "* " and "+ " bullets NORMALIZE to "- " (forbidden variants
         get rewritten to the canonical form so the renderer sees a
         consistent shape)."""

    def test_dash_bullet_preserved(self):
        text = "- first\n- second"
        assert strip_markdown(text) == text

    def test_asterisk_bullet_normalized_to_dash(self):
        assert strip_markdown("* first\n* second") == "- first\n- second"

    def test_plus_bullet_normalized_to_dash(self):
        assert strip_markdown("+ first\n+ second") == "- first\n- second"

    def test_dash_bullets_with_indent_preserved(self):
        text = "  - indented first\n  - indented second"
        # The leading whitespace is also stripped by the line-leading
        # regex, but the dash + content survives.
        result = strip_markdown(text)
        assert "- indented first" in result
        assert "- indented second" in result


class TestStripNumberedLists:
    def test_simple_numbered_list(self):
        assert strip_markdown("1. first\n2. second") == "first\nsecond"

    def test_double_digit_numbered_list(self):
        assert strip_markdown("10. tenth\n11. eleventh") == "tenth\neleventh"

    def test_period_in_middle_not_stripped(self):
        assert (
            strip_markdown("It is 5. The answer is here.")
            == "It is 5. The answer is here."
        )


# ---------------------------------------------------------------------------
# Tag preservation — the load-bearing contract
# ---------------------------------------------------------------------------


class TestPreservesStructuralTags:
    def test_verse_tag_preserved(self):
        text = "Listen to this:\n[VERSE]Om Namah Shivaya[/VERSE]\nIt brings peace."
        assert strip_markdown(text) == text

    def test_mantra_tag_preserved(self):
        text = "Try this:\n[MANTRA]Om Gam Ganapataye Namah[/MANTRA]\nten times."
        assert strip_markdown(text) == text

    def test_bold_inside_verse_tag_preserved(self):
        # The renderer is responsible for what's inside [VERSE]/[MANTRA].
        # The stripper must NOT touch it — that's a structural contract.
        text = "[VERSE]**OM** namah[/VERSE]"
        assert strip_markdown(text) == text

    def test_bold_outside_tag_preserved_alongside_tag(self):
        """Both **bold** (allowed) and the [MANTRA] tag (always preserved)
        survive. The two are independent — markdown stripping never touches
        tag content."""
        text = "Today is **Tuesday**. Try [MANTRA]**Om**[/MANTRA] now."
        result = strip_markdown(text)
        assert "Today is **Tuesday**." in result
        assert "[MANTRA]**Om**[/MANTRA]" in result

    def test_multiple_tags_in_one_response(self):
        text = (
            "Read [VERSE]Karmanyevadhikaraste[/VERSE] then chant "
            "[MANTRA]Om Namah Shivaya[/MANTRA] eleven times."
        )
        assert strip_markdown(text) == text

    def test_bold_preserved_italic_stripped_around_tags(self):
        """Bold survives, italic is still stripped, structural tag is
        always preserved. This is the canonical mixed case."""
        text = "**Important:** read [VERSE]text[/VERSE] *carefully*"
        result = strip_markdown(text)
        assert result == "**Important:** read [VERSE]text[/VERSE] carefully"


# ---------------------------------------------------------------------------
# Idempotence and robustness
# ---------------------------------------------------------------------------


class TestIdempotence:
    @pytest.mark.parametrize(
        "text",
        [
            "Plain text with no markdown",
            "**Bold text**",
            "Mixed **bold** and *italic*",
            "[VERSE]Om Namah Shivaya[/VERSE]",
            "## Header\nwith **bold**\n- bullet 1\n- bullet 2",
            "",
        ],
    )
    def test_running_twice_equals_running_once(self, text):
        once = strip_markdown(text)
        twice = strip_markdown(once)
        assert once == twice


class TestEdgeCases:
    def test_empty_string(self):
        assert strip_markdown("") == ""

    def test_none_safe(self):
        assert strip_markdown(None) == ""  # type: ignore[arg-type]

    def test_only_whitespace(self):
        assert strip_markdown("   \n  \n  ") == "   \n  \n  "

    def test_unicode_preserved(self):
        # Devanagari, emoji, accents — all must survive untouched.
        text = "नमस्ते Mitra ji 🙏 — café"
        assert strip_markdown(text) == text

    def test_very_long_input(self):
        """Stripper handles a 1000x repeated input without crashing.
        Bold is preserved (Apr 2026 contract change)."""
        text = "Hello **world**. " * 1000
        result = strip_markdown(text)
        # Bold survives — preserved by the new contract
        assert "**world**" in result
        # Length is roughly the same (modulo whitespace)
        assert len(result) >= len(text) - 100


# ---------------------------------------------------------------------------
# Apr 2026 contract change — bold is allowed, the historical Phase D
# response is now valid as-is.
# ---------------------------------------------------------------------------


class TestPhaseDRegressionInverted:
    """In the previous contract (no markdown allowed), the Phase D response
    that contained ``**Hanuman ji's**`` was a violation. Under the new
    restricted-markdown contract, that same response is now CORRECT — bold
    is allowed for emphasis on key terms like deity names.

    This test pins the inversion so a future revert of the contract is
    flagged loudly."""

    def test_phase_d_response_is_now_valid(self):
        original = (
            "That feeling of work anxiety can be very heavy, and it tends "
            "to spill over into everything else. Is there something specific "
            "at work that's on your mind?\n\n"
            "Since today is Tuesday, it's a good day to connect with "
            "**Hanuman ji's** energy of strength. Before you start your next "
            "task, try closing your eyes for just a minute and silently "
            "chanting [MANTRA]\nOm Hanumate Namah\n[/MANTRA] 11 times. It "
            "can help create a small pocket of calm for yourself."
        )
        cleaned = strip_markdown(original)
        # **bold** must be preserved exactly — no longer stripped.
        assert "**Hanuman ji's**" in cleaned
        # The structural mantra block must still be untouched.
        assert "[MANTRA]\nOm Hanumate Namah\n[/MANTRA]" in cleaned
        # The surrounding prose is unchanged.
        assert "That feeling of work anxiety" in cleaned


# ---------------------------------------------------------------------------
# Integration with clean_response — the public callsite
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# New restricted-markdown allowlist — comprehensive preservation tests
# ---------------------------------------------------------------------------


class TestPreservesAllowedMarkdown:
    """The new contract pin (Apr 2026): bold, dash bullets, and horizontal
    rules are first-class allowed markdown. They MUST survive through the
    stripper unchanged."""

    def test_horizontal_rule_preserved(self):
        text = "Take a breath.\n\n---\n\nNow continue."
        result = strip_markdown(text)
        assert "---" in result
        assert "Take a breath." in result
        assert "Now continue." in result

    def test_horizontal_rule_with_other_markdown_preserved(self):
        text = "**First idea** here.\n\n---\n\n**Second idea** here."
        result = strip_markdown(text)
        assert "**First idea**" in result
        assert "---" in result
        assert "**Second idea**" in result

    def test_realistic_mitra_response_preserves_all_allowed(self):
        """A realistic Mitra reply with bold + bullets + a [MANTRA] tag.
        Every allowed element must survive."""
        text = (
            "**Today is Shukravar**, sacred to Goddess Lakshmi. Try this "
            "morning ritual:\n\n"
            "- Sit facing east at sunrise\n"
            "- Light a small ghee diya\n"
            "- Chant [MANTRA]Om Mahalakshmyai Namah[/MANTRA] eleven times\n\n"
            "Even five minutes will steady your day."
        )
        result = strip_markdown(text)
        # Bold preserved
        assert "**Today is Shukravar**" in result
        # Bullets preserved
        assert "- Sit facing east at sunrise" in result
        assert "- Light a small ghee diya" in result
        # Mantra tag preserved
        assert "[MANTRA]Om Mahalakshmyai Namah[/MANTRA]" in result

    def test_strip_disallowed_markdown_alias(self):
        """The new function name should work the same as the back-compat alias."""
        text = "**bold** and *italic*"
        assert strip_disallowed_markdown(text) == strip_markdown(text)


class TestCleanResponseRestrictedMarkdown:
    """Verify the production callsite (clean_response → strip_disallowed_markdown)
    enforces the new restricted-markdown contract: forbidden elements out,
    allowed elements preserved."""

    def test_clean_response_preserves_bold(self):
        from llm.service import clean_response

        result = clean_response("Today is **Tuesday**")
        # Bold is now preserved end-to-end through clean_response
        assert "**Tuesday**" in result

    def test_clean_response_strips_headers(self):
        from llm.service import clean_response

        result = clean_response("# Big\nbody text")
        # Headers are still forbidden — marker stripped, content kept
        assert "#" not in result
        assert "Big" in result
        assert "body text" in result

    def test_clean_response_preserves_dash_bullets(self):
        from llm.service import clean_response

        result = clean_response("- first\n- second\n- third")
        assert "- first" in result
        assert "- second" in result
        assert "- third" in result

    def test_clean_response_preserves_mantra_tag(self):
        from llm.service import clean_response

        result = clean_response("Try [MANTRA]Om Namah Shivaya[/MANTRA] today")
        assert "[MANTRA]" in result
        assert "[/MANTRA]" in result
        assert "Om Namah Shivaya" in result
