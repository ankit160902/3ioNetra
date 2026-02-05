import logging
import random
from typing import Tuple, Optional, TYPE_CHECKING, Dict

from models.session import SessionState, ConversationPhase, SignalType
from models.memory_context import ConversationMemory
from llm.service import get_llm_service

if TYPE_CHECKING:
    from rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)


class CompanionEngine:
    """
    Empathetic front-line companion.

    Responsibilities:
    - Listen and update ConversationMemory
    - Decide when we're ready for dharmic wisdom
    - Generate grounded empathetic responses
    """

    def __init__(self, rag_pipeline: Optional["RAGPipeline"] = None) -> None:
        self.llm = get_llm_service()
        self.rag_pipeline = rag_pipeline
        self.available = self.llm.available
        logger.info(f"CompanionEngine initialized (LLM available={self.available})")

    def set_rag_pipeline(self, rag_pipeline: "RAGPipeline") -> None:
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
        Returns:
            (assistant_text, is_ready_for_wisdom)
        """
        self._update_memory(session.memory, session, message)

        is_ready = self._assess_readiness(session)

        # ------------------------------------------------------------------
        # Ready for wisdom → return short acknowledgement only
        # ------------------------------------------------------------------
        if is_ready:
            acknowledgements = [
                "Thank you for sharing. Let me reflect on this through the lens of Dharma.",
                "I appreciate your honesty. I'm looking into the scriptures for guidance.",
                "Your words touch me. Let me find a relevant verse to help guide us.",
            ]
            return random.choice(acknowledgements), True

        # ------------------------------------------------------------------
        # Listening / clarification phase
        # ------------------------------------------------------------------
        if self.llm.available:
            context_docs = []

            if self.rag_pipeline and self.rag_pipeline.available:
                try:
                    search_query = self._build_listening_query(message, session.memory)
                    context_docs = await self.rag_pipeline.search(
                        query=search_query,
                        scripture_filter=None,
                        language="en",
                        top_k=3,
                    )
                except Exception as e:
                    logger.warning(f"Listening-phase RAG failed: {e}")

            reply = await self.llm.generate_response(
                query=message,
                context_docs=context_docs,
                conversation_history=session.conversation_history,
                user_profile=self._build_user_profile(session.memory),
                phase=ConversationPhase.CLARIFICATION,
                memory_context=session.memory,
            )

            return reply, False

        # Fallback (no LLM)
        return (
            "I’m here with you. Could you tell me a little more about what feels most heavy right now?",
            False,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assess_readiness(self, session: SessionState) -> bool:
        """
        Decide if we should transition to ANSWERING phase.
        Requires more listening turns for emotionally intense situations.
        """
        readiness = session.memory.readiness_for_wisdom
        emotional_state = session.memory.story.emotional_state
        
        # High-intensity emotions require more listening before guidance
        high_intensity_emotions = ['sadness', 'anger', 'anxiety', 'hopelessness', 'grief', 'despair']
        requires_extra_listening = emotional_state in high_intensity_emotions

        # check if it is a direct question (user seeking answers)
        last_msg = ""
        if session.conversation_history and session.conversation_history[-1]["role"] == "user":
            last_msg = session.conversation_history[-1]["content"]
        
        is_direct_question = "?" in last_msg or any(w in last_msg.lower() for w in ["how", "what", "guide", "help", "solution"])

        if requires_extra_listening:
             # Even with direct questions, emotional cases need SOME listening
             min_turns_for_guidance = 3 if is_direct_question else 4
        else:
             # Standard cases: 2 turns is enough if they ask questions
             min_turns_for_guidance = 1 if is_direct_question else 2
        
        # Log the assessment
        logger.info(
            f"Session {session.session_id}: readiness={readiness:.2f}, turns={session.turn_count}, "
            f"emotion={emotional_state}, min_turns={min_turns_for_guidance}, direct_q={is_direct_question}"
        )
        
        # STRICT RULE: Require minimum turn count even if signals are collected
        if session.turn_count < min_turns_for_guidance:
             return False

        # Ensure spacing between guidance turns (Oscillation Logic)
        MIN_SPACING = 3
        last_guidance = getattr(session, 'last_guidance_turn', 0) or 0
        if last_guidance > 0 and (session.turn_count - last_guidance) < MIN_SPACING:
            logger.info(
                f"Session {session.session_id}: deferring guidance due to spacing "
                f"(last={last_guidance}, current={session.turn_count}, needed={MIN_SPACING})"
            )
            return False

        # Now check if we should force transition due to signal density/max turns
        if session.should_force_transition():
            logger.info(
                f"Session {session.session_id}: forced wisdom after {session.turn_count} turns"
            )
            return True

        return readiness >= 0.7

    def _build_user_profile(self, memory: ConversationMemory) -> Dict:
        profile = {}

        if memory.user_name:
            profile["name"] = memory.user_name

        story = memory.story
        if story.age_group:
            profile["age_group"] = story.age_group
        if story.gender:
            profile["gender"] = story.gender
        if story.profession:
            profile["profession"] = story.profession
        if story.primary_concern:
            profile["primary_concern"] = story.primary_concern
        if story.emotional_state:
            profile["emotional_state"] = story.emotional_state
        if story.life_area:
            profile["life_area"] = story.life_area
        if story.preferred_deity:
            profile["preferred_deity"] = story.preferred_deity
        if story.location:
            profile["location"] = story.location
        if story.spiritual_interests:
            profile["spiritual_interests"] = story.spiritual_interests
        
        # 🔥 Added nested spiritual profile fields
        if story.rashi:
            profile["rashi"] = story.rashi
        if story.gotra:
            profile["gotra"] = story.gotra
        if story.nakshatra:
            profile["nakshatra"] = story.nakshatra
        if story.temple_visits:
            profile["temple_visits"] = story.temple_visits
        if story.purchase_history:
            profile["purchase_history"] = story.purchase_history

        return profile

    def _build_listening_query(
        self, message: str, memory: ConversationMemory
    ) -> str:
        summary = memory.get_memory_summary()
        return summary if summary else message[:150]

    async def reconstruct_memory(self, session: SessionState, history: list) -> None:
        """Reconstruct high-level memory from historical messages"""
        if not history:
            return
            
        logger.info(f"Reconstructing deep memory from {len(history)} past messages...")
        
        # Process messages in order to rebuild the story
        for msg in history:
            if msg.get("role") == "user":
                self._update_memory(session.memory, session, msg.get("content", ""))
            
        logger.info(f"Memory reconstruction complete. Story concern: {session.memory.story.primary_concern[:50]}...")

    def _update_memory(
        self,
        memory: ConversationMemory,
        session: SessionState,
        message: str,
    ) -> None:
        text = message.lower().strip()

        if not memory.story.primary_concern and len(message) > 10:
            memory.story.primary_concern = message[:200]

        sadness = ["sad", "low", "lonely", "depressed", "tired", "hurt"]
        anxiety = ["anxious", "worried", "stressed", "overwhelmed"]
        anger = ["angry", "frustrated", "irritated"]

        if any(w in text for w in sadness):
            memory.story.emotional_state = "sadness"
            session.add_signal(SignalType.EMOTION, "sadness", 0.8)
        elif any(w in text for w in anxiety):
            memory.story.emotional_state = "anxiety"
            session.add_signal(SignalType.EMOTION, "anxiety", 0.8)
        elif any(w in text for w in anger):
            memory.story.emotional_state = "anger"
            session.add_signal(SignalType.EMOTION, "anger", 0.8)

        if any(w in text for w in ["work", "job", "office"]):
            memory.story.life_area = "work"
            session.add_signal(SignalType.LIFE_DOMAIN, "work", 0.9)
        elif any(w in text for w in ["relationship", "partner", "marriage"]):
            memory.story.life_area = "relationships"
            session.add_signal(SignalType.LIFE_DOMAIN, "relationships", 0.9)
        elif any(w in text for w in ["family", "parents", "children"]):
            memory.story.life_area = "family"
            session.add_signal(SignalType.LIFE_DOMAIN, "family", 0.9)

        # Temple and Pilgrimage detection
        temple_keywords = ["temple", "mandir", "visit", "trip", "pilgrimage", "architecture", "darshan", "puri", "kashi", "tirupati", "badrinath", "kedarnath", "dwarka", "rameswaram"]
        if any(w in text for w in temple_keywords):
            memory.story.temple_interest = message[:100]
            session.add_signal(SignalType.INTENT, "temple_interest", 0.7)
            # Boost readiness if they are asking about temples
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.3)

        # Longer quotes for better recall
        memory.add_user_quote(session.turn_count, message[:500])

        if memory.story.emotional_state:
            memory.record_emotion(
                session.turn_count,
                memory.story.emotional_state,
                "moderate",
            )
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.1)

        if len(message) > 100:
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.15)


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_companion_engine: Optional[CompanionEngine] = None


def get_companion_engine() -> CompanionEngine:
    global _companion_engine
    if _companion_engine is None:
        _companion_engine = CompanionEngine()
    return _companion_engine
