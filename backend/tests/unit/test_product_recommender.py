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
