"""
Retrieval Judge — Hybrid RAG with LLM-in-the-Loop

Simple queries (80%): zero overhead, pass through to rag_pipeline.search().
Complex queries (20%): LLM-powered decomposition, relevance judging, and retry.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

from config import settings
from rag.scoring_utils import get_doc_score


def _sanitize_for_prompt(text: str, max_len: int = 500) -> str:
    """Sanitize user input before interpolation into LLM prompts."""
    clean = text[:max_len].replace('"', "'").replace("\\", "")
    lines = clean.split("\n")
    safe_lines = [l for l in lines if not l.strip().upper().startswith(("[SYSTEM", "[INST", "<<SYS"))]
    return " ".join(safe_lines).strip()

if TYPE_CHECKING:
    from rag.pipeline import RAGPipeline

logger = logging.getLogger(__name__)


# --------------------------------------------------
# Data Models
# --------------------------------------------------

@dataclass
class JudgmentResult:
    score: int = 4
    reason: str = ""
    best_doc_indices: List[int] = field(default_factory=list)
    should_retry: bool = False


@dataclass
class GroundingResult:
    grounded: bool = True
    confidence: float = 1.0
    issues: str = ""


# --------------------------------------------------
# Dharmic terms for complexity detection
# --------------------------------------------------

DHARMIC_TERMS = {
    "karma", "dharma", "bhakti", "yoga", "moksha", "samsara", "atman",
    "brahman", "maya", "ahimsa", "tapas", "seva", "puja", "mantra",
    "chakra", "kundalini", "pranayama", "dhyana", "samadhi", "vairagya",
    "viveka", "sattvic", "rajasic", "tamasic", "guna", "shakti",
    "tantra", "vedanta", "sankhya", "nyaya", "vaisheshika", "mimamsa",
}

COMPARISON_WORDS = {
    "difference", "compare", "vs", "versus", "between", "distinguish",
    "contrast", "similarities", "different", "comparison",
}

SCRIPTURE_NAMES = {
    "gita", "bhagavad", "upanishad", "veda", "purana", "ramayana",
    "mahabharata", "vedanta", "sutra", "smriti", "shruti", "manu",
    "yoga sutra", "patanjali", "brahma sutra", "vishnu", "shiva",
}


# --------------------------------------------------
# RetrievalJudge
# --------------------------------------------------

class RetrievalJudge:
    """Hybrid RAG judge: routes simple queries directly, enhances complex ones."""

    def __init__(self):
        self._llm = None
        self._cache = None
        self.available = settings.HYBRID_RAG_ENABLED

    @property
    def llm(self):
        if self._llm is None:
            from llm.service import get_llm_service
            self._llm = get_llm_service()
        return self._llm

    @property
    def cache(self):
        if self._cache is None:
            try:
                from services.cache_service import get_cache_service
                self._cache = get_cache_service()
            except Exception:
                self._cache = None
        return self._cache

    # --------------------------------------------------
    # Main Orchestrator
    # --------------------------------------------------

    async def enhanced_retrieve(
        self,
        query: str,
        intent_analysis: Dict,
        rag_pipeline: "RAGPipeline",
        search_kwargs: Dict,
    ) -> List[Dict]:
        """Enhanced retrieval: simple queries pass through, complex get decomposition + judging."""
        if not self.available or not self.llm or not self.llm.available:
            return await rag_pipeline.search(query=query, **search_kwargs)

        try:
            complexity = self._classify_complexity(query, intent_analysis)
        except Exception as e:
            logger.warning(f"Complexity classification failed, defaulting to simple: {e}")
            complexity = "simple"

        if complexity == "simple":
            return await rag_pipeline.search(query=query, **search_kwargs)

        # COMPLEX PATH
        logger.info(f"Complex query detected, using enhanced retrieval: {query[:80]}")

        try:
            sub_queries = await self._decompose_query(query, intent_analysis)
        except Exception as e:
            logger.warning(f"Query decomposition failed: {e}")
            sub_queries = []

        all_queries = [query] + sub_queries

        # Parallel search for all sub-queries (with reduced top_k per sub-query)
        sub_top_k = min(search_kwargs.get("top_k", settings.RETRIEVAL_TOP_K), settings.RERANK_TOP_K)
        sub_search_kwargs = {**search_kwargs, "top_k": sub_top_k}
        sub_search_kwargs.pop("scripture_filter", None)  # Sub-queries need full corpus access
        tasks = [
            rag_pipeline.search(query=sq, **sub_search_kwargs)
            for sq in all_queries
        ]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, log failures
        for i, r in enumerate(all_results):
            if isinstance(r, Exception):
                logger.warning(f"Sub-query {i} failed: {r} | query='{all_queries[i][:60]}'")
        valid_results = [r for r in all_results if isinstance(r, list)]
        merged = self._merge_results(valid_results)

        if not merged:
            return await rag_pipeline.search(query=query, **search_kwargs)

        # Judge relevance
        try:
            judgment = await self._judge_relevance(query, merged, intent_analysis)
        except Exception as e:
            logger.warning(f"Relevance judging failed: {e}")
            judgment = JudgmentResult(score=4, should_retry=False)

        if not judgment.should_retry:
            if judgment.best_doc_indices:
                merged = [merged[i] for i in judgment.best_doc_indices if i < len(merged)]
            final_docs = merged[:search_kwargs.get("top_k", settings.RETRIEVAL_TOP_K)]
            # Add retrieval confidence metadata
            if final_docs:
                avg_score = sum(get_doc_score(d) for d in final_docs) / len(final_docs)
                for d in final_docs:
                    d["_retrieval_confidence"] = round(avg_score, 3)
            return final_docs

        # Retry loop — uses JUDGE_MAX_RETRIES setting
        retries_left = settings.JUDGE_MAX_RETRIES
        current_merged = merged
        last_reason = judgment.reason

        while retries_left > 0:
            retries_left -= 1
            logger.info(f"Judge scored {judgment.score}/5, retrying ({retries_left} retries remaining)")
            try:
                rewritten = await self._rewrite_query(query, last_reason, intent_analysis)
                retry_docs = await rag_pipeline.search(query=rewritten, **search_kwargs)
                current_merged = self._merge_results([current_merged, retry_docs])
            except Exception as e:
                logger.warning(f"Query rewrite/retry failed: {e}")
                break

            # Re-judge if more retries remain
            if retries_left > 0:
                try:
                    judgment = await self._judge_relevance(query, current_merged, intent_analysis)
                    if not judgment.should_retry:
                        if judgment.best_doc_indices:
                            current_merged = [current_merged[i] for i in judgment.best_doc_indices if i < len(current_merged)]
                        break
                    last_reason = judgment.reason
                except Exception:
                    break

        final_docs = current_merged[:search_kwargs.get("top_k", settings.RETRIEVAL_TOP_K)]
        # Add retrieval confidence metadata
        if final_docs:
            avg_score = sum(get_doc_score(d) for d in final_docs) / len(final_docs)
            for d in final_docs:
                d["_retrieval_confidence"] = round(avg_score, 3)
        return final_docs

    # --------------------------------------------------
    # Complexity Classification (deterministic, no LLM)
    # --------------------------------------------------

    _COMPLEX_EMOTIONS = frozenset({"hopelessness", "crisis", "guilt", "shame"})

    def _classify_complexity(self, query: str, intent_analysis: Dict) -> str:
        """Classify query as 'simple' or 'complex'. Deterministic rules, no LLM call."""
        intent = intent_analysis.get("intent", "")
        if isinstance(intent, str):
            intent_str = intent.upper()
        else:
            intent_str = str(intent.value).upper() if hasattr(intent, "value") else str(intent).upper()

        # Simple intents — always fast path
        simple_intents = {"GREETING", "CLOSURE", "ASKING_PANCHANG", "PRODUCT_SEARCH"}
        if intent_str in simple_intents:
            return "simple"

        # Fix 7: Emotional crisis queries need decomposition
        emotion = (intent_analysis.get("emotion") or "").lower()
        if emotion in self._COMPLEX_EMOTIONS:
            return "complex"

        query_lower = query.lower()
        words = query_lower.split()
        word_count = len(words)

        # Long queries (>20 words) are always complex — catches emotional dumps
        # that embed multiple concepts the embedding model can't handle in one shot.
        # Must be checked BEFORE needs_direct_answer to catch verbose emotional venting.
        if word_count > 20:
            return "complex"

        # Medium-length queries (15-20 words) with emotional or guidance intent — complex
        if word_count > 15 and intent_str in {"SEEKING_GUIDANCE", "ASKING_INFO", "EXPRESSING_EMOTION"}:
            return "complex"

        # Emotional sharing without needing direct answer — simple
        if not intent_analysis.get("needs_direct_answer", True):
            return "simple"

        # Short queries without comparison — simple
        if word_count <= 6 and not any(w in COMPARISON_WORDS for w in words):
            return "simple"

        # Comparison queries — complex
        if any(w in COMPARISON_WORDS for w in words):
            return "complex"

        # "according to" + scripture name — complex
        if "according to" in query_lower and any(s in query_lower for s in SCRIPTURE_NAMES):
            return "complex"

        # Multi-concept: 2+ dharmic terms — complex
        dharmic_count = sum(1 for w in words if w in DHARMIC_TERMS)
        if dharmic_count >= 2:
            return "complex"

        return "simple"

    # --------------------------------------------------
    # Query Decomposition (LLM)
    # --------------------------------------------------

    async def _decompose_query(self, query: str, intent_analysis: Dict) -> List[str]:
        """Decompose a complex query into 2-3 simpler sub-queries for scripture search."""
        # Check cache first
        cache_key_query = query.lower().strip()
        if self.cache:
            cached = await self.cache.get("query_decompose", query=cache_key_query)
            if cached:
                try:
                    return json.loads(cached) if isinstance(cached, str) else cached
                except (json.JSONDecodeError, TypeError):
                    pass

        emotion = intent_analysis.get("emotion", "")
        life_domain = intent_analysis.get("life_domain", "")

        prompt = (
            "Break this spiritual query into 2-3 simpler sub-queries for scripture search. "
            "Each should target a single concept or scripture.\n"
            f'Query: "{_sanitize_for_prompt(query)}"\n'
            f"Emotion: {emotion}\n"
            f"Domain: {life_domain}\n"
            'Respond ONLY with JSON: {"sub_queries": ["q1", "q2"]}'
        )

        try:
            response = await self.llm.generate_quick_response(prompt)
            # Parse JSON from response
            parsed = self._parse_json(response)
            sub_queries = parsed.get("sub_queries", [])
            if not isinstance(sub_queries, list) or not sub_queries:
                return []

            # Limit to 3 sub-queries
            sub_queries = [str(q) for q in sub_queries[:3] if q]

            # Cache result
            if self.cache and sub_queries:
                await self.cache.set(
                    "query_decompose",
                    json.dumps(sub_queries),
                    ttl=settings.JUDGE_CACHE_TTL,
                    query=cache_key_query,
                )

            return sub_queries
        except Exception as e:
            logger.warning(f"Query decomposition LLM call failed: {e}")
            return []

    # --------------------------------------------------
    # Relevance Judging (LLM)
    # --------------------------------------------------

    async def _judge_relevance(
        self, query: str, docs: List[Dict], intent_analysis: Dict
    ) -> JudgmentResult:
        """Score how relevant retrieved docs are to the query (1-5)."""
        if not docs:
            return JudgmentResult(score=4, should_retry=False)

        emotion = intent_analysis.get("emotion", "")
        life_domain = intent_analysis.get("life_domain", "")

        # Build doc summaries (top 5)
        doc_lines = []
        for i, doc in enumerate(docs[:5]):
            scripture = doc.get("scripture", "Unknown")
            reference = doc.get("reference", "")
            text = doc.get("text", doc.get("meaning", ""))[:150]
            doc_lines.append(f"Doc {i}: [{scripture}] {reference} - {text}")

        docs_text = "\n".join(doc_lines)

        intent = intent_analysis.get("intent", "unknown")

        prompt = (
            "Rate how relevant these scripture results are to the user's query.\n"
            f'Query: "{_sanitize_for_prompt(query)}"\n'
            f"Emotion: {emotion}\n"
            f"Domain: {life_domain}\n"
            f"User intent: {intent}\n"
            "Consider: temple docs are irrelevant for emotional queries. "
            "Meditation templates are irrelevant unless user asked about meditation.\n\n"
            f"{docs_text}\n\n"
            "Rate 1-5 overall (5=perfect match, 1=completely irrelevant).\n"
            'Respond ONLY with JSON: {"score": N, "reason": "brief reason", "best_doc_indices": [0, 2]}'
        )

        try:
            response = await self.llm.generate_quick_response(prompt)
            parsed = self._parse_json(response)
            score = int(parsed.get("score", 4))
            score = max(1, min(5, score))
            reason = str(parsed.get("reason", ""))
            best_indices = parsed.get("best_doc_indices", [])
            if not isinstance(best_indices, list):
                best_indices = []
            clean_indices = []
            for i in best_indices:
                try:
                    clean_indices.append(int(i))
                except (ValueError, TypeError):
                    pass
            best_indices = clean_indices

            return JudgmentResult(
                score=score,
                reason=reason,
                best_doc_indices=best_indices,
                should_retry=score < settings.JUDGE_MIN_SCORE,
            )
        except Exception as e:
            logger.warning(f"Relevance judging LLM call failed: {e}")
            return JudgmentResult(score=4, should_retry=False)

    # --------------------------------------------------
    # Query Rewrite (LLM)
    # --------------------------------------------------

    async def _rewrite_query(
        self, query: str, judgment_reason: str, intent_analysis: Dict
    ) -> str:
        """Rewrite query for better retrieval after poor judgment score."""
        cache_key_query = query.lower().strip()
        if self.cache:
            cached = await self.cache.get("query_rewrite", query=cache_key_query)
            if cached:
                return cached

        emotion = intent_analysis.get("emotion", "")

        prompt = (
            "Search returned poor results for this spiritual query. Rewrite for better retrieval.\n"
            f'Query: "{_sanitize_for_prompt(query)}"\n'
            f'Problem: "{judgment_reason}"\n'
            f"Emotion: {emotion}\n"
            "Write a single specific search query using dharmic concepts/Sanskrit terms.\n"
            'Respond ONLY with JSON: {"rewritten_query": "..."}'
        )

        try:
            response = await self.llm.generate_quick_response(prompt)
            parsed = self._parse_json(response)
            rewritten = str(parsed.get("rewritten_query", query))

            if self.cache and rewritten != query:
                await self.cache.set(
                    "query_rewrite",
                    rewritten,
                    ttl=settings.JUDGE_CACHE_TTL,
                    query=cache_key_query,
                )

            return rewritten
        except Exception as e:
            logger.warning(f"Query rewrite LLM call failed: {e}")
            return query

    # --------------------------------------------------
    # Merge & Deduplicate
    # --------------------------------------------------

    def _merge_results(self, result_sets: List[List[Dict]]) -> List[Dict]:
        """Merge multiple result sets, deduplicate by reference, keep highest score."""
        seen: Dict[str, Dict] = {}
        for docs in result_sets:
            if not docs:
                continue
            for doc in docs:
                ref = doc.get("reference", "") or doc.get("text", "")[:50]
                doc_score = get_doc_score(doc)
                existing_score = get_doc_score(seen[ref]) if ref in seen else -1
                if ref not in seen or doc_score > existing_score:
                    seen[ref] = doc
        return sorted(
            seen.values(),
            key=lambda d: get_doc_score(d),
            reverse=True,
        )

    # --------------------------------------------------
    # Grounding Verification
    # --------------------------------------------------

    async def verify_grounding(
        self, response_text: str, docs: List[Dict]
    ) -> GroundingResult:
        """Check if a response is grounded in the provided source documents."""
        if not self.available or not self.llm or not self.llm.available:
            return GroundingResult(grounded=True, confidence=1.0)

        if not docs or not response_text:
            return GroundingResult(grounded=True, confidence=1.0)

        # Build source summaries
        source_lines = []
        for doc in docs[:5]:
            scripture = doc.get("scripture", "Unknown")
            reference = doc.get("reference", "")
            text = doc.get("text", doc.get("meaning", ""))[:150]
            source_lines.append(f"[{scripture}] {reference}: {text}")
        sources_text = "\n".join(source_lines)

        prompt = (
            "Check if this response is grounded in the provided sources. "
            "A response is grounded if any scripture references, verse citations, or specific teachings "
            "it mentions are present in the sources. General spiritual wisdom without specific citations is also grounded.\n\n"
            f'Response: "{response_text[:500]}"\n\n'
            f"Sources:\n{sources_text}\n\n"
            'Respond ONLY with JSON: {"grounded": true/false, "confidence": 0.0-1.0, "issues": "brief description or empty"}'
        )

        try:
            response = await self.llm.generate_quick_response(prompt)
            parsed = self._parse_json(response)
            return GroundingResult(
                grounded=bool(parsed.get("grounded", True)),
                confidence=float(parsed.get("confidence", 1.0)),
                issues=str(parsed.get("issues", "")),
            )
        except Exception as e:
            logger.warning(f"Grounding verification failed: {e}")
            return GroundingResult(grounded=True, confidence=1.0)

    # --------------------------------------------------
    # JSON Parsing Helper
    # --------------------------------------------------

    @staticmethod
    def _parse_json(text: str) -> Dict:
        """Extract and parse JSON from LLM response text."""
        if not text:
            return {}
        # Try direct parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        # Try to find JSON block in text
        import re
        # Match ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try to find raw JSON object (balanced-brace scanner for nested objects)
        start = text.find('{')
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break
        return {}


# --------------------------------------------------
# Singleton
# --------------------------------------------------

_instance: Optional[RetrievalJudge] = None


def get_retrieval_judge() -> RetrievalJudge:
    global _instance
    if _instance is None:
        _instance = RetrievalJudge()
    return _instance
