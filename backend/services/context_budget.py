"""Context Budget Manager — prevents response truncation.

Manages the token budget for LLM prompts. Ensures the total input
never exceeds a safe threshold, leaving adequate room for the output.

When over budget, trims sections by priority (lowest-priority first):
  1. verse_history (anti-repetition hints)
  2. past_memories (nice-to-have context)
  3. panchang (nice-to-have date context)
  4. user_profile (reducible to essentials)
  5. conversation_history (reduce message count)
  6. rag_context (reduce document count)
  7. system_instruction, phase_prompt, current_query (NEVER trimmed)
"""
import logging
from typing import Dict, List, Optional

from config import settings

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Fast token estimation. ~4 chars per token for English/Hindi mixed text."""
    if not text:
        return 0
    return len(text) // 4


# Section priorities (higher number = trimmed LAST = more important)
SECTION_PRIORITIES = {
    "system_instruction": 10,
    "phase_prompt": 9,
    "current_query": 9,
    "length_hint": 8,
    "rag_context": 6,
    "conversation_history": 5,
    "user_profile": 4,
    "panchang": 3,
    "past_memories": 2,
    "verse_history": 1,
    "returning_user": 1,
}

# Target input budget — configurable via settings
DEFAULT_TARGET_INPUT = getattr(settings, "PROMPT_TARGET_INPUT_TOKENS", 12000)
DEFAULT_SAFETY_MARGIN = getattr(settings, "PROMPT_SAFETY_MARGIN", 500)
MIN_HISTORY_MESSAGES = getattr(settings, "PROMPT_MIN_HISTORY_MESSAGES", 4)
MIN_RAG_DOCS = getattr(settings, "PROMPT_MIN_RAG_DOCS", 1)


class ContextBudgetManager:
    """Ensures prompt sections fit within token budget.

    Usage:
        manager = ContextBudgetManager(max_output_tokens=2048)
        trimmed = manager.fit(sections)
        # trimmed is a dict of section_name → text, with lowest-priority sections trimmed
    """

    def __init__(self, max_output_tokens: int = 2048):
        self.max_output = max_output_tokens
        self.target_input = DEFAULT_TARGET_INPUT
        self.safety_margin = DEFAULT_SAFETY_MARGIN
        self.budget = self.target_input - self.safety_margin
        self._trims_applied: List[str] = []

    def fit(self, sections: Dict[str, str]) -> Dict[str, str]:
        """Trim sections to fit within budget. Returns new dict with trimmed content.

        Never modifies the input dict. Returns a copy.
        """
        result = dict(sections)
        self._trims_applied = []

        total = sum(estimate_tokens(v) for v in result.values())

        if total <= self.budget:
            logger.debug(f"Context budget OK: {total} tokens (budget: {self.budget})")
            return result

        overage = total - self.budget
        logger.info(
            f"Context budget OVER by {overage} tokens "
            f"(total: {total}, budget: {self.budget}). Trimming..."
        )

        # Sort sections by priority (lowest first = trim first)
        trimmable = sorted(
            [(name, SECTION_PRIORITIES.get(name, 5)) for name in result if name in SECTION_PRIORITIES],
            key=lambda x: x[1],
        )

        for section_name, priority in trimmable:
            if overage <= 0:
                break

            # Never trim critical sections
            if priority >= 8:
                continue

            content = result.get(section_name, "")
            tokens = estimate_tokens(content)

            if tokens == 0:
                continue

            # Trimming strategy depends on section type
            if section_name in ("verse_history", "returning_user"):
                # Remove entirely
                saved = tokens
                result[section_name] = ""
                self._trims_applied.append(f"Removed {section_name} ({saved} tokens)")

            elif section_name == "past_memories":
                # Keep only last 3 lines
                lines = content.strip().split("\n")
                if len(lines) > 4:  # header + 3 entries
                    trimmed_content = "\n".join(lines[:1] + lines[-3:])
                    saved = tokens - estimate_tokens(trimmed_content)
                    result[section_name] = trimmed_content
                    self._trims_applied.append(f"Trimmed past_memories to 3 entries ({saved} tokens)")
                else:
                    saved = tokens
                    result[section_name] = ""
                    self._trims_applied.append(f"Removed past_memories ({saved} tokens)")

            elif section_name == "panchang":
                # Remove entirely
                saved = tokens
                result[section_name] = ""
                self._trims_applied.append(f"Removed panchang ({saved} tokens)")

            elif section_name == "user_profile":
                # Reduce to essentials: keep first 3 lines (name, emotion, life_area)
                lines = content.strip().split("\n")
                if len(lines) > 5:
                    essential = "\n".join(lines[:5])
                    saved = tokens - estimate_tokens(essential)
                    result[section_name] = essential
                    self._trims_applied.append(f"Trimmed user_profile to essentials ({saved} tokens)")

            elif section_name == "conversation_history":
                # Reduce from 14 messages to fewer
                lines = content.strip().split("\n")
                # Each message is ~2-4 lines. Trim to keep roughly half.
                if len(lines) > 12:
                    half = max(8, len(lines) // 2)
                    trimmed_content = "\n".join(lines[-half:])
                    saved = tokens - estimate_tokens(trimmed_content)
                    result[section_name] = trimmed_content
                    self._trims_applied.append(f"Trimmed conversation_history ({saved} tokens)")

            elif section_name == "rag_context":
                # Remove last doc(s). RAG docs are separated by "---" or doc markers.
                # Simple approach: trim to ~60% of original
                target_len = int(len(content) * 0.6)
                if target_len < len(content):
                    trimmed_content = content[:target_len].rsplit("\n", 1)[0]
                    saved = tokens - estimate_tokens(trimmed_content)
                    result[section_name] = trimmed_content
                    self._trims_applied.append(f"Trimmed rag_context ({saved} tokens)")

            overage -= (tokens - estimate_tokens(result.get(section_name, "")))

        # Log results
        new_total = sum(estimate_tokens(v) for v in result.values())
        if self._trims_applied:
            for trim in self._trims_applied:
                logger.info(f"  TRIM: {trim}")
            logger.info(f"  Final: {new_total} tokens (was {total}, saved {total - new_total})")

        return result

    @property
    def trims_applied(self) -> List[str]:
        """Return list of trims applied in last fit() call."""
        return self._trims_applied


def trim_conversation_history(
    messages: List[Dict],
    max_messages: int = 14,
    max_tokens: int = 3000,
) -> List[Dict]:
    """Trim conversation history to fit within token budget.

    Keeps most recent messages. If still over token budget, further trims.
    """
    recent = messages[-max_messages:] if len(messages) > max_messages else list(messages)

    # Estimate total tokens
    total = sum(estimate_tokens(m.get("content", "")) for m in recent)

    if total <= max_tokens:
        return recent

    # Over budget — remove oldest messages until within budget
    while len(recent) > MIN_HISTORY_MESSAGES and total > max_tokens:
        removed = recent.pop(0)
        total -= estimate_tokens(removed.get("content", ""))

    return recent


def trim_rag_docs(
    docs: List[Dict],
    max_docs: int = 5,
    max_tokens: int = 3000,
) -> List[Dict]:
    """Trim RAG documents to fit within token budget.

    Keeps highest-scored docs. Truncates individual doc text if needed.
    """
    trimmed = docs[:max_docs]

    total = sum(estimate_tokens(d.get("text", "") + d.get("meaning", "")) for d in trimmed)

    if total <= max_tokens:
        return trimmed

    # Over budget — reduce doc count
    while len(trimmed) > MIN_RAG_DOCS and total > max_tokens:
        removed = trimmed.pop()
        total -= estimate_tokens(removed.get("text", "") + removed.get("meaning", ""))

    # If still over, truncate individual doc texts
    if total > max_tokens and trimmed:
        per_doc_budget = max_tokens // len(trimmed)
        for doc in trimmed:
            text = doc.get("text", "")
            meaning = doc.get("meaning", "")
            combined = text + meaning
            if estimate_tokens(combined) > per_doc_budget:
                # Truncate to budget
                char_limit = per_doc_budget * 4
                if len(meaning) > char_limit // 2:
                    doc["meaning"] = meaning[:char_limit // 2] + "..."
                if len(text) > char_limit // 2:
                    doc["text"] = text[:char_limit // 2] + "..."

    return trimmed
