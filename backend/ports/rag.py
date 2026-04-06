"""Port interface for RAG (Retrieval-Augmented Generation) pipeline."""
from typing import Dict, List, Optional, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class RAGPort(Protocol):
    """Contract for scripture retrieval and embedding generation."""

    @property
    def available(self) -> bool: ...

    async def search(
        self,
        query: str,
        scripture_filter: Optional[List[str]] = None,
        language: str = "en",
        top_k: int = 7,
        intent: Optional[str] = None,
        min_score: float = 0.15,
        doc_type_filter: Optional[List[str]] = None,
        life_domain: Optional[str] = None,
        query_variants: Optional[List[str]] = None,
    ) -> List[Dict]: ...

    async def generate_embeddings(
        self,
        text: str,
        is_query: bool = True,
    ) -> np.ndarray: ...
