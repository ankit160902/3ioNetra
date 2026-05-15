"""Port interfaces for Hexagonal Architecture.

Ports define the contracts between the CompanionEngine (core domain)
and external services (LLM, RAG, Session, etc.). Each port is a
typing.Protocol — existing service classes satisfy them structurally
without inheriting from anything.

Usage in CompanionEngine constructor:
    def __init__(self, llm: LLMPort, rag: RAGPort, ...):

Usage in tests:
    engine = CompanionEngine(llm=MockLLM(), rag=MockRAG(), ...)
"""

from ports.llm import LLMPort
from ports.rag import RAGPort
from ports.intent import IntentPort
from ports.memory import MemoryPort
from ports.product import ProductPort
from ports.safety import SafetyPort

__all__ = [
    "LLMPort",
    "RAGPort",
    "IntentPort",
    "MemoryPort",
    "ProductPort",
    "SafetyPort",
]
