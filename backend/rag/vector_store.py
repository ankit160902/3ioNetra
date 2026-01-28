"""
Minimal vector store shim.

The latest RAG implementation keeps embeddings in‑memory inside
`RAGPipeline` and does not require an external vector store object,
but `main.py` still imports `get_vector_store`.  This module provides
that symbol so the import succeeds without changing the public API.
"""

import logging

logger = logging.getLogger(__name__)


class DummyVectorStore:
    """Placeholder class kept for backwards compatibility."""

    def similarity_search(self, *_, **__):
        logger.warning("DummyVectorStore.similarity_search called – returning empty list")
        return []


_vector_store: DummyVectorStore | None = None


def get_vector_store() -> DummyVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = DummyVectorStore()
    return _vector_store

