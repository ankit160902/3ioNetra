"""
Token usage and cost tracking for multi-model routing.

Logs cost per request to structured logger and optionally to MongoDB
with a 90-day TTL for analytics.
"""

import asyncio
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Pricing per 1K tokens (USD) — update as pricing changes
MODEL_PRICING = {
    # Gemini
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.01},
    "gemini-2.5-flash": {"input": 0.0001, "output": 0.0004},
    # Claude
    "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.001, "output": 0.005},
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}


@dataclass
class RequestCostRecord:
    """Single request cost record."""
    timestamp: str
    session_id: str
    model_name: str
    tier: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    intent: str
    phase: str


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token counts."""
    pricing = MODEL_PRICING.get(model_name, {"input": 0.001, "output": 0.005})
    return (input_tokens / 1000 * pricing["input"] +
            output_tokens / 1000 * pricing["output"])


def extract_tokens_from_response(response) -> tuple:
    """Extract input/output token counts from a Gemini response object."""
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return (
            getattr(usage, "prompt_token_count", 0),
            getattr(usage, "candidates_token_count", 0),
        )
    return (0, 0)


class CostTracker:
    """Tracks model usage costs per request."""

    def __init__(self):
        self._db = None
        self._collection = None
        self.enabled = settings.MODEL_COST_TRACKING_ENABLED

    def _ensure_db(self):
        """Lazy-init MongoDB collection for cost logs."""
        if self._collection is not None:
            return
        try:
            from services.auth_service import get_mongo_client
            self._db = get_mongo_client()
            if self._db is not None:
                self._collection = self._db.model_cost_logs
                # 90-day TTL index
                self._collection.create_index(
                    "timestamp_dt",
                    expireAfterSeconds=90 * 24 * 3600,
                    background=True,
                )
        except Exception as e:
            logger.info(f"MongoDB cost tracking unavailable: {e}")

    def log(
        self,
        session_id: str,
        model_name: str,
        tier: str,
        input_tokens: int,
        output_tokens: int,
        intent: str = "",
        phase: str = "",
    ):
        """Log a cost record."""
        cost = estimate_cost(model_name, input_tokens, output_tokens)
        record = RequestCostRecord(
            timestamp=datetime.utcnow().isoformat(),
            session_id=session_id,
            model_name=model_name,
            tier=tier,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=cost,
            intent=intent,
            phase=phase,
        )

        # Always log to structured logger
        logger.info(
            f"MODEL_COST | model={model_name} tier={tier} "
            f"in={input_tokens} out={output_tokens} "
            f"cost=${cost:.6f} intent={intent} phase={phase}"
        )

        # Optionally persist to MongoDB (non-blocking if in async context)
        if self.enabled:
            self._ensure_db()
            if self._collection is not None:
                try:
                    doc = asdict(record)
                    doc["timestamp_dt"] = datetime.utcnow()
                    try:
                        loop = asyncio.get_running_loop()
                        loop.run_in_executor(None, self._collection.insert_one, doc)
                    except RuntimeError:
                        # No running event loop — persist synchronously
                        self._collection.insert_one(doc)
                except Exception as e:
                    logger.warning(f"Failed to persist cost record: {e}")


_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
