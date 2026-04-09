"""
LLM Service - Spiritual Companion with Context-Aware Responses
Provides empathetic, phase-aware interactions using Gemini AI
"""

import asyncio
import hashlib
import logging
import random
import re
import time as _time
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from config import settings
from services.resilience import CircuitBreaker
from services.language_detector import get_language_constraint
from google.genai import types as genai_types
from models.session import ConversationPhase


logger = logging.getLogger(__name__)

# Refresh Gemini cached content this many seconds before its TTL expires
_CACHE_REFRESH_BUFFER = 60

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

def strip_disallowed_markdown(text: str) -> str:
    """Remove the markdown elements forbidden by the Mitra style guide.

    Per CLAUDE.md rule #2 (revised Apr 2026), Mitra responses use a
    *restricted* markdown subset. This function is the belt-and-braces
    enforcement: it strips the disallowed elements while preserving the
    allowed ones, so even if a prompt drift or LLM quirk introduces a
    forbidden form, the user never sees it.

    Allowed (PRESERVED):
    - **bold** — for emphasis on key terms (1-2 per response)
    - "- " bullet lists at line start — for short step sequences (2-5 items)
    - "---" horizontal rules on their own line — once per response, max
    - [VERSE]...[/VERSE] and [MANTRA]...[/MANTRA] structural tags

    Forbidden (STRIPPED):
    - *italic* / _italic_ — competes with verse italic styling
    - `inline code` — out of place in spiritual chat
    - # headers — too clinical, breaks warm tone
    - > blockquotes — [VERSE] handles quoted scripture
    - 1. numbered lists — verbose; use prose or "- " bullets
    - "* " and "+ " bullets — normalized to "- " for consistency

    Does NOT strip: lone asterisks/underscores in math/identifiers, em
    dashes, or anything inside [VERSE]/[MANTRA] tags.
    """
    if not text:
        return ""

    # Protect structural tags so we don't rewrite anything inside them.
    placeholders: list[str] = []

    def _protect(match):
        placeholders.append(match.group(0))
        return f"\x00SM{len(placeholders) - 1}\x00"

    text = re.sub(
        r"\[(?:VERSE|MANTRA)\][\s\S]*?\[/(?:VERSE|MANTRA)\]",
        _protect,
        text,
    )

    # Protect "---" horizontal rules from any later regex pass.
    text = re.sub(r"^---\s*$", "\x00HR\x00", text, flags=re.MULTILINE)

    # Strip *italic* (single asterisk) WITHOUT touching **bold** spans.
    # Two-pass scan: skip past balanced **...** spans, strip lone *...*.
    def _strip_italic(t: str) -> str:
        out: list[str] = []
        i = 0
        n = len(t)
        while i < n:
            # Pass through **bold** spans untouched
            if i + 1 < n and t[i] == "*" and t[i + 1] == "*":
                end = t.find("**", i + 2)
                if end != -1:
                    out.append(t[i:end + 2])
                    i = end + 2
                    continue
            # Try to match a single-* italic span: *word(s)*
            if (
                t[i] == "*"
                and i + 1 < n
                and t[i + 1] != "*"
                and not t[i + 1].isspace()
            ):
                close = t.find("*", i + 1)
                if (
                    close != -1
                    and close - i <= 200
                    and "\n" not in t[i + 1:close]
                ):
                    out.append(t[i + 1:close])
                    i = close + 1
                    continue
            out.append(t[i])
            i += 1
        return "".join(out)

    text = _strip_italic(text)
    # _italic_ — strip with the same word-boundary guards as before
    text = re.sub(r"(?<!\w)_(?!\s)([^_\n]+?)(?<!\s)_(?!\w)", r"\1", text)
    # `inline code` → unwrap
    text = re.sub(r"`([^`\n]+)`", r"\1", text)

    # Line-leading FORBIDDEN markers — remove the marker, keep the content.
    text = re.sub(r"^[ \t]*#{1,6}[ \t]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*>[ \t]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*\d+\.[ \t]+", "", text, flags=re.MULTILINE)
    # Normalize "* " and "+ " bullets to "- " (canonical allowed form).
    # Crucially, this only matches at line start with trailing space —
    # so it cannot eat into a "**bold**" span (which has no trailing space).
    text = re.sub(r"^[ \t]*[*+][ \t]+", "- ", text, flags=re.MULTILINE)

    # Restore horizontal-rule placeholders.
    text = text.replace("\x00HR\x00", "---")
    # Restore structural tag placeholders.
    for i, block in enumerate(placeholders):
        text = text.replace(f"\x00SM{i}\x00", block)

    return text


# Backwards-compat alias — many callers and tests still import the old
# name. New code should prefer ``strip_disallowed_markdown``.
strip_markdown = strip_disallowed_markdown


def clean_response(text: str) -> str:
    """Remove trailing questions and clean formatting, especially from [VERSE] tags"""
    if not text:
        return ""

    # Simply return the text cleaned of whitespace initially
    text = text.strip()

    # CLAUDE.md rule #2 (revised Apr 2026): restricted markdown in LLM
    # responses. **bold**, "- " bullets, and "---" rules are PRESERVED;
    # headers, blockquotes, italic, code, and numbered lists are stripped.
    # Belt-and-braces enforcement so a prompt drift or LLM quirk never
    # leaks forbidden elements to users. Tags ([VERSE]/[MANTRA]) are
    # preserved by strip_disallowed_markdown internally.
    text = strip_disallowed_markdown(text)

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
        # Compact version for listening phase — strips domain compass, practice details, examples
        # to reduce token count (~3000 → ~1300) for faster Gemini responses
        self._compact_system_instruction = self._build_compact_instruction(self.system_instruction)

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

            self.client = genai.Client(
                api_key=self.api_key,
                http_options={"timeout": 60000},  # 60s — allows SDK retries when Gemini returns 503
            )
            self.available = True
            self._gemini_caches = {}  # {cache_key: cache_name}
            logger.info("✅ LLM Service initialized with Gemini (8s timeout)")

        except Exception:
            self.available = False
            logger.exception("❌ Failed to initialize Gemini")

    def prewarm_caches(self) -> None:
        """Pre-warm Gemini context caches at startup.

        Creates cached content for ALL model+phase combinations the router could select,
        so no user request ever pays the 30-35 second cache creation penalty.
        """
        if not self.available or settings.GEMINI_CACHE_TTL <= 0:
            return

        # Collect ALL models the router could use
        models_to_warm = set()
        models_to_warm.add(settings.GEMINI_MODEL)
        try:
            from services.model_router import TIER_MODELS
            for model_name in TIER_MODELS.values():
                models_to_warm.add(model_name)
        except ImportError:
            pass

        phase_keys = ["listening", "full"]

        for model in models_to_warm:
            for phase_key in phase_keys:
                phase = ConversationPhase.LISTENING if phase_key == "listening" else ConversationPhase.GUIDANCE
                sys_instruction = self._get_system_instruction(phase)
                cache_name = self._get_or_create_cache(model, sys_instruction, phase_key, allow_blocking=True)
                if cache_name:
                    logger.info(f"Pre-warmed cache: {model}:{phase_key} → {cache_name}")
                else:
                    logger.warning(f"Failed to pre-warm cache: {model}:{phase_key}")

    # --------------------------------------------------
    # Gemini Context Caching
    # --------------------------------------------------

    def _get_or_create_cache(self, model: str, system_instruction: str, phase_key: str, allow_blocking: bool = False) -> Optional[str]:
        """Get existing Gemini cached content or fall back to inline instruction.

        NEVER blocks on cache creation during a user request. If cache miss:
        - Returns None immediately (caller uses inline system_instruction)
        - Schedules background cache creation for next request

        Only blocks when allow_blocking=True (used during startup pre-warm).
        """
        if settings.GEMINI_CACHE_TTL <= 0:
            return None
        _instr_hash = hashlib.md5(system_instruction.encode()).hexdigest()[:8]
        cache_key = f"{model}:{phase_key}:{_instr_hash}"
        entry = self._gemini_caches.get(cache_key)
        if entry:
            name, expires_at = entry
            if _time.monotonic() < expires_at:
                return name
            del self._gemini_caches[cache_key]

        # Cache miss — if not allowed to block, return None immediately
        # and schedule background creation for next request
        if not allow_blocking:
            self._schedule_background_cache(model, system_instruction, phase_key, cache_key)
            return None

        # Blocking creation (only during startup pre-warm)
        return self._create_cache_sync(model, system_instruction, cache_key)

    def _create_cache_sync(self, model: str, system_instruction: str, cache_key: str) -> Optional[str]:
        """Synchronous cache creation — only used during startup pre-warm."""
        try:
            from google.genai import types
            cache = self.client.caches.create(
                model=model,
                config=types.CreateCachedContentConfig(
                    system_instruction=system_instruction,
                    ttl=f"{settings.GEMINI_CACHE_TTL}s",
                ),
            )
            expires_at = _time.monotonic() + settings.GEMINI_CACHE_TTL - _CACHE_REFRESH_BUFFER
            self._gemini_caches[cache_key] = (cache.name, expires_at)
            logger.info(f"Gemini cache created: {cache_key} → {cache.name}")
            return cache.name
        except Exception as e:
            logger.warning(f"Gemini cache creation failed: {e}")
            return None

    def _schedule_background_cache(self, model: str, system_instruction: str, phase_key: str, cache_key: str):
        """Schedule cache creation in background thread — doesn't block the request."""
        import threading
        if hasattr(self, '_pending_cache_keys') and cache_key in self._pending_cache_keys:
            return  # Already being created
        if not hasattr(self, '_pending_cache_keys'):
            self._pending_cache_keys = set()
        self._pending_cache_keys.add(cache_key)

        def _bg_create():
            try:
                self._create_cache_sync(model, system_instruction, cache_key)
            finally:
                self._pending_cache_keys.discard(cache_key)

        threading.Thread(target=_bg_create, daemon=True).start()
        logger.info(f"Background cache creation scheduled: {cache_key}")

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
            while file_ref.state == "PROCESSING":
                await asyncio.sleep(2)
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

    # _PHASE_MAX_TOKENS removed — token budgets are now solely managed by model_router.py

    def _build_gen_config(self, config_override: Optional[Dict] = None) -> Dict:
        """Build the Gemini generation config dict.

        Token budget (max_output_tokens) comes from model_router via config_override.
        This method does NOT override it — model_router is the single authority.
        Fallback uses TokenBudgetCalculator default (moderate=1024), NOT a hardcoded value.
        """
        from services.token_budget import CEILING_MAP, DEFAULT_CEILING
        gen_config = config_override.copy() if config_override else {
            "temperature": settings.RESPONSE_TEMPERATURE,
            "max_output_tokens": DEFAULT_CEILING,  # Adaptive default, not hardcoded
            "safety_settings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ],
        }
        phase = gen_config.pop("_phase", None)
        model = gen_config.pop("_model", settings.GEMINI_MODEL)
        # Caller may pin a specific thinking budget (e.g. internal callers
        # like the retrieval judge that genuinely benefit from reasoning).
        # If absent, fall through to the global default in config.py.
        thinking_budget_override = gen_config.pop("_thinking_budget", None)
        sys_instruction = self._get_system_instruction(phase)
        phase_key = "listening" if phase in (ConversationPhase.LISTENING, ConversationPhase.CLARIFICATION) else "full"

        # Disable AFC unconditionally — adds latency and we never use it.
        gen_config.pop("thinking_config", None)
        gen_config["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(disable=True)

        # Thinking-mode policy.
        #
        # Gemini 2.5/3 models default to thinking ON, which (a) adds 5-15s of
        # latency and (b) can leak chain-of-thought scratchpad into responses
        # if the SDK part filtering misses a frame (we observed this in live
        # E2E testing — see plan file C1). The default budget therefore comes
        # from settings.LLM_THINKING_BUDGET_DEFAULT (default 0 = off) so the
        # main conversational path never has scratchpad to leak. Internal
        # callers that need reasoning can opt in via the ``_thinking_budget``
        # gen_config kwarg.
        budget = (
            thinking_budget_override
            if thinking_budget_override is not None
            else settings.LLM_THINKING_BUDGET_DEFAULT
        )
        # Only set thinking_config on models that actually support it.
        # gemini-2.5/3 family supports it; gemini-2.0-flash does not.
        if budget > 0 and ("2.5" in model or "3-" in model or "3." in model):
            gen_config["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=budget)

        cache_name = self._get_or_create_cache(model, sys_instruction, phase_key)
        if cache_name:
            gen_config["cached_content"] = cache_name
        else:
            gen_config["system_instruction"] = sys_instruction
        return gen_config

    # --------------------------------------------------
    # Prompt Building
    # --------------------------------------------------

    _COMPACT_STRIP_MARKERS = (
        'DOMAIN-SPECIFIC COMPASS', 'WHEN THEY REPORT BACK',
        'WHEN THEY ACCEPT A SUGGESTION', 'WHEN THEY ARE ASKING FOR SOMEONE',
        'WHEN THEY ARE FAR FROM HOME', 'SANATAN DHARMA BOUNDARY',
    )

    @staticmethod
    def _build_compact_instruction(full_instruction: str) -> str:
        """Strip domain compass & reference sections for listening phase (saves ~1700 tokens)."""
        lines = full_instruction.split('\n')
        compact, skip = [], False
        for line in lines:
            if any(marker in line for marker in LLMService._COMPACT_STRIP_MARKERS):
                skip = True
            elif skip and line.strip().startswith('====='):
                skip = False
            if not skip:
                compact.append(line)
        return '\n'.join(compact)

    def _get_system_instruction(self, phase) -> str:
        """Return compact instruction for listening, full instruction for guidance."""
        if phase in (ConversationPhase.LISTENING, ConversationPhase.CLARIFICATION):
            return self._compact_system_instruction
        return self.system_instruction

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

        # Determine if conversation topic is spiritual (controls panchang/astro inclusion)
        life_area = (user_profile or {}).get('life_area', '')
        query_lower = query.lower()
        _spiritual_keywords = {"puja", "mantra", "temple", "vrat", "ritual", "meditation",
                               "dhyana", "prayer", "havan", "kirtan", "sadhana", "japa",
                               "panchang", "tithi", "nakshatra", "muhurat", "deity", "god",
                               "auspicious", "shubh", "muhurata", "aarti", "pooja", "bhajan"}
        is_spiritual_topic = (
            life_area == 'spiritual'
            or any(kw in query_lower for kw in _spiritual_keywords)
        )
        is_guidance_phase = phase in (ConversationPhase.GUIDANCE, ConversationPhase.SYNTHESIS)

        # Format user profile if available
        profile_text = ""
        if user_profile:
            logger.info(f"Building prompt with user_profile: {user_profile}")
            has_data = False
            profile_parts = []

            # Always include current date & time so LLM never has to guess
            now = datetime.now()
            profile_parts.append(f"   • Current Date & Time: {now.strftime('%A, %B %d, %Y')} | {now.strftime('%I:%M %p')} IST")
            has_data = True

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

            # Conversation context
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
                profile_parts.append(f"   • Preferred deity: {user_profile.get('preferred_deity')} (use as a starting point, not the only tradition — vary your recommendations across deities and traditions)")
                has_data = True
            if user_profile.get('location'):
                profile_parts.append(f"   • Location: {user_profile.get('location')}")
                has_data = True
            if user_profile.get('spiritual_interests'):
                profile_parts.append(f"   • Spiritual interests: {', '.join(user_profile.get('spiritual_interests', []))}")
                has_data = True

            # Spiritual profile — always include so LLM can personalize any response
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

            # Current Panchang — only include when topic is spiritual or in guidance phase
            if user_profile.get('current_panchang') and (is_spiritual_topic or is_guidance_phase):
                p = user_profile['current_panchang']
                panchang_lines = ["   • CURRENT PANCHANG (Today):"]
                if p.get('date') or p.get('vaara'):
                    panchang_lines.append(f"     Today: {p.get('vaara', '')} {p.get('date', '')}")

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
            
            # Semantic Long-Term Memories — deduplicated
            if user_profile.get('past_memories'):
                seen = set()
                deduped = []
                for mem in user_profile['past_memories']:
                    key = mem.strip().lower()[:120]
                    if key not in seen:
                        seen.add(key)
                        deduped.append(mem)
                if deduped:
                    profile_parts.append("\n   RELEVANT PAST CONTEXT (from your history):")
                    for i, mem in enumerate(deduped, 1):
                        profile_parts.append(f"   {i}. \"{mem}\"")
                    has_data = True

            # Previous suggestions context (so LLM can deepen on acceptance)
            if user_profile.get('last_suggestions'):
                suggestions = user_profile['last_suggestions']
                profile_parts.append("\n   YOUR RECENT SUGGESTIONS TO THIS USER:")
                for s in suggestions[-3:]:
                    profile_parts.append(f"   • Turn {s['turn']}: You suggested {s['practice']}")
                has_data = True

            # Products previously recommended in this session — surfaced so the
            # LLM can answer follow-ups like "how do I use that mala?" with
            # awareness of the actual item recommended. Added Apr 2026 because
            # users were getting generic answers when referencing earlier
            # product cards. Source: SessionState.recent_products (FIFO cap 5).
            if user_profile.get('recent_products'):
                recent_products = user_profile['recent_products']
                profile_parts.append("\n   PRODUCTS YOU RECOMMENDED IN THIS SESSION:")
                for p in recent_products[-5:]:
                    name = p.get('name') or 'Unnamed product'
                    category = p.get('category') or ''
                    line = f"   • {name}"
                    if category:
                        line += f" ({category})"
                    profile_parts.append(line)
                profile_parts.append(
                    "   If the user references one of these (e.g. 'that mala', "
                    "'the diya you mentioned', 'how do I use it'), you know "
                    "exactly which item they mean — answer specifically about it."
                )
                has_data = True

            # Verse/mantra anti-repetition history (Layer 2 diversity).
            # Wording is intentionally strong because Gemini's earlier
            # "offer fresh alternatives" phrasing was treated as a soft hint
            # and frequently ignored. The prohibition language below is
            # paired with a per-entry FORBIDDEN marker to nudge the model
            # toward picking from the broader 16-mantra approved list in the
            # YAML prompt.
            if user_profile.get('suggested_verses'):
                profile_parts.append(
                    "\n   ===== MANTRAS / VERSES ALREADY GIVEN — DO NOT REPEAT ====="
                )
                profile_parts.append(
                    "   You have already suggested the following in this conversation."
                )
                profile_parts.append(
                    "   You MUST pick a DIFFERENT mantra or verse this turn:"
                )
                for entry in user_profile['suggested_verses'][-10:]:
                    parts = []
                    if entry.get("mantras"):
                        parts.extend(entry["mantras"][:2])
                    if entry.get("references"):
                        parts.extend(entry["references"][:2])
                    if parts:
                        profile_parts.append(
                            f"   ✗ Turn {entry.get('turn', '?')}: {' | '.join(parts)} (FORBIDDEN this turn)"
                        )
                profile_parts.append(
                    "   If you catch yourself about to suggest one of the above, "
                    "STOP and pick another mantra from the approved list."
                )
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
        
        # Format conversation history (last 14 messages = 7 turns of context)
        history_text = ""
        if conversation_history:
            # Exclude the very last message if it's the current query to avoid duplication
            recent_history = conversation_history[-14:]
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
        
        # Context summary — deduplicated (rashi/gotra/nakshatra already in profile)
        fact_text = ""
        if memory_context:
            context_summary = memory_context.get_memory_summary()
            story = memory_context.story

            # Only include facts NOT already present in the profile section
            facts = []
            if story.purchase_history:
                facts.append(f"• Purchase History: {', '.join(story.purchase_history)}")
            if story.detected_topics:
                recent_topics = list(dict.fromkeys(story.detected_topics[-5:]))
                facts.append(f"• Topic journey: {' → '.join(recent_topics)}")

            # User quotes — deduplicate near-identical quotes
            if hasattr(memory_context, 'user_quotes'):
                seen_quotes = set()
                for quote in memory_context.user_quotes[-10:]:
                    q = quote['quote'].strip().lower()
                    if q not in seen_quotes:
                        seen_quotes.add(q)
                        facts.append(f"• User shared: \"{quote['quote']}\"")

            fact_text = "\n".join(facts) if facts else ""
        else:
            context_summary = self._format_context(context)
            fact_text = ""
        
        # Phase-specific instructions with readiness trigger context
        phase_instructions = self._get_phase_instructions(phase)
        readiness_trigger = (user_profile or {}).get('readiness_trigger', '')
        if readiness_trigger and phase == ConversationPhase.GUIDANCE:
            trigger_labels = {
                'explicit_request': (
                    'The user asked a DIRECT question — answer it directly using '
                    'all available profile data. Do not deflect with generic advice.'
                ),
                'user_asked_for_guidance': (
                    'The user asked for guidance directly — give a specific, '
                    'personalized answer using all available profile data.'
                ),
                'signals_accumulated': 'You have gathered enough context over multiple turns to offer guidance now.',
            }
            trigger_note = trigger_labels.get(readiness_trigger, '')
            if trigger_note:
                phase_instructions += f"\nWHY GUIDANCE NOW: {trigger_note}\n"
        
        # Format scripture context from RAG if available
        scripture_context = ""
        # Allow verses in both phases so the bot can choose the right moment
        if context_docs and len(context_docs) > 0:
            scripture_context = "\n═══════════════════════════════════════════════════════════\n"
            scripture_context += "RESOURCES AVAILABLE (OPTIONAL — use ONLY if one genuinely fits this moment. It is completely fine to ignore ALL of these.):\n"
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

                # Defense against curated_concept docs that store the full
                # 3,000+ char markdown document in their text/reference fields.
                # Without this cap, Gemini regurgitates the markdown into the
                # response — found Apr 2026 in a user screenshot showing
                # "SOURCES: SANATAN SCRIPTURES SANATAN SCRIPTURES
                # CURATED_CONCEPTS_GENERATED.## NANDI BULL SYMBOLISM..."
                # leaking into the chat bubble. The real fix is data
                # re-ingestion; this is the runtime guardrail.
                if doc_type == "curated_concept":
                    if original_text and len(original_text) > 400:
                        original_text = original_text[:400].rstrip() + "…"
                    if meaning and len(meaning) > 400:
                        meaning = meaning[:400].rstrip() + "…"

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
                    # Cap reference at 120 chars — real scripture refs are
                    # under 60 chars (e.g. "Bhagavad Gita 2.47"), only the
                    # curated_concepts entries have markdown bodies stuffed
                    # into the field. Same Apr 2026 leak as above.
                    _ref = reference if len(reference) <= 120 else reference[:120].rstrip() + "…"
                    scripture_context += f" — {_ref}"
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
                "No scripture resources are available for this query. "
                "Respond with general spiritual wisdom WITHOUT citing any specific "
                "verse, chapter, or scripture reference. A warm, human response "
                "without citations is always better than a vague or inaccurate one.\n"
            )


        # Build final prompt
        # Only include returning-user greeting instruction on the first turn.
        # After turn 1, the LLM has conversation history and doesn't need the "greet them" prompt.
        _history_turns = len(conversation_history) if conversation_history else 0
        _is_first_turn = _history_turns <= 1  # 0 = no history, 1 = just the user's first message
        returning_user_section = self._build_returning_user_section(
            is_returning_user and _is_first_turn, memory_context
        )

        # Build facts section only if there's content
        facts_section = ""
        if fact_text:
            facts_section = f"""
═══════════════════════════════════════════════════════════
CONTEXT & JOURNEY:
═══════════════════════════════════════════════════════════
{fact_text}
"""

        # Adaptive length hint — placed at end of prompt for maximum model attention
        _query_words = len(query.strip().split())
        _acceptance_words = {"ok", "okay", "sure", "fine", "sounds", "good", "thanks", "thank", "bye", "goodbye", "alright", "cool", "great", "perfect", "noted", "got"}
        _query_lower_words = set(query.strip().lower().split())

        # Detect first emotional turn — the user's opening share of distress.
        # On a first emotional message, the YAML prompt's adaptive-length
        # guidance is too permissive and the model produces 150-250 word
        # responses with verses + mantras + practices. The evaluation showed
        # this overwhelms users who needed to feel heard first. Force a hard
        # cap and explicitly forbid scripture/mantras on this turn.
        _emotional_states = {
            "grief", "anxiety", "anger", "fear", "despair",
            "loneliness", "hopelessness", "shame",
        }
        _current_emotion = ""
        if memory_context and memory_context.story:
            _current_emotion = (memory_context.story.emotional_state or "").lower()
        # User-turn count from history (assistant messages don't count toward
        # the user's "first share").
        _user_turns = sum(
            1 for m in (conversation_history or []) if m.get("role") == "user"
        )
        _is_first_emotional_share = (
            _current_emotion in _emotional_states
            and _user_turns <= 1
            and _query_words >= 10  # not a one-liner; the user is opening up
        )

        if _query_words <= 4 and _query_lower_words & _acceptance_words:
            _length_hint = "LENGTH: The user's message is a brief acceptance or closing. Respond in 1-2 sentences only.\n"
        elif _query_words <= 3:
            _length_hint = "LENGTH: The user's message is very short. Keep your response to 1-3 sentences.\n"
        elif _is_first_emotional_share:
            _length_hint = (
                "LENGTH: This is the user's FIRST emotional share in this session. "
                "Respond in 2-3 short sentences (under 60 words total). Acknowledge "
                "their pain specifically, then ask ONE gentle clarifying question. "
                "Do NOT include any verse, mantra, scripture citation, or practice "
                "prescription on this turn — just listen and be present. The depth "
                "comes later, after they feel heard.\n"
            )
        else:
            _length_hint = ""

        # Programmatic language/script constraint — overrides Gemini's default
        # mirror inference, which is unreliable when the system prompt contains
        # heavy Hindi vocabulary. Computed from the actual user query script.
        _language_constraint = get_language_constraint(query)

        # Context Budget Manager — trim variable sections if prompt is too large
        from services.context_budget import ContextBudgetManager
        _budget_mgr = ContextBudgetManager(
            max_output_tokens=getattr(self, '_current_max_output', 2048)
        )
        _sections = {
            "user_profile": profile_text,
            "panchang": "",  # Already embedded in profile_text
            "past_memories": "",  # Already embedded in profile_text
            "verse_history": "",  # Already embedded in profile_text
            "conversation_history": history_text,
            "rag_context": scripture_context,
            "returning_user": returning_user_section,
            "system_instruction": "",  # Handled separately via system_instruction
            "current_query": query,
            "phase_prompt": phase_instructions,
        }
        _trimmed = _budget_mgr.fit(_sections)
        profile_text = _trimmed.get("user_profile", profile_text)
        history_text = _trimmed.get("conversation_history", history_text)
        scripture_context = _trimmed.get("rag_context", scripture_context)
        returning_user_section = _trimmed.get("returning_user", returning_user_section)

        prompt = f"""
{profile_text}

═══════════════════════════════════════════════════════════
WHAT YOU KNOW SO FAR (EMOTIONAL CONTEXT):
═══════════════════════════════════════════════════════════
{context_summary}
{facts_section}
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

BEHAVIORAL CHECKS (apply before writing your response):
- {_language_constraint}
- SHORT ACKNOWLEDGMENT: If user's message is 1-3 words (ok, thanks, sure, fine, got it, sounds good) — respond with ONLY 1 warm sentence. NO verse, NO mantra, NO scripture, NO spiritual advice. Just acknowledge warmly.
- REPETITION: If your last 2 responses already gave a mantra/practice/Gita reference and the user is STILL processing — ask a deeper question instead.
- LISTENING PHASE: If phase is LISTENING and user is sharing pain — end with a QUESTION, not a practice.
- "TONIGHT": If your previous response also said "Tonight" — use a different timing.
- RETURNING USER: Only on the FIRST message of a session. After that, DO NOT re-greet or re-introduce — continue the conversation naturally.

{scripture_context}

RESPOND TO WHAT THEY ACTUALLY SAID — not to what your context data contains.
GREETING RULE: When user just says "Hello", "Hi", "Namaste" — respond with a simple warm greeting and ask how they are. Do NOT mention their gotra, deity, temple visits, purchase history, or any profile data. Just be warm and human: "Namaste! How are you doing today?" Profile data is for LATER when it becomes contextually relevant.
Do NOT force panchang, verses, deity names, or practices into every response. A warm 2-3 sentence reply is almost always better than one that tries to include everything. One verse maximum. Use deity NAMES (Shiva, Krishna) not just "He".
Do NOT repeat any mantra, practice, or advice you already gave in this conversation. The user heard you the first time.
{_length_hint}
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
🔄 RETURNING USER — CONTEXT REFERENCE
{'═'*70}
THEIR JOURNEY SO FAR: {prev_summary}

KEY TOPICS FROM THEIR JOURNEY: {topic_list}

This user is RETURNING. Try to reference at least ONE detail from their KEY TOPICS above in your greeting — it shows you remember them. A generic "good to see you again" without any personal touch feels impersonal.
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

            # Handle correction hints from ResponseValidator (regeneration path)
            if effective_config and effective_config.get("correction_hints"):
                hints = effective_config["correction_hints"] or []
                effective_config = {k: v for k, v in effective_config.items() if k != "correction_hints"}
                if hints:
                    prompt += (
                        "\n\nCRITICAL — your previous response failed validation. "
                        "Regenerate the same answer addressing every point below:\n- "
                        + "\n- ".join(hints)
                    )

            _cfg = dict(effective_config or {}); _cfg["_phase"] = phase; _cfg["_model"] = active_model
            gen_config = self._build_gen_config(_cfg or None)

            # Generate response from Gemini with streaming via Circuit Breaker

            async def _do_stream_call():
                def _sync():
                    return self.client.models.generate_content_stream(
                        model=active_model,
                        contents=prompt,
                        config=gen_config,
                    )
                return await asyncio.to_thread(_sync)

            stream = await _do_stream_call()

            queue: asyncio.Queue[str | None] = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def _read_stream():
                try:
                    for chunk in stream:
                        if chunk.text:
                            loop.call_soon_threadsafe(queue.put_nowait, chunk.text)
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

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

            # Handle correction hints from ResponseValidator (regeneration path)
            if effective_config and effective_config.get("correction_hints"):
                hints = effective_config["correction_hints"] or []
                effective_config = {k: v for k, v in effective_config.items() if k != "correction_hints"}
                if hints:
                    prompt += (
                        "\n\nCRITICAL — your previous response failed validation. "
                        "Regenerate the same answer addressing every point below:\n- "
                        + "\n- ".join(hints)
                    )

            _cfg = dict(effective_config or {}); _cfg["_phase"] = phase; _cfg["_model"] = active_model
            gen_config = self._build_gen_config(_cfg or None)

            # Generate response from Gemini via Circuit Breaker

            async def _do_call():
                def _sync():
                    return self.client.models.generate_content(
                        model=active_model,
                        contents=prompt,
                        config=gen_config,
                    )
                return await asyncio.to_thread(_sync)

            response = await _do_call()

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
        """Quick generation using gemini-2.0-flash for internal tasks (grounding, summaries).
        Uses the lightweight model — no thinking overhead, ~1s vs ~4s."""
        try:
            from google.genai import types as _gentypes

            def _sync():
                return self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config={
                        "temperature": 0.1,
                        "max_output_tokens": 256,
                        "automatic_function_calling": _gentypes.AutomaticFunctionCallingConfig(disable=True),
                    },
                )
            response = await asyncio.to_thread(_sync)
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
