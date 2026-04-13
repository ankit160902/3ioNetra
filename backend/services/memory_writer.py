"""MemoryUpdater — Gemini call #2 for the dynamic memory system.

Per extracted fact, this module:

    1. Embeds the new fact text
    2. Retrieves the top-k still-valid similar existing memories
    3. Asks Gemini to decide ADD / UPDATE / DELETE / NOOP
    4. Executes the decision on ``user_memories`` with bi-temporal semantics
    5. Bumps ``user_profiles.importance_since_reflection`` on ADD/UPDATE so
       Commit 9's ReflectionService has the trigger signal ready

The file is named ``memory_writer.py`` to avoid colliding with the legacy
keyword-based ``memory_updater.py`` which still powers CompanionEngine's
in-session signal detection. The concept is still "MemoryUpdater" per
the spec — only the Python filename differs.

Public entry point:

    update_memories_from_extraction(
        user_id, session_id, conversation_id, turn_number, extraction,
    ) -> List[MemoryUpdateDecision]

Returns the list of decisions (one per fact) for observability and
testing. Never raises — all errors are caught and logged as warnings,
and the caller (``memory_extractor._extract_with_timeout``) can ignore
the return value entirely. Safety default on any decision-parse failure
is ``ADD`` — per spec §9.3, it is safer to duplicate than to
accidentally invalidate a valid memory.

Crisis-tier facts short-circuit the entire pipeline. Crisis meta-facts
are written by the crisis hook in ``companion_engine.py`` (Commit 10),
never through the standard extraction path.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

from config import settings
from models.llm_schemas import (
    ExtractedMemory,
    ExtractionResult,
    MemoryUpdateDecision,
    extract_json,
)

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


def get_rag_pipeline():
    from routers.dependencies import get_rag_pipeline as _getter
    return _getter()


def get_db():
    from services.auth_service import get_mongo_client
    return get_mongo_client()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def update_memories_from_extraction(
    *,
    user_id: str,
    session_id: str,
    conversation_id: Optional[str],
    turn_number: int,
    extraction: ExtractionResult,
) -> List[MemoryUpdateDecision]:
    """Apply Mem0 ADD/UPDATE/DELETE/NOOP for each extracted fact.

    Returns the list of decisions actually executed (empty list on any
    early-exit path). Never raises — a failure anywhere in the pipeline
    is logged and the fact is skipped so the rest of the batch can still
    land.
    """
    if not extraction or not extraction.facts:
        return []

    if not user_id:
        logger.debug("memory_writer: skip — anonymous user_id")
        return []

    db = get_db()
    if db is None:
        logger.warning("memory_writer: db unavailable — skipping writes")
        return []

    rag = get_rag_pipeline()
    if rag is None:
        logger.warning("memory_writer: rag pipeline unavailable — skipping writes")
        return []

    provenance = {
        "session_id": session_id,
        "conversation_id": conversation_id,
        "turn_number": turn_number,
    }

    decisions: List[MemoryUpdateDecision] = []
    for fact in extraction.facts:
        # Crisis defense — crisis facts never go through the standard path.
        # Commit 10 will wire the crisis meta-fact writer in companion_engine.
        if fact.sensitivity == "crisis":
            logger.warning(
                f"memory_writer: crisis-tier fact short-circuited for "
                f"user={user_id}; handled by crisis hook instead"
            )
            continue

        try:
            decision = await _process_fact(
                db=db,
                rag=rag,
                user_id=user_id,
                fact=fact,
                provenance=provenance,
            )
            if decision is not None:
                decisions.append(decision)
        except Exception as exc:
            logger.warning(
                f"memory_writer: fact processing failed for user={user_id}: "
                f"{type(exc).__name__}: {exc}"
            )

    # Reflection trigger — only if at least one ADD or UPDATE actually bumped
    # the counter. DELETE and NOOP don't contribute toward the threshold.
    if any(d.operation in ("ADD", "UPDATE") for d in decisions):
        try:
            from services.reflection_service import maybe_trigger_reflection
            await maybe_trigger_reflection(user_id)
        except Exception as exc:
            logger.debug(
                f"memory_writer: reflection trigger check failed for "
                f"user={user_id}: {type(exc).__name__}: {exc}"
            )

    return decisions


# ---------------------------------------------------------------------------
# Per-fact pipeline
# ---------------------------------------------------------------------------

async def _process_fact(
    *,
    db: Any,
    rag: Any,
    user_id: str,
    fact: ExtractedMemory,
    provenance: Dict[str, Any],
) -> Optional[MemoryUpdateDecision]:
    """Embed → retrieve similar → decide → execute. One fact."""
    try:
        new_embedding = await rag.generate_embeddings(fact.text)
    except Exception as exc:
        logger.warning(
            f"memory_writer: embedding failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return None

    similar = await _fetch_similar_memories(
        db=db,
        user_id=user_id,
        query_embedding=new_embedding,
        top_k=settings.MEMORY_UPDATER_SIMILAR_K,
    )

    decision = await _decide_operation(fact=fact, similar_memories=similar)

    await _execute_decision(
        db=db,
        user_id=user_id,
        decision=decision,
        fact=fact,
        new_embedding=new_embedding,
        provenance=provenance,
    )
    return decision


# ---------------------------------------------------------------------------
# Similarity retrieval
# ---------------------------------------------------------------------------

async def _fetch_similar_memories(
    *,
    db: Any,
    user_id: str,
    query_embedding: np.ndarray,
    top_k: int,
) -> List[Dict[str, Any]]:
    """Return top-k still-valid memories ranked by cosine similarity.

    Uses the bi-temporal filter ``invalid_at: None`` so superseded memories
    are never surfaced to the decider. Crisis-tier memories are defensively
    filtered out — they should never live in ``user_memories`` in the first
    place, but this is a safety belt.

    Each returned dict has its ``_id`` stringified for injection into the
    prompt block.
    """
    def _sync_fetch() -> List[Dict[str, Any]]:
        cursor = db.user_memories.find(
            {"user_id": user_id, "invalid_at": None},
            {"text": 1, "embedding": 1, "importance": 1,
             "sensitivity": 1, "tone_marker": 1, "valid_at": 1},
        )
        return list(cursor)

    try:
        docs = await asyncio.to_thread(_sync_fetch)
    except Exception as exc:
        logger.warning(
            f"memory_writer: mongo fetch similar failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return []

    if not docs:
        return []

    docs = [d for d in docs if d.get("sensitivity") != "crisis"]
    docs = [d for d in docs if d.get("embedding")]
    if not docs:
        return []

    def _rank() -> List[Dict[str, Any]]:
        mem_matrix = np.array([d["embedding"] for d in docs], dtype=np.float32)
        norms = np.linalg.norm(mem_matrix, axis=1)
        norms[norms == 0] = 1e-9
        q_norm = np.linalg.norm(query_embedding) + 1e-9
        sims = (mem_matrix @ query_embedding) / (norms * q_norm)
        order = np.argsort(-sims)[:top_k]
        ranked = []
        for idx in order:
            doc = docs[int(idx)]
            doc_out = {
                "id": str(doc.get("_id", "")),
                "text": doc.get("text", ""),
                "importance": doc.get("importance", 5),
                "sensitivity": doc.get("sensitivity", "personal"),
                "tone_marker": doc.get("tone_marker", "neutral"),
                "similarity": float(sims[int(idx)]),
            }
            ranked.append(doc_out)
        return ranked

    try:
        return await asyncio.to_thread(_rank)
    except Exception as exc:
        logger.warning(
            f"memory_writer: similarity rank failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
        return []


# ---------------------------------------------------------------------------
# Decision — Gemini call #2
# ---------------------------------------------------------------------------

def _format_similar_block(similar: List[Dict[str, Any]]) -> str:
    """Render the top-k similar memories as a numbered block for the prompt."""
    if not similar:
        return "(no similar existing memories)"
    lines = []
    for i, m in enumerate(similar, start=1):
        lines.append(
            f"{i}. id={m['id']} | importance={m['importance']} | "
            f"sensitivity={m['sensitivity']} | tone={m['tone_marker']} | "
            f"similarity={m['similarity']:.3f}\n"
            f"   text: {m['text']}"
        )
    return "\n".join(lines)


async def _decide_operation(
    *,
    fact: ExtractedMemory,
    similar_memories: List[Dict[str, Any]],
) -> MemoryUpdateDecision:
    """Ask Gemini to pick ADD/UPDATE/DELETE/NOOP. Any error → ADD (safety default)."""
    try:
        llm = get_llm_service()
        pm = get_prompt_manager()
    except Exception as exc:
        logger.warning(
            f"memory_writer: failed to load LLM or prompt manager: {exc}"
        )
        return MemoryUpdateDecision(operation="ADD", reason="loader_failed")

    template = pm.get_prompt(
        "spiritual_mitra", "memory_prompts.update_decision", default=""
    )
    if not template:
        logger.warning("memory_writer: memory_prompts.update_decision is empty")
        return MemoryUpdateDecision(operation="ADD", reason="prompt_missing")

    try:
        prompt = template.format(
            new_fact_text=fact.text,
            new_fact_importance=fact.importance,
            new_fact_sensitivity=fact.sensitivity,
            new_fact_tone=fact.tone_marker,
            similar_memories_block=_format_similar_block(similar_memories),
        )
    except KeyError as exc:
        logger.warning(f"memory_writer: prompt missing placeholder: {exc}")
        return MemoryUpdateDecision(operation="ADD", reason="format_failed")

    try:
        raw = await llm.complete_json(
            prompt,
            model=settings.GEMINI_FAST_MODEL,
            max_output_tokens=512,
            temperature=0.1,
        )
    except Exception as exc:
        logger.warning(
            f"memory_writer: Gemini decide call failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return MemoryUpdateDecision(operation="ADD", reason="gemini_failed")

    parsed = extract_json(raw)
    if parsed is None:
        logger.warning(
            f"memory_writer: failed to parse decision JSON; "
            f"raw snippet: {raw[:120]!r}"
        )
        return MemoryUpdateDecision(operation="ADD", reason="json_parse_failed")

    try:
        return MemoryUpdateDecision(**parsed)
    except Exception as exc:
        logger.warning(
            f"memory_writer: decision Pydantic validation failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return MemoryUpdateDecision(operation="ADD", reason="pydantic_failed")


# ---------------------------------------------------------------------------
# Execute — bi-temporal writes
# ---------------------------------------------------------------------------

def _build_new_memory_doc(
    *,
    user_id: str,
    text: str,
    embedding: np.ndarray,
    fact: ExtractedMemory,
    provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """Shape a fresh user_memories document (used by both ADD and UPDATE-insert)."""
    now = datetime.utcnow()
    return {
        "user_id": user_id,
        "text": text,
        "embedding": embedding.tolist() if hasattr(embedding, "tolist") else list(embedding),
        "importance": fact.importance,
        "sensitivity": fact.sensitivity,
        "tone_marker": fact.tone_marker,
        "valid_at": now,
        "invalid_at": None,
        "provenance": dict(provenance),
        "source": "extracted",
        "last_accessed_at": None,
        "access_count": 0,
        "created_at": now,
    }


def _to_object_id(raw: Optional[str]):
    """Best-effort ObjectId conversion. Returns None on any failure."""
    if not raw:
        return None
    try:
        from bson import ObjectId
        return ObjectId(raw)
    except Exception:
        return None


async def _execute_decision(
    *,
    db: Any,
    user_id: str,
    decision: MemoryUpdateDecision,
    fact: ExtractedMemory,
    new_embedding: np.ndarray,
    provenance: Dict[str, Any],
) -> None:
    """Apply the decision to MongoDB. Bi-temporal: never hard-delete.

    ADD    — insert a fresh doc
    UPDATE — invalid_at=now on target, insert merged updated_text as fresh
    DELETE — invalid_at=now on target, NO insert (correction, not new fact)
    NOOP   — bump access_count / last_accessed_at on target, no other writes

    Reflection counter on user_profiles.importance_since_reflection is
    bumped by fact.importance on ADD and UPDATE only. DELETE and NOOP
    do not represent net-new information, so they do not contribute
    toward the reflection threshold.
    """
    op = decision.operation

    if op == "ADD":
        doc = _build_new_memory_doc(
            user_id=user_id, text=fact.text, embedding=new_embedding,
            fact=fact, provenance=provenance,
        )
        try:
            await asyncio.to_thread(db.user_memories.insert_one, doc)
        except Exception as exc:
            logger.warning(
                f"memory_writer: ADD insert failed for user={user_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            return
        await _bump_reflection_counter(db, user_id, fact.importance)
        logger.info(
            f"memory_writer: ADD user={user_id} importance={fact.importance} "
            f"sensitivity={fact.sensitivity}"
        )
        return

    if op == "UPDATE":
        target_id = _to_object_id(decision.target_memory_id)
        if target_id is None:
            # Missing / bad target — safety default: fall through to ADD
            logger.warning(
                f"memory_writer: UPDATE missing valid target_memory_id "
                f"(raw={decision.target_memory_id!r}) — falling back to ADD"
            )
            doc = _build_new_memory_doc(
                user_id=user_id, text=fact.text, embedding=new_embedding,
                fact=fact, provenance=provenance,
            )
            try:
                await asyncio.to_thread(db.user_memories.insert_one, doc)
            except Exception as exc:
                logger.warning(
                    f"memory_writer: UPDATE→ADD fallback failed: "
                    f"{type(exc).__name__}: {exc}"
                )
                return
            await _bump_reflection_counter(db, user_id, fact.importance)
            return

        # Invalidate the old record
        try:
            await asyncio.to_thread(
                db.user_memories.update_one,
                {"_id": target_id, "user_id": user_id},
                {"$set": {"invalid_at": datetime.utcnow()}},
            )
        except Exception as exc:
            logger.warning(
                f"memory_writer: UPDATE invalidation failed for user={user_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        # Insert the merged text as a fresh doc
        merged_text = decision.updated_text or fact.text
        doc = _build_new_memory_doc(
            user_id=user_id, text=merged_text, embedding=new_embedding,
            fact=fact, provenance=provenance,
        )
        try:
            await asyncio.to_thread(db.user_memories.insert_one, doc)
        except Exception as exc:
            logger.warning(
                f"memory_writer: UPDATE insert-merged failed for user={user_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            return

        await _bump_reflection_counter(db, user_id, fact.importance)
        logger.info(
            f"memory_writer: UPDATE user={user_id} target={decision.target_memory_id} "
            f"importance={fact.importance}"
        )
        return

    if op == "DELETE":
        target_id = _to_object_id(decision.target_memory_id)
        if target_id is None:
            logger.warning(
                f"memory_writer: DELETE missing valid target_memory_id "
                f"(raw={decision.target_memory_id!r}) — no-op"
            )
            return
        try:
            await asyncio.to_thread(
                db.user_memories.update_one,
                {"_id": target_id, "user_id": user_id},
                {"$set": {"invalid_at": datetime.utcnow()}},
            )
        except Exception as exc:
            logger.warning(
                f"memory_writer: DELETE invalidation failed for user={user_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            return
        logger.info(
            f"memory_writer: DELETE user={user_id} target={decision.target_memory_id}"
        )
        return

    if op == "NOOP":
        target_id = _to_object_id(decision.target_memory_id)
        if target_id is None:
            logger.debug(
                f"memory_writer: NOOP without target_memory_id for user={user_id}"
            )
            return
        try:
            await asyncio.to_thread(
                db.user_memories.update_one,
                {"_id": target_id, "user_id": user_id},
                {
                    "$set": {"last_accessed_at": datetime.utcnow()},
                    "$inc": {"access_count": 1},
                },
            )
        except Exception as exc:
            logger.warning(
                f"memory_writer: NOOP access bump failed for user={user_id}: "
                f"{type(exc).__name__}: {exc}"
            )
            return
        logger.debug(
            f"memory_writer: NOOP user={user_id} target={decision.target_memory_id}"
        )
        return

    # Defensive — MemoryUpdateDecision validator already clamps to the 4 ops,
    # so reaching this branch means Pydantic was bypassed somehow.
    logger.warning(
        f"memory_writer: unknown operation {op!r} — treating as ADD"
    )
    doc = _build_new_memory_doc(
        user_id=user_id, text=fact.text, embedding=new_embedding,
        fact=fact, provenance=provenance,
    )
    try:
        await asyncio.to_thread(db.user_memories.insert_one, doc)
    except Exception as exc:
        logger.warning(
            f"memory_writer: defensive ADD failed: {type(exc).__name__}: {exc}"
        )
        return
    await _bump_reflection_counter(db, user_id, fact.importance)


async def _bump_reflection_counter(
    db: Any, user_id: str, importance_delta: int
) -> None:
    """Increment user_profiles.importance_since_reflection by the fact's importance.

    Upserts the profile doc if it doesn't yet exist (new user's first memory).
    Commit 9's ReflectionService reads this counter and dispatches reflection
    when it crosses settings.REFLECTION_THRESHOLD. This commit only maintains
    the counter — no reflection dispatch here.
    """
    try:
        now = datetime.utcnow()
        await asyncio.to_thread(
            db.user_profiles.update_one,
            {"user_id": user_id},
            {
                "$inc": {"importance_since_reflection": int(importance_delta)},
                "$setOnInsert": {
                    "user_id": user_id,
                    "relational_narrative": "",
                    "spiritual_themes": [],
                    "ongoing_concerns": [],
                    "tone_preferences": [],
                    "people_mentioned": [],
                    "prior_crisis_flag": False,
                    "prior_crisis_context": None,
                    "prior_crisis_count": 0,
                    "last_reflection_at": None,
                    "reflection_count": 0,
                    "created_at": now,
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning(
            f"memory_writer: reflection counter bump failed for user={user_id}: "
            f"{type(exc).__name__}: {exc}"
        )
