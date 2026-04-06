"""Collects and updates session signals from intent analysis results.

Extracted from CompanionEngine to eliminate duplication between
process_message_preamble() and generate_response_stream().
"""
import logging
from typing import Dict

from models.session import SessionState, SignalType

logger = logging.getLogger(__name__)


def collect_signals_from_analysis(session: SessionState, analysis: Dict) -> None:
    """Update session signals and memory.story from intent analysis.

    Applies:
    - Life domain → session signal + story.life_area
    - Emotion → session signal + story.emotional_state
    - Dharmic concepts → memory.relevant_concepts (if empty)
    - Entities (deity, ritual) → story fields
    - Summary → story.primary_concern
    """
    # Life domain signal
    life_domain = analysis.get("life_domain")
    if life_domain and life_domain != "unknown":
        session.memory.story.life_area = life_domain
        session.add_signal(SignalType.LIFE_DOMAIN, life_domain, 0.95)

    # Emotion signal
    emotion = analysis.get("emotion")
    if emotion and emotion != "neutral":
        session.memory.story.emotional_state = emotion
        session.add_signal(SignalType.EMOTION, emotion, 0.9)

    # Populate dharmic concepts from emotion when empty
    if not session.memory.relevant_concepts and session.memory.story.emotional_state:
        try:
            from services.context_synthesizer import EMOTION_TO_CONCEPTS
            emotion_key = session.memory.story.emotional_state.lower()
            concepts = EMOTION_TO_CONCEPTS.get(emotion_key, [])
            if concepts:
                session.memory.relevant_concepts = concepts[:5]
        except ImportError:
            pass

    # Entity enrichment
    entities = analysis.get("entities", {})
    if entities.get("deity"):
        session.memory.story.preferred_deity = entities["deity"]
    if entities.get("ritual"):
        session.memory.story.primary_concern = f"Performing {entities['ritual']}"

    # Summary
    if analysis.get("summary"):
        session.memory.story.primary_concern = analysis["summary"]
