"""
Conversation Memory - Rich context for understanding user's story
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.llm_schemas import ReflectionProfilePatch


@dataclass
class UserStory:
    """
    Represents the user's story as understood through conversation.
    Built up progressively as the companion listens.
    """
    # Core concern
    primary_concern: str = ""

    # Emotional state
    emotional_state: Optional[str] = None

    # Life area (work, family, relationships, etc.)
    life_area: Optional[str] = None

    # What triggered the current distress
    trigger_event: Optional[str] = None

    # What the user needs but isn't getting
    unmet_needs: List[str] = field(default_factory=list)

    # Demographics (can be pre-populated from user profile)
    age_group: str = ""
    gender: str = ""
    profession: str = ""

    # Temple related interest
    temple_interest: Optional[str] = None

    # Extended profiling
    preferred_deity: str = ""
    location: str = ""
    spiritual_interests: List[str] = field(default_factory=list)
    
    # 🔥 NEW Spiritual Profile
    rashi: str = ""
    gotra: str = ""
    nakshatra: str = ""
    
    # 🔥 NEW History
    temple_visits: List[str] = field(default_factory=list)
    purchase_history: List[str] = field(default_factory=list)
    
    # Topics detected over time
    detected_topics: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "primary_concern": self.primary_concern,
            "emotional_state": self.emotional_state,
            "life_area": self.life_area,
            "trigger_event": self.trigger_event,
            "unmet_needs": self.unmet_needs,
            "age_group": self.age_group,
            "gender": self.gender,
            "profession": self.profession,
            "temple_interest": self.temple_interest,
            "preferred_deity": self.preferred_deity,
            "location": self.location,
            "spiritual_interests": self.spiritual_interests,
            "rashi": self.rashi,
            "gotra": self.gotra,
            "nakshatra": self.nakshatra,
            "temple_visits": self.temple_visits,
            "purchase_history": self.purchase_history,
            "detected_topics": self.detected_topics
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserStory':
        if not data:
            return cls()
        return cls(
            primary_concern=data.get("primary_concern", ""),
            emotional_state=data.get("emotional_state"),
            life_area=data.get("life_area"),
            trigger_event=data.get("trigger_event"),
            unmet_needs=data.get("unmet_needs", []),
            age_group=data.get("age_group", ""),
            gender=data.get("gender", ""),
            profession=data.get("profession", ""),
            temple_interest=data.get("temple_interest"),
            preferred_deity=data.get("preferred_deity", ""),
            location=data.get("location", ""),
            spiritual_interests=data.get("spiritual_interests", []),
            rashi=data.get("rashi", ""),
            gotra=data.get("gotra", ""),
            nakshatra=data.get("nakshatra", ""),
            temple_visits=data.get("temple_visits", []),
            purchase_history=data.get("purchase_history", []),
            detected_topics=data.get("detected_topics", [])
        )


@dataclass
class ConversationMemory:
    """
    Rich memory context that captures the full understanding of a conversation.
    Used by the CompanionEngine to build empathetic, personalized responses.
    """
    # User's story (built progressively)
    story: UserStory = field(default_factory=UserStory)

    # Readiness score (0.0 to 1.0) - when high enough, transition to wisdom
    readiness_for_wisdom: float = 0.0

    # Key quotes from the user (for personalization)
    user_quotes: List[Dict] = field(default_factory=list)

    # Emotional arc through the conversation
    emotional_arc: List[Dict] = field(default_factory=list)

    # Dharmic concepts that seem relevant
    relevant_concepts: List[str] = field(default_factory=list)

    # Conversation history reference
    conversation_history: List[Dict] = field(default_factory=list)

    # User identification (from auth)
    user_id: str = ""
    user_name: str = ""
    user_email: str = ""
    user_phone: str = ""
    user_dob: str = ""
    user_created_at: str = ""
    
    # Returning user flag
    is_returning_user: bool = False

    # Summary of previous sessions for returning users
    previous_session_summary: str = ""

    def to_dict(self) -> Dict:
        return {
            "story": self.story.to_dict(),
            "readiness_for_wisdom": self.readiness_for_wisdom,
            "user_quotes": self.user_quotes,
            "emotional_arc": self.emotional_arc,
            "relevant_concepts": self.relevant_concepts,
            "conversation_history": self.conversation_history,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "user_email": self.user_email,
            "user_phone": self.user_phone,
            "user_dob": self.user_dob,
            "user_created_at": self.user_created_at,
            "is_returning_user": self.is_returning_user,
            "previous_session_summary": self.previous_session_summary
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationMemory':
        if not data:
            return cls()
        memory = cls(
            story=UserStory.from_dict(data.get("story", {})),
            readiness_for_wisdom=data.get("readiness_for_wisdom", 0.0),
            user_quotes=data.get("user_quotes", []),
            emotional_arc=data.get("emotional_arc", []),
            relevant_concepts=data.get("relevant_concepts", []),
            conversation_history=data.get("conversation_history", []),
            user_id=data.get("user_id", ""),
            user_name=data.get("user_name", ""),
            user_email=data.get("user_email", ""),
            user_phone=data.get("user_phone", ""),
            user_dob=data.get("user_dob", ""),
            user_created_at=data.get("user_created_at", ""),
            is_returning_user=data.get("is_returning_user", False),
            previous_session_summary=data.get("previous_session_summary", "")
        )
        return memory

    def add_user_quote(self, turn: int, quote: str) -> None:
        """Record a significant user quote"""
        self.user_quotes.append({
            "turn": turn,
            "quote": quote
        })

    def record_emotion(self, turn: int, emotion: str, intensity: str = "moderate") -> None:
        """Record a point in the emotional arc"""
        self.emotional_arc.append({
            "turn": turn,
            "emotion": emotion,
            "intensity": intensity
        })

    def add_concept(self, concept: str) -> None:
        """Add a relevant dharmic concept"""
        if concept not in self.relevant_concepts:
            self.relevant_concepts.append(concept)

    def get_memory_summary(self) -> str:
        """Get a lightweight summary focused on current conversational context.

        Profile fields (preferred_deity, rashi, gotra, temple_visits, purchase_history,
        location, spiritual_interests) are intentionally excluded here — they are already
        injected via the user profile section of the prompt. Repeating them here amplifies
        bias and causes the LLM to loop on the same deity/temple/topic.
        """
        parts = []

        if self.story.primary_concern:
            parts.append(f"The user is currently dealing with {self.story.primary_concern}")

        if self.story.emotional_state:
            parts.append(f"They are feeling {self.story.emotional_state}")

        if self.story.life_area:
            parts.append(f"This relates to their {self.story.life_area}")

        if self.story.trigger_event:
            parts.append(f"Triggered by {self.story.trigger_event}")

        if self.story.unmet_needs:
            parts.append(f"They are seeking {', '.join(self.story.unmet_needs)}")

        return ". ".join(parts) if parts else "This is the start of the conversation."

    def get_user_context_string(self) -> str:
        """Get a string describing the user for personalization"""
        parts = []

        if self.user_name:
            parts.append(self.user_name)

        if self.story.age_group:
            parts.append(self.story.age_group)

        if self.story.gender:
            parts.append(self.story.gender)

        if self.story.profession:
            parts.append(f"working as {self.story.profession}")

        return ", ".join(parts) if parts else "anonymous seeker"


# ---------------------------------------------------------------------------
# Dynamic memory system (Apr 2026) — see docs/superpowers/specs/2026-04-12-
# dynamic-memory-design.md for the design that motivates this class.
# ---------------------------------------------------------------------------

# Maximum items per list field in the RelationalProfile — enforced at
# apply_reflection time so a runaway LLM output can't balloon the profile
# past its prompt-injection budget.
_PROFILE_LIST_FIELD_CAP = 10


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Tolerant datetime parser for from_dict — accepts datetime, ISO string, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _iso_or_none(dt: Optional[datetime]) -> Optional[str]:
    """Serialize datetime for to_dict — ISO format or None."""
    if dt is None:
        return None
    return dt.isoformat()


@dataclass
class RelationalProfile:
    """The always-in-context relational layer for Mitra's dynamic memory.

    One document per user. Loaded on every turn (Redis-cached). Holds the
    slowly-evolving narrative that describes who this user is to Mitra,
    plus structured chip-style fields for queryable facts. Written only
    by ReflectionService (periodic) and the crisis meta-fact hook in
    CompanionEngine — never by per-turn extraction.

    Crisis handling: `prior_crisis_flag` + `prior_crisis_context` are the
    ONLY memory-layer trace of crisis moments. The specific user words
    are never stored — `prior_crisis_context` holds a single-line
    meta-fact like "On 2026-04-10 user had a crisis moment; helplines
    provided; user continued engaging". The profile's to_prompt_text()
    renders a generic safety note, never the raw context.
    """

    user_id: str = ""
    relational_narrative: str = ""
    spiritual_themes: List[str] = field(default_factory=list)
    ongoing_concerns: List[str] = field(default_factory=list)
    tone_preferences: List[str] = field(default_factory=list)
    people_mentioned: List[str] = field(default_factory=list)

    # Crisis awareness (populated by companion_engine crisis hook only)
    prior_crisis_flag: bool = False
    prior_crisis_context: Optional[str] = None
    prior_crisis_count: int = 0

    # Reflection state
    last_reflection_at: Optional[datetime] = None
    importance_since_reflection: int = 0
    reflection_count: int = 0

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_prompt_text(self) -> str:
        """Render this profile as the text block injected into the LLM prompt.

        Layout:
            1. (optional) safety note — only if prior_crisis_flag is set.
               Never contains verbatim crisis content, only a generic
               tone-bias instruction.
            2. (optional) relational narrative — the big paragraph.
            3. (optional) structured chip lines — spiritual themes,
               ongoing concerns, people mentioned.

        Empty profile returns an empty string so the prompt builder can
        cleanly skip the section.
        """
        parts: List[str] = []

        if self.prior_crisis_flag:
            parts.append(
                "[NOTE: This user has previously shared a crisis moment. "
                "Bias tone softer. Do not reference the specific content.]"
            )

        if self.relational_narrative:
            parts.append(self.relational_narrative)

        if self.spiritual_themes:
            parts.append("Spiritual themes: " + ", ".join(self.spiritual_themes[:5]))

        if self.ongoing_concerns:
            parts.append("Ongoing concerns: " + ", ".join(self.ongoing_concerns[:5]))

        if self.people_mentioned:
            parts.append("People in their life: " + ", ".join(self.people_mentioned[:5]))

        return "\n\n".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "relational_narrative": self.relational_narrative,
            "spiritual_themes": list(self.spiritual_themes),
            "ongoing_concerns": list(self.ongoing_concerns),
            "tone_preferences": list(self.tone_preferences),
            "people_mentioned": list(self.people_mentioned),
            "prior_crisis_flag": self.prior_crisis_flag,
            "prior_crisis_context": self.prior_crisis_context,
            "prior_crisis_count": self.prior_crisis_count,
            "last_reflection_at": _iso_or_none(self.last_reflection_at),
            "importance_since_reflection": self.importance_since_reflection,
            "reflection_count": self.reflection_count,
            "created_at": _iso_or_none(self.created_at),
            "updated_at": _iso_or_none(self.updated_at),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> "RelationalProfile":
        if not data:
            return cls()
        return cls(
            user_id=data.get("user_id", ""),
            relational_narrative=data.get("relational_narrative", "") or "",
            spiritual_themes=list(data.get("spiritual_themes") or []),
            ongoing_concerns=list(data.get("ongoing_concerns") or []),
            tone_preferences=list(data.get("tone_preferences") or []),
            people_mentioned=list(data.get("people_mentioned") or []),
            prior_crisis_flag=bool(data.get("prior_crisis_flag", False)),
            prior_crisis_context=data.get("prior_crisis_context"),
            prior_crisis_count=int(data.get("prior_crisis_count", 0) or 0),
            last_reflection_at=_parse_iso_datetime(data.get("last_reflection_at")),
            importance_since_reflection=int(data.get("importance_since_reflection", 0) or 0),
            reflection_count=int(data.get("reflection_count", 0) or 0),
            created_at=_parse_iso_datetime(data.get("created_at")),
            updated_at=_parse_iso_datetime(data.get("updated_at")),
        )

    def apply_reflection(self, patch: "ReflectionProfilePatch") -> "RelationalProfile":
        """Merge a ReflectionProfilePatch into a NEW RelationalProfile instance.

        Does not mutate self. Preserves user_id, crisis state, and reflection
        counters (those are managed by ReflectionService separately). Caps
        each list field at `_PROFILE_LIST_FIELD_CAP` items so a runaway LLM
        output can't balloon the profile past its prompt-injection budget.

        Sets updated_at = datetime.utcnow() on the new instance.
        """
        return RelationalProfile(
            user_id=self.user_id,  # preserved
            relational_narrative=patch.relational_narrative or "",
            spiritual_themes=list(patch.spiritual_themes)[:_PROFILE_LIST_FIELD_CAP],
            ongoing_concerns=list(patch.ongoing_concerns)[:_PROFILE_LIST_FIELD_CAP],
            tone_preferences=list(patch.tone_preferences)[:_PROFILE_LIST_FIELD_CAP],
            people_mentioned=list(patch.people_mentioned)[:_PROFILE_LIST_FIELD_CAP],
            # Crisis state preserved — only the crisis hook writes these,
            # never reflection.
            prior_crisis_flag=self.prior_crisis_flag,
            prior_crisis_context=self.prior_crisis_context,
            prior_crisis_count=self.prior_crisis_count,
            # Reflection counters are managed by ReflectionService.run_reflection
            # after this returns — leave them alone here.
            last_reflection_at=self.last_reflection_at,
            importance_since_reflection=self.importance_since_reflection,
            reflection_count=self.reflection_count,
            created_at=self.created_at,
            updated_at=datetime.utcnow(),
        )
