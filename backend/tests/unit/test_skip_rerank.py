"""Verify skip_rerank parameter prevents CrossEncoder from running."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_search_skip_rerank_returns_results():
    """search(skip_rerank=True) returns hybrid-scored results without CrossEncoder."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")

    with patch.object(pipeline, '_rerank_results', wraps=pipeline._rerank_results) as mock_rerank:
        results = await pipeline.search(query="What is dharma?", skip_rerank=True)
        mock_rerank.assert_not_called()

    assert isinstance(results, list)
    for r in results:
        assert "score" in r
        assert "final_score" in r


@pytest.mark.asyncio
async def test_search_default_does_not_skip():
    """Default search (skip_rerank=False) allows CrossEncoder to run."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")
    results = await pipeline.search(query="What is dharma?", skip_rerank=False)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_public_rerank_method_exists():
    """Public rerank() method caps candidates and delegates to _rerank_results."""
    from rag.pipeline import get_rag_pipeline
    pipeline = get_rag_pipeline()
    if pipeline is None or not pipeline.available:
        pytest.skip("RAG pipeline not available")
    assert hasattr(pipeline, 'rerank'), "RAGPipeline must have a public rerank() method"
    # Test with empty candidates
    result = await pipeline.rerank(query="test", candidates=[])
    assert result == []
