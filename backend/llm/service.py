"""
LLM Service - Spiritual Companion with Context-Aware Responses
Provides empathetic, phase-aware interactions using Gemini AI
"""

import asyncio
import logging
import random
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from config import settings
from services.resilience import CircuitBreaker
from models.session import ConversationPhase


logger = logging.getLogger(__name__)


# --------------------------------------------------
# Enums & Data Models
# --------------------------------------------------


@dataclass
class UserContext:
    """User's conversation context and signals"""
    family_support: bool = False
    support_quality: bool = False
    relationship_crisis: bool = False
    work_stress: bool = False
    spiritual_seeking: bool = False
    is_greeting: bool = False
    
    def is_ready_for_guidance(self) -> bool:
        """Check if enough context gathered for guidance"""
        # Never go to guidance if it's just a greeting
        if self.is_greeting:
            return False
            
        # Transition if we've identified a life area OR spiritual seeking
        # OR if we've identified a relationship/work crisis
        return (self.spiritual_seeking or self.work_stress or 
                self.relationship_crisis or self.family_support)


# --------------------------------------------------
# Utilities
# --------------------------------------------------

def clean_response(text: str) -> str:
    """Remove trailing questions and clean formatting, especially from [VERSE] tags"""
    if not text:
        return ""
        
    # Simply return the text cleaned of whitespace initially
    text = text.strip()
    
    # Robustly clean content inside [VERSE] tags to prevent markdown artifacts
    def clean_verse_content(match):
        content = match.group(1).strip()
        # Remove common markdown hallucinations at start/end
        # - Double/Triple asterisks (bold/italic)
        # - Leading/trailing markdown quotes (>)
        # - Extra double/single quotes that the LLM might hallucinate
        # - List markers like - or *
        content = re.sub(r'^[\*\s_>"`„“\']+', '', content)
        content = re.sub(r'[\*\s_>"`„“\']+$', '', content)
        
        # Ensure we don't accidentally strip the closing quote of a citation if it's legitimate
        # but usually verses are provided "Text" - Source, so we can be careful.
        
        return f"[VERSE]\n{content}\n[/VERSE]"

    # Apply sanitization to all verse blocks
    text = re.sub(r'\[VERSE\]([\s\S]*?)\[/VERSE\]', clean_verse_content, text)

    # Robustly clean content inside [MANTRA] tags (same pattern as [VERSE])
    def clean_mantra_content(match):
        content = match.group(1).strip()
        content = re.sub(r'^[\*\s_>"`„"\']+', '', content)
        content = re.sub(r'[\*\s_>"`„"\']+$', '', content)
        return f"[MANTRA]\n{content}\n[/MANTRA]"

    text = re.sub(r'\[MANTRA\]([\s\S]*?)\[/MANTRA\]', clean_mantra_content, text)

    # Safety net: detect known mantras NOT already inside [MANTRA] or [VERSE] tags and wrap them
    KNOWN_MANTRA_PATTERNS = [
        # Long mantras (safe to auto-detect without quotes)
        r"Om\s+Tryambakam\s+Yajamahe[\s\S]*?Ma'?amritat",
        r'Om\s+Gam\s+Ganapataye\s+Namah[a]?',
        r'Om\s+Namah\s+Shivaya',
        r'Om\s+Shreem\s+Mahalakshmyai\s+Namah[a]?',
        r'Om\s+Aim\s+Saraswatyai\s+Namah[a]?',
        r'Om\s+Kleem\s+Krishnaya\s+Namah[a]?',
        r'Om\s+Namo\s+Bhagavate\s+Vasudevaya',
        r'Lokah\s+Samastah\s+Sukhino\s+Bhavantu',
        # Short mantras — require quotes around them to avoid false positives
        r"['\u2018\u201c]Om\s+Shanti(?:\s+Om\s+Shanti)*['\u2019\u201d]",
        r"['\u2018\u201c]So\s+Hum['\u2019\u201d]",
        r"['\u2018\u201c]Om\s+Tat\s+Sat['\u2019\u201d]",
    ]

    def _is_inside_tags(text, start, end):
        """Check if position start..end is already inside [MANTRA] or [VERSE] tags."""
        for tag in ['MANTRA', 'VERSE']:
            for m in re.finditer(r'\[' + tag + r'\][\s\S]*?\[/' + tag + r'\]', text):
                if m.start() <= start and end <= m.end():
                    return True
        return False

    for pattern in KNOWN_MANTRA_PATTERNS:
        # Re-scan after each wrap since indices shift
        while True:
            m = re.search(pattern, text, re.IGNORECASE)
            if not m:
                break
            if _is_inside_tags(text, m.start(), m.end()):
                break  # Already tagged, skip this pattern
            mantra_text = m.group(0)
            # Strip surrounding quotes if present
            mantra_text = mantra_text.strip("'\u2018\u2019\u201c\u201d")
            text = text[:m.start()] + f"[MANTRA]{mantra_text}[/MANTRA]" + text[m.end():]

    # --- Punctuation Artifact Cleanup Around Tags ---
    # The LLM treats [MANTRA]/[VERSE] as inline text, generating punctuation
    # like: "...mantra, [MANTRA]...[/MANTRA]. Try it..."
    # When rendered as cards, this punctuation becomes orphaned.

    # 1. Remove stray punctuation + orphaned quotes AFTER closing tags
    #    Handles: [/MANTRA]. , [/MANTRA]", , [/MANTRA]\n. , etc.
    text = re.sub(
        r'(\[/(?:VERSE|MANTRA)\])\s*["""\'\u2018\u2019\u201c\u201d]*[.,;:]+\s*',
        r'\1\n\n',
        text
    )

    # 2. Remove trailing comma/semicolon/colon and orphaned quotes BEFORE opening tags
    #    Handles: "mantra, [MANTRA]" → "mantra [MANTRA]"
    text = re.sub(
        r'[,;:]\s*["""\'\u2018\u2019\u201c\u201d]*\s*(\[(?:VERSE|MANTRA)\])',
        r' \1',
        text
    )

    # 3. Remove orphaned opening quotes immediately before opening tags
    #    Handles: "..text "[MANTRA]..." → "..text [MANTRA]..."
    text = re.sub(
        r'["""\'\u2018\u201c]\s*(\[(?:VERSE|MANTRA)\])',
        r' \1',
        text
    )

    # --- De-hyphenation: remove AI-typical em dashes and compound hyphens ---
    # AI models over-use em dashes (word — word) and compound hyphens (well-being).
    # Natural conversational text uses commas or spaces instead.

    # Step 1: Protect [VERSE] and [MANTRA] blocks from modification
    _dh_blocks = []
    def _dh_protect(m):
        _dh_blocks.append(m.group(0))
        return f'\x00DH{len(_dh_blocks) - 1}\x00'
    text = re.sub(r'\[(?:VERSE|MANTRA)\][\s\S]*?\[/(?:VERSE|MANTRA)\]', _dh_protect, text)

    # Step 2: Em/en dashes (— –) → context-aware replacement
    text = re.sub(r'([.!?])\s*[—–]\s+', r'\1 ', text)   # after sentence end → space
    text = re.sub(r'^[—–]\s*', '', text)                   # start of text → remove
    text = re.sub(r'\s*[—–]\s+', ', ', text)               # spaced dash → comma
    text = re.sub(r'(\w)[—–](\w)', r'\1, \2', text)        # unspaced dash → comma
    text = re.sub(r'\s*[—–]\s*', ' ', text)                # any remaining → space

    # Step 3: Compound hyphens between letters → space
    text = re.sub(r'(?<=[A-Za-z\u0900-\u097F])-(?=[A-Za-z\u0900-\u097F])', ' ', text)

    # Step 4: Artifact cleanup
    text = re.sub(r',\s*,', ',', text)                     # double commas
    text = re.sub(r'([.!?])\s*,', r'\1', text)             # comma after sentence end
    text = re.sub(r'^\s*,\s*', '', text)                    # leading comma
    text = re.sub(r'  +', ' ', text)                        # double spaces

    # Step 5: Restore protected tag content
    for i, block in enumerate(_dh_blocks):
        text = text.replace(f'\x00DH{i}\x00', block)

    return text


def is_closure_signal(text: str) -> bool:
    """Detect if user is wrapping up conversation"""
    closure_phrases = [
        "ok", "okay", "thanks", "thank you", 
        "got it", "fine", "alright", "i understand",
        "no", "nothing", "that's it", "that is all",
        "nothing else", "i'm done", "im done"
    ]
    text_lower = text.strip().lower()
    # Check for exact matches or common phrases
    if text_lower in ["no", "no thanks", "no thank you", "nothing", "that's all"]:
        return True
    return any(phrase in text_lower for phrase in closure_phrases)


# --------------------------------------------------
# Gemini Integration
# --------------------------------------------------

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False


# --------------------------------------------------
# Main LLM Service
# --------------------------------------------------

class LLMService:
    """
    Spiritual companion LLM service using Google Gemini.
    Provides context-aware, empathetic responses in different conversation phases.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.available = False
        self.client = None
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        from services.prompt_manager import get_prompt_manager
        self.prompt_manager = get_prompt_manager()

        
        # Load system instruction from external YAML
        self.system_instruction = self.prompt_manager.get_prompt(
            'spiritual_mitra',
            'system_instruction'
        )
        
        # Initialize Circuit Breaker for Gemini API
        self.circuit_breaker = CircuitBreaker(
            name="GeminiAPI",
            failure_threshold=settings.CIRCUIT_BREAKER_THRESHOLD,
            recovery_timeout=settings.CIRCUIT_BREAKER_TIMEOUT
        )

        if not GEMINI_AVAILABLE:
            logger.warning("Gemini SDK not available")
            return

        if not self.api_key:
            logger.warning("Gemini API key not provided")
            return

        try:
            from google import genai

            self.client = genai.Client(api_key=self.api_key)
            self.available = True
            logger.info("✅ LLM Service initialized with Gemini")

        except Exception:
            self.available = False
            logger.exception("❌ Failed to initialize Gemini")

    # --------------------------------------------------
    # OCR & Multimodal
    # --------------------------------------------------

    async def extract_text_from_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """
        Extract spiritual text/verses from an image using Gemini OCR.
        Optimized for Sanskrit, Hindi, and complex spiritual formatting.
        """
        if not self.available:
            return ""

        prompt = """
        You are a specialized OCR engine for spiritual texts in Sanātana Dharma.
        Extract all text from this image. 
        
        If you see any Shlokas (verses) in Sanskrit or Hindi:
        1. Extract the original text exactly as written.
        2. Identify the source if mentioned (e.g., Gita 2.47).
        3. Provide the English meaning if it's present in the image.
        
        Format the output as a clean text, focusing on the spiritual content.
        Do not describe the image, only extract the text.
        """

        try:
            from google.genai import types
            
            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            types.Part.from_text(text=prompt)
                        ]
                    )
                ]
            )
            
            return response.text if response.text else ""
            
        except Exception as e:
            logger.error(f"OCR Extraction failed: {e}")
            return ""

    async def analyze_video(self, video_path: str) -> str:
        """
        Analyze a video file using Gemini's multimodal capabilities.
        Extracts spiritual context, transcription, and key takeaways.
        """
        if not self.available:
            return ""

        logger.info(f"Analyzing video via Gemini: {video_path}")
        
        try:
            from google.genai import types
            # 1. Upload the file to Gemini Files API
            # Note: SDK v2 handles file uploads differently
            file_ref = self.client.files.upload(path=video_path)
            
            # Wait for file to be processed (standard for Files API)
            import time
            while file_ref.state == "PROCESSING":
                time.sleep(2)
                file_ref = self.client.files.get(name=file_ref.name)
            
            if file_ref.state == "FAILED":
                logger.error(f"Video processing failed in Gemini Files API: {file_ref.name}")
                return ""

            prompt = """
            You are a specialized spiritual companion (Mitra). Your task is to analyze this spiritual video with extreme precision.
            
            Return the analysis in a strictly structured JSON format with the following schema:
            {
              "overall_summary": "A high-level summary of the entire video",
              "practical_takeaways": ["Takeaway 1", "Takeaway 2"],
              "segments": [
                {
                  "start_time": "MM:SS",
                  "end_time": "MM:SS",
                  "transcription": "Precise transcription of spoken words in this segment",
                  "visual_description": "Detailed description of rituals, gestures, or surroundings shown",
                  "spiritual_context": "Explanation of the spiritual significance of this specific part",
                  "shlokas": [
                    {"original": "Sanskrit/Hindi text", "meaning": "English translation"}
                  ]
                }
              ]
            }

            Rules:
            1. Ensure timestamps are accurate.
            2. Extract EVERY Shloka or Mantra mentioned or shown.
            3. Detailed visual descriptions are crucial for RAG context (e.g., 'Offering Bilva leaves to a Shivling while chanting').
            4. Keep transcriptions original (Hindi/Sanskrit where applicable) but provide English context if it helps clarity.
            """

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    file_ref,
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            # Optionally delete file from Files API after processing
            try:
                self.client.files.delete(name=file_ref.name)
            except Exception as delete_err:
                logger.warning(f"Could not delete video from Files API: {delete_err}")

            return response.text if response.text else "{}"
            
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            return ""

    # --------------------------------------------------
    # Context Analysis
    # --------------------------------------------------

    def _extract_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> UserContext:
        """Extract user context from query and conversation history"""
        context = UserContext()
        
        # Analyze current query
        query_lower = query.lower().strip()
        
        # Greeting detection
        greetings = ["hi", "hey", "hello", "namaste", "pranam", "shubh prabhat", "shubh sandhya", "good morning", "good evening"]
        context.is_greeting = any(query_lower == g or query_lower.startswith(g + " ") for g in greetings)
        
        # Relationship signals
        if any(word in query_lower for word in ["wife", "husband", "divorce", "marriage", "partner"]):
            context.relationship_crisis = True
        
        # Family signals
        if any(word in query_lower for word in ["family", "mother", "father", "parents", "children"]):
            context.family_support = True
        
        # Support quality signals
        if any(word in query_lower for word in ["listen", "support", "understand", "care", "help"]):
            context.support_quality = True
        
        # Work stress signals
        if any(word in query_lower for word in ["work", "job", "boss", "career", "office", "deadline"]):
            context.work_stress = True
        
        # Spiritual seeking / Struggle / Happiness signals
        if any(word in query_lower for word in ["peace", "purpose", "meaning", "dharma", "karma", "meditation", "sad", "sadness", "struggle", "lost", "confused", "happy", "happiness", "joy"]):
            context.spiritual_seeking = True

        # Panchang signals
        if any(word in query_lower for word in ["panchang", "tithi", "nakshatra", "astrology", "calendar", "today's day", "festivals", "shubh muhurat"]):
            context.spiritual_seeking = True # Treat as spiritual seeking for phase transition
        
        # Analyze conversation history
        if conversation_history:
            for msg in conversation_history:
                if msg.get("role") != "user":
                    continue
                
                content = msg.get("content", "").lower()
                
                if "family" in content:
                    context.family_support = True
                if any(word in content for word in ["listen", "support", "understand"]):
                    context.support_quality = True
                if any(word in content for word in ["divorce", "separation", "breakup"]):
                    context.relationship_crisis = True
        
        return context

    # --------------------------------------------------
    # Phase Detection
    # --------------------------------------------------

    def _detect_phase(self, query: str, context: UserContext, history_len: int = 0) -> ConversationPhase:
        """Determine which conversation phase we're in"""
        # Closure signals take priority
        if is_closure_signal(query):
            return ConversationPhase.CLOSURE
        
        # Simple greetings always stay in LISTENING (or CLARIFICATION) phase
        if context.is_greeting and history_len < 2:
            return ConversationPhase.LISTENING
            
        # Ready for guidance after 4 turns OR if we have solid context AND at least 2 turns of back-and-forth
        if (history_len >= 4) or (context.is_ready_for_guidance() and history_len >= 2):
            return ConversationPhase.GUIDANCE
        
        # Default to listening/clarification
        return ConversationPhase.LISTENING

    # --------------------------------------------------
    # Generation Config
    # --------------------------------------------------

    def _build_gen_config(self, config_override: Optional[Dict] = None) -> Dict:
        """Build the Gemini generation config dict."""
        gen_config = config_override.copy() if config_override else {
            "temperature": settings.RESPONSE_TEMPERATURE,
            "thinking_config": {"thinking_budget": 256},
            "max_output_tokens": settings.RESPONSE_MAX_TOKENS,
            "automatic_function_calling": {"disable": True},
            "safety_settings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ],
        }
        gen_config["system_instruction"] = self.system_instruction
        return gen_config

    # --------------------------------------------------
    # Prompt Building
    # --------------------------------------------------

    def _build_prompt(
        self,
        query: str,
        conversation_history: Optional[List[Dict]],
        phase: ConversationPhase,
        context: UserContext,
        context_docs: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        memory_context: Optional[Any] = None,
    ) -> str:
        """Build context-aware prompt for Gemini with user profile personalization"""
        
        # Format user profile if available
        profile_text = ""
        if user_profile:
            logger.info(f"Building prompt with user_profile: {user_profile}")
            has_data = False
            profile_parts = []
            
            if user_profile.get('name'):
                profile_parts.append(f"   • Their name is: {user_profile.get('name')}")
                has_data = True
            if user_profile.get('age_group'):
                profile_parts.append(f"   • Age group: {user_profile.get('age_group')}")
                has_data = True
            if user_profile.get('dob'):
                profile_parts.append(f"   • Date of birth: {user_profile.get('dob')}")
                has_data = True
            if user_profile.get('profession'):
                profile_parts.append(f"   • Profession: {user_profile.get('profession')}")
                has_data = True
            if user_profile.get('gender'):
                profile_parts.append(f"   • Gender: {user_profile.get('gender')}")
                has_data = True
            if user_profile.get('phone'):
                profile_parts.append(f"   • Phone: {user_profile.get('phone')}")
                has_data = True
            
            # Add context for conversation
            if user_profile.get('primary_concern'):
                profile_parts.append(f"   • What they've shared: {user_profile.get('primary_concern')}")
                has_data = True
            if user_profile.get('emotional_state'):
                profile_parts.append(f"   • Current emotion: {user_profile.get('emotional_state')}")
                has_data = True
            if user_profile.get('life_area'):
                profile_parts.append(f"   • Life area: {user_profile.get('life_area')}")
                has_data = True
            if user_profile.get('preferred_deity'):
                profile_parts.append(f"   • Preferred deity: {user_profile.get('preferred_deity')}")
                has_data = True
            if user_profile.get('location'):
                profile_parts.append(f"   • Location: {user_profile.get('location')}")
                has_data = True
            if user_profile.get('spiritual_interests'):
                profile_parts.append(f"   • Spiritual interests: {', '.join(user_profile.get('spiritual_interests', []))}")
                has_data = True
            
            # 🔥 Extended Spiritual Profile
            if user_profile.get('rashi'):
                profile_parts.append(f"   • Rashi (Zodiac): {user_profile.get('rashi')}")
                has_data = True
            if user_profile.get('gotra'):
                profile_parts.append(f"   • Gotra: {user_profile.get('gotra')}")
                has_data = True
            if user_profile.get('nakshatra'):
                profile_parts.append(f"   • Nakshatra: {user_profile.get('nakshatra')}")
                has_data = True
            if user_profile.get('temple_visits'):
                profile_parts.append(f"   • Past Pilgrimages: {', '.join(user_profile.get('temple_visits', []))}")
                has_data = True
            
            # 🗓️ Current Panchang Context
            if user_profile.get('current_panchang'):
                p = user_profile['current_panchang']
                panchang_lines = ["   • CURRENT PANCHANG (Today):"]

                # Tithi with significance
                tithi_line = f"     Tithi: {p.get('tithi', '')}"
                if p.get('tithi_significance'):
                    tithi_line += f" — {p['tithi_significance']}"
                if p.get('tithi_vrat'):
                    tithi_line += f" ({p['tithi_vrat']})"
                panchang_lines.append(tithi_line)

                # Nakshatra with quality
                nak_line = f"     Nakshatra: {p.get('nakshatra', '')}"
                if p.get('nakshatra_quality'):
                    nak_line += f" — {p['nakshatra_quality']}"
                if p.get('nakshatra_good_for'):
                    nak_line += f". Good for: {p['nakshatra_good_for']}"
                panchang_lines.append(nak_line)

                # Yoga
                if p.get('yoga') and p.get('yoga_quality'):
                    panchang_lines.append(f"     Yoga: {p['yoga']} — {p['yoga_quality']}")

                # Paksha + Masa
                if p.get('paksha') and p.get('masa'):
                    panchang_lines.append(f"     {p['paksha']} Paksha, {p['masa']} month — {p.get('masa_significance', '')}")

                # Festival with spiritual context (conditional)
                if p.get('festival'):
                    panchang_lines.append(f"     FESTIVAL TODAY: {p['festival']}")
                    if p.get('festival_significance'):
                        panchang_lines.append(f"       Significance: {p['festival_significance']}")
                    if p.get('festival_mantra'):
                        panchang_lines.append(f"       Mantra: {p['festival_mantra']}")
                    if p.get('festival_rituals'):
                        panchang_lines.append(f"       Rituals: {p['festival_rituals']}")

                # Special day info
                if p.get('special_day'):
                    panchang_lines.append(f"     Note: {p['special_day']}")

                # Upcoming festivals (next 1-3 days)
                if p.get('upcoming_festivals'):
                    for uf in p['upcoming_festivals']:
                        days = uf['days_away']
                        when = "Tomorrow" if days == 1 else f"In {days} days"
                        line = f"     UPCOMING: {when} — {uf['festival']}"
                        if uf.get('mantra'):
                            line += f" (Mantra: {uf['mantra']})"
                        panchang_lines.append(line)

                profile_parts.append("\n".join(panchang_lines))
                has_data = True
            
            # 🧠 Semantic Long-Term Memories
            if user_profile.get('past_memories'):
                profile_parts.append("\n   RELEVANT PAST CONTEXT (from your history):")
                for i, mem in enumerate(user_profile.get('past_memories'), 1):
                    profile_parts.append(f"   {i}. \"{mem}\"")
                has_data = True

            # Previous suggestions context (so LLM can deepen on acceptance)
            if user_profile.get('last_suggestions'):
                suggestions = user_profile['last_suggestions']
                profile_parts.append("\n   YOUR RECENT SUGGESTIONS TO THIS USER:")
                for s in suggestions[-2:]:
                    profile_parts.append(f"   • Turn {s['turn']}: You suggested {s['practice']}")
                has_data = True
            
            if has_data:
                profile_text = "\n" + "="*70 + "\n"
                profile_text += "WHO YOU ARE SPEAKING TO:\n"
                profile_text += "="*70 + "\n"
                profile_text += "\n".join(profile_parts)
                profile_text += "\n" + "="*70 + "\n"
                profile_text += "\n"
                logger.info(f"Generated profile section with {len(profile_parts)} fields")
            else:
                logger.warning("user_profile provided but no data fields found!")
        
        # Detect returning user — prefer the explicit flag from user_profile,
        # then fall back to checking for session separator strings in history
        is_returning_user = bool(user_profile.get("is_returning_user", False)) if user_profile else False
        if not is_returning_user and conversation_history and len(conversation_history) > 3:
            is_returning_user = any(
                "New Session" in msg.get("content", "")
                for msg in conversation_history
                if msg.get("role") == "system"
            )
        
        # Format conversation history (last 8 messages = 4 turns of context)
        history_text = ""
        if conversation_history:
            # Exclude the very last message if it's the current query to avoid duplication
            recent_history = conversation_history[-8:]
            if recent_history and recent_history[-1]["role"] == "user" and recent_history[-1]["content"] == query:
                recent_history = recent_history[:-1]
                
            for msg in recent_history:
                role = "User" if msg["role"] == "user" else "You"
                content = msg.get("content", "")
                
                # Mark session separators clearly
                if msg.get("role") == "system" and "New Session" in content:
                    history_text += f"\n{'='*60}\n{content}\n{'='*60}\n"
                    is_returning_user = True
                else:
                    history_text += f"{role}: {content}\n"
        
        # Context summary
        fact_text = ""
        if memory_context:
            context_summary = memory_context.get_memory_summary()
            story = memory_context.story
            
            # Extract specific facts from story
            facts = []
            if story.rashi:
                facts.append(f"• Rashi: {story.rashi}")
            if story.gotra:
                facts.append(f"• Gotra: {story.gotra}")
            if story.nakshatra:
                facts.append(f"• Nakshatra: {story.nakshatra}")
            if story.temple_visits:
                facts.append(f"• Temple Visits: {', '.join(story.temple_visits)}")
            if story.purchase_history:
                facts.append(f"• Purchase History: {', '.join(story.purchase_history)}")
            if story.detected_topics:
                recent_topics = list(dict.fromkeys(story.detected_topics[-5:]))
                facts.append(f"• Topic journey: {' → '.join(recent_topics)}")

            # Also extract specific user quotes as "Facts"
            if hasattr(memory_context, 'user_quotes'):
                for quote in memory_context.user_quotes[-10:]:
                    facts.append(f"• User shared: \"{quote['quote']}\"")
            
            fact_text = "\n".join(facts) if facts else "• No specific facts extracted yet"
        else:
            context_summary = self._format_context(context)
            fact_text = "• No memory context available"
        
        # Phase-specific instructions
        phase_instructions = self._get_phase_instructions(phase)
        
        # Format scripture context from RAG if available
        scripture_context = ""
        # Allow verses in both phases so the bot can choose the right moment
        if context_docs and len(context_docs) > 0:
            scripture_context = "\n═══════════════════════════════════════════════════════════\n"
            scripture_context += "RESOURCES AVAILABLE (Use ONLY if they naturally fit the conversation):\n"
            scripture_context += "═══════════════════════════════════════════════════════════\n\n"
            
            # Fix 5: Compute relative baseline for quality labels
            from rag.scoring_utils import get_doc_score
            surviving_scores = [
                get_doc_score(d)
                for d in context_docs if not d.get('is_context_verse')
            ]
            max_surviving = max(surviving_scores) if surviving_scores else 1.0

            for i, doc in enumerate(context_docs, 1):
                # Context verses from parent-child expansion: compact inline format
                if doc.get("is_context_verse"):
                    scripture_context += f"  (Adjacent context: {doc.get('reference', '')})\n"
                    scripture_context += f"  Text: \"{(doc.get('text') or '')[:200]}\"\n"
                    ctx_meaning = doc.get('meaning') or doc.get('translation', '')
                    if ctx_meaning:
                        scripture_context += f"  Meaning: {ctx_meaning[:200]}\n"
                    scripture_context += "\n"
                    continue

                scripture = doc.get('scripture', 'Scripture')
                reference = doc.get('reference', '')
                doc_type = (doc.get('type') or 'scripture').lower()

                # Fix 5: Relative quality labels — docs that survived ContextValidator are the best available
                quality_score = get_doc_score(doc)
                relative_score = quality_score / max_surviving if max_surviving > 0 else 0
                quality_label = (
                    "BEST MATCH" if relative_score >= 0.85 else
                    "GOOD MATCH" if relative_score >= 0.60 else
                    "SUPPORTING"
                )

                # Robustly find the original verse text and its meaning
                # Skip placeholder text like "intermediate" or very short technical strings
                verse_raw = doc.get('verse')
                if verse_raw and verse_raw.lower() in ['intermediate', 'beginner', 'advanced', 'none', 'null']:
                    verse_raw = None

                # Priority: hindi (for original) -> verse -> text
                original_text = doc.get('hindi') or verse_raw or doc.get('text', '')

                # Identify meaning/translation
                meaning = doc.get('meaning') or doc.get('translation')
                if not meaning and doc.get('verse') and doc.get('text') and doc.get('text') != original_text:
                    meaning = doc.get('text')

                # Final check: if original is still placeholder-ish, try to clean it
                if len(original_text) < 5 and doc.get('text'):
                    original_text = doc.get('text')

                # Type-aware label for LLM guidance
                type_hints = {
                    "temple": "🏛️ TEMPLE REFERENCE — Use ONLY if user asked about pilgrimage, a specific temple, or nearby places to visit.",
                    "procedural": "📋 PROCEDURAL GUIDE — Use when user needs step-by-step ritual or practice instructions.",
                    "scripture": "📖 SCRIPTURE VERSE — Use when the verse directly addresses the user's emotion or question.",
                }
                type_label = type_hints.get(doc_type, "📖 SCRIPTURE — Use contextually.")

                scripture_context += f"RESOURCE {i} [{quality_label}]:\n"
                scripture_context += f"Type: {doc_type.upper()} | {type_label}\n"
                scripture_context += f"Source: {scripture}"
                if reference:
                    scripture_context += f" — {reference}"
                scripture_context += f"\n\nORIGINAL TEXT (Sanskrit/Hindi/Procedural): \"{original_text}\"\n"

                if meaning:
                    scripture_context += f"MEANING/TRANSLATION (English): {meaning}\n"

                scripture_context += "\n" + "-" * 60 + "\n\n"

            # Fix 5: Relative "low confidence" warning instead of absolute threshold
            if max_surviving < 0.25:
                scripture_context += (
                    "\nNOTE: These are the best available resources for this specific query. "
                    "Use them if they resonate with the user's situation, "
                    "but feel free to draw on general spiritual knowledge too.\n\n"
                )

            # Load RAG usage instructions from YAML (centralised prompt management)
            rag_instructions = self.prompt_manager.get_prompt(
                'spiritual_mitra',
                'rag_synthesis.instruction',
                default=""
            ) if self.prompt_manager else ""
            if rag_instructions:
                scripture_context += rag_instructions
            else:
                # Fallback if YAML not available
                scripture_context += """\
HOW TO USE THESE RESOURCES:
- Only use a resource if it GENUINELY helps the user's specific situation.
- Prioritize BEST MATCH resources. SUPPORTING resources may provide additional context.
- SCRIPTURE: Cite it (e.g., Bhagavad Gita 2.47), explain it simply, connect to their life.
- TEMPLE: Suggest a visit only if the user is seeking pilgrimage, spiritual courage, or blessings.
- PROCEDURAL: Share the steps when user explicitly asked HOW to do a ritual or practice.
- Quality matters more than quantity.
"""
        else:
            scripture_context = (
                "\n═══════════════════════════════════════════════════════════\n"
                "SCRIPTURE CONTEXT: NONE AVAILABLE\n"
                "═══════════════════════════════════════════════════════════\n"
                "No relevant scripture matches were found for this query. "
                "Respond with general spiritual wisdom. "
                "Do NOT cite any specific verse, chapter, or shloka number. "
                "Use phrases like 'the Gita teaches us...' or 'as our scriptures remind us...' "
                "instead of specific references like 'Bhagavad Gita 2.47'.\n"
            )


        # Build final prompt
        returning_user_section = self._build_returning_user_section(is_returning_user, memory_context)

        prompt = f"""
{profile_text}

═══════════════════════════════════════════════════════════
EXTRACTED FACTS & PLANS:
═══════════════════════════════════════════════════════════
{fact_text}

═══════════════════════════════════════════════════════════
WHAT YOU KNOW SO FAR (EMOTIONAL CONTEXT):
═══════════════════════════════════════════════════════════
{context_summary}

{returning_user_section}

═══════════════════════════════════════════════════════════
CONVERSATION FLOW:
═══════════════════════════════════════════════════════════
{history_text}

User's CURRENT message:
{query}

═══════════════════════════════════════════════════════════
YOUR INSTRUCTIONS FOR THIS PHASE ({phase.value}):
═══════════════════════════════════════════════════════════
{phase_instructions}

{scripture_context}

BEFORE YOU RESPOND — CHECK THESE (violations = failure):
1. SCAN your first 5 words. If they contain "I hear you", "I understand", or "It sounds like" — DELETE and rewrite. Start with something specific: "That is a lot to carry", "Twelve years is a lifetime of love", "Of course you are angry."
2. SCAN for echoed dismissive words. If the user complained about "adjust", "get over it", "move on", or "just a [thing]" — make sure NONE of those words or substrings appear in your response. Rephrase completely.
3. NO numbered lists (1. 2. 3.), NO bullet points (- or *), NO bold (**text**), NO headers (#). Even for ritual how-to — use flowing prose.
4. Don't end with "How does that sound?", "Would you like to hear more?", or "Does this resonate?" — just end.
5. One verse maximum, only if it truly fits.
6. You are a companion, not a therapist running an assessment.
7. When discussing a specific deity, always use their NAME at least once (Shiva, Krishna, Hanuman, Durga) — never just "He" or "His".
8. RETURNING USER CHECK: If the RETURNING USER section exists above, re-read it now. Your response MUST include one specific detail from their journey.
9. REPETITION CHECK: Read your last 2 responses in the conversation. If you already gave a mantra/practice/Gita reference and the user is STILL processing the same emotion — do NOT give another mantra/practice/Gita reference. Ask a deeper question instead. Break the pattern.
10. LISTENING PHASE CHECK: If the phase is LISTENING and the user is sharing pain — your response should end with a QUESTION, not a practice. "What part of this weighs heaviest?" is better than "Chant Om Shanti 11 times tonight."
11. "TONIGHT" CHECK: Does your response contain "Tonight" as a practice timing? If your previous response ALSO said "Tonight" — REWRITE with a different timing: "tomorrow morning", "this week", "right now", "before your chai".
12. DHARMA BOUNDARY CHECK: Is the user asking about another religion, coding, politics, or non-spiritual topics? Do NOT answer the question. Do NOT bridge it into spirituality. Just warmly redirect: "That is outside my world — I am here for your spiritual journey."

Your response:
"""
        
        return prompt.strip()

    def _extract_key_topics(self, summary: str) -> list:
        """Extract key topic words from a session summary for mandatory reference."""
        # Common stop words to exclude
        stop_words = {
            "the", "a", "an", "is", "was", "are", "were", "been", "be", "have", "has",
            "had", "do", "does", "did", "will", "would", "could", "should", "may", "might",
            "shall", "can", "need", "must", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again", "further", "then",
            "once", "here", "there", "when", "where", "why", "how", "all", "each", "every",
            "both", "few", "more", "most", "other", "some", "such", "no", "nor", "not",
            "only", "own", "same", "so", "than", "too", "very", "just", "about", "up",
            "and", "but", "or", "if", "while", "because", "until", "that", "which", "who",
            "whom", "this", "these", "those", "am", "it", "its", "i", "me", "my", "we",
            "our", "you", "your", "he", "him", "his", "she", "her", "they", "them", "their",
            "what", "also", "like", "much", "many", "still", "even", "back", "get", "got",
            "make", "made", "take", "took", "come", "came", "go", "went", "see", "saw",
            "know", "knew", "think", "thought", "feel", "felt", "say", "said", "tell",
            "told", "give", "gave", "find", "found", "want", "let", "seem", "try", "keep",
            "put", "thing", "things", "something", "user", "mentioned", "discussed",
            "talked", "session", "conversation", "expressed", "shared", "feeling",
        }
        words = re.findall(r'[a-zA-Z]{3,}', summary.lower())
        topics = []
        seen = set()
        for w in words:
            if w not in stop_words and w not in seen:
                seen.add(w)
                topics.append(w)
        return topics[:8]  # Top 8 unique topic words

    def _build_returning_user_section(self, is_returning_user: bool, memory_context) -> str:
        """Build the returning-user prompt section with journey context."""
        if not is_returning_user:
            return ""

        prev_summary = ""
        if memory_context and getattr(memory_context, 'previous_session_summary', ''):
            prev_summary = memory_context.previous_session_summary
        elif memory_context:
            prev_summary = memory_context.get_memory_summary()

        if not prev_summary:
            prev_summary = "This user has had previous conversations with you. They are returning for continued support."

        sensitive_markers = ["divorce", "separation", "abuse", "suicide", "death",
                             "passed away", "miscarriage", "assault", "violence"]
        is_sensitive = any(m in prev_summary.lower() for m in sensitive_markers)

        key_topics = self._extract_key_topics(prev_summary)
        topic_list = ", ".join(key_topics) if key_topics else "their past experience"

        section = f"""{'═'*70}
🔄 RETURNING USER — MANDATORY CONTEXT REFERENCE
{'═'*70}
THEIR JOURNEY SO FAR: {prev_summary}

KEY TOPICS FROM THEIR JOURNEY: {topic_list}

⚠️ CRITICAL RULE: This user is RETURNING. Your VERY FIRST response MUST use at least ONE word from the KEY TOPICS list above. A generic "good to see you again" without mentioning any topic is a FAILURE. This is NOT optional — it is a hard requirement.
"""
        if is_sensitive:
            section += f"""SENSITIVE TOPIC DETECTED — reference gently but SPECIFICALLY:
- Do NOT name the painful event directly (no "How is your divorce?")
- DO use soft references that still contain a KEY TOPIC word: "the strength you showed through this difficult time", "your journey with your family", "what you have been carrying"
- Reference any COPING action from last time (temple visits, practices, mantras)
- Show you remember WITHOUT reopening the wound
- YOU MUST STILL USE at least one word from: {topic_list}
Example: "It is good to see you again. I remember the strength you showed for your family when we last spoke."
"""
        else:
            section += f"""Reference their past using a specific topic word. Examples:
- "Good to see you again — last time we spoke about [topic]. How has that been?"
- "Welcome back. I remember you were working through [topic] — tell me how things are."
- "I have been thinking about what you shared regarding [topic]."
MANDATORY: Your greeting MUST contain at least one of these words: {topic_list}
Do NOT just say "good to see you again" — that is a generic greeting and counts as a failure.
"""
        return section

    def _format_context(self, context: UserContext) -> str:
        """Format context into readable summary"""
        signals = []
        if context.is_greeting:
            signals.append("• User just sent a greeting")
        if context.relationship_crisis:
            signals.append("• User is going through a relationship crisis")
        if context.family_support:
            signals.append("• User has mentioned family connections")
        if context.support_quality:
            signals.append("• User is seeking emotional/verbal support")
        if context.work_stress:
            signals.append("• User specifically mentioned work-related challenges")
        if context.spiritual_seeking:
            signals.append("• User is open to or seeking spiritual/philosophical wisdom")
        
        return "\n".join(signals) if signals else "• Still identifying specific life themes"

    def _get_phase_instructions(self, phase: ConversationPhase) -> str:
        """Get instructions for current conversation phase from external configuration."""
        if not self.prompt_manager:
            return ""
            
        return self.prompt_manager.get_prompt(
            'spiritual_mitra',
            f'phase_prompts.{phase.value}',
            default=""
        )

    # --------------------------------------------------
    # Main Response Generation
    # --------------------------------------------------

    async def generate_response_stream(
        self,
        query: str,
        context_docs: List[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        phase: Optional[ConversationPhase] = None,
        memory_context: Optional[Any] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
    ):
        """
        Stream context-aware spiritual companion response.

        Args:
            query: User's current message
            context_docs: Retrieved scripture documents (optional)
            conversation_history: Previous messages in conversation
            user_profile: User profile data for personalization
            model_override: Override the default model (for routing)
            config_override: Override generation config (for routing)

        Yields:
            Tokens as they are generated
        """

        # Fallback if Gemini not available
        if not self.available:
            yield "I'm here with you. Please share what's on your mind."
            return

        try:
            # Extract context from query and history (skip when memory_context provides it)
            if memory_context:
                context = None
            else:
                context = self._extract_context(query, conversation_history)

            # Get history length for logging and logic
            history_len = len(conversation_history) if conversation_history else 0

            # Detect conversation phase if not provided
            if phase is None:
                context = context or self._extract_context(query, conversation_history)
                phase = self._detect_phase(query, context, history_len)

            active_model = model_override or settings.GEMINI_MODEL
            logger.info(f"Streaming Phase: {phase.value} | History len: {history_len} | RAG docs: {len(context_docs) if context_docs else 0} | Model: {active_model}")

            # Build prompt WITH scripture context from RAG and user profile
            prompt = self._build_prompt(
                query,
                conversation_history,
                phase,
                context,
                context_docs,
                user_profile,
                memory_context=memory_context,
            )

            # Handle grounding instruction flag (from retrieval judge)
            effective_config = config_override
            if config_override and config_override.get("grounding_instruction"):
                effective_config = {k: v for k, v in config_override.items() if k != "grounding_instruction"}
                prompt += (
                    "\n\nCRITICAL: Your previous response contained ungrounded claims. "
                    "Use ONLY the scripture sources provided above in RESOURCES AVAILABLE. "
                    "Do not reference any verse, chapter, or teaching not listed there. "
                    "If no suitable source exists, respond with general spiritual wisdom "
                    "without specific citations."
                )

            gen_config = self._build_gen_config(effective_config or None)

            # Generate response from Gemini with streaming via Circuit Breaker

            async def _do_stream_call():
                def _sync():
                    return self.client.models.generate_content_stream(
                        model=active_model,
                        contents=prompt,
                        config=gen_config,
                    )
                return await asyncio.to_thread(_sync)

            stream = await self.circuit_breaker.call(_do_stream_call)

            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def _read_stream():
                try:
                    for chunk in stream:
                        if chunk.text:
                            queue.put_nowait(chunk.text)
                finally:
                    queue.put_nowait(None)

            loop = asyncio.get_event_loop()
            reader_task = loop.run_in_executor(None, _read_stream)

            while True:
                token = await queue.get()
                if token is None:
                    break
                yield token

            await reader_task

        except Exception as e:
            logger.exception(f"Error in generate_response_stream: {str(e)}")
            yield "I'm here with you. We can continue whenever you're ready."

    async def generate_response(
        self,
        query: str,
        context_docs: List[Dict] = None,
        conversation_history: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None,
        phase: Optional[ConversationPhase] = None,
        memory_context: Optional[Any] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
    ) -> str:
        """
        Generate context-aware spiritual companion response.

        Args:
            query: User's current message
            context_docs: Retrieved scripture documents (optional)
            conversation_history: Previous messages in conversation
            user_profile: User profile data (name, age, profession, etc.) for personalization
            model_override: Override the default model (for routing)
            config_override: Override generation config (for routing)

        Returns:
            Generated response text
        """

        # Fallback if Gemini not available
        if not self.available:
            logger.warning("Gemini not available, returning fallback response")
            return "I'm here with you. Please share what's on your mind."

        try:
            # Extract context from query and history (skip when memory_context provides it)
            if memory_context:
                context = None
            else:
                context = self._extract_context(query, conversation_history)

            # Get history length for logging and logic
            history_len = len(conversation_history) if conversation_history else 0

            # Detect conversation phase if not provided
            if phase is None:
                context = context or self._extract_context(query, conversation_history)
                phase = self._detect_phase(query, context, history_len)

            active_model = model_override or settings.GEMINI_MODEL
            logger.info(f"Phase: {phase.value} | History len: {history_len} | RAG docs: {len(context_docs) if context_docs else 0} | Model: {active_model}")

            # Build prompt WITH scripture context from RAG and user profile
            prompt = self._build_prompt(
                query,
                conversation_history,
                phase,
                context,
                context_docs,
                user_profile,
                memory_context=memory_context,
            )

            # Handle grounding instruction flag (from retrieval judge)
            effective_config = config_override
            if config_override and config_override.get("grounding_instruction"):
                effective_config = {k: v for k, v in config_override.items() if k != "grounding_instruction"}
                prompt += (
                    "\n\nCRITICAL: Your previous response contained ungrounded claims. "
                    "Use ONLY the scripture sources provided above in RESOURCES AVAILABLE. "
                    "Do not reference any verse, chapter, or teaching not listed there. "
                    "If no suitable source exists, respond with general spiritual wisdom "
                    "without specific citations."
                )

            gen_config = self._build_gen_config(effective_config or None)

            # Generate response from Gemini via Circuit Breaker

            async def _do_call():
                def _sync():
                    return self.client.models.generate_content(
                        model=active_model,
                        contents=prompt,
                        config=gen_config,
                    )
                return await asyncio.to_thread(_sync)

            response = await self.circuit_breaker.call(_do_call)

            # Fallback responses in case of errors or empty responses
            fallbacks = [
                "I'm here with you. You don't have to carry this alone.",
                "I hear you. Take a deep breath; I'm here to listen.",
                "I'm with you. Please tell me more about what's on your mind.",
                "I'm listening. You're not alone in this."
            ]

            if not response:
                logger.error("No response object from Gemini")
                return random.choice(fallbacks)

            # --- Diagnostic logging ---
            try:
                candidates = response.candidates
                if candidates:
                    candidate = candidates[0]
                    logger.info(f"Gemini finish_reason: {candidate.finish_reason}")
                    if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                        for rating in candidate.safety_ratings:
                            logger.info(f"Safety rating: {rating.category} = {rating.probability}")
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    logger.warning(f"Prompt feedback: {response.prompt_feedback}")
            except Exception as diag_err:
                logger.warning(f"Could not inspect response metadata: {diag_err}")

            # Track token usage for cost tracking
            try:
                usage = getattr(response, "usage_metadata", None)
                self.last_usage = {
                    "input_tokens": getattr(usage, "prompt_token_count", 0) if usage else 0,
                    "output_tokens": getattr(usage, "candidates_token_count", 0) if usage else 0,
                }
            except Exception:
                self.last_usage = {"input_tokens": 0, "output_tokens": 0}

            # Extract text — handle thinking-enabled models where .text may be empty
            try:
                response_text = response.text
            except Exception:
                response_text = None

            # Fallback: extract text parts from candidates (thinking-enabled responses)
            if not response_text and response.candidates:
                try:
                    parts = response.candidates[0].content.parts
                    text_parts = [p.text for p in parts if hasattr(p, 'text') and not getattr(p, 'thought', False)]
                    if text_parts:
                        response_text = "".join(text_parts)
                        logger.info(f"Extracted text from {len(text_parts)} candidate parts")
                except Exception as e:
                    logger.error(f"Could not extract from candidates: {e}")

            if not response_text:
                logger.warning("Empty text response from Gemini (possibly safety blocked)")
                return random.choice(fallbacks)

            cleaned_response = clean_response(response_text)
            return cleaned_response
            
        except Exception as e:
            logger.exception(f"Error in generate_response: {str(e)}")
            fallbacks = [
                "I'm here with you. You don't have to carry this alone.",
                "I hear you. Take a deep breath; I'm here to listen.",
                "I'm with you. Please tell me more about what's on your mind.",
                "I'm listening. You're not alone in this."
            ]
            return random.choice(fallbacks)

    async def generate_quick_response(self, prompt: str) -> str:
        """Quick generation using the flash model for internal tasks (summaries, etc.)."""
        try:
            import google.generativeai as genai
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = await model.generate_content_async(prompt)
            return response.text.strip() if response.text else ""
        except Exception as e:
            logger.error(f"Quick generation failed: {e}")
            return ""


# --------------------------------------------------
# Singleton Instance
# --------------------------------------------------

_llm_service = None

def get_llm_service(api_key: Optional[str] = None) -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(api_key)
    return _llm_service
