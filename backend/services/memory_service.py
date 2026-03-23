import asyncio
import logging
import numpy as np
from typing import List
from datetime import datetime
from config import settings
from services.auth_service import get_mongo_client

logger = logging.getLogger(__name__)

# Maximum number of memories per user to prevent unbounded growth
MAX_MEMORIES_PER_USER = 200


class LongTermMemoryService:
    """
    Vectorized Long-term Memory Storage.
    Stores and retrieves semantically relevant past conversation excerpts.
    Uses a dedicated 'user_memories' collection (one document per memory)
    to avoid document size explosion and dual-purpose collection issues.
    """

    def __init__(self, rag_pipeline=None):
        self.db = get_mongo_client()
        self.rag_pipeline = rag_pipeline
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create indexes on the user_memories collection."""
        if self.db is None:
            return
        try:
            self.db.user_memories.create_index("user_id")
            self.db.user_memories.create_index([("user_id", 1), ("created_at", -1)])
        except Exception as e:
            logger.warning(f"user_memories index creation failed: {e}")

    def set_rag_pipeline(self, rag_pipeline):
        self.rag_pipeline = rag_pipeline

    async def store_memory(self, user_id: str, text: str):
        """Store a new anchor memory for the user in the dedicated user_memories collection."""
        if self.db is None:
            logger.warning("Long-term memory storage skipped: Database not connected")
            return

        if not self.rag_pipeline:
            logger.warning("RAG pipeline not connected to MemoryService")
            return

        try:
            # Check for existing memory with same text to avoid redundancy
            existing = await asyncio.to_thread(
                self.db.user_memories.find_one,
                {"user_id": user_id, "text": text},
            )

            if existing:
                # Update timestamp for existing memory
                await asyncio.to_thread(
                    self.db.user_memories.update_one,
                    {"_id": existing["_id"]},
                    {"$set": {"created_at": datetime.utcnow().isoformat()}},
                )
                logger.info("Refreshed timestamp for existing memory anchor")
                return

            # Generate embedding for the new memory snippet
            embedding = await self.rag_pipeline.generate_embeddings(text)

            memory_doc = {
                "user_id": user_id,
                "text": text,
                "embedding": embedding.tolist(),
                "created_at": datetime.utcnow().isoformat()
            }

            await asyncio.to_thread(self.db.user_memories.insert_one, memory_doc)

            # Enforce cap: remove oldest memories if over limit
            def _prune_old():
                count = self.db.user_memories.count_documents({"user_id": user_id})
                if count > MAX_MEMORIES_PER_USER:
                    excess = count - MAX_MEMORIES_PER_USER
                    oldest = self.db.user_memories.find(
                        {"user_id": user_id}
                    ).sort("created_at", 1).limit(excess)
                    old_ids = [doc["_id"] for doc in oldest]
                    if old_ids:
                        self.db.user_memories.delete_many({"_id": {"$in": old_ids}})
                    return excess
                return 0

            excess = await asyncio.to_thread(_prune_old)
            if excess:
                logger.info(f"Pruned {excess} oldest memories for user {user_id}")

            logger.info(f"Stored new long-term semantic memory for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to store long-term memory: {e}")

    # Intents that never benefit from past-memory retrieval
    _SKIP_MEMORY_INTENTS = frozenset({"GREETING", "CLOSURE", "ASKING_PANCHANG"})

    async def retrieve_relevant_memories(self, user_id: str, query: str, top_k: int = 5, intent: str = "") -> List[str]:
        """Retrieve semantically similar past memories from the dedicated user_memories collection.

        Skips the expensive embedding + MongoDB fetch for trivial messages (greetings,
        closures, panchang) where past memories are never used.
        """
        # Fast exit: trivial intents never use memories
        if intent in self._SKIP_MEMORY_INTENTS:
            return []

        # Fast exit: very short messages (≤2 words) are unlikely to benefit
        if len(query.split()) <= 2:
            return []

        if self.db is None:
            logger.debug("Memory retrieval skipped: database not connected")
            return []

        if not self.rag_pipeline:
            logger.debug("Memory retrieval skipped: RAG pipeline not available")
            return []

        try:
            # Get all memories for this user
            memories = await asyncio.to_thread(
                lambda: list(self.db.user_memories.find(
                    {"user_id": user_id},
                    {"text": 1, "embedding": 1, "created_at": 1},
                ))
            )
            if not memories:
                return []

            # Generate embedding for the current query
            query_vec = await self.rag_pipeline.generate_embeddings(query)

            # Vectorized similarity: batch all memory vectors into a matrix for single matmul
            mem_matrix = np.array([mem["embedding"] for mem in memories], dtype=np.float32)
            norms = np.linalg.norm(mem_matrix, axis=1)
            norms[norms == 0] = 1e-9
            query_norm = np.linalg.norm(query_vec) + 1e-9
            similarities = (mem_matrix @ query_vec) / (norms * query_norm)

            # Pre-filter: only keep above threshold, then argsort descending
            mask = similarities >= settings.MEMORY_SIMILARITY_THRESHOLD
            if not np.any(mask):
                return []

            valid_indices = np.where(mask)[0]
            valid_sims = similarities[valid_indices]
            sorted_order = np.argsort(-valid_sims)
            sorted_indices = valid_indices[sorted_order]

            # Deduplicate with vectorized dot-product checks
            deduped = []
            deduped_vecs = []
            for idx in sorted_indices:
                score = float(similarities[idx])
                vec = mem_matrix[idx]

                # Vectorized dedup: compare against all kept vectors at once
                if deduped_vecs:
                    kept_matrix = np.array(deduped_vecs, dtype=np.float32)
                    kept_norms = np.linalg.norm(kept_matrix, axis=1)
                    kept_norms[kept_norms == 0] = 1e-9
                    vec_norm = np.linalg.norm(vec) + 1e-9
                    dup_sims = (kept_matrix @ vec) / (kept_norms * vec_norm)
                    if np.any(dup_sims > settings.MEMORY_DEDUP_THRESHOLD):
                        continue

                mem = memories[int(idx)]
                date_str = mem.get("created_at", "").split("T")[0]
                deduped.append(f"[{date_str}]: {mem['text']}")
                deduped_vecs.append(vec)
                if len(deduped) >= settings.MEMORY_MAX_RESULTS:
                    break

            if len(sorted_indices) > len(deduped):
                logger.info(f"Memory dedup: {len(sorted_indices)} candidates → {len(deduped)} unique memories")

            return deduped

        except Exception as e:
            logger.error(f"Failed to retrieve relevant memories: {e}")
            return []

_memory_service = None

def get_memory_service(rag_pipeline=None) -> LongTermMemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = LongTermMemoryService(rag_pipeline)
    return _memory_service
