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
    PANCHANG = "panchang"


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

        # 1. Boost Life Domain (Personalization)
        # We front-load this to heavily weigh the context
        if self.life_domain:
            domain_map = {
                "work": "career job workplace profession duty employment",
                "family": "parents children siblings house relations domestic",
                "relationships": "marriage partner love conflict divorce connection",
                "financial": "money wealth debt economic poverty prosperity",
                "health": "illness sickness body pain healing physical well-being",
                "spiritual": "practice meditation sadhana devotion god faith",
                "career": "job business success failure profession ambition",
                "education": "studies exams learning student knowledge",
            }
            # Expand with synonyms for better RAG matching
            keywords = domain_map.get(self.life_domain.lower(), self.life_domain)
            query_parts.append(f"Context: {self.life_domain} ({keywords})")

        # 2. Core user query
        if self.query:
            query_parts.append(self.query)

        # 3. Add conversation summary for context
        if self.conversation_summary and len(self.conversation_summary) > 20:
            query_parts.append(self.conversation_summary)

        # 4. Add emotional context
        if self.emotion and self.emotion != "unknown":
            query_parts.append(f"dealing with {self.emotion}")

        # 5. Add dharmic concepts
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
