"""Tests that mock implementations satisfy their Protocol interfaces."""
from tests.unit.mocks import MockLLM, MockRAG, MockIntent, MockMemory, MockProduct, MockSafety

from ports.llm import LLMPort
from ports.rag import RAGPort
from ports.intent import IntentPort
from ports.memory import MemoryPort
from ports.product import ProductPort
from ports.safety import SafetyPort


def test_mock_llm_satisfies_protocol():
    assert isinstance(MockLLM(), LLMPort)


def test_mock_rag_satisfies_protocol():
    assert isinstance(MockRAG(), RAGPort)


def test_mock_intent_satisfies_protocol():
    assert isinstance(MockIntent(), IntentPort)


def test_mock_memory_satisfies_protocol():
    assert isinstance(MockMemory(), MemoryPort)


def test_mock_product_satisfies_protocol():
    assert isinstance(MockProduct(), ProductPort)


def test_mock_safety_satisfies_protocol():
    assert isinstance(MockSafety(), SafetyPort)


# ---------------------------------------------------------------------------
# Runtime behavior tests for key mocks
# ---------------------------------------------------------------------------

async def test_mock_llm_generates_response():
    llm = MockLLM(response="Namaste, dear friend.")
    result = await llm.generate_response("I feel lost")
    assert result == "Namaste, dear friend."
    assert llm.call_count == 1
    assert llm.last_query == "I feel lost"


async def test_mock_llm_streams_response():
    llm = MockLLM(response="Be at peace.")
    tokens = []
    async for token in llm.generate_response_stream("help"):
        tokens.append(token)
    assert len(tokens) > 0
    assert "".join(tokens).strip() == "Be at peace."


async def test_mock_intent_returns_analysis():
    intent = MockIntent()
    result = await intent.analyze_intent("I'm stressed about work")
    assert result["intent"] == "EXPRESSING_EMOTION"
    assert result["emotion"] == "anxiety"
    assert intent.call_count == 1


async def test_mock_memory_stores_and_retrieves():
    mem = MockMemory()
    await mem.store_memory("user1", "I lost my job last month")
    await mem.store_memory("user1", "My family is supportive")

    results = await mem.retrieve_relevant_memories("user1", "career stress")
    assert len(results) == 2
    assert "I lost my job last month" in results


async def test_mock_product_searches():
    products = [{"name": "Rudraksha Mala", "price": 599}]
    svc = MockProduct(products=products)
    results = await svc.search_products("mala", life_domain="spiritual")
    assert len(results) == 1
    assert results[0]["name"] == "Rudraksha Mala"


async def test_mock_rag_generates_embeddings():
    import numpy as np
    rag = MockRAG()
    vec = await rag.generate_embeddings("peace and meditation")
    assert vec.shape == (1024,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-5  # Unit normalized


async def test_mock_safety_no_crisis():
    from models.session import SessionState
    safety = MockSafety()
    session = SessionState.__new__(SessionState)
    is_crisis, response = await safety.check_crisis_signals(session, "I feel sad")
    assert is_crisis is False
    assert response is None
