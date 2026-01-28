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
    Lightweight RAG pipeline that:
    - loads pre‑computed verse embeddings from data/processed
    - performs cosine‑similarity search
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

        If the processed file doesn't exist yet, the pipeline will stay
        in a "not available" state but the API will still behave
        gracefully (returning safe fallbacks instead of crashing).
        """
        try:
            base_dir = Path(__file__).parent.parent
            processed_path = base_dir / "data" / "processed" / "all_scriptures_processed.json"

            if not processed_path.exists():
                logger.warning(
                    f"RAGPipeline: processed data not found at {processed_path}. "
                    "Run scripts/ingest_all_data.py to create it."
                )
                self.available = False
                return

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

            self.embeddings = np.asarray(emb_list, dtype="float32")
            if self.embeddings.ndim != 2:
                logger.error(f"RAGPipeline: unexpected embedding shape {self.embeddings.shape}")
                self.available = False
                return

            self.dim = self.embeddings.shape[1]
            self.available = True

            logger.info(
                f"RAGPipeline initialized with {len(self.verses)} verses "
                f"(dim={self.dim})"
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

        vec = self._embedding_model.encode([text], convert_to_tensor=False)[0]
        return np.asarray(vec, dtype="float32")

    # ------------------------------------------------------------------
    # Core search
    # ------------------------------------------------------------------

    def _cosine_similarities(self, query_vec: np.ndarray) -> np.ndarray:
        if self.embeddings is None or not self.available:
            return np.zeros((0,), dtype="float32")

        # Normalise
        q = query_vec.astype("float32")
        q_norm = np.linalg.norm(q) or 1.0
        q = q / q_norm

        docs = self.embeddings
        doc_norms = np.linalg.norm(docs, axis=1, keepdims=True)
        doc_norms[doc_norms == 0.0] = 1.0
        normed_docs = docs / doc_norms

        return normed_docs @ q

    async def search(
        self,
        query: str,
        scripture_filter: Optional[str] = None,
        language: str = "en",
        top_k: int = 5,
    ) -> List[Dict]:
        """
        Low‑level search API used by:
        - /api/scripture/search
        - conversational flow when building wisdom responses
        """
        if not self.available or not self.verses:
            logger.warning("RAGPipeline.search called but pipeline is not available")
            return []

        if not query.strip():
            logger.warning("RAGPipeline.search received empty query")
            return []

        query_vec = await self.generate_embeddings(query)
        sims = self._cosine_similarities(query_vec)
        if sims.size == 0:
            return []

        # Rank indices by similarity
        top_k = min(top_k, sims.shape[0])
        top_indices = np.argsort(-sims)[:top_k]

        results: List[Dict] = []
        for idx in top_indices:
            verse = self.verses[int(idx)]
            if scripture_filter and verse.get("scripture") != scripture_filter:
                continue
            results.append(
                {
                    **verse,
                    "score": float(sims[int(idx)]),
                }
            )

        logger.info(f"RAGPipeline.search: retrieved {len(results)} verses for query='{query[:60]}'")
        return results

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
        docs = await self.search(query=query, scripture_filter=None, language=language, top_k=5)

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
            for doc in docs[:2]:
                citations.append(
                    {
                        "reference": doc.get("reference", ""),
                        "scripture": doc.get("scripture", ""),
                        "text": (doc.get("text") or "")[:200],
                        "score": doc.get("score", 0.0),
                    }
                )

        return {
            "answer": answer,
            "citations": citations,
            "confidence": 1.0 if docs else 0.3,
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
