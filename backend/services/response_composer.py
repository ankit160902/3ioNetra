"""
Response Composer - Single authority for response generation
"""
from typing import List, Dict, Optional
import logging

from models.dharmic_query import DharmicQueryObject
from models.memory_context import ConversationMemory
from models.session import SessionState, ConversationPhase
from llm.service import get_llm_service

logger = logging.getLogger(__name__)


class ResponseComposer:

    def __init__(self):
        self.llm = get_llm_service()
        self.available = self.llm.available
        logger.info(f"ResponseComposer initialized (LLM available={self.available})")

    async def compose_with_memory(
        self,
        dharmic_query: DharmicQueryObject,
        memory: ConversationMemory,
        retrieved_verses: List[Dict],
        reduce_scripture: bool = False,
        phase: Optional[ConversationPhase] = None,
        original_query: Optional[str] = None
    ) -> str:
        """
        Compose a response using:
        - synthesized dharmic query (for RAG context)
        - rich conversation memory
        - verses retrieved via RAG
        - current conversation phase
        - original user query (for natural response)
        """

        # Use original query for the LLM prompt if available, 
        # otherwise fallback to build_search_query
        llm_query = original_query
        if not llm_query:
            llm_query = (
                dharmic_query.build_search_query()
                if hasattr(dharmic_query, "build_search_query")
                else dharmic_query.get_search_query()
            )

        if not llm_query:
            logger.error("No query text available for ResponseComposer")
            return self._compose_fallback(dharmic_query)

        # Optionally thin out the scripture context when a user is very
        # distressed – we still keep a couple of strong anchors.
        context_docs = retrieved_verses
        if reduce_scripture and len(retrieved_verses) > 2:
            context_docs = retrieved_verses[:2]

        # Build user profile from memory
        user_profile = self._build_user_profile(memory)

        if self.llm.available:
            return await self.llm.generate_response(
                query=llm_query,
                context_docs=context_docs,
                conversation_history=memory.conversation_history,
                user_profile=user_profile,
                phase=phase,
                memory_context=memory
            )

        logger.info("LLM unavailable, using fallback")
        return self._compose_fallback(dharmic_query)

    def _build_user_profile(self, memory: ConversationMemory) -> Dict:
        """
        Build a user profile dictionary from conversation memory.
        This includes all personalization data for the LLM.
        """
        profile = {}
        
        # User identity and contact info (from authentication)
        if memory.user_name:
            profile['name'] = memory.user_name
        if memory.user_email:
            profile['email'] = memory.user_email
        if memory.user_phone:
            profile['phone'] = memory.user_phone
        if memory.user_dob:
            profile['dob'] = memory.user_dob
        if memory.user_id:
            profile['user_id'] = memory.user_id
        if memory.user_created_at:
            profile['created_at'] = memory.user_created_at
        
        # Demographics and current state from story
        story = memory.story
        if story.age_group:
            profile['age_group'] = story.age_group
        if story.gender:
            profile['gender'] = story.gender
        if story.profession:
            profile['profession'] = story.profession
        
        # Add situational context for the "Problem" and "Action" pillars
        if story.primary_concern:
            profile['primary_concern'] = story.primary_concern
        if story.emotional_state:
            profile['emotional_state'] = story.emotional_state
        if story.life_area:
            profile['life_area'] = story.life_area
            
        # Add spiritual/astrological context
        if story.rashi:
            profile['rashi'] = story.rashi
        if story.gotra:
            profile['gotra'] = story.gotra
        if story.nakshatra:
            profile['nakshatra'] = story.nakshatra
            
        return profile

    def _compose_fallback(self, dq: DharmicQueryObject) -> str:
        response = (
            f"I understand what you're going through.\n\n"
            f"From a dharmic perspective, concepts like "
            f"{', '.join(dq.dharmic_concepts[:2])} remind us to move step by step.\n\n"
            "Take a slow breath. You do not need to solve everything at once."
        )
        logger.info(f"Composed fallback response ({len(response)} chars)")
        return response


_response_composer: Optional[ResponseComposer] = None


def get_response_composer() -> ResponseComposer:
    global _response_composer
    if _response_composer is None:
        _response_composer = ResponseComposer()
    return _response_composer
