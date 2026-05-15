"""Unit tests for MemoryExtractor — the Gemini call #1 wrapper that extracts
memory-worthy facts from a single user turn.

All tests use a mocked LLM service — no real Gemini calls. The actual Gemini
classification behavior is exercised by test_memory_live.py (opt-in).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.llm_schemas import ExtractionResult


@pytest.fixture
def mock_llm_service():
    """Mock LLM service with a patched generate_response returning structured JSON."""
    svc = MagicMock()
    svc.available = True
    # The extractor will call a method that returns the raw JSON string from Gemini.
    svc.complete_json = AsyncMock()
    return svc


@pytest.fixture
def mock_prompt_manager():
    """Mock prompt manager returning the extract template."""
    pm = MagicMock()
    pm.get_prompt = MagicMock(
        return_value=(
            "Context: {relational_profile_text}\n"
            "Turn {turn_number} session {session_id}\n"
            "USER: {user_message}\n"
            "MITRA: {assistant_response}"
        )
    )
    return pm


@pytest.fixture
def extractor(monkeypatch, mock_llm_service, mock_prompt_manager):
    """Extractor with mocked LLM + prompt_manager dependencies."""
    from services import memory_extractor

    monkeypatch.setattr(memory_extractor, "get_llm_service", lambda: mock_llm_service)
    monkeypatch.setattr(
        memory_extractor, "get_prompt_manager", lambda: mock_prompt_manager
    )
    return memory_extractor


class TestMemoryExtractorExtract:
    @pytest.mark.asyncio
    async def test_returns_empty_extraction_on_zero_facts(
        self, extractor, mock_llm_service
    ):
        mock_llm_service.complete_json.return_value = '{"facts": []}'
        result = await extractor.extract_memories(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="hi",
            assistant_response="hello",
            relational_profile_text="",
        )
        assert isinstance(result, ExtractionResult)
        assert result.facts == []

    @pytest.mark.asyncio
    async def test_parses_single_fact(self, extractor, mock_llm_service):
        mock_llm_service.complete_json.return_value = (
            '{"facts": [{"text": "User is a software engineer", '
            '"importance": 6, "sensitivity": "personal", "tone_marker": "neutral"}]}'
        )
        result = await extractor.extract_memories(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="I work in tech",
            assistant_response="That is interesting",
            relational_profile_text="",
        )
        assert len(result.facts) == 1
        assert result.facts[0].text == "User is a software engineer"
        assert result.facts[0].importance == 6

    @pytest.mark.asyncio
    async def test_parses_multiple_facts(self, extractor, mock_llm_service):
        mock_llm_service.complete_json.return_value = """{
            "facts": [
                {"text": "User's father passed in February", "importance": 9, "sensitivity": "sensitive", "tone_marker": "grief"},
                {"text": "User is vegetarian", "importance": 4, "sensitivity": "personal", "tone_marker": "neutral"}
            ]
        }"""
        result = await extractor.extract_memories(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=3,
            user_message="my father died and I'm vegetarian",
            assistant_response="I'm sorry for your loss",
            relational_profile_text="",
        )
        assert len(result.facts) == 2
        assert result.facts[0].sensitivity == "sensitive"
        assert result.facts[1].importance == 4

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty_extraction(
        self, extractor, mock_llm_service
    ):
        mock_llm_service.complete_json.return_value = "not valid json at all"
        result = await extractor.extract_memories(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="hi",
            assistant_response="hello",
            relational_profile_text="",
        )
        assert isinstance(result, ExtractionResult)
        assert result.facts == []

    @pytest.mark.asyncio
    async def test_llm_error_returns_empty_extraction(
        self, extractor, mock_llm_service
    ):
        mock_llm_service.complete_json.side_effect = RuntimeError("gemini boom")
        result = await extractor.extract_memories(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="hi",
            assistant_response="hello",
            relational_profile_text="",
        )
        assert isinstance(result, ExtractionResult)
        assert result.facts == []

    @pytest.mark.asyncio
    async def test_prompt_manager_called_with_memory_extract_key(
        self, extractor, mock_llm_service, mock_prompt_manager
    ):
        mock_llm_service.complete_json.return_value = '{"facts": []}'
        await extractor.extract_memories(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="hi",
            assistant_response="hello",
            relational_profile_text="",
        )
        mock_prompt_manager.get_prompt.assert_called_once()
        args, kwargs = mock_prompt_manager.get_prompt.call_args
        # First positional arg is the prompt group, second is the dot-path key
        assert args[0] == "spiritual_mitra"
        assert args[1] == "memory_prompts.extract"


class TestMemoryExtractorDispatchGates:
    @pytest.mark.asyncio
    async def test_dispatch_skips_anonymous_session(
        self, extractor, mock_llm_service
    ):
        """No user_id → no extraction task scheduled."""
        await extractor.dispatch_memory_extraction(
            user_id=None,
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="I just lost my father",
            assistant_response="I am so sorry",
            intent_analysis={"intent": "EXPRESSING_EMOTION"},
        )
        # LLM must never have been called
        mock_llm_service.complete_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_skips_greeting_intent(
        self, extractor, mock_llm_service
    ):
        await extractor.dispatch_memory_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="hi",
            assistant_response="hello",
            intent_analysis={"intent": "GREETING"},
        )
        mock_llm_service.complete_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_skips_closure_intent(
        self, extractor, mock_llm_service
    ):
        await extractor.dispatch_memory_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="thanks bye",
            assistant_response="take care",
            intent_analysis={"intent": "CLOSURE"},
        )
        mock_llm_service.complete_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_skips_off_topic(
        self, extractor, mock_llm_service
    ):
        await extractor.dispatch_memory_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="write python code",
            assistant_response="I am here as your spiritual companion",
            intent_analysis={"intent": "OTHER", "is_off_topic": True},
        )
        mock_llm_service.complete_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_fires_for_substantive_turn(
        self, extractor, mock_llm_service, monkeypatch
    ):
        """A non-trivial emotional share dispatches the task. We await the
        task instead of relying on asyncio background execution, so the test
        is deterministic."""
        mock_llm_service.complete_json.return_value = '{"facts": []}'
        dispatched_tasks = []

        # Wrap create_task so we can await the inner coroutine synchronously
        orig_create_task = asyncio.create_task
        def capturing_create_task(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched_tasks.append(task)
            return task

        monkeypatch.setattr(
            "services.memory_extractor.asyncio.create_task",
            capturing_create_task,
        )

        await extractor.dispatch_memory_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="I lost my father in February",
            assistant_response="That is a heavy loss",
            intent_analysis={"intent": "EXPRESSING_EMOTION"},
        )

        # Should have dispatched exactly one task
        assert len(dispatched_tasks) == 1

        # Await the task to completion
        await dispatched_tasks[0]

        # LLM should have been called
        mock_llm_service.complete_json.assert_called_once()


class TestMemoryExtractorErrorSafety:
    @pytest.mark.asyncio
    async def test_dispatch_swallows_all_exceptions(
        self, extractor, mock_llm_service, monkeypatch
    ):
        """Even if the entire extraction pipeline raises, dispatch never re-raises."""
        mock_llm_service.complete_json.side_effect = RuntimeError("everything broke")

        dispatched_tasks = []
        orig_create_task = asyncio.create_task

        def capturing_create_task(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched_tasks.append(task)
            return task

        monkeypatch.setattr(
            "services.memory_extractor.asyncio.create_task",
            capturing_create_task,
        )

        # Must NOT raise
        await extractor.dispatch_memory_extraction(
            user_id="u1",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="I lost my father",
            assistant_response="sorry",
            intent_analysis={"intent": "EXPRESSING_EMOTION"},
        )

        # Task dispatched
        assert len(dispatched_tasks) == 1
        # Awaiting the task must also not re-raise (the wrapper swallows)
        await dispatched_tasks[0]
