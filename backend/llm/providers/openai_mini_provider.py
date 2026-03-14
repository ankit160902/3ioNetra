"""
GPT-4o-mini provider for intent classification evaluation.
"""

import asyncio
import json
import logging
import re
import time

from config import settings
from llm.providers.base import IntentProvider, IntentResponse

logger = logging.getLogger(__name__)


class OpenAIMiniIntentProvider(IntentProvider):
    """GPT-4o-mini intent classifier."""

    def __init__(self, model: str = None):
        from openai import OpenAI
        self._model = model or settings.EVAL_OPENAI_MINI_MODEL
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    @property
    def cost_per_1k_input(self) -> float:
        return 0.00015  # $0.15 per 1M

    @property
    def cost_per_1k_output(self) -> float:
        return 0.0006  # $0.60 per 1M

    async def classify(self, prompt: str) -> IntentResponse:
        def _sync():
            return self._client.chat.completions.create(
                model=self._model,
                temperature=0.1,
                max_tokens=512,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an intent classification system. "
                            "Respond with ONLY a valid JSON object."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )

        start = time.perf_counter()
        response = await asyncio.to_thread(_sync)
        latency = (time.perf_counter() - start) * 1000

        raw_text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        parse_success = False
        parsed = {}
        try:
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed = json.loads(cleaned)
            parse_success = True
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"GPT-4o-mini JSON parse error: {e}")

        return IntentResponse(
            raw_json=parsed,
            model=self._model,
            provider="openai",
            latency_ms=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calculate_cost(input_tokens, output_tokens),
            parse_success=parse_success,
            raw_text=raw_text,
        )
