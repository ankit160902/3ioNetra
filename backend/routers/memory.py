"""User-facing /api/memory endpoints for the dynamic memory system.

Spec §12. Every endpoint requires authentication via ``get_current_user``.
user_id isolation is enforced in every Mongo query so a user can NEVER
see, edit, or delete another user's memories.

Provenance is included in every GET response — users can audit "when
did I tell you this?" down to session/conversation/turn granularity.

Soft delete is the default. ``?hard=true`` opts into a real row removal
but stays off by default so nothing is silently destroyed. Bi-temporal
semantics mean soft-deleted rows stay queryable with ``invalid_at != None``
via the (non-public) internal paths but never surface in reader retrieval.

Crisis sensitivity is NEVER writable via the public POST/PATCH endpoints.
Crisis meta-facts are the exclusive domain of ``crisis_memory_hook``.
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from models.api_schemas import (
    MemoryBatchDeleteResponse,
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryListItem,
    MemoryListResponse,
    MemoryPatchRequest,
    MemoryProvenance,
    ProfileResetRequest,
    ProfileResetResponse,
    RelationalProfileResponse,
)
from routers.auth import get_current_user
from services.auth_service import get_mongo_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_auth(user: Optional[Dict]) -> str:
    """Return the authenticated user's id. 401 if anonymous."""
    if not user or not user.get("id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access memory endpoints",
        )
    return str(user["id"])


def _require_db():
    """Return the pymongo database. 503 if unavailable."""
    db = get_mongo_client()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Memory backing store unavailable",
        )
    return db


def _iso_or_none(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _doc_to_list_item(doc: Dict) -> MemoryListItem:
    """Convert a raw user_memories document into the API response shape.

    Private MongoDB fields (``embedding``, ``user_id``) are never surfaced.
    """
    prov_raw = doc.get("provenance") or {}
    return MemoryListItem(
        memory_id=str(doc.get("_id", "")),
        text=str(doc.get("text", "")),
        importance=int(doc.get("importance", 5) or 5),
        sensitivity=str(doc.get("sensitivity", "personal") or "personal"),
        tone_marker=str(doc.get("tone_marker", "neutral") or "neutral"),
        valid_at=_iso_or_none(doc.get("valid_at")),
        invalid_at=_iso_or_none(doc.get("invalid_at")),
        last_accessed_at=_iso_or_none(doc.get("last_accessed_at")),
        access_count=int(doc.get("access_count", 0) or 0),
        source=str(doc.get("source", "extracted") or "extracted"),
        provenance=MemoryProvenance(
            session_id=prov_raw.get("session_id"),
            conversation_id=prov_raw.get("conversation_id"),
            turn_number=prov_raw.get("turn_number"),
        ),
        created_at=_iso_or_none(doc.get("created_at")),
    )


def _doc_to_profile_response(doc: Optional[Dict], user_id: str) -> RelationalProfileResponse:
    """Convert a user_profiles document into the API response shape.

    ``prior_crisis_context`` is deliberately stripped — users see the
    flag and count, but the verbatim meta-fact stays internal.
    """
    if not doc:
        return RelationalProfileResponse(user_id=user_id)
    return RelationalProfileResponse(
        user_id=str(doc.get("user_id", user_id)),
        relational_narrative=str(doc.get("relational_narrative", "") or ""),
        spiritual_themes=list(doc.get("spiritual_themes") or []),
        ongoing_concerns=list(doc.get("ongoing_concerns") or []),
        tone_preferences=list(doc.get("tone_preferences") or []),
        people_mentioned=list(doc.get("people_mentioned") or []),
        prior_crisis_flag=bool(doc.get("prior_crisis_flag", False)),
        prior_crisis_count=int(doc.get("prior_crisis_count", 0) or 0),
        last_reflection_at=_iso_or_none(doc.get("last_reflection_at")),
        reflection_count=int(doc.get("reflection_count", 0) or 0),
        updated_at=_iso_or_none(doc.get("updated_at")),
    )


def _to_object_id(raw: Optional[str]):
    if not raw:
        return None
    try:
        from bson import ObjectId
        return ObjectId(raw)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GET /api/memory  — full list + profile
# ---------------------------------------------------------------------------

@router.get("", response_model=MemoryListResponse)
async def list_memories(
    include_invalidated: bool = Query(
        default=False,
        description="Include soft-deleted / superseded memories in the response.",
    ),
    user: Optional[Dict] = Depends(get_current_user),
):
    """Return every memory (and the relational profile) for the current user.

    By default only still-valid memories (``invalid_at == None``) are
    returned. Pass ``?include_invalidated=true`` to see the full history
    including superseded/soft-deleted rows — useful for the user-facing
    memory panel's "show deleted" toggle.
    """
    user_id = _require_auth(user)
    db = _require_db()

    def _sync_fetch():
        mem_query: Dict = {"user_id": user_id}
        if not include_invalidated:
            mem_query["invalid_at"] = None
        mem_cursor = (
            db.user_memories.find(mem_query)
            .sort([("valid_at", -1), ("created_at", -1)])
        )
        memories = list(mem_cursor)
        profile_doc = db.user_profiles.find_one({"user_id": user_id})
        return memories, profile_doc

    try:
        memories, profile_doc = await asyncio.to_thread(_sync_fetch)
    except Exception as exc:
        logger.error(f"memory router: list fetch failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load memories",
        )

    items = [_doc_to_list_item(d) for d in memories]
    profile = _doc_to_profile_response(profile_doc, user_id)

    return MemoryListResponse(
        memories=items,
        total=len(items),
        profile=profile,
    )


# ---------------------------------------------------------------------------
# GET /api/memory/profile  — just the relational profile
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=RelationalProfileResponse)
async def get_profile(user: Optional[Dict] = Depends(get_current_user)):
    """Return just the RelationalProfile for the current user."""
    user_id = _require_auth(user)
    db = _require_db()

    try:
        doc = await asyncio.to_thread(
            db.user_profiles.find_one, {"user_id": user_id}
        )
    except Exception as exc:
        logger.error(f"memory router: profile fetch failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load profile",
        )

    return _doc_to_profile_response(doc, user_id)


# ---------------------------------------------------------------------------
# POST /api/memory  — manual add
# ---------------------------------------------------------------------------

@router.post("", response_model=MemoryListItem)
async def add_memory(
    body: MemoryCreateRequest,
    user: Optional[Dict] = Depends(get_current_user),
):
    """User manually adds a memory.

    Skips Gemini extraction — goes straight to embedding via RAGPipeline
    and insert. Source is marked ``manual_user_add`` so reflection can
    distinguish user-added memories from LLM-extracted ones.
    """
    user_id = _require_auth(user)
    db = _require_db()

    # Embed the new text so it can be retrieved by the MemoryReader later
    from routers.dependencies import get_rag_pipeline
    rag = get_rag_pipeline()
    if rag is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service unavailable",
        )
    try:
        embedding = await rag.generate_embeddings(body.text)
    except Exception as exc:
        logger.error(f"memory router: embedding failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to embed memory text",
        )

    now = datetime.utcnow()
    doc = {
        "user_id": user_id,
        "text": body.text,
        "embedding": embedding.tolist() if hasattr(embedding, "tolist") else list(embedding),
        "importance": body.importance,
        "sensitivity": body.sensitivity,
        "tone_marker": body.tone_marker,
        "valid_at": now,
        "invalid_at": None,
        "provenance": {
            "session_id": None,
            "conversation_id": None,
            "turn_number": None,
        },
        "source": "manual_user_add",
        "last_accessed_at": None,
        "access_count": 0,
        "created_at": now,
    }

    try:
        result = await asyncio.to_thread(db.user_memories.insert_one, doc)
        doc["_id"] = result.inserted_id
    except Exception as exc:
        logger.error(f"memory router: insert failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save memory",
        )

    return _doc_to_list_item(doc)


# ---------------------------------------------------------------------------
# PATCH /api/memory/{id}  — edit text or sensitivity
# ---------------------------------------------------------------------------

@router.patch("/{memory_id}", response_model=MemoryListItem)
async def edit_memory(
    memory_id: str,
    body: MemoryPatchRequest,
    user: Optional[Dict] = Depends(get_current_user),
):
    """Edit an existing memory's text and/or sensitivity.

    If ``text`` changes, the embedding is regenerated so future retrieval
    reflects the new wording. user_id match is enforced in the Mongo
    query so users can never edit another user's memories.
    """
    user_id = _require_auth(user)
    db = _require_db()

    oid = _to_object_id(memory_id)
    if oid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid memory id",
        )

    set_doc: Dict = {"updated_at": datetime.utcnow()}

    if body.text is not None:
        # Re-embed on text change so retrieval stays accurate
        from routers.dependencies import get_rag_pipeline
        rag = get_rag_pipeline()
        if rag is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedding service unavailable",
            )
        try:
            embedding = await rag.generate_embeddings(body.text)
        except Exception as exc:
            logger.error(f"memory router: re-embed failed for user={user_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to embed memory text",
            )
        set_doc["text"] = body.text
        set_doc["embedding"] = (
            embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        )

    if body.sensitivity is not None:
        set_doc["sensitivity"] = body.sensitivity

    if len(set_doc) == 1:
        # Only updated_at was set — no real patch
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No patchable fields supplied (text or sensitivity required)",
        )

    try:
        # user_id match is the key isolation guard — without it, a guessed
        # ObjectId could patch another user's memory
        result = await asyncio.to_thread(
            db.user_memories.update_one,
            {"_id": oid, "user_id": user_id, "invalid_at": None},
            {"$set": set_doc},
        )
    except Exception as exc:
        logger.error(f"memory router: patch failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update memory",
        )

    if getattr(result, "matched_count", 0) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found or already invalidated",
        )

    try:
        doc = await asyncio.to_thread(
            db.user_memories.find_one, {"_id": oid, "user_id": user_id}
        )
    except Exception as exc:
        logger.error(f"memory router: fetch-after-patch failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory updated but failed to re-read",
        )

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found after update",
        )

    return _doc_to_list_item(doc)


# ---------------------------------------------------------------------------
# DELETE /api/memory/{id}  — soft by default, ?hard=true opts in
# ---------------------------------------------------------------------------

@router.delete("/{memory_id}", response_model=MemoryDeleteResponse)
async def delete_memory(
    memory_id: str,
    hard: bool = Query(default=False, description="Hard-delete the row instead of soft-deleting."),
    user: Optional[Dict] = Depends(get_current_user),
):
    """Delete a memory.

    Default is a soft delete: sets ``invalid_at=now`` so the row
    disappears from retrieval but provenance is preserved. ``?hard=true``
    does an actual ``delete_one`` — useful for GDPR-style erasure.
    """
    user_id = _require_auth(user)
    db = _require_db()

    oid = _to_object_id(memory_id)
    if oid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid memory id",
        )

    try:
        if hard:
            result = await asyncio.to_thread(
                db.user_memories.delete_one,
                {"_id": oid, "user_id": user_id},
            )
            deleted = int(getattr(result, "deleted_count", 0) or 0) > 0
        else:
            result = await asyncio.to_thread(
                db.user_memories.update_one,
                {"_id": oid, "user_id": user_id, "invalid_at": None},
                {"$set": {"invalid_at": datetime.utcnow()}},
            )
            deleted = int(getattr(result, "matched_count", 0) or 0) > 0
    except Exception as exc:
        logger.error(f"memory router: delete failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete memory",
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found or already invalidated",
        )

    return MemoryDeleteResponse(deleted=True, memory_id=memory_id, hard=hard)


# ---------------------------------------------------------------------------
# DELETE /api/memory?before=YYYY-MM-DD  — batch invalidate
# ---------------------------------------------------------------------------

@router.delete("", response_model=MemoryBatchDeleteResponse)
async def batch_invalidate_before(
    before: str = Query(
        ..., description="ISO date (YYYY-MM-DD). All memories created strictly before this date are soft-deleted.",
    ),
    user: Optional[Dict] = Depends(get_current_user),
):
    """Soft-delete all memories created before the given date.

    Uses ``created_at`` for the cutoff (more intuitive for users than
    ``valid_at``). ``invalid_at`` is set to now so reader retrieval will
    skip them immediately.
    """
    user_id = _require_auth(user)
    db = _require_db()

    try:
        cutoff = datetime.fromisoformat(before)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="before must be ISO date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
        )

    try:
        result = await asyncio.to_thread(
            db.user_memories.update_many,
            {
                "user_id": user_id,
                "invalid_at": None,
                "created_at": {"$lt": cutoff},
            },
            {"$set": {"invalid_at": datetime.utcnow()}},
        )
    except Exception as exc:
        logger.error(f"memory router: batch invalidate failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to batch invalidate",
        )

    return MemoryBatchDeleteResponse(
        invalidated_count=int(getattr(result, "modified_count", 0) or 0)
    )


# ---------------------------------------------------------------------------
# POST /api/memory/profile/reset  — wipe the narrative
# ---------------------------------------------------------------------------

@router.post("/profile/reset", response_model=ProfileResetResponse)
async def reset_profile(
    body: ProfileResetRequest,
    user: Optional[Dict] = Depends(get_current_user),
):
    """Reset the relational profile to empty.

    Requires ``{"confirm": true}`` in the body — a minimal guard against
    accidental resets. This clears the narrative, themes, concerns,
    tone prefs, and people lists, and resets reflection state (counter,
    last_reflection_at). It does NOT clear the crisis flag — that's
    intentional, crisis awareness survives profile resets so the user
    still gets softer tone after clearing otherwise unrelated narrative.
    To clear the crisis flag, the user would need a separate request
    (not exposed in this MVP).
    """
    user_id = _require_auth(user)
    db = _require_db()

    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile reset requires explicit confirmation ({'confirm': true})",
        )

    now = datetime.utcnow()
    reset_fields = {
        "relational_narrative": "",
        "spiritual_themes": [],
        "ongoing_concerns": [],
        "tone_preferences": [],
        "people_mentioned": [],
        "importance_since_reflection": 0,
        "last_reflection_at": None,
        "reflection_count": 0,
        "updated_at": now,
    }
    try:
        await asyncio.to_thread(
            db.user_profiles.update_one,
            {"user_id": user_id},
            {"$set": reset_fields},
            upsert=True,
        )
    except Exception as exc:
        logger.error(f"memory router: profile reset failed for user={user_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset profile",
        )

    # Best-effort cache bust so the next chat turn sees the empty profile
    try:
        from services import memory_reader
        await memory_reader.invalidate_profile_cache(user_id)
    except Exception as exc:
        logger.debug(f"memory router: cache bust failed: {exc}")

    return ProfileResetResponse(reset=True)
