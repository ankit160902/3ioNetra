"""ReflectionService — periodic consolidation + pruning for dynamic memory.

Threshold-triggered background task that turns raw episodic memories
into a consolidated RelationalProfile and prunes the stale / superseded
memory rows the LLM judges no longer part of the user's arc.

Design (spec §11):
    - After each successful ADD or UPDATE, MemoryUpdater bumps
      user_profiles.importance_since_reflection. When the counter
      crosses REFLECTION_THRESHOLD (default 30), maybe_trigger_reflection
      is called and dispatches run_reflection via asyncio.create_task.
    - run_reflection does exactly ONE Gemini call that produces BOTH the
      updated profile AND the list of memory ids to prune. Single round-
      trip — no second pass.
    - The LLM is free to suggest any memory for pruning, but the hard
      safety floor `importance >= MEMORY_PRUNE_IMPORTANCE_SAFETY_FLOOR`
      (default 8) is applied in the MongoDB query itself. High-importance
      memories are never auto-pruned, even if the LLM asks.
    - Reflection uses `gemini-2.5-flash` (REFLECTION_MODEL) — slightly
      stronger than extraction because the consolidation prompt is harder
      and firing frequency is low.
    - No scheduler. Event-driven via the threshold crossing only.
    - Per-user in-flight lock prevents concurrent reflections for the
      same user (race between two near-simultaneous ADDs pushing the
      counter across the threshold). Different users can reflect in
      parallel freely.
    - Failed reflections leave the profile unchanged. The counter does
      NOT reset on failure, so the next ADD will try again.

This commit adds the service and wires it into MemoryUpdater. The
chat-router-level trigger point is unchanged — reflection rides on top
of the existing fire-and-forget extraction task spawned by the chat
router after the response stream closes.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from config import settings
from models.llm_schemas import ReflectionResult, extract_json
from models.memory_context import RelationalProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy accessors — tests monkeypatch these to inject mocks cleanly
# ---------------------------------------------------------------------------

def get_llm_service():
    from llm.service import get_llm_service as _getter
    return _getter()


def get_prompt_manager():
    from services.prompt_manager import get_prompt_manager as _getter
    return _getter()


def get_db():
    from services.auth_service import get_mongo_client
    return get_mongo_client()


async def _invalidate_profile_cache(user_id: str) -> None:
    """Best-effort cache bust — lazy import to avoid a circular dep."""
    try:
        from services import memory_reader
        await memory_reader.invalidate_profile_cache(user_id)
    except Exception as exc:
        logger.debug(
            f"reflection_service: cache invalidate failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# Per-user in-flight tracking
# ---------------------------------------------------------------------------

# Module-level set; guarded by _inflight_lock. A user appears here while
# their reflection task is running, so duplicate dispatches are deduped.
_inflight_users: Set[str] = set()
_inflight_lock = asyncio.Lock()


async def _claim_slot(user_id: str) -> bool:
    """Atomically claim a reflection slot for this user. Returns False
    if one is already in flight."""
    async with _inflight_lock:
        if user_id in _inflight_users:
            return False
        _inflight_users.add(user_id)
        return True


async def _release_slot(user_id: str) -> None:
    async with _inflight_lock:
        _inflight_users.discard(user_id)


# ---------------------------------------------------------------------------
# Trigger — called by MemoryUpdater after ADD/UPDATE
# ---------------------------------------------------------------------------

async def maybe_trigger_reflection(user_id: str) -> bool:
    """Check the reflection counter; if the threshold has been crossed,
    dispatch a background reflection task. Fire-and-forget.

    Returns True iff a task was actually dispatched. False on any
    early-exit (no user, db unavailable, counter below threshold,
    already in flight, dispatch failure). Never raises.

    Call this from MemoryUpdater AFTER ``_bump_reflection_counter``
    returns. The counter is already persisted when this runs, so
    the read below sees the up-to-date value.
    """
    if not user_id:
        return False

    db = get_db()
    if db is None:
        return False

    # Read just the counter field — fast round-trip.
    try:
        doc = await asyncio.to_thread(
            db.user_profiles.find_one,
            {"user_id": user_id},
            {"importance_since_reflection": 1, "_id": 0},
        )
    except Exception as exc:
        logger.debug(
            f"reflection_service: counter read failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return False

    if not doc:
        return False

    counter = int(doc.get("importance_since_reflection", 0) or 0)
    threshold = int(settings.REFLECTION_THRESHOLD)
    if counter < threshold:
        return False

    claimed = await _claim_slot(user_id)
    if not claimed:
        logger.debug(
            f"reflection_service: skip dispatch — reflection already in "
            f"flight for user={user_id}"
        )
        return False

    try:
        task = asyncio.create_task(_run_and_release(user_id))
        task.add_done_callback(_log_task_exception)
    except Exception as exc:
        await _release_slot(user_id)
        logger.warning(
            f"reflection_service: failed to dispatch task for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return False

    logger.info(
        f"reflection_service: dispatched reflection for user={user_id} "
        f"counter={counter} threshold={threshold}"
    )
    return True


async def _run_and_release(user_id: str) -> None:
    """Background wrapper — always releases the in-flight slot."""
    try:
        await run_reflection(user_id)
    finally:
        await _release_slot(user_id)


def _log_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning(
            f"reflection_service: background task raised "
            f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# run_reflection — the main LLM pass
# ---------------------------------------------------------------------------

async def run_reflection(user_id: str) -> Optional[ReflectionResult]:
    """One Gemini call: consolidate profile + prune stale memories.

    Always writes the authoritative profile state from MongoDB, never
    from the cache. Bypasses memory_reader.load_relational_profile for
    this reason. On success, invalidates the Redis cache so the next
    user-facing read sees the fresh narrative.

    Returns the parsed ReflectionResult on success, None on any failure.
    Failures are logged at warning and never raised — the caller is a
    background task that must not propagate exceptions.
    """
    if not user_id:
        return None

    db = get_db()
    if db is None:
        logger.debug("reflection_service: db unavailable — skipping")
        return None

    # 1. Load current profile authoritatively from MongoDB.
    try:
        profile_doc = await asyncio.to_thread(
            db.user_profiles.find_one, {"user_id": user_id}
        )
    except Exception as exc:
        logger.warning(
            f"reflection_service: profile load failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    current_profile = (
        RelationalProfile.from_dict(profile_doc)
        if profile_doc
        else RelationalProfile(user_id=user_id)
    )

    # 2. Load the last-N still-valid memories.
    window = int(settings.REFLECTION_EPISODIC_WINDOW)
    try:
        memories = await asyncio.to_thread(
            _fetch_recent_valid_memories, db, user_id, window
        )
    except Exception as exc:
        logger.warning(
            f"reflection_service: memory load failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    if not memories:
        logger.debug(
            f"reflection_service: no memories yet for user={user_id} — "
            f"nothing to reflect on"
        )
        # Still reset the counter so we don't loop on empty state.
        await _reset_counter(db, user_id)
        return None

    # 3. Render the prompt.
    try:
        pm = get_prompt_manager()
        template = pm.get_prompt("spiritual_mitra", "memory_prompts.reflect", default="")
    except Exception as exc:
        logger.warning(
            f"reflection_service: prompt manager load failed: {exc}"
        )
        return None

    if not template:
        logger.warning("reflection_service: memory_prompts.reflect is empty")
        return None

    try:
        prompt = template.format(
            current_profile_text=current_profile.to_prompt_text() or "(no profile yet)",
            memories_block=_format_memories_for_reflection(memories),
        )
    except KeyError as exc:
        logger.warning(f"reflection_service: prompt missing placeholder: {exc}")
        return None

    # 4. Gemini call.
    try:
        llm = get_llm_service()
        raw = await llm.complete_json(
            prompt,
            model=settings.REFLECTION_MODEL,
            max_output_tokens=2048,
            temperature=0.3,
        )
    except Exception as exc:
        logger.warning(
            f"reflection_service: Gemini call failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    parsed = extract_json(raw)
    if parsed is None:
        logger.warning(
            f"reflection_service: failed to parse JSON for user={user_id}; "
            f"raw snippet: {raw[:120]!r}"
        )
        return None

    try:
        result = ReflectionResult(**parsed)
    except Exception as exc:
        logger.warning(
            f"reflection_service: Pydantic validation failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    # 5. Merge the patch into a new RelationalProfile, reset counters,
    #    write the full profile doc back. This is atomic at the document
    #    level — either the new profile is fully persisted or the old
    #    one is untouched (if the write fails below, the counter is
    #    still non-zero and the next ADD will retry reflection).
    updated = current_profile.apply_reflection(result.updated_profile)
    now = datetime.utcnow()
    # Reflection counters live on the RelationalProfile but are managed
    # here, not by apply_reflection (which deliberately preserves them).
    updated.last_reflection_at = now
    updated.importance_since_reflection = 0
    updated.reflection_count = current_profile.reflection_count + 1
    if not updated.created_at:
        updated.created_at = now

    profile_to_write = updated.to_dict()
    profile_to_write["user_id"] = user_id  # ensure user_id stays on the doc

    try:
        await asyncio.to_thread(
            db.user_profiles.update_one,
            {"user_id": user_id},
            {"$set": profile_to_write},
            upsert=True,
        )
    except Exception as exc:
        logger.warning(
            f"reflection_service: profile write failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    # 6. Prune — LLM-suggested ids filtered by the hardcoded safety floor.
    if result.prune_ids:
        try:
            pruned = await asyncio.to_thread(
                _invalidate_memories_by_id,
                db, user_id, result.prune_ids,
                int(settings.MEMORY_PRUNE_IMPORTANCE_SAFETY_FLOOR),
            )
            if pruned:
                logger.info(
                    f"reflection_service: pruned {pruned} memories for user={user_id} "
                    f"(requested={len(result.prune_ids)})"
                )
        except Exception as exc:
            logger.warning(
                f"reflection_service: prune failed for user={user_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    # 7. Bust the profile cache so the next turn sees the new narrative.
    await _invalidate_profile_cache(user_id)

    logger.info(
        f"reflection_service: reflection complete for user={user_id} "
        f"reflection_count={updated.reflection_count}"
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_recent_valid_memories(
    db: Any, user_id: str, window: int
) -> List[Dict[str, Any]]:
    """Sync — to be called inside asyncio.to_thread.

    Returns the most-recent ``window`` still-valid memories for this user,
    sorted by valid_at descending. Documents that predate the dynamic
    memory system (no valid_at field) fall back to created_at via the
    compound sort.
    """
    cursor = (
        db.user_memories.find(
            {"user_id": user_id, "invalid_at": None},
            {
                "text": 1, "importance": 1, "sensitivity": 1,
                "tone_marker": 1, "valid_at": 1, "created_at": 1,
            },
        )
        .sort([("valid_at", -1), ("created_at", -1)])
        .limit(int(window))
    )
    return list(cursor)


def _format_memories_for_reflection(memories: List[Dict[str, Any]]) -> str:
    """Render the memory list for the reflect prompt."""
    if not memories:
        return "(none)"
    lines: List[str] = []
    for i, m in enumerate(memories, start=1):
        when = m.get("valid_at") or m.get("created_at")
        when_str = when.isoformat() if hasattr(when, "isoformat") else str(when or "")
        lines.append(
            f"{i}. id={m.get('_id', '')} | importance={m.get('importance', 5)} | "
            f"sensitivity={m.get('sensitivity', 'personal')} | "
            f"tone={m.get('tone_marker', 'neutral')} | date={when_str}\n"
            f"   text: {m.get('text', '')}"
        )
    return "\n".join(lines)


def _invalidate_memories_by_id(
    db: Any, user_id: str, raw_ids: List[str], safety_floor: int
) -> int:
    """Sync — to be called inside asyncio.to_thread.

    Sets ``invalid_at=now`` on each of the requested memory ids, BUT ONLY
    for memories with ``importance < safety_floor``. This is the one
    hardcoded safety floor in the entire memory system — the LLM may
    suggest pruning a crisis-adjacent high-importance memory, and we
    refuse.

    Also enforces ``user_id`` match so a prune request can never touch
    another user's data.
    """
    oids: List[Any] = []
    for raw in raw_ids:
        oid = _to_object_id(raw)
        if oid is not None:
            oids.append(oid)
    if not oids:
        return 0

    now = datetime.utcnow()
    result = db.user_memories.update_many(
        {
            "_id": {"$in": oids},
            "user_id": user_id,
            "importance": {"$lt": safety_floor},
            "invalid_at": None,
        },
        {"$set": {"invalid_at": now}},
    )
    return int(getattr(result, "modified_count", 0) or 0)


def _to_object_id(raw: Optional[str]):
    """Best-effort ObjectId conversion. None on failure."""
    if not raw:
        return None
    try:
        from bson import ObjectId
        return ObjectId(raw)
    except Exception:
        return None


async def _reset_counter(db: Any, user_id: str) -> None:
    """Used when there's nothing to reflect on — reset the counter so the
    next ADD doesn't immediately re-trigger an empty pass."""
    try:
        await asyncio.to_thread(
            db.user_profiles.update_one,
            {"user_id": user_id},
            {"$set": {"importance_since_reflection": 0}},
        )
    except Exception as exc:
        logger.debug(
            f"reflection_service: counter reset failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
