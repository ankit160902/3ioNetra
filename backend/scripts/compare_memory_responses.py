"""Dev smoke tool for the dynamic memory system (Tier 4 per spec §13.4).

Runs a scripted multi-turn conversation against the live memory pipeline
and, after each turn, dumps what the memory system thinks it has learned
about the user: the current relational profile, the top-k episodic
memories retrieved for the NEXT turn, the new extractions dispatched in
the background, and the Mem0 decisions made on those extractions.

This is NOT a test. It is a human-eyeball utility for verifying that
long-conversation memory behavior feels right — that the profile
evolves sensibly across turns, that retrieval surfaces the right facts
when the user circles back to an earlier topic, that contradictions
are handled gracefully, etc. The developer reviews the dump and
decides if it looks right.

What the script needs in the environment:
    GEMINI_API_KEY         — required; real Gemini calls happen here
    MONGODB_URI            — required; real Mongo writes happen here
    DATABASE_NAME          — required
    REDIS_HOST / PORT      — optional; without Redis the cache paths
                             fall through to Mongo (slower but fine)

Usage:
    python scripts/compare_memory_responses.py
    python scripts/compare_memory_responses.py --user-id smoke_test_001
    python scripts/compare_memory_responses.py --script custom_script.py
    python scripts/compare_memory_responses.py --wipe-first

The default conversation walks the user through a typical arc — work
stress → deeper life concern → grief mention → evolution → practical
question. Each turn exercises a different response mode and a
different memory pathway. You can supply your own by pointing
``--script`` at a Python file that exports a ``CONVERSATION`` list of
user messages.

WARNING: This script writes to your real MongoDB. Use ``--wipe-first``
to clear all memories + profile for the smoke user before starting,
or point ``--user-id`` at a dedicated test user.
"""
import argparse
import asyncio
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make backend/ importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


_DEFAULT_CONVERSATION = [
    "Hi, I'm feeling a bit overwhelmed with work lately",
    "Yes, my boss keeps piling deadlines on me and I barely sleep",
    "I keep asking myself what the point is — I used to love this job",
    "My father died last year and I think I never really grieved him",
    "How do I honor him through a small daily practice?",
    "Thank you — that feels right",
]


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _header(text: str) -> str:
    line = "═" * 74
    return f"\n{_color(line, '1;36')}\n{_color(text, '1;36')}\n{_color(line, '1;36')}"


def _subheader(text: str) -> str:
    return f"\n{_color('── ' + text + ' ──', '1;33')}"


def _dim(text: str) -> str:
    return _color(text, '2')


def _load_custom_script(path: str) -> List[str]:
    spec = importlib.util.spec_from_file_location("custom_script", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    conversation = getattr(mod, "CONVERSATION", None)
    if not isinstance(conversation, list) or not all(
        isinstance(m, str) for m in conversation
    ):
        raise ValueError(
            f"{path} must export a CONVERSATION list of strings"
        )
    return conversation


async def _wipe_user(user_id: str) -> None:
    """Clear user_memories + user_profiles for this user. Destructive."""
    from services.auth_service import get_mongo_client

    db = get_mongo_client()
    if db is None:
        print("⚠ MongoDB unavailable — cannot wipe")
        return
    mem_result = db.user_memories.delete_many({"user_id": user_id})
    prof_result = db.user_profiles.delete_many({"user_id": user_id})
    print(
        f"⚠ Wiped {mem_result.deleted_count} memories and "
        f"{prof_result.deleted_count} profiles for user={user_id}"
    )


async def _load_profile_dump(user_id: str) -> Dict[str, Any]:
    """Load the raw profile from Mongo (not through the cache) so we
    see what the reflection pipeline has actually written."""
    from services.auth_service import get_mongo_client

    db = get_mongo_client()
    if db is None:
        return {"_error": "mongo unavailable"}
    doc = db.user_profiles.find_one({"user_id": user_id})
    if not doc:
        return {"_empty": True}

    return {
        "relational_narrative": doc.get("relational_narrative", ""),
        "spiritual_themes": doc.get("spiritual_themes", []),
        "ongoing_concerns": doc.get("ongoing_concerns", []),
        "tone_preferences": doc.get("tone_preferences", []),
        "people_mentioned": doc.get("people_mentioned", []),
        "prior_crisis_flag": doc.get("prior_crisis_flag", False),
        "prior_crisis_count": doc.get("prior_crisis_count", 0),
        "importance_since_reflection": doc.get("importance_since_reflection", 0),
        "reflection_count": doc.get("reflection_count", 0),
        "last_reflection_at": (
            doc["last_reflection_at"].isoformat()
            if doc.get("last_reflection_at")
            else None
        ),
    }


async def _load_all_memories(user_id: str) -> List[Dict[str, Any]]:
    from services.auth_service import get_mongo_client

    db = get_mongo_client()
    if db is None:
        return []
    cursor = (
        db.user_memories.find(
            {"user_id": user_id},
            {
                "text": 1, "importance": 1, "sensitivity": 1,
                "tone_marker": 1, "valid_at": 1, "invalid_at": 1,
                "source": 1, "access_count": 1,
            },
        )
        .sort([("valid_at", -1), ("created_at", -1)])
    )
    out = []
    for doc in cursor:
        out.append(
            {
                "id": str(doc.get("_id", "")),
                "text": doc.get("text", ""),
                "importance": doc.get("importance", 5),
                "sensitivity": doc.get("sensitivity", "personal"),
                "tone_marker": doc.get("tone_marker", "neutral"),
                "source": doc.get("source", ""),
                "valid": doc.get("invalid_at") is None,
                "access_count": int(doc.get("access_count", 0) or 0),
            }
        )
    return out


async def _retrieve_top_k(
    user_id: str,
    query: str,
    response_mode: str,
    session: Any,
) -> List[Dict[str, Any]]:
    """Call the reader directly and return a JSON-friendly dump of the
    top-k scored memories it surfaces for this turn's query."""
    from services import memory_reader

    analysis = {"emotion": "neutral", "response_mode": response_mode}
    try:
        result = await memory_reader.load_and_retrieve(
            user_id=user_id,
            query=query,
            response_mode=response_mode,
            analysis=analysis,
            session=session,
        )
    except Exception as exc:
        return [{"_error": f"{type(exc).__name__}: {exc}"}]

    return [
        {
            "text": sm.memory.get("text", ""),
            "score": round(sm.score, 3),
            "importance": sm.memory.get("importance", 5),
            "sensitivity": sm.memory.get("sensitivity", "personal"),
        }
        for sm in result.episodic
    ]


async def _run_turn(
    turn_num: int,
    user_message: str,
    user_id: str,
    session: Any,
) -> None:
    """Simulate one turn: build a simulated assistant response, fire
    extraction, wait for it to complete, then dump the post-turn state."""
    from services import memory_extractor

    print(_header(f"TURN {turn_num}"))
    print(f"{_color('USER', '1;32')}:  {user_message}")

    # Retrieve what the system would surface for this turn
    retrieval_dump = await _retrieve_top_k(
        user_id=user_id,
        query=user_message,
        response_mode="exploratory",
        session=session,
    )
    print(_subheader("retrieved top-k before response"))
    if not retrieval_dump:
        print(_dim("  (empty — mode gate OR nothing above score floor)"))
    else:
        for sm in retrieval_dump:
            if "_error" in sm:
                print(_dim(f"  error: {sm['_error']}"))
            else:
                print(
                    f"  score={sm['score']:.3f} imp={sm['importance']} "
                    f"{sm['sensitivity']}: {sm['text']}"
                )

    # Synthesize a minimal assistant response that would plausibly elicit
    # memory-worthy facts without needing to run the full LLM stream.
    assistant_response = (
        "I hear you. Thank you for sharing that with me. Tell me a little "
        "more about what's been on your heart."
    )
    print(f"\n{_color('MITRA', '1;35')}: {_dim('(simulated — actual stream would be a full response here)')}")
    print(_dim("  " + assistant_response))

    # Fire the extraction pipeline and await it to completion. In
    # production this is fire-and-forget, but for smoke inspection we
    # block on it so we can dump the result synchronously.
    print(_subheader("extraction + mem0 decision"))
    try:
        result = await memory_extractor.extract_memories(
            user_id=user_id,
            session_id=session.session_id,
            conversation_id=None,
            turn_number=turn_num,
            user_message=user_message,
            assistant_response=assistant_response,
            relational_profile_text="",
        )
    except Exception as exc:
        print(_dim(f"  extraction error: {type(exc).__name__}: {exc}"))
        return

    if not result.facts:
        print(_dim("  (zero facts extracted — common for greetings / clarifications)"))
    else:
        for i, fact in enumerate(result.facts, 1):
            print(
                f"  [{i}] imp={fact.importance} "
                f"{fact.sensitivity}/{fact.tone_marker}: {fact.text}"
            )

    if result.facts:
        from services import memory_writer

        try:
            decisions = await memory_writer.update_memories_from_extraction(
                user_id=user_id,
                session_id=session.session_id,
                conversation_id=None,
                turn_number=turn_num,
                extraction=result,
            )
            for i, d in enumerate(decisions, 1):
                reason = f" — {d.reason}" if d.reason else ""
                target = f" target={d.target_memory_id}" if d.target_memory_id else ""
                print(_dim(f"  -> decision [{i}]: {d.operation}{target}{reason}"))
        except Exception as exc:
            print(_dim(f"  writer error: {type(exc).__name__}: {exc}"))

    # Dump the updated profile state
    print(_subheader("profile after turn"))
    profile = await _load_profile_dump(user_id)
    print(_dim(json.dumps(profile, indent=2, default=str)))

    # And the full memory ledger
    memories = await _load_all_memories(user_id)
    print(_subheader(f"memory ledger ({len(memories)} rows)"))
    for m in memories:
        tag = "✓" if m["valid"] else "✗ invalidated"
        print(
            f"  [{tag}] imp={m['importance']} {m['sensitivity']}/"
            f"{m['tone_marker']} src={m['source']} access={m['access_count']}: "
            f"{m['text']}"
        )


async def _main_async(args: argparse.Namespace) -> int:
    from models.session import SessionState
    from models.memory_context import ConversationMemory, UserStory

    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not set — live Gemini calls are required")
        return 2

    if args.wipe_first:
        await _wipe_user(args.user_id)

    if args.script:
        conversation = _load_custom_script(args.script)
    else:
        conversation = _DEFAULT_CONVERSATION

    # Minimal session — the reader only reads session.turn_count + user_id
    session = SessionState()
    session.memory = ConversationMemory(story=UserStory())
    session.memory.user_id = args.user_id
    session.session_id = f"smoke_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    print(_header("3ioNetra Memory Smoke Test"))
    print(f"  user_id:    {args.user_id}")
    print(f"  session_id: {session.session_id}")
    print(f"  turns:      {len(conversation)}")
    print(f"  gemini:     {os.environ.get('GEMINI_MODEL', 'default')}")

    for i, msg in enumerate(conversation, 1):
        session.turn_count = i
        await _run_turn(
            turn_num=i,
            user_message=msg,
            user_id=args.user_id,
            session=session,
        )

    print(_header("smoke complete"))
    print(_dim("Review the dumps above. Good signals to look for:"))
    print(_dim("  • Profile narrative evolves — not identical across turns"))
    print(_dim("  • Retrieval surfaces the right memory when user circles back"))
    print(_dim("  • Importance scores match your gut (grief ~8-9, work stress ~5-6)"))
    print(_dim("  • No verbatim crisis content anywhere in profile.prior_crisis_context"))
    print(_dim("  • Sensitive memories tagged with appropriate tone_marker"))
    print(_dim("  • Contradictions show up as UPDATE not ADD (one fresh + one invalidated)"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dev smoke tool for the dynamic memory pipeline",
    )
    parser.add_argument(
        "--user-id",
        default="memory_smoke_test",
        help="User id to run the smoke conversation against.",
    )
    parser.add_argument(
        "--script",
        default=None,
        help=(
            "Python file exporting a CONVERSATION list of user messages. "
            "If omitted, uses the built-in 6-turn script."
        ),
    )
    parser.add_argument(
        "--wipe-first",
        action="store_true",
        help="Delete all memories + profile for the user BEFORE running.",
    )
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
