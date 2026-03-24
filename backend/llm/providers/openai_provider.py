"""
GPT-4o provider for response generation evaluation.
"""

import asyncio
import logging
import time
from typing import Dict, Optional

from config import settings
from llm.providers.base import LLMResponse, ResponseProvider

logger = logging.getLogger(__name__)


class OpenAIResponseProvider(ResponseProvider):
    """Wraps openai SDK for GPT-4o."""

    def __init__(self, model: str = None):
        from openai import OpenAI
        self._model = model or settings.EVAL_OPENAI_MODEL
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    @property
    def cost_per_1k_input(self) -> float:
        return 0.0025  # $2.50 per 1M

    @property
    def cost_per_1k_output(self) -> float:
        return 0.01  # $10.00 per 1M

    async def generate(
        self,
        query: str,
        system_instruction: str,
        phase_instructions: str,
        user_profile: Optional[Dict] = None,
    ) -> LLMResponse:
        user_content = self._build_prompt(query, phase_instructions, user_profile)

        def _sync():
            return self._client.chat.completions.create(
                model=self._model,
                temperature=0.7,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_content},
                ],
            )

        start = time.perf_counter()
        response = await asyncio.to_thread(_sync)
        latency = (time.perf_counter() - start) * 1000

        text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return LLMResponse(
            text=text,
            model=self._model,
            provider="openai",
            latency_ms=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calculate_cost(input_tokens, output_tokens),
        )

    # _build_prompt inherited from ResponseProvider base class
