"""
Context Synthesizer - Transforms collected signals into a Dharmic Query Object
"""
from typing import List, Optional
import logging

from models.session import SessionState, SignalType
from models.dharmic_query import (
    DharmicQueryObject,
    QueryType,
    UserStage,
    ResponseStyle,
)

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# MAPPINGS
# -------------------------------------------------------------------

EMOTION_TO_CONCEPTS = {
    'anxiety': ['vairagya', 'surrender', 'present_moment', 'trust', 'breath'],
    'sadness': ['impermanence', 'acceptance', 'dharma', 'seva', 'compassion'],
    'anger': ['patience', 'forgiveness', 'detachment', 'ahimsa', 'self_control'],
    'confusion': ['viveka', 'clarity', 'svadharma', 'guidance', 'wisdom'],
    'fear': ['courage', 'faith', 'surrender', 'protection', 'strength'],
    'hopelessness': ['hope', 'grace', 'perseverance', 'dharma', 'faith'],
    'frustration': ['patience', 'acceptance', 'karma', 'equanimity', 'detachment'],
    'guilt': ['forgiveness', 'redemption', 'dharma', 'renewal', 'self_compassion'],
    'loneliness': ['connection', 'devotion', 'sangha', 'inner_self', 'love'],
    'stress': ['peace', 'balance', 'karma_yoga', 'detachment', 'breath'],
    'overwhelm': ['surrender', 'one_step', 'trust', 'simplicity', 'present_moment'],
}

LIFE_DOMAIN_TO_SCRIPTURES = {
    'work': ['Bhagavad Gita', 'Mahabharata'],
    'family': ['Ramayana', 'Mahabharata', 'Bhagavad Gita'],
    'relationships': ['Ramayana', 'Bhagavad Gita'],
    'health': ['Sanatan Scriptures', 'Bhagavad Gita'],
    'spiritual': ['Bhagavad Gita', 'Sanatan Scriptures'],
    'financial': ['Mahabharata', 'Bhagavad Gita'],
    'career': ['Bhagavad Gita', 'Mahabharata'],
}

EMOTION_TO_GUIDANCE_TYPE = {
    'anxiety': 'comfort',
    'sadness': 'comfort',
    'anger': 'understanding',
    'confusion': 'clarity',
    'fear': 'reassurance',
    'hopelessness': 'hope',
    'frustration': 'perspective',
    'guilt': 'forgiveness',
    'loneliness': 'connection',
    'stress': 'relief',
    'overwhelm': 'simplification',
}

DEFAULT_SCRIPTURES = ['Bhagavad Gita', 'Ramayana', 'Mahabharata']
DEFAULT_CONCEPTS = ['dharma', 'karma', 'peace', 'wisdom']


# -------------------------------------------------------------------
# CONTEXT SYNTHESIZER
# -------------------------------------------------------------------

class ContextSynthesizer:
    """
    Builds DharmicQueryObject for RAG + LLM
    """

    # --------------------------------------------------
    # SIGNAL-BASED (EARLY PHASE)
    # --------------------------------------------------

    async def synthesize(self, session: SessionState) -> DharmicQueryObject:
        signals = session.signals_collected

        emotion = signals.get(SignalType.EMOTION)
        trigger = signals.get(SignalType.TRIGGER)
        life_domain = signals.get(SignalType.LIFE_DOMAIN)
        mental_state = signals.get(SignalType.MENTAL_STATE)
        user_goal = signals.get(SignalType.USER_GOAL)
        intent = signals.get(SignalType.INTENT)
        severity = signals.get(SignalType.SEVERITY)

        query_text = self._extract_user_query(session)

        dharmic_query = DharmicQueryObject(
            query=query_text,
            query_type=self._determine_query_type(severity, intent, emotion),
            dharmic_concepts=self._get_dharmic_concepts(emotion),
            user_stage=self._infer_user_stage(session),
            response_style=self._determine_response_style(severity, intent),
            emotion=emotion.value if emotion else 'unknown',
            trigger=trigger.value if trigger else None,
            life_domain=life_domain.value if life_domain else None,
            mental_state=mental_state.value if mental_state else None,
            user_goal=user_goal.value if user_goal else None,
            allowed_scriptures=self._get_allowed_scriptures(life_domain),
            guidance_type=self._get_guidance_type(emotion),
            conversation_summary=self._build_conversation_summary(session),
        )

        return dharmic_query

    # --------------------------------------------------
    # MEMORY-BASED (WISDOM PHASE)  ✅ FIXED
    # --------------------------------------------------

    def synthesize_from_memory(self, session: SessionState) -> DharmicQueryObject:
        memory = session.memory
        story = memory.story

        query_text = self._extract_user_query(session)

        dharmic_query = DharmicQueryObject(
            query=query_text,
            query_type=self._determine_query_type_from_memory(story),
            dharmic_concepts=memory.relevant_concepts[:7] or DEFAULT_CONCEPTS,
            user_stage=self._infer_user_stage(session),
            response_style=self._determine_response_style_from_memory(memory),
            emotion=story.emotional_state or 'unknown',
            trigger=story.trigger_event,
            life_domain=story.life_area,
            mental_state=None,
            user_goal=story.unmet_needs[0] if story.unmet_needs else None,
            allowed_scriptures=LIFE_DOMAIN_TO_SCRIPTURES.get(
                story.life_area, DEFAULT_SCRIPTURES
            ),
            guidance_type=EMOTION_TO_GUIDANCE_TYPE.get(
                story.emotional_state, 'guidance'
            ),
            conversation_summary=memory.get_memory_summary(),
        )

        logger.info(
            f"Synthesized from memory: type={dharmic_query.query_type.value}, "
            f"emotion={dharmic_query.emotion}, "
            f"query='{query_text[:60]}'"
        )

        return dharmic_query

    # -------------------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------------------

    def _extract_user_query(self, session: SessionState) -> str:
        for msg in reversed(session.conversation_history):
            if msg.get("role") == "user" and msg.get("content"):
                return msg["content"]
        return ""

    def _determine_query_type(self, severity, intent, emotion) -> QueryType:
        if severity and severity.value == 'crisis':
            return QueryType.CRISIS_SUPPORT
        if intent:
            if intent.value in ['action', 'guidance']:
                return QueryType.PRACTICAL_ADVICE
            if intent.value in ['understanding', 'perspective']:
                return QueryType.PHILOSOPHICAL
        if emotion and emotion.value in ['sadness', 'loneliness', 'hopelessness', 'guilt']:
            return QueryType.EMOTIONAL_HEALING
        return QueryType.LIFE_GUIDANCE

    def _determine_query_type_from_memory(self, story) -> QueryType:
        if story.emotional_state in ['sadness', 'hopelessness', 'loneliness']:
            return QueryType.EMOTIONAL_HEALING
        if story.unmet_needs:
            needs = " ".join(story.unmet_needs).lower()
            if 'action' in needs or 'steps' in needs:
                return QueryType.PRACTICAL_ADVICE
            if 'understanding' in needs or 'meaning' in needs:
                return QueryType.PHILOSOPHICAL
        return QueryType.LIFE_GUIDANCE

    def _get_dharmic_concepts(self, emotion) -> List[str]:
        if emotion:
            return EMOTION_TO_CONCEPTS.get(emotion.value, DEFAULT_CONCEPTS)
        return DEFAULT_CONCEPTS

    def _infer_user_stage(self, session: SessionState) -> UserStage:
        text = " ".join(
            m.get("content", "").lower()
            for m in session.conversation_history
            if m.get("role") == "user"
        )
        hits = sum(1 for kw in ['dharma', 'karma', 'gita', 'meditation'] if kw in text)
        if hits >= 3:
            return UserStage.PRACTITIONER
        if hits >= 1:
            return UserStage.SEEKER
        return UserStage.BEGINNER

    def _determine_response_style(self, severity, intent) -> ResponseStyle:
        if severity and severity.value in ['severe', 'crisis']:
            return ResponseStyle.GENTLE_NURTURING
        if intent and intent.value == 'action':
            return ResponseStyle.DIRECT_PRACTICAL
        return ResponseStyle.GENTLE_NURTURING

    def _determine_response_style_from_memory(self, memory) -> ResponseStyle:
        if memory.emotional_arc and memory.emotional_arc[-1].get("intensity") == "high":
            return ResponseStyle.GENTLE_NURTURING
        return ResponseStyle.GENTLE_NURTURING

    def _get_allowed_scriptures(self, life_domain) -> List[str]:
        if life_domain:
            return LIFE_DOMAIN_TO_SCRIPTURES.get(life_domain.value, DEFAULT_SCRIPTURES)
        return DEFAULT_SCRIPTURES

    def _get_guidance_type(self, emotion) -> str:
        if emotion:
            return EMOTION_TO_GUIDANCE_TYPE.get(emotion.value, 'guidance')
        return 'guidance'

    def _build_conversation_summary(self, session: SessionState) -> str:
        if hasattr(session, "memory") and session.memory:
            summary = session.memory.get_memory_summary()
            if summary:
                return summary
        msgs = [
            m.get("content", "")[:150]
            for m in session.conversation_history
            if m.get("role") == "user"
        ]
        return " | ".join(msgs[-4:]) if msgs else ""


# -------------------------------------------------------------------
# SINGLETON
# -------------------------------------------------------------------

_context_synthesizer: Optional[ContextSynthesizer] = None


def get_context_synthesizer() -> ContextSynthesizer:
    global _context_synthesizer
    if _context_synthesizer is None:
        _context_synthesizer = ContextSynthesizer()
    return _context_synthesizer
