"""Speech-to-text client backed by OpenAI Whisper."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import numpy as np

try:
    import whisper
except ImportError:  # pragma: no cover - optional dependency
    whisper = None  # type: ignore

logger = logging.getLogger(__name__)


class WhisperClient:
    """Wrapper that transcribes PCM audio using Whisper."""

    def __init__(self, model: str = "tiny", *, language: Optional[str] = "ja") -> None:
        self._model_name = model
        self._language = language
        self._model: Optional["whisper.Whisper"] = None
        self._load_lock = asyncio.Lock()

    async def _ensure_model(self) -> "whisper.Whisper":
        if whisper is None:
            raise RuntimeError("openai-whisper がインストールされていません。")
        if self._model is not None:
            return self._model
        async with self._load_lock:
            if self._model is None:
                logger.info("Loading Whisper model %s", self._model_name)
                self._model = await asyncio.to_thread(whisper.load_model, self._model_name)
        return self._model

    async def transcribe_pcm(
        self,
        pcm_data: bytes,
        *,
        sample_rate: int = 48000,
        channels: int = 2,
    ) -> str:
        """Transcribe PCM audio to text using Whisper.

        This implementation is resilient to missing dependencies and runtime
        errors. If ``openai-whisper`` or ``numpy`` are not available, or if
        an error occurs during preprocessing or decoding, an empty string
        will be returned. This prevents the voice listener from crashing
        silently when speech recognition fails.
        """
        if not pcm_data:
            return ""
        # Attempt to ensure the Whisper model is loaded; if not available,
        # immediately return an empty string instead of raising an exception.
        try:
            model = await self._ensure_model()
        except Exception:
            logger.exception("Whisper model could not be loaded")
            return ""
        # Convert PCM bytes to float32 numpy array and normalise audio
        try:
            audio = np.frombuffer(pcm_data, np.int16).astype(np.float32)
            if channels > 1 and audio.size % channels == 0:
                # Reshape to (n_frames, n_channels) and take mean across channels
                audio = audio.reshape(-1, channels).mean(axis=1)
            # Avoid division by zero by providing initial parameter
            max_abs = np.max(np.abs(audio), initial=1.0)
            if max_abs > 0:
                audio = audio / max_abs
        except Exception:
            logger.exception("Failed to preprocess audio for Whisper")
            return ""
        # Perform decoding in a thread to avoid blocking the event loop
        def _decode(audio: np.ndarray) -> str:
            # Resample from 48kHz to 16kHz (simple decimation by 3)
            if sample_rate == 48000:
                audio = audio[::3]
            
            try:
                # Pad or trim to 30 seconds
                audio = whisper.pad_or_trim(audio)
                
                # Debug logging - using INFO to ensure visibility
                logger.info(f"Whisper input audio shape: {audio.shape}, dtype: {audio.dtype}, range: [{audio.min()}, {audio.max()}]")
                
                if audio.size == 0:
                    logger.warning("Whisper input audio is empty after resampling")
                    return ""
                
                if np.all(audio == 0):
                    logger.warning("Whisper input audio is all zeros (silence)")
                    return ""
                
                # Check for silence (RMS amplitude)
                rms = np.sqrt(np.mean(audio**2))
                # logger.info(f"Audio RMS: {rms:.5f}")
                if rms < 0.01:  # Adjust threshold as needed
                    logger.info(f"Skipping silence (RMS: {rms:.5f})")
                    return ""

                if np.isnan(audio).any() or np.isinf(audio).any():
                    logger.warning("Whisper input audio contains NaN or Inf")
                    return ""

                # Use model.transcribe which is more robust than manual decode
                # It handles padding, mel spectrogram, and decoding loop internally
                # We are already in a thread, so we can call this blocking function directly
                result = model.transcribe(
                    audio,
                    language=self._language,
                    fp16=False,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=False,
                    beam_size=1
                )
                return result["text"].strip()

            except RuntimeError as e:
                if "cannot reshape tensor of 0 elements" in str(e):
                    logger.warning(f"Whisper internal error (likely empty tokens): {e}")
                    return ""
                logger.exception(f"Whisper runtime error: {e}")
                return ""
            except Exception as e:
                logger.exception(f"Whisper decoding failed: {e}")
                return ""

        return await asyncio.to_thread(_decode, audio)
