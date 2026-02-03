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
                "Thank you for sharing this so openly. Let me reflect and bring you wisdom from the scriptures.",
                "I appreciate your honesty. I will now look into the ancient teachings for guidance.",
                "Your words help me understand deeply. Let me draw from Dharma to respond thoughtfully.",
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
        """
        if session.should_force_transition():
            logger.info(
                f"Session {session.session_id}: forced wisdom after {session.turn_count} turns"
            )
            return True

        readiness = session.memory.readiness_for_wisdom
        logger.info(
            f"Session {session.session_id}: readiness={readiness:.2f}, turns={session.turn_count}"
        )

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

        return profile

    def _build_listening_query(
        self, message: str, memory: ConversationMemory
    ) -> str:
        summary = memory.get_memory_summary()
        return summary if summary else message[:150]

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
        elif any(w in text for w in anxiety):
            memory.story.emotional_state = "anxiety"
        elif any(w in text for w in anger):
            memory.story.emotional_state = "anger"

        if any(w in text for w in ["work", "job", "office"]):
            memory.story.life_area = "work"
        elif any(w in text for w in ["relationship", "partner", "marriage"]):
            memory.story.life_area = "relationships"
        elif any(w in text for w in ["family", "parents", "children"]):
            memory.story.life_area = "family"

        # Temple and Pilgrimage detection
        temple_keywords = ["temple", "mandir", "visit", "trip", "pilgrimage", "architecture", "darshan", "puri", "kashi", "tirupati", "badrinath", "kedarnath", "dwarka", "rameswaram"]
        if any(w in text for w in temple_keywords):
            memory.story.temple_interest = message[:100]
            # Boost readiness if they are asking about temples
            memory.readiness_for_wisdom = min(1.0, memory.readiness_for_wisdom + 0.3)

        memory.add_user_quote(session.turn_count, message[:200])

        if memory.story.emotional_state:
            memory.record_emotion(
                session.turn_count,
                memory.story.emotional_state,
                "moderate",
            )

        # ✅ THIS IS NOW USED CORRECTLY
        memory.readiness_for_wisdom = min(
            1.0,
            memory.readiness_for_wisdom + 0.2,
        )


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_companion_engine: Optional[CompanionEngine] = None


def get_companion_engine() -> CompanionEngine:
    global _companion_engine
    if _companion_engine is None:
        _companion_engine = CompanionEngine()
    return _companion_engine
