"""Integration tests: CompanionEngine with all mock adapters.

Tests full conversation flows through the real CompanionEngine code
with no external services (no Gemini, no Redis, no MongoDB, no ML models).

These tests verify that FSM, signal collection, memory update, and
product recommendation work together correctly after extraction.
"""
import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, AsyncMock

import pytest

from models.session import SessionState, ConversationPhase, IntentType, SignalType
from models.memory_context import ConversationMemory, UserStory
from tests.unit.mocks import MockLLM, MockRAG, MockIntent, MockMemory, MockProduct


# ---------------------------------------------------------------------------
# Mock ModelRouter (needed by CompanionEngine)
# ---------------------------------------------------------------------------

@dataclass
class FakeRoutingDecision:
    tier: str = "STANDARD"
    model_name: str = "gemini-2.0-flash"
    config_override: Dict = None
    reason: str = "test"

    def __post_init__(self):
        if self.config_override is None:
            self.config_override = {}


class MockModelRouter:
    def route(self, intent_analysis=None, phase=None, session=None, has_rag_context=False):
        return FakeRoutingDecision()


# ---------------------------------------------------------------------------
# Load CompanionEngine with mocked dependencies
# ---------------------------------------------------------------------------

def _load_module(name: str, filepath: Path):
    """Load a single module by file path into sys.modules."""
    spec = importlib.util.spec_from_file_location(name, str(filepath))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "services"
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_engine_class():
    """Load CompanionEngine class while mocking heavy deps."""
    backend = Path(__file__).resolve().parents[2]

    # Mock modules that would pull in pymongo, sentence-transformers, etc.
    mock_modules = {
        "services.panchang_service": types.ModuleType("services.panchang_service"),
        "services.cost_tracker": types.ModuleType("services.cost_tracker"),
        "services.retrieval_judge": types.ModuleType("services.retrieval_judge"),
        "services.context_validator": types.ModuleType("services.context_validator"),
        "services.context_synthesizer": types.ModuleType("services.context_synthesizer"),
        "services.response_composer": types.ModuleType("services.response_composer"),
        "services.intent_agent": types.ModuleType("services.intent_agent"),
        "services.memory_service": types.ModuleType("services.memory_service"),
        "services.product_service": types.ModuleType("services.product_service"),
        "services.model_router": types.ModuleType("services.model_router"),
        "services.cache_service": types.ModuleType("services.cache_service"),
        "services.auth_service": types.ModuleType("services.auth_service"),
        "llm.service": types.ModuleType("llm.service"),
        "rag.scoring_utils": types.ModuleType("rag.scoring_utils"),
        "constants": types.ModuleType("constants"),
    }

    mock_modules["services.panchang_service"].get_panchang_service = MagicMock(return_value=None)
    mock_modules["services.cost_tracker"].get_cost_tracker = MagicMock()
    mock_modules["services.cost_tracker"].extract_tokens_from_response = MagicMock(return_value=(0, 0))
    mock_modules["services.retrieval_judge"].get_retrieval_judge = MagicMock()
    mock_modules["services.intent_agent"].get_intent_agent = MagicMock()
    mock_modules["services.memory_service"].get_memory_service = MagicMock()
    mock_modules["services.product_service"].get_product_service = MagicMock()
    mock_modules["services.model_router"].get_model_router = MagicMock()
    mock_modules["services.auth_service"].get_mongo_client = MagicMock(return_value=None)
    mock_modules["llm.service"].get_llm_service = MagicMock()
    mock_modules["rag.scoring_utils"].get_doc_score = MagicMock(return_value=0.5)
    mock_modules["constants"].TRIVIAL_MESSAGES = set()

    # Create a proper services package
    svc_pkg = types.ModuleType("services")
    svc_pkg.__path__ = [str(backend / "services")]
    mock_modules["services"] = svc_pkg

    saved = {}
    for name in mock_modules:
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mock_modules[name]

    # Also clear cached extracted modules
    for name in ["services.companion_engine", "services.conversation_fsm",
                 "services.memory_updater", "services.signal_collector",
                 "services.product_recommender", "services.profile_builder"]:
        sys.modules.pop(name, None)

    try:
        # Load extracted services in dependency order
        _load_module("services.signal_collector", backend / "services" / "signal_collector.py")
        _load_module("services.memory_updater", backend / "services" / "memory_updater.py")
        _load_module("services.conversation_fsm", backend / "services" / "conversation_fsm.py")
        _load_module("services.product_recommender", backend / "services" / "product_recommender.py")

        pb_mod = types.ModuleType("services.profile_builder")
        pb_mod.build_user_profile = MagicMock(return_value={"name": "Test"})
        sys.modules["services.profile_builder"] = pb_mod

        engine_mod = _load_module("services.companion_engine", backend / "services" / "companion_engine.py")
        return engine_mod.CompanionEngine
    finally:
        for name, orig in saved.items():
            if orig is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = orig


def _make_engine(intent_overrides=None):
    """Create a CompanionEngine with all mocks injected."""
    CompanionEngine = _load_engine_class()

    llm = MockLLM(response="May peace be with you, dear friend.")
    intent = MockIntent(analysis=intent_overrides) if intent_overrides else MockIntent()
    memory = MockMemory()
    product = MockProduct()

    engine = CompanionEngine(
        rag_pipeline=MockRAG(),
        llm=llm,
        intent_agent=intent,
        memory_service=memory,
        product_service=product,
        panchang=MagicMock(),
        model_router=MockModelRouter(),
    )
    return engine, llm, intent, memory, product


def _make_session(turn_count=0):
    s = SessionState()
    s.turn_count = turn_count
    s.memory = ConversationMemory(story=UserStory())
    return s


# ---------------------------------------------------------------------------
# Integration: generate_response_stream (simplified streaming path)
# ---------------------------------------------------------------------------

class TestStreamFlow:
    async def test_listening_phase_streams_tokens(self):
        """First turn with expressing emotion should stay in LISTENING and stream."""
        engine, llm, intent, _, _ = _make_engine()
        session = _make_session(turn_count=1)

        chunks = []
        async for chunk in engine.generate_response_stream(session, "I feel anxious about my exams"):
            chunks.append(chunk)

        # Should have control chunk + token chunks
        assert len(chunks) >= 2
        assert chunks[0]["type"] == "control"
        assert chunks[0]["is_ready_for_wisdom"] is False
        assert any(c["type"] == "token" for c in chunks)

    async def test_explicit_request_triggers_guidance(self):
        """Panchang request should immediately trigger guidance."""
        engine, _, intent, _, _ = _make_engine({
            "intent": IntentType.ASKING_PANCHANG,
            "emotion": "neutral",
            "life_domain": "spiritual",
            "entities": {},
            "urgency": "normal",
            "summary": "Asking about today's panchang",
            "needs_direct_answer": True,
            "recommend_products": False,
            "product_search_keywords": [],
            "product_rejection": False,
            "query_variants": [],
        })
        session = _make_session(turn_count=1)

        chunks = []
        async for chunk in engine.generate_response_stream(session, "What is today's tithi?"):
            chunks.append(chunk)

        assert chunks[0]["type"] == "control"
        assert chunks[0]["is_ready_for_wisdom"] is True

    async def test_closure_intent_stays_not_ready(self):
        """Closure intent should not trigger guidance."""
        engine, _, _, _, _ = _make_engine({
            "intent": IntentType.CLOSURE,
            "emotion": "gratitude",
            "life_domain": "unknown",
            "entities": {},
            "urgency": "low",
            "summary": "Saying goodbye",
            "needs_direct_answer": False,
            "recommend_products": False,
            "product_search_keywords": [],
            "product_rejection": False,
            "query_variants": [],
        })
        session = _make_session(turn_count=5)

        chunks = []
        async for chunk in engine.generate_response_stream(session, "Thank you, bye"):
            chunks.append(chunk)

        assert chunks[0]["is_ready_for_wisdom"] is False


# ---------------------------------------------------------------------------
# Integration: signal collection works with extracted services
# ---------------------------------------------------------------------------

class TestSignalIntegration:
    async def test_signals_collected_after_stream(self):
        """After streaming, session should have signals from intent analysis."""
        engine, _, _, _, _ = _make_engine()
        session = _make_session(turn_count=1)

        async for _ in engine.generate_response_stream(session, "I'm stressed about work"):
            pass

        # MockIntent returns emotion="anxiety" and life_domain="career"
        assert session.memory.story.emotional_state == "anxiety"
        assert session.memory.story.life_area == "career"
        assert SignalType.EMOTION in session.signals_collected
        assert SignalType.LIFE_DOMAIN in session.signals_collected


# ---------------------------------------------------------------------------
# Integration: memory updater works through engine
# ---------------------------------------------------------------------------

class TestMemoryUpdateIntegration:
    async def test_turn_topics_populated(self):
        """_update_memory should run and populate turn_topics."""
        engine, _, _, _, _ = _make_engine()
        session = _make_session(turn_count=1)

        chunks = []
        async for chunk in engine.generate_response_stream(session, "I want to buy a rudraksha mala"):
            chunks.append(chunk)

        # Memory updater should have detected product inquiry
        # The control chunk should have turn_topics
        control = chunks[0]
        assert "turn_topics" in control


# ---------------------------------------------------------------------------
# Integration: multi-turn conversation
# ---------------------------------------------------------------------------

class TestMultiTurnConversation:
    async def test_three_turn_flow(self):
        """Simulate greeting → emotion → guidance ask."""
        # Turn 1: Greeting
        engine, llm, intent, _, _ = _make_engine({
            "intent": IntentType.GREETING,
            "emotion": "neutral",
            "life_domain": "unknown",
            "entities": {},
            "urgency": "low",
            "summary": "User greeting",
            "needs_direct_answer": False,
            "recommend_products": False,
            "product_search_keywords": [],
            "product_rejection": False,
            "query_variants": [],
        })
        session = _make_session(turn_count=1)

        chunks = []
        async for chunk in engine.generate_response_stream(session, "Namaste"):
            chunks.append(chunk)
        assert chunks[0]["is_ready_for_wisdom"] is False

        # Turn 2: Express emotion
        intent._analysis = {
            "intent": IntentType.EXPRESSING_EMOTION,
            "emotion": "anxiety",
            "life_domain": "career",
            "entities": {},
            "urgency": "normal",
            "summary": "Stressed about deadlines",
            "needs_direct_answer": False,
            "recommend_products": False,
            "product_search_keywords": [],
            "product_rejection": False,
            "query_variants": [],
        }
        session.turn_count = 2
        session.conversation_history.append({"role": "user", "content": "I'm stressed about work deadlines"})

        chunks = []
        async for chunk in engine.generate_response_stream(session, "I'm stressed about work deadlines"):
            chunks.append(chunk)
        assert chunks[0]["is_ready_for_wisdom"] is False  # Still listening at turn 2

        # Turn 3: Direct guidance ask with enough turns
        intent._analysis = {
            "intent": IntentType.SEEKING_GUIDANCE,
            "emotion": "anxiety",
            "life_domain": "career",
            "entities": {},
            "urgency": "normal",
            "summary": "Asking for guidance on stress",
            "needs_direct_answer": True,
            "recommend_products": False,
            "product_search_keywords": [],
            "product_rejection": False,
            "query_variants": [],
        }
        session.turn_count = 3
        session.conversation_history.append({"role": "user", "content": "What should I do about this stress?"})

        chunks = []
        async for chunk in engine.generate_response_stream(session, "What should I do about this stress?"):
            chunks.append(chunk)
        assert chunks[0]["is_ready_for_wisdom"] is True  # Now ready!
