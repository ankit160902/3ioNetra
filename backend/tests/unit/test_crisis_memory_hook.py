"""Unit tests for crisis_memory_hook — the bridge between the crisis
detection paths and the RelationalProfile's safety-note layer.

Core invariants this suite protects:
    - NEVER stores verbatim crisis content (only a neutral meta-fact line)
    - Upsert semantics: first crisis for a user creates the profile doc
    - Subsequent crises increment prior_crisis_count
    - Cache invalidation fires after every successful write
    - Anonymous user_id is a clean no-op (never hits Mongo)
    - Dispatch is fire-and-forget and swallows all exceptions
"""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.user_profiles.update_one = MagicMock(
        return_value=MagicMock(modified_count=1, upserted_id=None)
    )
    return db


@pytest.fixture
def hook(monkeypatch, mock_db):
    from services import crisis_memory_hook
    monkeypatch.setattr(crisis_memory_hook, "get_db", lambda: mock_db)

    invalidated = []

    async def fake_invalidate(user_id):
        invalidated.append(user_id)

    monkeypatch.setattr(
        crisis_memory_hook, "_invalidate_profile_cache", fake_invalidate
    )
    crisis_memory_hook._invalidated_spy = invalidated  # type: ignore[attr-defined]
    return crisis_memory_hook


# ---------------------------------------------------------------------------
# TestMetaFactConstruction
# ---------------------------------------------------------------------------

class TestMetaFactConstruction:
    def test_meta_fact_contains_date(self, hook):
        text = hook._build_meta_fact(datetime(2026, 4, 12))
        assert "2026-04-12" in text

    def test_meta_fact_mentions_helplines(self, hook):
        text = hook._build_meta_fact(datetime.utcnow())
        assert "helplines" in text.lower()

    def test_meta_fact_explicitly_notes_no_verbatim(self, hook):
        text = hook._build_meta_fact(datetime.utcnow())
        assert "no verbatim content" in text.lower()

    def test_meta_fact_never_contains_user_input(self, hook):
        """The meta-fact builder takes only a datetime — it has no user
        text input surface, so verbatim content cannot leak by design."""
        import inspect
        sig = inspect.signature(hook._build_meta_fact)
        assert list(sig.parameters.keys()) == ["now"]
        # Also sanity-check: the output contains no user-contributed text
        text = hook._build_meta_fact(datetime(2026, 1, 1))
        forbidden = ["i want", "i can't", "kill", "hurt myself", "die"]
        for word in forbidden:
            assert word not in text.lower()


# ---------------------------------------------------------------------------
# TestWriteCrisisMetaFact
# ---------------------------------------------------------------------------

class TestWriteCrisisMetaFact:
    @pytest.mark.asyncio
    async def test_happy_path_upserts_profile(self, hook, mock_db):
        result = await hook.write_crisis_meta_fact("u1")
        assert result is True
        mock_db.user_profiles.update_one.assert_called_once()

        args = mock_db.user_profiles.update_one.call_args
        filter_arg, update_body = args.args[0], args.args[1]
        assert filter_arg == {"user_id": "u1"}
        assert args.kwargs.get("upsert") is True

        set_doc = update_body["$set"]
        assert set_doc["prior_crisis_flag"] is True
        assert "On " in set_doc["prior_crisis_context"]

        inc_doc = update_body["$inc"]
        assert inc_doc["prior_crisis_count"] == 1

        # upsert insert-only defaults are set on first-ever profile creation
        set_on_insert = update_body["$setOnInsert"]
        assert set_on_insert["user_id"] == "u1"
        assert set_on_insert["importance_since_reflection"] == 0
        # prior_crisis_count must live on $inc, NOT $setOnInsert — otherwise
        # Mongo refuses the update ("Cannot update 'x' and 'x' at the same time")
        assert "prior_crisis_count" not in set_on_insert

    @pytest.mark.asyncio
    async def test_anonymous_user_is_noop(self, hook, mock_db):
        result = await hook.write_crisis_meta_fact("")
        assert result is False
        mock_db.user_profiles.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_unavailable_returns_false(self, monkeypatch):
        from services import crisis_memory_hook
        monkeypatch.setattr(crisis_memory_hook, "get_db", lambda: None)

        async def fake_invalidate(user_id):
            return None

        monkeypatch.setattr(
            crisis_memory_hook, "_invalidate_profile_cache", fake_invalidate
        )
        result = await crisis_memory_hook.write_crisis_meta_fact("u1")
        assert result is False

    @pytest.mark.asyncio
    async def test_mongo_error_returns_false_but_never_raises(
        self, hook, mock_db
    ):
        mock_db.user_profiles.update_one.side_effect = RuntimeError("mongo down")
        result = await hook.write_crisis_meta_fact("u1")
        assert result is False

    @pytest.mark.asyncio
    async def test_successful_write_invalidates_cache(self, hook):
        await hook.write_crisis_meta_fact("u1")
        assert hook._invalidated_spy == ["u1"]

    @pytest.mark.asyncio
    async def test_failed_write_does_not_invalidate_cache(self, hook, mock_db):
        mock_db.user_profiles.update_one.side_effect = RuntimeError("mongo down")
        await hook.write_crisis_meta_fact("u1")
        assert hook._invalidated_spy == []

    @pytest.mark.asyncio
    async def test_multiple_writes_stack_via_inc(self, hook, mock_db):
        """Each call bumps the counter — no dedup. Three crisis messages
        produce three $inc calls (MongoDB atomically sums)."""
        await hook.write_crisis_meta_fact("u1")
        await hook.write_crisis_meta_fact("u1")
        await hook.write_crisis_meta_fact("u1")
        assert mock_db.user_profiles.update_one.call_count == 3
        for call in mock_db.user_profiles.update_one.call_args_list:
            body = call.args[1]
            assert body["$inc"]["prior_crisis_count"] == 1


# ---------------------------------------------------------------------------
# TestDispatch
# ---------------------------------------------------------------------------

class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_schedules_background_task(self, hook, mock_db):
        dispatched = []
        orig_create_task = asyncio.create_task

        def capture(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched.append(task)
            return task

        import services.crisis_memory_hook as cmh
        cmh.asyncio.create_task = capture
        try:
            hook.dispatch_crisis_meta_fact("u1")
            assert len(dispatched) == 1
            await dispatched[0]
            mock_db.user_profiles.update_one.assert_called_once()
        finally:
            cmh.asyncio.create_task = orig_create_task

    @pytest.mark.asyncio
    async def test_dispatch_with_empty_user_is_noop(self, hook, mock_db):
        dispatched = []
        orig_create_task = asyncio.create_task

        def capture(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched.append(task)
            return task

        import services.crisis_memory_hook as cmh
        cmh.asyncio.create_task = capture
        try:
            hook.dispatch_crisis_meta_fact("")
            hook.dispatch_crisis_meta_fact(None)
            assert dispatched == []
            mock_db.user_profiles.update_one.assert_not_called()
        finally:
            cmh.asyncio.create_task = orig_create_task

    @pytest.mark.asyncio
    async def test_dispatch_swallows_write_exceptions(self, hook, mock_db):
        """Even if the entire write path raises, dispatch never propagates."""
        mock_db.user_profiles.update_one.side_effect = RuntimeError("boom")

        dispatched = []
        orig_create_task = asyncio.create_task

        def capture(coro, *args, **kwargs):
            task = orig_create_task(coro, *args, **kwargs)
            dispatched.append(task)
            return task

        import services.crisis_memory_hook as cmh
        cmh.asyncio.create_task = capture
        try:
            # Must NOT raise in the caller's frame
            hook.dispatch_crisis_meta_fact("u1")
            # Awaiting the underlying task must also not re-raise
            assert len(dispatched) == 1
            await dispatched[0]
        finally:
            cmh.asyncio.create_task = orig_create_task
