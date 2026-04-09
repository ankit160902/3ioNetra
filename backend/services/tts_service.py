"""
TTS Service - Text-to-Speech using gTTS with Hindi female voice
Optimized for reading Sanskrit/Hindi verses and spiritual content
"""

import io
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("gTTS not available. TTS features will be disabled.")


def _strip_markdown_for_tts(text: str) -> str:
    """Strip allowed-markdown syntax tokens before TTS synthesis.

    Apr 2026: Mitra responses can now contain **bold**, "- " bullets,
    and "---" horizontal rules (see backend/prompts/spiritual_mitra.yaml).
    Without sanitization gTTS would read "asterisk asterisk" or "dash" out
    loud. This is the server-side strip so every TTS consumer (current
    frontend, future mobile, etc.) gets clean audio automatically.
    """
    if not text:
        return text
    # **bold** → bold (unwrap)
    text = re.sub(r'\*\*([^*\n]+?)\*\*', r'\1', text)
    # "- " bullet prefix → just speak the item content (no leading dash)
    text = re.sub(r'^[ \t]*-[ \t]+', '', text, flags=re.MULTILINE)
    # "---" horizontal rule → drop entirely (it's a visual break, not speech)
    text = re.sub(r'^---\s*$', '', text, flags=re.MULTILINE)
    return text


class TTSService:
    """Text-to-Speech service using gTTS with Indian Hindi female voice."""

    def __init__(self):
        self.available = GTTS_AVAILABLE
        if self.available:
            logger.info("✅ TTS Service initialized (gTTS with Hindi voice)")
        else:
            logger.warning("❌ TTS Service unavailable (gTTS not installed)")

    def synthesize(self, text: str, lang: str = "hi") -> Optional[io.BytesIO]:
        """
        Convert text to speech audio (MP3).

        Args:
            text: The text to convert to speech.
            lang: Language code. 'hi' for Hindi (default), 'en' for English.

        Returns:
            BytesIO buffer containing MP3 audio, or None on failure.
        """
        if not self.available:
            logger.error("TTS synthesis requested but gTTS is not available")
            return None

        if not text or not text.strip():
            logger.warning("Empty text provided for TTS synthesis")
            return None

        # Strip allowed-markdown syntax tokens (**bold**, "- " bullets, "---")
        # so the listener doesn't hear "asterisk asterisk" or "dash". The
        # frontend renders these styled visually; audio gets the prose form.
        clean_text = _strip_markdown_for_tts(text).strip()
        if not clean_text:
            logger.warning("Text became empty after markdown stripping")
            return None

        try:
            # Use Hindi (hi) with Indian TLD for authentic accent
            # gTTS uses Google Translate TTS which provides a female Hindi voice
            logger.info(f"Synthesizing TTS: lang={lang}, tld=co.in, text_len={len(clean_text)}")
            tts = gTTS(
                text=clean_text,
                lang=lang,
                tld="co.in",  # Indian domain for Indian Hindi accent
                slow=False,
            )

            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            buffer.seek(0)

            logger.info(f"✅ TTS synthesized: {len(clean_text)} chars → {buffer.getbuffer().nbytes} bytes audio")
            return buffer

        except Exception as e:
            logger.exception(f"❌ TTS synthesis failed: {e}")
            return None


# Singleton
_tts_service: Optional[TTSService] = None


def get_tts_service() -> TTSService:
    global _tts_service
    if _tts_service is None:
        _tts_service = TTSService()
    return _tts_service
