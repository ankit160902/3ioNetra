"""Port interface for long-term memory service."""
from typing import List, Protocol, runtime_checkable


@runtime_checkable
class MemoryPort(Protocol):
    """Contract for storing and retrieving user conversation memories."""

    async def store_memory(
        self,
        user_id: str,
        text: str,
    ) -> None: ...
    

    async def retrieve_relevant_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        intent: str = "",
    ) -> List[str]: ...

    def set_rag_pipeline(self, rag_pipeline) -> None: ...
