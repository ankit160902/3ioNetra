import logging
import json
from typing import Dict, Any, Optional
from llm.service import get_llm_service
from config import settings

logger = logging.getLogger(__name__)

class IntentAgent:
    """
    LLM-based Intent Agent for deep understanding of user messages.
    Categorizes intent, emotion, life domains, and extracts key entities.
    """

    INTENT_PROMPT = """
    You are an expert intent classifier for a spiritual companion bot named 3ioNetra.
    Analyze the following user message and provide a structured JSON response.

    USER MESSAGE: "{message}"
    CONVERSATION CONTEXT: {context}

    Return a JSON object with the following fields:
    1. "intent": One of [GREETING, SEEKING_GUIDANCE, EXPRESSING_EMOTION, ASKING_INFO, ASKING_PANCHANG, PRODUCT_SEARCH, CLOSURE, OTHER]
    2. "emotion": The primary emotion detected (e.g., sadness, anxiety, joy, neutral, etc.)
    3. "life_domain": The relevant life area (e.g., career, family, health, relationships, spiritual, unknown)
    4. "entities": A dictionary of extracted entities like {{"name": "...", "deity": "...", "location": "...", "ritual": "Satyanarayan Puja", "item": "puja thali"}}. Extract specific nouns related to spiritual practices.
    5. "urgency": One of [low, normal, high, crisis]
    6. "summary": A very brief 1-sentence summary of what the user is actually asking or saying. Use the context to resolve pronouns like "it", "this", or "same".
    7. "needs_direct_answer": boolean - True if the user asked a specific factual or "how-to" question that requires a direct answer rather than just empathy.
    8. "recommend_products": boolean - True if the user explicitly asks for a product/service, where to buy something, or if a specific spiritual tool or service (like a mala, astrology consultation, specific puja, or incense) is a practical solution to their query.
    9. "product_search_keywords": List of strings - If recommend_products is true, identify 3-4 precise keywords for the product database. CRITICAL: Resolve references using context. If the user asks for "essentials for same" and the context is "Satyanarayan Puja", the keywords MUST include "Satyanarayan" and specific puja items.

    Respond ONLY with the JSON object.
    """

    def __init__(self):
        self.llm = get_llm_service()
        self.available = self.llm.available

    async def analyze_intent(self, message: str, context_summary: str = "") -> Dict[str, Any]:
        """Analyze intent using LLM"""
        if not self.available:
            return self._fallback_analysis(message)

        prompt = self.INTENT_PROMPT.format(message=message, context=context_summary)
        
        try:
            # We use a lower temperature for classification tasks
            response_text = self.llm.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config={
                    "temperature": 0.1,
                    "response_mime_type": "application/json"
                }
            )
            
            raw_text = response_text.text.strip()
            # Handle potential markdown code blocks in response
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "", 1).replace("```", "", 1).strip()
            
            data = json.loads(raw_text)
            logger.info(f"LLM Intent Analysis for '{message[:30]}...': {data.get('intent')} | Keywords: {data.get('product_search_keywords')}")
            return data
            
        except Exception as e:
            logger.error(f"Error in LLM intent analysis: {e}")
            return self._fallback_analysis(message)

    def _fallback_analysis(self, message: str) -> Dict[str, Any]:
        """Keyword-based fallback if LLM is unavailable"""
        message_lower = message.lower()
        
        intent = "OTHER"
        if any(w in message_lower for w in ["hi", "hello", "hey", "namaste"]):
            intent = "GREETING"
        elif "?" in message or any(w in message_lower for w in ["how", "what", "guide", "help"]):
            intent = "SEEKING_GUIDANCE"
        elif any(w in message_lower for w in ["panchang", "tithi", "nakshatra"]):
            intent = "ASKING_PANCHANG"
        elif any(w in message_lower for w in ["bye", "thanks", "thank you", "ok", "no", "nothing"]):
            intent = "CLOSURE"

        return {
            "intent": intent,
            "emotion": "neutral",
            "life_domain": "unknown",
            "entities": {},
            "urgency": "normal",
            "summary": message[:100],
            "needs_direct_answer": "?" in message or any(w in message_lower for w in ["how", "what", "where", "why"]),
            "recommend_products": any(w in message_lower for w in ["buy", "price", "shop", "product", "astro", "consult", "astrologer"]),
            "product_search_keywords": []
        }

_intent_agent = None

def get_intent_agent() -> IntentAgent:
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = IntentAgent()
    return _intent_agent
