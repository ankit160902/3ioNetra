from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import List, Optional, Dict
from enum import Enum
from models.session import ConversationPhase

# Max user input length — prevents Gemini API overload and circuit breaker trips
_MAX_QUERY_LENGTH = 2000

class TextQuery(BaseModel):
    query: str = Field(..., max_length=_MAX_QUERY_LENGTH)
    language: str = "en"
    include_citations: bool = True
    conversation_history: Optional[List[dict]] = None

class TextResponse(BaseModel):
    answer: str
    citations: List[dict]
    language: str
    confidence: float

class ConversationPhaseEnum(str, Enum):
    """Enum for API responses"""
    clarification = "clarification"
    synthesis = "synthesis"
    answering = "answering"
    listening = "listening"
    guidance = "guidance"
    closure = "closure"

class SessionCreateResponse(BaseModel):
    """Response when creating a new session"""
    session_id: str
    phase: ConversationPhaseEnum
    message: str

class SessionStateResponse(BaseModel):
    """Response for session state query"""
    session_id: str
    phase: ConversationPhaseEnum
    turn_count: int
    signals_collected: Dict[str, str]
    created_at: str

class UserProfileContext(BaseModel):
    """User profile for personalization (from authenticated user)"""
    age_group: str = ""
    gender: str = ""
    profession: str = ""
    name: str = ""
    preferred_deity: str = ""
    location: str = ""
    spiritual_interests: List[str] = []
    rashi: str = ""
    gotra: str = ""
    nakshatra: str = ""

class ConversationalQuery(BaseModel):
    """Request body for conversational endpoint"""
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=_MAX_QUERY_LENGTH)
    language: str = "en"
    user_profile: Optional[UserProfileContext] = None

class SourceReference(BaseModel):
    """Individual source reference with confidence scoring"""
    scripture: str
    reference: str
    context_text: str
    relevance_score: float

class FlowMetadata(BaseModel):
    """Conversation analytics for flow monitoring"""
    detected_domain: Optional[str] = None
    emotional_state: Optional[str] = None
    topics: List[str] = []
    readiness_score: float = 0.0
    guidance_type: Optional[str] = None

class ConversationalResponse(BaseModel):
    """Response from conversational endpoint"""
    session_id: str
    phase: ConversationPhaseEnum
    response: str
    signals_collected: Dict[str, str]
    turn_count: int
    is_complete: bool
    citations: Optional[List[dict]] = None
    sources: Optional[List[SourceReference]] = None
    recommended_products: Optional[List[dict]] = None
    flow_metadata: Optional[FlowMetadata] = None

# AUTHENTICATION MODELS

class UserRegisterRequest(BaseModel):
    """Request body for user registration with extended profile"""
    name: str
    email: EmailStr
    password: str
    phone: str = ""
    gender: str = ""
    dob: str = ""
    profession: str = ""
    preferred_deity: str = ""
    location: str = ""
    spiritual_interests: List[str] = []
    rashi: str = ""
    gotra: str = ""
    nakshatra: str = ""
    favorite_temples: List[str] = []
    past_purchases: List[str] = []

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v

class UserLoginRequest(BaseModel):
    """Request body for user login"""
    email: str
    password: str

class UserResponse(BaseModel):
    """User info in responses"""
    id: str
    name: str
    email: str
    phone: str = ""
    gender: str = ""
    dob: str = ""
    age: int = 0
    age_group: str = ""
    profession: str = ""
    preferred_deity: str = ""
    location: str = ""
    spiritual_interests: List[str] = []
    rashi: str = ""
    gotra: str = ""
    nakshatra: str = ""
    temple_visits: List[str] = []
    purchase_history: List[str] = []
    created_at: str

class AuthResponse(BaseModel):
    """Response for login/register"""
    user: UserResponse
    token: str

class SaveConversationRequest(BaseModel):
    """Request to save a conversation"""
    conversation_id: str
    title: str
    messages: List[dict]

class FeedbackRequest(BaseModel):
    """Request to submit like/dislike feedback on a response"""
    session_id: str
    message_index: int
    response_text: str
    feedback: str  # "like" or "dislike"


# ---------------------------------------------------------------------------
# Dynamic memory API schemas (Apr 2026 — see docs/superpowers/specs/
# 2026-04-12-dynamic-memory-design.md §12). User-facing views of the
# RelationalProfile + user_memories collections — every response
# includes provenance so users can audit "when did I tell you this?".
# ---------------------------------------------------------------------------

class MemoryProvenance(BaseModel):
    """Where a memory came from — shown in GET responses for auditability."""
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_number: Optional[int] = None


class MemoryListItem(BaseModel):
    """One memory record in a user-facing list.

    ``source`` is one of: ``extracted`` | ``manual_user_add`` |
    ``reflection_insight`` | ``migration_backfill``. ``invalid_at`` is
    None for still-valid memories.
    """
    memory_id: str
    text: str
    importance: int = 5
    sensitivity: str = "personal"
    tone_marker: str = "neutral"
    valid_at: Optional[str] = None
    invalid_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
    access_count: int = 0
    source: str = "extracted"
    provenance: MemoryProvenance = Field(default_factory=MemoryProvenance)
    created_at: Optional[str] = None


class RelationalProfileResponse(BaseModel):
    """User-facing view of the RelationalProfile document.

    Crisis context is NOT exposed via this response — the backend
    strips ``prior_crisis_context`` before returning so the verbatim
    meta-fact line stays internal, but ``prior_crisis_flag`` and count
    are surfaced so the user can see that a flag exists and clear it
    via the reset endpoint if they wish.
    """
    user_id: str = ""
    relational_narrative: str = ""
    spiritual_themes: List[str] = Field(default_factory=list)
    ongoing_concerns: List[str] = Field(default_factory=list)
    tone_preferences: List[str] = Field(default_factory=list)
    people_mentioned: List[str] = Field(default_factory=list)
    prior_crisis_flag: bool = False
    prior_crisis_count: int = 0
    last_reflection_at: Optional[str] = None
    reflection_count: int = 0
    updated_at: Optional[str] = None


class MemoryListResponse(BaseModel):
    """GET /api/memory — the full user-facing memory panel."""
    memories: List[MemoryListItem] = Field(default_factory=list)
    total: int = 0
    profile: RelationalProfileResponse = Field(default_factory=RelationalProfileResponse)


class MemoryCreateRequest(BaseModel):
    """POST /api/memory body — user manually adds a memory.

    Skips Gemini extraction: goes straight to embedding + insert with
    ``source='manual_user_add'``. Importance and sensitivity default
    to conservative values if omitted.
    """
    text: str = Field(..., min_length=1, max_length=1000)
    importance: int = Field(default=5, ge=1, le=10)
    sensitivity: str = "personal"
    tone_marker: str = "neutral"

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, v):
        valid = {"trivial", "personal", "sensitive"}
        if v is None:
            return "personal"
        s = str(v).strip().lower()
        # Crisis tier is NEVER manually addable via the public API —
        # crisis meta-facts come only from the crisis hook.
        return s if s in valid else "personal"


class MemoryPatchRequest(BaseModel):
    """PATCH /api/memory/{id} body — edit an existing memory.

    Only ``text`` and ``sensitivity`` are patchable. Importance and
    tone_marker are LLM-assigned at write time and reflect the LLM's
    judgment, not the user's preference. If the user disagrees with
    those, they can delete and re-add.
    """
    text: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    sensitivity: Optional[str] = None

    @field_validator("sensitivity", mode="before")
    @classmethod
    def _coerce_sensitivity(cls, v):
        if v is None:
            return None
        valid = {"trivial", "personal", "sensitive"}
        s = str(v).strip().lower()
        return s if s in valid else None


class MemoryDeleteResponse(BaseModel):
    """DELETE /api/memory/{id} response."""
    deleted: bool
    memory_id: str
    hard: bool = False


class MemoryBatchDeleteResponse(BaseModel):
    """DELETE /api/memory?before=... response."""
    invalidated_count: int


class ProfileResetRequest(BaseModel):
    """POST /api/memory/profile/reset body — requires explicit confirmation."""
    confirm: bool = False


class ProfileResetResponse(BaseModel):
    reset: bool
