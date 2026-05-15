"""Crisis meta-fact hook — writes a generic tone-bias marker on user_profiles
when a crisis is detected. NEVER stores verbatim crisis content.

The dynamic memory system has a hard rule: user_memories must never contain
the user's actual crisis words. Crisis awareness is expressed as a single
meta-fact line plus a boolean flag on the RelationalProfile. Future turns
read the flag via ``profile.to_prompt_text()`` which renders a generic
safety note ("This user has previously shared a crisis moment — bias tone
softer, do not reference specifics") instead of any verbatim text.

This module is called from two places (see commit 10 wiring):
    1. ``routers/chat._preflight`` — after keyword-based crisis detection
    2. ``services/companion_engine.process_message_preamble`` — after
       LLM-based (IntentAgent urgency=crisis) detection

Both call sites use the fire-and-forget ``dispatch_crisis_meta_fact`` helper
so the crisis response stream is never blocked by a MongoDB write.

Writes are IDEMPOTENT at the document level (upsert), not at the event
level: each crisis message increments ``prior_crisis_count``. This is
intentional — a repeated crisis signal is actually meaningful tone info,
not noise to be deduped.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy accessors — tests monkeypatch these to inject mocks cleanly
# ---------------------------------------------------------------------------

def get_db():
    from services.auth_service import get_mongo_client
    return get_mongo_client()


async def _invalidate_profile_cache(user_id: str) -> None:
    """Best-effort Redis cache bust — lazy import avoids circular deps."""
    try:
        from services import memory_reader
        await memory_reader.invalidate_profile_cache(user_id)
    except Exception as exc:
        logger.debug(
            f"crisis_memory_hook: cache invalidate failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# Meta-fact construction — generic, never verbatim
# ---------------------------------------------------------------------------

def _build_meta_fact(now: datetime) -> str:
    """The single line written to ``prior_crisis_context``.

    Hard rule: never include verbatim user words. Never include the
    specific topic. Never speculate on cause. This line exists solely
    to remind future turns that a crisis occurred on this date — the
    generic safety note rendered by ``profile.to_prompt_text()`` is
    what actually influences LLM tone; this field is for audit and
    user-visible provenance, not prompt injection.
    """
    date_str = now.strftime("%Y-%m-%d")
    return (
        f"On {date_str}, this user shared a crisis moment; helplines "
        f"were offered and the conversation continued. (Meta-fact only; "
        f"no verbatim content stored.)"
    )


# ---------------------------------------------------------------------------
# Core write — atomic upsert that never crashes the caller
# ---------------------------------------------------------------------------

async def write_crisis_meta_fact(user_id: str) -> bool:
    """Atomically set prior_crisis_flag=True, increment prior_crisis_count,
    refresh prior_crisis_context.

    Returns True iff the write hit MongoDB successfully. False on any
    early-exit (anonymous user, db unavailable) or failure. Never raises.

    This is a single MongoDB update_one with upsert=True — the profile
    doc is created on first-ever crisis for a user who somehow crisised
    before their first normal memory extraction (edge case, but real).

    A separate call invalidates the Redis profile cache so the next
    turn sees the flag.
    """
    if not user_id:
        logger.debug("crisis_memory_hook: anonymous user — skip")
        return False

    db = get_db()
    if db is None:
        logger.warning("crisis_memory_hook: db unavailable — skip")
        return False

    now = datetime.utcnow()
    meta_fact = _build_meta_fact(now)

    try:
        await asyncio.to_thread(
            db.user_profiles.update_one,
            {"user_id": user_id},
            {
                "$set": {
                    "prior_crisis_flag": True,
                    "prior_crisis_context": meta_fact,
                    "updated_at": now,
                },
                "$inc": {"prior_crisis_count": 1},
                "$setOnInsert": {
                    "user_id": user_id,
                    "relational_narrative": "",
                    "spiritual_themes": [],
                    "ongoing_concerns": [],
                    "tone_preferences": [],
                    "people_mentioned": [],
                    "importance_since_reflection": 0,
                    "reflection_count": 0,
                    "last_reflection_at": None,
                    "created_at": now,
                },
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning(
            f"crisis_memory_hook: write failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return False

    # Best-effort cache bust. Never let a cache failure break the write.
    await _invalidate_profile_cache(user_id)

    logger.info(
        f"crisis_memory_hook: crisis meta-fact written for user={user_id}"
    )
    return True


# ---------------------------------------------------------------------------
# Fire-and-forget dispatch — called from chat router + companion_engine
# ---------------------------------------------------------------------------

def dispatch_crisis_meta_fact(user_id: Optional[str]) -> None:
    """Schedule write_crisis_meta_fact as a background task.

    Fire-and-forget. Safe to call with user_id=None (no-op). The caller
    returns immediately; the MongoDB write happens alongside the crisis
    response stream. Failures log a warning but never surface to the
    crisis-handling code path.
    """
    if not user_id:
        return

    try:
        task = asyncio.create_task(write_crisis_meta_fact(user_id))
        task.add_done_callback(_log_task_exception)
    except Exception as exc:
        logger.warning(
            f"crisis_memory_hook: dispatch failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )


def _log_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning(
            f"crisis_memory_hook: background task raised "
            f"{type(exc).__name__}: {exc}"
        )
