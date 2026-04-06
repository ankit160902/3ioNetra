"""Verse and mantra tracking for diversity.

Extracts verse/mantra references from LLM responses and maintains
session-level history to prevent repetitive recommendations.
"""
import re
import logging
from typing import Dict, List

from models.session import SessionState

logger = logging.getLogger(__name__)

# Regex patterns for extracting tagged mantras and verses
_MANTRA_TAG_RE = re.compile(r'\[MANTRA\](.*?)\[/MANTRA\]', re.DOTALL)
_VERSE_TAG_RE = re.compile(r'\[VERSE\](.*?)\[/VERSE\]', re.DOTALL)

# Common verse reference patterns (BG 2.47, Gita 6.26, Yoga Sutra 1.12, etc.)
_VERSE_REF_RE = re.compile(
    r'(?:BG|Gita|Bhagavad Gita|Yoga Sutra|Ramayana|Mahabharata|Upanishad)\s+'
    r'[\d]+[.:]\d+(?:-\d+)?',
    re.IGNORECASE,
)

# Max entries in suggested_verses (prevent unbounded growth)
MAX_VERSE_HISTORY = 20


def extract_verses_from_response(text: str) -> Dict:
    """Extract mantras and verse references from an LLM response.

    Returns dict with:
        mantras: List[str] — mantra texts found in [MANTRA] tags
        references: List[str] — verse citations like "BG 2.47"
    """
    mantras = [m.strip() for m in _MANTRA_TAG_RE.findall(text) if m.strip()]
    references = _VERSE_REF_RE.findall(text)

    # Also check for [VERSE] tags — extract first line as reference
    verse_blocks = _VERSE_TAG_RE.findall(text)
    for block in verse_blocks:
        first_line = block.strip().split('\n')[0].strip()
        if first_line and first_line not in references:
            references.append(first_line[:80])

    return {
        "mantras": mantras,
        "references": references,
    }


def record_suggested_verses(session: SessionState, response_text: str) -> None:
    """Extract and record verse/mantra references from a response into session history."""
    extracted = extract_verses_from_response(response_text)

    if not extracted["mantras"] and not extracted["references"]:
        return

    entry = {
        "turn": session.turn_count,
        "mantras": extracted["mantras"],
        "references": extracted["references"],
    }
    session.suggested_verses.append(entry)

    # Cap history
    if len(session.suggested_verses) > MAX_VERSE_HISTORY:
        session.suggested_verses = session.suggested_verses[-MAX_VERSE_HISTORY:]

    logger.info(
        f"Verse tracker: turn={session.turn_count} "
        f"mantras={extracted['mantras']} refs={extracted['references']}"
    )


def format_verse_history_for_prompt(session: SessionState) -> str:
    """Format suggested verse history as text for LLM prompt injection.

    Returns empty string if no history, otherwise a block like:
    PREVIOUSLY SUGGESTED (offer fresh alternatives — do not repeat):
    - Turn 2: Om Gan Ganapataye Namah | BG 3.19
    - Turn 4: Maha Mrityunjaya | BG 2.13
    """
    if not session.suggested_verses:
        return ""

    lines = ["PREVIOUSLY SUGGESTED (offer fresh alternatives — do NOT repeat these):"]
    for entry in session.suggested_verses:
        parts = []
        if entry.get("mantras"):
            parts.extend(entry["mantras"][:2])
        if entry.get("references"):
            parts.extend(entry["references"][:2])
        if parts:
            lines.append(f"  - Turn {entry.get('turn', '?')}: {' | '.join(parts)}")

    return "\n".join(lines)
