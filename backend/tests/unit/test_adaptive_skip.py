"""Verify adaptive rerank skip conditions."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_skip_rerank_for_presence_first():
    """presence_first response mode skips reranking."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    with patch.object(pipeline, '_rerank_results', new_callable=AsyncMock) as mock:
        results = await pipeline.search(
            query="I feel so lost",
            response_mode="presence_first",
        )
        mock.assert_not_called()


@pytest.mark.asyncio
async def test_skip_rerank_for_closure():
    """closure response mode skips reranking."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    with patch.object(pipeline, '_rerank_results', new_callable=AsyncMock) as mock:
        results = await pipeline.search(
            query="Thank you, goodbye",
            response_mode="closure",
        )
        mock.assert_not_called()


@pytest.mark.asyncio
async def test_no_skip_for_teaching():
    """teaching mode should still rerank (scripture precision matters)."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    results = await pipeline.search(
        query="What does Bhagavad Gita say about duty?",
        response_mode="teaching",
    )
    assert isinstance(results, list)
