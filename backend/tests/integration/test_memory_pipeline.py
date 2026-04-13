"""Integration tests for the dynamic memory system (mocked pipeline).

Tier 2 from spec §13.2 — exercises the full turn flow end-to-end with
mocked LLM + mocked embeddings + an in-memory FakeMongoDB that behaves
realistically enough to catch query-shape bugs that isolated unit tests
miss. No live Gemini, no real Mongo, no Redis — these tests run in the
default CI.

Scenarios protected:
    - Full turn flow: extraction fires post-response → Mem0 decision →
      user_memories populated → next turn's MemoryReader surfaces the
      new fact in the LLM prompt
    - Mode gating end-to-end: practical_first skips episodic retrieval
      but extraction STILL runs (memories are still being written, just
      not surfaced this turn)
    - Crisis path: crisis short-circuit fires the meta-fact hook,
      user_profiles gets prior_crisis_flag=True, and user_memories
      receives ZERO writes for that turn
    - Bi-temporal UPDATE: superseded memory sets invalid_at, the new
      merged text becomes a fresh row — old record is preserved

These tests are deliberately written against the FakeMongoDB rather
than real Mongo so they run fast and deterministically. The FakeMongoDB
implements just enough of the pymongo.collection API to satisfy the
memory pipeline's queries — see ``FakeMongoDB`` docstring for the full
surface covered.
"""
import asyncio
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

# Ensure backend/ is on sys.path for `from services import ...` to work
# when pytest is invoked from the repo root or from backend/.
_backend_dir = Path(__file__).resolve().parents[2]
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Stub transitions module — same reason as the unit-test stub in
# tests/unit/conftest.py. conversation_fsm imports `from transitions
# import Machine` which isn't installed in the test environment.
if "transitions" not in sys.modules:
    _stub = types.ModuleType("transitions")

    class _StubMachine:
        def __init__(self, *args, **kwargs):
            pass

        def add_transition(self, *args, **kwargs):
            pass

    _stub.Machine = _StubMachine
    sys.modules["transitions"] = _stub


# ---------------------------------------------------------------------------
# FakeMongoDB — minimal stateful pymongo substitute
# ---------------------------------------------------------------------------

class _FakeUpdateResult:
    def __init__(self, matched: int = 0, modified: int = 0, upserted_id=None):
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = upserted_id


class _FakeInsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _FakeDeleteResult:
    def __init__(self, deleted: int = 0):
        self.deleted_count = deleted


class _FakeCursor:
    """Mimics a pymongo cursor — supports .sort().limit() chaining and
    iteration via list()."""

    def __init__(self, docs: List[Dict]):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):
        # Best-effort: sort by valid_at desc if the test asks for it.
        # Tests that care about ordering should sort their expectations
        # independently; we return self for chain compatibility.
        try:
            if args and isinstance(args[0], list):
                sort_key, direction = args[0][0]
                self._docs.sort(
                    key=lambda d: d.get(sort_key) or datetime.min,
                    reverse=(direction == -1),
                )
        except Exception:
            pass
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)

    def to_list(self, length=None):
        return list(self._docs[:length] if length else self._docs)


class _FakeCollection:
    """Minimal pymongo Collection shim backed by an in-memory dict store.

    Uses real ``bson.ObjectId`` for `_id` so code that round-trips through
    ``str(id)`` + ``ObjectId(raw)`` (e.g. memory_writer's UPDATE path)
    works end-to-end. _match supports $in, $lt, $ne operator queries —
    enough for the memory pipeline's query shapes.
    """

    def __init__(self):
        self._docs: List[Dict] = []

    def _match(self, doc: Dict, query: Dict) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                # Operator queries: $in, $lt, $ne
                for op, op_val in expected.items():
                    if op == "$in":
                        if actual not in op_val:
                            return False
                    elif op == "$lt":
                        if actual is None or not actual < op_val:
                            return False
                    elif op == "$ne":
                        if actual == op_val:
                            return False
                    else:
                        raise NotImplementedError(
                            f"FakeCollection doesn't support operator {op!r}"
                        )
            else:
                if actual != expected:
                    return False
        return True

    def _apply_update(self, doc: Dict, update: Dict) -> None:
        for op, body in update.items():
            if op == "$set":
                doc.update(body)
            elif op == "$inc":
                for k, delta in body.items():
                    doc[k] = int(doc.get(k, 0) or 0) + int(delta)
            elif op == "$setOnInsert":
                # Only applied during upsert insert path — never to existing docs
                pass
            else:
                raise NotImplementedError(
                    f"FakeCollection doesn't support update op {op!r}"
                )

    def insert_one(self, doc: Dict) -> _FakeInsertResult:
        if "_id" not in doc:
            from bson import ObjectId
            doc["_id"] = ObjectId()
        self._docs.append(dict(doc))  # shallow copy to prevent caller mutation
        return _FakeInsertResult(doc["_id"])

    def find(self, query: Optional[Dict] = None, projection=None) -> _FakeCursor:
        query = query or {}
        matching = [dict(d) for d in self._docs if self._match(d, query)]
        return _FakeCursor(matching)

    def find_one(self, query: Optional[Dict] = None, projection=None):
        query = query or {}
        for d in self._docs:
            if self._match(d, query):
                return dict(d)
        return None

    def update_one(self, filter: Dict, update: Dict, upsert: bool = False) -> _FakeUpdateResult:
        for d in self._docs:
            if self._match(d, filter):
                self._apply_update(d, update)
                return _FakeUpdateResult(matched=1, modified=1)
        if upsert:
            new_doc: Dict = {}
            # $setOnInsert seed
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            # $set applies too
            if "$set" in update:
                new_doc.update(update["$set"])
            # $inc initializes counters
            if "$inc" in update:
                for k, v in update["$inc"].items():
                    new_doc[k] = int(v)
            # Filter equality fields become seed values
            for k, v in filter.items():
                if not isinstance(v, dict) and k not in new_doc:
                    new_doc[k] = v
            from bson import ObjectId
            new_doc["_id"] = ObjectId()
            self._docs.append(new_doc)
            return _FakeUpdateResult(matched=0, modified=0, upserted_id=new_doc["_id"])
        return _FakeUpdateResult()

    def update_many(self, filter: Dict, update: Dict) -> _FakeUpdateResult:
        modified = 0
        for d in self._docs:
            if self._match(d, filter):
                self._apply_update(d, update)
                modified += 1
        return _FakeUpdateResult(matched=modified, modified=modified)

    def delete_one(self, filter: Dict) -> _FakeDeleteResult:
        for i, d in enumerate(self._docs):
            if self._match(d, filter):
                del self._docs[i]
                return _FakeDeleteResult(deleted=1)
        return _FakeDeleteResult()

    def count_documents(self, query: Optional[Dict] = None) -> int:
        return sum(1 for d in self._docs if self._match(d, query or {}))

    def create_index(self, *args, **kwargs):
        # No-op — real index creation is a pymongo-only concern
        pass


class FakeMongoDB:
    """Dict-of-collections shim. Each attribute access creates a new
    ``_FakeCollection`` on demand so code like ``db.user_memories.find(...)``
    works without pre-declaration. This mirrors pymongo's behavior where
    accessing a nonexistent collection silently creates it.
    """

    def __init__(self):
        self._collections: Dict[str, _FakeCollection] = {}

    def __getattr__(self, name: str) -> _FakeCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


# ---------------------------------------------------------------------------
# Fixture — wire all the memory modules at the dynamic-memory boundary
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_db():
    return FakeMongoDB()


@pytest.fixture
def fake_rag():
    rag = MagicMock()
    # Every embedding is the same vector — the scoring test doesn't
    # depend on semantic similarity, just that retrieval works.
    rag.generate_embeddings = AsyncMock(
        return_value=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    )
    return rag


@pytest.fixture
def fake_llm():
    """Stubbed LLMService. Individual tests override complete_json to
    return canned extraction / decision / reflection JSON."""
    svc = MagicMock()
    svc.available = True
    svc.complete_json = AsyncMock(return_value='{"facts": []}')
    return svc


@pytest.fixture
def fake_prompt_manager():
    pm = MagicMock()

    def _get_prompt(group, key, default=""):
        # Return a template-like string that .format() can handle. The
        # reflection and decision prompts have different placeholder
        # names, so we return a format string that accepts any kwargs
        # via defaultdict-style tolerance. Simplest: use a template
        # that contains only trivial placeholders.
        if "extract" in key:
            return (
                "Context: {relational_profile_text}\n"
                "Turn {turn_number} session {session_id}\n"
                "USER: {user_message}\n"
                "MITRA: {assistant_response}"
            )
        if "update_decision" in key:
            return (
                "NEW: {new_fact_text}/{new_fact_importance}/"
                "{new_fact_sensitivity}/{new_fact_tone}\n"
                "SIM: {similar_memories_block}"
            )
        if "reflect" in key:
            return (
                "PROFILE: {current_profile_text}\n"
                "MEMS: {memories_block}"
            )
        return ""

    pm.get_prompt = MagicMock(side_effect=_get_prompt)
    return pm


@pytest.fixture
def wired_memory(monkeypatch, fake_db, fake_rag, fake_llm, fake_prompt_manager):
    """Monkeypatch every lazy accessor across the dynamic memory modules
    so they all point at the same fake backing stores."""
    from services import memory_extractor, memory_writer, memory_reader
    from services import reflection_service, crisis_memory_hook
    from routers import dependencies as router_deps

    # memory_extractor uses get_llm_service + get_prompt_manager
    monkeypatch.setattr(memory_extractor, "get_llm_service", lambda: fake_llm)
    monkeypatch.setattr(
        memory_extractor, "get_prompt_manager", lambda: fake_prompt_manager
    )

    # memory_writer uses all four
    monkeypatch.setattr(memory_writer, "get_llm_service", lambda: fake_llm)
    monkeypatch.setattr(
        memory_writer, "get_prompt_manager", lambda: fake_prompt_manager
    )
    monkeypatch.setattr(memory_writer, "get_rag_pipeline", lambda: fake_rag)
    monkeypatch.setattr(memory_writer, "get_db", lambda: fake_db)

    # memory_reader uses get_db, get_cache_service, get_rag_pipeline
    monkeypatch.setattr(memory_reader, "get_db", lambda: fake_db)
    monkeypatch.setattr(memory_reader, "get_rag_pipeline", lambda: fake_rag)
    # No Redis in tests — cache returns nothing, set is a no-op
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value=None)
    fake_cache.set = AsyncMock(return_value=None)
    fake_cache.flush_prefix = AsyncMock(return_value=0)
    monkeypatch.setattr(memory_reader, "get_cache_service", lambda: fake_cache)

    # reflection_service uses get_llm_service, get_prompt_manager, get_db
    monkeypatch.setattr(
        reflection_service, "get_llm_service", lambda: fake_llm
    )
    monkeypatch.setattr(
        reflection_service, "get_prompt_manager", lambda: fake_prompt_manager
    )
    monkeypatch.setattr(reflection_service, "get_db", lambda: fake_db)

    # crisis_memory_hook uses get_db
    monkeypatch.setattr(crisis_memory_hook, "get_db", lambda: fake_db)

    # routers.dependencies.get_rag_pipeline — used by the /api/memory router
    monkeypatch.setattr(router_deps, "get_rag_pipeline", lambda: fake_rag)

    return {
        "db": fake_db,
        "rag": fake_rag,
        "llm": fake_llm,
        "prompt_manager": fake_prompt_manager,
        "cache": fake_cache,
        "memory_extractor": memory_extractor,
        "memory_writer": memory_writer,
        "memory_reader": memory_reader,
        "reflection_service": reflection_service,
        "crisis_memory_hook": crisis_memory_hook,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extraction_response(
    text: str = "User is a software engineer",
    importance: int = 6,
    sensitivity: str = "personal",
    tone_marker: str = "neutral",
) -> str:
    return (
        f'{{"facts": [{{"text": "{text}", "importance": {importance}, '
        f'"sensitivity": "{sensitivity}", "tone_marker": "{tone_marker}"}}]}}'
    )


def _add_decision() -> str:
    return (
        '{"operation": "ADD", "target_memory_id": null, '
        '"updated_text": null, "reason": "new fact"}'
    )


def _update_decision(target_id: str, merged: str) -> str:
    return (
        f'{{"operation": "UPDATE", "target_memory_id": "{target_id}", '
        f'"updated_text": "{merged}", "reason": "evolved"}}'
    )


def _make_session(
    user_id: str = "u1",
    turn_count: int = 3,
    session_id: str = "s1",
    response_mode: str = "exploratory",
):
    s = MagicMock()
    s.session_id = session_id
    s.turn_count = turn_count
    s.memory = MagicMock()
    s.memory.user_id = user_id
    return s


async def _extraction_only(wired, fact_text: str, importance: int = 6) -> None:
    """Run a full extract + update cycle for one user message. Returns
    after the update decision has been executed on the fake db."""
    wired["llm"].complete_json = AsyncMock(
        side_effect=[
            _extraction_response(text=fact_text, importance=importance),
            _add_decision(),
        ]
    )
    from models.llm_schemas import ExtractionResult, ExtractedMemory

    result = await wired["memory_extractor"].extract_memories(
        user_id="u1",
        session_id="s1",
        conversation_id="c1",
        turn_number=1,
        user_message="tell me something",
        assistant_response="here is wisdom",
        relational_profile_text="",
    )
    assert len(result.facts) == 1
    await wired["memory_writer"].update_memories_from_extraction(
        user_id="u1",
        session_id="s1",
        conversation_id="c1",
        turn_number=1,
        extraction=result,
    )


# ---------------------------------------------------------------------------
# Scenario 1 — Full turn flow: extract → store → next turn retrieves it
# ---------------------------------------------------------------------------

class TestFullTurnFlow:
    @pytest.mark.asyncio
    async def test_extraction_then_next_turn_reader_surfaces_fact(self, wired_memory):
        """Extract a fact on turn 1, then on turn 2 the MemoryReader
        should surface it as an episodic memory in the load_and_retrieve
        result."""
        wired = wired_memory

        # Turn 1: extract + store
        await _extraction_only(wired, fact_text="User is a software engineer")

        # Verify one memory landed in user_memories
        stored = wired["db"].user_memories.find_one({"user_id": "u1"})
        assert stored is not None
        assert stored["text"] == "User is a software engineer"
        assert stored["sensitivity"] == "personal"
        assert stored["source"] == "extracted"
        assert stored["invalid_at"] is None

        # Turn 2: simulate a reader query (teaching mode → runs retrieval)
        session = _make_session(turn_count=2)
        read_result = await wired["memory_reader"].load_and_retrieve(
            user_id="u1",
            query="what do you remember about my work?",
            response_mode="teaching",
            analysis={"emotion": "curiosity"},
            session=session,
        )
        # Reader should surface the memory we just stored
        assert len(read_result.episodic) >= 1
        retrieved = read_result.episodic[0].memory
        assert retrieved["text"] == "User is a software engineer"

    @pytest.mark.asyncio
    async def test_importance_counter_accumulates_across_turns(self, wired_memory):
        """Each ADD bumps user_profiles.importance_since_reflection by
        the fact's importance. Three ADDs → counter = sum of importances."""
        wired = wired_memory

        for fact, imp in [
            ("User is a software engineer", 5),
            ("User is grieving father", 8),
            ("User meditates daily", 4),
        ]:
            await _extraction_only(wired, fact_text=fact, importance=imp)

        profile = wired["db"].user_profiles.find_one({"user_id": "u1"})
        assert profile is not None
        assert profile["importance_since_reflection"] == 5 + 8 + 4


# ---------------------------------------------------------------------------
# Scenario 2 — Mode gating: retrieval skips but extraction still runs
# ---------------------------------------------------------------------------

class TestModeGating:
    @pytest.mark.asyncio
    async def test_practical_first_skips_retrieval(self, wired_memory):
        """practical_first response mode must NOT touch episodic retrieval
        regardless of what's in the DB."""
        wired = wired_memory
        await _extraction_only(wired, fact_text="User is a software engineer")

        session = _make_session(turn_count=5)
        result = await wired["memory_reader"].load_and_retrieve(
            user_id="u1",
            query="how do I prepare for my interview",
            response_mode="practical_first",
            analysis={"emotion": "neutral"},
            session=session,
        )
        assert result.episodic == []

    @pytest.mark.asyncio
    async def test_practical_first_still_allows_extraction(self, wired_memory):
        """Mode gating skips READER retrieval but WRITER still runs —
        memories are still being written for future turns. Verify by
        running extraction and then reading back in a different mode."""
        wired = wired_memory
        await _extraction_only(wired, fact_text="User loves mornings")

        # Read in practical_first (no retrieval)
        session = _make_session(turn_count=5)
        r_practical = await wired["memory_reader"].load_and_retrieve(
            user_id="u1",
            query="how to wake up earlier",
            response_mode="practical_first",
            analysis={"emotion": "neutral"},
            session=session,
        )
        assert r_practical.episodic == []

        # But the memory IS in the DB — a teaching-mode read retrieves it
        r_teaching = await wired["memory_reader"].load_and_retrieve(
            user_id="u1",
            query="what do I enjoy about mornings?",
            response_mode="teaching",
            analysis={"emotion": "curiosity"},
            session=session,
        )
        assert len(r_teaching.episodic) == 1

    @pytest.mark.asyncio
    async def test_early_presence_first_skips(self, wired_memory):
        """presence_first on turns ≤ 2 skips retrieval (user needs
        presence, not receipts)."""
        wired = wired_memory
        await _extraction_only(wired, fact_text="User is grieving")

        session = _make_session(turn_count=1)
        r = await wired["memory_reader"].load_and_retrieve(
            user_id="u1",
            query="i miss him so much",
            response_mode="presence_first",
            analysis={"emotion": "grief"},
            session=session,
        )
        assert r.episodic == []

    @pytest.mark.asyncio
    async def test_late_presence_first_runs(self, wired_memory):
        """presence_first on turn > 2 does run retrieval."""
        wired = wired_memory
        # Pre-populate a sensitive grief memory (tone-aligned)
        await _extraction_only(wired, fact_text="User is grieving father")
        # Mark the memory as sensitive + grief tone so tone filter aligns
        wired["db"].user_memories._docs[0]["sensitivity"] = "sensitive"
        wired["db"].user_memories._docs[0]["tone_marker"] = "grief"

        session = _make_session(turn_count=5)
        r = await wired["memory_reader"].load_and_retrieve(
            user_id="u1",
            query="i still feel heavy about him",
            response_mode="presence_first",
            analysis={"emotion": "grief"},
            session=session,
        )
        # Turn > 2 AND tone-aligned → retrieval runs and returns the memory
        assert len(r.episodic) == 1


# ---------------------------------------------------------------------------
# Scenario 3 — Crisis path: meta-fact hook fires, no verbatim writes
# ---------------------------------------------------------------------------

class TestCrisisPath:
    @pytest.mark.asyncio
    async def test_crisis_hook_sets_profile_flag(self, wired_memory):
        """The crisis hook is a fire-and-forget MongoDB write that flips
        prior_crisis_flag, increments the count, and stores a neutral
        meta-fact (never verbatim user words)."""
        wired = wired_memory

        await wired["crisis_memory_hook"].write_crisis_meta_fact("u1")

        profile = wired["db"].user_profiles.find_one({"user_id": "u1"})
        assert profile is not None
        assert profile["prior_crisis_flag"] is True
        assert profile["prior_crisis_count"] == 1
        # Meta-fact must NOT contain verbatim suicidal ideation, self-harm
        # phrases, or user's actual words — it's date-stamped generic text
        meta_fact = profile["prior_crisis_context"]
        assert "helplines" in meta_fact.lower()
        assert "no verbatim" in meta_fact.lower()
        forbidden = ["kill", "die", "hurt myself", "end it", "suicide"]
        for word in forbidden:
            assert word not in meta_fact.lower(), (
                f"Crisis meta-fact must never contain {word!r}"
            )

    @pytest.mark.asyncio
    async def test_crisis_path_does_not_write_to_user_memories(self, wired_memory):
        """Crisis turns must bypass the regular extraction pipeline.
        user_memories stays empty even after the crisis hook fires."""
        wired = wired_memory
        await wired["crisis_memory_hook"].write_crisis_meta_fact("u1")

        # user_memories count stays at 0
        assert wired["db"].user_memories.count_documents({"user_id": "u1"}) == 0

    @pytest.mark.asyncio
    async def test_crisis_tier_extraction_is_filtered_by_writer(self, wired_memory):
        """Even if the extraction pipeline is tricked into producing a
        crisis-tier fact, the writer's sensitivity filter rejects it
        before any user_memories write."""
        wired = wired_memory
        from models.llm_schemas import ExtractionResult, ExtractedMemory

        crisis_extraction = ExtractionResult(
            facts=[
                ExtractedMemory(
                    text="PLACEHOLDER crisis fact", importance=10,
                    sensitivity="crisis", tone_marker="despair",
                )
            ]
        )
        decisions = await wired["memory_writer"].update_memories_from_extraction(
            user_id="u1", session_id="s1", conversation_id=None,
            turn_number=1, extraction=crisis_extraction,
        )
        assert decisions == []
        # No writes happened
        assert wired["db"].user_memories.count_documents({}) == 0
        assert wired["db"].user_profiles.count_documents({}) == 0


# ---------------------------------------------------------------------------
# Scenario 4 — Bi-temporal UPDATE preserves the old record
# ---------------------------------------------------------------------------

class TestBiTemporalUpdate:
    @pytest.mark.asyncio
    async def test_update_invalidates_old_and_inserts_new(self, wired_memory):
        """UPDATE operation must set invalid_at on the target AND insert
        the merged text as a new row. Nothing is ever hard-deleted."""
        wired = wired_memory

        # Turn 1: initial memory
        await _extraction_only(wired, fact_text="User is grieving father")
        original = wired["db"].user_memories.find_one({"user_id": "u1"})
        original_id = original["_id"]

        # Turn 2: evolved fact — updater emits UPDATE
        wired["llm"].complete_json = AsyncMock(
            side_effect=[
                _extraction_response(
                    text="User is slowly healing",
                    importance=7,
                    sensitivity="sensitive",
                    tone_marker="healing",
                ),
                _update_decision(
                    target_id=str(original_id),
                    merged="User is slowly healing from father's death",
                ),
            ]
        )
        from models.llm_schemas import ExtractionResult

        result = await wired["memory_extractor"].extract_memories(
            user_id="u1", session_id="s2", conversation_id="c2",
            turn_number=2, user_message="I'm finally feeling lighter",
            assistant_response="That is grace returning", relational_profile_text="",
        )
        await wired["memory_writer"].update_memories_from_extraction(
            user_id="u1", session_id="s2", conversation_id="c2",
            turn_number=2, extraction=result,
        )

        # Original is still there, but now has invalid_at set
        old = next(
            d for d in wired["db"].user_memories._docs if d["_id"] == original_id
        )
        assert old["invalid_at"] is not None, (
            "Old memory must be soft-invalidated, not removed"
        )
        assert old["text"] == "User is grieving father"  # Unchanged

        # And there's a NEW row with the merged text
        merged = [
            d for d in wired["db"].user_memories._docs
            if d["text"] == "User is slowly healing from father's death"
        ]
        assert len(merged) == 1
        assert merged[0]["invalid_at"] is None

    @pytest.mark.asyncio
    async def test_reader_only_returns_valid_memories(self, wired_memory):
        """After UPDATE, the reader surfaces only the NEW row, not the
        invalidated one — even though both still exist in the collection."""
        wired = wired_memory

        await _extraction_only(wired, fact_text="User is grieving father")
        original = wired["db"].user_memories.find_one({"user_id": "u1"})
        original_id = original["_id"]

        wired["llm"].complete_json = AsyncMock(
            side_effect=[
                _extraction_response(
                    text="User is slowly healing",
                    importance=7,
                    sensitivity="personal",  # personal so tone filter doesn't block
                ),
                _update_decision(
                    target_id=str(original_id),
                    merged="User is slowly healing from father's death",
                ),
            ]
        )

        result = await wired["memory_extractor"].extract_memories(
            user_id="u1", session_id="s2", conversation_id="c2",
            turn_number=2, user_message="feeling lighter",
            assistant_response="that is grace", relational_profile_text="",
        )
        await wired["memory_writer"].update_memories_from_extraction(
            user_id="u1", session_id="s2", conversation_id="c2",
            turn_number=2, extraction=result,
        )

        session = _make_session(turn_count=5)
        read_result = await wired["memory_reader"].load_and_retrieve(
            user_id="u1", query="how am I now?", response_mode="teaching",
            analysis={"emotion": "curiosity"}, session=session,
        )
        # Exactly one memory surfaces — the merged one
        surfaced_texts = [sm.memory["text"] for sm in read_result.episodic]
        assert "User is slowly healing from father's death" in surfaced_texts
        assert "User is grieving father" not in surfaced_texts


# ---------------------------------------------------------------------------
# Scenario 5 — Reflection threshold trigger
# ---------------------------------------------------------------------------

class TestReflectionTrigger:
    @pytest.mark.asyncio
    async def test_reflection_fires_when_counter_crosses_threshold(
        self, wired_memory, monkeypatch
    ):
        """Enough cumulative importance → maybe_trigger_reflection dispatches
        a reflection task. With the fake LLM returning a valid reflection
        response, the profile gets consolidated and the counter resets."""
        wired = wired_memory

        # Bump the counter above the threshold directly (shortcut the slow
        # path of running 6 extractions)
        from config import settings
        wired["db"].user_profiles.insert_one({
            "user_id": "u1",
            "relational_narrative": "",
            "spiritual_themes": [],
            "ongoing_concerns": [],
            "tone_preferences": [],
            "people_mentioned": [],
            "prior_crisis_flag": False,
            "prior_crisis_context": None,
            "prior_crisis_count": 0,
            "importance_since_reflection": int(settings.REFLECTION_THRESHOLD) + 5,
            "reflection_count": 0,
        })

        # Add a memory so reflection has something to consolidate from
        wired["db"].user_memories.insert_one({
            "user_id": "u1",
            "text": "User is a software engineer",
            "embedding": [1.0, 0.0, 0.0, 0.0],
            "importance": 6,
            "sensitivity": "personal",
            "tone_marker": "neutral",
            "valid_at": datetime.utcnow(),
            "invalid_at": None,
            "created_at": datetime.utcnow(),
        })

        # Reflection Gemini response — consolidation JSON
        wired["llm"].complete_json = AsyncMock(
            return_value=(
                '{"updated_profile": {'
                '"relational_narrative": "A thoughtful seeker with '
                'a technical mind", '
                '"spiritual_themes": [], "ongoing_concerns": [], '
                '"tone_preferences": [], "people_mentioned": []'
                '}, "prune_ids": []}'
            )
        )

        # Run reflection (bypassing the in-flight lock by calling
        # run_reflection directly — tests maybe_trigger separately)
        result = await wired["reflection_service"].run_reflection("u1")
        assert result is not None

        profile = wired["db"].user_profiles.find_one({"user_id": "u1"})
        assert profile["relational_narrative"] == (
            "A thoughtful seeker with a technical mind"
        )
        # Counter reset to 0 after successful reflection
        assert profile["importance_since_reflection"] == 0
        assert profile["reflection_count"] == 1


# ---------------------------------------------------------------------------
# Scenario 6 — Anonymous sessions bypass the whole pipeline
# ---------------------------------------------------------------------------

class TestAnonymousBypass:
    @pytest.mark.asyncio
    async def test_no_writes_for_anonymous_dispatch(self, wired_memory):
        """Anonymous user_id never triggers any write, regardless of what
        the (mocked) Gemini says."""
        wired = wired_memory
        wired["llm"].complete_json = AsyncMock(
            return_value=_extraction_response()
        )

        await wired["memory_extractor"].dispatch_memory_extraction(
            user_id="",
            session_id="s1",
            conversation_id=None,
            turn_number=1,
            user_message="I am a software engineer",
            assistant_response="noted",
            intent_analysis={"intent": "EXPRESSING_EMOTION"},
        )
        # Give any scheduled task a chance to run
        await asyncio.sleep(0.05)

        assert wired["db"].user_memories.count_documents({}) == 0
        assert wired["db"].user_profiles.count_documents({}) == 0
