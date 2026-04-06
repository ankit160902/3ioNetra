"""Live smoke test — verifies the refactored backend works with real services.

Requirements: GEMINI_API_KEY set in .env, Redis running, MongoDB accessible.
Run: cd backend && source .venv/bin/activate && python tests/live_smoke_test.py
"""
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("live_smoke_test")


async def test_health():
    """Test 1: Import and initialize services."""
    logger.info("=" * 60)
    logger.info("TEST 1: Health check — import and initialize")
    logger.info("=" * 60)

    from config import settings
    logger.info(f"  Gemini model: {settings.GEMINI_MODEL}")
    logger.info(f"  Fast model: {settings.GEMINI_FAST_MODEL}")

    # RAG Pipeline
    from rag.pipeline import RAGPipeline
    rag = RAGPipeline()
    t0 = time.perf_counter()
    await rag.initialize()
    t1 = time.perf_counter()
    logger.info(f"  RAG initialized: available={rag.available} ({(t1-t0)*1000:.0f}ms)")
    assert rag.available, "RAG pipeline failed to initialize"

    # LLM Service
    from llm.service import get_llm_service
    llm = get_llm_service()
    logger.info(f"  LLM available: {llm.available}")
    assert llm.available, "LLM service not available (check GEMINI_API_KEY)"

    # Session Manager
    from services.session_manager import get_session_manager
    sm = get_session_manager()
    logger.info(f"  Session manager: {type(sm).__name__}")

    logger.info("  PASS: All services initialized\n")
    return rag, llm


async def test_intent_agent(message="I feel anxious about my exams"):
    """Test 2: IntentAgent with Pydantic validation."""
    logger.info("=" * 60)
    logger.info("TEST 2: IntentAgent — real Gemini classification")
    logger.info("=" * 60)

    from services.intent_agent import get_intent_agent
    agent = get_intent_agent()

    t0 = time.perf_counter()
    result = await agent.analyze_intent(message)
    t1 = time.perf_counter()

    logger.info(f"  Message: '{message}'")
    logger.info(f"  Intent: {result.get('intent')}")
    logger.info(f"  Emotion: {result.get('emotion')}")
    logger.info(f"  Life domain: {result.get('life_domain')}")
    logger.info(f"  Needs direct answer: {result.get('needs_direct_answer')}")
    logger.info(f"  Latency: {(t1-t0)*1000:.0f}ms")

    assert result.get("intent") is not None, "Intent is None"
    assert result.get("emotion") is not None, "Emotion is None"
    logger.info("  PASS: IntentAgent works with Pydantic validation\n")
    return result


async def test_conversation_fsm():
    """Test 3: ConversationFSM state transitions."""
    logger.info("=" * 60)
    logger.info("TEST 3: ConversationFSM — state machine transitions")
    logger.info("=" * 60)

    from services.conversation_fsm import ConversationFSM
    from models.session import SessionState, IntentType
    from models.memory_context import ConversationMemory, UserStory

    # Simulate: turn 1 emotion → listening, turn 3 guidance ask → guidance
    session = SessionState()
    session.memory = ConversationMemory(story=UserStory())

    # Turn 1: Express emotion
    session.turn_count = 1
    fsm = ConversationFSM(session)
    is_ready, trigger = fsm.evaluate(
        {"intent": IntentType.EXPRESSING_EMOTION, "emotion": "anxiety"},
        ["Anxiety & Fear"]
    )
    logger.info(f"  Turn 1: is_ready={is_ready}, trigger={trigger}")
    assert not is_ready, "Should NOT be ready at turn 1"

    # Turn 3: Seek guidance
    session.turn_count = 3
    fsm2 = ConversationFSM(session)
    is_ready, trigger = fsm2.evaluate(
        {"intent": IntentType.SEEKING_GUIDANCE, "emotion": "anxiety", "needs_direct_answer": True},
        []
    )
    logger.info(f"  Turn 3: is_ready={is_ready}, trigger={trigger}")
    assert is_ready, "Should be ready at turn 3 with SEEKING_GUIDANCE"

    logger.info("  PASS: FSM transitions work correctly\n")


async def test_memory_updater():
    """Test 4: Extracted MemoryUpdater."""
    logger.info("=" * 60)
    logger.info("TEST 4: MemoryUpdater — keyword detection")
    logger.info("=" * 60)

    from services.memory_updater import update_memory
    from models.session import SessionState
    from models.memory_context import ConversationMemory, UserStory

    session = SessionState()
    session.memory = ConversationMemory(story=UserStory())

    topics = update_memory(session.memory, session, "I want to buy a rudraksha mala for daily japa meditation")
    logger.info(f"  Message: 'I want to buy a rudraksha mala for daily japa meditation'")
    logger.info(f"  Topics: {topics}")
    logger.info(f"  Emotion: {session.memory.story.emotional_state}")
    logger.info(f"  Readiness: {session.memory.readiness_for_wisdom:.2f}")

    assert "Product Inquiry" in topics, f"Expected 'Product Inquiry' in {topics}"
    assert session.memory.readiness_for_wisdom > 0, "Readiness should be boosted"
    logger.info("  PASS: MemoryUpdater detects intents correctly\n")


async def test_product_recommender():
    """Test 5: Extracted ProductRecommender with real ProductService."""
    logger.info("=" * 60)
    logger.info("TEST 5: ProductRecommender — real product search")
    logger.info("=" * 60)

    from services.product_recommender import ProductRecommender
    from services.product_service import get_product_service
    from models.session import SessionState, IntentType
    from models.memory_context import ConversationMemory, UserStory

    ps = get_product_service()
    recommender = ProductRecommender(ps)

    session = SessionState()
    session.turn_count = 3
    session.memory = ConversationMemory(story=UserStory())

    analysis = {
        "intent": IntentType.PRODUCT_SEARCH,
        "emotion": "neutral",
        "life_domain": "spiritual",
        "entities": {},
        "urgency": "normal",
        "recommend_products": False,
        "product_search_keywords": ["rudraksha", "mala"],
        "product_rejection": False,
    }

    t0 = time.perf_counter()
    products = await recommender.recommend(
        session, "show me rudraksha malas", analysis,
        ["Product Inquiry"], is_ready_for_wisdom=True, life_domain="spiritual"
    )
    t1 = time.perf_counter()

    logger.info(f"  Products found: {len(products)}")
    for p in products[:3]:
        logger.info(f"    - {p.get('name', 'N/A')} (Rs {p.get('amount', '?')})")
    logger.info(f"  Latency: {(t1-t0)*1000:.0f}ms")

    # Products may be empty if MongoDB has no products loaded — that's OK
    logger.info(f"  PASS: ProductRecommender executed without errors (found {len(products)} products)\n")


async def test_full_companion_engine(rag):
    """Test 6: Full CompanionEngine with real services — generate_response_stream."""
    logger.info("=" * 60)
    logger.info("TEST 6: CompanionEngine — full conversation turn (LIVE)")
    logger.info("=" * 60)

    from services.companion_engine import CompanionEngine
    from models.session import SessionState
    from models.memory_context import ConversationMemory, UserStory

    engine = CompanionEngine(rag_pipeline=rag)

    session = SessionState()
    session.turn_count = 1
    session.memory = ConversationMemory(story=UserStory())
    session.conversation_history = []

    message = "I've been feeling really stressed about my career lately"

    t0 = time.perf_counter()
    chunks = []
    async for chunk in engine.generate_response_stream(session, message):
        chunks.append(chunk)
    t1 = time.perf_counter()

    control_chunk = chunks[0] if chunks else {}
    token_chunks = [c for c in chunks if c.get("type") == "token"]
    full_response = "".join(c.get("content", "") for c in token_chunks)

    logger.info(f"  Message: '{message}'")
    logger.info(f"  Phase: {control_chunk.get('phase', 'N/A')}")
    logger.info(f"  Is ready: {control_chunk.get('is_ready_for_wisdom', 'N/A')}")
    logger.info(f"  Tokens streamed: {len(token_chunks)}")
    logger.info(f"  Response preview: '{full_response[:150]}...'")
    logger.info(f"  Total latency: {(t1-t0)*1000:.0f}ms")

    assert len(chunks) >= 2, "Expected at least control + token chunks"
    assert control_chunk.get("is_ready_for_wisdom") is False, "Turn 1 should be LISTENING"
    assert len(full_response) > 10, "Response should have content"
    logger.info("  PASS: Full conversation turn works end-to-end\n")


async def test_observability():
    """Test 7: Observability — correlation IDs work."""
    logger.info("=" * 60)
    logger.info("TEST 7: Observability — correlation ID propagation")
    logger.info("=" * 60)

    from services.observability import set_correlation_id, get_correlation_id

    cid = set_correlation_id()
    assert len(cid) == 12
    assert get_correlation_id() == cid
    logger.info(f"  Correlation ID: {cid}")
    logger.info("  PASS: Observability works\n")


async def main():
    logger.info("\n" + "=" * 60)
    logger.info("3ioNetra LIVE SMOKE TEST — Refactored Backend")
    logger.info("Testing with REAL Gemini API, Redis, MongoDB")
    logger.info("=" * 60 + "\n")

    passed = 0
    failed = 0
    errors = []

    tests = [
        ("Health Check", test_health),
        ("IntentAgent", lambda: test_intent_agent()),
        ("ConversationFSM", test_conversation_fsm),
        ("MemoryUpdater", test_memory_updater),
        ("ProductRecommender", test_product_recommender),
        ("Observability", test_observability),
    ]

    rag = None
    for name, test_fn in tests:
        try:
            result = await test_fn()
            if name == "Health Check":
                rag = result[0]  # RAG pipeline for later tests
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((name, str(e)))
            logger.error(f"  FAIL: {name} — {e}\n")

    # Test 6 depends on RAG
    if rag:
        try:
            await test_full_companion_engine(rag)
            passed += 1
        except Exception as e:
            failed += 1
            errors.append(("Full CompanionEngine", str(e)))
            logger.error(f"  FAIL: Full CompanionEngine — {e}\n")
    else:
        logger.warning("  SKIP: Full CompanionEngine (RAG not available)\n")

    # Summary
    logger.info("=" * 60)
    logger.info(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
    logger.info("=" * 60)
    if errors:
        for name, err in errors:
            logger.error(f"  FAILED: {name} — {err}")
    else:
        logger.info("  ALL TESTS PASSED")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
