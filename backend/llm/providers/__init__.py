"""
Multi-model provider abstractions for evaluation and routing.

These providers are used by evaluation scripts (multi_model_evaluator, intent_evaluator)
and the model router. They do NOT replace the existing LLMService for production traffic.
"""

from llm.providers.base import (
    LLMResponse,
    IntentResponse,
    ResponseProvider,
    IntentProvider,
)

__all__ = [
    "LLMResponse",
    "IntentResponse",
    "ResponseProvider",
    "IntentProvider",
]
