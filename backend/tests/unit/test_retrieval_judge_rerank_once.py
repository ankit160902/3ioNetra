"""Verify retrieval judge's complex path uses rerank-once pattern."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_complex_path_passes_skip_rerank():
    """Complex queries: parallel searches use skip_rerank=True, then rerank once."""
    from services.retrieval_judge import RetrievalJudge

    mock_pipeline = AsyncMock()
    mock_pipeline.search = AsyncMock(return_value=[
        {"reference": "BG 2.47", "text": "test", "score": 0.5, "final_score": 0.5, "rerank_score": 0.5},
    ])
    mock_pipeline.rerank = AsyncMock(return_value=[
        {"reference": "BG 2.47", "text": "test", "score": 0.5, "final_score": 0.7, "rerank_score": 0.7},
    ])

    mock_llm = MagicMock()
    mock_llm.available = True

    judge = RetrievalJudge.__new__(RetrievalJudge)
    judge._llm = mock_llm
    judge.available = True
    judge._cache = None

    judge._decompose_query = AsyncMock(return_value=["sub query 1", "sub query 2"])
    judge._judge_relevance = AsyncMock(return_value=MagicMock(
        score=4, should_retry=False, best_doc_indices=[]
    ))
    judge._classify_complexity = MagicMock(return_value="complex")

    results = await judge.enhanced_retrieve(
        query="What is the difference between karma and dharma according to the Gita?",
        intent_analysis={"intent": "SEEKING_GUIDANCE", "emotion": "curiosity"},
        rag_pipeline=mock_pipeline,
        search_kwargs={"top_k": 5},
    )

    # All search calls should have skip_rerank=True
    for call in mock_pipeline.search.call_args_list:
        kwargs = call.kwargs if call.kwargs else {}
        # skip_rerank could be in kwargs directly or in the spread search_kwargs
        assert kwargs.get("skip_rerank") is True, \
            f"Search call missing skip_rerank=True: kwargs={kwargs}"

    # rerank() should be called at least once on merged results
    assert mock_pipeline.rerank.call_count >= 1, "rerank() must be called on merged results"
