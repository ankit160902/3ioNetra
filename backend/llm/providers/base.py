"""
Abstract base classes and dataclasses for multi-model providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    text: str
    model: str
    provider: str           # "gemini" | "claude" | "openai"
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class IntentResponse:
    """Standardized intent classification response."""
    raw_json: Dict
    model: str
    provider: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    parse_success: bool
    raw_text: str = ""


class ResponseProvider(ABC):
    """Abstract base for response-generation providers (Task 6)."""

    @abstractmethod
    async def generate(
        self,
        query: str,
        system_instruction: str,
        phase_instructions: str,
        user_profile: Optional[Dict] = None,
    ) -> LLMResponse:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def cost_per_1k_input(self) -> float:
        """Cost per 1K input tokens in USD."""
        ...

    @property
    @abstractmethod
    def cost_per_1k_output(self) -> float:
        """Cost per 1K output tokens in USD."""
        ...

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1000 * self.cost_per_1k_input +
                output_tokens / 1000 * self.cost_per_1k_output)

    @staticmethod
    def _build_prompt(query: str, phase_instructions: str, user_profile: Optional[Dict]) -> str:
        profile_text = ""
        if user_profile:
            parts = []
            for key, val in user_profile.items():
                if val:
                    parts.append(f"   - {key}: {val}")
            if parts:
                profile_text = "\nWHO YOU ARE SPEAKING TO:\n" + "\n".join(parts) + "\n"

        return f"""{profile_text}
User's message:
{query}

YOUR INSTRUCTIONS FOR THIS PHASE:
{phase_instructions}

BEFORE YOU RESPOND — CHECK THESE:
- Don't open with "I hear you", "It sounds like", "I understand" — say something specific.
- No numbered lists or bullet points. Flowing sentences only.
- Don't end with "How does that sound?" or "Would you like to hear more?" — just end.
- One verse maximum per response, only if it truly fits.

Your response:""".strip()


class IntentProvider(ABC):
    """Abstract base for intent-classification providers (Task 7)."""

    @abstractmethod
    async def classify(self, prompt: str) -> IntentResponse:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def cost_per_1k_input(self) -> float:
        ...

    @property
    @abstractmethod
    def cost_per_1k_output(self) -> float:
        ...

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1000 * self.cost_per_1k_input +
                output_tokens / 1000 * self.cost_per_1k_output)
