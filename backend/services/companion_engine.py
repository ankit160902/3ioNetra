import logging
from typing import Tuple, Optional, TYPE_CHECKING

from models.session import SessionState, ConversationPhase
from models.memory_context import ConversationMemory
from llm.service import get_llm_service

if TYPE_CHECKING:
    from rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class CompanionEngine:
    """
    Empathetic front‑line companion.

    Responsibilities:
    - Listen and update `ConversationMemory`
    - Decide when we're ready for dharmic wisdom (ANSWERING phase)
    - Generate gentle, RAG-informed responses during clarification
    """

    def __init__(self, rag_pipeline: Optional['RAGPipeline'] = None) -> None:
        self.llm = get_llm_service()
        self.rag_pipeline = rag_pipeline
        self.available = self.llm.available
        logger.info(f"CompanionEngine initialized (LLM available={self.available})")

    def set_rag_pipeline(self, rag_pipeline: 'RAGPipeline') -> None:
        """Set the RAG pipeline for context retrieval"""
        self.rag_pipeline = rag_pipeline
        logger.info("RAG pipeline connected to CompanionEngine")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_message(
        self,
        session: SessionState,
        message: str,
    ) -> Tuple[str, bool]:
        """
        Process a user message, update memory, and decide if we're
        ready to transition into the wisdom / answering phase.

        Returns:
            (assistant_text, is_ready_for_wisdom)
        """
        self._update_memory(session.memory, session, message)

        # Decide if enough context has been gathered
        is_ready = self._assess_readiness(session)

        # During wisdom phase, we don't actually produce the final
        # answer here – the main flow will call RAG + ResponseComposer.
        # We still return a short acknowledgment so the UI always has
        # something sane to show if needed.
        if is_ready:
            ack = (
                "Thank you for sharing this so openly. "
                "Let me gather some wisdom from the scriptures that fits your situation."
            )
            return ack, True

        # Clarification / listening phase – use LLM with RAG context if available
        if self.llm.available:
            # Retrieve relevant spiritual context even during listening phase
            # This helps the companion provide spiritually grounded empathetic responses
            context_docs = []
            if self.rag_pipeline and self.rag_pipeline.available:
                try:
                    # Build a query from the user's message and emotional state
                    search_query = self._build_listening_query(message, session.memory)
                    
                    # Retrieve relevant verses (fewer than in answering phase)
                    context_docs = await self.rag_pipeline.search(
                        query=search_query,
                        scripture_filter=None,
                        language="en",
                        top_k=2  # Just 1-2 verses for subtle guidance during listening
                    )
                    logger.info(f"Retrieved {len(context_docs)} RAG docs for listening phase")
                except Exception as e:
                    logger.warning(f"Could not retrieve RAG context during listening: {e}")
            
            reply = await self.llm.generate_response(
                query=message,
                context_docs=context_docs,  # Now passing RAG context!
                conversation_history=session.conversation_history,
                user_id=session.memory.user_id or "anonymous",
            )
            logger.info(f"CompanionEngine received LLM reply (len={len(reply)}): '{reply}'")
            return reply, False

        # Very simple template fallback
        fallback = (
            "I hear how much this is affecting you. "
            "Tell me a little more about what feels hardest right now."
        )
        return fallback, False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_listening_query(self, message: str, memory: ConversationMemory) -> str:
        """
        Build a search query for RAG retrieval during listening phase.
        This query focuses on the user's emotional state and life area
        to find relevant gentle wisdom.
        """
        query_parts = []
        
        # Add the user's current concern
        if memory.story.primary_concern:
            query_parts.append(memory.story.primary_concern[:100])
        
        # Add emotional context
        if memory.story.emotional_state:
            emotions_map = {
                "anxiety": "peace of mind, overcoming worry, finding calm",
                "sadness": "dealing with grief, finding strength, inner peace",
                "anger": "managing anger, patience, self-control"
            }
            query_parts.append(emotions_map.get(memory.story.emotional_state, "inner peace"))
        
        # Add life area context
        if memory.story.life_area:
            life_areas_map = {
                "work": "dharmic approach to work, duty, balance",
                "family": "family relationships, dharma towards family",
                "relationships": "relationships, love, understanding"
            }
            query_parts.append(life_areas_map.get(memory.story.life_area, ""))
        
        # Fallback to current message
        if not query_parts:
            query_parts.append(message[:100])
        
        query = " ".join(query_parts)
        logger.debug(f"Listening phase RAG query: {query[:100]}...")
        return query


    def _update_memory(
        self,
        memory: ConversationMemory,
        session: SessionState,
        message: str,
    ) -> None:
        """
        Lightweight heuristics to keep `ConversationMemory` in sync.
        This doesn't need to be perfect – it just needs to give the
        LLM + RAG a good narrative summary.
        """
        text_lower = message.lower().strip()

        # Seed primary concern on first few turns
        if not memory.story.primary_concern:
            memory.story.primary_concern = message[:200]

        # Very rough emotion tagging
        if any(w in text_lower for w in ["anxious", "worried", "nervous", "panic"]):
            memory.story.emotional_state = "anxiety"
        elif any(w in text_lower for w in ["sad", "cry", "depressed", "lonely"]):
            memory.story.emotional_state = "sadness"
        elif any(w in text_lower for w in ["angry", "frustrated", "irritated"]):
            memory.story.emotional_state = "anger"

        # Track life area
        if any(w in text_lower for w in ["job", "office", "work", "career"]):
            memory.story.life_area = memory.story.life_area or "work"
        elif any(w in text_lower for w in ["marriage", "partner", "husband", "wife", "relationship"]):
            memory.story.life_area = memory.story.life_area or "relationships"
        elif any(w in text_lower for w in ["family", "parents", "children", "son", "daughter"]):
            memory.story.life_area = memory.story.life_area or "family"

        # Record a quote + emotional arc point
        memory.add_user_quote(turn=session.turn_count, quote=message[:200])
        if memory.story.emotional_state:
            memory.record_emotion(
                turn=session.turn_count,
                emotion=memory.story.emotional_state,
                intensity="moderate",
            )

        # Increase readiness slowly each turn
        memory.readiness_for_wisdom = min(
            1.0,
            memory.readiness_for_wisdom + 0.2,
        )

    def _assess_readiness(self, session: SessionState) -> bool:
        """
        Decide if we're ready to move into ANSWERING phase.

        Strategy:
        - Prefer structured readiness from SessionState + memory
        - Hard cap on clarification turns as a safety net
        """
        # Honour global clarification flow thresholds
        if session.should_force_transition():
            logger.info(
                f"Session {session.session_id}: forcing ANSWERING phase "
                f"after {session.turn_count} turns"
            )
            return True

        # Soft readiness based on memory score
        readiness = session.memory_readiness
        logger.info(
            f"Session {session.session_id}: readiness_for_wisdom={readiness:.2f}, "
            f"turns={session.turn_count}"
        )

        return readiness >= 0.8


_companion_engine: CompanionEngine | None = None


def get_companion_engine() -> CompanionEngine:
    global _companion_engine
    if _companion_engine is None:
        _companion_engine = CompanionEngine()
    return _companion_engine
