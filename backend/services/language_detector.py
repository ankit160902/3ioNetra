"""Programmatic language and script detection for response mirroring.

The system prompt instructs Gemini to mirror the user's language, but Gemini's
self-inference is unreliable when the system prompt itself contains heavy
Hindi vocabulary (deity names, dharmic terms, mantras). This module provides
a deterministic script check and a hard constraint string that gets injected
into the LLM prompt to override Gemini's default language behavior.

Public API:
    ScriptType.LATIN | ScriptType.DEVANAGARI
    detect_script(text: str) -> ScriptType
    get_language_constraint(text: str) -> str
"""
from __future__ import annotations

import re
from enum import Enum


class ScriptType(str, Enum):
    """Dominant script of a piece of user text."""

    LATIN = "latin"
    DEVANAGARI = "devanagari"


# Devanagari Unicode block (U+0900..U+097F) covers Hindi, Marathi, Sanskrit.
# Extended Devanagari (U+A8E0..U+A8FF) is rare in user input — omitted to keep
# the regex small. If needed in the future, add it here.
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")

# Threshold: if more than 30% of letter characters are Devanagari, treat the
# message as Devanagari-script. Below 30% the message is treated as Latin
# (English or Romanized Hindi). The 30% threshold tolerates incidental
# Devanagari characters inside [VERSE] tags or proper-noun mixing.
_DEVANAGARI_DOMINANCE_THRESHOLD = 0.3


def detect_script(text: str) -> ScriptType:
    """Return the dominant script of the user message.

    Defaults to Latin for empty/numeric/whitespace-only input. Pure Devanagari
    returns DEVANAGARI. Mixed input returns DEVANAGARI only if Devanagari
    characters dominate; otherwise Latin (which keeps Hinglish in Latin script).
    """
    if not text:
        return ScriptType.LATIN

    devanagari_count = len(_DEVANAGARI_RE.findall(text))
    latin_count = len(_LATIN_LETTER_RE.findall(text))
    total = devanagari_count + latin_count

    if total == 0:
        # Numbers, punctuation, or whitespace only — default to Latin.
        return ScriptType.LATIN

    if (devanagari_count / total) > _DEVANAGARI_DOMINANCE_THRESHOLD:
        return ScriptType.DEVANAGARI
    return ScriptType.LATIN


def get_language_constraint(text: str) -> str:
    """Return a hard-constraint string for injection into the LLM prompt.

    The string explicitly tells Gemini which script to use for the main
    response, with a carve-out for Sanskrit verses inside the existing
    [VERSE] / [MANTRA] tag conventions.
    """
    script = detect_script(text)
    if script == ScriptType.DEVANAGARI:
        return (
            "LANGUAGE CONSTRAINT (HARD RULE): The user wrote in Devanagari script. "
            "Respond in Hindi using Devanagari script. Do not use Latin/Roman script "
            "for the main response (Sanskrit verses inside [VERSE] or [MANTRA] tags "
            "are exempt from this rule)."
        )
    return (
        "LANGUAGE CONSTRAINT (HARD RULE): The user wrote in Latin script. "
        "Respond ONLY in Latin script — either English or Romanized Hindi/Hinglish. "
        "Do NOT switch to Devanagari script for the main response. Match the user's "
        "register: if they wrote pure English, respond in English; if they used "
        "Hinglish, mirror it. Sanskrit text inside [VERSE] or [MANTRA] tags may "
        "use Devanagari."
    )
