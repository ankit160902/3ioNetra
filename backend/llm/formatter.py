"""
Response Formatter, Reformatter, and Query Refiner
Uses Google Gemini (google-genai SDK, new API)
"""

import logging
from typing import Optional

from google import genai
from config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Gemini Client Singleton
# ------------------------------------------------------------------

_gemini_client = None


def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Gemini client initialized")
    return _gemini_client


# ------------------------------------------------------------------
# Response Formatter (high‑intelligence restructuring)
# ------------------------------------------------------------------

class ResponseFormatter:
    def __init__(self):
        self.client = get_gemini_client()
        self.model = self.client.models.get("gemini-2.0-flash")
        self.available = True
        logger.info("ResponseFormatter ready")

    async def reformulate_response(
        self,
        original_response: str,
        user_query: str,
        context_verses: str
    ) -> str:
        prompt = f"""
You are a wise Bhagavad Gita teacher.

USER QUESTION:
{user_query}

AVAILABLE SCRIPTURE:
{context_verses}

ROUGH RESPONSE:
{original_response}

Rebuild the response using this structure:

1. Brief acknowledgment
2. Relevant Verse (optional)
3. One sentence explanation
4. Gentle question

Max Length: 75 words.

Rules:
- Plain text
- Short paragraphs
- No markdown
"""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            logger.exception("Gemini formatter failed")
            raise RuntimeError("LLM formatter unavailable")


# ------------------------------------------------------------------
# Response Reformatter (light rewrite only)
# ------------------------------------------------------------------

class ResponseReformatter:
    def __init__(self, api_key: str | None = None):
        self.available = False
        self.client = None

        if not api_key:
            logger.warning("ResponseReformatter disabled (no GEMINI_API_KEY)")
            return

        try:
            from google import genai

            self.client = genai.Client(api_key=api_key)
            self.available = True
            logger.info("✅ ResponseReformatter ready with Gemini")

        except Exception as e:
            self.available = False
            logger.error(f"❌ ResponseReformatter init failed: {e}")

    async def reformulate_response(
        self,
        original_response: str,
        user_query: str,
        context_verses: str,
    ) -> str:
        if not self.available:
            return original_response

        prompt = f"""
You are a compassionate Sanatan Dharma guide.

USER QUESTION:
{user_query}

SCRIPTURAL CONTEXT:
{context_verses}

RAW RESPONSE:
{original_response}

Rewrite the response to be:
- empathetic
- clear
- grounded in Sanatan wisdom
- calm and reassuring

Do not repeat verses verbatim unless necessary.
"""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text.strip()
        except Exception:
            return original_response


# ------------------------------------------------------------------
# Query Refiner (RAG search optimization)
# ------------------------------------------------------------------

class QueryRefiner:
    def __init__(self, api_key: str | None = None):
        self.available = False
        self.client = None
        self.model = None

        if not api_key:
            logger.warning("QueryRefiner disabled (no GEMINI_API_KEY)")
            return

        try:
            from google import genai

            self.client = genai.Client(api_key=api_key)
            self.model = self.client.models.get(
                model="gemini-2.0-flash"
            )
            self.available = True
            logger.info("✅ QueryRefiner ready with Gemini")

        except Exception as e:
            self.available = False
            logger.error(f"❌ QueryRefiner init failed: {e}")

    async def refine_query(self, query: str, language: str = "en") -> str:
        if not self.available or len(query.split()) < 3:
            return query

        prompt = f"""
Convert the following user input into a concise spiritual search query
for Sanatan Dharma / Bhagavad Gita context.

User input:
{query}

Return only 3–6 keyword phrase.
"""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            return response.text.strip()
        except Exception:
            return query


# ------------------------------------------------------------------
# Singletons
# ------------------------------------------------------------------

_formatter: Optional[ResponseFormatter] = None
_reformatter: Optional[ResponseReformatter] = None
_refiner: Optional[QueryRefiner] = None


def get_formatter() -> ResponseFormatter:
    global _formatter
    if _formatter is None:
        _formatter = ResponseFormatter()
    return _formatter


def get_reformatter(api_key: str | None = None) -> ResponseReformatter:
    global _reformatter
    if _reformatter is None:
        _reformatter = ResponseReformatter(api_key)
    return _reformatter


def get_refiner(api_key: str | None = None) -> QueryRefiner:
    global _refiner
    if _refiner is None:
        _refiner = QueryRefiner(api_key)
    return _refiner
