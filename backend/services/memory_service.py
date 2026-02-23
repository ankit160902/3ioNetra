import logging
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
from services.auth_service import get_mongo_client

logger = logging.getLogger(__name__)

class LongTermMemoryService:
    """
    Vectorized Long-term Memory Storage.
    Stores and retrieves semantically relevant past conversation excerpts.
    """

    def __init__(self, rag_pipeline=None):
        self.db = get_mongo_client()
        self.rag_pipeline = rag_pipeline

    def set_rag_pipeline(self, rag_pipeline):
        self.rag_pipeline = rag_pipeline

    async def store_memory(self, user_id: str, text: str):
        """Summarize and store a new anchor memory for the user"""
        if not self.rag_pipeline:
            logger.warning("RAG pipeline not connected to MemoryService")
            return

        try:
            # Generate embedding for the memory snippet
            embedding = await self.rag_pipeline.generate_embeddings(text)
            
            memory_doc = {
                "text": text,
                "embedding": embedding.tolist(),
                "created_at": datetime.utcnow().isoformat()
            }

            # Append to user's vectorized_memory in MongoDB
            self.db.conversations.update_one(
                {"user_id": user_id},
                {"$push": {"vectorized_memory": memory_doc}},
                upsert=True
            )
            logger.info(f"Stored long-term memory for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to store long-term memory: {e}")

    async def retrieve_relevant_memories(self, user_id: str, query: str, top_k: int = 3) -> List[str]:
        """Retrieve semantically similar past memories"""
        if not self.rag_pipeline:
            return []

        try:
            # Get user's vectorized memory from DB
            user_conv = self.db.conversations.find_one({"user_id": user_id}, {"vectorized_memory": 1})
            if not user_conv or "vectorized_memory" not in user_conv:
                return []

            memories = user_conv["vectorized_memory"]
            if not memories:
                return []

            # Generate embedding for the current query
            query_vec = await self.rag_pipeline.generate_embeddings(query)
            
            # Calculate cosine similarities
            results = []
            for mem in memories:
                mem_vec = np.array(mem["embedding"])
                similarity = np.dot(query_vec, mem_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(mem_vec))
                results.append((mem["text"], similarity))

            # Sort by similarity
            results.sort(key=lambda x: x[1], reverse=True)
            
            # Return top_k
            return [text for text, score in results[:top_k] if score > 0.6] # Threshold 0.6
            
        except Exception as e:
            logger.error(f"Failed to retrieve relevant memories: {e}")
            return []

_memory_service = None

def get_memory_service(rag_pipeline=None) -> LongTermMemoryService:
    global _memory_service
    if _memory_service is None:
        _memory_service = LongTermMemoryService(rag_pipeline)
    return _memory_service
