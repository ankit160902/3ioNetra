"""
Response Composer - Single authority for response generation
"""
from typing import List, Dict, Optional
import logging

from models.dharmic_query import DharmicQueryObject
from models.memory_context import ConversationMemory
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
    ) -> str:
        """
        Compose a response using:
        - synthesized dharmic query
        - rich conversation memory
        - verses retrieved via RAG

        `reduce_scripture` lets the SafetyValidator ask us to lean
        more on plain‑language comfort vs dense citation lists.
        """

        # Build search/query text in a way that's compatible with both
        # old and new DharmicQueryObject implementations.
        query_text = (
            dharmic_query.build_search_query()
            if hasattr(dharmic_query, "build_search_query")
            else dharmic_query.get_search_query()
        )

        if not query_text:
            logger.error("DharmicQueryObject has no extractable query text")
            return self._compose_fallback(dharmic_query)

        # Optionally thin out the scripture context when a user is very
        # distressed – we still keep a couple of strong anchors.
        context_docs = retrieved_verses
        if reduce_scripture and len(retrieved_verses) > 2:
            context_docs = retrieved_verses[:2]

        if self.llm.available:
            return await self.llm.generate_response(
                query=query_text,
                context_docs=context_docs,
                conversation_history=memory.conversation_history,
                user_id=memory.user_id,
            )

        logger.info("LLM unavailable, using fallback")
        return self._compose_fallback(dharmic_query)

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
