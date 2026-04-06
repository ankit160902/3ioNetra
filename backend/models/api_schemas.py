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
    conversation_id: Optional[str] = None
    title: str
    messages: List[dict]

class FeedbackRequest(BaseModel):
    """Request to submit like/dislike feedback on a response"""
    session_id: str
    message_index: int
    response_text: str
    feedback: str  # "like" or "dislike"
