"""Comprehensive tests for ConversationFSM.

Tests every transition path:
1. LISTENING → GUIDANCE via explicit request
2. LISTENING → GUIDANCE via guidance ask + min turns
3. LISTENING → GUIDANCE via readiness score
4. LISTENING → GUIDANCE via force transition
5. ANY → CLOSURE via closure intent
6. Stay in LISTENING when no conditions met
7. Cooldown enforcement + urgent override
8. Distress emotion increases min turns
"""
import importlib.util

from models.session import SessionState, ConversationPhase, IntentType, SignalType, Signal
from models.memory_context import ConversationMemory, UserStory

# Load conversation_fsm directly to avoid services/__init__.py import chain
_fsm_path = str(__import__("pathlib").Path(__file__).resolve().parents[2] / "services" / "conversation_fsm.py")
_spec = importlib.util.spec_from_file_location("conversation_fsm", _fsm_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ConversationFSM = _mod.ConversationFSM


def _make_session(
    turn_count: int = 0,
    readiness: float = 0.0,
    emotional_state: str = "",
    last_guidance_turn: int = -1,
    signals: int = 0,
    last_user_message: str = "",
    phase: ConversationPhase = ConversationPhase.LISTENING,
) -> SessionState:
    """Helper to create a SessionState with specified conditions."""
    session = SessionState()
    session.turn_count = turn_count
    session.last_guidance_turn = last_guidance_turn
    session.phase = phase
    session.memory = ConversationMemory(
        story=UserStory(emotional_state=emotional_state),
        readiness_for_wisdom=readiness,
    )
    # Add dummy signals
    for i in range(signals):
        sig_type = list(SignalType)[i % len(list(SignalType))]
        session.signals_collected[sig_type] = Signal(signal_type=sig_type, value="test", confidence=0.9)
    # Add conversation history with last user message
    if last_user_message:
        session.conversation_history = [
            {"role": "user", "content": last_user_message},
        ]
    return session


def _default_analysis(**overrides):
    """Helper to create a default intent analysis dict."""
    base = {
        "intent": IntentType.EXPRESSING_EMOTION,
        "emotion": "anxiety",
        "life_domain": "career",
        "entities": {},
        "urgency": "normal",
        "summary": "User is worried about work",
        "needs_direct_answer": False,
        "recommend_products": False,
        "product_search_keywords": [],
        "product_rejection": False,
        "query_variants": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Transition 1: Explicit request → GUIDANCE (bypasses turn threshold)
# ---------------------------------------------------------------------------

class TestExplicitRequest:
    def test_panchang_intent_triggers_guidance(self):
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.ASKING_PANCHANG), []
        )
        assert is_ready is True
        assert trigger == "explicit_request"

    def test_product_search_intent_triggers_guidance(self):
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.PRODUCT_SEARCH), []
        )
        assert is_ready is True
        assert trigger == "explicit_request"

    def test_verse_request_topic_triggers_guidance(self):
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(), ["Verse Request"]
        )
        assert is_ready is True
        assert trigger == "explicit_request"

    def test_product_inquiry_topic_triggers_guidance(self):
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(), ["Product Inquiry"]
        )
        assert is_ready is True
        assert trigger == "explicit_request"

    def test_needs_direct_answer_triggers_guidance_for_neutral_user(self):
        """needs_direct_answer flag triggers guidance when user is not in distress."""
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(needs_direct_answer=True, emotion="curiosity"), []
        )
        assert is_ready is True
        assert trigger == "explicit_request"

    def test_recommend_products_triggers_guidance(self):
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(recommend_products=True), []
        )
        assert is_ready is True
        assert trigger == "explicit_request"

    def test_explicit_at_turn_zero(self):
        """Explicit requests should work even at turn 0."""
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.ASKING_PANCHANG), []
        )
        assert is_ready is True


# ---------------------------------------------------------------------------
# Listening-first guard for distressed users on early turns
# ---------------------------------------------------------------------------

class TestListeningFirstGuard:
    """Verify that the needs_listening_first guard blocks premature guidance.

    The intent agent's needs_direct_answer flag is heuristic and often fires
    for emotional vents. For distressed users on their first or second turn,
    the FSM should keep them in LISTENING regardless of that flag.
    """

    def test_distressed_user_turn_zero_stays_listening(self):
        """User opening with anxiety + needs_direct_answer should NOT jump to guidance."""
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(emotion="anxiety", needs_direct_answer=True), []
        )
        assert is_ready is False
        assert trigger == "listening"

    def test_distressed_user_turn_one_stays_listening(self):
        """Even on turn 1, distressed users get one more listening turn."""
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(emotion="grief", needs_direct_answer=True), []
        )
        assert is_ready is False

    def test_distressed_user_turn_two_can_proceed(self):
        """After 2 listening turns, distressed users can move to guidance."""
        session = _make_session(turn_count=2)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(emotion="anxiety", needs_direct_answer=True), []
        )
        assert is_ready is True

    def test_neutral_user_turn_zero_can_proceed(self):
        """Non-distressed users still bypass via needs_direct_answer."""
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(emotion="curiosity", needs_direct_answer=True), []
        )
        assert is_ready is True

    def test_explicit_user_request_bypasses_guard_even_when_distressed(self):
        """Verse Request and similar explicit signals are not blocked by listening-first.

        If a distressed user explicitly asks "share a verse on grief", they
        get the verse — they have explicitly named what they want.
        """
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(emotion="grief"), ["Verse Request"]
        )
        assert is_ready is True
        assert trigger == "explicit_request"

    def test_panchang_query_bypasses_guard_even_when_distressed(self):
        """Factual panchang queries are not blocked by listening-first."""
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.ASKING_PANCHANG, emotion="anxiety"), []
        )
        assert is_ready is True

    def test_distressed_user_low_intensity_emotion_can_proceed(self):
        """Mild emotions (e.g. confusion, curiosity) don't trigger the guard."""
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(emotion="confusion", needs_direct_answer=True), []
        )
        assert is_ready is True

    def test_grief_vent_misclassified_as_seeking_guidance_stays_listening(self):
        """Regression for live E2E S1: 'I lost my mother last month and I
        can't stop crying' → IntentAgent flagged as SEEKING_GUIDANCE on
        turn 1, the FSM jumped straight to GUIDANCE because transition 3
        (is_guidance_ask) had no listening guard. Adding the
        needs_listening_first guard to transition 3 fixes this — the FSM
        must now hold in LISTENING for grief openers regardless of intent.
        """
        session = _make_session(turn_count=1, last_user_message="I lost my mother and I can't stop crying")
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(
                intent=IntentType.SEEKING_GUIDANCE,
                emotion="grief",
                urgency="high",
            ),
            [],
        )
        assert is_ready is False, (
            f"Distressed grief vent on turn 1 must stay in LISTENING "
            f"regardless of intent classification (got trigger={trigger})"
        )
        assert trigger == "listening"

    def test_high_urgency_blocks_guidance_even_for_neutral_emotion(self):
        """If IntentAgent flags urgency=high, listening guard fires even
        when the surface emotion looks neutral. Urgency is the LLM's own
        severity signal — we trust it without a hardcoded emotion check.
        """
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, _ = fsm.evaluate(
            _default_analysis(
                intent=IntentType.SEEKING_GUIDANCE,
                emotion="confusion",
                urgency="high",
            ),
            [],
        )
        assert is_ready is False

    def test_high_readiness_score_blocks_when_distressed_on_turn_zero(self):
        """Even a 0.95 readiness score should not unlock guidance for a
        distressed turn-0 user. Transition 4 (signal-based) now also
        respects the listening guard.
        """
        session = _make_session(
            turn_count=0,
            readiness=0.95,
            emotional_state="grief",
            signals=4,
        )
        fsm = ConversationFSM(session)
        is_ready, _ = fsm.evaluate(
            _default_analysis(emotion="grief", urgency="high"),
            [],
        )
        assert is_ready is False

    def test_is_explicit_request_composite_remains_truthy(self):
        """The composite predicate is preserved for backwards compatibility."""
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        fsm._analysis = _default_analysis(needs_direct_answer=True)
        # The composite is True even though the transition is blocked.
        assert fsm.is_explicit_request() is True
        # The split predicates expose the difference.
        assert fsm.is_explicit_user_request() is False
        assert fsm.is_inferred_direct_answer() is True


# ---------------------------------------------------------------------------
# Transition 2: Guidance ask + min turns
# ---------------------------------------------------------------------------

class TestGuidanceAsk:
    def test_seeking_guidance_with_enough_turns(self):
        session = _make_session(turn_count=3)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.SEEKING_GUIDANCE), []
        )
        assert is_ready is True
        assert trigger == "user_asked_for_guidance"

    def test_seeking_guidance_insufficient_turns(self):
        session = _make_session(turn_count=1)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.SEEKING_GUIDANCE), []
        )
        assert is_ready is False
        assert trigger == "listening"

    def test_asking_info_with_enough_turns(self):
        session = _make_session(turn_count=2)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.ASKING_INFO), []
        )
        assert is_ready is True

    def test_routine_request_topic(self):
        session = _make_session(turn_count=3)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(), ["Routine Request"]
        )
        assert is_ready is True
        assert trigger == "user_asked_for_guidance"

    def test_distress_emotion_requires_more_turns(self):
        """Distress emotions increase min_turns from 2 to min_clarification_turns (3)."""
        session = _make_session(turn_count=2, emotional_state="grief")
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.SEEKING_GUIDANCE, emotion="grief"), []
        )
        assert is_ready is False  # 2 < 3 (distress requires 3)

    def test_distress_emotion_passes_with_enough_turns(self):
        session = _make_session(turn_count=3)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.SEEKING_GUIDANCE, emotion="grief"), []
        )
        assert is_ready is True


# ---------------------------------------------------------------------------
# Transition 3: Readiness score threshold
# ---------------------------------------------------------------------------

class TestReadinessScore:
    def test_high_readiness_with_enough_turns(self):
        session = _make_session(
            turn_count=4, readiness=0.8,
            last_user_message="I need some spiritual help"
        )
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is True
        assert trigger == "signals_accumulated"

    def test_high_readiness_but_insufficient_turns(self):
        session = _make_session(turn_count=1, readiness=0.9)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is False

    def test_low_readiness_doesnt_trigger(self):
        session = _make_session(turn_count=5, readiness=0.3)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        # Won't trigger via readiness, but may trigger via force if turns >= max
        # With default max=6 and turn=5, no force either
        assert is_ready is False


# ---------------------------------------------------------------------------
# Transition 4: Force transition
# ---------------------------------------------------------------------------

class TestForceTransition:
    def test_force_at_max_turns(self):
        session = _make_session(turn_count=7, signals=5)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is True
        assert trigger == "forced_transition"

    def test_no_force_below_max_turns(self):
        session = _make_session(turn_count=4, readiness=0.3)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is False


# ---------------------------------------------------------------------------
# Transition 5: Closure
# ---------------------------------------------------------------------------

class TestClosure:
    def test_closure_from_listening(self):
        session = _make_session(turn_count=3)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.CLOSURE), []
        )
        assert is_ready is False
        assert trigger == "closure"
        assert fsm.state == "CLOSURE"

    def test_closure_overrides_explicit_request(self):
        """Closure intent takes precedence over explicit request."""
        session = _make_session(turn_count=3)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.CLOSURE, needs_direct_answer=True), []
        )
        assert is_ready is False
        assert trigger == "closure"


# ---------------------------------------------------------------------------
# Transition 6: Stay in LISTENING
# ---------------------------------------------------------------------------

class TestStayListening:
    def test_expressing_emotion_early_turn(self):
        session = _make_session(turn_count=1, readiness=0.2)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is False
        assert trigger == "listening"
        assert fsm.state == "LISTENING"

    def test_greeting_stays_listening(self):
        session = _make_session(turn_count=0)
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(
            _default_analysis(intent=IntentType.GREETING), []
        )
        assert is_ready is False


# ---------------------------------------------------------------------------
# Cooldown enforcement
# ---------------------------------------------------------------------------

class TestCooldown:
    def test_cooldown_blocks_guidance(self):
        """After guidance at turn 5, turns 6-7 should stay in LISTENING."""
        session = _make_session(
            turn_count=6, readiness=0.9, last_guidance_turn=5,
            last_user_message="tell me more about meditation"
        )
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is False

    def test_cooldown_allows_after_spacing(self):
        """After 3+ turns, cooldown passes."""
        session = _make_session(
            turn_count=9, readiness=0.9, last_guidance_turn=5,
            last_user_message="suggest me a mantra"
        )
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is True

    def test_urgent_request_bypasses_cooldown(self):
        """Urgent keywords override the cooldown."""
        session = _make_session(
            turn_count=6, readiness=0.9, last_guidance_turn=5,
            last_user_message="please guide me on what to do"
        )
        fsm = ConversationFSM(session)
        is_ready, trigger = fsm.evaluate(_default_analysis(), [])
        assert is_ready is True


# ---------------------------------------------------------------------------
# Return to listening
# ---------------------------------------------------------------------------

class TestReturnToListening:
    def test_return_from_guidance(self):
        session = _make_session(phase=ConversationPhase.GUIDANCE)
        fsm = ConversationFSM(session)
        assert fsm.state == "GUIDANCE"
        fsm.return_to_listening()
        assert fsm.state == "LISTENING"
