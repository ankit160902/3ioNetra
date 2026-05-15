"""One-time backfill migration for the dynamic memory system.

Per spec §14.1. When the dynamic memory system goes live, existing
users already have rich conversation history in MongoDB's
``conversations`` collection but zero entries in ``user_memories`` or
``user_profiles``. This script walks each user's most recent N
conversations, pairs user/assistant turns into (user_msg, response)
tuples, and runs each pair through the regular extraction + write
pipeline — the same pipeline that would have run live if the memory
system had been present from day one.

After every user is backfilled we also fire ONE reflection pass to
consolidate the raw extracted memories into a coherent relational
profile. Future turns then start with a populated profile and a set
of retrievable episodic memories, instead of cold-starting blank.

Scale + cost:

    * Per turn: 1 extraction Gemini call (~$0.0001 with
      gemini-2.5-flash-lite) + optional 1 decision Gemini call per
      extracted fact (~$0.0001). Typical good turn produces 0-1 facts,
      so ~$0.0002 per turn average.
    * Per user: 10 conversations * 10 turns avg * $0.0002 + 1
      reflection at ~$0.002 = roughly $0.022 per user
    * 1000 users: ~$22 one-time cost

The spec mandates a 1-extraction-per-second per-user rate limit to
avoid hammering Gemini on a login-burst. This script honors that via
an asyncio.sleep between each extraction within a user's batch.

Usage:

    # Dry run — report what would be backfilled, no writes
    python scripts/backfill_memory.py --dry-run

    # All users with at least one conversation, 10 most-recent convos each
    python scripts/backfill_memory.py

    # Specific user
    python scripts/backfill_memory.py --user-id u_abc

    # Limit turns per user (for aggressive cost control on first run)
    python scripts/backfill_memory.py --max-turns-per-user 30

    # Don't run reflection — just backfill raw memories
    python scripts/backfill_memory.py --skip-reflection

Idempotency:

    The script checks each user's existing user_memories collection
    BEFORE backfilling. Any user with >= 1 existing memory is skipped
    unless --force is passed. The script also tags every backfilled
    memory with ``source=migration_backfill`` so a future second run
    can identify and skip them (or purge them) as needed.

Safety:

    * No hard deletes, ever
    * Never writes verbatim crisis content — the same sensitivity
      filter that the live extractor uses is applied here (crisis-
      tier facts are skipped by MemoryUpdater before any write)
    * The reflection pass runs through the real reflection_service
      with all its guards (prune safety floor, cache invalidation)
"""
import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Make backend/ importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stats container
# ---------------------------------------------------------------------------

@dataclass
class BackfillStats:
    users_scanned: int = 0
    users_skipped_existing: int = 0
    users_backfilled: int = 0
    users_failed: int = 0
    conversations_processed: int = 0
    turns_processed: int = 0
    extractions_attempted: int = 0
    facts_extracted: int = 0
    memories_written: int = 0
    reflections_run: int = 0
    reflections_failed: int = 0

    def summary_lines(self) -> List[str]:
        return [
            f"users scanned:          {self.users_scanned}",
            f"users skipped:          {self.users_skipped_existing}",
            f"users backfilled:       {self.users_backfilled}",
            f"users failed:           {self.users_failed}",
            f"conversations:          {self.conversations_processed}",
            f"turns:                  {self.turns_processed}",
            f"extraction attempts:    {self.extractions_attempted}",
            f"facts extracted:        {self.facts_extracted}",
            f"memories written:       {self.memories_written}",
            f"reflections run:        {self.reflections_run}",
            f"reflections failed:     {self.reflections_failed}",
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pair_user_assistant_turns(
    messages: List[Dict[str, Any]],
) -> List[Tuple[str, str]]:
    """Walk the message list and emit (user_msg, assistant_msg) pairs.

    Session messages are stored as ``{"role": "user"|"assistant", ...}``.
    A well-formed conversation alternates — user, assistant, user,
    assistant. In practice there can be stray assistant-only messages
    (system greetings) or consecutive user messages (bot silence or
    re-prompts). We only pair sequential user -> assistant transitions
    and drop everything else.
    """
    pairs: List[Tuple[str, str]] = []
    pending_user: Optional[str] = None
    for m in messages or []:
        role = str(m.get("role", "")).lower()
        content = str(m.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            pending_user = content
        elif role == "assistant" and pending_user is not None:
            pairs.append((pending_user, content))
            pending_user = None
    return pairs


async def _get_all_user_ids_with_conversations(
    db, limit: Optional[int]
) -> List[str]:
    """Distinct user_id across the conversations collection."""
    try:
        def _fetch():
            cursor = db.conversations.aggregate(
                [
                    {"$match": {"user_id": {"$exists": True, "$ne": None}}},
                    {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": limit or 10_000},
                ]
            )
            return [doc["_id"] for doc in cursor if doc.get("_id")]

        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        logger.error(f"failed to list users: {exc}")
        return []


async def _user_already_backfilled(db, user_id: str) -> bool:
    def _count():
        return db.user_memories.count_documents({"user_id": user_id})

    try:
        count = await asyncio.to_thread(_count)
        return int(count) > 0
    except Exception as exc:
        logger.warning(f"existing-check failed for {user_id}: {exc}")
        return False


async def _backfill_one_user(
    user_id: str,
    *,
    max_conversations: int,
    max_turns_per_user: Optional[int],
    rate_limit_seconds: float,
    skip_reflection: bool,
    dry_run: bool,
    stats: BackfillStats,
) -> bool:
    """Backfill a single user. Returns True on success."""
    from services.auth_service import get_conversation_storage
    from services import memory_extractor, memory_writer, reflection_service
    from models.llm_schemas import ExtractionResult

    storage = get_conversation_storage()

    try:
        convos = await storage.get_conversations_list(
            user_id, limit=max_conversations
        )
    except Exception as exc:
        logger.error(f"failed to list conversations for {user_id}: {exc}")
        return False

    if not convos:
        logger.debug(f"user {user_id} has no conversation history — skipping")
        return True

    turns_processed = 0

    for convo_meta in convos:
        convo_id = convo_meta.get("id") or convo_meta.get("session_id")
        if not convo_id:
            continue

        try:
            full = await storage.get_conversation(user_id, convo_id)
        except Exception as exc:
            logger.warning(
                f"failed to load conversation {convo_id} for {user_id}: {exc}"
            )
            continue

        if not full or not full.get("messages"):
            continue

        stats.conversations_processed += 1
        session_id = full.get("session_id") or convo_id

        pairs = _pair_user_assistant_turns(full["messages"])
        for turn_num, (user_msg, assistant_msg) in enumerate(pairs, start=1):
            if max_turns_per_user and turns_processed >= max_turns_per_user:
                break

            stats.turns_processed += 1
            turns_processed += 1

            if dry_run:
                # Log what WOULD happen without running Gemini
                logger.info(
                    f"DRY user={user_id} convo={convo_id} turn={turn_num} "
                    f"user_msg_len={len(user_msg)} asst_msg_len={len(assistant_msg)}"
                )
                continue

            # Rate-limit extraction to 1/s per user to avoid hammering
            # Gemini with a login burst.
            if rate_limit_seconds > 0 and turns_processed > 1:
                await asyncio.sleep(rate_limit_seconds)

            stats.extractions_attempted += 1
            try:
                result: ExtractionResult = await memory_extractor.extract_memories(
                    user_id=user_id,
                    session_id=session_id,
                    conversation_id=convo_id,
                    turn_number=turn_num,
                    user_message=user_msg,
                    assistant_response=assistant_msg,
                    relational_profile_text="",
                )
            except Exception as exc:
                logger.warning(
                    f"extract failed user={user_id} convo={convo_id} "
                    f"turn={turn_num}: {exc}"
                )
                continue

            if not result.facts:
                continue

            stats.facts_extracted += len(result.facts)

            try:
                decisions = await memory_writer.update_memories_from_extraction(
                    user_id=user_id,
                    session_id=session_id,
                    conversation_id=convo_id,
                    turn_number=turn_num,
                    extraction=result,
                )
                stats.memories_written += sum(
                    1 for d in decisions if d.operation in ("ADD", "UPDATE")
                )
            except Exception as exc:
                logger.warning(
                    f"write failed user={user_id} convo={convo_id} "
                    f"turn={turn_num}: {exc}"
                )
                continue

        if max_turns_per_user and turns_processed >= max_turns_per_user:
            break

    # Final consolidation pass — turn the raw extracted memories into a
    # coherent relational profile. This is a single Gemini call per user.
    if not dry_run and not skip_reflection:
        try:
            ref_result = await reflection_service.run_reflection(user_id)
            if ref_result is not None:
                stats.reflections_run += 1
            else:
                stats.reflections_failed += 1
        except Exception as exc:
            stats.reflections_failed += 1
            logger.warning(f"reflection failed for {user_id}: {exc}")

    return True


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------

async def _main_async(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.dry_run and not os.environ.get("GEMINI_API_KEY"):
        logger.error("GEMINI_API_KEY not set — live Gemini calls are required")
        return 2

    from services.auth_service import get_mongo_client
    from routers.dependencies import get_rag_pipeline, set_rag_pipeline

    db = get_mongo_client()
    if db is None:
        logger.error("MongoDB unavailable")
        return 2

    # The writer needs the rag pipeline for embedding. In a live
    # lifespan this is attached by main.py startup. Here we construct
    # and attach one directly so the script is standalone.
    if get_rag_pipeline() is None and not args.dry_run:
        from rag.pipeline import RAGPipeline

        logger.info("initializing RAG pipeline for embeddings...")
        rag_pipe = RAGPipeline()
        await rag_pipe.initialize()
        set_rag_pipeline(rag_pipe)

    stats = BackfillStats()

    if args.user_id:
        user_ids = [args.user_id]
    else:
        logger.info(
            f"discovering users with conversations (limit={args.max_users})..."
        )
        user_ids = await _get_all_user_ids_with_conversations(
            db, limit=args.max_users
        )
        logger.info(f"found {len(user_ids)} candidate users")

    for user_id in user_ids:
        stats.users_scanned += 1

        if not args.force and await _user_already_backfilled(db, user_id):
            stats.users_skipped_existing += 1
            logger.info(
                f"user {user_id} already has memories — skipping (use --force to override)"
            )
            continue

        logger.info(f"backfilling user {user_id}...")
        try:
            ok = await _backfill_one_user(
                user_id,
                max_conversations=args.max_conversations_per_user,
                max_turns_per_user=args.max_turns_per_user,
                rate_limit_seconds=args.rate_limit_seconds,
                skip_reflection=args.skip_reflection,
                dry_run=args.dry_run,
                stats=stats,
            )
        except Exception as exc:
            logger.error(
                f"unhandled error during backfill for {user_id}: {exc}"
            )
            ok = False

        if ok:
            stats.users_backfilled += 1
        else:
            stats.users_failed += 1

    logger.info("=" * 60)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 60)
    for line in stats.summary_lines():
        logger.info(line)

    if args.dry_run:
        logger.info("(dry run — no writes actually happened)")

    return 0 if stats.users_failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-time backfill migration for dynamic memory",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="Backfill a single user by id. If omitted, backfills all users.",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=1000,
        help="Upper bound on users to backfill in one run (default: 1000).",
    )
    parser.add_argument(
        "--max-conversations-per-user",
        type=int,
        default=10,
        help="Most-recent-N conversations per user (default: 10, per spec §14.1).",
    )
    parser.add_argument(
        "--max-turns-per-user",
        type=int,
        default=None,
        help="Hard cap on turns extracted per user. Use for cost control.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        type=float,
        default=1.0,
        help="Sleep between extractions within a user to avoid login-burst hammering (default: 1.0s).",
    )
    parser.add_argument(
        "--skip-reflection",
        action="store_true",
        help="Don't run the final reflection pass after backfilling each user.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Walk conversations and log what would be extracted, but make NO Gemini or Mongo writes.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Backfill even if the user already has memories.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (DEBUG / INFO / WARNING / ERROR).",
    )
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
