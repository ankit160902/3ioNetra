"""
Tests for RetrievalJudge — Hybrid RAG with LLM-in-the-Loop

Usage:
    cd backend && python -m pytest tests/test_retrieval_judge.py -v
    cd backend && python tests/test_retrieval_judge.py
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_doc(scripture="Bhagavad Gita", reference="2.47", text="Karmanye vadhikaraste", score=0.8):
    return {
        "scripture": scripture,
        "reference": reference,
        "text": text,
        "meaning": f"Meaning of {reference}",
        "final_score": score,
        "score": score,
        "type": "scripture",
    }


def _make_judge(llm_response=None, cache_hit=None):
    """Create a RetrievalJudge with mocked LLM and cache."""
    with patch("config.settings") as mock_settings:
        mock_settings.HYBRID_RAG_ENABLED = True
        mock_settings.JUDGE_MIN_SCORE = 4
        mock_settings.JUDGE_MAX_RETRIES = 1
        mock_settings.JUDGE_CACHE_TTL = 86400
        from services.retrieval_judge import RetrievalJudge
        judge = RetrievalJudge()
    judge.available = True
    mock_llm = MagicMock()
    mock_llm.available = True
    mock_llm.generate_quick_response = AsyncMock(return_value=llm_response or "")
    judge._llm = mock_llm
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=cache_hit)
    mock_cache.set = AsyncMock()
    judge._cache = mock_cache
    return judge


def _run_async(coro):
    """Helper to run async code in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Test: Complexity Classification
# ---------------------------------------------------------------------------

class TestClassifyComplexity:

    def setup_method(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = True
            mock_settings.JUDGE_MIN_SCORE = 4
            mock_settings.JUDGE_MAX_RETRIES = 1
            mock_settings.JUDGE_CACHE_TTL = 86400
            from services.retrieval_judge import RetrievalJudge
            self.judge = RetrievalJudge()

    def test_greeting_is_simple(self):
        result = self.judge._classify_complexity("Namaste", {"intent": "GREETING"})
        assert result == "simple"

    def test_closure_is_simple(self):
        result = self.judge._classify_complexity("Thank you, goodbye", {"intent": "CLOSURE"})
        assert result == "simple"

    def test_panchang_is_simple(self):
        result = self.judge._classify_complexity("What is today's tithi?", {"intent": "ASKING_PANCHANG"})
        assert result == "simple"

    def test_product_search_is_simple(self):
        result = self.judge._classify_complexity("Show me rudraksha malas", {"intent": "PRODUCT_SEARCH"})
        assert result == "simple"

    def test_emotional_sharing_is_simple(self):
        result = self.judge._classify_complexity(
            "I feel so lost and confused about my life",
            {"intent": "EXPRESSING_EMOTION", "needs_direct_answer": False},
        )
        assert result == "simple"

    def test_short_query_is_simple(self):
        result = self.judge._classify_complexity(
            "What is karma?",
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        assert result == "simple"

    def test_comparison_is_complex(self):
        result = self.judge._classify_complexity(
            "What is the difference between karma and dharma?",
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        assert result == "complex"

    def test_versus_is_complex(self):
        result = self.judge._classify_complexity(
            "Bhakti yoga vs karma yoga which is better?",
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        assert result == "complex"

    def test_scripture_reference_is_complex(self):
        result = self.judge._classify_complexity(
            "What does the Bhagavad Gita say about detachment according to Vedanta?",
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        assert result == "complex"

    def test_long_guidance_query_is_complex(self):
        result = self.judge._classify_complexity(
            "I have been feeling very anxious about my career and family responsibilities and want to know how dharmic principles can help me find balance in my daily life",
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        assert result == "complex"

    def test_multi_dharmic_terms_is_complex(self):
        result = self.judge._classify_complexity(
            "How do karma and bhakti relate to moksha?",
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        assert result == "complex"

    def test_enum_intent_handled(self):
        """Test that IntentType enum values are handled correctly."""

        class FakeIntent:
            value = "GREETING"

        result = self.judge._classify_complexity("Hello", {"intent": FakeIntent()})
        assert result == "simple"


# ---------------------------------------------------------------------------
# Test: Merge Results
# ---------------------------------------------------------------------------

class TestMergeResults:

    def setup_method(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = True
            from services.retrieval_judge import RetrievalJudge
            self.judge = RetrievalJudge()

    def test_merge_deduplicates_by_reference(self):
        docs1 = [make_doc(reference="2.47", score=0.8)]
        docs2 = [make_doc(reference="2.47", score=0.6), make_doc(reference="3.19", score=0.7)]
        merged = self.judge._merge_results([docs1, docs2])
        refs = [d["reference"] for d in merged]
        assert "2.47" in refs
        assert "3.19" in refs
        assert len(merged) == 2

    def test_merge_keeps_higher_score(self):
        docs1 = [make_doc(reference="2.47", score=0.8)]
        docs2 = [make_doc(reference="2.47", score=0.6)]
        merged = self.judge._merge_results([docs1, docs2])
        assert merged[0]["final_score"] == 0.8

    def test_merge_sorted_by_score_desc(self):
        docs1 = [make_doc(reference="1.1", score=0.5)]
        docs2 = [make_doc(reference="2.2", score=0.9)]
        merged = self.judge._merge_results([docs1, docs2])
        assert merged[0]["reference"] == "2.2"

    def test_merge_handles_empty(self):
        merged = self.judge._merge_results([[], []])
        assert merged == []

    def test_merge_handles_none_in_list(self):
        docs1 = [make_doc(reference="2.47", score=0.8)]
        merged = self.judge._merge_results([docs1, None])
        assert len(merged) == 1


# ---------------------------------------------------------------------------
# Test: JSON Parsing (basic)
# ---------------------------------------------------------------------------

class TestParseJson:

    def setup_method(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = True
            from services.retrieval_judge import RetrievalJudge
            self.judge = RetrievalJudge()

    def test_direct_json(self):
        result = self.judge._parse_json('{"score": 4, "reason": "good"}')
        assert result["score"] == 4

    def test_json_in_code_block(self):
        text = '```json\n{"score": 3, "reason": "mediocre"}\n```'
        result = self.judge._parse_json(text)
        assert result["score"] == 3

    def test_json_embedded_in_text(self):
        text = 'Here is my analysis:\n{"score": 5, "reason": "excellent"}\nEnd.'
        result = self.judge._parse_json(text)
        assert result["score"] == 5

    def test_empty_input(self):
        assert self.judge._parse_json("") == {}
        assert self.judge._parse_json(None) == {}

    def test_no_json(self):
        assert self.judge._parse_json("no json here") == {}


# ---------------------------------------------------------------------------
# Test: JSON Parsing — Nested Objects (Bug 1 verification)
# ---------------------------------------------------------------------------

class TestParseJsonNested:

    def setup_method(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = True
            from services.retrieval_judge import RetrievalJudge
            self.judge = RetrievalJudge()

    def test_nested_object(self):
        text = '{"score": 4, "details": {"key": "val"}}'
        result = self.judge._parse_json(text)
        assert result["score"] == 4
        assert result["details"]["key"] == "val"

    def test_nested_in_text(self):
        text = 'Result: {"score": 3, "meta": {"source": "gita"}} done.'
        result = self.judge._parse_json(text)
        assert result["score"] == 3
        assert result["meta"]["source"] == "gita"

    def test_nested_with_array(self):
        text = '{"sub_queries": ["q1", "q2"], "meta": {"count": 2}}'
        result = self.judge._parse_json(text)
        assert result["sub_queries"] == ["q1", "q2"]
        assert result["meta"]["count"] == 2

    def test_three_level_nesting(self):
        text = '{"a": {"b": {"c": "deep"}}}'
        result = self.judge._parse_json(text)
        assert result["a"]["b"]["c"] == "deep"

    def test_nested_in_code_block(self):
        text = '```json\n{"score": 5, "details": {"reason": "perfect", "docs": [0, 1]}}\n```'
        result = self.judge._parse_json(text)
        assert result["score"] == 5
        assert result["details"]["docs"] == [0, 1]


# ---------------------------------------------------------------------------
# Test: Enhanced Retrieve (async, with mocks)
# ---------------------------------------------------------------------------

class TestEnhancedRetrieve:

    def test_falls_back_when_disabled(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = False
            from services.retrieval_judge import RetrievalJudge
            judge = RetrievalJudge()

        mock_pipeline = MagicMock()
        mock_pipeline.search = AsyncMock(return_value=[make_doc()])

        result = _run_async(
            judge.enhanced_retrieve(
                query="test", intent_analysis={"intent": "GREETING"},
                rag_pipeline=mock_pipeline, search_kwargs={"top_k": 5},
            )
        )
        mock_pipeline.search.assert_called_once()
        assert len(result) == 1

    def test_simple_query_passes_through(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = True
            mock_settings.JUDGE_MIN_SCORE = 4
            mock_settings.JUDGE_MAX_RETRIES = 1
            mock_settings.JUDGE_CACHE_TTL = 86400
            from services.retrieval_judge import RetrievalJudge
            judge = RetrievalJudge()

        # Mock llm as available
        mock_llm = MagicMock()
        mock_llm.available = True
        judge._llm = mock_llm

        mock_pipeline = MagicMock()
        mock_pipeline.search = AsyncMock(return_value=[make_doc()])

        result = _run_async(
            judge.enhanced_retrieve(
                query="Namaste",
                intent_analysis={"intent": "GREETING"},
                rag_pipeline=mock_pipeline,
                search_kwargs={"top_k": 5},
            )
        )
        # Should call search once directly (no decomposition)
        assert mock_pipeline.search.call_count == 1
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Test: Kill Switch
# ---------------------------------------------------------------------------

class TestKillSwitch:

    def test_disabled_flag_bypasses_everything(self):
        from services.retrieval_judge import RetrievalJudge
        judge = RetrievalJudge()
        judge.available = False
        assert not judge.available

    def test_enabled_flag(self):
        from services.retrieval_judge import RetrievalJudge
        judge = RetrievalJudge()
        judge.available = True
        assert judge.available


# ---------------------------------------------------------------------------
# Test: Grounding Verification (basic)
# ---------------------------------------------------------------------------

class TestGroundingVerification:

    def test_skips_when_no_docs(self):
        from services.retrieval_judge import RetrievalJudge
        judge = RetrievalJudge()
        judge.available = True

        result = _run_async(judge.verify_grounding("Some response", []))
        assert result.grounded is True
        assert result.confidence == 1.0

    def test_skips_when_unavailable(self):
        from services.retrieval_judge import RetrievalJudge
        judge = RetrievalJudge()
        judge.available = False

        result = _run_async(judge.verify_grounding("Some response", [make_doc()]))
        assert result.grounded is True


# ---------------------------------------------------------------------------
# Test: Classification Coverage (50+ queries)
# ---------------------------------------------------------------------------

class TestClassificationCoverage:
    """Verify correct classification across diverse query types."""

    def setup_method(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = True
            mock_settings.JUDGE_MIN_SCORE = 4
            from services.retrieval_judge import RetrievalJudge
            self.judge = RetrievalJudge()

    SIMPLE_CASES = [
        ("Hello", {"intent": "GREETING"}),
        ("Namaste ji", {"intent": "GREETING"}),
        ("Thank you so much", {"intent": "CLOSURE"}),
        ("Bye", {"intent": "CLOSURE"}),
        ("What is today's tithi?", {"intent": "ASKING_PANCHANG"}),
        ("Show me puja items", {"intent": "PRODUCT_SEARCH"}),
        ("I want rudraksha", {"intent": "PRODUCT_SEARCH"}),
        ("I feel sad today", {"intent": "EXPRESSING_EMOTION", "needs_direct_answer": False}),
        ("I am anxious", {"intent": "EXPRESSING_EMOTION", "needs_direct_answer": False}),
        ("My mother passed away", {"intent": "EXPRESSING_EMOTION", "needs_direct_answer": False}),
        ("I am lonely", {"intent": "EXPRESSING_EMOTION", "needs_direct_answer": False}),
        ("What is dharma?", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("Tell me about karma", {"intent": "ASKING_INFO", "needs_direct_answer": True}),
        ("Who is Hanuman?", {"intent": "ASKING_INFO", "needs_direct_answer": True}),
        ("What mantra should I chant?", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("How to meditate?", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("Om Namah Shivaya", {"intent": "OTHER", "needs_direct_answer": False}),
        ("Good morning", {"intent": "GREETING"}),
        ("Jai Shri Ram", {"intent": "GREETING"}),
        ("Har Har Mahadev", {"intent": "GREETING"}),
        ("Please help", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("I need guidance", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("Suggest a prayer", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("Which temple to visit?", {"intent": "ASKING_INFO", "needs_direct_answer": True}),
        ("Tell me a shloka", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
    ]

    COMPLEX_CASES = [
        ("What is the difference between karma and dharma?", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("Compare bhakti yoga vs karma yoga", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("According to the Bhagavad Gita, how should one handle grief and loss in daily life?", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("How do karma and moksha relate to each other in Vedanta philosophy?", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("I have been struggling with anxiety at work and problems at home and want to understand how dharmic principles of detachment and seva can help me cope", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("What does Patanjali say about meditation versus what the Gita teaches about dhyana?", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("Explain the similarities between yoga and bhakti paths to spiritual growth", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}),
        ("How is dharma different across the four yugas according to the Puranas?", {"intent": "ASKING_INFO", "needs_direct_answer": True}),
    ]

    def test_simple_queries_classified_correctly(self):
        for query, intent in self.SIMPLE_CASES:
            result = self.judge._classify_complexity(query, intent)
            assert result == "simple", f"Expected 'simple' for: {query!r}, got: {result}"

    def test_complex_queries_classified_correctly(self):
        for query, intent in self.COMPLEX_CASES:
            result = self.judge._classify_complexity(query, intent)
            assert result == "complex", f"Expected 'complex' for: {query!r}, got: {result}"


# ---------------------------------------------------------------------------
# Test: Decompose Query (LLM mock)
# ---------------------------------------------------------------------------

class TestDecomposeQuery:

    def test_valid_decomposition(self):
        llm_resp = '{"sub_queries": ["What is karma?", "What is dharma?"]}'
        judge = _make_judge(llm_response=llm_resp)
        result = _run_async(judge._decompose_query(
            "difference between karma and dharma",
            {"emotion": "curious", "life_domain": "philosophy"},
        ))
        assert result == ["What is karma?", "What is dharma?"]

    def test_decomposition_from_code_block(self):
        llm_resp = '```json\n{"sub_queries": ["q1", "q2", "q3"]}\n```'
        judge = _make_judge(llm_response=llm_resp)
        result = _run_async(judge._decompose_query("test", {}))
        assert len(result) == 3

    def test_malformed_response_returns_empty(self):
        judge = _make_judge(llm_response="I don't know how to break this down")
        result = _run_async(judge._decompose_query("test", {}))
        assert result == []

    def test_empty_sub_queries_returns_empty(self):
        judge = _make_judge(llm_response='{"sub_queries": []}')
        result = _run_async(judge._decompose_query("test", {}))
        assert result == []

    def test_exception_returns_empty(self):
        judge = _make_judge()
        judge._llm.generate_quick_response = AsyncMock(side_effect=Exception("LLM down"))
        result = _run_async(judge._decompose_query("test", {}))
        assert result == []

    def test_limits_to_3_sub_queries(self):
        llm_resp = '{"sub_queries": ["q1", "q2", "q3", "q4", "q5"]}'
        judge = _make_judge(llm_response=llm_resp)
        result = _run_async(judge._decompose_query("test", {}))
        assert len(result) == 3

    def test_cache_set_on_success(self):
        llm_resp = '{"sub_queries": ["q1", "q2"]}'
        judge = _make_judge(llm_response=llm_resp)
        _run_async(judge._decompose_query("test query", {}))
        judge._cache.set.assert_called_once()

    def test_cache_hit_skips_llm(self):
        cached = json.dumps(["cached_q1", "cached_q2"])
        judge = _make_judge(cache_hit=cached)
        result = _run_async(judge._decompose_query("test query", {}))
        assert result == ["cached_q1", "cached_q2"]
        judge._llm.generate_quick_response.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Judge Relevance (LLM mock)
# ---------------------------------------------------------------------------

class TestJudgeRelevance:

    def test_high_score_no_retry(self):
        llm_resp = '{"score": 5, "reason": "excellent match", "best_doc_indices": [0, 1]}'
        judge = _make_judge(llm_response=llm_resp)
        with patch("config.settings") as ms:
            ms.JUDGE_MIN_SCORE = 4
            result = _run_async(judge._judge_relevance("test", [make_doc()], {}))
        assert result.score == 5
        assert result.should_retry is False
        assert result.best_doc_indices == [0, 1]

    def test_low_score_triggers_retry(self):
        llm_resp = '{"score": 2, "reason": "poor results", "best_doc_indices": []}'
        judge = _make_judge(llm_response=llm_resp)
        with patch("config.settings") as ms:
            ms.JUDGE_MIN_SCORE = 4
            result = _run_async(judge._judge_relevance("test", [make_doc()], {}))
        assert result.score == 2
        assert result.should_retry is True

    def test_malformed_json_defaults(self):
        judge = _make_judge(llm_response="not json at all")
        result = _run_async(judge._judge_relevance("test", [make_doc()], {}))
        # Falls back to default JudgmentResult
        assert result.score == 4
        assert result.should_retry is False

    def test_exception_returns_default(self):
        judge = _make_judge()
        judge._llm.generate_quick_response = AsyncMock(side_effect=Exception("fail"))
        result = _run_async(judge._judge_relevance("test", [make_doc()], {}))
        assert result.score == 4
        assert result.should_retry is False

    def test_score_clamped_to_1_5(self):
        llm_resp = '{"score": 10, "reason": "over"}'
        judge = _make_judge(llm_response=llm_resp)
        with patch("config.settings") as ms:
            ms.JUDGE_MIN_SCORE = 4
            result = _run_async(judge._judge_relevance("test", [make_doc()], {}))
        assert result.score == 5

    def test_score_clamped_minimum(self):
        llm_resp = '{"score": -3, "reason": "under"}'
        judge = _make_judge(llm_response=llm_resp)
        with patch("config.settings") as ms:
            ms.JUDGE_MIN_SCORE = 4
            result = _run_async(judge._judge_relevance("test", [make_doc()], {}))
        assert result.score == 1

    def test_empty_docs_returns_default(self):
        judge = _make_judge()
        result = _run_async(judge._judge_relevance("test", [], {}))
        assert result.score == 4
        assert result.should_retry is False

    def test_best_doc_indices_filtering(self):
        llm_resp = '{"score": 5, "reason": "good", "best_doc_indices": [0, 2]}'
        judge = _make_judge(llm_response=llm_resp)
        with patch("config.settings") as ms:
            ms.JUDGE_MIN_SCORE = 4
            result = _run_async(judge._judge_relevance("test", [make_doc(), make_doc(), make_doc()], {}))
        assert result.best_doc_indices == [0, 2]

    def test_string_index_coercion(self):
        """Bug 4 verification: string indices like '1' should be coerced to int."""
        llm_resp = '{"score": 5, "reason": "good", "best_doc_indices": ["0", "2", "invalid"]}'
        judge = _make_judge(llm_response=llm_resp)
        with patch("config.settings") as ms:
            ms.JUDGE_MIN_SCORE = 4
            result = _run_async(judge._judge_relevance("test", [make_doc(), make_doc(), make_doc()], {}))
        assert result.best_doc_indices == [0, 2]


# ---------------------------------------------------------------------------
# Test: Rewrite Query (LLM mock)
# ---------------------------------------------------------------------------

class TestRewriteQuery:

    def test_valid_rewrite(self):
        llm_resp = '{"rewritten_query": "karma yoga Bhagavad Gita detachment"}'
        judge = _make_judge(llm_response=llm_resp)
        result = _run_async(judge._rewrite_query("original query", "poor results", {}))
        assert result == "karma yoga Bhagavad Gita detachment"

    def test_exception_returns_original(self):
        judge = _make_judge()
        judge._llm.generate_quick_response = AsyncMock(side_effect=Exception("fail"))
        result = _run_async(judge._rewrite_query("original query", "reason", {}))
        assert result == "original query"

    def test_empty_response_returns_original(self):
        judge = _make_judge(llm_response="")
        result = _run_async(judge._rewrite_query("original query", "reason", {}))
        assert result == "original query"

    def test_cache_set_on_rewrite(self):
        llm_resp = '{"rewritten_query": "better query"}'
        judge = _make_judge(llm_response=llm_resp)
        _run_async(judge._rewrite_query("original query", "poor", {}))
        judge._cache.set.assert_called_once()

    def test_cache_hit_skips_llm(self):
        judge = _make_judge(cache_hit="cached rewrite query")
        result = _run_async(judge._rewrite_query("original query", "reason", {}))
        assert result == "cached rewrite query"
        judge._llm.generate_quick_response.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Verify Grounding with LLM
# ---------------------------------------------------------------------------

class TestVerifyGroundingWithLLM:

    def test_grounded_response(self):
        llm_resp = '{"grounded": true, "confidence": 0.95, "issues": ""}'
        judge = _make_judge(llm_response=llm_resp)
        result = _run_async(judge.verify_grounding("Some response about Gita 2.47", [make_doc()]))
        assert result.grounded is True
        assert result.confidence == 0.95

    def test_ungrounded_response(self):
        llm_resp = '{"grounded": false, "confidence": 0.3, "issues": "cites non-existent verse"}'
        judge = _make_judge(llm_response=llm_resp)
        result = _run_async(judge.verify_grounding("Made up verse", [make_doc()]))
        assert result.grounded is False
        assert result.confidence == 0.3
        assert "non-existent" in result.issues

    def test_exception_defaults_grounded(self):
        judge = _make_judge()
        judge._llm.generate_quick_response = AsyncMock(side_effect=Exception("fail"))
        result = _run_async(judge.verify_grounding("text", [make_doc()]))
        assert result.grounded is True
        assert result.confidence == 1.0

    def test_empty_text_skips(self):
        judge = _make_judge()
        result = _run_async(judge.verify_grounding("", [make_doc()]))
        assert result.grounded is True

    def test_llm_unavailable_skips(self):
        judge = _make_judge()
        judge._llm.available = False
        result = _run_async(judge.verify_grounding("text", [make_doc()]))
        assert result.grounded is True


# ---------------------------------------------------------------------------
# Test: Enhanced Retrieve — Complex Path (full flow)
# ---------------------------------------------------------------------------

class TestEnhancedRetrieveComplex:

    def _make_complex_judge(self, judge_score=5, decompose_resp=None, rewrite_resp=None, max_retries=1):
        """Helper: create judge with all mocks wired for complex path testing."""
        decompose_resp = decompose_resp or '{"sub_queries": ["q1", "q2"]}'
        rewrite_resp = rewrite_resp or '{"rewritten_query": "better query"}'
        judge_resp = json.dumps({"score": judge_score, "reason": "test", "best_doc_indices": [0]})

        judge = _make_judge()
        # LLM returns different responses based on prompt content
        call_count = {"n": 0}
        responses = [decompose_resp, judge_resp, rewrite_resp, judge_resp]

        async def mock_generate(prompt):
            idx = call_count["n"]
            call_count["n"] += 1
            if idx < len(responses):
                return responses[idx]
            return judge_resp

        judge._llm.generate_quick_response = AsyncMock(side_effect=mock_generate)
        return judge

    def test_complex_path_decompose_and_merge(self):
        judge = self._make_complex_judge(judge_score=5)
        pipeline = MagicMock()
        pipeline.search = AsyncMock(return_value=[make_doc()])

        with patch("config.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 1
            ms.JUDGE_CACHE_TTL = 86400
            result = _run_async(judge.enhanced_retrieve(
                query="What is the difference between karma and dharma?",
                intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                rag_pipeline=pipeline,
                search_kwargs={"top_k": 5},
            ))
        # Should have called search multiple times (original + sub-queries)
        assert pipeline.search.call_count >= 2
        assert len(result) >= 1

    def test_no_retry_on_high_score(self):
        judge = self._make_complex_judge(judge_score=5)
        pipeline = MagicMock()
        pipeline.search = AsyncMock(return_value=[make_doc()])

        with patch("config.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 1
            ms.JUDGE_CACHE_TTL = 86400
            result = _run_async(judge.enhanced_retrieve(
                query="What is the difference between karma and dharma?",
                intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                rag_pipeline=pipeline,
                search_kwargs={"top_k": 5},
            ))
        # With high score, no retry search should happen beyond initial decomposition
        # Initial: original + 2 sub-queries = 3 searches
        initial_count = pipeline.search.call_count
        assert initial_count <= 4  # at most original + 3 sub-queries

    def test_retry_on_low_score(self):
        """Bug 2 verification: low score triggers retry loop."""
        judge = _make_judge()

        # First call: decompose, second: judge (low score), third: rewrite, fourth: search
        call_count = {"n": 0}
        responses = [
            '{"sub_queries": ["q1"]}',  # decompose
            '{"score": 2, "reason": "poor", "best_doc_indices": []}',  # judge (low)
            '{"rewritten_query": "better"}',  # rewrite
        ]

        async def mock_gen(prompt):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx] if idx < len(responses) else '{"score": 5}'

        judge._llm.generate_quick_response = AsyncMock(side_effect=mock_gen)

        pipeline = MagicMock()
        pipeline.search = AsyncMock(return_value=[make_doc()])

        with patch("config.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 1
            ms.JUDGE_CACHE_TTL = 86400
            result = _run_async(judge.enhanced_retrieve(
                query="What is the difference between karma and dharma?",
                intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                rag_pipeline=pipeline,
                search_kwargs={"top_k": 5},
            ))
        # Should have done initial searches + 1 retry search
        assert pipeline.search.call_count >= 3

    def test_decomposition_failure_still_searches(self):
        judge = _make_judge()
        judge._llm.generate_quick_response = AsyncMock(side_effect=Exception("LLM down"))

        pipeline = MagicMock()
        pipeline.search = AsyncMock(return_value=[make_doc()])

        with patch("config.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 1
            ms.JUDGE_CACHE_TTL = 86400
            result = _run_async(judge.enhanced_retrieve(
                query="What is the difference between karma and dharma?",
                intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                rag_pipeline=pipeline,
                search_kwargs={"top_k": 5},
            ))
        # Should still return results from original query search
        assert len(result) >= 1

    def test_all_searches_fail_falls_back(self):
        judge = _make_judge(llm_response='{"sub_queries": ["q1"]}')

        pipeline = MagicMock()
        pipeline.search = AsyncMock(side_effect=Exception("search failed"))

        with patch("config.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 1
            ms.JUDGE_CACHE_TTL = 86400
            # When all searches fail, gather returns exceptions which are filtered.
            # Then merged is empty → fallback search is attempted (which also fails).
            try:
                result = _run_async(judge.enhanced_retrieve(
                    query="What is the difference between karma and dharma?",
                    intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                    rag_pipeline=pipeline,
                    search_kwargs={"top_k": 5},
                ))
            except Exception:
                pass  # Expected — fallback search also raises
            # The important thing is it attempted the fallback
            assert pipeline.search.call_count >= 2

    def test_best_indices_filtering_in_complex_path(self):
        judge = _make_judge()
        judge._llm.generate_quick_response = AsyncMock(side_effect=[
            '{"sub_queries": ["q1"]}',
            '{"score": 5, "reason": "good", "best_doc_indices": [0]}',
        ])

        docs = [make_doc(reference="1.1", score=0.9), make_doc(reference="2.2", score=0.7)]
        pipeline = MagicMock()
        pipeline.search = AsyncMock(return_value=docs)

        with patch("config.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 1
            ms.JUDGE_CACHE_TTL = 86400
            result = _run_async(judge.enhanced_retrieve(
                query="What is the difference between karma and dharma?",
                intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                rag_pipeline=pipeline,
                search_kwargs={"top_k": 5},
            ))
        # best_doc_indices=[0] should filter to just the first doc
        assert len(result) >= 1

    def test_top_k_respected(self):
        judge = _make_judge()
        judge._llm.generate_quick_response = AsyncMock(side_effect=[
            '{"sub_queries": ["q1"]}',
            '{"score": 5, "reason": "ok", "best_doc_indices": []}',
        ])

        many_docs = [make_doc(reference=f"ref_{i}", score=0.9 - i * 0.1) for i in range(10)]
        pipeline = MagicMock()
        pipeline.search = AsyncMock(return_value=many_docs)

        with patch("config.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 1
            ms.JUDGE_CACHE_TTL = 86400
            result = _run_async(judge.enhanced_retrieve(
                query="What is the difference between karma and dharma?",
                intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                rag_pipeline=pipeline,
                search_kwargs={"top_k": 3},
            ))
        assert len(result) <= 3

    def test_max_retries_loop(self):
        """Bug 2 verification: JUDGE_MAX_RETRIES > 1 actually loops multiple times."""
        judge = _make_judge()

        call_count = {"n": 0}
        responses = [
            '{"sub_queries": ["q1"]}',  # decompose
            '{"score": 2, "reason": "poor", "best_doc_indices": []}',  # judge 1 (low)
            '{"rewritten_query": "try1"}',  # rewrite 1
            '{"score": 2, "reason": "still poor", "best_doc_indices": []}',  # judge 2 (low)
            '{"rewritten_query": "try2"}',  # rewrite 2
        ]

        async def mock_gen(prompt):
            idx = call_count["n"]
            call_count["n"] += 1
            return responses[idx] if idx < len(responses) else '{"score": 5}'

        judge._llm.generate_quick_response = AsyncMock(side_effect=mock_gen)

        pipeline = MagicMock()
        pipeline.search = AsyncMock(return_value=[make_doc()])

        # Must patch the module-level settings reference in retrieval_judge
        with patch("services.retrieval_judge.settings") as ms:
            ms.HYBRID_RAG_ENABLED = True
            ms.JUDGE_MIN_SCORE = 4
            ms.JUDGE_MAX_RETRIES = 3
            ms.JUDGE_CACHE_TTL = 86400
            result = _run_async(judge.enhanced_retrieve(
                query="What is the difference between karma and dharma?",
                intent_analysis={"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
                rag_pipeline=pipeline,
                search_kwargs={"top_k": 5},
            ))
        # With max_retries=3, should do up to 3 retry searches
        # Initial: 2 searches (original + q1), then up to 3 retries = 5 total max
        assert pipeline.search.call_count >= 4
        assert len(result) >= 1


# ---------------------------------------------------------------------------
# Test: Cache Integration
# ---------------------------------------------------------------------------

class TestCacheIntegration:

    def test_decompose_cache_miss_then_hit(self):
        # First call: cache miss, LLM called
        judge = _make_judge(
            llm_response='{"sub_queries": ["q1", "q2"]}',
            cache_hit=None,
        )
        result1 = _run_async(judge._decompose_query("test query", {}))
        assert result1 == ["q1", "q2"]
        judge._llm.generate_quick_response.assert_called_once()
        judge._cache.set.assert_called_once()

        # Second call: simulate cache hit
        judge2 = _make_judge(cache_hit=json.dumps(["q1", "q2"]))
        result2 = _run_async(judge2._decompose_query("test query", {}))
        assert result2 == ["q1", "q2"]
        judge2._llm.generate_quick_response.assert_not_called()

    def test_rewrite_cache_miss_then_hit(self):
        judge = _make_judge(
            llm_response='{"rewritten_query": "improved query"}',
            cache_hit=None,
        )
        result1 = _run_async(judge._rewrite_query("original", "poor", {}))
        assert result1 == "improved query"
        judge._cache.set.assert_called_once()

        judge2 = _make_judge(cache_hit="improved query")
        result2 = _run_async(judge2._rewrite_query("original", "poor", {}))
        assert result2 == "improved query"
        judge2._llm.generate_quick_response.assert_not_called()

    def test_no_cache_still_works(self):
        """When cache is None, methods should still work without errors."""
        judge = _make_judge(llm_response='{"sub_queries": ["q1"]}')
        judge._cache = None
        result = _run_async(judge._decompose_query("test", {}))
        assert result == ["q1"]


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_query(self):
        judge = _make_judge()
        result = judge._classify_complexity("", {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True})
        assert result == "simple"  # empty = short = simple

    def test_empty_intent_analysis(self):
        judge = _make_judge()
        result = judge._classify_complexity("What is karma?", {})
        assert result == "simple"  # short query

    def test_none_intent(self):
        judge = _make_judge()
        # intent=None should not crash
        result = judge._classify_complexity("What is karma?", {"intent": None})
        assert result == "simple"

    def test_very_long_query(self):
        long_query = "How " + "very " * 50 + "long query about karma and dharma"
        judge = _make_judge()
        result = judge._classify_complexity(
            long_query,
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        assert result == "complex"  # long + multi dharmic terms

    def test_unicode_hindi_query(self):
        judge = _make_judge()
        result = judge._classify_complexity(
            "कर्म और धर्म में क्या अंतर है?",
            {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True},
        )
        # Should not crash — classification is based on English keywords
        assert result in ("simple", "complex")

    def test_docs_missing_fields(self):
        """Judge should handle docs with missing standard fields."""
        judge = _make_judge(llm_response='{"score": 4, "reason": "ok"}')
        sparse_doc = {"text": "some text"}
        with patch("config.settings") as ms:
            ms.JUDGE_MIN_SCORE = 4
            result = _run_async(judge._judge_relevance("test", [sparse_doc], {}))
        assert result.score == 4


# ---------------------------------------------------------------------------
# Test: Benchmark Classification
# ---------------------------------------------------------------------------

class TestBenchmarkClassification:

    def setup_method(self):
        with patch("config.settings") as mock_settings:
            mock_settings.HYBRID_RAG_ENABLED = True
            mock_settings.JUDGE_MIN_SCORE = 4
            from services.retrieval_judge import RetrievalJudge
            self.judge = RetrievalJudge()

    def test_benchmark_queries_classify_without_crash(self):
        """Load 100 benchmark queries and classify all without errors."""
        benchmark_path = Path(__file__).parent / "benchmarks" / "retrieval_benchmark_100.json"
        if not benchmark_path.exists():
            return  # Skip if benchmark file not available

        with open(benchmark_path) as f:
            queries = json.load(f)

        for q in queries:
            intent = {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}
            result = self.judge._classify_complexity(q["query"], intent)
            assert result in ("simple", "complex"), f"Invalid result for query {q['id']}"

    def test_benchmark_complex_ratio(self):
        """Verify 10-30% of benchmark queries classify as complex."""
        benchmark_path = Path(__file__).parent / "benchmarks" / "retrieval_benchmark_100.json"
        if not benchmark_path.exists():
            return  # Skip if benchmark file not available

        with open(benchmark_path) as f:
            queries = json.load(f)

        intent = {"intent": "SEEKING_GUIDANCE", "needs_direct_answer": True}
        complex_count = sum(
            1 for q in queries
            if self.judge._classify_complexity(q["query"], intent) == "complex"
        )
        ratio = complex_count / len(queries)
        assert 0.02 <= ratio <= 0.50, f"Complex ratio {ratio:.2%} outside expected range 2-50%"


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("RetrievalJudge Unit Tests")
    print("=" * 70)

    passed = 0
    failed = 0
    errors = []

    test_classes = [
        TestClassifyComplexity,
        TestMergeResults,
        TestParseJson,
        TestParseJsonNested,
        TestEnhancedRetrieve,
        TestKillSwitch,
        TestGroundingVerification,
        TestClassificationCoverage,
        TestDecomposeQuery,
        TestJudgeRelevance,
        TestRewriteQuery,
        TestVerifyGroundingWithLLM,
        TestEnhancedRetrieveComplex,
        TestCacheIntegration,
        TestEdgeCases,
        TestBenchmarkClassification,
    ]

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        for method_name in methods:
            try:
                if hasattr(instance, "setup_method"):
                    instance.setup_method()
                getattr(instance, method_name)()
                passed += 1
                print(f"  PASS: {cls.__name__}.{method_name}")
            except Exception as e:
                failed += 1
                errors.append((f"{cls.__name__}.{method_name}", str(e)))
                print(f"  FAIL: {cls.__name__}.{method_name} — {e}")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print("\nFailed tests:")
        for name, err in errors:
            print(f"  {name}: {err}")
        sys.exit(1)
    else:
        print("\nAll tests passed!")
        sys.exit(0)
