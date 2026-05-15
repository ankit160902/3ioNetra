"""
Pluggable embedding and reranker backend abstraction for model comparison.

Provides lazy-loaded factories for embedding and reranking models so that
evaluation scripts can compare multiple models without downloading all at import.

Usage:
    from rag.model_registry import get_embedding_backend, get_reranker_backend

    emb = get_embedding_backend("multilingual-e5-large")
    vecs, elapsed = emb.encode_timed(texts)

    rer = get_reranker_backend("bge-reranker-v2-m3")
    scores, elapsed = rer.rerank_timed(query, documents)
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Embedding Backends
# ═══════════════════════════════════════════════════════════════════

class EmbeddingBackend(ABC):
    """Abstract base for embedding models."""

    name: str
    dim: int

    @abstractmethod
    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """Encode texts into embedding vectors."""
        ...

    def encode_timed(self, texts: List[str], normalize: bool = True) -> Tuple[np.ndarray, float]:
        """Encode and return (embeddings, elapsed_seconds)."""
        start = time.perf_counter()
        embeddings = self.encode(texts, normalize=normalize)
        elapsed = time.perf_counter() - start
        return embeddings, elapsed


class SentenceTransformerBackend(EmbeddingBackend):
    """Local SentenceTransformer-based embedding backend."""

    def __init__(self, model_name: str, dim: int):
        self.name = model_name
        self.dim = dim
        self._model = None
        self._model_name = model_name

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        self._ensure_model()
        embeddings = self._model.encode(
            texts,
            convert_to_tensor=False,
            show_progress_bar=len(texts) > 100,
            normalize_embeddings=normalize,
        )
        return np.asarray(embeddings, dtype="float32")


class CohereEmbeddingBackend(EmbeddingBackend):
    """Cohere API-based embedding backend."""

    def __init__(self, model_name: str, dim: int):
        self.name = model_name
        self.dim = dim
        self._client = None
        self._model_name = model_name

    def _ensure_client(self):
        if self._client is None:
            import cohere
            from config import settings
            self._client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        self._ensure_client()
        # Cohere has a batch limit; chunk into 96-text batches
        all_embeddings = []
        batch_size = 96
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self._client.embed(
                texts=batch,
                model=self._model_name,
                input_type="search_document",
                embedding_types=["float"],
            )
            batch_embs = response.embeddings.float
            all_embeddings.extend(batch_embs)

        result = np.asarray(all_embeddings, dtype="float32")
        if normalize:
            norms = np.linalg.norm(result, axis=1, keepdims=True)
            norms[norms == 0] = 1
            result = result / norms
        return result


class OpenAIEmbeddingBackend(EmbeddingBackend):
    """OpenAI API-based embedding backend."""

    def __init__(self, model_name: str, dim: int):
        self.name = model_name
        self.dim = dim
        self._client = None
        self._model_name = model_name

    def _ensure_client(self):
        if self._client is None:
            from openai import OpenAI
            from config import settings
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def encode(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        self._ensure_client()
        # OpenAI batch limit is 2048
        all_embeddings = []
        batch_size = 512
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self._client.embeddings.create(
                model=self._model_name,
                input=batch,
            )
            for item in response.data:
                all_embeddings.append(item.embedding)

        result = np.asarray(all_embeddings, dtype="float32")
        if normalize:
            norms = np.linalg.norm(result, axis=1, keepdims=True)
            norms[norms == 0] = 1
            result = result / norms
        return result


# Lazy factory lambdas — models are only downloaded when accessed
EMBEDDING_MODELS: Dict[str, callable] = {
    "paraphrase-multilingual-mpnet-base-v2": lambda: SentenceTransformerBackend(
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2", 768
    ),
    "multilingual-e5-large": lambda: SentenceTransformerBackend(
        "intfloat/multilingual-e5-large", 1024
    ),
    "bge-m3": lambda: SentenceTransformerBackend(
        "BAAI/bge-m3", 1024
    ),
    "all-MiniLM-L6-v2": lambda: SentenceTransformerBackend(
        "sentence-transformers/all-MiniLM-L6-v2", 384
    ),
    "cohere-embed-multilingual-v3.0": lambda: CohereEmbeddingBackend(
        "embed-multilingual-v3.0", 1024
    ),
    "text-embedding-3-large": lambda: OpenAIEmbeddingBackend(
        "text-embedding-3-large", 3072
    ),
}


def get_embedding_backend(name: str) -> EmbeddingBackend:
    """Get an embedding backend by short name."""
    factory = EMBEDDING_MODELS.get(name)
    if factory is None:
        available = ", ".join(EMBEDDING_MODELS.keys())
        raise ValueError(f"Unknown embedding model '{name}'. Available: {available}")
    return factory()


# ═══════════════════════════════════════════════════════════════════
# Reranker Backends
# ═══════════════════════════════════════════════════════════════════

class RerankerBackend(ABC):
    """Abstract base for reranking models."""

    name: str

    @abstractmethod
    def rerank(self, query: str, documents: List[str]) -> List[float]:
        """Score query-document pairs. Returns list of relevance scores."""
        ...

    def rerank_timed(self, query: str, documents: List[str]) -> Tuple[List[float], float]:
        """Rerank and return (scores, elapsed_seconds)."""
        start = time.perf_counter()
        scores = self.rerank(query, documents)
        elapsed = time.perf_counter() - start
        return scores, elapsed


class CrossEncoderBackend(RerankerBackend):
    """Local CrossEncoder-based reranker."""

    def __init__(self, model_name: str):
        self.name = model_name
        self._model = None
        self._model_name = model_name

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {self._model_name}")
            self._model = CrossEncoder(self._model_name)

    def rerank(self, query: str, documents: List[str]) -> List[float]:
        self._ensure_model()
        pairs = [[query, doc] for doc in documents]
        scores = self._model.predict(pairs)
        return [float(s) for s in scores]

    def predict(self, pairs: List[List[str]]) -> List[float]:
        """CrossEncoder-compatible predict method for duck-typing in pipeline.py."""
        self._ensure_model()
        scores = self._model.predict(pairs)
        return [float(s) for s in scores]


class CohereRerankerBackend(RerankerBackend):
    """Cohere API-based reranker."""

    def __init__(self, model_name: str):
        self.name = model_name
        self._client = None
        self._model_name = model_name

    def _ensure_client(self):
        if self._client is None:
            import cohere
            from config import settings
            self._client = cohere.ClientV2(api_key=settings.COHERE_API_KEY)

    def rerank(self, query: str, documents: List[str]) -> List[float]:
        self._ensure_client()
        response = self._client.rerank(
            model=self._model_name,
            query=query,
            documents=documents,
            top_n=len(documents),
        )
        # Build ordered scores array matching input document order
        scores = [0.0] * len(documents)
        for result in response.results:
            scores[result.index] = result.relevance_score
        return scores


RERANKER_MODELS: Dict[str, callable] = {
    "ms-marco-MiniLM-L-6-v2": lambda: CrossEncoderBackend(
        "cross-encoder/ms-marco-MiniLM-L-6-v2"
    ),
    "bge-reranker-v2-m3": lambda: CrossEncoderBackend(
        "BAAI/bge-reranker-v2-m3"
    ),
    "mxbai-rerank-large-v1": lambda: CrossEncoderBackend(
        "mixedbread-ai/mxbai-rerank-large-v1"
    ),
    "ms-marco-multilingual-MiniLM-L-12-H384-v1": lambda: CrossEncoderBackend(
        "cross-encoder/ms-marco-multilingual-MiniLM-L-12-H384-v1"
    ),
    "cohere-rerank-multilingual-v3.0": lambda: CohereRerankerBackend(
        "rerank-multilingual-v3.0"
    ),
}


def get_reranker_backend(name: str) -> RerankerBackend:
    """Get a reranker backend by short name."""
    factory = RERANKER_MODELS.get(name)
    if factory is None:
        available = ", ".join(RERANKER_MODELS.keys())
        raise ValueError(f"Unknown reranker model '{name}'. Available: {available}")
    return factory()
