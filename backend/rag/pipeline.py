import json
import logging
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

import numpy as np

from config import settings
from llm.service import get_llm_service

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
        self._embedding_model = None  # lazy‑loaded
        self._llm = get_llm_service()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """
        Load processed scripture data + embeddings from disk.
        Pre-computes vector norms for efficient cosine similarity search.
        """
        try:
            base_dir = Path(__file__).parent.parent
            processed_path = base_dir / "data" / "processed" / "processed_data.json"

            if not processed_path.exists():
                logger.warning(
                    f"RAGPipeline: processed data not found at {processed_path}. "
                    "Run scripts/ingest_all_data.py to create it."
                )
                self.available = False
                return

            logger.info(f"RAGPipeline: Loading processed data from {processed_path}...")
            # Use chunks if file is massive, but for 2GB we might load it all if RAM allows.
            # Assuming standard server RAM, loading 2GB JSON into memory is heavy but doable.
            with processed_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            self.verses = payload.get("verses", [])
            if not self.verses:
                logger.warning("RAGPipeline: no verses in processed data")
                self.available = False
                return

            # Extract embeddings into a single float32 matrix
            emb_list = [v.get("embedding") for v in self.verses if v.get("embedding") is not None]
            if not emb_list:
                logger.warning("RAGPipeline: verses missing embeddings")
                self.available = False
                return

            raw_embeddings = np.asarray(emb_list, dtype="float32")
            if raw_embeddings.ndim != 2:
                logger.error(f"RAGPipeline: unexpected embedding shape {raw_embeddings.shape}")
                self.available = False
                return

            self.dim = raw_embeddings.shape[1]
            
            # Pre-normalize embeddings for cosine similarity
            #Cosine Similarity(A, B) = (A . B) / (||A|| * ||B||)
            # If we pre-normalize A (docs), then we only need to normalize B (query) and do dot product.
            norms = np.linalg.norm(raw_embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0  # Avoid division by zero
            self.embeddings = raw_embeddings / norms
            
            self.available = True

            scripture_counts = {}
            for v in self.verses:
                s = v.get("scripture", "Unknown")
                scripture_counts[s] = scripture_counts.get(s, 0) + 1

            logger.info(
                f"RAGPipeline initialized with {len(self.verses)} verses "
                f"(dim={self.dim}). Breakdown: {scripture_counts}"
            )
        except Exception as exc:
            logger.exception(f"Failed to initialize RAGPipeline: {exc}")
            self.available = False

    # ------------------------------------------------------------------
    # Embedding utilities
    # ------------------------------------------------------------------

    def _ensure_embedding_model(self) -> None:
        if self._embedding_model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer

            model_name = settings.EMBEDDING_MODEL
            logger.info(f"RAGPipeline: loading embedding model '{model_name}'")
            self._embedding_model = SentenceTransformer(model_name)
        except Exception as exc:
            logger.exception(f"RAGPipeline: failed to load embedding model: {exc}")
            self._embedding_model = None

    def _ensure_reranker_model(self) -> None:
        if hasattr(self, "_reranker_model") and self._reranker_model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            # Small but effective re-ranker
            model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
            logger.info(f"RAGPipeline: loading re-ranker model '{model_name}'")
            self._reranker_model = CrossEncoder(model_name)
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
        vec = self._embedding_model.encode([clean_text], convert_to_tensor=False)[0]
        return np.asarray(vec, dtype="float32")

    # ------------------------------------------------------------------
    # Query Expansion
    # ------------------------------------------------------------------

    async def _expand_query(self, query: str) -> List[str]:
        """Use LLM to expand the query for better recall"""
        if not self._llm.available:
            return [query]

        prompt = f"""
        Expand the following spiritual query into 2 alternative search terms that capture different aspects of the request.
        Original: "{query}"
        Respond ONLY with the 2 terms, separated by a newline. Do not include numbering or bullets.
        """
        try:
            expansion = await self._llm.generate_response(query=prompt, conversation_history=[])
            expanded_terms = [t.strip() for t in expansion.split("\n") if t.strip()]
            logger.info(f"Query expansion: {expanded_terms}")
            return [query] + expanded_terms[:2]
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return [query]

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

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

    def _keyword_score_bm25(self, query: str) -> np.ndarray:
        """Improved keyword matching using a simplified BM25 approach"""
        if not self.verses:
            return np.zeros((0,))
        
        # We'll use a fast custom implementation for mid-sized datasets
        # In a production setting with millions of docs, we'd use a dedicated library
        query_tokens = [t.lower() for t in query.split() if len(t) > 2]
        if not query_tokens:
            return np.zeros(len(self.verses))

        N = len(self.verses)
        # Pre-calculating doc lengths if not already done
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

    async def _rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """Neural re-ranking for higher precision"""
        if not results:
            return results
            
        self._ensure_reranker_model()
        if not hasattr(self, "_reranker_model") or self._reranker_model is None:
            return results

        # Pairs for cross-encoder
        pairs = []
        for doc in results:
            content = f"{doc.get('text', '')} {doc.get('meaning', '')}"
            pairs.append([query, content])

        try:
            # Cross-encoder scores
            re_scores = self._reranker_model.predict(pairs)
            
            # Attach and re-sort
            for i, score in enumerate(re_scores):
                results[i]["rerank_score"] = float(score)
                # Combine original retrieval score with neural score (70% rerank weight)
                results[i]["final_score"] = 0.3 * results[i]["score"] + 0.7 * float(score)

            # Sort by final score
            results.sort(key=lambda x: x["final_score"], reverse=True)
            logger.info("Neural re-ranking complete")
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
    ) -> List[Dict]:
        """
        Advanced RAG Search:
        1. Contextual Query Expansion
        2. Hybrid Search (Semantic + BM25)
        3. Initial Candidate Retrieval
        4. Neural Re-ranking
        """
        if not self.available or not self.verses:
            return []

        if not query.strip():
            return []

        # 1. Query Expansion (optional, helpful for short queries)
        expanded_queries = [query]
        if len(query.split()) < 4:
            expanded_queries = await self._expand_query(query)

        # 2. Multi-Vector Semantic Search & Keyword Search
        all_semantic_scores = []
        for q in expanded_queries:
            q_vec = await self.generate_embeddings(q)
            all_semantic_scores.append(self._cosine_similarities(q_vec))
        
        # Merge semantic scores (max pool across expansions)
        semantic_scores = np.max(np.array(all_semantic_scores), axis=0)
        
        # 3. Hybrid Search: Semantic + BM25
        keyword_scores = self._keyword_score_bm25(query)
        
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
        results = await self._rerank_results(query, results)

        # Limit to final top_k
        final_results = results[:top_k]
        
        logger.info(f"Advanced RAG: retrieved {len(final_results)} verses for query='{query[:40]}'")
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
        RAG‑augmented QA for standalone text queries.
        """
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

        return {
            "answer": answer,
            "citations": citations,
            "confidence": confidence,
        }

    async def query_stream(
        self,
        query: str,
        language: str = "en",
        include_citations: bool = True,
        conversation_history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        Simple streaming wrapper over `query`.

        For now we emit the full answer in a single chunk so that the
        existing SSE plumbing in `main.py` works without change.
        """
        result = await self.query(
            query=query,
            language=language,
            include_citations=include_citations,
            conversation_history=conversation_history,
        )

        # First send metadata
        yield {
            "type": "meta",
            "citations": result.get("citations", []),
            "confidence": result.get("confidence", 0.0),
        }

        # Then the full text as one chunk
        yield {
            "type": "answer",
            "text": result.get("answer", ""),
        }
