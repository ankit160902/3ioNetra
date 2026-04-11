"""MemoryExtractor — Gemini call #1 for the dynamic memory system.

Reads a single user turn + Mitra's response + the current relational profile
and asks Gemini to extract 0..N memory-worthy facts with importance,
sensitivity, and tone markers. Empty extraction is a valid result — most
turns produce zero facts.

The extractor exposes two public entry points:

    extract_memories(...)             — the raw call that returns an
                                          ExtractionResult. Used by tests
                                          and by the MemoryUpdater pipeline.

    dispatch_memory_extraction(...)   — fire-and-forget wrapper. Safe to
                                          call with user_id=None (no-op)
                                          and for trivial intents
                                          (GREETING/CLOSURE/OFF_TOPIC
                                          skip). Never raises. Called from
                                          the chat router after the response
                                          stream has closed.

All LLM errors are caught inside the helpers and logged as warnings. A
failed extraction simply means "this turn wasn't remembered" — a graceful
degradation that never surfaces to the user.
"""
import asyncio
import logging
from typing import Any, Dict, Optional

from config import settings
from models.llm_schemas import ExtractionResult, extract_json

logger = logging.getLogger(__name__)


# Lazy imports — the LLMService and PromptManager singletons are heavy,
# and we want the test suite to be able to patch them cleanly via
# monkeypatch.setattr on the module.
def get_llm_service():
    from llm.service import get_llm_service as _getter
    return _getter()


def get_prompt_manager():
    from services.prompt_manager import get_prompt_manager as _getter
    return _getter()


# Intents where extraction is a guaranteed no-op — short-circuit before
# burning any Gemini quota.
_NO_EXTRACTION_INTENTS = frozenset({
    "GREETING",
    "CLOSURE",
    "OFF_TOPIC",
})


async def extract_memories(
    *,
    user_id: str,
    session_id: str,
    conversation_id: Optional[str],
    turn_number: int,
    user_message: str,
    assistant_response: str,
    relational_profile_text: str = "",
) -> ExtractionResult:
    """Run Gemini call #1 to extract memory-worthy facts from one turn.

    Returns an empty ExtractionResult (zero facts) on any failure. Does
    NOT raise — the caller should treat an empty result as "nothing to
    remember this turn."
    """
    try:
        llm = get_llm_service()
        pm = get_prompt_manager()
    except Exception as exc:
        logger.warning(
            f"MemoryExtractor: failed to load LLM or prompt manager: {exc}"
        )
        return ExtractionResult()

    template = pm.get_prompt("spiritual_mitra", "memory_prompts.extract", default="")
    if not template:
        logger.warning("MemoryExtractor: memory_prompts.extract is empty")
        return ExtractionResult()

    try:
        prompt = template.format(
            relational_profile_text=relational_profile_text or "(no profile yet)",
            turn_number=turn_number,
            session_id=session_id,
            user_message=user_message,
            assistant_response=assistant_response,
        )
    except KeyError as exc:
        logger.warning(f"MemoryExtractor: prompt template missing placeholder: {exc}")
        return ExtractionResult()

    try:
        raw = await llm.complete_json(
            prompt,
            model=settings.GEMINI_FAST_MODEL,
            max_output_tokens=1024,
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning(
            f"MemoryExtractor: Gemini call failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return ExtractionResult()

    parsed = extract_json(raw)
    if parsed is None:
        logger.warning(
            f"MemoryExtractor: failed to parse JSON for user={user_id}; "
            f"raw snippet: {raw[:120]!r}"
        )
        return ExtractionResult()

    try:
        result = ExtractionResult(**parsed)
    except Exception as exc:
        logger.warning(
            f"MemoryExtractor: Pydantic validation failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return ExtractionResult()

    if result.facts:
        logger.info(
            f"MemoryExtractor: user={user_id} turn={turn_number} "
            f"extracted {len(result.facts)} fact(s)"
        )
    return result


async def _extract_with_timeout(
    *,
    user_id: str,
    session_id: str,
    conversation_id: Optional[str],
    turn_number: int,
    user_message: str,
    assistant_response: str,
) -> None:
    """Inner coroutine run by dispatch_memory_extraction. Wraps extract_memories
    in a timeout guard so a hung Gemini call cannot leak a zombie task.
    Further storage (MemoryUpdater) will be wired in by the next commit."""
    try:
        async with asyncio.timeout(settings.MEMORY_EXTRACTION_TIMEOUT_SECONDS):
            result = await extract_memories(
                user_id=user_id,
                session_id=session_id,
                conversation_id=conversation_id,
                turn_number=turn_number,
                user_message=user_message,
                assistant_response=assistant_response,
                relational_profile_text="",
            )
            # NOTE: Commit 7 will wire MemoryUpdater in here. For now, we
            # just log the extraction result so the pipeline is observable.
            if result.facts:
                logger.info(
                    f"MemoryExtractor: user={user_id} produced "
                    f"{len(result.facts)} fact(s), awaiting storage pipeline "
                    f"(MemoryUpdater not yet wired)."
                )
    except asyncio.TimeoutError:
        logger.warning(
            f"MemoryExtractor: extraction timed out after "
            f"{settings.MEMORY_EXTRACTION_TIMEOUT_SECONDS}s for user={user_id}"
        )
    except Exception as exc:
        logger.warning(
            f"MemoryExtractor: _extract_with_timeout failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )


def _log_task_exception(task: asyncio.Task) -> None:
    """Attach as a done-callback so unhandled exceptions in the background
    task don't crash silently at garbage-collection time."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning(
            f"MemoryExtractor: background task raised "
            f"{type(exc).__name__}: {exc}"
        )


async def dispatch_memory_extraction(
    *,
    user_id: Optional[str],
    session_id: str,
    conversation_id: Optional[str],
    turn_number: int,
    user_message: str,
    assistant_response: str,
    intent_analysis: Dict[str, Any],
) -> None:
    """Fire-and-forget memory extraction, safe for all call sites.

    Safe to call with:
        user_id=None            — anonymous session, no-op
        intent=GREETING/CLOSURE  — trivial turn, no-op
        is_off_topic=True         — off-topic turn, no-op

    Never raises. Failures in the background task are logged but don't
    propagate. The caller (chat router, after the response stream closes)
    should call this and immediately return to the user.
    """
    # Gate 1: no user
    if not user_id:
        return

    # Gate 2: trivial intent
    intent_raw = str(intent_analysis.get("intent", "")).upper() if intent_analysis else ""
    if intent_raw in _NO_EXTRACTION_INTENTS:
        return

    # Gate 3: off-topic
    if intent_analysis and intent_analysis.get("is_off_topic"):
        return

    # All gates passed — dispatch the fire-and-forget task
    try:
        task = asyncio.create_task(
            _extract_with_timeout(
                user_id=user_id,
                session_id=session_id,
                conversation_id=conversation_id,
                turn_number=turn_number,
                user_message=user_message,
                assistant_response=assistant_response,
            )
        )
        task.add_done_callback(_log_task_exception)
    except Exception as exc:
        # If we can't even schedule the task, log and move on
        logger.warning(
            f"MemoryExtractor: failed to dispatch task for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
