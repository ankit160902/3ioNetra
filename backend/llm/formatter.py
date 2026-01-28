"""
Response Formatter Service - Ensures responses are well-formatted and readable
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import Google Generative AI SDK
try:
    from google import genai
    GEMINI_AVAILABLE = True
except Exception as e:
    genai = None
    GEMINI_AVAILABLE = False
    logger.error(f"Failed to import Google Generative AI SDK: {str(e)}")


class ResponseReformatter:
    """
    Reformatter that completely rebuilds responses with proper Gita wisdom and formatting
    This goes ABOVE the RAG knowledge base by using Gemini's intelligence
    """

    def __init__(self, api_key: str):
        """
        Initialize Response Reformatter

        Args:
            api_key: Gemini API key
        """
        self.api_key = api_key
        self.model = None
        self.available = False

        if not GEMINI_AVAILABLE:
            logger.error("Google Generative AI SDK not available")
            return

        if not api_key:
            logger.warning("API key not provided - reformatter will not be available")
            return

        try:
            genai.configure(api_key=self.api_key)
            # Use Gemini Flash for intelligent reformulation
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            self.available = True
            logger.info("Response Reformatter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize reformatter: {str(e)}")

    async def reformulate_response(self, original_response: str, user_query: str, context_verses: str) -> str:
        """
        Completely reformulate a response to be clear, structured, and understandable

        Args:
            original_response: The original response from LLM
            user_query: What the user asked
            context_verses: The Gita verses that were retrieved

        Returns:
            Reformulated response that's easy to understand
        """
        if not self.available or not self.model:
            logger.warning("Reformatter not available, returning original")
            return original_response

        try:
            reformulation_prompt = f"""You are a wise Bhagavad Gita teacher. Your job is to take a rough response and reformulate it into a clear, beautiful teaching.

USER'S QUESTION:
{user_query}

BHAGAVAD GITA VERSES AVAILABLE:
{context_verses}

ROUGH RESPONSE TO IMPROVE:
{original_response}

YOUR TASK:
Reformulate this into a clear, structured response that a normal person can understand. Follow this EXACT structure:

1. BRIEF ACKNOWLEDGMENT (1-2 sentences)
   - Acknowledge their feeling/question warmly

2. BHAGAVAD GITA VERSE (Must include if verses are available)
   - Quote the specific verse with chapter and verse number
   - Use the exact verse text provided in context
   - Format: "In Bhagavad Gita [Chapter].[Verse], Krishna teaches: '[verse text]'"

3. EXPLANATION (2-3 sentences)
   - Explain what this verse means in simple language
   - Connect it to their specific situation

4. PRACTICAL APPLICATION (2-3 sentences)
   - How they can apply this wisdom
   - Make it relevant to modern life

5. ENGAGING QUESTION (1 sentence)
   - Ask them something to reflect on

CRITICAL FORMATTING RULES:
- Add a BLANK LINE between EACH section (press Enter twice)
- Keep paragraphs SHORT (2-3 sentences max)
- NO markdown (*bold*, **italic**)
- Write in simple, conversational English
- Make it feel warm and personal, not robotic
- Use actual line breaks, not the text "\\n\\n"

OUTPUT ONLY THE REFORMULATED RESPONSE. Nothing else."""

            response = await self.model.generate_content_async(
                reformulation_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,  # Balanced for natural but consistent output
                    max_output_tokens=1024,
                )
            )

            reformulated = response.text.strip()

            logger.info(f"Successfully reformulated response ({len(original_response)} -> {len(reformulated)} chars)")

            return reformulated

        except Exception as e:
            logger.error(f"Error reformulating response: {str(e)}")
            return original_response  # Return original on error


class ResponseFormatter:
    """
    Formatter service to ensure responses are well-formatted with proper paragraph breaks
    """

    def __init__(self, api_key: str):
        """
        Initialize Response Formatter

        Args:
            api_key: Gemini API key
        """
        self.api_key = api_key
        self.model = None
        self.available = False

        if not GEMINI_AVAILABLE:
            logger.error("Google Generative AI SDK not available")
            return

        if not api_key:
            logger.warning("API key not provided - formatter will not be available")
            return

        try:
            genai.configure(api_key=self.api_key)
            # Use a fast, lightweight model for formatting
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            self.available = True
            logger.info("Response Formatter initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize formatter: {str(e)}")

    async def format_response(self, text: str) -> str:
        """
        Format a response to ensure proper paragraph breaks and readability

        Args:
            text: The raw response text to format

        Returns:
            Formatted response with proper paragraph breaks
        """
        if not self.available or not self.model:
            logger.warning("Formatter not available, returning original text")
            return text

        # If already well-formatted (has multiple blank lines), skip formatting
        if text.count('\n\n') >= 2:
            logger.info("Text already has good paragraph breaks, skipping format")
            return text

        try:
            formatting_prompt = f"""You are a text formatter. Your ONLY job is to add proper paragraph breaks to make text more readable.

RULES:
1. Break the text into SHORT paragraphs (2-3 sentences each)
2. Add ONE blank line between each paragraph
3. DO NOT change the wording, meaning, or content
4. DO NOT add or remove any information
5. DO NOT use markdown formatting like *word* or **word**
6. Keep all quotes and citations exactly as they are
7. Just add blank lines to improve readability

Here is the text to format:

{text}

Return ONLY the formatted text with proper paragraph breaks. Nothing else."""

            response = await self.model.generate_content_async(
                formatting_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Very low temperature for consistency
                    max_output_tokens=2048,
                )
            )

            formatted_text = response.text.strip()

            logger.info(f"Successfully formatted response ({len(text)} -> {len(formatted_text)} chars)")

            return formatted_text

        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            return text  # Return original text on error


class QueryRefiner:
    """
    Service to refine and clarify user queries before RAG retrieval
    """

    def __init__(self, api_key: str):
        """
        Initialize Query Refiner

        Args:
            api_key: Gemini API key
        """
        self.api_key = api_key
        self.model = None
        self.available = False

        if not GEMINI_AVAILABLE:
            logger.error("Google Generative AI SDK not available")
            return

        if not api_key:
            logger.warning("API key not provided - refiner will not be available")
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            self.available = True
            logger.info("Query Refiner initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize refiner: {str(e)}")

    async def refine_query(self, query: str, language: str = "en") -> str:
        """
        Refine a user query to be more suitable for Bhagavad Gita search

        Args:
            query: Original user query
            language: Language code (en or hi)

        Returns:
            Refined query optimized for scripture search
        """
        if not self.available or not self.model:
            logger.warning("Refiner not available, returning original query")
            return query

        # Skip refinement for very clear queries
        if len(query.split()) < 3:
            return query

        try:
            lang_note = ""
            if language == "hi":
                lang_note = "The user is asking in Hindi context, but keep the refined query in English for search."

            refining_prompt = f"""You are a Bhagavad Gita expert. Convert this user question into a clear search query that will help find relevant Bhagavad Gita verses.

RULES:
1. Extract the core spiritual/life topic (e.g., "duty", "detachment", "karma", "peace")
2. Keep it short and focused (3-7 words maximum)
3. Use keywords that would appear in Bhagavad Gita verses
4. Remove casual language and make it more spiritual/philosophical
5. If unclear, identify the life situation theme (work, relationships, purpose, etc.)

{lang_note}

User question: "{query}"

Return ONLY the refined search query. Nothing else. No explanations."""

            response = await self.model.generate_content_async(
                refining_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=50,
                )
            )

            refined_query = response.text.strip().strip('"').strip("'")

            logger.info(f"Refined query: '{query}' -> '{refined_query}'")

            return refined_query

        except Exception as e:
            logger.error(f"Error refining query: {str(e)}")
            return query  # Return original query on error


# Singleton instances
_formatter = None
_refiner = None
_reformatter = None


def get_formatter(api_key: Optional[str] = None) -> Optional[ResponseFormatter]:
    """Get or create formatter singleton"""
    global _formatter
    if api_key is None:
        return _formatter
    if _formatter is None:
        _formatter = ResponseFormatter(api_key)
    return _formatter


def get_refiner(api_key: Optional[str] = None) -> Optional[QueryRefiner]:
    """Get or create refiner singleton"""
    global _refiner
    if api_key is None:
        return _refiner
    if _refiner is None:
        _refiner = QueryRefiner(api_key)
    return _refiner


def get_reformatter(api_key: Optional[str] = None) -> Optional[ResponseReformatter]:
    """Get or create reformatter singleton"""
    global _reformatter
    if api_key is None:
        return _reformatter
    if _reformatter is None:
        _reformatter = ResponseReformatter(api_key)
    return _reformatter


def ensure_paragraph_breaks(text: str) -> str:
    """
    Ensure text has proper paragraph breaks for readability
    This is a lightweight fallback that doesn't use LLM

    Args:
        text: Text to process

    Returns:
        Text with proper paragraph breaks
    """
    # If already has good breaks, return as-is
    if text.count('\n\n') >= 3:
        return text

    import re

    # Fix common spacing issues first
    # Fix missing spaces before capital letters (like "upset.Krishna" -> "upset. Krishna")
    text = re.sub(r'([.!?])([A-Z])', r'\1 \2', text)

    # Fix run-on words before common phrases
    text = re.sub(r'([a-z])([A-Z][a-z]+\s+says:)', r'\1 \2', text)  # "upset.Krishna says:" -> "upset. Krishna says:"
    text = re.sub(r'([.!?])In\s+Bhagavad', r'\1 In Bhagavad', text)  # Fix "text.In Bhagavad"

    # Protect quotes and Gita references
    text = re.sub(r'(In Bhagavad Gita \d+\.\d+[^.!?]*[:.][^"]*"[^"]*")', r'\n\n__VERSE__\1__VERSE__\n\n', text)
    text = re.sub(r'(Krishna says:[^"]*"[^"]*")', r'\n\n__VERSE__\1__VERSE__\n\n', text)

    # Split into sentences
    sentences = re.split(r'([.!?])\s+', text)

    # Reconstruct with breaks every 2 sentences
    result = []
    current_para = []
    sent_count = 0

    for i in range(0, len(sentences) - 1, 2):
        sent = sentences[i]
        punct = sentences[i + 1] if i + 1 < len(sentences) else ''

        # Skip empty
        if not sent.strip() or sent.strip() in ['__VERSE__']:
            continue

        current_para.append(sent + punct)
        sent_count += 1

        # Break after 2 sentences
        if sent_count >= 2:
            para_text = ' '.join(current_para).strip()
            if para_text and para_text != '__VERSE__':
                result.append(para_text)
            current_para = []
            sent_count = 0

    # Add remaining
    if current_para:
        para_text = ' '.join(current_para).strip()
        if para_text and para_text != '__VERSE__':
            result.append(para_text)

    # Join with blank lines
    formatted = '\n\n'.join(filter(None, result))

    # Remove verse markers
    formatted = formatted.replace('__VERSE__', '').strip()

    # Clean up multiple consecutive blank lines
    while '\n\n\n' in formatted:
        formatted = formatted.replace('\n\n\n', '\n\n')

    return formatted
