import asyncio
import logging
import json
from typing import Dict, Any, Optional
from config import settings
from models.session import IntentType
from services.cache_service import _LRUCache

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
       [career, family, relationships, health, spiritual, finance, education]
       - career: job, boss, business, workplace, work-life balance
       - family: parents, children, siblings, elders
       - relationships: spouse, partner, dating, social isolation, loneliness
       - health: illness, fatigue, sleep, Ayurveda, diet, yoga, body
       - spiritual: deity, mantra, puja ritual, scripture, meditation, soul, karma (pure practice queries)
       - finance: money, investment, savings
       - education: studies, exams, school, college, learning, academic, board exams, grades, students

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

    10. "product_rejection": boolean — True ONLY when the user explicitly rejects or dismisses product suggestions.
        Examples: "stop suggesting products", "I don't want to buy anything", "no products please",
        "not interested in shopping", "don't recommend products"
        False for all other messages.

    11. "query_variants": List of EXACTLY 2 alternative search phrasings for the user's spiritual question.
        - You MUST generate 2 variants for ALL intents EXCEPT GREETING, CLOSURE, PRODUCT_SEARCH, and trivial/single-word messages.
        - For EXPRESSING_EMOTION: include comfort/healing oriented terms (e.g. "finding peace in grief", "overcoming anxiety through dharma").
        - For SEEKING_GUIDANCE / ASKING_INFO: include specific Sanskrit/English teaching terms.
        - Each variant should capture a different semantic angle of the user's concern.
        - Return empty list [] ONLY for GREETING, CLOSURE, PRODUCT_SEARCH, or trivial messages.

    Respond ONLY with the valid JSON object.
    """

    def __init__(self):
        from llm.service import get_llm_service
        self.llm = get_llm_service()
        self.available = self.llm.available
        self._cache = _LRUCache(max_size=100)  # 5-min default TTL

    # ── Fast-path constants ──
    _GREETING_SET = frozenset({
        "hi", "hey", "hello", "namaste", "pranam", "hii", "hiii",
    })
    _CLOSURE_SET = frozenset({
        "thank you", "thanks", "bye", "goodbye", "ok bye", "dhanyavaad", "shukriya",
        "alvida", "ok thanks", "thanks bye", "good bye", "ok thank you",
    })
    _PANCHANG_KEYWORDS = ("panchang", "tithi", "nakshatra", "muhurat")
    _INFO_PREFIXES = ("what is ", "what are ", "tell me about ", "who is ", "explain ")
    _EMOTION_MAP = {
        "sad": "grief", "unhappy": "grief", "crying": "grief",
        "anxious": "anxiety", "worried": "anxiety", "nervous": "anxiety",
        "stressed": "frustration", "frustrated": "frustration", "overwhelmed": "frustration",
        "lonely": "loneliness", "alone": "loneliness", "isolated": "loneliness",
        "angry": "anger", "furious": "anger", "irritated": "anger",
        "lost": "confusion", "confused": "confusion",
        "depressed": "hopelessness", "hopeless": "hopelessness",
        "scared": "anxiety", "afraid": "anxiety", "fearful": "anxiety",
    }
    _EMOTION_PATTERNS = (
        "i feel ", "i'm feeling ", "im feeling ", "i am feeling ",
        "feeling ", "i'm so ", "im so ", "i am so ",
        "i feel so ", "i'm ", "im ", "i am ",
    )

    def _fast_path(self, msg_lower: str) -> Optional[Dict[str, Any]]:
        """Return a fast-path result dict if the message matches a known pattern, else None."""
        _base = {
            "entities": {}, "urgency": "low", "summary": "",
            "needs_direct_answer": False, "recommend_products": False,
            "product_search_keywords": [], "product_rejection": False,
            "query_variants": [],
        }

        # (a) GREETING
        if msg_lower in self._GREETING_SET:
            return {**_base, "intent": IntentType.GREETING, "emotion": "neutral", "life_domain": "unknown"}

        # (b) CLOSURE
        if msg_lower in self._CLOSURE_SET:
            return {**_base, "intent": IntentType.CLOSURE, "emotion": "gratitude", "life_domain": "unknown"}

        # (c) ASKING_PANCHANG — substring check
        if any(kw in msg_lower for kw in self._PANCHANG_KEYWORDS):
            return {**_base, "intent": IntentType.ASKING_PANCHANG, "emotion": "neutral",
                    "life_domain": "spiritual", "needs_direct_answer": True}

        # (d) EXPRESSING_EMOTION — short messages with emotion keywords
        words = msg_lower.split()
        if len(words) <= 8:
            for pattern in self._EMOTION_PATTERNS:
                if msg_lower.startswith(pattern):
                    remainder = msg_lower[len(pattern):].strip().rstrip(".")
                    for keyword, emotion in self._EMOTION_MAP.items():
                        if keyword in remainder:
                            return {**_base, "intent": IntentType.EXPRESSING_EMOTION,
                                    "emotion": emotion, "life_domain": "unknown",
                                    "summary": msg_lower}
                    break  # matched a pattern prefix but no emotion keyword — fall through

        # (e) ASKING_INFO — starts with question prefix
        for prefix in self._INFO_PREFIXES:
            if msg_lower.startswith(prefix):
                return {**_base, "intent": IntentType.ASKING_INFO, "emotion": "curiosity",
                        "life_domain": "unknown", "needs_direct_answer": True,
                        "summary": msg_lower}

        return None  # no fast-path match

    async def analyze_intent(self, message: str, context_summary: str = "") -> Dict[str, Any]:
        """Analyze intent using LLM (fast model for low latency)."""
        msg_lower = message.strip().lower()

        # Fast-path: skip LLM for obvious intents (saves 800ms-2s)
        fast = self._fast_path(msg_lower)
        if fast is not None:
            logger.info(f"Fast-path intent: {fast['intent']} for '{message[:30]}'")
            return fast

        # LRU cache: return cached result for identical messages (saves 800ms-2s on repeats)
        cached = self._cache.get(msg_lower)
        if cached is not None:
            logger.info(f"Intent cache HIT for '{message[:30]}'")
            return cached

        if not self.available:
            return self._fallback_analysis(message)

        prompt = self.INTENT_PROMPT.format(message=message, context=context_summary)

        try:
            # Use fast model for classification (gemini-2.0-flash: ~1s vs 2.5-pro: ~7s)
            def _sync_call():
                return self.llm.client.models.generate_content(
                    model=settings.GEMINI_FAST_MODEL,
                    contents=prompt,
                    config={
                        "temperature": settings.INTENT_TEMPERATURE,
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
            # Cache successful LLM result for repeat messages
            self._cache.set(msg_lower, data, 300)
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

        product_rejection_phrases = [
            "stop suggesting products", "don't want products", "no products",
            "not interested in shopping", "don't recommend", "stop recommending",
            "no recommendations", "don't show products", "stop showing products",
        ]
        is_product_rejection = any(phrase in message_lower for phrase in product_rejection_phrases)

        return {
            "intent": intent,
            "emotion": "neutral",
            "life_domain": "unknown",
            "entities": {},
            "urgency": "normal",
            "summary": message[:100],
            "needs_direct_answer": "?" in message or any(w in message_lower for w in ["how", "what", "where", "why"]),
            "recommend_products": any(w in message_lower for w in ["buy", "price", "shop", "product", "recommend", "suggest"]),
            "product_search_keywords": [],
            "product_rejection": is_product_rejection,
            "query_variants": [],
        }

_intent_agent = None

def get_intent_agent() -> IntentAgent:
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = IntentAgent()
    return _intent_agent
