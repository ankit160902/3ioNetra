"""Declarative conversation phase state machine.

Replaces the 87-line _assess_readiness() and inline if/else readiness
logic in CompanionEngine with a formal pytransitions FSM.

Usage:
    fsm = ConversationFSM(session)
    is_ready, trigger = fsm.evaluate(analysis, turn_topics)
"""
import logging
from typing import Dict, List, Tuple

from transitions import Machine

from models.session import SessionState, IntentType

logger = logging.getLogger(__name__)

# Emotions requiring extra listening turns before guidance
DISTRESS_EMOTIONS = frozenset({
    "shame", "grief", "guilt", "fear", "humiliation", "trauma", "panic",
})

# High-intensity emotions used inside _assess_readiness (broader set)
HIGH_INTENSITY_EMOTIONS = frozenset({
    "sadness", "anger", "anxiety", "hopelessness", "grief", "despair",
})

# Urgent keywords that bypass oscillation cooldown
URGENT_KEYWORDS = frozenset({
    "please guide", "suggest me", "tell me what",
    "give me some", "show me", "what should i",
})

# Explicit topics that bypass turn threshold entirely
EXPLICIT_TOPICS = frozenset({"Verse Request", "Product Inquiry"})

# Topics treated as guidance asks (need min turns)
GUIDANCE_TOPICS = frozenset({"Routine Request", "Puja Guidance", "Diet Plan"})

# Minimum turns between consecutive guidance phases
COOLDOWN_TURNS = 3


class ConversationFSM:
    """Conversation phase state machine.

    States: LISTENING, GUIDANCE, CLOSURE
    Evaluates intent analysis + session state to decide phase transitions.
    """

    states = ["LISTENING", "GUIDANCE", "CLOSURE"]

    def __init__(self, session: SessionState):
        self.session = session
        self._analysis: Dict = {}
        self._turn_topics: List[str] = []
        self._last_message: str = ""
        self._trigger_reason: str = "listening"

        # Map current session phase to FSM state
        initial = "LISTENING"
        if session.phase and session.phase.value == "guidance":
            initial = "GUIDANCE"
        elif session.phase and session.phase.value == "closure":
            initial = "CLOSURE"

        self.machine = Machine(
            model=self,
            states=ConversationFSM.states,
            initial=initial,
            send_event=True,
            auto_transitions=False,
        )

        # Transitions are evaluated in order — first match wins
        # 1. Closure from any state
        self.machine.add_transition(
            trigger="step",
            source=["LISTENING", "GUIDANCE"],
            dest="CLOSURE",
            conditions=["is_closure_intent"],
            before="set_trigger_closure",
        )
        # 2. Explicit request (bypasses turn threshold)
        self.machine.add_transition(
            trigger="step",
            source="LISTENING",
            dest="GUIDANCE",
            conditions=["is_explicit_request"],
            unless=["is_closure_intent", "is_greeting_intent"],
            before="set_trigger_explicit",
        )
        # 3. Guidance ask with min turns met
        self.machine.add_transition(
            trigger="step",
            source="LISTENING",
            dest="GUIDANCE",
            conditions=["is_guidance_ask", "min_turns_met_for_ask"],
            unless=["is_closure_intent", "is_greeting_intent"],
            before="set_trigger_guidance_ask",
        )
        # 4. Signal-based readiness (score + turns + cooldown)
        self.machine.add_transition(
            trigger="step",
            source="LISTENING",
            dest="GUIDANCE",
            conditions=["readiness_threshold_met", "min_turns_met_for_signals", "cooldown_passed"],
            unless=["is_closure_intent", "is_greeting_intent"],
            before="set_trigger_signals",
        )
        # 5. Force transition (max turns)
        self.machine.add_transition(
            trigger="step",
            source="LISTENING",
            dest="GUIDANCE",
            conditions=["should_force_transition"],
            unless=["is_closure_intent", "is_greeting_intent"],
            before="set_trigger_force",
        )
        # 6. Stay in LISTENING (no-op fallback, keeps state)
        self.machine.add_transition(
            trigger="step",
            source="LISTENING",
            dest=None,  # internal transition, no state change
            before="set_trigger_listening",
        )
        # 7. Return to listening after guidance
        self.machine.add_transition(
            trigger="return_to_listening",
            source="GUIDANCE",
            dest="LISTENING",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, analysis: Dict, turn_topics: List[str]) -> Tuple[bool, str]:
        """Evaluate whether to transition to GUIDANCE.

        Returns (is_ready_for_wisdom, readiness_trigger).
        """
        self._analysis = analysis
        self._turn_topics = turn_topics

        # Extract last user message for keyword checks
        history = self.session.conversation_history
        if history and history[-1].get("role") == "user":
            self._last_message = history[-1].get("content", "").lower()
        else:
            self._last_message = ""

        self._trigger_reason = "listening"

        # Fire the FSM — first matching transition wins
        self.step()

        is_ready = self.state == "GUIDANCE"

        logger.info(
            f"FSM session={self.session.session_id}: "
            f"state={self.state}, trigger={self._trigger_reason}, "
            f"turns={self.session.turn_count}, "
            f"readiness={self.session.memory.readiness_for_wisdom:.2f}"
        )

        return is_ready, self._trigger_reason

    # ------------------------------------------------------------------
    # Guard conditions (all receive EventData from pytransitions)
    # ------------------------------------------------------------------

    def is_greeting_intent(self, event=None) -> bool:
        """Greetings should ALWAYS stay in LISTENING — never jump to guidance."""
        return self._analysis.get("intent") == IntentType.GREETING

    def is_closure_intent(self, event=None) -> bool:
        return self._analysis.get("intent") == IntentType.CLOSURE

    def is_explicit_request(self, event=None) -> bool:
        intent = self._analysis.get("intent")
        if intent in (IntentType.ASKING_PANCHANG, IntentType.PRODUCT_SEARCH):
            return True
        if any(t in EXPLICIT_TOPICS for t in self._turn_topics):
            return True
        if self._analysis.get("recommend_products", False):
            return True
        if self._analysis.get("needs_direct_answer", False):
            return True
        return False

    def is_guidance_ask(self, event=None) -> bool:
        intent = self._analysis.get("intent")
        if intent in (IntentType.SEEKING_GUIDANCE, IntentType.ASKING_INFO):
            return True
        if any(t in GUIDANCE_TOPICS for t in self._turn_topics):
            return True
        return False

    def min_turns_met_for_ask(self, event=None) -> bool:
        """Min turns gate for guidance asks (distress-aware)."""
        detected_emotion = (self._analysis.get("emotion") or "").lower()
        min_turns = self.session.min_clarification_turns if detected_emotion in DISTRESS_EMOTIONS else 2
        return self.session.turn_count >= min_turns

    def min_turns_met_for_signals(self, event=None) -> bool:
        """Min turns gate for signal-based transitions (uses _assess_readiness logic)."""
        emotional_state = getattr(self.session.memory.story, "emotional_state", "")
        requires_extra = emotional_state in HIGH_INTENSITY_EMOTIONS

        # Replicate the tiered min-turns logic from _assess_readiness
        msg_lower = self._last_message
        explicit_spiritual_keywords = [
            "mantra", "shloka", "verse", "prayer", "pooja", "puja", "vrat",
            "chant", "suggest a practice", "spiritual help", "koi upay",
            "mantra batao", "kuch batao", "what should i chant",
            "give me a mantra", "suggest me", "guide me spiritually",
        ]
        guidance_phrases = [
            "what should i do", "what can i do", "how do i fix",
            "help me with", "give me advice", "suggest a solution",
            "way out", "way to deal", "how to overcome",
        ]

        if any(kw in msg_lower for kw in explicit_spiritual_keywords):
            min_turns = 2 if requires_extra else 1
        elif any(phrase in msg_lower for phrase in guidance_phrases):
            min_turns = 4 if requires_extra else 3
        else:
            min_turns = 5 if requires_extra else 3

        return self.session.turn_count >= min_turns

    def cooldown_passed(self, event=None) -> bool:
        """Oscillation cooldown: 3+ turns since last guidance, unless urgent."""
        last_guidance = getattr(self.session, "last_guidance_turn", 0) or 0
        if last_guidance <= 0:
            return True

        turns_since = self.session.turn_count - last_guidance
        if turns_since >= COOLDOWN_TURNS:
            return True

        # Check urgent keyword override
        if any(kw in self._last_message for kw in URGENT_KEYWORDS):
            logger.info(
                f"FSM session={self.session.session_id}: urgent request bypasses cooldown"
            )
            return True

        return False

    def readiness_threshold_met(self, event=None) -> bool:
        return self.session.memory.readiness_for_wisdom >= 0.7

    def should_force_transition(self, event=None) -> bool:
        return self.session.should_force_transition()

    # ------------------------------------------------------------------
    # Trigger reason callbacks (called via `before=`)
    # ------------------------------------------------------------------

    def set_trigger_closure(self, event=None):
        self._trigger_reason = "closure"

    def set_trigger_explicit(self, event=None):
        self._trigger_reason = "explicit_request"

    def set_trigger_guidance_ask(self, event=None):
        self._trigger_reason = "user_asked_for_guidance"

    def set_trigger_signals(self, event=None):
        self._trigger_reason = "signals_accumulated"

    def set_trigger_force(self, event=None):
        self._trigger_reason = "forced_transition"

    def set_trigger_listening(self, event=None):
        self._trigger_reason = "listening"
