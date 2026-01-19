"""VOICEVOX text-to-speech client."""

from __future__ import annotations

import logging

import aiohttp

logger = logging.getLogger(__name__)


class VoiceVoxClient:
    """Minimal VOICEVOX HTTP client that synthesises WAV audio from text."""

    def __init__(self, base_url: str, speaker_id: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._speaker_id = speaker_id

    async def synthesize(self, text: str, speaker_id: int = None, speed_scale: float = 1.0) -> bytes:
        """Synthesise ``text`` into WAV audio bytes."""

        if not text.strip():
            raise ValueError("読み上げ対象のテキストが空です。")

        sid = speaker_id if speaker_id is not None else self._speaker_id
        params = {"speaker": sid}
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            query_url = f"{self._base_url}/audio_query"
            # VOICEVOX expects 'text' and 'speaker' as query parameters
            query_params = {"text": text, "speaker": sid}
            async with session.post(query_url, params=query_params) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"VOICEVOX audio_query 失敗: {resp.status} {body}")
                query = await resp.json()

            # Apply Speed Scale
            # VOICEVOX query object has 'speedScale'
            original_speed = query.get("speedScale", 1.0)
            query["speedScale"] = original_speed * speed_scale

            # Debug log for query
            logger.debug(f"VOICEVOX query response: {query}")
            logger.info(f"VOICEVOX audio_query successful (Speed: {query['speedScale']})")

            synthesis_url = f"{self._base_url}/synthesis"
            async with session.post(synthesis_url, params=params, json=query) as resp2:
                if resp2.status != 200:
                    body = await resp2.text()
                    raise RuntimeError(f"VOICEVOX synthesis 失敗: {resp2.status} {body}")
                audio = await resp2.read()

        logger.debug("VOICEVOX synthesis completed (bytes=%d)", len(audio))
        return audio

    async def get_speakers(self) -> list[dict]:
        """Fetch available speakers from VoiceVox."""
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{self._base_url}/speakers"
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to fetch speakers: {resp.status}")
                    return []
                return await resp.json()
