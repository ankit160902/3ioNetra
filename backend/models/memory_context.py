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
    user_created_at: str = ""

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
