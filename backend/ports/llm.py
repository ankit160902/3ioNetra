"""Port interface for LLM service (Gemini, Claude, OpenAI, etc.)."""
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable

from models.session import ConversationPhase


@runtime_checkable
class LLMPort(Protocol):
    """Contract for language model interactions."""

    @property
    def available(self) -> bool: ...

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
    ) -> str: ...

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
    ) -> AsyncIterator[str]: ...
