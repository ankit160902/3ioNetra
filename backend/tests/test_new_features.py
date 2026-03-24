"""
Comprehensive unit tests for new multi-model features.

Tests: Model Router, Cost Tracker, Provider Abstractions, Model Registry.
All tests use mocks — no external services needed.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import fields

# Ensure backend is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ══════════════════════════════════════════════════════════════════
# Test Group 1: Model Router (15 tests)
# ══════════════════════════════════════════════════════════════════

class TestModelRouter:
    """Tests for services/model_router.py routing decisions."""

    def _make_session(self, turn_count=1, signals=None, history=None, phase="listening"):
        from models.session import SessionState, ConversationPhase, SignalType, Signal
        session = SessionState()
        session.turn_count = turn_count
        session.phase = ConversationPhase(phase)
        if signals:
            session.signals_collected = signals
        if history:
            session.conversation_history = history
        return session

    def test_routing_disabled_returns_premium(self):
        """MODEL_ROUTING_ENABLED=False → PREMIUM tier with default model."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = False
            mock_settings.GEMINI_MODEL = "gemini-2.5-pro"
            mock_settings.MODEL_PREMIUM = "gemini-2.5-pro"

            session = self._make_session()
            result = route({"intent": "GREETING"}, ConversationPhase.LISTENING, session)

            assert result.tier == ModelTier.PREMIUM
            assert result.reason == "routing_disabled"

    def test_crisis_urgency_returns_premium(self):
        """urgency='crisis' → PREMIUM tier."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_PREMIUM = "gemini-2.5-pro"

            session = self._make_session()
            result = route(
                {"intent": "SEEKING_GUIDANCE", "urgency": "crisis"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.PREMIUM
            assert "crisis" in result.reason

    def test_greeting_returns_economy(self):
        """intent=GREETING → ECONOMY tier."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_ECONOMY = "gemini-2.0-flash"

            session = self._make_session()
            result = route(
                {"intent": "GREETING", "urgency": "normal"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.ECONOMY
            assert result.reason == "greeting"

    def test_closure_returns_economy(self):
        """intent=CLOSURE → ECONOMY tier."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_ECONOMY = "gemini-2.0-flash"

            session = self._make_session()
            result = route(
                {"intent": "CLOSURE", "urgency": "normal"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.ECONOMY
            assert result.reason == "closure"

    def test_listening_short_msg_returns_economy(self):
        """LISTENING phase + <8 words → ECONOMY."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_ECONOMY = "gemini-2.0-flash"

            session = self._make_session(
                history=[{"role": "user", "content": "hello how are you"}]
            )
            result = route(
                {"intent": "OTHER", "urgency": "normal"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.ECONOMY
            assert "listening_short" in result.reason

    def test_asking_info_direct_returns_standard(self):
        """ASKING_INFO + needs_direct_answer → STANDARD."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_STANDARD = "gemini-2.5-pro"

            session = self._make_session(
                history=[{"role": "user", "content": "this is a longer question about detailed spiritual practices and their meaning"}]
            )
            result = route(
                {"intent": "ASKING_INFO", "needs_direct_answer": True, "urgency": "normal"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.STANDARD
            assert "asking_info" in result.reason

    def test_expressing_emotion_returns_standard(self):
        """EXPRESSING_EMOTION → STANDARD."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_STANDARD = "gemini-2.5-pro"

            session = self._make_session(
                history=[{"role": "user", "content": "I am feeling very anxious about my future and career prospects right now"}]
            )
            result = route(
                {"intent": "EXPRESSING_EMOTION", "urgency": "normal"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.STANDARD
            assert "expressing_emotion" in result.reason

    def test_asking_panchang_returns_economy(self):
        """ASKING_PANCHANG → ECONOMY."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_ECONOMY = "gemini-2.0-flash"

            session = self._make_session(
                history=[{"role": "user", "content": "what is today's panchang and tithi and nakshatra info please"}]
            )
            result = route(
                {"intent": "ASKING_PANCHANG", "urgency": "normal"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.ECONOMY
            assert "panchang" in result.reason

    def test_product_search_returns_economy(self):
        """PRODUCT_SEARCH → ECONOMY."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_ECONOMY = "gemini-2.0-flash"

            session = self._make_session(
                history=[{"role": "user", "content": "show me some rudraksha mala products from the store please"}]
            )
            result = route(
                {"intent": "PRODUCT_SEARCH", "urgency": "normal"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.ECONOMY
            assert "product_search" in result.reason

    def test_guidance_rag_complex_premium(self):
        """GUIDANCE phase + RAG + high complexity → PREMIUM."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase, SignalType, Signal

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_PREMIUM = "gemini-2.5-pro"

            signals = {
                SignalType.EMOTION: Signal(SignalType.EMOTION, "sad"),
                SignalType.LIFE_DOMAIN: Signal(SignalType.LIFE_DOMAIN, "family"),
                SignalType.USER_GOAL: Signal(SignalType.USER_GOAL, "peace"),
            }
            session = self._make_session(
                turn_count=6, signals=signals,
                history=[{"role": "user", "content": f"msg {i}"} for i in range(10)],
            )
            result = route(
                {"intent": "SEEKING_GUIDANCE", "urgency": "high", "emotion": "sad"},
                ConversationPhase.GUIDANCE, session, has_rag_context=True,
            )

            assert result.tier == ModelTier.PREMIUM

    def test_guidance_rag_simple_standard(self):
        """GUIDANCE phase + RAG + low complexity → STANDARD."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_STANDARD = "gemini-2.5-pro"

            session = self._make_session(turn_count=2)
            result = route(
                {"intent": "ASKING_INFO", "urgency": "normal", "emotion": "neutral"},
                ConversationPhase.GUIDANCE, session, has_rag_context=True,
            )

            assert result.tier == ModelTier.STANDARD

    def test_seeking_guidance_complex_premium(self):
        """SEEKING_GUIDANCE + complexity>=4 → PREMIUM."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase, SignalType, Signal

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_PREMIUM = "gemini-2.5-pro"

            signals = {
                SignalType.EMOTION: Signal(SignalType.EMOTION, "anxious"),
                SignalType.LIFE_DOMAIN: Signal(SignalType.LIFE_DOMAIN, "career"),
                SignalType.TRIGGER: Signal(SignalType.TRIGGER, "job loss"),
            }
            session = self._make_session(
                turn_count=6, signals=signals,
                history=[{"role": "user", "content": f"msg {i}"} for i in range(10)],
            )
            result = route(
                {"intent": "SEEKING_GUIDANCE", "urgency": "high", "emotion": "anxious"},
                ConversationPhase.LISTENING, session, has_rag_context=True,
            )

            assert result.tier == ModelTier.PREMIUM

    def test_seeking_guidance_simple_standard(self):
        """SEEKING_GUIDANCE + complexity<4 → STANDARD."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_STANDARD = "gemini-2.5-pro"

            # Use a long enough message to avoid the listening_short_message path
            session = self._make_session(
                turn_count=1,
                history=[{"role": "user", "content": "please guide me on how to deal with stress in my daily spiritual practice"}],
            )
            result = route(
                {"intent": "SEEKING_GUIDANCE", "urgency": "normal", "emotion": "neutral"},
                ConversationPhase.LISTENING, session,
            )

            assert result.tier == ModelTier.STANDARD

    def test_default_returns_standard(self):
        """Unknown/OTHER intent → STANDARD."""
        from services.model_router import route, ModelTier
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = True
            mock_settings.MODEL_STANDARD = "gemini-2.5-pro"

            session = self._make_session(
                history=[{"role": "user", "content": "this is some random long text that does not match any category at all"}]
            )
            result = route(
                {"intent": "OTHER", "urgency": "normal"},
                ConversationPhase.GUIDANCE, session,
            )

            assert result.tier == ModelTier.STANDARD
            assert result.reason == "default"

    def test_routing_decision_has_all_fields(self):
        """RoutingDecision has tier, model_name, config_override, reason."""
        from services.model_router import route
        from models.session import ConversationPhase

        with patch("services.model_router.settings") as mock_settings:
            mock_settings.MODEL_ROUTING_ENABLED = False
            mock_settings.GEMINI_MODEL = "gemini-2.5-pro"
            mock_settings.MODEL_PREMIUM = "gemini-2.5-pro"

            session = self._make_session()
            result = route({"intent": "GREETING"}, ConversationPhase.LISTENING, session)

            assert hasattr(result, "tier")
            assert hasattr(result, "model_name")
            assert hasattr(result, "config_override")
            assert hasattr(result, "reason")
            assert result.model_name is not None
            assert isinstance(result.config_override, dict)
            assert len(result.reason) > 0


# ══════════════════════════════════════════════════════════════════
# Test Group 2: Cost Tracker (6 tests)
# ══════════════════════════════════════════════════════════════════

class TestCostTracker:
    """Tests for services/cost_tracker.py."""

    def test_estimate_cost_known_model(self):
        """Verify math for gemini-2.5-pro."""
        from services.cost_tracker import estimate_cost

        cost = estimate_cost("gemini-2.5-pro", input_tokens=1000, output_tokens=500)
        # input: 1000/1000 * 0.00125 = 0.00125
        # output: 500/1000 * 0.01 = 0.005
        expected = 0.00125 + 0.005
        assert abs(cost - expected) < 1e-9

    def test_estimate_cost_unknown_model_uses_default(self):
        """Unknown model falls back to default pricing."""
        from services.cost_tracker import estimate_cost

        cost = estimate_cost("some-unknown-model", input_tokens=1000, output_tokens=1000)
        # Default: input=0.001, output=0.005
        expected = 1.0 * 0.001 + 1.0 * 0.005
        assert abs(cost - expected) < 1e-9

    def test_extract_tokens_from_response(self):
        """Test with and without usage_metadata."""
        from services.cost_tracker import extract_tokens_from_response

        # With usage
        mock_response = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 150
        mock_response.usage_metadata.candidates_token_count = 80
        inp, out = extract_tokens_from_response(mock_response)
        assert inp == 150
        assert out == 80

        # Without usage
        mock_no_usage = MagicMock(spec=[])  # no attributes
        inp, out = extract_tokens_from_response(mock_no_usage)
        assert inp == 0
        assert out == 0

    def test_log_disabled_no_crash(self):
        """enabled=False doesn't crash when logging."""
        from services.cost_tracker import CostTracker

        with patch("services.cost_tracker.settings") as mock_settings:
            mock_settings.MODEL_COST_TRACKING_ENABLED = False
            tracker = CostTracker()
            # Should not raise
            tracker.log(
                session_id="test-123",
                model_name="gemini-2.0-flash",
                tier="economy",
                input_tokens=100,
                output_tokens=50,
                intent="GREETING",
                phase="listening",
            )

    def test_log_enabled_no_db_no_crash(self):
        """enabled=True, no MongoDB, no crash."""
        from services.cost_tracker import CostTracker

        with patch("services.cost_tracker.settings") as mock_settings:
            mock_settings.MODEL_COST_TRACKING_ENABLED = True
            tracker = CostTracker()
            tracker.enabled = True
            # Should not raise even without MongoDB
            tracker.log(
                session_id="test-456",
                model_name="gemini-2.5-pro",
                tier="premium",
                input_tokens=500,
                output_tokens=200,
                intent="SEEKING_GUIDANCE",
                phase="guidance",
            )

    def test_request_cost_record_fields(self):
        """All dataclass fields are valid."""
        from services.cost_tracker import RequestCostRecord
        from dataclasses import fields as dc_fields

        field_names = {f.name for f in dc_fields(RequestCostRecord)}
        expected = {
            "timestamp", "session_id", "model_name", "tier",
            "input_tokens", "output_tokens", "estimated_cost_usd",
            "intent", "phase",
        }
        assert field_names == expected


# ══════════════════════════════════════════════════════════════════
# Test Group 3: Provider Abstractions (6 tests)
# ══════════════════════════════════════════════════════════════════

class TestProviderAbstractions:
    """Tests for llm/providers/base.py."""

    def test_llm_response_dataclass(self):
        """All fields accessible on LLMResponse."""
        from llm.providers.base import LLMResponse

        resp = LLMResponse(
            text="Namaste",
            model="gemini-2.5-pro",
            provider="gemini",
            latency_ms=123.4,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.002,
        )
        assert resp.text == "Namaste"
        assert resp.model == "gemini-2.5-pro"
        assert resp.provider == "gemini"
        assert resp.latency_ms == 123.4
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.cost_usd == 0.002

    def test_intent_response_dataclass(self):
        """IntentResponse parse_success True/False."""
        from llm.providers.base import IntentResponse

        # Success case
        resp_ok = IntentResponse(
            raw_json={"intent": "GREETING"},
            model="gemini-2.0-flash",
            provider="gemini",
            latency_ms=50.0,
            input_tokens=80,
            output_tokens=20,
            cost_usd=0.0001,
            parse_success=True,
        )
        assert resp_ok.parse_success is True

        # Failure case
        resp_fail = IntentResponse(
            raw_json={},
            model="gemini-2.0-flash",
            provider="gemini",
            latency_ms=50.0,
            input_tokens=80,
            output_tokens=0,
            cost_usd=0.0001,
            parse_success=False,
            raw_text="unparseable garbage",
        )
        assert resp_fail.parse_success is False
        assert resp_fail.raw_text == "unparseable garbage"

    def test_calculate_cost_math(self):
        """Verify _calculate_cost() on both base classes."""
        from llm.providers.base import ResponseProvider, IntentProvider

        class DummyResponse(ResponseProvider):
            @property
            def name(self): return "test"
            @property
            def cost_per_1k_input(self): return 0.003
            @property
            def cost_per_1k_output(self): return 0.015
            async def generate(self, **kwargs): pass

        class DummyIntent(IntentProvider):
            @property
            def name(self): return "test"
            @property
            def cost_per_1k_input(self): return 0.001
            @property
            def cost_per_1k_output(self): return 0.005
            async def classify(self, prompt): pass

        rp = DummyResponse()
        cost = rp._calculate_cost(2000, 1000)
        # 2000/1000 * 0.003 + 1000/1000 * 0.015 = 0.006 + 0.015 = 0.021
        assert abs(cost - 0.021) < 1e-9

        ip = DummyIntent()
        cost = ip._calculate_cost(1000, 500)
        # 1.0 * 0.001 + 0.5 * 0.005 = 0.001 + 0.0025 = 0.0035
        assert abs(cost - 0.0035) < 1e-9

    def test_response_provider_is_abstract(self):
        """Can't instantiate ResponseProvider directly."""
        from llm.providers.base import ResponseProvider

        with pytest.raises(TypeError):
            ResponseProvider()

    def test_intent_provider_is_abstract(self):
        """Can't instantiate IntentProvider directly."""
        from llm.providers.base import IntentProvider

        with pytest.raises(TypeError):
            IntentProvider()

    def test_build_prompt_on_base_class(self):
        """After dedup, _build_prompt works on base class."""
        from llm.providers.base import ResponseProvider

        # Call the static method directly on the base class
        prompt = ResponseProvider._build_prompt(
            query="How to meditate?",
            phase_instructions="Listen carefully.",
            user_profile={"name": "Ankit", "age": "30"},
        )

        assert "How to meditate?" in prompt
        assert "Listen carefully." in prompt
        assert "Ankit" in prompt
        assert "WHO YOU ARE SPEAKING TO" in prompt
        assert "Your response:" in prompt

        # Without user_profile
        prompt_no_profile = ResponseProvider._build_prompt(
            query="Namaste",
            phase_instructions="Greet warmly.",
            user_profile=None,
        )
        assert "Namaste" in prompt_no_profile
        assert "WHO YOU ARE SPEAKING TO" not in prompt_no_profile


# ══════════════════════════════════════════════════════════════════
# Test Group 4: Model Registry (5 tests)
# ══════════════════════════════════════════════════════════════════

class TestModelRegistry:
    """Tests for rag/model_registry.py."""

    def test_embedding_models_registry_has_entries(self):
        """EMBEDDING_MODELS has >=6 entries."""
        from rag.model_registry import EMBEDDING_MODELS

        assert len(EMBEDDING_MODELS) >= 6

    def test_reranker_models_registry_has_entries(self):
        """RERANKER_MODELS has >=5 entries."""
        from rag.model_registry import RERANKER_MODELS

        assert len(RERANKER_MODELS) >= 5

    def test_get_embedding_backend_invalid_raises(self):
        """ValueError for unknown embedding model name."""
        from rag.model_registry import get_embedding_backend

        with pytest.raises(ValueError, match="Unknown embedding model"):
            get_embedding_backend("nonexistent-model-xyz")

    def test_get_reranker_backend_invalid_raises(self):
        """ValueError for unknown reranker model name."""
        from rag.model_registry import get_reranker_backend

        with pytest.raises(ValueError, match="Unknown reranker model"):
            get_reranker_backend("nonexistent-reranker-xyz")

    def test_cross_encoder_has_predict_and_rerank(self):
        """CrossEncoderBackend has both predict() and rerank() for duck-typing."""
        from rag.model_registry import CrossEncoderBackend

        backend = CrossEncoderBackend("some-model")
        assert hasattr(backend, "predict")
        assert hasattr(backend, "rerank")
        assert callable(backend.predict)
        assert callable(backend.rerank)
