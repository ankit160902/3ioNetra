"""MemoryReader — synchronous read path for the dynamic memory system.

Three responsibilities, all on the user-visible critical path so they
MUST be fast and non-blocking-wise bounded:

    1. load_relational_profile(user_id)
       Always-on. Returns the RelationalProfile for this user, sourced
       from Redis (5-min TTL) → MongoDB → empty fallback. Empty profiles
       render as empty strings so the prompt builder can skip the block.

    2. retrieve_episodic(user_id, query, response_mode, analysis, session)
       Mode-gated. Skips entirely for practical_first / closure /
       early presence_first turns. Otherwise fetches all still-valid
       user_memories, applies the sensitivity-tier + tone-aware filter,
       scores via Generative-Agents-style recency × importance × relevance,
       and returns the top-k above the absolute score floor. Fire-and-
       forget access-boost updates the retrieved memories' last_accessed_at
       and access_count so recall strengthens memory.

    3. load_and_retrieve(user_id, query, response_mode, analysis, session)
       Thin convenience wrapper that runs profile + episodic in parallel
       via asyncio.gather and returns a ReadResult containing both. This
       is the entry point the CompanionEngine preamble will call in
       commit 11 (integration); this commit just builds the machinery
       and the tests, no callers yet.

Crisis memories are defensively filtered out during retrieval — they
should never live in ``user_memories`` in the first place, but this is
a safety belt in case the extraction pipeline or a migration ever slips.

This module is new code living alongside the legacy
``memory_service.LongTermMemoryService``. The old code path still works
unchanged; commit 11 will switch CompanionEngine to use this reader.
"""
import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from config import settings
from models.memory_context import RelationalProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy accessors — tests monkeypatch these to inject mocks cleanly
# ---------------------------------------------------------------------------

def get_db():
    from services.auth_service import get_mongo_client
    return get_mongo_client()


def get_cache_service():
    from services.cache_service import get_cache_service as _getter
    return _getter()


def get_rag_pipeline():
    from routers.dependencies import get_rag_pipeline as _getter
    return _getter()


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

@dataclass
class ScoredMemory:
    """One episodic memory plus its ranking score for this turn."""
    memory: Dict[str, Any]
    score: float


@dataclass
class ReadResult:
    """What load_and_retrieve returns.

    profile — always present (empty profile for new/anonymous users).
    episodic — top-k scored memories, possibly empty (mode-gated or no match).
    """
    profile: RelationalProfile
    episodic: List[ScoredMemory] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Profile load
# ---------------------------------------------------------------------------

async def load_relational_profile(user_id: str) -> RelationalProfile:
    """Load the always-in-context profile for this user.

    Order: Redis cache → MongoDB → empty default. Empty profile is a
    perfectly valid state (new user, never reflected). Caller should
    call ``profile.to_prompt_text()`` which returns ``""`` for empty.
    """
    if not user_id:
        return RelationalProfile()

    try:
        cache = get_cache_service()
        cached = await cache.get("user_profile", user_id=user_id)
    except Exception as exc:
        cached = None
        logger.debug(
            f"memory_reader: profile cache get failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
    if cached:
        try:
            return RelationalProfile.from_dict(cached)
        except Exception as exc:
            logger.warning(
                f"memory_reader: cached profile failed to rehydrate "
                f"for user={user_id}: {exc}"
            )

    db = get_db()
    if db is None:
        return RelationalProfile(user_id=user_id)

    try:
        doc = await asyncio.to_thread(
            db.user_profiles.find_one, {"user_id": user_id}
        )
    except Exception as exc:
        logger.warning(
            f"memory_reader: profile find_one failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return RelationalProfile(user_id=user_id)

    profile = RelationalProfile.from_dict(doc) if doc else RelationalProfile(user_id=user_id)

    # Backfill cache. Best-effort — never raise on cache write failures.
    try:
        cache = get_cache_service()
        await cache.set(
            "user_profile",
            profile.to_dict(),
            ttl=settings.MEMORY_PROFILE_CACHE_TTL_SECONDS,
            user_id=user_id,
        )
    except Exception as exc:
        logger.debug(
            f"memory_reader: profile cache set failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )

    return profile


async def invalidate_profile_cache(user_id: str) -> None:
    """Best-effort invalidation hook — call after any profile write.

    Reflection, manual edits, and the crisis hook all use this to force
    the next ``load_relational_profile`` call to re-read from MongoDB.
    """
    if not user_id:
        return
    try:
        cache = get_cache_service()
        # CacheService has no single-key delete in the public surface, so
        # we just overwrite with an empty dict at the same short TTL. The
        # next load will hit MongoDB because empty dict rehydrates to an
        # empty RelationalProfile and the caller detects that via the
        # falsy check below... which doesn't exist. Safer approach: we
        # use flush_prefix, which clears the L1 cache and scans Redis.
        await cache.flush_prefix("user_profile")
    except Exception as exc:
        logger.debug(
            f"memory_reader: profile cache invalidation failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------------------
# Episodic retrieval — mode gate, fetch, filter, score, top-k
# ---------------------------------------------------------------------------

_MODE_SKIPS_RETRIEVAL = frozenset({"practical_first", "closure"})


def _should_skip_retrieval(response_mode: str, turn_count: int) -> bool:
    """Mode-gating rules from spec §6.2 and §10.2.

    practical_first and closure always skip. presence_first skips for
    the first two turns (user needs presence, not evidence). Everything
    else runs retrieval.
    """
    mode = (response_mode or "").strip().lower()
    if mode in _MODE_SKIPS_RETRIEVAL:
        return True
    if mode == "presence_first" and turn_count <= 2:
        return True
    return False


async def retrieve_episodic(
    *,
    user_id: str,
    query: str,
    response_mode: Optional[str],
    analysis: Optional[Dict[str, Any]],
    session: Any,
) -> List[ScoredMemory]:
    """Mode-gated + scored + tier-filtered episodic retrieval.

    Returns the top-k scored memories above the absolute score floor, or
    an empty list if the mode gate skipped, there were no memories, or
    everything fell below the floor.
    """
    if not user_id:
        return []

    turn_count = int(getattr(session, "turn_count", 0) or 0)
    if _should_skip_retrieval(response_mode or "", turn_count):
        logger.debug(
            f"memory_reader: episodic skip mode={response_mode} turn={turn_count}"
        )
        return []

    db = get_db()
    if db is None:
        return []

    rag = get_rag_pipeline()
    if rag is None:
        return []

    try:
        query_embedding = await rag.generate_embeddings(query)
    except Exception as exc:
        logger.warning(
            f"memory_reader: query embedding failed: {type(exc).__name__}: {exc}"
        )
        return []

    def _sync_fetch() -> List[Dict[str, Any]]:
        cursor = db.user_memories.find(
            {"user_id": user_id, "invalid_at": None},
        )
        return list(cursor)

    try:
        memories = await asyncio.to_thread(_sync_fetch)
    except Exception as exc:
        logger.warning(
            f"memory_reader: memory fetch failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return []

    if not memories:
        return []

    current_tone = _infer_current_tone(analysis or {}, response_mode or "")
    now = datetime.utcnow()

    scored: List[ScoredMemory] = []
    for m in memories:
        sensitivity = m.get("sensitivity", "personal")
        # Defensive — crisis memories should never live here, but filter anyway
        if sensitivity == "crisis":
            continue
        # Tone-aware filter for sensitive memories only
        if sensitivity == "sensitive":
            if not _tone_aligned(m.get("tone_marker", "neutral"), current_tone):
                continue
        try:
            score = _score_memory(m, query_embedding, now)
        except Exception as exc:
            logger.debug(
                f"memory_reader: scoring failed for one doc: "
                f"{type(exc).__name__}: {exc}"
            )
            continue
        scored.append(ScoredMemory(memory=m, score=score))

    if not scored:
        return []

    scored.sort(key=lambda sm: sm.score, reverse=True)
    top_k = int(settings.MEMORY_EPISODIC_TOP_K)
    top = scored[:top_k]
    top = [sm for sm in top if sm.score >= settings.MEMORY_SCORE_FLOOR]

    if top:
        ids = [sm.memory.get("_id") for sm in top if sm.memory.get("_id") is not None]
        if ids:
            try:
                task = asyncio.create_task(_bump_access(ids))
                task.add_done_callback(_log_task_exception)
            except Exception as exc:
                logger.debug(
                    f"memory_reader: access-boost dispatch failed: "
                    f"{type(exc).__name__}: {exc}"
                )

    return top


async def load_and_retrieve(
    *,
    user_id: str,
    query: str,
    response_mode: Optional[str],
    analysis: Optional[Dict[str, Any]],
    session: Any,
) -> ReadResult:
    """Run profile load + episodic retrieval in parallel.

    Returns a ReadResult. Never raises — either half can fail
    independently and return a safe default. Commit 11 wires this into
    ``CompanionEngine.process_message_preamble``.
    """
    profile_task = asyncio.create_task(load_relational_profile(user_id))
    episodic_task = asyncio.create_task(
        retrieve_episodic(
            user_id=user_id,
            query=query,
            response_mode=response_mode,
            analysis=analysis,
            session=session,
        )
    )
    profile, episodic = await asyncio.gather(
        profile_task, episodic_task, return_exceptions=True
    )
    if isinstance(profile, BaseException):
        logger.warning(
            f"memory_reader: profile task errored: "
            f"{type(profile).__name__}: {profile}"
        )
        profile = RelationalProfile(user_id=user_id or "")
    if isinstance(episodic, BaseException):
        logger.warning(
            f"memory_reader: episodic task errored: "
            f"{type(episodic).__name__}: {episodic}"
        )
        episodic = []
    return ReadResult(profile=profile, episodic=episodic)


# ---------------------------------------------------------------------------
# Scoring — Generative-Agents-style recency × importance × relevance
# ---------------------------------------------------------------------------

def _coerce_datetime(value: Any) -> Optional[datetime]:
    """Accept datetime, ISO string, or None → datetime or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _score_memory(
    memory: Dict[str, Any],
    query_embedding: np.ndarray,
    now: datetime,
) -> float:
    """Weighted blend of recency, importance, and relevance.

    Recency decays exponentially with half-life ``MEMORY_HALF_LIFE_DAYS``.
    For memories with importance at or above the floor threshold (default
    8), recency can never fall below ``MEMORY_IMPORTANCE_FLOOR_VALUE`` —
    defining life events stay retrievable even years later.

    Importance is normalized (importance/10)^1.5 — slight superlinear so
    a 9 outranks a 7 by more than the raw ratio suggests.

    Relevance is cosine similarity assuming the query is already
    normalized (E5 model pre-normalizes). Memory embeddings are
    normalized at ingestion time.
    """
    last_seen = (
        _coerce_datetime(memory.get("last_accessed_at"))
        or _coerce_datetime(memory.get("valid_at"))
        or _coerce_datetime(memory.get("created_at"))
        or now
    )
    days = max(0.0, (now - last_seen).total_seconds() / 86400.0)
    half_life = max(1, int(settings.MEMORY_HALF_LIFE_DAYS))
    raw_recency = math.exp(-math.log(2) * days / half_life)

    importance = int(memory.get("importance", 5) or 5)
    if importance >= int(settings.MEMORY_IMPORTANCE_FLOOR_THRESHOLD):
        recency = max(raw_recency, float(settings.MEMORY_IMPORTANCE_FLOOR_VALUE))
    else:
        recency = raw_recency

    importance_norm = (max(1, min(10, importance)) / 10.0) ** 1.5

    mem_emb_raw = memory.get("embedding")
    if mem_emb_raw is None:
        relevance = 0.0
    else:
        try:
            mem_emb = np.asarray(mem_emb_raw, dtype=np.float32)
            q = np.asarray(query_embedding, dtype=np.float32)
            # Safe cosine — normalize both sides
            mem_norm = float(np.linalg.norm(mem_emb)) or 1e-9
            q_norm = float(np.linalg.norm(q)) or 1e-9
            relevance = float(np.dot(mem_emb, q) / (mem_norm * q_norm))
        except Exception:
            relevance = 0.0

    return (
        float(settings.MEMORY_WEIGHT_RECENCY) * recency
        + float(settings.MEMORY_WEIGHT_IMPORTANCE) * importance_norm
        + float(settings.MEMORY_WEIGHT_RELEVANCE) * relevance
    )


# ---------------------------------------------------------------------------
# Tone-aware filter
# ---------------------------------------------------------------------------

def _tone_aligned(memory_tone: str, current_tone: str) -> bool:
    """Check whether a memory's tone sits in the same family as the current turn.

    Returns True iff both tones appear together in at least one family in
    ``settings.MEMORY_TONE_FAMILIES``. Unknown tones return False — a
    defensive stance that errs toward NOT surfacing sensitive memories.
    """
    mt = (memory_tone or "").strip().lower()
    ct = (current_tone or "").strip().lower()
    if not mt or not ct:
        return False
    families = settings.MEMORY_TONE_FAMILIES or {}
    for members in families.values():
        member_set = {str(x).strip().lower() for x in members}
        if mt in member_set and ct in member_set:
            return True
    return False


def _infer_current_tone(analysis: Dict[str, Any], response_mode: str) -> str:
    """Infer the current turn's dominant tone word.

    Prefers the IntentAgent-reported emotion if set and not "neutral".
    Otherwise falls back to a sensible default per response mode — e.g.
    presence_first defaults to "heavy", teaching to "curiosity".
    """
    emotion = str(analysis.get("emotion") or "").strip().lower()
    if emotion and emotion != "neutral":
        return emotion
    mode_defaults = {
        "presence_first": "grief",    # heavy family
        "teaching": "curiosity",      # warm family
        "exploratory": "confusion",   # heavy family
        "closure": "gratitude",       # warm family
        "practical_first": "neutral", # neutral family
    }
    return mode_defaults.get((response_mode or "").strip().lower(), "neutral")


# ---------------------------------------------------------------------------
# Access boost — fire-and-forget recency bump
# ---------------------------------------------------------------------------

async def _bump_access(memory_ids: List[Any]) -> None:
    """Update last_accessed_at + access_count on the given memory ids.

    Fire-and-forget via ``asyncio.create_task`` — retrieval never waits.
    Mongo update_many is a single round-trip, fast enough to not care.
    """
    if not memory_ids:
        return
    db = get_db()
    if db is None:
        return
    try:
        await asyncio.to_thread(
            db.user_memories.update_many,
            {"_id": {"$in": list(memory_ids)}},
            {
                "$set": {"last_accessed_at": datetime.utcnow()},
                "$inc": {"access_count": 1},
            },
        )
    except Exception as exc:
        logger.debug(
            f"memory_reader: access boost update_many failed: "
            f"{type(exc).__name__}: {exc}"
        )


def _log_task_exception(task: asyncio.Task) -> None:
    """Done-callback that prevents silent crash at GC time."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.warning(
            f"memory_reader: background task raised "
            f"{type(exc).__name__}: {exc}"
        )
