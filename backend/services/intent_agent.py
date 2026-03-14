import logging
import json
from typing import Dict, Any
from config import settings
from models.session import IntentType

logger = logging.getLogger(__name__)

class IntentAgent:
    """
    LLM-based Intent Agent for deep understanding of user messages.
    Categorizes intent, emotion, life domains, and extracts key entities.
    """

    INTENT_PROMPT = """
    You are an expert intent classifier for 3ioNetra, a spiritual companion bot.
    Analyze the user message below and return a JSON object.

    USER MESSAGE: "{message}"
    CONVERSATION CONTEXT: {context}

    Return ONLY a JSON object with these fields:

    1. "intent": Choose ONE from:
       [GREETING, SEEKING_GUIDANCE, EXPRESSING_EMOTION, ASKING_INFO, ASKING_PANCHANG, PRODUCT_SEARCH, CLOSURE, OTHER]
       - ASKING_INFO: factual "what is", "how does", "tell me about" questions
       - SEEKING_GUIDANCE: planning/advice requests like "give me a routine", "plan me a puja", "how should I"
       - PRODUCT_SEARCH: ONLY when user explicitly asks to buy/find/order something

    2. "emotion": The dominant emotion. Detect IMPLICIT emotions — look beyond surface words:
       "zero friends", "eat lunch alone", "nobody would notice" → loneliness
       "cant walk properly", "stuck at home" → grief, frustration
       "dont want to live", "nothing matters" → despair
       "cant stop drinking", "always relapse" → shame
       NEVER return "neutral" when the user describes a painful situation. Choose from: grief, anxiety, loneliness, frustration, anger, despair, hopelessness, shame, confusion, joy, gratitude, hope, curiosity, neutral.

    3. "life_domain": Primary area of concern. Choose from:
       [career, family, relationships, health, spiritual, finance]
       - career: job, boss, business, workplace, work-life balance
       - family: parents, children, siblings, elders
       - relationships: spouse, partner, dating, social isolation, loneliness
       - health: illness, fatigue, sleep, Ayurveda, diet, yoga, body
       - spiritual: deity, mantra, puja ritual, scripture, meditation, soul, karma (pure practice queries)
       - finance: money, investment, savings

    4. "entities": Dict of extracted nouns e.g. {{"deity": "Shiva", "ritual": "Abhishekam", "item": "mala"}}

    5. "urgency": One of [low, normal, high, crisis]

    6. "summary": One-sentence summary of the user's core need.

    7. "needs_direct_answer": boolean
       - True: user asked a specific HOW-TO, WHAT, or planning question (routine, steps, procedure)
       - False: user is venting, sharing feelings, or seeking emotional support

    8. "recommend_products": boolean — STRICT RULES:
       - True ONLY when:
         a) User explicitly mentions: buy, shop, items, essentials, what do I need, which mala, which oil
         b) User asks about a puja/ritual AND needs physical items to perform it
         c) User describes a workplace/home/body need where a product is the clear solution
       - False when:
         a) User is expressing pure grief, loss, or spiritual seeking without asking for help
         b) User asks for a yoga/pranayama routine (no product needed)
         c) User wants a diet plan (food, not a product)
         d) User asks philosophical/scriptural questions

    9. "product_search_keywords": List of 3-4 specific product keywords if recommend_products is True.
       Use context to resolve references (e.g., "essentials" + context "Satyanarayan Puja" → ["Satyanarayan", "puja samagri", "ghee"])
       Leave empty [] if recommend_products is False.

    Respond ONLY with the valid JSON object.
    """

    def __init__(self):
        from llm.service import get_llm_service
        self.llm = get_llm_service()
        self.available = self.llm.available

    async def analyze_intent(self, message: str, context_summary: str = "") -> Dict[str, Any]:
        """Analyze intent using LLM (fast model for low latency)."""
        # Fast-path: skip LLM for obvious greetings
        msg_lower = message.strip().lower()
        if msg_lower in ("hi", "hey", "hello", "namaste", "pranam", "hii", "hiii"):
            logger.info(f"Fast-path intent: GREETING for '{message[:30]}'")
            return {
                "intent": IntentType.GREETING, "emotion": "neutral", "life_domain": "unknown",
                "entities": {}, "urgency": "low", "summary": message,
                "needs_direct_answer": False, "recommend_products": False,
                "product_search_keywords": []
            }

        if not self.available:
            return self._fallback_analysis(message)

        prompt = self.INTENT_PROMPT.format(message=message, context=context_summary)

        try:
            import asyncio

            # Use fast model for classification (gemini-2.0-flash: ~1s vs 2.5-pro: ~7s)
            def _sync_call():
                return self.llm.client.models.generate_content(
                    model=settings.GEMINI_FAST_MODEL,
                    contents=prompt,
                    config={
                        "temperature": 0.1,
                        "response_mime_type": "application/json",
                        "automatic_function_calling": {"disable": True},
                    }
                )

            # Run in thread pool so it doesn't block the event loop
            response_text = await asyncio.to_thread(_sync_call)

            raw_text = response_text.text.strip()
            # Handle potential markdown code blocks in response
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "", 1).replace("```", "", 1).strip()

            data = json.loads(raw_text)
            data["intent"] = IntentType(data.get("intent", "OTHER"))
            logger.info(f"LLM Intent Analysis for '{message[:30]}...': {data.get('intent')} | Keywords: {data.get('product_search_keywords')}")
            return data

        except Exception as e:
            logger.error(f"Error in LLM intent analysis: {e}")
            return self._fallback_analysis(message)

    def _fallback_analysis(self, message: str) -> Dict[str, Any]:
        """Keyword-based fallback if LLM is unavailable"""
        message_lower = message.lower()
        
        intent = IntentType.OTHER
        if any(w in message_lower for w in ["hi", "hello", "hey", "namaste"]):
            intent = IntentType.GREETING
        elif "?" in message or any(w in message_lower for w in ["how", "what", "guide", "help"]):
            intent = IntentType.SEEKING_GUIDANCE
        elif any(w in message_lower for w in ["panchang", "tithi", "nakshatra"]):
            intent = IntentType.ASKING_PANCHANG
        elif any(w in message_lower for w in ["bye", "thanks", "thank you", "ok", "no", "nothing"]):
            intent = IntentType.CLOSURE

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
