import logging
from typing import List
from datetime import datetime
from config import settings
from services.auth_service import get_mongo_client, get_motor_db

logger = logging.getLogger(__name__)

MAX_MEMORIES_PER_USER = 200


class LongTermMemoryService:
    """
    Vectorized Long-term Memory Storage.
    Stores and retrieves semantically relevant past conversation excerpts.
    Uses a dedicated 'user_memories' collection (one document per memory)
    to avoid document size explosion and dual-purpose collection issues.
    """

    def __init__(self, rag_pipeline=None):
        self.db = get_mongo_client()       # sync pymongo — index creation only
        self.adb = get_motor_db()          # async motor — all runtime operations
        self.rag_pipeline = rag_pipeline
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create indexes on user_memories and user_profiles collections.

        Legacy indexes are kept for backward compatibility with the pre-
        dynamic-memory retrieval path. New indexes support the dynamic
        memory system (Apr 2026) — bi-temporal filtering, importance-
        ranked top-k, sensitivity tier filtering, and the new user_profiles
        collection for relational profiles.

        Each create_index call is wrapped in its own try/except so one
        failure (e.g. "index already exists under a different name")
        doesn't block the rest.
        """
        if self.db is None:
            return

        # Legacy user_memories indexes (pre Apr 2026) — preserved
        _legacy_memory_indexes = [
            ("user_id",),
            ([("user_id", 1), ("created_at", -1)],),
        ]
        for args in _legacy_memory_indexes:
            try:
                self.db.user_memories.create_index(*args)
            except Exception as e:
                logger.warning(f"user_memories legacy index {args!r} creation failed: {e}")

        # NEW user_memories indexes for dynamic memory system
        _new_memory_indexes = [
            # Bi-temporal filter — invalid_at=None means still valid. This is
            # the hottest path — every retrieval filters out invalidated
            # memories, so user_id + invalid_at is the primary compound index.
            [("user_id", 1), ("invalid_at", 1)],
            # Top-k by importance — supports the Generative-Agents scoring
            # function's importance lookup when the scoring short-circuits
            # to high-importance memories.
            [("user_id", 1), ("importance", -1)],
            # Tier filter — supports the sensitivity-tier retrieval filter
            # so the MemoryReader can quickly exclude sensitive memories
            # when the current turn's tone doesn't align.
            [("user_id", 1), ("sensitivity", 1)],
        ]
        for index_spec in _new_memory_indexes:
            try:
                self.db.user_memories.create_index(index_spec)
            except Exception as e:
                logger.warning(f"user_memories index {index_spec!r} creation failed: {e}")

        # NEW user_profiles collection index — unique, one profile per user
        try:
            self.db.user_profiles.create_index([("user_id", 1)], unique=True)
        except Exception as e:
            logger.warning(f"user_profiles unique index creation failed: {e}")

    def set_rag_pipeline(self, rag_pipeline):
        self.rag_pipeline = rag_pipeline

    async def store_memory(self, user_id: str, text: str):
        """Store a new anchor memory for the user in the dedicated user_memories collection."""
        if self.adb is None:
            logger.warning("Long-term memory storage skipped: Database not connected")
            return

        if not self.rag_pipeline:
            logger.warning("RAG pipeline not connected to MemoryService")
            return

        try:
            existing = await self.adb.user_memories.find_one({"user_id": user_id, "text": text})
            if existing:
                await self.adb.user_memories.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"created_at": datetime.utcnow().isoformat()}},
                )
                logger.info("Refreshed timestamp for existing memory anchor")
                return

            embedding = await self.rag_pipeline.generate_embeddings(text)
            memory_doc = {
                "user_id": user_id,
                "text": text,
                "embedding": embedding.tolist(),
                "created_at": datetime.utcnow().isoformat()
            }
            await self.adb.user_memories.insert_one(memory_doc)

            # Prune oldest memories if over cap
            count = await self.adb.user_memories.count_documents({"user_id": user_id})
            if count > MAX_MEMORIES_PER_USER:
                excess = count - MAX_MEMORIES_PER_USER
                oldest = await self.adb.user_memories.find(
                    {"user_id": user_id}
                ).sort("created_at", 1).limit(excess).to_list(excess)
                old_ids = [doc["_id"] for doc in oldest]
                if old_ids:
                    await self.adb.user_memories.delete_many({"_id": {"$in": old_ids}})
                logger.info(f"Pruned {excess} oldest memories for user {user_id}")

            logger.info(f"Stored new long-term semantic memory for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to store long-term memory: {e}")

    # Intents that never benefit from past-memory retrieval
    _SKIP_MEMORY_INTENTS = frozenset({"GREETING", "CLOSURE", "ASKING_PANCHANG"})

    async def retrieve_relevant_memories(self, user_id: str, query: str, top_k: int = 5, intent: str = "") -> List[str]:
        """Retrieve semantically similar past memories via MongoDB Atlas $vectorSearch.

        Skips the expensive embedding + ANN search for trivial messages (greetings,
        closures, panchang) where past memories are never used.
        """
        if intent in self._SKIP_MEMORY_INTENTS:
            return []
        if len(query.split()) <= 2:
            return []

        if self.adb is None:
            logger.debug("Memory retrieval skipped: database not connected")
            return []
        if not self.rag_pipeline:
            logger.debug("Memory retrieval skipped: RAG pipeline not available")
            return []

        try:
            query_vec = (await self.rag_pipeline.generate_embeddings(query)).tolist()
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "user_memory_vector_index",
                        "path": "embedding",
                        "queryVector": query_vec,
                        "numCandidates": 100,
                        "limit": top_k,
                        "filter": {"user_id": user_id},
                    }
                },
                {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
                {"$match": {"score": {"$gte": settings.MEMORY_SIMILARITY_THRESHOLD}}},
                {"$project": {"text": 1, "created_at": 1, "_id": 0}},
            ]
            results = await self.adb.user_memories.aggregate(pipeline).to_list(top_k)
            return [
                f"[{r.get('created_at', '').split('T')[0]}]: {r['text']}"
                for r in results
            ]
        except Exception as e:
            logger.error(f"Failed to retrieve relevant memories: {e}")
            return []

_memory_service = None

def get_memory_service(rag_pipeline=None) -> LongTermMemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = LongTermMemoryService(rag_pipeline)
    return _memory_service
