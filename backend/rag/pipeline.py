import asyncio
import json
import os
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

import numpy as np

from config import settings
from llm.service import get_llm_service
from services.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Optimized RAG pipeline that:
    - loads pre‑computed verse embeddings from data/processed
    - performs efficient cosine‑similarity search with pre-normalized vectors
    - filters results based on configuration thresholds for precision
    - can optionally call the LLM to synthesize answers

    The API is designed to match how `main.py` uses it:
    - await initialize()
    - await query(...)
    - async for chunk in query_stream(...)
    - await search(...)
    - await generate_embeddings(...)
    """

    def __init__(self) -> None:
        self.verses: List[Dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self.dim: int = 0
        self.available: bool = False
        self._embedding_model = None
        self._reranker_model = None
        self._llm = get_llm_service()

    def __bool__(self) -> bool:
        return self.available

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Load RAG data efficiently using memory mapping for embeddings.
        This allows handling massive datasets (2GB+) without OOM crashes.
        """
        try:
            base_dir = Path(__file__).parent.parent
            processed_dir = base_dir / "data" / "processed"
            metadata_path = processed_dir / "verses.json"
            embeddings_path = processed_dir / "embeddings.npy"

            # Check for high-efficiency split format
            if metadata_path.exists() and embeddings_path.exists():
                logger.info(f"RAGPipeline: Loading metadata from {metadata_path}...")
                with metadata_path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                self.verses = payload.get("verses", [])
                
                logger.info(f"RAGPipeline: Memory-mapping embeddings from {embeddings_path}...")
                # mmap_mode='r' is the critical fix for Cloud Run OOM
                raw_embeddings = np.load(embeddings_path, mmap_mode='r')
            else:
                logger.warning("RAGPipeline: No processed data found (verses.json + embeddings.npy). Run scripts/ingest_all_data.py.")
                self.available = False
                return

            if not self.verses or raw_embeddings.size == 0:
                logger.warning("RAGPipeline: Empty dataset loaded")
                self.available = False
                return

            self.dim = raw_embeddings.shape[1]
            self.embeddings = raw_embeddings
            self.available = True

            scripture_counts = {}
            for v in self.verses:
                s = v.get("scripture", "Unknown")
                scripture_counts[s] = scripture_counts.get(s, 0) + 1

            logger.info(
                f"RAGPipeline initialized with {len(self.verses)} verses "
                f"(dim={self.dim}). Memory Map: {'Active' if metadata_path.exists() else 'Inactive (Legacy Mode)'}"
            )

            # Eagerly load ML models at startup to avoid per-request delays
            self._load_ml_models()

        except Exception as exc:
            logger.exception(f"Failed to initialize RAGPipeline: {exc}")
            self.available = False

    # ------------------------------------------------------------------
    # ML Model Loading (eager at startup, cached locally)
    # ------------------------------------------------------------------

    def _load_ml_models(self) -> None:
        """Load embedding and reranker models once at startup.
        Also pre-computes BM25 statistics and sets HuggingFace Hub to offline
        mode to prevent HTTP requests during request handling.
        """
        self._ensure_embedding_model()
        self._ensure_reranker_model()

        # Pre-compute BM25 doc stats so first search is instant
        self._precompute_bm25_stats()

        # Block all future HuggingFace Hub HTTP requests
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        logger.info(
            "RAGPipeline: ML models loaded at startup — "
            "HuggingFace Hub set to offline mode for runtime"
        )

    @staticmethod
    def _local_dev_model_dir() -> Path:
        """Return <backend>/models — the local dev model cache directory."""
        return Path(__file__).resolve().parent.parent / "models"

    # ------------------------------------------------------------------
    # Embedding utilities
    # ------------------------------------------------------------------

    def _ensure_embedding_model(self) -> None:
        if self._embedding_model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            # 1. Docker production path
            local_path = "/app/models/embeddings"
            if os.path.isdir(local_path):
                logger.info(f"RAGPipeline: loading embedding model from LOCAL path: {local_path}")
                self._embedding_model = SentenceTransformer(local_path)
                return

            # 2. Local dev cache path (backend/models/embeddings)
            dev_path = str(self._local_dev_model_dir() / "embeddings")
            if os.path.isdir(dev_path) and os.listdir(dev_path):
                logger.info(f"RAGPipeline: loading embedding model from DEV cache: {dev_path}")
                self._embedding_model = SentenceTransformer(dev_path)
                return

            # 3. Download from Hub (first time only), then cache locally
            model_name = settings.EMBEDDING_MODEL
            logger.info(f"RAGPipeline: downloading embedding model '{model_name}' from Hub (one-time)")
            self._embedding_model = SentenceTransformer(model_name)

            # Auto-save to local dev cache for instant loads next time
            os.makedirs(dev_path, exist_ok=True)
            self._embedding_model.save(dev_path)
            logger.info(f"RAGPipeline: cached embedding model to {dev_path}")
        except Exception as exc:
            logger.exception(f"RAGPipeline: failed to load embedding model: {exc}")
            self._embedding_model = None

    def _ensure_reranker_model(self) -> None:
        if self._reranker_model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder

            # 1. Docker production path
            local_path = "/app/models/reranker"
            if os.path.isdir(local_path):
                logger.info(f"RAGPipeline: loading re-ranker from LOCAL path: {local_path}")
                self._reranker_model = CrossEncoder(local_path)
                return

            # 2. Local dev cache path (backend/models/reranker)
            dev_path = str(self._local_dev_model_dir() / "reranker")
            if os.path.isdir(dev_path) and os.listdir(dev_path):
                logger.info(f"RAGPipeline: loading re-ranker from DEV cache: {dev_path}")
                self._reranker_model = CrossEncoder(dev_path)
                return

            # 3. Download from Hub (first time only), then cache locally
            model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
            logger.info(f"RAGPipeline: downloading re-ranker '{model_name}' from Hub (one-time)")
            self._reranker_model = CrossEncoder(model_name)

            # Auto-save to local dev cache for instant loads next time
            os.makedirs(dev_path, exist_ok=True)
            self._reranker_model.save(dev_path)
            logger.info(f"RAGPipeline: cached re-ranker to {dev_path}")
        except Exception as exc:
            logger.exception(f"RAGPipeline: failed to load re-ranker: {exc}")
            self._reranker_model = None

    async def generate_embeddings(self, text: str) -> np.ndarray:
        """
        Public utility used by /api/embeddings/generate.
        """
        self._ensure_embedding_model()
        if self._embedding_model is None:
            # Fallback: deterministic zero vector with configured dim
            dim = self.dim or 768
            logger.warning("RAGPipeline: embedding model unavailable, returning zeros")
            return np.zeros((dim,), dtype="float32")

        # Normalize text: strip whitespace, replace newlines
        clean_text = text.strip().replace("\n", " ")
        vec = self._embedding_model.encode([clean_text], convert_to_tensor=False, show_progress_bar=False)[0]
        return np.asarray(vec, dtype="float32")

    # ------------------------------------------------------------------
    # Query Expansion
    # ------------------------------------------------------------------

    # Words that should never trigger LLM-based query expansion
    _SKIP_EXPANSION = frozenset([
        "hi", "hey", "hello", "namaste", "pranam", "ok", "okay",
        "thanks", "thank you", "bye", "hii", "hiii", "yes", "no",
    ])

    async def _expand_query(self, query: str) -> List[str]:
        """Use LLM to expand the query for better recall.
        Skips expansion for greetings and trivial messages to save a Gemini call.
        """
        # Fast-path: skip expansion for greetings / trivial messages
        if query.strip().lower() in self._SKIP_EXPANSION:
            return [query]

        if not self._llm.available:
            return [query]

        prompt = f"""
        Expand the following spiritual query into 2 alternative search terms that capture different aspects of the request.
        Original: "{query}"
        Respond ONLY with the 2 terms, separated by a newline. Do not include numbering or bullets.
        """
        try:
            import asyncio

            # Use the fast model for query expansion (lightweight task)
            def _sync_expand():
                return self._llm.client.models.generate_content(
                    model=settings.GEMINI_FAST_MODEL,
                    contents=prompt,
                    config={"temperature": 0.3, "max_output_tokens": 100, "automatic_function_calling": {"disable": True}}
                )

            response = await asyncio.to_thread(_sync_expand)
            expansion = response.text if response.text else ""
            expanded_terms = [t.strip() for t in expansion.split("\n") if t.strip()]
            logger.info(f"Query expansion: {expanded_terms}")
            return [query] + expanded_terms[:2]
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return [query]

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

    def _get_best_score(self, doc: Dict) -> float:
        """Return the best available numeric score from a retrieved document."""
        return float(
            doc.get("final_score")
            or doc.get("rerank_score")
            or doc.get("score")
            or 0.0
        )

    def _cosine_similarities(self, query_vec: np.ndarray) -> np.ndarray:
        if self.embeddings is None or not self.available:
            return np.zeros((0,), dtype="float32")

        # Normalize the query vector
        q = query_vec.astype("float32")
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        # Dot product with pre-normalized document vectors
        return self.embeddings @ q

    def _precompute_bm25_stats(self) -> None:
        """Pre-compute BM25 document statistics at startup (avoids first-search delay)."""
        if not self.verses:
            return
        N = len(self.verses)
        self._doc_lengths = []
        self._word_counts = []
        for verse in self.verses:
            text = (
                (verse.get("text") or "") + " " +
                (verse.get("meaning") or "") + " " +
                (verse.get("translation") or "")
            ).lower()
            tokens = text.split()
            self._doc_lengths.append(len(tokens))
            counts: Dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            self._word_counts.append(counts)

        self._avg_dl = sum(self._doc_lengths) / max(1, N)
        self._df: Dict[str, int] = {}
        for counts in self._word_counts:
            for token in counts:
                self._df[token] = self._df.get(token, 0) + 1
        logger.info(f"BM25 stats pre-computed for {N} documents")

    def _keyword_score_bm25(self, query: str) -> np.ndarray:
        """Improved keyword matching using a simplified BM25 approach"""
        if not self.verses:
            return np.zeros((0,))

        query_tokens = [t.lower() for t in query.split() if len(t) > 2]
        if not query_tokens:
            return np.zeros(len(self.verses))

        N = len(self.verses)
        # Lazy fallback if not pre-computed (shouldn't happen after startup)
        if not hasattr(self, "_doc_lengths"):
            self._doc_lengths = []
            self._word_counts = []
            for verse in self.verses:
                text = (
                    (verse.get("text") or "") + " " + 
                    (verse.get("meaning") or "") + " " + 
                    (verse.get("translation") or "")
                ).lower()
                tokens = text.split()
                self._doc_lengths.append(len(tokens))
                # Simple word frequency count
                counts = {}
                for t in tokens:
                    counts[t] = counts.get(t, 0) + 1
                self._word_counts.append(counts)
            
            self._avg_dl = sum(self._doc_lengths) / max(1, N)
            # Calculate Document Frequency for items in our corpus
            self._df = {}
            for counts in self._word_counts:
                for token in counts:
                    self._df[token] = self._df.get(token, 0) + 1

        # BM25 parameters
        k1 = 1.5
        b = 0.75
        
        scores = np.zeros(N)
        for token in query_tokens:
            if token not in self._df:
                continue
            
            # Inverse Document Frequency
            df_t = self._df[token]
            idf = np.log((N - df_t + 0.5) / (df_t + 0.5) + 1.0)
            
            for i in range(N):
                tf = self._word_counts[i].get(token, 0)
                if tf == 0:
                    continue
                
                # TF normalization
                score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (self._doc_lengths[i] / self._avg_dl)))
                scores[i] += score
                
        # Normalize scores to [0, 1] for fusion
        max_score = np.max(scores)
        if max_score > 0:
            scores = scores / max_score
            
        return scores

    async def _rerank_results(self, query: str, results: List[Dict], intent: Optional[str] = None) -> List[Dict]:
        """Neural re-ranking for higher precision with intent-based weighting"""
        if not results:
            return results
            
        self._ensure_reranker_model()
        
        # Pairs for cross-encoder
        pairs = []
        for doc in results:
            content = f"{doc.get('text', '')} {doc.get('meaning', '')}"
            pairs.append([query, content])

        try:
            # Cross-encoder scores
            if hasattr(self, "_reranker_model") and self._reranker_model is not None:
                re_scores = self._reranker_model.predict(pairs)
            else:
                re_scores = [0.0] * len(results)
            
            # Attach and re-sort
            for i, score in enumerate(re_scores):
                results[i]["rerank_score"] = float(score)
                
                # Dynamic Intent-Based Weighting
                weighting_adjustment = 0.0
                doc_type = results[i].get("type", "scripture")
                doc_text = (results[i].get("text", "") + " " + results[i].get("reference", "")).lower()
                
                # 1. Penalize Temple/Locations for non-spatial intents
                spatial_keywords = ["maidan", "ground", "complex", "road", "street", "near"]
                is_spatial = any(k in doc_text for k in spatial_keywords) or doc_type == "temple"
                
                query_lower = query.lower()
                is_story_request = any(k in query_lower for k in ["story", "legend", "tale", "katha", "parable"])

                if intent in ["SEEKING_GUIDANCE", "EXPRESSING_EMOTION", "OTHER"] or is_story_request:
                    if is_spatial:
                        # Very heavy penalty for locations when seeking wisdom or stories
                        weighting_adjustment -= 3.0 if is_story_request else 1.5
                    if doc_type == "procedural" or doc_type == "scripture":
                        # Significant boost for wisdom sources
                        weighting_adjustment += 1.5 if is_story_request else 1.0
                
                # 2. Boost Procedural for Guidance
                if intent == "SEEKING_GUIDANCE" and doc_type == "procedural":
                    weighting_adjustment += 1.0
                
                # 3. Boost Temples ONLY for specific intents
                if intent == "ASKING_INFO" and is_spatial:
                    weighting_adjustment += 0.5
                
                # 4. 🔥 NEW: Explicit "How-to" boost for procedural rituals
                is_howto = any(k in query_lower for k in ["how", "step", "procedure", "ritual", "guide", "method"])
                if is_howto and doc_type == "procedural":
                    weighting_adjustment += 1.5 # Aggressive boost for procedural steps

                # Combined retrieval score + neural score + manual weighting
                # (30% retrieval, 50% rerank, 20% intent weight - removing multiplier for direct impact)
                results[i]["final_score"] = (0.3 * results[i]["score"]) + (0.5 * float(score)) + weighting_adjustment

            # Sort by final score
            results.sort(key=lambda x: x["final_score"], reverse=True)
            logger.info(f"Neural re-ranking with intent='{intent}' complete")
            return results
        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            return results

    async def search(
        self,
        query: str,
        scripture_filter: Optional[List[str]] = None,
        language: str = "en",
        top_k: int = settings.RETRIEVAL_TOP_K,
        intent: Optional[str] = None,
        min_score: float = 0.12,
        doc_type_filter: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Advanced RAG Search:
        1. Contextual Query Expansion
        2. Hybrid Search (Semantic + BM25)
        3. Initial Candidate Retrieval
        4. Neural Re-ranking with Intent-Based Weighting
        """
        if not self.available or not self.verses:
            return []

        if not query.strip():
            return []

        # 1. Query Expansion (optional, helpful for short queries)
        expanded_queries = [query]
        if len(query.split()) < 4:
            expanded_queries = await self._expand_query(query)

        # 🚀 Parallel Execution: Embeddings for all expansions
        # Execute semantic search and BM25 concurrently for significant latency reduction
        async def get_all_semantic_scores():
            tasks = [self.generate_embeddings(q) for q in expanded_queries]
            vecs = await asyncio.gather(*tasks)
            all_scores = [self._cosine_similarities(v) for v in vecs]
            return np.max(np.array(all_scores), axis=0)

        # 3. Hybrid Search (Parallel EXECUTION)
        semantic_task = get_all_semantic_scores()
        keyword_task = asyncio.to_thread(self._keyword_score_bm25, query)
        
        semantic_scores, keyword_scores = await asyncio.gather(semantic_task, keyword_task)
        
        # Fusion (70% semantic weight)
        fused_scores = (0.7 * semantic_scores) + (0.3 * keyword_scores)

        # 4. Fetch enough candidates for re-ranking (e.g. 20)
        candidates_k = max(20, top_k * 2)
        k_search = min(candidates_k, fused_scores.shape[0])
        
        if k_search <= 0:
            return []
            
        candidate_indices = np.argpartition(-fused_scores, k_search - 1)[:k_search]
        sorted_indices = candidate_indices[np.argsort(-fused_scores[candidate_indices])]

        results: List[Dict] = []
        for idx in sorted_indices:
            score = float(fused_scores[int(idx)])
            verse = self.verses[int(idx)]
            
            # Metadata filtering
            if scripture_filter:
                verse_scripture = verse.get("scripture")
                if isinstance(scripture_filter, list):
                    if verse_scripture not in scripture_filter:
                        continue
                elif verse_scripture != scripture_filter:
                    continue
                
            results.append({**verse, "score": score})
            if len(results) >= candidates_k:
                break

        # 5. Neural Re-ranking (Cross-Encoder)
        results = await self._rerank_results(query, results, intent=intent)

        # 6. Minimum score gate — drop irrelevant candidates
        if min_score > 0:
            before = len(results)
            results = [r for r in results if self._get_best_score(r) >= min_score]
            dropped = before - len(results)
            if dropped:
                logger.info(f"min_score gate: dropped {dropped} doc(s) below threshold={min_score}")

        # 7. Doc-type exclusion filter
        if doc_type_filter:
            excluded_types = {t.lower() for t in doc_type_filter}
            before = len(results)
            results = [r for r in results if (r.get("type") or "scripture").lower() not in excluded_types]
            dropped = before - len(results)
            if dropped:
                logger.info(f"doc_type_filter: dropped {dropped} doc(s) of types={doc_type_filter}")

        # Limit to final top_k
        final_results = results[:top_k]
        
        logger.info(f"Advanced RAG: retrieved {len(final_results)} verses for query='{query[:40]}' with intent='{intent}'")
        return final_results

    # ------------------------------------------------------------------
    # High‑level text QA (used by /api/text/query)
    # ------------------------------------------------------------------

    async def query(
        self,
        query: str,
        language: str = "en",
        include_citations: bool = True,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        RAG‑augmented QA for standalone text queries with caching.
        """
        cache = get_cache_service()
        
        # 1. Try to get from cache
        # Note: we use a limited history slice for cache key stability
        history_key = str(conversation_history[-2:]) if conversation_history else ""
        cache_params = {
            "query": query,
            "language": language,
            "citations": include_citations,
            "history": history_key
        }
        
        cached_res = await cache.get("rag_query", **cache_params)
        if cached_res:
            return cached_res

        # Retrieve context first
        docs = await self.search(
            query=query, 
            scripture_filter=None, 
            language=language, 
            top_k=settings.RETRIEVAL_TOP_K
        )

        # If LLM is available, let it synthesize an answer
        if self._llm.available:
            answer = await self._llm.generate_response(
                query=query,
                context_docs=docs,
                language=language,
                conversation_history=conversation_history or [],
            )
        else:
            # Very simple fallback that just echoes top verse text
            if docs:
                top = docs[0]
                answer = top.get("text") or top.get("meaning") or "I found a relevant verse for you."
            else:
                answer = "I couldn't find a specific verse, but I'm here to listen to what you're going through."

        citations: List[Dict] = []
        if include_citations:
            for doc in docs[:3]: # Show up to 3 citations
                citations.append(
                    {
                        "reference": doc.get("reference", ""),
                        "scripture": doc.get("scripture", ""),
                        "text": (doc.get("text") or "")[:200],
                        "score": doc.get("score", 0.0),
                    }
                )

        confidence = 1.0 if docs and docs[0].get('score', 0) > 0.4 else (0.5 if docs else 0.0)

        result = {
            "answer": answer,
            "citations": citations,
            "confidence": confidence,
        }

        # 3. Store in cache (expire after 1 hour by default)
        await cache.set("rag_query", result, ttl=3600, **cache_params)

        return result

    async def query_stream(
        self,
        query: str,
        language: str = "en",
        include_citations: bool = True,
        conversation_history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        True streaming version of standalone text query.
        """
        # 1. Retrieval
        docs = await self.search(
            query=query, 
            scripture_filter=None, 
            language=language, 
            top_k=settings.RETRIEVAL_TOP_K
        )

        # 2. Build metadata chunk
        citations: List[Dict] = []
        if include_citations:
            for doc in docs[:3]:
                citations.append(
                    {
                        "reference": doc.get("reference", ""),
                        "scripture": doc.get("scripture", ""),
                        "text": (doc.get("text") or "")[:200],
                        "score": doc.get("score", 0.0),
                    }
                )

        confidence = 1.0 if docs and docs[0].get('score', 0) > 0.4 else (0.5 if docs else 0.0)

        # Yield metadata first
        yield {
            "type": "meta",
            "citations": citations,
            "confidence": confidence,
        }

        # 3. Stream Synthesis
        if self._llm.available:
            # Use generate_response_stream for token-by-token delivery
            async for token in self._llm.generate_response_stream(
                query=query,
                context_docs=docs,
                language=language,
                conversation_history=conversation_history or [],
            ):
                yield {
                    "type": "answer",
                    "text": token,
                }
        else:
            # Simple fallback
            if docs:
                top = docs[0]
                answer = top.get("text") or top.get("meaning") or "I found a relevant verse for you."
            else:
                answer = "I'm here to listen to what you're going through."
            
            yield {
                "type": "answer",
                "text": answer,
            }
