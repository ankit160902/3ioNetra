"""
Dharmic Query Object - Structured representation of user's spiritual query
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class QueryType(str, Enum):
    """Type of spiritual query"""
    PHILOSOPHICAL = "philosophical"
    PRACTICAL_ADVICE = "practical_advice"
    EMOTIONAL_HEALING = "emotional_healing"
    LIFE_GUIDANCE = "life_guidance"
    CRISIS_SUPPORT = "crisis_support"
    TEMPLE_GUIDANCE = "temple_guidance"


class UserStage(str, Enum):
    """User's familiarity with spiritual concepts"""
    BEGINNER = "beginner"
    SEEKER = "seeker"
    PRACTITIONER = "practitioner"


class ResponseStyle(str, Enum):
    """Style of response delivery"""
    GENTLE_NURTURING = "gentle_nurturing"
    DIRECT_PRACTICAL = "direct_practical"
    PHILOSOPHICAL = "philosophical"
    STORY_BASED = "story_based"


@dataclass
class DharmicQueryObject:
    """
    Structured representation of a user's query for RAG retrieval and response generation.
    Captures the essence of what the user is seeking from a dharmic perspective.
    """
    # Core query
    query: str
    query_type: QueryType = QueryType.LIFE_GUIDANCE

    # Dharmic concepts to focus on
    dharmic_concepts: List[str] = field(default_factory=lambda: ["dharma", "karma", "peace"])

    # User context
    user_stage: UserStage = UserStage.BEGINNER
    response_style: ResponseStyle = ResponseStyle.GENTLE_NURTURING

    # Emotional/situational context
    emotion: str = "unknown"
    trigger: Optional[str] = None
    life_domain: Optional[str] = None
    mental_state: Optional[str] = None
    user_goal: Optional[str] = None

    # Content filtering
    allowed_scriptures: List[str] = field(default_factory=lambda: [
        "Bhagavad Gita", "Ramayana", "Mahabharata", "Sanatan Scriptures"
    ])

    # Response guidance
    guidance_type: str = "guidance"
    conversation_summary: str = ""

    def build_search_query(self) -> str:
        """Build a search query for RAG retrieval"""
        query_parts = []

        # Start with the core user query/intent
        if self.query:
            query_parts.append(self.query)

        # Add the conversation summary to provide more semantic context for RAG
        if self.conversation_summary and len(self.conversation_summary) > 20:
            # We add this to help the embedding model pick up on the broader story
            query_parts.append(self.conversation_summary)

        # Add emotional context
        if self.emotion and self.emotion != "unknown":
            query_parts.append(f"dealing with {self.emotion}")

        # Add life domain context
        if self.life_domain:
            query_parts.append(f"regarding {self.life_domain}")

        # Add dharmic concepts
        if self.dharmic_concepts:
            concepts = " ".join(self.dharmic_concepts[:3])
            query_parts.append(concepts)

        # Return a semantic blob for the embedding model
        return ". ".join(query_parts)

    def get_search_query(self) -> str:
        """Alias for build_search_query for backwards compatibility"""
        return self.build_search_query()

    def get_scripture_filter(self) -> Optional[str]:
        """Get scripture filter for RAG if only one scripture is allowed"""
        if len(self.allowed_scriptures) == 1:
            return self.allowed_scriptures[0]
        return None
