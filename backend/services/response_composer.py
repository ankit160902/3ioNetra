"""
Response Composer - Single authority for response generation
"""
import hashlib
import re
from typing import List, Dict, Optional
import logging
import numpy as np

from models.dharmic_query import DharmicQueryObject
from models.memory_context import ConversationMemory
from models.session import ConversationPhase
from config import settings
from services.profile_builder import build_user_profile
from services.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class ResponseComposer:

    def __init__(self):
        from llm.service import get_llm_service
        self.llm = get_llm_service()
        self.available = self.llm.available
        self._embedding_model = None
        logger.info(f"ResponseComposer initialized (LLM available={self.available})")

    def _get_embedding_model(self):
        """Lazy-load embedding model from RAG pipeline (shared singleton)."""
        if self._embedding_model is None:
            try:
                from rag.pipeline import get_rag_pipeline
                pipeline = get_rag_pipeline()
                if pipeline and pipeline._embedding_model is not None:
                    self._embedding_model = pipeline._embedding_model
            except Exception:
                pass
        return self._embedding_model

    def _build_cache_key(self, query: str, phase: Optional[ConversationPhase], emotion: str, life_domain: str) -> str:
        """Build a deterministic cache key from query semantics + context."""
        phase_val = phase.value if phase else "unknown"
        key_str = f"{query.strip().lower()}|{phase_val}|{emotion}|{life_domain}"
        return hashlib.md5(key_str.encode()).hexdigest()

    async def _check_response_cache(self, query: str, phase: Optional[ConversationPhase], memory: ConversationMemory) -> Optional[str]:
        """Check if a semantically similar query has a cached response."""
        if not settings.RESPONSE_CACHE_ENABLED:
            return None

        emotion = (memory.story.emotional_state or "").lower()
        life_domain = (memory.story.life_area or "").lower()

        cache = get_cache_service()
        cache_key = self._build_cache_key(query, phase, emotion, life_domain)
        cached = await cache.get("response_semantic", key=cache_key)
        if cached and isinstance(cached, dict):
            logger.info(f"Response cache HIT for query='{query[:40]}' (exact key match)")
            return cached.get("response")
        return None

    async def _store_response_cache(self, query: str, phase: Optional[ConversationPhase], memory: ConversationMemory, response: str) -> None:
        """Cache a generated response for future semantic matches."""
        if not settings.RESPONSE_CACHE_ENABLED:
            return
        # Don't cache very short or fallback responses
        if len(response) < 30:
            return

        emotion = (memory.story.emotional_state or "").lower()
        life_domain = (memory.story.life_area or "").lower()

        cache = get_cache_service()
        cache_key = self._build_cache_key(query, phase, emotion, life_domain)
        await cache.set(
            "response_semantic",
            {"response": response, "query": query},
            ttl=settings.RESPONSE_CACHE_TTL,
            key=cache_key,
        )
        logger.debug(f"Response cache SET for query='{query[:40]}'")

    def _personalize_cached_response(self, response: str, memory: ConversationMemory) -> str:
        """Light personalization of a cached response (swap user name if present)."""
        name = memory.user_name
        if not name:
            return response
        # If the cached response has a generic "friend" reference, replace with name
        response = re.sub(r'\bfriend\b', name, response, count=1, flags=re.IGNORECASE)
        return response

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

        # Check response cache before expensive LLM call
        cached_response = await self._check_response_cache(llm_query, phase, memory)
        if cached_response:
            return self._personalize_cached_response(cached_response, memory)

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
            response = await self.llm.generate_response(
                query=llm_query,
                context_docs=context_docs,
                conversation_history=conversation_history, # Use the explicit history passed from session
                user_profile=user_profile,
                phase=phase,
                memory_context=memory,
                model_override=model_override,
                config_override=config_override,
            )
            # Cache the response for future similar queries
            await self._store_response_cache(llm_query, phase, memory, response)
            return response

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

        # Check response cache — if hit, yield in word-sized chunks to preserve streaming UX
        cached_response = await self._check_response_cache(llm_query, phase, memory)
        if cached_response:
            text = self._personalize_cached_response(cached_response, memory)
            for word in text.split(' '):
                yield word + ' '
            return

        context_docs = retrieved_verses
        _distress_cap = max(1, settings.RERANK_TOP_K - 1)
        if reduce_scripture and len(retrieved_verses) > _distress_cap:
            context_docs = retrieved_verses[:_distress_cap]

        user_profile = build_user_profile(memory)
        if past_memories:
            user_profile["past_memories"] = past_memories

        if self.llm.available:
            full_response_parts = []
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
                full_response_parts.append(chunk)
                yield chunk
            # Cache the full response after streaming completes
            full_response = "".join(full_response_parts)
            await self._store_response_cache(llm_query, phase, memory, full_response)
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
