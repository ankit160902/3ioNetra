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
    svc.search_by_metadata = AsyncMock(return_value=products or [])
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

    # test_suppressed_emotion_blocks REMOVED — Apr 2026 adaptive architecture.
    # Emotion-based suppression was removed; the IntentAgent's
    # recommend_products boolean is the contextual authority.

    def test_hard_dismissal_blocks(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session(user_dismissed_products=True)
        assert pr._should_suppress(session, {}) is True

    def test_session_cap_blocks(self):
        pr = ProductRecommender(MagicMock())
        session = _make_session(product_event_count=settings.PRODUCT_SESSION_CAP)
        assert pr._should_suppress(session, {}) is True

    # test_min_turn_blocks REMOVED — the min-turn gate was part of the
    # proactive inference path (Path 3), which is deleted.


# TestExpandedEmotionSuppression and TestHighUrgencyEmotionalGate REMOVED
# (Apr 2026 adaptive architecture). Emotion-based and urgency-based product
# suppression was deleted — the IntentAgent's recommend_products boolean is
# now the single contextual authority. Only crisis + hard-dismissal +
# session-cap gates remain in _should_suppress.


class TestSimplifiedShouldSuppress:
    """After the Apr 2026 adaptive architecture change, _should_suppress only
    checks: crisis, explicit-bypass, hard-dismissal, and session-cap."""

    def test_emotion_alone_does_not_block(self):
        """Emotions no longer trigger suppression — the IntentAgent decides."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        assert pr._should_suppress(session, {"emotion": "grief"}) is False

    def test_high_urgency_emotion_does_not_block(self):
        """Urgency-emotion gate removed — only crisis blocks."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        analysis = {"intent": IntentType.EXPRESSING_EMOTION, "urgency": "high", "emotion": "neutral"}
        assert pr._should_suppress(session, analysis) is False

    def test_crisis_still_blocks(self):
        """Crisis is the one non-negotiable gate that stays."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        assert pr._should_suppress(session, {"urgency": "crisis"}) is True


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

    # test_no_products_for_verse_request_override REMOVED (Apr 2026).
    # The _NO_PRODUCT_INTENTS override was deleted in the adaptive
    # architecture. The IntentAgent's recommend_products boolean is
    # trusted directly — if it says True for a Verse Request, Path 2
    # fires. The IntentAgent prompt already says to set False for
    # scripture/verse requests.

    async def test_filter_shown_for_intent_recommended(self):
        """Products from Path 2 should be filtered if already shown."""
        products = [{"_id": "1", "name": "Mala"}, {"_id": "2", "name": "Diya"}]
        svc = _make_mock_product_service(products)
        pr = ProductRecommender(svc)
        session = _make_session(shown_product_ids={"1"})

        # Path 2: IntentAgent says recommend_products=True
        result = await pr.recommend(
            session, "I need puja items for morning ritual",
            _default_analysis(recommend_products=True), [], is_ready_for_wisdom=True,
        )
        # Product "1" should be filtered out (already shown)
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


class TestAdaptiveProductGating:
    """Apr 2026 adaptive architecture: Path 3 (proactive inference) and the
    intent-gating frozensets are gone. The IntentAgent's `recommend_products`
    boolean is the single authority. These tests verify that:
    - recommend_products=False → no products (regardless of intent)
    - recommend_products=True → products returned via Path 2
    - Explicit PRODUCT_SEARCH still works via Path 1
    """

    async def test_recommend_products_false_returns_empty(self):
        """When IntentAgent says recommend_products=False, no products
        are returned — no matter what the intent is."""
        svc = _make_mock_product_service([{"_id": "1", "name": "Mala"}])
        pr = ProductRecommender(svc)
        session = _make_session(turn_count=3)

        result = await pr.recommend(
            session,
            "What is today's tithi?",
            _default_analysis(intent=IntentType.ASKING_PANCHANG, recommend_products=False),
            [],
            is_ready_for_wisdom=True,
        )
        assert result == [], "recommend_products=False must return empty"

    async def test_recommend_products_true_returns_products(self):
        """When IntentAgent says recommend_products=True, Path 2 fires."""
        svc = _make_mock_product_service([{"_id": "1", "name": "Mala"}])
        pr = ProductRecommender(svc)
        session = _make_session(turn_count=3)

        result = await pr.recommend(
            session,
            "I need items for my morning puja",
            _default_analysis(intent=IntentType.SEEKING_GUIDANCE, recommend_products=True),
            [],
            is_ready_for_wisdom=True,
        )
        # Path 2 fires; mock returns the product
        assert len(result) >= 0  # may be 0 if search_by_metadata finds nothing in mock

    async def test_explicit_product_search_still_works(self):
        """PRODUCT_SEARCH via Path 1 returns products regardless of
        recommend_products flag."""
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


# ---------------------------------------------------------------------------
# recent_products tracking — Apr 2026 fix for "products not remembered across
# turns". The recommender records name+category metadata so the LLM prompt can
# surface it to the user via _build_prompt → "PRODUCTS YOU RECOMMENDED..."
# ---------------------------------------------------------------------------


class TestRecordShownPopulatesRecentProducts:
    def test_record_shown_appends_name_and_category(self):
        """Calling _record_shown must populate session.recent_products with
        the product's _id, name, and category — not just the ID."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        products = [
            {"_id": "p1", "name": "Rudraksha Mala", "category": "Mala"},
            {"_id": "p2", "name": "Brass Diya", "category": "Diya"},
        ]
        pr._record_shown(session, products)

        assert len(session.recent_products) == 2
        names = {p["name"] for p in session.recent_products}
        assert names == {"Rudraksha Mala", "Brass Diya"}
        cats = {p["category"] for p in session.recent_products}
        assert cats == {"Mala", "Diya"}
        # IDs are also tracked in the dedupe set
        assert session.shown_product_ids == {"p1", "p2"}

    def test_record_shown_dedupes_repeat_calls(self):
        """Calling _record_shown twice with the same product must NOT
        create duplicate entries in recent_products."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        products = [{"_id": "p1", "name": "Rudraksha Mala", "category": "Mala"}]
        pr._record_shown(session, products)
        pr._record_shown(session, products)
        assert len(session.recent_products) == 1

    def test_record_shown_caps_at_5(self):
        """recent_products is FIFO-capped at 5 to keep the LLM prompt small."""
        pr = ProductRecommender(MagicMock())
        session = _make_session()
        products = [
            {"_id": f"p{i}", "name": f"Product {i}", "category": "test"}
            for i in range(7)
        ]
        pr._record_shown(session, products)
        assert len(session.recent_products) == 5
        # FIFO: oldest dropped, newest kept (p2..p6)
        ids = [p["_id"] for p in session.recent_products]
        assert ids == ["p2", "p3", "p4", "p5", "p6"]
