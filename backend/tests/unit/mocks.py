"""Mock implementations of port interfaces for testing.

Each mock satisfies its port Protocol structurally (duck typing).
No real LLM calls, no Redis, no MongoDB, no ML models.
"""
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import numpy as np

from models.session import ConversationPhase, SessionState


class MockLLM:
    """Mock LLM that returns deterministic responses."""

    def __init__(self, response: str = "I am here with you, friend.", available: bool = True):
        self._response = response
        self._available = available
        self.last_usage = {"input_tokens": 100, "output_tokens": 50}
        self.call_count = 0
        self.last_query = None
        # Needed by companion_engine for Gemini client access
        self.client = None

    @property
    def available(self) -> bool:
        return self._available

    async def generate_response(
        self,
        query: str,
        context_docs: Optional[List[Dict]] = None,
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        phase: Optional[ConversationPhase] = None,
        memory_context: Optional[Any] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
    ) -> str:
        self.call_count += 1
        self.last_query = query
        return self._response

    async def generate_response_stream(
        self,
        query: str,
        context_docs: Optional[List[Dict]] = None,
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        phase: Optional[ConversationPhase] = None,
        memory_context: Optional[Any] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
    ) -> AsyncIterator[str]:
        self.call_count += 1
        self.last_query = query
        for word in self._response.split():
            yield word + " "


class MockRAG:
    """Mock RAG pipeline that returns empty results or configurable docs."""

    def __init__(self, docs: Optional[List[Dict]] = None, available: bool = True):
        self._docs = docs or []
        self._available = available
        self._embedding_model = None

    @property
    def available(self) -> bool:
        return self._available

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
    ) -> List[Dict]:
        return self._docs[:top_k]

    async def generate_embeddings(
        self,
        text: str,
        is_query: bool = True,
    ) -> np.ndarray:
        # Return a deterministic 1024-dim embedding
        np.random.seed(hash(text) % (2**31))
        vec = np.random.randn(1024).astype(np.float32)
        return vec / np.linalg.norm(vec)


class MockIntent:
    """Mock intent classifier returning configurable analysis."""

    def __init__(self, analysis: Optional[Dict] = None, available: bool = True):
        self._analysis = analysis or {
            "intent": "EXPRESSING_EMOTION",
            "emotion": "anxiety",
            "life_domain": "career",
            "entities": {},
            "urgency": "normal",
            "summary": "User is expressing concern",
            "needs_direct_answer": False,
            "recommend_products": False,
            "product_search_keywords": [],
            "product_rejection": False,
            "query_variants": [],
        }
        self._available = available
        self.call_count = 0
        self.last_message = None

    @property
    def available(self) -> bool:
        return self._available

    async def analyze_intent(
        self,
        message: str,
        context_summary: str = "",
    ) -> Dict[str, Any]:
        self.call_count += 1
        self.last_message = message
        return dict(self._analysis)


class MockMemory:
    """Mock memory service that stores/retrieves in-memory."""

    def __init__(self):
        self._memories: Dict[str, List[str]] = {}
        self.store_count = 0
        self.retrieve_count = 0

    async def store_memory(self, user_id: str, text: str) -> None:
        self.store_count += 1
        self._memories.setdefault(user_id, []).append(text)

    async def retrieve_relevant_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        intent: str = "",
    ) -> List[str]:
        self.retrieve_count += 1
        return self._memories.get(user_id, [])[:top_k]

    def set_rag_pipeline(self, rag_pipeline) -> None:
        pass


class MockProduct:
    """Mock product service returning configurable products."""

    def __init__(self, products: Optional[List[Dict]] = None):
        self._products = products or []
        self.search_count = 0

    async def search_products(
        self,
        query_text: str,
        life_domain: str = "unknown",
        limit: int = 5,
        emotion: str = "",
        deity: str = "",
        allow_category_fallback: bool = True,
    ) -> List[Dict[str, Any]]:
        self.search_count += 1
        return self._products[:limit]

    async def get_recommended_products(
        self,
        category: Optional[str] = None,
        limit: int = 4,
    ) -> List[Dict[str, Any]]:
        return self._products[:limit]


class MockSafety:
    """Mock safety validator — no crisis, no changes."""

    def __init__(self, is_crisis: bool = False, crisis_response: Optional[str] = None):
        self._is_crisis = is_crisis
        self._crisis_response = crisis_response

    async def check_crisis_signals(
        self,
        session: SessionState,
        current_message: str = "",
    ) -> Tuple[bool, Optional[str]]:
        return (self._is_crisis, self._crisis_response)

    async def validate_response(self, response: str) -> str:
        return response

    def append_professional_help(
        self,
        response: str,
        help_type: str,
        already_mentioned: bool = False,
    ) -> str:
        return response
