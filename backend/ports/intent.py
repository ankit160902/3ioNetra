"""Port interface for intent classification."""
from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class IntentPort(Protocol):
    """Contract for analyzing user intent from messages."""

    @property
    def available(self) -> bool: ...

    async def analyze_intent(
        self,
        message: str,
        context_summary: str = "",
    ) -> Dict[str, Any]: ...
