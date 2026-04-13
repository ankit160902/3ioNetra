"""Smoke tests for the dynamic memory system's startup wiring.

These are NOT a replacement for a full FastAPI lifespan test (that would
require spinning up the whole app, including Gemini and Mongo). Instead
they protect the two narrow invariants commit 13 introduced:

    1. main.py imports the five dynamic-memory modules eagerly so any
       syntax or circular-import error surfaces at boot, not at first
       request.
    2. main.py calls get_memory_service(rag) during the lifespan to
       force the MongoDB index creation path (LongTermMemoryService
       ._ensure_indexes()) to run at startup.

Both invariants are checked via source inspection rather than a live
lifespan run, to keep the test fast and dependency-free. If someone
refactors main.py and breaks the dynamic memory wiring, these tests
fail loudly before the change lands.
"""
import inspect

import pytest


class TestMainEagerImports:
    def test_main_imports_all_dynamic_memory_modules(self):
        """main.py must eagerly import all five new memory modules."""
        import main
        src = inspect.getsource(main)
        required_modules = [
            "services import memory_reader",
            "services import memory_writer",
            "services import memory_extractor",
            "services import reflection_service",
            "services import crisis_memory_hook",
        ]
        for mod in required_modules:
            assert mod in src, f"main.py missing eager import of: {mod}"

    def test_main_calls_get_memory_service_in_lifespan(self):
        """main.py lifespan must explicitly call get_memory_service so
        MongoDB index creation runs at boot, not lazy on first request."""
        import main
        src = inspect.getsource(main)
        assert "from services.memory_service import get_memory_service" in src
        assert "get_memory_service(rag_pipe)" in src

    def test_memory_router_is_registered(self):
        """main.py must register the /api/memory router alongside auth, chat, admin."""
        import main
        src = inspect.getsource(main)
        assert "from routers import auth, chat, admin, memory" in src
        assert "app.include_router(memory.router)" in src


class TestDynamicMemoryModulesImportable:
    """Defensive: verify each module imports cleanly in isolation.

    A circular-import regression in any of the five modules would only
    surface when the module is imported for the first time — which might
    be mid-request. Importing them here at test collection time catches
    that class of bug before the app starts.
    """

    def test_memory_reader_imports(self):
        from services import memory_reader
        assert hasattr(memory_reader, "load_and_retrieve")
        assert hasattr(memory_reader, "load_relational_profile")
        assert hasattr(memory_reader, "retrieve_episodic")

    def test_memory_writer_imports(self):
        from services import memory_writer
        assert hasattr(memory_writer, "update_memories_from_extraction")

    def test_memory_extractor_imports(self):
        from services import memory_extractor
        assert hasattr(memory_extractor, "extract_memories")
        assert hasattr(memory_extractor, "dispatch_memory_extraction")

    def test_reflection_service_imports(self):
        from services import reflection_service
        assert hasattr(reflection_service, "run_reflection")
        assert hasattr(reflection_service, "maybe_trigger_reflection")

    def test_crisis_memory_hook_imports(self):
        from services import crisis_memory_hook
        assert hasattr(crisis_memory_hook, "write_crisis_meta_fact")
        assert hasattr(crisis_memory_hook, "dispatch_crisis_meta_fact")

    def test_memory_router_imports(self):
        from routers import memory
        assert hasattr(memory, "router")
        # Router exposes the expected endpoints
        paths = {route.path for route in memory.router.routes}
        assert "/api/memory" in paths
        assert "/api/memory/profile" in paths
        assert "/api/memory/profile/reset" in paths
        assert "/api/memory/{memory_id}" in paths


class TestMemoryServiceIndexesCreatedAtInit:
    """Verify LongTermMemoryService._ensure_indexes is called at __init__.

    This is the mechanism by which main.py's startup get_memory_service()
    call creates indexes at boot. If someone ever removes _ensure_indexes
    from __init__, the new bi-temporal indexes won't exist and reader
    queries will fall back to full collection scans.
    """

    def test_ensure_indexes_called_at_init(self, monkeypatch):
        """LongTermMemoryService.__init__ must call _ensure_indexes."""
        from services.memory_service import LongTermMemoryService

        called = []

        def fake_ensure(self):
            called.append(True)

        # Also stub get_mongo_client so no real DB connection is attempted
        monkeypatch.setattr(
            "services.memory_service.get_mongo_client", lambda: None
        )
        monkeypatch.setattr(
            LongTermMemoryService, "_ensure_indexes", fake_ensure
        )
        LongTermMemoryService(rag_pipeline=None)
        assert called == [True]

    def test_ensure_indexes_creates_bi_temporal_and_unique_indexes(self):
        """Source-level check — _ensure_indexes must reference the three
        new bi-temporal indexes and the user_profiles unique index."""
        from services import memory_service
        src = inspect.getsource(memory_service)
        # user_memories bi-temporal
        assert '"user_id", 1), ("invalid_at", 1)' in src or \
               "('user_id', 1), ('invalid_at', 1)" in src
        # user_memories importance desc
        assert '"user_id", 1), ("importance", -1)' in src or \
               "('user_id', 1), ('importance', -1)" in src
        # user_memories sensitivity
        assert '"user_id", 1), ("sensitivity", 1)' in src or \
               "('user_id', 1), ('sensitivity', 1)" in src
        # user_profiles unique
        assert "user_profiles.create_index" in src
        assert "unique=True" in src
