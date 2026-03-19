"""
Response Composer - Single authority for response generation
"""
from typing import List, Dict, Optional
import logging

from models.dharmic_query import DharmicQueryObject
from models.memory_context import ConversationMemory
from models.session import ConversationPhase
from config import settings
from services.profile_builder import build_user_profile

logger = logging.getLogger(__name__)


class ResponseComposer:

    def __init__(self):
        from llm.service import get_llm_service
        self.llm = get_llm_service()
        self.available = self.llm.available
        logger.info(f"ResponseComposer initialized (LLM available={self.available})")

    async def compose_with_memory(
        self,
        dharmic_query: DharmicQueryObject,
        memory: ConversationMemory,
        retrieved_verses: List[Dict],
        conversation_history: List[Dict],
        reduce_scripture: bool = False,
        phase: Optional[ConversationPhase] = None,
        original_query: Optional[str] = None,
        user_id: Optional[str] = None,
        past_memories: List[str] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
    ) -> str:
        """
        Compose a response using:
        - synthesized dharmic query (for RAG context)
        - rich conversation memory
        - verses retrieved via RAG
        - full conversation history (for context continuity)
        - current conversation phase
        - original user query (for natural response)
        """

        # Use original query for the LLM prompt if available,
        # otherwise fallback to build_search_query
        llm_query = original_query
        if not llm_query:
            llm_query = dharmic_query.build_search_query()

        if not llm_query:
            logger.error("No query text available for ResponseComposer")
            return self._compose_fallback(dharmic_query)

        # Optionally thin out the scripture context when a user is very
        # distressed – we still keep a couple of strong anchors.
        context_docs = retrieved_verses
        _distress_cap = max(1, settings.RERANK_TOP_K - 1)
        if reduce_scripture and len(retrieved_verses) > _distress_cap:
            context_docs = retrieved_verses[:_distress_cap]

        # Build user profile from memory
        user_profile = build_user_profile(memory)

        # Inject past memories into profile
        if past_memories:
            user_profile["past_memories"] = past_memories

        if self.llm.available:
            return await self.llm.generate_response(
                query=llm_query,
                context_docs=context_docs,
                conversation_history=conversation_history, # Use the explicit history passed from session
                user_profile=user_profile,
                phase=phase,
                memory_context=memory,
                model_override=model_override,
                config_override=config_override,
            )

        logger.info("LLM unavailable, using fallback")
        return self._compose_fallback(dharmic_query)

    async def compose_stream(
        self,
        dharmic_query: DharmicQueryObject,
        memory: ConversationMemory,
        retrieved_verses: List[Dict],
        conversation_history: List[Dict],
        reduce_scripture: bool = False,
        phase: Optional[ConversationPhase] = None,
        original_query: Optional[str] = None,
        user_id: Optional[str] = None,
        past_memories: List[str] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
    ):
        """
        Stream response synthesis using LLMService.generate_response_stream.
        """
        llm_query = original_query or dharmic_query.build_search_query()

        if not llm_query:
            yield self._compose_fallback(dharmic_query)
            return

        context_docs = retrieved_verses
        _distress_cap = max(1, settings.RERANK_TOP_K - 1)
        if reduce_scripture and len(retrieved_verses) > _distress_cap:
            context_docs = retrieved_verses[:_distress_cap]

        user_profile = build_user_profile(memory)
        if past_memories:
            user_profile["past_memories"] = past_memories

        if self.llm.available:
            async for chunk in self.llm.generate_response_stream(
                query=llm_query,
                context_docs=context_docs,
                conversation_history=conversation_history,
                user_profile=user_profile,
                phase=phase,
                memory_context=memory,
                model_override=model_override,
                config_override=config_override,
            ):
                yield chunk
        else:
            yield self._compose_fallback(dharmic_query)

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
