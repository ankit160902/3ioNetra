import logging
import random
from typing import Tuple, Optional, TYPE_CHECKING, Dict

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
            acks = [
                "Thank you for sharing this so openly. Let me see how the ancient wisdom of the scriptures can light your path.",
                "I truly appreciate your trust in sharing this. I am looking into the sacred texts now to find the guidance that speaks to your situation.",
                "Your openness helps me understand deeply. Let me reach into the timeless wisdom of Dharma to find a perspective that might help you find peace.",
                "I feel your situation deeply. I'm gathering some specific verses right now that offer a mirror to what you're experiencing."
            ]
            ack = random.choice(acks)
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
            
            # Build user profile from session memory
            user_profile = self._build_user_profile(session.memory)
            
            # Log profile for debugging
            logger.info(
                f"Session {session.session_id}: User profile for LLM: "
                f"name={user_profile.get('name', 'NOT_SET')}, "
                f"age={user_profile.get('age_group', 'NOT_SET')}, "
                f"profession={user_profile.get('profession', 'NOT_SET')}, "
                f"gender={user_profile.get('gender', 'NOT_SET')}"
            )
            
            reply = await self.llm.generate_response(
                query=message,
                context_docs=context_docs,
                conversation_history=session.conversation_history,
                user_profile=user_profile,
                phase=ConversationPhase.LISTENING,
                memory_context=session.memory
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

    def _build_user_profile(self, memory: ConversationMemory) -> Dict:
        """
        Build a user profile dictionary from conversation memory.
        This includes all personalization data for the LLM.
        """
        profile = {}
        
        # User identity
        if memory.user_name:
            profile['name'] = memory.user_name
        
        # Demographics and current state from story
        story = memory.story
        if story.age_group:
            profile['age_group'] = story.age_group
        if story.gender:
            profile['gender'] = story.gender
        if story.profession:
            profile['profession'] = story.profession
        
        # Add situational context for the "3-Value Framework"
        if story.primary_concern:
            profile['primary_concern'] = story.primary_concern
        if story.emotional_state:
            profile['emotional_state'] = story.emotional_state
        if story.life_area:
            profile['life_area'] = story.life_area
            
        return profile

    def _build_listening_query(self, message: str, memory: ConversationMemory) -> str:
        """
        Build a search query for RAG retrieval during listening phase.
        This query focuses on the user's emotional state and life area
        to find relevant gentle wisdom.
        """
        query_parts = []
        # Add conversation summary narrative for richer RAG context
        summary = memory.get_memory_summary()
        if summary:
            query_parts.append(summary)
        
        # Fallback to current message if still empty
        if not query_parts:
            query_parts.append(message[:150])
        
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

        if not memory.story.primary_concern:
            if len(message) > 10:
                 memory.story.primary_concern = message[:200]
        else:
            if len(message) > 20 and message[:50].lower() not in memory.story.primary_concern.lower():
                memory.story.primary_concern = f"{memory.story.primary_concern} | {message[:150]}"

        # Name extraction (simple)
        if any(intro in text_lower for intro in ["my name is ", "i am ", "call me "]):
            for intro in ["my name is ", "i am ", "call me "]:
                if intro in text_lower:
                    try:
                        name = message[text_lower.find(intro) + len(intro):].split()[0].strip(',.')
                        if len(name) > 2:
                            memory.user_name = name
                            logger.info(f"Extracted name: {name}")
                    except: pass

        # Age group extraction (simple)
        if any(age_ref in text_lower for age_ref in ["years old", "i'm "]) and any(char.isdigit() for char in message):
            # Very rough guess
            if any(str(i) in message for i in range(15, 25)): memory.story.age_group = "18-24"
            elif any(str(i) in message for i in range(25, 35)): memory.story.age_group = "25-34"
            elif any(str(i) in message for i in range(35, 50)): memory.story.age_group = "35-50"

        # Expanded keyword lists for better sensitivity
        anxiety_words = ["anxious", "worried", "nervous", "panic", "stress", "overwhelmed", "pressure", "scared", "fear", "tension"]
        sadness_words = ["sad", "cry", "depressed", "lonely", "grief", "loss", "tired", "down", "low", "hopeless", "hurt"]
        anger_words = ["angry", "frustrated", "irritated", "mad", "annoyed", "hate", "unfair", "furious"]

        if any(w in text_lower for w in anxiety_words):
            memory.story.emotional_state = "anxiety"
        elif any(w in text_lower for w in sadness_words):
            memory.story.emotional_state = "sadness"
        elif any(w in text_lower for w in anger_words):
            memory.story.emotional_state = "anger"

        # Track life area
        work_words = ["job", "office", "work", "career", "salary", "boss", "deadline", "project", "business", "company"]
        relationship_words = ["marriage", "partner", "husband", "wife", "relationship", "dating", "boyfriend", "girlfriend", "breakup", "divorce"]
        family_words = ["family", "parents", "children", "son", "daughter", "mother", "father", "relative", "brother", "sister"]

        if any(w in text_lower for w in work_words):
            memory.story.life_area = "work"
        elif any(w in text_lower for w in relationship_words):
            memory.story.life_area = "relationships"
        elif any(w in text_lower for w in family_words):
            memory.story.life_area = "family"

        # Try to extract trigger event
        if any(w in text_lower for w in ["happened", "because", "after", "since", "due to", "started", "occurred"]):
            if len(message) > 25 and not memory.story.trigger_event:
                memory.story.trigger_event = message[:150]

        # Try to extract unmet needs
        if "need" in text_lower or "want" in text_lower or "wish" in text_lower:
            need_keywords = ["peace", "clarity", "guidance", "strength", "support", "solutions", "action"]
            for kw in need_keywords:
                if kw in text_lower and kw not in memory.story.unmet_needs:
                    memory.story.unmet_needs.append(kw)

        # Record a quote + emotional arc point
        memory.add_user_quote(turn=session.turn_count, quote=message[:200])
        if memory.story.emotional_state:
            memory.record_emotion(
                turn=session.turn_count,
                emotion=memory.story.emotional_state,
                intensity="moderate",
            )

        # Increase readiness faster each turn to be more responsive
        memory.readiness_for_wisdom = min(
            1.0,
            memory.readiness_for_wisdom + 0.4,
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

        return readiness >= 0.7


_companion_engine: CompanionEngine | None = None


def get_companion_engine() -> CompanionEngine:
    global _companion_engine
    if _companion_engine is None:
        _companion_engine = CompanionEngine()
    return _companion_engine
