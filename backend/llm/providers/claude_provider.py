"""
Claude Sonnet provider for response generation evaluation.
"""

import asyncio
import logging
import time
from typing import Dict, Optional

from config import settings
from llm.providers.base import LLMResponse, ResponseProvider

logger = logging.getLogger(__name__)


class ClaudeResponseProvider(ResponseProvider):
    """Wraps anthropic SDK for Claude Sonnet."""

    def __init__(self, model: str = None):
        import anthropic
        self._model = model or settings.EVAL_CLAUDE_MODEL
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    @property
    def name(self) -> str:
        return f"claude:{self._model}"

    @property
    def cost_per_1k_input(self) -> float:
        return 0.003  # $3.00 per 1M

    @property
    def cost_per_1k_output(self) -> float:
        return 0.015  # $15.00 per 1M

    async def generate(
        self,
        query: str,
        system_instruction: str,
        phase_instructions: str,
        user_profile: Optional[Dict] = None,
    ) -> LLMResponse:
        user_content = self._build_prompt(query, phase_instructions, user_profile)

        def _sync():
            return self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                temperature=0.7,
                system=system_instruction,
                messages=[{"role": "user", "content": user_content}],
            )

        start = time.perf_counter()
        response = await asyncio.to_thread(_sync)
        latency = (time.perf_counter() - start) * 1000

        text = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        return LLMResponse(
            text=text,
            model=self._model,
            provider="claude",
            latency_ms=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calculate_cost(input_tokens, output_tokens),
        )

    # _build_prompt inherited from ResponseProvider base class
