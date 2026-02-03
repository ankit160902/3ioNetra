"""
Conversation Memory - Rich context for understanding user's story
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


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
            "spiritual_interests": self.spiritual_interests
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
            spiritual_interests=data.get("spiritual_interests", [])
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
            "user_created_at": self.user_created_at
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
            user_created_at=data.get("user_created_at", "")
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
        """Get a textual summary of the conversation memory in natural language"""
        parts = []

        # Build a narrative sentence
        if self.story.primary_concern:
            parts.append(f"The user is dealing with {self.story.primary_concern}")

        if self.story.emotional_state:
            parts.append(f"They are currently feeling {self.story.emotional_state}")

        if self.story.life_area:
            parts.append(f"This situation relates to their {self.story.life_area}")

        if self.story.trigger_event:
            parts.append(f"It was triggered by {self.story.trigger_event}")

        if self.story.temple_interest:
            parts.append(f"They have shown interest in {self.story.temple_interest}")

        if self.story.preferred_deity:
            parts.append(f"Their preferred deity is {self.story.preferred_deity}")

        if self.story.location:
            parts.append(f"They are located in {self.story.location}")
            
        if self.story.spiritual_interests:
            parts.append(f"They are interested in {', '.join(self.story.spiritual_interests)}")

        if self.story.unmet_needs:
            parts.append(f"They are seeking {', '.join(self.story.unmet_needs)}")

        if self.user_quotes:
            recent_quote = self.user_quotes[-1]["quote"]
            # Only add if significant
            if len(recent_quote) > 20:
                parts.append(f"They recently mentioned: \"{recent_quote}\"")

        return ". ".join(parts) if parts else ""

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
