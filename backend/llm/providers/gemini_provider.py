"""
Gemini 2.5 Pro provider for response generation evaluation.
"""

import asyncio
import logging
import time
from typing import Dict, Optional

from config import settings
from llm.providers.base import LLMResponse, ResponseProvider

logger = logging.getLogger(__name__)


class GeminiResponseProvider(ResponseProvider):
    """Wraps google-genai SDK for Gemini 2.5 Pro."""

    def __init__(self, model: str = None):
        from google import genai
        self._model = model or settings.EVAL_GEMINI_MODEL
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @property
    def name(self) -> str:
        return f"gemini:{self._model}"

    @property
    def cost_per_1k_input(self) -> float:
        return 0.00125  # $1.25 per 1M

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
        prompt = self._build_prompt(query, phase_instructions, user_profile)

        def _sync():
            return self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config={
                    "system_instruction": system_instruction,
                    "temperature": 0.7,
                    "max_output_tokens": 1024,
                    "automatic_function_calling": {"disable": True},
                },
            )

        start = time.perf_counter()
        response = await asyncio.to_thread(_sync)
        latency = (time.perf_counter() - start) * 1000

        text = response.text or ""
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

        return LLMResponse(
            text=text,
            model=self._model,
            provider="gemini",
            latency_ms=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calculate_cost(input_tokens, output_tokens),
        )

    # _build_prompt inherited from ResponseProvider base class
