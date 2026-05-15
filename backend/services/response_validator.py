"""
ResponseValidator — final-stage gate between LLM output and the user.

Parallel to ``services.context_validator.ContextValidator`` (which gates
RAG → LLM input), this module gates LLM → user output. It runs after
``llm.service.clean_response()`` and before the response is returned to the
caller. Each check is a small pure function with a single responsibility so
new rules can be added without touching unrelated logic.

Architectural rules (do not break these):
    * No hardcoded domain knowledge. Length limits, scratchpad markers, and
      Devanagari thresholds all come from ``prompts/spiritual_mitra.yaml``
      via ``PromptManager`` so the content team can tune them without code.
    * Hollow / formulaic phrase lists live in ``constants.py`` because they
      are cross-cutting taboos used by both runtime and tests — single
      source of truth.
    * Validator is read-only on the input. Auto-wrap helpers return a new
      string; the validator never mutates argument state.
    * Each check returns a ``CheckResult``. ``ResponseValidator.validate()``
      aggregates all results into a ``ValidationReport`` so the caller can
      see severity and decide whether to retry, repair, or accept.

Severity levels:
    * ``HIGH``  — definite contract violation; caller should regenerate
      (length blowup, scratchpad leak).
    * ``MEDIUM`` — content should be repaired in place (verse auto-wrap)
      or trigger one regeneration if no repair is possible (hollow phrase).
    * ``LOW``  — observation only, used for metrics. Never blocks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from constants import HOLLOW_PHRASES, FORMULAIC_ENDINGS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class CheckResult:
    """Outcome of a single validator check."""
    name: str
    passed: bool
    severity: Severity = Severity.LOW
    reason: str = ""
    repaired_text: Optional[str] = None  # set if the check produced a fixed copy


@dataclass
class ValidationReport:
    """Aggregate result of all checks for one response."""
    text: str                         # final text after any in-place repairs
    passed: bool                      # True iff every HIGH/MEDIUM check passed
    results: List[CheckResult] = field(default_factory=list)

    @property
    def needs_regeneration(self) -> bool:
        return any(
            (not r.passed) and r.severity == Severity.HIGH and r.repaired_text is None
            for r in self.results
        )

    @property
    def correction_hints(self) -> List[str]:
        """Plain-language hints to inject into a regeneration prompt."""
        return [r.reason for r in self.results if not r.passed and r.reason]


# ---------------------------------------------------------------------------
# Scratchpad detection
# ---------------------------------------------------------------------------
# These patterns detect known LLM thinking-mode / chain-of-thought markers
# that we observed leaking through Gemini 2.5/3 preview model responses.
# They are intentionally narrow and high-precision: a false positive would
# trigger needless regeneration, so each pattern targets a meta-text shape
# that no normal Mitra reply would ever produce.
#
# These are the LAST resort. The primary fix is settings.LLM_THINKING_BUDGET_DEFAULT
# which disables thinking mode for the main path entirely. This validator is
# the defense-in-depth net for any future model regression.
_SCRATCHPAD_PATTERNS = (
    re.compile(r'\*\s*Final\s+check', re.IGNORECASE),
    re.compile(r'rule"\s*:\s*\*'),
    re.compile(r'Previous\s+response\s+suggested', re.IGNORECASE),
    re.compile(r'^\s*Used\s+"', re.MULTILINE),
    re.compile(r'\bGood\.\s*\n.*\bGood\.', re.DOTALL),
    re.compile(r'^\s*\*[a-zA-Z][^*\n]*:$', re.MULTILINE),  # "*Final check on X:"
    re.compile(r'\b(thinking|reasoning):\s*\n', re.IGNORECASE),
)


def check_scratchpad_leak(text: str) -> CheckResult:
    """Detect LLM internal-monologue text leaking into user-facing output.

    Returns HIGH severity on any match — the response is unrecoverable in
    place because the leak indicates the LLM emitted meta-text instead of a
    user reply, and that text cannot be safely stripped (we'd be left with
    the wrong content).
    """
    for pattern in _SCRATCHPAD_PATTERNS:
        if pattern.search(text):
            return CheckResult(
                name="scratchpad_leak",
                passed=False,
                severity=Severity.HIGH,
                reason=(
                    "Response contains LLM scratchpad/meta-text. "
                    "Reply with ONLY the user-facing message — no self-critique, "
                    "no 'Previous response', no 'Final check' annotations."
                ),
            )
    return CheckResult(name="scratchpad_leak", passed=True)


# ---------------------------------------------------------------------------
# Prompt-context regurgitation detection
# ---------------------------------------------------------------------------
# Detect Gemini echoing its own RAG-context block back into the user-facing
# reply. Found Apr 2026 in a real user screenshot where a panchang query
# returned "SOURCES: SANATAN SCRIPTURES SANATAN SCRIPTURES
# CURATED_CONCEPTS_GENERATED.## NANDI BULL SYMBOLISM..." appended to the
# actual response. Root cause: curated_concepts data has 3,000+ char
# markdown documents stored in the text/reference fields of verses.json
# (see backend/data/processed/verses.json), which got piped verbatim into
# the prompt RESOURCES block at llm/service.py:1107-1112 and then echoed
# by Gemini.
#
# These patterns are intentionally narrow / high-precision so they don't
# false-positive on legitimate Mitra responses that mention scripture
# (e.g. "the Bhagavad Gita teaches..." should pass).
_PROMPT_LEAK_PATTERNS = (
    re.compile(r'\bSOURCES?\s*:\s*SANATAN', re.IGNORECASE),
    re.compile(r'\bRESOURCE\s+\d+\s*\[', re.IGNORECASE),
    re.compile(r'\bCURATED_CONCEPTS_GENERATED\b', re.IGNORECASE),
    re.compile(r'\bORIGINAL TEXT\s*\(Sanskrit', re.IGNORECASE),
    re.compile(r'^\s*Type\s*:\s*[A-Z_]+\s*\|', re.MULTILINE),
)


def check_prompt_context_leak(text: str) -> CheckResult:
    """Detect LLM regurgitating its own RAG-context prompt block.

    HIGH severity → triggers regeneration with corrective hint, same
    contract as scratchpad leak: the response is unrecoverable in place
    because the leak text is structural prompt content, not something we
    can safely strip without mangling the surrounding reply.
    """
    for pattern in _PROMPT_LEAK_PATTERNS:
        if pattern.search(text):
            return CheckResult(
                name="prompt_context_leak",
                passed=False,
                severity=Severity.HIGH,
                reason=(
                    "Response is repeating the RESOURCES / SOURCES context block. "
                    "Reply with ONLY the user-facing message — never echo the "
                    "RESOURCE labels, the Type/Source headers, or the raw "
                    "scripture context text."
                ),
            )
    return CheckResult(name="prompt_context_leak", passed=True)


# ---------------------------------------------------------------------------
# Length check
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    """Word count that ignores formatting noise.

    Strips both:
    - [VERSE] / [MANTRA] block contents (a long shloka shouldn't blow
      the budget on the surrounding prose)
    - Allowed-markdown syntax tokens (Apr 2026): **bold** wrappers,
      leading "- " bullet markers, and "---" horizontal rules. The
      formatting itself shouldn't consume the user-facing word budget.
    """
    stripped = re.sub(r'\[(VERSE|MANTRA)\][\s\S]*?\[/\1\]', '', text, flags=re.IGNORECASE)
    # Unwrap **bold** so the asterisks don't add fake characters.
    stripped = re.sub(r'\*\*([^*\n]+?)\*\*', r'\1', stripped)
    # Strip "- " bullet prefixes — keep the item content as words.
    stripped = re.sub(r'^[ \t]*-[ \t]+', '', stripped, flags=re.MULTILINE)
    # Drop "---" horizontal rules — they're not words.
    stripped = re.sub(r'^---\s*$', '', stripped, flags=re.MULTILINE)
    return len(stripped.split())


def check_length(text: str, *, min_words: int, max_words: int) -> CheckResult:
    """Word-count gate.

    Args:
        text: Response text. Verse/mantra blocks are excluded from the count.
        min_words: Lower bound from response_constraints YAML.
        max_words: Upper bound from response_constraints YAML.
    """
    wc = _word_count(text)
    if wc > max_words:
        # Apr 2026: downgraded from HIGH → LOW. The LLM self-regulates
        # length via the ADAPTIVE LENGTH prompt instruction. This check
        # is now observational (logged for metrics, never blocks or
        # triggers regen). The hard token budget in TokenBudgetCalculator
        # is the cost safety net; word-count gating was truncating
        # legitimate detailed responses (itineraries, step-by-step guides).
        return CheckResult(
            name="length",
            passed=False,
            severity=Severity.LOW,
            reason=(
                f"Response is {wc} words; soft ceiling is {max_words}. "
                f"(Observational only — not blocking.)"
            ),
        )
    if wc < min_words:
        # Too-short is logged but not blocking — sometimes the right answer
        # is genuinely short ("Yes, you can." / "Take rest tonight.").
        return CheckResult(
            name="length",
            passed=False,
            severity=Severity.LOW,
            reason=f"Response is {wc} words; floor is {min_words}.",
        )
    return CheckResult(name="length", passed=True)


# ---------------------------------------------------------------------------
# Hollow phrase check
# ---------------------------------------------------------------------------

def check_hollow_phrases(text: str) -> CheckResult:
    """Detect banned therapy-bot phrases ("I hear you", "It sounds like", etc.).

    Source of truth: ``constants.HOLLOW_PHRASES`` — same set used by tests
    so a phrase added there is enforced both at runtime and in CI.
    """
    low = text.lower()
    hits = [p for p in HOLLOW_PHRASES if p in low]
    if hits:
        # Apr 2026: elevated from MEDIUM → HIGH. At MEDIUM severity Gemini
        # sometimes ignored the regen hint and kept the phrase. HIGH
        # triggers a hard regen with corrective instructions, which the
        # existing _validate_and_repair loop handles automatically.
        return CheckResult(
            name="hollow_phrases",
            passed=False,
            severity=Severity.HIGH,
            reason=(
                "Response uses banned hollow phrase(s): " + ", ".join(repr(h) for h in hits)
                + ". Rewrite without these — be specific about what you observe."
            ),
        )
    return CheckResult(name="hollow_phrases", passed=True)


def check_formulaic_endings(text: str) -> CheckResult:
    """Detect canned bot-style endings ("Does this resonate?", "Shall I continue?")."""
    low = text.lower()
    hits = [e for e in FORMULAIC_ENDINGS if e in low]
    if hits:
        return CheckResult(
            name="formulaic_endings",
            passed=False,
            severity=Severity.MEDIUM,
            reason=(
                "Response uses formulaic ending(s): " + ", ".join(repr(h) for h in hits)
                + ". End with a natural sentence — no 'how does that sound', no 'shall I continue'."
            ),
        )
    return CheckResult(name="formulaic_endings", passed=True)


# Phrases banned specifically in presence-holding / closure modes. Subset of
# HOLLOW_PHRASES but with mode-specific framing so the regeneration hint can
# point the LLM at the mode contract it violated. This check layers on top
# of check_hollow_phrases — both run, and the more specific (mode-aware)
# message gives the regeneration a sharper instruction.
_BANNED_EMPATHY_BY_MODE = ("i hear you", "i understand", "it sounds like")
_MODES_THAT_FORBID_EMPATHY = ("presence_first", "closure")


def check_banned_empathy_by_mode(text: str, response_mode: Optional[str]) -> CheckResult:
    """HIGH-severity check: banned empathy phrases in presence_first / closure.

    This is the structural backstop for Bug 1 from the E2E test report. The
    mode_prompts.presence_first and mode_prompts.closure YAML blocks both
    explicitly forbid "I hear you" / "I understand" / "It sounds like". When
    the LLM slips into these phrases under strong emotional conversation
    context, this check catches the violation, reports the specific mode
    that's being violated, and triggers ResponseComposer's regeneration
    loop with a mode-aware corrective hint.

    Passes silently when response_mode is None or a mode that DOES allow
    these phrases (teaching, practical_first, exploratory).
    """
    if response_mode not in _MODES_THAT_FORBID_EMPATHY:
        return CheckResult(name="banned_empathy_by_mode", passed=True)
    low = text.lower()
    hits = [p for p in _BANNED_EMPATHY_BY_MODE if p in low]
    if not hits:
        return CheckResult(name="banned_empathy_by_mode", passed=True)
    return CheckResult(
        name="banned_empathy_by_mode",
        passed=False,
        severity=Severity.HIGH,
        reason=(
            f"Response uses banned empathy phrase(s) {hits} which are explicitly "
            f"forbidden in {response_mode} mode. The {response_mode} mode_prompts "
            "block says to be SPECIFIC about what you notice, not generic. "
            "Rewrite without any of these phrases — name the actual thing the "
            "user said that you noticed."
        ),
    )


# ---------------------------------------------------------------------------
# Verse auto-wrap (in-place repair)
# ---------------------------------------------------------------------------

_DEVANAGARI_RUN = re.compile(r'[\u0900-\u097F][\u0900-\u097F\s\u0964\u0965।॥]*[\u0900-\u097F]')
_TAGGED_BLOCK = re.compile(r'\[(VERSE|MANTRA)\][\s\S]*?\[/\1\]', re.IGNORECASE)


def check_verse_tags(text: str, *, min_chars: int = 8) -> CheckResult:
    """Auto-wrap any contiguous Devanagari run >= ``min_chars`` characters
    that is NOT already inside a [VERSE] or [MANTRA] block.

    Why this works without a vocabulary: Devanagari is unambiguous — any
    long run of it is by definition a Sanskrit/Hindi verse fragment, and
    the persona contract says verses must be wrapped. No domain knowledge
    needed.
    """
    # Compute byte ranges of existing tagged blocks so we can skip them.
    tagged_spans = [(m.start(), m.end()) for m in _TAGGED_BLOCK.finditer(text)]

    def in_tagged_span(start: int, end: int) -> bool:
        for ts, te in tagged_spans:
            if ts <= start and end <= te:
                return True
        return False

    repairs: List[tuple] = []  # (start, end, replacement)
    for m in _DEVANAGARI_RUN.finditer(text):
        if (m.end() - m.start()) < min_chars:
            continue
        if in_tagged_span(m.start(), m.end()):
            continue
        repairs.append((m.start(), m.end(), f"[VERSE]\n{m.group(0).strip()}\n[/VERSE]"))

    if not repairs:
        return CheckResult(name="verse_tags", passed=True)

    # Apply repairs from end to start so earlier indices stay valid.
    repaired = text
    for start, end, replacement in reversed(repairs):
        repaired = repaired[:start] + replacement + repaired[end:]

    return CheckResult(
        name="verse_tags",
        passed=False,
        severity=Severity.MEDIUM,
        reason=f"Auto-wrapped {len(repairs)} unwrapped Devanagari verse(s) in [VERSE] tags.",
        repaired_text=repaired,
    )


# ---------------------------------------------------------------------------
# Validator orchestration
# ---------------------------------------------------------------------------

class ResponseValidator:
    """Orchestrates the per-check validators and aggregates a ValidationReport.

    Construction is dependency-injection friendly: pass an alternative
    ``prompt_manager`` in tests to point at a fixture YAML.
    """

    def __init__(self, prompt_manager=None):
        if prompt_manager is None:
            from services.prompt_manager import get_prompt_manager
            prompt_manager = get_prompt_manager()
        self._pm = prompt_manager

    def _constraints_for_phase(self, phase: Optional[str]) -> dict:
        """Look up the response_constraints block for a phase, with a safe
        fallback so callers never crash if YAML drift removes a key."""
        phase_key = (phase or "guidance").lower()
        constraints = self._pm.get_value(
            "spiritual_mitra", f"response_constraints.{phase_key}", default=None
        )
        if not isinstance(constraints, dict):
            # Fall back to guidance — the strictest defensible default.
            constraints = self._pm.get_value(
                "spiritual_mitra", "response_constraints.guidance", default={}
            ) or {}
        return constraints

    def validate(
        self,
        text: str,
        *,
        phase: Optional[str] = None,
        response_mode: Optional[str] = None,
    ) -> ValidationReport:
        """Run every check against ``text``. Returns an aggregate report.

        Repairs (verse auto-wrap) are applied in place to the working text;
        downstream checks see the repaired version so a freshly-wrapped
        verse doesn't trip the length check incorrectly.

        ``response_mode`` (optional) enables mode-specific checks. Today that
        means upgrading hollow-phrase detection to HIGH severity (forcing a
        regeneration) when the active mode is ``presence_first`` or ``closure``
        — both modes explicitly forbid "I hear you" / "I understand" / "It
        sounds like" in their YAML mode_prompts blocks.
        """
        results: List[CheckResult] = []
        working = text or ""

        # Hard-stop check first: scratchpad leak short-circuits everything
        # because the response is unrecoverable in place.
        sl = check_scratchpad_leak(working)
        results.append(sl)

        # Same hard-stop for prompt-context regurgitation. Catches Gemini
        # echoing the RESOURCES block back at the user (the curated_concept
        # SOURCES leak from Apr 2026).
        pl = check_prompt_context_leak(working)
        results.append(pl)

        # Verse auto-wrap (repair-in-place). Run BEFORE length check so a
        # newly wrapped verse is excluded from word count.
        vt = check_verse_tags(
            working,
            min_chars=int(self._pm.get_value(
                "spiritual_mitra",
                "response_validator.devanagari_verse_min_chars",
                default=8,
            )),
        )
        if vt.repaired_text is not None:
            working = vt.repaired_text
        results.append(vt)

        # Length
        constraints = self._constraints_for_phase(phase)
        results.append(check_length(
            working,
            min_words=int(constraints.get("min_words", 20)),
            max_words=int(constraints.get("max_words", 110)),
        ))

        # Style: hollow phrases + formulaic endings
        results.append(check_hollow_phrases(working))
        results.append(check_formulaic_endings(working))

        # Mode-aware banned empathy phrase enforcement — layered on top of
        # the uniform hollow-phrase check above. In presence_first and
        # closure modes, the mode_prompts block explicitly forbids "I hear
        # you" / "I understand" / "It sounds like" as a contract violation.
        # We elevate detection to HIGH severity so the composer regenerates
        # once with corrective hints.
        results.append(check_banned_empathy_by_mode(working, response_mode))

        # Aggregate pass/fail: HIGH or MEDIUM with no repair = fail
        passed = all(
            r.passed or (r.repaired_text is not None) or r.severity == Severity.LOW
            for r in results
        )

        # Log every failed check for observability
        for r in results:
            if not r.passed:
                logger.info(
                    f"ResponseValidator: {r.name} failed (severity={r.severity}) — {r.reason}"
                )

        return ValidationReport(text=working, passed=passed, results=results)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_instance: Optional[ResponseValidator] = None


def get_response_validator() -> ResponseValidator:
    global _instance
    if _instance is None:
        _instance = ResponseValidator()
    return _instance
