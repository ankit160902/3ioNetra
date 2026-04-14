"""Tests for the simplified ProductRecommender (LLM-as-sole-authority)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from models.session import SessionState
from models.memory_context import ConversationMemory, RelationalProfile


def _make_session():
    session = SessionState()
    session.memory = ConversationMemory()
    session.shown_product_ids = set()
    session.recent_products = []
    return session


def _make_signal(intent="none", keywords=None, max_results=0, type_filter="any"):
    return {
        "intent": intent,
        "confidence": 0.8,
        "search_keywords": keywords or [],
        "max_results": max_results,
        "type_filter": type_filter,
        "sensitivity_note": "",
    }


class TestHardSafetyRails:

    @pytest.mark.asyncio
    async def test_crisis_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        analysis = {"urgency": "crisis", "product_signal": _make_signal("explicit_search", ["mala"], 3)}
        result = await pr.recommend(session, "help me", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_opted_out_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("contextual_need", ["mala"], 2)}

        with patch("services.product_recommender.load_relational_profile") as mock_load:
            profile = RelationalProfile()
            profile.product_preference = "opted_out"
            mock_load.return_value = profile
            result = await pr.recommend(session, "I need a mala", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_opted_out_overridden_by_explicit_search(self):
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[{"_id": "p1", "name": "Mala"}])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("explicit_search", ["mala"], 3)}

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction") as mock_update:
            profile = RelationalProfile()
            profile.product_preference = "opted_out"
            mock_load.return_value = profile
            mock_update.return_value = None
            result = await pr.recommend(session, "where can I buy a mala?", analysis)
        assert len(result) > 0


class TestLLMAuthority:

    @pytest.mark.asyncio
    async def test_intent_none_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        analysis = {"urgency": "normal", "product_signal": _make_signal("none")}
        result = await pr.recommend(session, "I feel sad", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_intent_negative_returns_empty_and_records(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("negative")}

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction") as mock_update:
            mock_load.return_value = RelationalProfile()
            mock_update.return_value = None
            result = await pr.recommend(session, "stop suggesting products", analysis)
        assert result == []
        mock_update.assert_called_once()
        call_args = mock_update.call_args[0]
        assert call_args[1].get("product_preference") == "opted_out"

    @pytest.mark.asyncio
    async def test_contextual_need_triggers_search(self):
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[
            {"_id": "p1", "name": "Rudraksha Mala", "amount": 499}
        ])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        session.memory.user_id = "u123"
        analysis = {"urgency": "normal", "product_signal": _make_signal("contextual_need", ["mala"], 2)}

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            result = await pr.recommend(session, "I need a mala for japa", analysis)
        assert len(result) == 1
        assert result[0]["name"] == "Rudraksha Mala"

    @pytest.mark.asyncio
    async def test_no_keywords_returns_empty(self):
        from services.product_recommender import ProductRecommender
        pr = ProductRecommender(product_service=MagicMock())
        session = _make_session()
        analysis = {"urgency": "normal", "product_signal": _make_signal("contextual_need", [], 2)}
        result = await pr.recommend(session, "suggest something", analysis)
        assert result == []

    @pytest.mark.asyncio
    async def test_type_filter_strips_only_suffix(self):
        """Bug #1: type_filter 'physical_only' must be normalized to 'physical'."""
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[
            {"_id": "p1", "name": "Krishna Murti", "product_type": "physical"}
        ])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        analysis = {
            "urgency": "normal",
            "product_signal": _make_signal("contextual_need", ["krishna", "murti"], 3, type_filter="physical_only"),
        }

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            result = await pr.recommend(session, "I want a Krishna murti", analysis)

        # Verify search_products was called with "physical", not "physical_only"
        mock_service.search_products.assert_called_once()
        call_kwargs = mock_service.search_products.call_args
        assert call_kwargs.kwargs.get("product_type") == "physical" or \
               call_kwargs[1].get("product_type") == "physical", \
               f"Expected product_type='physical', got {call_kwargs}"
        assert len(result) == 1


class TestMetadataFallback:

    @pytest.mark.asyncio
    async def test_practices_passed_to_metadata_fallback(self):
        """Bug #2: practices from entities must be passed to search_by_metadata."""
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[])
        mock_service.search_by_metadata = AsyncMock(return_value=[
            {"_id": "p1", "name": "Puja Thali Set", "product_type": "physical"}
        ])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        analysis = {
            "urgency": "normal",
            "life_domain": "spiritual",
            "emotion": "neutral",
            "entities": {"ritual": "puja", "deity": "Ganesh"},
            "product_signal": _make_signal("contextual_need", ["puja", "thali"], 3),
        }

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            result = await pr.recommend(session, "I need puja items for Ganesh puja", analysis)

        mock_service.search_by_metadata.assert_called_once()
        call_kwargs = mock_service.search_by_metadata.call_args[1]
        assert call_kwargs.get("practices") is not None, \
            f"practices not passed to search_by_metadata. Got kwargs: {call_kwargs}"
        assert "puja" in call_kwargs["practices"], \
            f"Expected 'puja' in practices, got {call_kwargs['practices']}"

    @pytest.mark.asyncio
    async def test_practice_terms_extracted_from_keywords(self):
        """Bug #2: practice terms in search_keywords should also be passed."""
        from services.product_recommender import ProductRecommender
        mock_service = MagicMock()
        mock_service.search_products = AsyncMock(return_value=[])
        mock_service.search_by_metadata = AsyncMock(return_value=[])
        pr = ProductRecommender(product_service=mock_service)
        session = _make_session()
        analysis = {
            "urgency": "normal",
            "life_domain": "spiritual",
            "emotion": "neutral",
            "entities": {},
            "product_signal": _make_signal("contextual_need", ["meditation", "cushion"], 3),
        }

        with patch("services.product_recommender.load_relational_profile") as mock_load, \
             patch("services.product_recommender.update_product_interaction"):
            mock_load.return_value = RelationalProfile()
            await pr.recommend(session, "I need something for meditation", analysis)

        mock_service.search_by_metadata.assert_called_once()
        call_kwargs = mock_service.search_by_metadata.call_args[1]
        assert call_kwargs.get("practices") is not None
        assert "meditation" in call_kwargs["practices"]
