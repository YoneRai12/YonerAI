import logging
import io
from gtts import gTTS
import asyncio

logger = logging.getLogger(__name__)

class GTTSClient:
    """Client for Google Translate TTS."""

    def __init__(self, lang: str = "ja") -> None:
        self.lang = lang

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes using gTTS."""
        def _synthesize():
            fp = io.BytesIO()
            tts = gTTS(text=text, lang=self.lang)
            tts.write_to_fp(fp)
            fp.seek(0)
            return fp.read()

        return await asyncio.to_thread(_synthesize)
