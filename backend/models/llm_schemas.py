"""Pydantic response schemas for LLM outputs.

Provides:
    IntentEnum, UrgencyEnum, ExpectedLengthEnum — string enums with tolerant
        coercion (case-insensitive, unknown values fall back to safe defaults).
    IntentAnalysis — the full shape returned by the IntentAgent classifier.
    QueryRewrite, GroundingResult — schemas used by the retrieval_judge.
    extract_json() — resilient JSON extractor that handles clean JSON,
        markdown codefences, and JSON embedded in surrounding prose.
"""
import json
import re
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IntentEnum(str, Enum):
    """Intent categories. Mirrors models.session.IntentType string values."""
    GREETING = "GREETING"
    SEEKING_GUIDANCE = "SEEKING_GUIDANCE"
    EXPRESSING_EMOTION = "EXPRESSING_EMOTION"
    ASKING_INFO = "ASKING_INFO"
    ASKING_PANCHANG = "ASKING_PANCHANG"
    PRODUCT_SEARCH = "PRODUCT_SEARCH"
    CLOSURE = "CLOSURE"
    OTHER = "OTHER"


class UrgencyEnum(str, Enum):
    """Urgency categories for the IntentAgent output."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRISIS = "crisis"


class ExpectedLengthEnum(str, Enum):
    """Expected response length categories."""
    BRIEF = "brief"
    MODERATE = "moderate"
    DETAILED = "detailed"
    FULL_TEXT = "full_text"


# ---------------------------------------------------------------------------
# Default factories
# ---------------------------------------------------------------------------

def _default_product_signal() -> Dict[str, Any]:
    return {
        "intent": "none",
        "confidence": 0.0,
        "type_filter": "any",
        "search_keywords": [],
        "max_results": 0,
        "sensitivity_note": "",
    }


# ---------------------------------------------------------------------------
# IntentAnalysis
# ---------------------------------------------------------------------------

class IntentAnalysis(BaseModel):
    """Structured intent analysis produced by the IntentAgent LLM classifier.

    Tolerant of missing fields, case variations, and unknown enum values —
    bad LLM output coerces to safe defaults rather than raising.
    """

    model_config = ConfigDict(extra="allow")

    intent: IntentEnum = IntentEnum.OTHER
    emotion: str = "neutral"
    life_domain: str = "unknown"
    entities: Dict[str, Any] = Field(default_factory=dict)
    urgency: UrgencyEnum = UrgencyEnum.NORMAL
    summary: str = ""
    needs_direct_answer: bool = False
    product_signal: Dict[str, Any] = Field(default_factory=_default_product_signal)
    recommend_products: bool = False
    product_search_keywords: List[str] = Field(default_factory=list)
    product_rejection: bool = False
    query_variants: List[str] = Field(default_factory=list)
    expected_length: ExpectedLengthEnum = ExpectedLengthEnum.MODERATE
    is_off_topic: bool = False
    response_mode: Literal[
        "practical_first", "presence_first", "teaching", "exploratory", "closure"
    ] = "exploratory"

    @field_validator("intent", mode="before")
    @classmethod
    def _coerce_intent(cls, v: Any) -> IntentEnum:
        if v is None:
            return IntentEnum.OTHER
        if isinstance(v, IntentEnum):
            return v
        try:
            return IntentEnum(str(v).strip().upper())
        except (ValueError, KeyError):
            return IntentEnum.OTHER

    @field_validator("emotion", mode="before")
    @classmethod
    def _coerce_emotion(cls, v: Any) -> str:
        if v is None:
            return "neutral"
        s = str(v).strip().lower()
        return s if s else "neutral"

    @field_validator("life_domain", mode="before")
    @classmethod
    def _coerce_life_domain(cls, v: Any) -> str:
        if v is None:
            return "unknown"
        s = str(v).strip()
        return s if s else "unknown"

    @field_validator("urgency", mode="before")
    @classmethod
    def _coerce_urgency(cls, v: Any) -> UrgencyEnum:
        if v is None:
            return UrgencyEnum.NORMAL
        if isinstance(v, UrgencyEnum):
            return v
        try:
            return UrgencyEnum(str(v).strip().lower())
        except (ValueError, KeyError):
            return UrgencyEnum.NORMAL

    @field_validator("expected_length", mode="before")
    @classmethod
    def _coerce_expected_length(cls, v: Any) -> ExpectedLengthEnum:
        if v is None:
            return ExpectedLengthEnum.MODERATE
        if isinstance(v, ExpectedLengthEnum):
            return v
        try:
            return ExpectedLengthEnum(str(v).strip().lower())
        except (ValueError, KeyError):
            return ExpectedLengthEnum.MODERATE

    @field_validator("response_mode", mode="before")
    @classmethod
    def _coerce_response_mode(cls, v: Any) -> str:
        valid = {"practical_first", "presence_first", "teaching", "exploratory", "closure"}
        if v is None:
            return "exploratory"
        s = str(v).strip().lower()
        return s if s in valid else "exploratory"

    @field_validator("entities", mode="before")
    @classmethod
    def _coerce_entities(cls, v: Any) -> Dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        return {}

    @field_validator("product_search_keywords", mode="before")
    @classmethod
    def _coerce_keywords(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    @field_validator("query_variants", mode="before")
    @classmethod
    def _coerce_variants(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_summary(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to the legacy dict format expected by downstream code.

        Enum values are emitted as their underlying strings (e.g. "GREETING")
        so callers can compare against plain strings without importing the
        enum types.
        """
        return {
            "intent": self.intent.value if isinstance(self.intent, IntentEnum) else str(self.intent),
            "emotion": self.emotion,
            "life_domain": self.life_domain,
            "entities": self.entities,
            "urgency": self.urgency.value if isinstance(self.urgency, UrgencyEnum) else str(self.urgency),
            "summary": self.summary,
            "needs_direct_answer": self.needs_direct_answer,
            "product_signal": self.product_signal,
            "recommend_products": self.recommend_products,
            "product_search_keywords": self.product_search_keywords,
            "product_rejection": self.product_rejection,
            "query_variants": self.query_variants,
            "expected_length": (
                self.expected_length.value
                if isinstance(self.expected_length, ExpectedLengthEnum)
                else str(self.expected_length)
            ),
            "is_off_topic": self.is_off_topic,
            "response_mode": self.response_mode,
        }


# ---------------------------------------------------------------------------
# QueryRewrite / GroundingResult
# ---------------------------------------------------------------------------

class QueryRewrite(BaseModel):
    """Schema for the query-rewriting step inside retrieval_judge."""
    rewritten_query: str = ""

    @field_validator("rewritten_query", mode="before")
    @classmethod
    def _coerce_query(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)


class GroundingResult(BaseModel):
    """Schema for the grounding-verification step.

    ``confidence`` is clamped to [0.0, 1.0]; invalid input (non-numeric)
    defaults to 1.0 so a malformed grounding response never accidentally
    flags a correct answer as ungrounded.
    """
    grounded: bool = True
    confidence: float = 1.0
    issues: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: Any) -> float:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 1.0
        if f < 0.0:
            return 0.0
        if f > 1.0:
            return 1.0
        return f

    @field_validator("issues", mode="before")
    @classmethod
    def _coerce_issues(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("grounded", mode="before")
    @classmethod
    def _coerce_grounded(cls, v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "y")
        return bool(v)


# ---------------------------------------------------------------------------
# Dynamic memory system (Apr 2026) — see docs/superpowers/specs/2026-04-12-
# dynamic-memory-design.md for the design that motivates these models.
# ---------------------------------------------------------------------------

_VALID_SENSITIVITY_TIERS = {"trivial", "personal", "sensitive", "crisis"}
_VALID_UPDATE_OPERATIONS = {"ADD", "UPDATE", "DELETE", "NOOP"}


class ExtractedMemory(BaseModel):
    """One fact extracted from a single user turn by MemoryExtractor.

    Importance is LLM-assigned on a 1-10 scale. Sensitivity is one of four
    tiers that drive retrieval filtering. tone_marker is a free-text single
    word that names the dominant emotional tone (grief/joy/anxiety/etc.) —
    used for tone-aware retrieval of sensitive memories.

    All fields are tolerant of bad LLM output: out-of-range importance
    clamps, unknown sensitivity defaults to "personal", missing tone_marker
    defaults to "neutral".
    """

    model_config = ConfigDict(extra="allow")

    text: str
    importance: int = 5
    sensitivity: str = "personal"
    tone_marker: str = "neutral"

    @field_validator("text", mode="before")
    @classmethod
    def _coerce_text(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("importance", mode="before")
    @classmethod
    def _clamp_importance(cls, v: Any) -> int:
        try:
            i = int(v)
        except (TypeError, ValueError):
            return 5
        if i < 1:
            return 1
        if i > 10:
            return 10
        return i

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, v: Any) -> str:
        if v is None:
            return "personal"
        s = str(v).strip().lower()
        return s if s in _VALID_SENSITIVITY_TIERS else "personal"

    @field_validator("tone_marker", mode="before")
    @classmethod
    def _coerce_tone(cls, v: Any) -> str:
        if v is None:
            return "neutral"
        s = str(v).strip().lower()
        return s if s else "neutral"


class ExtractionResult(BaseModel):
    """Output of MemoryExtractor Gemini call #1. Zero facts is valid."""

    model_config = ConfigDict(extra="allow")

    facts: List[ExtractedMemory] = Field(default_factory=list)


class MemoryUpdateDecision(BaseModel):
    """Output of MemoryUpdater Gemini call #2. Mem0 ADD/UPDATE/DELETE/NOOP.

    ADD — new memory, no existing similar memory captures this fact.
    UPDATE — target_memory_id refines/supersedes; updated_text is the merged text.
    DELETE — target_memory_id is no longer true; don't insert new fact.
    NOOP — target_memory_id already captures this fact; no write, just bump access.
    """

    model_config = ConfigDict(extra="allow")

    operation: str = "ADD"
    target_memory_id: Optional[str] = None
    updated_text: Optional[str] = None
    reason: str = ""

    @field_validator("operation", mode="before")
    @classmethod
    def _coerce_operation(cls, v: Any) -> str:
        if v is None:
            return "ADD"
        s = str(v).strip().upper()
        return s if s in _VALID_UPDATE_OPERATIONS else "ADD"

    @field_validator("target_memory_id", mode="before")
    @classmethod
    def _coerce_target_id(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("updated_text", mode="before")
    @classmethod
    def _coerce_updated_text(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None

    @field_validator("reason", mode="before")
    @classmethod
    def _coerce_reason(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)


class ReflectionProfilePatch(BaseModel):
    """The profile-delta portion of ReflectionResult.

    Represents the updated relational profile after consolidation. Each list
    field is capped at 10 items by the ReflectionService (not by Pydantic)
    so the profile never balloons past its prompt-injection budget.
    """

    model_config = ConfigDict(extra="allow")

    relational_narrative: str = ""
    spiritual_themes: List[str] = Field(default_factory=list)
    ongoing_concerns: List[str] = Field(default_factory=list)
    tone_preferences: List[str] = Field(default_factory=list)
    people_mentioned: List[str] = Field(default_factory=list)

    @field_validator("relational_narrative", mode="before")
    @classmethod
    def _coerce_narrative(cls, v: Any) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator(
        "spiritual_themes", "ongoing_concerns",
        "tone_preferences", "people_mentioned",
        mode="before",
    )
    @classmethod
    def _coerce_str_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if x is not None and str(x).strip()]
        return []


class ReflectionResult(BaseModel):
    """Output of ReflectionService Gemini call. Produced by one LLM call
    that does BOTH consolidation (the updated_profile) AND pruning (the
    prune_ids list of episodic memory ids to invalidate).
    """

    model_config = ConfigDict(extra="allow")

    updated_profile: ReflectionProfilePatch = Field(
        default_factory=ReflectionProfilePatch
    )
    prune_ids: List[str] = Field(default_factory=list)

    @field_validator("prune_ids", mode="before")
    @classmethod
    def _coerce_prune_ids(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if x is not None and str(x).strip()]
        return []


# ---------------------------------------------------------------------------
# JSON extractor
# ---------------------------------------------------------------------------

_JSON_CODEFENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```",
    re.DOTALL | re.IGNORECASE,
)


def extract_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extract a JSON object from text, handling various wrapping styles.

    Strategies, in order:
        1. Try direct json.loads on the stripped text.
        2. Strip markdown codefences (```json ... ``` or ``` ... ```) and retry.
        3. Find the first '{' and scan for the matching '}' with escape-aware
           string tracking; attempt to parse that slice.

    Returns ``None`` for empty / whitespace-only input or when no valid JSON
    object can be recovered. Returns only dict objects — top-level arrays or
    scalars are treated as failure.
    """
    if text is None:
        return None
    stripped = text.strip()
    if not stripped:
        return None

    # Strategy 1: direct parse
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: markdown codefence (```json ... ``` or ``` ... ```)
    m = _JSON_CODEFENCE_RE.search(stripped)
    if m:
        inner = m.group(1).strip()
        try:
            result = json.loads(inner)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: balanced-brace scan respecting string escapes
    start = stripped.find('{')
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_string:
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = stripped[start:i + 1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, dict):
                            return result
                    except (json.JSONDecodeError, ValueError):
                        return None
                    return None
    return None
