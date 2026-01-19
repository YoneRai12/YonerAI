import logging

import edge_tts

logger = logging.getLogger(__name__)

class EdgeTTSClient:
    """Client for Microsoft Edge TTS."""

    def __init__(self, voice: str = "ja-JP-NanamiNeural") -> None:
        self.voice = voice

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes using Edge TTS."""
        communicate = edge_tts.Communicate(text, self.voice)
        
        # Edge TTS writes to a file or stream. We'll write to a temp file then read bytes.
        # Alternatively, we can iterate over the stream.
        
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
            elif chunk["type"] == "error":
                logger.error(f"EdgeTTS Error Chunk: {chunk}")
            else:
                logger.debug(f"EdgeTTS Other Chunk: {chunk}")
        
        if not audio_data:
            raise RuntimeError("Edge TTS returned no audio data.")
            
        return bytes(audio_data)
