"""
Claude Haiku provider for intent classification evaluation.
"""

import asyncio
import json
import logging
import re
import time

from config import settings
from llm.providers.base import IntentProvider, IntentResponse

logger = logging.getLogger(__name__)


class ClaudeHaikuIntentProvider(IntentProvider):
    """Claude Haiku intent classifier."""

    def __init__(self, model: str = None):
        import anthropic
        self._model = model or settings.EVAL_CLAUDE_HAIKU_MODEL
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    @property
    def name(self) -> str:
        return f"claude:{self._model}"

    @property
    def cost_per_1k_input(self) -> float:
        return 0.001  # $1.00 per 1M

    @property
    def cost_per_1k_output(self) -> float:
        return 0.005  # $5.00 per 1M

    async def classify(self, prompt: str) -> IntentResponse:
        system_msg = (
            "You are an intent classification system. "
            "Respond with ONLY a valid JSON object. No markdown, no code fences, no explanation."
        )

        def _sync():
            return self._client.messages.create(
                model=self._model,
                max_tokens=512,
                temperature=0.1,
                system=system_msg,
                messages=[{"role": "user", "content": prompt}],
            )

        start = time.perf_counter()
        response = await asyncio.to_thread(_sync)
        latency = (time.perf_counter() - start) * 1000

        raw_text = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

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
            logger.warning(f"Claude Haiku JSON parse error: {e}")

        return IntentResponse(
            raw_json=parsed,
            model=self._model,
            provider="claude",
            latency_ms=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=self._calculate_cost(input_tokens, output_tokens),
            parse_success=parse_success,
            raw_text=raw_text,
        )
