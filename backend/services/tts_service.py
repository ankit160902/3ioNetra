"""
TTS Service - Text-to-Speech using gTTS with Hindi female voice
Optimized for reading Sanskrit/Hindi verses and spiritual content
"""

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    logger.warning("gTTS not available. TTS features will be disabled.")


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

        try:
            # Use Hindi (hi) with Indian TLD for authentic accent
            # gTTS uses Google Translate TTS which provides a female Hindi voice
            logger.info(f"Synthesizing TTS: lang={lang}, tld=co.in, text_len={len(text)}")
            tts = gTTS(
                text=text.strip(),
                lang=lang,
                tld="co.in",  # Indian domain for Indian Hindi accent
                slow=False,
            )

            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            buffer.seek(0)

            logger.info(f"✅ TTS synthesized: {len(text)} chars → {buffer.getbuffer().nbytes} bytes audio")
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
