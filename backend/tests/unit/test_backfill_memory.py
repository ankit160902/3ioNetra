"""Unit tests for the backfill migration helpers.

The backfill script is a one-time migration tool so there's little
testable logic beyond the message-pairing helper and the idempotency
check. Both are covered here.
"""
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Load the script as a module — it's in scripts/ which isn't a package
_script_path = Path(__file__).resolve().parents[2] / "scripts" / "backfill_memory.py"
_spec = importlib.util.spec_from_file_location("backfill_memory", _script_path)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)


class TestPairUserAssistantTurns:
    def test_alternating_user_assistant_pairs_correctly(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "I am sad"},
            {"role": "assistant", "content": "I hear you"},
        ]
        pairs = backfill._pair_user_assistant_turns(messages)
        assert pairs == [
            ("hi", "hello"),
            ("I am sad", "I hear you"),
        ]

    def test_consecutive_user_messages_keeps_latest(self):
        """User types twice before bot responds — only the most recent
        user message gets paired with the bot's eventual response."""
        messages = [
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "reply"},
        ]
        pairs = backfill._pair_user_assistant_turns(messages)
        assert pairs == [("second", "reply")]

    def test_leading_assistant_greeting_is_dropped(self):
        """Bot greets first (no prior user message) — that assistant
        turn has nothing to pair with, so it's dropped."""
        messages = [
            {"role": "assistant", "content": "Namaste, how can I help?"},
            {"role": "user", "content": "I feel stuck"},
            {"role": "assistant", "content": "Tell me more"},
        ]
        pairs = backfill._pair_user_assistant_turns(messages)
        assert pairs == [("I feel stuck", "Tell me more")]

    def test_empty_content_is_skipped(self):
        messages = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "real message"},
            {"role": "assistant", "content": "   "},
            {"role": "assistant", "content": "real response"},
        ]
        pairs = backfill._pair_user_assistant_turns(messages)
        assert pairs == [("real message", "real response")]

    def test_case_insensitive_role(self):
        messages = [
            {"role": "USER", "content": "hi"},
            {"role": "Assistant", "content": "hello"},
        ]
        pairs = backfill._pair_user_assistant_turns(messages)
        assert pairs == [("hi", "hello")]

    def test_empty_messages_returns_empty(self):
        assert backfill._pair_user_assistant_turns([]) == []
        assert backfill._pair_user_assistant_turns(None) == []

    def test_unknown_roles_are_ignored(self):
        messages = [
            {"role": "system", "content": "you are a bot"},
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": "noise"},
            {"role": "assistant", "content": "hello"},
        ]
        pairs = backfill._pair_user_assistant_turns(messages)
        assert pairs == [("hi", "hello")]


class TestUserAlreadyBackfilledIdempotency:
    @pytest.mark.asyncio
    async def test_zero_memories_returns_false(self):
        db = MagicMock()
        db.user_memories.count_documents = MagicMock(return_value=0)
        result = await backfill._user_already_backfilled(db, "u1")
        assert result is False

    @pytest.mark.asyncio
    async def test_nonzero_memories_returns_true(self):
        db = MagicMock()
        db.user_memories.count_documents = MagicMock(return_value=3)
        result = await backfill._user_already_backfilled(db, "u1")
        assert result is True

    @pytest.mark.asyncio
    async def test_mongo_error_returns_false_safely(self):
        """A count_documents failure should not block backfill — return
        False so the user gets processed instead of silently skipped."""
        db = MagicMock()
        db.user_memories.count_documents = MagicMock(
            side_effect=RuntimeError("mongo down")
        )
        result = await backfill._user_already_backfilled(db, "u1")
        assert result is False


class TestBackfillStats:
    def test_summary_lines_all_zero(self):
        stats = backfill.BackfillStats()
        lines = stats.summary_lines()
        assert len(lines) == 11
        for line in lines:
            assert ": " in line

    def test_summary_lines_with_counts(self):
        stats = backfill.BackfillStats(
            users_scanned=5,
            users_backfilled=3,
            facts_extracted=17,
        )
        summary = "\n".join(stats.summary_lines())
        assert "users scanned:          5" in summary
        assert "users backfilled:       3" in summary
        assert "facts extracted:        17" in summary
