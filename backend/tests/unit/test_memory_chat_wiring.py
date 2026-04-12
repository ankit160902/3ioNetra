"""Unit tests for the Commit 11 wiring: chat router's post-response
memory extraction dispatch + companion_engine preamble's MemoryReader
integration.

These tests verify the INTEGRATION CONTRACTS, not the underlying
services (which are tested in their own suites):

    - chat._dispatch_memory_extraction_post_response — correct gating
      on crisis / missing analysis / anonymous, correct kwargs passed
      through, fire-and-forget semantics.
    - process_message_preamble — calls memory_reader.load_and_retrieve
      when user_id is set, populates user_profile['relational_profile']
      and user_profile['past_memories'], skips reader on crisis / off-
      topic short-circuit paths.
    - llm.service.build_prompt — renders the relational_profile section
      when user_profile has it.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.memory_context import RelationalProfile


# ---------------------------------------------------------------------------
# _dispatch_memory_extraction_post_response
# ---------------------------------------------------------------------------

class TestDispatchHelper:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.session_id = "s1"
        session.turn_count = 3
        session.memory = MagicMock()
        session.memory.user_id = "u1"
        session.conversation_id = None
        return session

    @pytest.mark.asyncio
    async def test_dispatches_for_normal_turn(self, monkeypatch, mock_session):
        from routers import chat

        calls = []

        async def fake_dispatch(**kwargs):
            calls.append(kwargs)

        # Patch the module the helper imports at call-time
        from services import memory_extractor
        monkeypatch.setattr(memory_extractor, "dispatch_memory_extraction", fake_dispatch)

        dispatched = []
        orig_create_task = asyncio.create_task

        def capture(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched.append(task)
            return task

        monkeypatch.setattr(chat.asyncio, "create_task", capture)

        chat._dispatch_memory_extraction_post_response(
            session=mock_session,
            user_message="I lost my father last week",
            assistant_response="I'm so sorry for your loss",
            analysis={"intent": "EXPRESSING_EMOTION", "urgency": "normal"},
        )
        assert len(dispatched) == 1
        await dispatched[0]
        assert len(calls) == 1
        assert calls[0]["user_id"] == "u1"
        assert calls[0]["session_id"] == "s1"
        assert calls[0]["turn_number"] == 3
        assert calls[0]["user_message"] == "I lost my father last week"
        assert calls[0]["assistant_response"] == "I'm so sorry for your loss"
        assert calls[0]["intent_analysis"]["intent"] == "EXPRESSING_EMOTION"

    @pytest.mark.asyncio
    async def test_skips_on_crisis_analysis(self, monkeypatch, mock_session):
        """Crisis turns must never enter the regular memory pipeline —
        crisis_memory_hook handles them on a separate code path."""
        from routers import chat
        from services import memory_extractor

        calls = []

        async def fake_dispatch(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(memory_extractor, "dispatch_memory_extraction", fake_dispatch)
        dispatched = []
        orig_create_task = asyncio.create_task

        def capture(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched.append(task)
            return task

        monkeypatch.setattr(chat.asyncio, "create_task", capture)

        chat._dispatch_memory_extraction_post_response(
            session=mock_session,
            user_message="i dont want to live anymore",
            assistant_response="please call this helpline",
            analysis={"intent": "EXPRESSING_EMOTION", "urgency": "crisis"},
        )
        assert dispatched == []
        assert calls == []

    @pytest.mark.asyncio
    async def test_skips_on_missing_analysis(self, monkeypatch, mock_session):
        """Empty analysis → no dispatch (caller bug safety)."""
        from routers import chat
        from services import memory_extractor

        calls = []

        async def fake_dispatch(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(memory_extractor, "dispatch_memory_extraction", fake_dispatch)

        chat._dispatch_memory_extraction_post_response(
            session=mock_session,
            user_message="anything",
            assistant_response="something",
            analysis={},
        )
        assert calls == []
        chat._dispatch_memory_extraction_post_response(
            session=mock_session,
            user_message="anything",
            assistant_response="something",
            analysis=None,
        )
        assert calls == []


# ---------------------------------------------------------------------------
# process_message_preamble MemoryReader integration
# ---------------------------------------------------------------------------

class TestPreambleReaderWiring:
    @pytest.fixture
    def patched_memory_summary(self, monkeypatch):
        """Stub ConversationMemory.get_memory_summary — it's missing from the
        class (pre-existing bug: method is in RelationalProfile instead).
        The preamble calls it on session.memory, so tests need to provide it."""
        from models.memory_context import ConversationMemory

        def fake_summary(self):
            return ""

        monkeypatch.setattr(
            ConversationMemory, "get_memory_summary", fake_summary, raising=False
        )

    @pytest.mark.asyncio
    async def test_preamble_populates_relational_profile_and_past_memories(
        self, monkeypatch, patched_memory_summary
    ):
        """When user_id is set and reader returns data, the preamble attaches
        it to user_profile for the listening-path return."""
        from services import companion_engine, memory_reader
        from models.session import SessionState
        from models.memory_context import ConversationMemory, UserStory

        # Build a reader result with a populated profile and one episodic memory
        profile = RelationalProfile(
            user_id="u1",
            relational_narrative="A warm seeker on a journey of devotion",
            spiritual_themes=["bhakti"],
        )
        scored_memory = MagicMock()
        scored_memory.memory = {"text": "User is a software engineer"}
        scored_memory.score = 0.8

        read_result = memory_reader.ReadResult(
            profile=profile,
            episodic=[scored_memory],
        )

        async def fake_load_and_retrieve(**kwargs):
            return read_result

        monkeypatch.setattr(
            memory_reader, "load_and_retrieve", fake_load_and_retrieve
        )

        # Stub IntentAgent to return a non-crisis, non-off-topic analysis
        engine = companion_engine.get_companion_engine()

        async def fake_analyze(msg, summary):
            return {
                "intent": "EXPRESSING_EMOTION",
                "emotion": "curiosity",
                "life_domain": "general",
                "urgency": "normal",
                "entities": {},
                "summary": "",
                "needs_direct_answer": False,
                "product_signal": {"intent": "none", "confidence": 0.0, "type_filter": "any",
                                   "search_keywords": [], "max_results": 0, "sensitivity_note": ""},
                "recommend_products": False,
                "product_search_keywords": [],
                "product_rejection": False,
                "query_variants": [],
                "expected_length": "moderate",
                "is_off_topic": False,
                "response_mode": "exploratory",
            }

        monkeypatch.setattr(engine.intent_agent, "analyze_intent", fake_analyze)

        # Stub RAG retrieval inside the preamble so we don't touch the real pipeline
        async def fake_retrieve(*args, **kwargs):
            return [], 0.0

        monkeypatch.setattr(engine, "_retrieve_and_validate", fake_retrieve)

        # Stub product recommender
        engine.product_recommender.recommend = AsyncMock(return_value=[])

        # Session with a user_id
        session = SessionState()
        session.memory = ConversationMemory(story=UserStory())
        session.memory.user_id = "u1"
        session.turn_count = 5

        result = await engine.process_message_preamble(session, "tell me about bhakti")

        # Listening path result — reader output should be on user_profile
        user_profile = result["user_profile"]
        assert "relational_profile" in user_profile
        assert "A warm seeker" in user_profile["relational_profile"]
        assert user_profile["past_memories"] == ["User is a software engineer"]

    @pytest.mark.asyncio
    async def test_preamble_skips_reader_for_anonymous_session(
        self, monkeypatch, patched_memory_summary
    ):
        """Anonymous session (no user_id) should not call memory_reader."""
        from services import companion_engine, memory_reader
        from models.session import SessionState
        from models.memory_context import ConversationMemory, UserStory

        calls = []

        async def fake_load_and_retrieve(**kwargs):
            calls.append(kwargs)
            return memory_reader.ReadResult(
                profile=RelationalProfile(),
                episodic=[],
            )

        monkeypatch.setattr(
            memory_reader, "load_and_retrieve", fake_load_and_retrieve
        )

        engine = companion_engine.get_companion_engine()

        async def fake_analyze(msg, summary):
            return {
                "intent": "EXPRESSING_EMOTION", "emotion": "neutral",
                "life_domain": "general", "urgency": "normal",
                "entities": {}, "summary": "", "needs_direct_answer": False,
                "product_signal": {"intent": "none", "confidence": 0.0, "type_filter": "any",
                                   "search_keywords": [], "max_results": 0, "sensitivity_note": ""},
                "recommend_products": False, "product_search_keywords": [],
                "product_rejection": False, "query_variants": [],
                "expected_length": "moderate", "is_off_topic": False,
                "response_mode": "exploratory",
            }

        monkeypatch.setattr(engine.intent_agent, "analyze_intent", fake_analyze)

        async def fake_retrieve(*args, **kwargs):
            return [], 0.0

        monkeypatch.setattr(engine, "_retrieve_and_validate", fake_retrieve)
        engine.product_recommender.recommend = AsyncMock(return_value=[])

        session = SessionState()
        session.memory = ConversationMemory(story=UserStory())
        session.memory.user_id = ""  # anonymous
        session.turn_count = 5

        await engine.process_message_preamble(session, "tell me about bhakti")
        assert calls == []  # Reader was never called

    @pytest.mark.asyncio
    async def test_preamble_skips_reader_on_crisis_path(
        self, monkeypatch, patched_memory_summary
    ):
        """Crisis short-circuit must fire BEFORE the reader call."""
        from services import companion_engine, memory_reader, crisis_memory_hook
        from models.session import SessionState
        from models.memory_context import ConversationMemory, UserStory

        calls = []

        async def fake_load_and_retrieve(**kwargs):
            calls.append(kwargs)
            return memory_reader.ReadResult(
                profile=RelationalProfile(), episodic=[]
            )

        monkeypatch.setattr(
            memory_reader, "load_and_retrieve", fake_load_and_retrieve
        )

        # Silence the crisis meta-fact dispatch so we don't hit Mongo
        monkeypatch.setattr(
            crisis_memory_hook, "dispatch_crisis_meta_fact", lambda uid: None
        )

        engine = companion_engine.get_companion_engine()

        async def fake_analyze(msg, summary):
            return {
                "intent": "EXPRESSING_EMOTION", "emotion": "despair",
                "life_domain": "general", "urgency": "crisis",
                "entities": {}, "summary": "", "needs_direct_answer": False,
                "product_signal": {"intent": "none", "confidence": 0.0, "type_filter": "any",
                                   "search_keywords": [], "max_results": 0, "sensitivity_note": ""},
                "recommend_products": False, "product_search_keywords": [],
                "product_rejection": False, "query_variants": [],
                "expected_length": "moderate", "is_off_topic": False,
                "response_mode": "presence_first",
            }

        monkeypatch.setattr(engine.intent_agent, "analyze_intent", fake_analyze)

        session = SessionState()
        session.memory = ConversationMemory(story=UserStory())
        session.memory.user_id = "u1"
        session.turn_count = 1

        result = await engine.process_message_preamble(session, "i dont want to live")
        # Reader never called on crisis path
        assert calls == []
        # Crisis short-circuit populated crisis_response
        assert "crisis_response" in result


# ---------------------------------------------------------------------------
# LLM prompt builder renders relational_profile
# ---------------------------------------------------------------------------

class TestPromptRelationalProfileRendering:
    """Source-level inspection of the profile_parts block in _build_prompt.

    Running the full _build_prompt requires a live LLMService with Gemini
    client, prompt_manager, model_router, etc. — too many dependencies for a
    unit test. Since my wiring change is a small block of inline code, the
    cleanest guard against regression is to inspect the source directly for
    the new rendering block.
    """

    def test_relational_profile_block_present_in_source(self):
        """The source must contain the WHO YOU ARE SPEAKING TO header
        guarded by user_profile.get('relational_profile')."""
        import inspect
        from llm import service
        src = inspect.getsource(service)
        assert "user_profile.get('relational_profile')" in src
        assert "WHO YOU ARE SPEAKING TO" in src

    def test_relational_profile_block_renders_above_past_memories(self):
        """Relational profile block must come BEFORE past_memories block
        in the source so the narrative takes precedence in the rendered
        prompt (narrative = mental model, facts = receipts)."""
        import inspect
        from llm import service
        src = inspect.getsource(service)
        rel_idx = src.find("WHO YOU ARE SPEAKING TO")
        past_idx = src.find("RELEVANT PAST CONTEXT")
        assert rel_idx >= 0
        assert past_idx >= 0
        assert rel_idx < past_idx, (
            "relational_profile rendering should appear before past_memories "
            "in the profile_parts builder so narrative renders first"
        )

    def test_relational_profile_block_is_gated_by_key_presence(self):
        """The new block must be INSIDE an `if user_profile.get(...)`
        so empty profiles produce no section."""
        import inspect
        from llm import service
        src = inspect.getsource(service)
        # Find the block and check the surrounding 150 chars for the guard
        idx = src.find("WHO YOU ARE SPEAKING TO")
        assert idx >= 0
        preceding = src[max(0, idx - 200):idx]
        assert "user_profile.get('relational_profile')" in preceding
