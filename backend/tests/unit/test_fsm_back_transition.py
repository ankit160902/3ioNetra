"""Tests for FSM GUIDANCE->LISTENING back-transition.

After a guidance turn, the FSM must return to LISTENING on the next turn
so the oscillation cooldown and listening-first guards can function.
"""
import pytest
from models.session import SessionState, ConversationPhase
from models.memory_context import ConversationMemory
from services.conversation_fsm import ConversationFSM


def _make_session(phase=ConversationPhase.GUIDANCE, turn_count=3, last_guidance_turn=2, readiness=0.3):
    session = SessionState()
    session.phase = phase
    session.turn_count = turn_count
    session.last_guidance_turn = last_guidance_turn
    session.memory = ConversationMemory()
    session.memory.readiness_for_wisdom = readiness
    session.conversation_history = [
        {"role": "user", "content": "test message"},
    ]
    return session


def test_guidance_returns_to_listening_on_next_turn():
    """After guidance, next non-closure turn must land in LISTENING."""
    session = _make_session(phase=ConversationPhase.GUIDANCE, turn_count=3, last_guidance_turn=2)
    fsm = ConversationFSM(session)
    assert fsm.state == "GUIDANCE"

    analysis = {
        "intent": "EXPRESSING_EMOTION",
        "emotion": "gratitude",
        "needs_direct_answer": False,
        "recommend_products": False,
        "life_domain": "relationships",
        "urgency": "normal",
        "response_mode": "presence_first",
    }
    is_ready, trigger = fsm.evaluate(analysis, [])
    assert not is_ready, f"Expected LISTENING but got GUIDANCE (trigger={trigger})"
    assert fsm.state == "LISTENING"


def test_guidance_stays_for_closure_intent():
    """Closure intent from GUIDANCE should go to CLOSURE, not LISTENING."""
    session = _make_session(phase=ConversationPhase.GUIDANCE, turn_count=4, last_guidance_turn=3)
    fsm = ConversationFSM(session)

    analysis = {
        "intent": "CLOSURE",
        "emotion": "gratitude",
        "needs_direct_answer": False,
        "recommend_products": False,
        "urgency": "normal",
        "response_mode": "closure",
    }
    is_ready, trigger = fsm.evaluate(analysis, [])
    assert fsm.state == "CLOSURE"


def test_full_cycle_listening_guidance_listening():
    """Full cycle: LISTENING -> GUIDANCE -> LISTENING."""
    session = _make_session(
        phase=ConversationPhase.LISTENING,
        turn_count=1,
        last_guidance_turn=-1,
        readiness=0.0,
    )
    fsm = ConversationFSM(session)
    assert fsm.state == "LISTENING"

    # Explicit verse request -> should transition to GUIDANCE
    analysis = {
        "intent": "SEEKING_GUIDANCE",
        "emotion": "neutral",
        "needs_direct_answer": True,
        "recommend_products": False,
        "urgency": "normal",
        "response_mode": "teaching",
    }
    is_ready, trigger = fsm.evaluate(analysis, ["Verse Request"])
    assert is_ready
    assert fsm.state == "GUIDANCE"

    # Simulate next turn -- session is now in GUIDANCE
    session.phase = ConversationPhase.GUIDANCE
    session.turn_count = 2
    session.last_guidance_turn = 1

    fsm2 = ConversationFSM(session)
    analysis2 = {
        "intent": "EXPRESSING_EMOTION",
        "emotion": "hope",
        "needs_direct_answer": False,
        "recommend_products": False,
        "urgency": "normal",
        "response_mode": "presence_first",
    }
    is_ready2, trigger2 = fsm2.evaluate(analysis2, [])
    assert not is_ready2, "Should return to LISTENING after guidance"
    assert fsm2.state == "LISTENING"
