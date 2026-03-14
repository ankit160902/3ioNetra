import logging
import numpy as np
from typing import List
from datetime import datetime
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
            existing = self.db.user_memories.find_one(
                {"user_id": user_id, "text": text}
            )

            if existing:
                # Update timestamp for existing memory
                self.db.user_memories.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"created_at": datetime.utcnow().isoformat()}}
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

            self.db.user_memories.insert_one(memory_doc)

            # Enforce cap: remove oldest memories if over limit
            count = self.db.user_memories.count_documents({"user_id": user_id})
            if count > MAX_MEMORIES_PER_USER:
                excess = count - MAX_MEMORIES_PER_USER
                oldest = self.db.user_memories.find(
                    {"user_id": user_id}
                ).sort("created_at", 1).limit(excess)
                old_ids = [doc["_id"] for doc in oldest]
                self.db.user_memories.delete_many({"_id": {"$in": old_ids}})
                logger.info(f"Pruned {excess} oldest memories for user {user_id}")

            logger.info(f"Stored new long-term semantic memory for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to store long-term memory: {e}")

    async def retrieve_relevant_memories(self, user_id: str, query: str, top_k: int = 3) -> List[str]:
        """Retrieve semantically similar past memories from the dedicated user_memories collection."""
        if self.db is None:
            return []

        if not self.rag_pipeline:
            return []

        try:
            # Get all memories for this user
            cursor = self.db.user_memories.find(
                {"user_id": user_id},
                {"text": 1, "embedding": 1, "created_at": 1}
            )
            memories = list(cursor)
            if not memories:
                return []

            # Generate embedding for the current query
            query_vec = await self.rag_pipeline.generate_embeddings(query)

            # Calculate cosine similarities
            results = []
            for mem in memories:
                mem_vec = np.array(mem["embedding"])
                similarity = np.dot(query_vec, mem_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(mem_vec))

                # Format memory with date
                date_str = mem.get("created_at", "").split("T")[0]
                results.append((f"[{date_str}]: {mem['text']}", similarity))

            # Sort by similarity
            results.sort(key=lambda x: x[1], reverse=True)

            # Return top_k
            return [text for text, score in results[:top_k] if score > 0.55]

        except Exception as e:
            logger.error(f"Failed to retrieve relevant memories: {e}")
            return []

_memory_service = None

def get_memory_service(rag_pipeline=None) -> LongTermMemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = LongTermMemoryService(rag_pipeline)
    return _memory_service
