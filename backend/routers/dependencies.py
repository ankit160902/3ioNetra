"""Shared dependency — single RAG pipeline reference for all routers."""

_rag_pipeline = None


def set_rag_pipeline(pipeline):
    global _rag_pipeline
    _rag_pipeline = pipeline


def get_rag_pipeline():
    return _rag_pipeline
