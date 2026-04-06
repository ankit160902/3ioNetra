"""Port interface for safety validation and crisis detection."""
from typing import Optional, Protocol, Tuple, runtime_checkable

from models.session import SessionState


@runtime_checkable
class SafetyPort(Protocol):
    """Contract for crisis detection and response safety validation."""

    async def check_crisis_signals(
        self,
        session: SessionState,
        current_message: str = "",
    ) -> Tuple[bool, Optional[str]]: ...

    async def validate_response(
        self,
        response: str,
    ) -> str: ...

    def append_professional_help(
        self,
        response: str,
        help_type: str,
        already_mentioned: bool = False,
    ) -> str: ...
