"""
Gemini 2.0 Flash provider for intent classification evaluation.
"""

import asyncio
import json
import logging
import re
import time
from typing import Dict

from config import settings
from llm.providers.base import IntentProvider, IntentResponse

logger = logging.getLogger(__name__)


class GeminiFastIntentProvider(IntentProvider):
    """Gemini 2.0 Flash intent classifier — mirrors existing IntentAgent."""

    def __init__(self, model: str = None):
        from google import genai
        self._model = model or settings.EVAL_GEMINI_FAST_MODEL
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    @property
    def name(self) -> str:
        return f"gemini:{self._model}"

    @property
    def cost_per_1k_input(self) -> float:
        return 0.0001  # $0.10 per 1M

    @property
    def cost_per_1k_output(self) -> float:
        return 0.0004  # $0.40 per 1M

    async def classify(self, prompt: str) -> IntentResponse:
        def _sync():
            return self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config={
                    "temperature": settings.INTENT_TEMPERATURE,
                    "response_mime_type": "application/json",
                    "automatic_function_calling": {"disable": True},
                },
            )

        start = time.perf_counter()
        response = await asyncio.to_thread(_sync)
        latency = (time.perf_counter() - start) * 1000

        raw_text = response.text.strip() if response.text else ""
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
        output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

        parse_success = False
        parsed = {}
        try:
            cleaned = raw_text
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed = json.loads(cleaned)
            parse_success = True
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Gemini Flash JSON parse error: {e}")

        return IntentResponse(
            raw_json=parsed,
            model=self._model,
            provider="gemini",
            latency_ms=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calculate_cost(input_tokens, output_tokens),
            parse_success=parse_success,
            raw_text=raw_text,
        )
