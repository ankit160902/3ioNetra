"""Tests for ProductRecommender extracted from CompanionEngine."""
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from models.session import SessionState, IntentType
from models.memory_context import ConversationMemory, UserStory

# Load directly to avoid services/__init__.py chain
_path = str(Path(__file__).resolve().parents[2] / "services" / "product_recommender.py")
_spec = importlib.util.spec_from_file_location("product_recommender", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
ProductRecommender = _mod.ProductRecommender
PRACTICE_PRODUCT_MAP = _mod.PRACTICE_PRODUCT_MAP


def _make_session(turn_count=3, **kwargs) -> SessionState:
    s = SessionState()
    s.turn_count = turn_count
    s.memory = ConversationMemory(story=UserStory())
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


def _make_mock_product_service(products=None):
    svc = MagicMock()
    svc.search_products = AsyncMock(return_value=products or [])
    svc.get_recommended_products = AsyncMock(return_value=products or [])
    return svc


def _default_analysis(**overrides):
    base = {
        "intent": IntentType.EXPRESSING_EMOTION,
        "emotion": "anxiety",
        "life_domain": "career",
        "entities": {},
        "urgency": "normal",
        "needs_direct_answer": False,
        "recommend_products": False,
        "product_search_keywords": [],
        "product_rejection": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Gatekeeper tests
# ---------------------------------------------------------------------------

class TestShouldSuppress:
    def test_crisis_blocks_even_explicit(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        assert pr._should_suppress(session, {"urgency": "crisis"}, is_explicit_request=True) is True

    def test_explicit_bypasses_all_except_crisis(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session(product_event_count=99)
        assert pr._should_suppress(session, {"urgency": "normal"}, is_explicit_request=True) is False

    def test_suppressed_emotion_blocks(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        assert pr._should_suppress(session, {"emotion": "grief"}) is True

    def test_hard_dismissal_blocks(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session(user_dismissed_products=True)
        assert pr._should_suppress(session, {}) is True

    def test_session_cap_blocks(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session(product_event_count=settings.PRODUCT_SESSION_CAP)
        assert pr._should_suppress(session, {}) is True

    def test_min_turn_blocks(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session(turn_count=0)
        assert pr._should_suppress(session, {}) is True


class TestExpandedEmotionSuppression:
    """Verify the expanded PRODUCT_SUPPRESS_EMOTIONS list catches more
    distress states. Each test asserts that products are blocked for
    that specific emotion — what the evaluation report flagged as
    'tone-deaf product cards during anger / anxiety / loneliness'.
    """

    def _block(self, emotion):
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        return pr._should_suppress(session, {"emotion": emotion})

    def test_anger_blocks(self):
        assert self._block("anger") is True

    def test_anxiety_blocks(self):
        assert self._block("anxiety") is True

    def test_fear_blocks(self):
        assert self._block("fear") is True

    def test_panic_blocks(self):
        assert self._block("panic") is True

    def test_loneliness_blocks(self):
        assert self._block("loneliness") is True

    def test_guilt_blocks(self):
        assert self._block("guilt") is True

    def test_humiliation_blocks(self):
        assert self._block("humiliation") is True

    def test_trauma_blocks(self):
        assert self._block("trauma") is True

    def test_sadness_blocks(self):
        assert self._block("sadness") is True

    def test_neutral_does_not_block(self):
        assert self._block("neutral") is False

    def test_curiosity_does_not_block(self):
        assert self._block("curiosity") is False

    def test_hope_does_not_block(self):
        assert self._block("hope") is False


class TestHighUrgencyEmotionalGate:
    """Verify the defense-in-depth gate that blocks products when intent is
    EXPRESSING_EMOTION and urgency is high, even if the emotion field came
    back as 'neutral' (LLM uncertainty)."""

    def test_high_urgency_emotional_blocks_even_neutral_emotion(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        analysis = {
            "intent": IntentType.EXPRESSING_EMOTION,
            "urgency": "high",
            "emotion": "neutral",
        }
        assert pr._should_suppress(session, analysis) is True

    def test_high_urgency_non_emotion_intent_does_not_block_via_this_gate(self):
        """Other intents still go through the emotion-set check, not the urgency gate."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        analysis = {
            "intent": IntentType.PRODUCT_SEARCH,
            "urgency": "high",
            "emotion": "curiosity",
        }
        # PRODUCT_SEARCH explicit user requests bypass emotion gates entirely
        # via is_explicit_request, but here we're testing _should_suppress's
        # internal urgency-emotional gate. Since intent is not EXPRESSING_EMOTION,
        # the urgency gate does NOT trigger.
        assert pr._should_suppress(session, analysis, is_explicit_request=False) is False

    def test_normal_urgency_emotional_does_not_trigger_urgency_gate(self):
        """Normal urgency relies on the emotion-set check, not the urgency gate."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        analysis = {
            "intent": IntentType.EXPRESSING_EMOTION,
            "urgency": "normal",
            "emotion": "curiosity",  # not in suppress set
        }
        assert pr._should_suppress(session, analysis) is False


# ---------------------------------------------------------------------------
# Rejection detection tests
# ---------------------------------------------------------------------------

class TestRejectDetection:
    def test_hard_dismiss_phrase(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        pr._detect_product_rejection(session, "Stop suggesting products please")
        assert session.user_dismissed_products is True

    def test_soft_rejection_counted(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        pr._detect_product_rejection(session, "I don't want products right now")
        assert session.product_rejection_count == 1
        assert session.user_dismissed_products is False

    def test_two_soft_rejections_trigger_hard_dismiss(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        pr._detect_product_rejection(session, "No products please")
        pr._detect_product_rejection(session, "I don't need products")
        assert session.user_dismissed_products is True


# ---------------------------------------------------------------------------
# Acceptance detection tests
# ---------------------------------------------------------------------------

class TestAcceptance:
    def test_yes_is_acceptance(self):
        assert ProductRecommender._is_acceptance("Yes, I will try that") is True

    def test_no_is_not_acceptance(self):
        assert ProductRecommender._is_acceptance("No, I don't want that") is False

    def test_long_message_is_not_acceptance(self):
        assert ProductRecommender._is_acceptance("a " * 40) is False

    def test_thanks_is_acceptance(self):
        assert ProductRecommender._is_acceptance("Thank you, sounds good") is True


# ---------------------------------------------------------------------------
# Recommend entry point tests
# ---------------------------------------------------------------------------

class TestRecommend:
    async def test_explicit_product_request(self):
        products = [{"_id": "1", "name": "Rudraksha Mala"}]
        svc = _make_mock_product_service(products)
        pr = ProductRecommender(svc)
        session = _make_session(turn_count=3)

        result = await pr.recommend(
            session, "I want to buy a mala",
            _default_analysis(intent=IntentType.PRODUCT_SEARCH),
            ["Product Inquiry"], is_ready_for_wisdom=True,
        )
        assert len(result) == 1
        assert result[0]["name"] == "Rudraksha Mala"
        svc.search_products.assert_called_once()

    async def test_no_products_for_crisis(self):
        svc = _make_mock_product_service([{"_id": "1", "name": "X"}])
        pr = ProductRecommender(svc)
        session = _make_session()

        result = await pr.recommend(
            session, "I want to buy something",
            _default_analysis(intent=IntentType.PRODUCT_SEARCH, urgency="crisis"),
            ["Product Inquiry"], is_ready_for_wisdom=True,
        )
        assert result == []

    async def test_no_products_for_verse_request_override(self):
        """recommend_products=True should be overridden for Verse Request topics."""
        svc = _make_mock_product_service([{"_id": "1", "name": "X"}])
        pr = ProductRecommender(svc)
        session = _make_session()

        result = await pr.recommend(
            session, "Give me a verse from the Gita",
            _default_analysis(recommend_products=True),
            ["Verse Request"], is_ready_for_wisdom=True,
        )
        # Should not call search because recommend_products was overridden
        assert result == []

    async def test_filter_shown_for_proactive(self):
        """Proactive products should be filtered if already shown."""
        products = [{"_id": "1", "name": "Mala"}, {"_id": "2", "name": "Diya"}]
        svc = _make_mock_product_service(products)
        pr = ProductRecommender(svc)
        session = _make_session(shown_product_ids={"1"})

        # Force proactive path by using acceptance message
        session.conversation_history = [
            {"role": "assistant", "content": "I suggest daily japa meditation with a mala."},
            {"role": "user", "content": "ok i will try"},
        ]
        result = await pr.recommend(
            session, "ok i will try",
            _default_analysis(), [], is_ready_for_wisdom=True,
        )
        # Product "1" should be filtered out
        assert all(p["_id"] != "1" for p in result)

    async def test_listening_phase_only_explicit(self):
        """In listening phase, only explicit PRODUCT_SEARCH gets products."""
        svc = _make_mock_product_service([{"_id": "1", "name": "X"}])
        pr = ProductRecommender(svc)
        session = _make_session()

        # Non-explicit, non-product intent in listening phase
        result = await pr.recommend(
            session, "I feel stressed",
            _default_analysis(recommend_products=False),
            [], is_ready_for_wisdom=False,
        )
        assert result == []


# ---------------------------------------------------------------------------
# Intent-based product gating tests (Apr 9 2026 — fixes the "shopping kiosk"
# bug where every guidance-phase response returned 3-5 product cards even
# when the user asked an educational/panchang/emotional question. The fix
# expanded _SKIP_PROACTIVE_INTENTS and _NO_PRODUCT_INTENTS to include
# ASKING_PANCHANG, ASKING_INFO, EXPRESSING_EMOTION, and OTHER. These tests
# lock that behavior in so a future refactor can't reintroduce the spam.)
# ---------------------------------------------------------------------------


class TestIntentGating:
    """Verify that the proactive-inference path (Path 3 of recommend()) is
    blocked for intents that should never trigger product recommendations.

    Each test sets up a guidance-phase call (is_ready_for_wisdom=True) with
    products available in the mock service AND a message that would normally
    match the proactive-inference keyword maps. The assertion is that the
    intent gate short-circuits before the proactive path can fire.
    """

    async def test_panchang_intent_returns_no_products(self):
        """ASKING_PANCHANG must NOT trigger product recommendations.

        Real-world failure: a user asking 'what is today's tithi?' was
        getting 3 mala/diya cards alongside the panchang reading because
        the proactive-inference path keyword-matched on incidental terms.
        After the fix, the intent gate at the top of recommend() returns
        [] before any inference runs.
        """
        svc = _make_mock_product_service([{"_id": "1", "name": "Mala"}])
        pr = ProductRecommender(svc)
        session = _make_session(turn_count=3)

        result = await pr.recommend(
            session,
            "What is today's tithi and is it auspicious for a puja?",
            _default_analysis(intent=IntentType.ASKING_PANCHANG, recommend_products=False),
            [],
            is_ready_for_wisdom=True,
        )
        assert result == [], "panchang queries should never return products"

    async def test_asking_info_intent_returns_no_products(self):
        """ASKING_INFO (educational queries) must NOT trigger product recs.

        Real-world failure: 'tell me about Mahabharata' returned mala
        recommendations. Educational queries are about learning, not
        shopping — products break the conversational tone.
        """
        svc = _make_mock_product_service([{"_id": "1", "name": "Mala"}])
        pr = ProductRecommender(svc)
        session = _make_session(turn_count=3)

        result = await pr.recommend(
            session,
            "Tell me one beautiful thing about Mahabharata",
            _default_analysis(intent=IntentType.ASKING_INFO, recommend_products=False),
            [],
            is_ready_for_wisdom=True,
        )
        assert result == [], "educational queries should never return products"

    async def test_expressing_emotion_intent_returns_no_products(self):
        """EXPRESSING_EMOTION must NOT trigger product recs.

        Real-world failure: a user venting about career stress was getting
        rudraksha mala suggestions in the same response. Emotional support
        and shopping are not compatible — the bot needs to listen, not sell.
        Note: there's already a separate emotion-suppression gate
        (_should_suppress checks the emotion field), but this test asserts
        the intent gate is ALSO sufficient even with neutral emotion.
        """
        svc = _make_mock_product_service([{"_id": "1", "name": "Mala"}])
        pr = ProductRecommender(svc)
        session = _make_session(turn_count=3)

        result = await pr.recommend(
            session,
            "I've been feeling lost and unsure about life lately",
            _default_analysis(
                intent=IntentType.EXPRESSING_EMOTION,
                emotion="neutral",  # bypass the emotion-set check; rely on intent gate
                recommend_products=False,
            ),
            [],
            is_ready_for_wisdom=True,
        )
        assert result == [], "emotional shares should never return products"

    async def test_explicit_product_search_still_works_after_gating(self):
        """REGRESSION: PRODUCT_SEARCH must STILL return products.

        The intent-gating fix expanded _SKIP_PROACTIVE_INTENTS and
        _NO_PRODUCT_INTENTS, but PRODUCT_SEARCH is intentionally NOT in
        either set — explicit shopping requests bypass the intent gate
        via Path 1 of recommend(). This test guards against an over-
        eager future change that would also block Path 1.
        """
        products = [{"_id": "1", "name": "Rudraksha Mala"}]
        svc = _make_mock_product_service(products)
        pr = ProductRecommender(svc)
        session = _make_session(turn_count=3)

        result = await pr.recommend(
            session,
            "I want to buy a rudraksha mala for daily japa",
            _default_analysis(intent=IntentType.PRODUCT_SEARCH),
            ["Product Inquiry"],
            is_ready_for_wisdom=True,
        )
        assert len(result) == 1
        assert result[0]["name"] == "Rudraksha Mala"


# ---------------------------------------------------------------------------
# Static maps test
# ---------------------------------------------------------------------------

class TestProductMaps:
    def test_practice_map_has_japa(self):
        assert "japa" in PRACTICE_PRODUCT_MAP
        assert "search_keywords" in PRACTICE_PRODUCT_MAP["japa"]

    def test_practice_map_has_detect_and_keywords(self):
        for name, info in PRACTICE_PRODUCT_MAP.items():
            assert "detect" in info, f"{name} missing 'detect'"
            assert "search_keywords" in info, f"{name} missing 'search_keywords'"
            assert len(info["detect"]) > 0, f"{name} has empty 'detect'"
            assert len(info["search_keywords"]) > 0, f"{name} has empty 'search_keywords'"


# Need to import settings for gate tests
from config import settings
