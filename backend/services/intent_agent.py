import asyncio
import logging
import json
from typing import Dict, Any, Optional
from config import settings
from models.session import IntentType
from models.llm_schemas import IntentAnalysis, extract_json
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

    3. "life_domain": Describe the primary area of concern in 2-5 words. Be specific to
       the user's actual situation — do NOT force-fit into a generic category.
       Examples: "career growth frustration", "marriage conflict", "board exam preparation",
       "health anxiety chest pain", "Kedarnath pilgrimage planning", "financial debt stress",
       "daily spiritual practice", "grief after parent loss", "anger management",
       "travel and temple visit planning", "parenting a teenager", "addiction recovery"

    4. "entities": Dict of extracted nouns e.g. {{"deity": "Shiva", "ritual": "Abhishekam", "item": "mala"}}

    5. "urgency": One of [low, normal, high, crisis]
       - crisis: user expresses suicidal ideation, self-harm intent, or desire to end their life
         (even with typos/misspellings like "i dnt wnt 2 liv", "suicde", "kil myself")
       - high: deep existential despair WITHOUT explicit self-harm intent — "giving up on
         everything", "nothing makes sense", "what's the point of going on", "can't take it
         anymore". These need extra care but NOT helpline numbers.
       - normal: emotional but not in danger — stress, frustration, sadness, confusion
       - low: factual/informational queries, casual conversation

    6. "summary": One-sentence summary of the user's core need.

    7. "needs_direct_answer": boolean
       - True ONLY when the user asks a specific HOW-TO, factual WHAT-IS, or planning/procedure
         question with NO emotional weight.
         Examples: "What is karma yoga?", "How to perform Satyanarayan puja?",
         "Which mantra for Ganesh?", "Steps to do pranayama"
       - False when the user is venting, sharing feelings, expressing pain, or describing a
         difficult situation, even if the message contains question words.
         Examples: "I feel lost about my career", "What should I do, I'm so confused",
         "Why does this hurt so much?"
       - HARD RULE: If the message contains explicit emotion words (sad, angry, hurt, lost,
         scared, anxious, hopeless, lonely, depressed, worthless, broken, overwhelmed) OR
         the emotion you classified above is one of grief/anxiety/anger/fear/despair/loneliness/
         hopelessness/shame, return False.

    8. "recommend_products": boolean — DEFAULT IS FALSE. Products should feel like a rare,
       relevant surprise — NOT a default on every response. Being pushy with products
       destroys trust.
       - True ONLY when the user EXPLICITLY asks to buy/shop/find a physical item:
         a) "I want to buy a mala", "show me puja items", "what do I need for havan"
         b) "recommend me a murti", "where can I get incense", "suggest products"
       - ALWAYS False when:
         a) User is sharing emotions, venting, or seeking support
         b) User asks about mantras, verses, philosophy, scripture, karma, moksha
         c) User asks for advice (career, relationship, health, education)
         d) User asks about panchang, tithi, nakshatra
         e) User asks how to do a practice (meditation, yoga, pranayama, japa)
         f) User is greeting, thanking, or closing the conversation
         g) The companion just MENTIONED a practice like japa or puja — that does
            NOT mean the user wants to buy items for it. Wait for them to ask.
         h) User asks about travel, pilgrimage, itinerary planning
       - WHEN IN DOUBT: return False. It is always better to NOT show products
         than to show irrelevant ones. The user can always ask explicitly.

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

    12. "expected_length": How long the response should be. Choose ONE:
        - "brief": greetings, yes/no answers, acknowledgments, closures, "ok", "thanks"
        - "moderate": emotional sharing, simple questions, most conversation turns
        - "detailed": guidance requests, how-to questions, explanations, deeper topics
        - "full_text": user explicitly asks for complete text (full chalisa, full prayer, complete stotra, all steps of a ritual)

    13. "is_off_topic": boolean
        - True ONLY when the query is clearly outside spiritual/life-guidance scope.
          Examples: writing code, debugging software, sports scores, weather forecasts,
          stock prices, cooking recipes, movie reviews, generic web searches, news headlines.
        - False for anything related to life, emotions, relationships, family, career stress,
          health, dharma, spirituality, rituals, philosophy, personal growth, or anything
          a spiritual companion might reasonably engage with.
        - When in doubt, return False — let the conversation flow naturally.

    Respond ONLY with the valid JSON object.
    """

    def __init__(self):
        from llm.service import get_llm_service
        self.llm = get_llm_service()
        self.available = self.llm.available
        self._cache = _LRUCache(max_size=500)  # Expanded for better hit rate

    # ── Fast-path constants ──
    _GREETING_SET = frozenset({
        "hi", "hey", "hello", "namaste", "pranam", "hii", "hiii",
        "hi mitra", "hey mitra", "hello mitra", "namaste mitra", "pranam mitra",
        "namaskar", "namaskar mitra", "jai shree ram", "har har mahadev",
        "jai shri ram", "ram ram", "radhe radhe", "hare krishna",
        "good morning", "good evening", "good afternoon",
        "good morning mitra", "good evening mitra",
        "kaise ho", "kaise ho mitra", "kya haal hai",
    })
    _CLOSURE_SET = frozenset({
        "thank you", "thanks", "bye", "goodbye", "ok bye", "dhanyavaad", "shukriya",
        "alvida", "ok thanks", "thanks bye", "good bye", "ok thank you",
        "thank you mitra", "thanks mitra", "bye mitra", "goodbye mitra",
        "bye bye", "accha bye", "theek hai bye", "chalo bye",
        "thank you so much", "thanks a lot", "bahut dhanyavaad",
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
    # Words that indicate emotional weight — used to suppress fast-path INFO classification
    # and to gate the fallback's needs_direct_answer heuristic. Kept as a frozenset for O(1)
    # lookup; updated alongside _EMOTION_MAP whenever new emotion vocabulary is added.
    _EMOTIONAL_INDICATORS = frozenset({
        "feel", "feeling", "felt", "hurt", "hurts", "scared", "afraid", "anxious",
        "sad", "angry", "lost", "hopeless", "lonely", "depressed", "overwhelmed",
        "worthless", "broken", "crying", "miserable", "exhausted", "drained",
        "empty", "stuck", "trapped", "ashamed", "guilty", "grieving",
    })
    # Off-topic phrases — narrow keyword list to avoid false positives. The LLM-level
    # is_off_topic field provides the broader semantic check; this fast-path catches
    # the most obvious non-spiritual queries without an LLM round-trip.
    _OFF_TOPIC_PHRASES = frozenset({
        "python code", "javascript", "java code", "write code for", "debug my",
        "write a function", "regex for", "html tag", "css for",
        "stock price", "share price", "weather forecast", "temperature today",
        "movie review", "football match", "cricket score", "ipl match",
        "recipe for", "how to cook", "calorie count",
    })

    def _has_emotional_weight(self, msg_lower: str) -> bool:
        """Return True if the message contains explicit emotion vocabulary.

        Used by the fast-path to suppress INFO classification when the user
        is venting, and by the fallback to gate needs_direct_answer.
        """
        tokens = set(msg_lower.split())
        return bool(tokens & self._EMOTIONAL_INDICATORS)

    def _fast_path(self, msg_lower: str) -> Optional[Dict[str, Any]]:
        """Return a fast-path result dict if the message matches a known pattern, else None."""
        _base = {
            "entities": {}, "urgency": "low", "summary": "",
            "needs_direct_answer": False, "recommend_products": False,
            "product_search_keywords": [], "product_rejection": False,
            "query_variants": [], "expected_length": "moderate",
            "is_off_topic": False,
        }

        # (a) GREETING — exact match or short greeting pattern
        if msg_lower in self._GREETING_SET:
            return {**_base, "intent": IntentType.GREETING, "emotion": "neutral", "life_domain": "unknown", "expected_length": "brief"}
        first_word = msg_lower.split()[0] if msg_lower else ""
        if first_word in {"hi", "hey", "hello", "namaste", "namaskar", "pranam", "hii", "hiii"} and len(msg_lower.split()) <= 4:
            return {**_base, "intent": IntentType.GREETING, "emotion": "neutral", "life_domain": "unknown", "expected_length": "brief"}

        # (b) CLOSURE
        if msg_lower in self._CLOSURE_SET:
            return {**_base, "intent": IntentType.CLOSURE, "emotion": "gratitude", "life_domain": "unknown", "expected_length": "brief"}

        # (c) OFF_TOPIC — short-circuit before normal classification.
        # We skip this check if the message also has emotional weight (e.g.
        # "I'm so stressed I can't even cook a recipe"), letting the LLM
        # handle the disambiguation.
        if not self._has_emotional_weight(msg_lower):
            for phrase in self._OFF_TOPIC_PHRASES:
                if phrase in msg_lower:
                    return {**_base, "intent": IntentType.OTHER, "emotion": "neutral",
                            "life_domain": "unknown", "is_off_topic": True,
                            "expected_length": "brief"}

        # (d) ASKING_PANCHANG — substring check
        if any(kw in msg_lower for kw in self._PANCHANG_KEYWORDS):
            return {**_base, "intent": IntentType.ASKING_PANCHANG, "emotion": "neutral",
                    "life_domain": "spiritual", "needs_direct_answer": True, "expected_length": "detailed"}

        # (e) EXPRESSING_EMOTION — short messages with emotion keywords
        words = msg_lower.split()
        if len(words) <= 8:
            for pattern in self._EMOTION_PATTERNS:
                if msg_lower.startswith(pattern):
                    remainder = msg_lower[len(pattern):].strip().rstrip(".")
                    for keyword, emotion in self._EMOTION_MAP.items():
                        if keyword in remainder:
                            return {**_base, "intent": IntentType.EXPRESSING_EMOTION,
                                    "emotion": emotion, "life_domain": "unknown",
                                    "summary": msg_lower, "expected_length": "moderate"}
                    break

        # (f) ASKING_INFO — starts with question prefix.
        # Suppress fast-path classification when the message has emotional weight,
        # so the LLM can decide whether the user wants a factual answer or empathy.
        for prefix in self._INFO_PREFIXES:
            if msg_lower.startswith(prefix):
                if self._has_emotional_weight(msg_lower):
                    break  # fall through to LLM analysis
                return {**_base, "intent": IntentType.ASKING_INFO, "emotion": "curiosity",
                        "life_domain": "unknown", "needs_direct_answer": True,
                        "summary": msg_lower, "expected_length": "detailed"}

        return None

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
                        "max_output_tokens": 1024,
                        "automatic_function_calling": __import__("google.genai", fromlist=["types"]).types.AutomaticFunctionCallingConfig(disable=True),
                    }
                )

            # Run in thread pool — no timeout, let Gemini complete
            response_text = await asyncio.to_thread(_sync_call)

            raw_text = response_text.text.strip()
            parsed = extract_json(raw_text)
            if parsed is None:
                logger.warning(f"IntentAgent: JSON extraction failed for '{message[:30]}...'")
                return self._fallback_analysis(message)

            # Validate with Pydantic model (coerces enums, applies defaults)
            analysis = IntentAnalysis(**parsed)
            data = analysis.to_dict()
            data["intent"] = IntentType(data.get("intent", "OTHER"))
            logger.info(f"LLM Intent Analysis for '{message[:30]}...': {data.get('intent')} | Keywords: {data.get('product_search_keywords')}")
            self._cache.set(msg_lower, data, 1800)  # 30-min TTL
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

        # Suppress needs_direct_answer when the message has emotional weight, even if
        # it contains a question word. Without this, "What should I do? I'm so lost"
        # would short-circuit straight to guidance instead of being heard first.
        has_emotion = self._has_emotional_weight(message_lower)
        needs_direct = (not has_emotion) and (
            "?" in message or any(w in message_lower for w in ["how", "what", "where", "why"])
        )

        return {
            "intent": intent,
            "emotion": "neutral",
            "life_domain": "unknown",
            "entities": {},
            "urgency": "normal",
            "summary": message[:100],
            "needs_direct_answer": needs_direct,
            "recommend_products": any(w in message_lower for w in ["buy", "price", "shop", "product", "recommend", "suggest"]),
            "product_search_keywords": [],
            "product_rejection": is_product_rejection,
            "query_variants": [],
            "is_off_topic": False,
        }

_intent_agent = None

def get_intent_agent() -> IntentAgent:
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = IntentAgent()
    return _intent_agent
