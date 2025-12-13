"""Utilities for managing Discord voice connections, TTS playback, and STT hotword detection."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from collections import defaultdict
from typing import Awaitable, Callable, Dict, Optional, Any

import discord
# from discord.ext import voice_recv

from .stt_client import WhisperClient
from .tts_client import VoiceVoxClient
from .edge_tts_client import EdgeTTSClient
from .gtts_client import GTTSClient
import audioop

class VoiceConnectionError(Exception):
    """Raised when the bot fails to connect to a voice channel."""
    pass


logger = logging.getLogger(__name__)


HotwordCallback = Callable[[discord.Member, str], Awaitable[None]]


class HotwordListener:
    """Listens to PCM frames and detects the ORALLM hotword."""

    def __init__(self, stt_client: WhisperClient, loop: asyncio.AbstractEventLoop) -> None:
        self._stt = stt_client
        self._loop = loop
        self._buffers: Dict[int, bytearray] = defaultdict(bytearray)
        self._processing: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._callback: Optional[HotwordCallback] = None

    def set_callback(self, callback: HotwordCallback) -> None:
        self._callback = callback

    def feed(self, member: Optional[discord.Member], pcm: bytes) -> None:
        if member is None or not pcm:
            return
        buffer = self._buffers[member.id]
        buffer.extend(pcm)
        # Process roughly every ~2 seconds of audio (assuming 48kHz 16-bit stereo -> 192000 bytes/sec)
        if len(buffer) >= 384000:
            data = bytes(buffer)
            self._buffers[member.id].clear()
            self._buffers[member.id].clear()
            asyncio.run_coroutine_threadsafe(self._process(member, data), self._loop)

    async def _process(self, member: discord.Member, pcm: bytes) -> None:
        lock = self._processing[member.id]
        if lock.locked():
            return
        async with lock:
            # try:
            #     # Debug: Save audio to file to verify quality
            #     import wave
            #     with wave.open("debug_audio.wav", "wb") as wf:
            #         wf.setnchannels(2)
            #         wf.setsampwidth(2)
            #         wf.setframerate(48000)
            #         wf.writeframes(pcm)
                
            #     transcript = await self._stt.transcribe_pcm(pcm)
            # except Exception:
            #     logger.exception("音声認識に失敗しました")
            #     return

            # if not transcript:
            #     return

            # lower = transcript.lower()
            # key = "orallm"
            # if key not in lower:
            #     return

            # index = lower.index(key)
            # command = transcript[index + len(key) :].strip()
            # if not command:
            #     return

            # if self._callback:
            #     await self._callback(member, command)
            pass


class MixingAudioSource(discord.AudioSource):
    def __init__(self, main_source: discord.AudioSource, overlay_source: discord.AudioSource, target_volume: float = 0.2, fade_duration: float = 0.5) -> None:
        self.main = main_source
        self.overlay = overlay_source
        self.target_volume = target_volume
        self.current_volume = 1.0
        self.fade_duration = fade_duration
        self.overlay_finished = False
        self.fading_in = False
        # 20ms per frame (standard Discord audio)
        self.volume_step = (1.0 - target_volume) / (fade_duration / 0.02)

    def read(self) -> bytes:
        # Read from main
        main_data = self.main.read()
        # If main is done, we treat it as silence but we MUST continue if overlay is active
        if not main_data:
            main_data = b""

        # Read from overlay
        if not self.overlay_finished:
            overlay_data = self.overlay.read()
            if not overlay_data:
                self.overlay_finished = True
                self.fading_in = True
        else:
            overlay_data = b""

        # If both are done, return empty
        if not main_data and not overlay_data:
            return b""

        # Calculate Volume
        if not self.overlay_finished and not self.fading_in:
            # Fading Out (1.0 -> target)
            if self.current_volume > self.target_volume:
                self.current_volume = max(self.target_volume, self.current_volume - self.volume_step)
        elif self.fading_in:
            # Fading In (target -> 1.0)
            if self.current_volume < 1.0:
                self.current_volume = min(1.0, self.current_volume + self.volume_step)
            else:
                self.fading_in = False # Done fading in

        # Apply Volume to Main
        if main_data:
            try:
                # audioop.mul throws error if volume is 0? No, but let's be safe.
                main_adjusted = audioop.mul(main_data, 2, self.current_volume)
            except Exception:
                main_adjusted = main_data
        else:
            main_adjusted = b""

        # Mix if overlay exists
        if overlay_data:
            if main_adjusted:
                try:
                    return audioop.add(main_adjusted, overlay_data, 2)
                except Exception:
                    return main_adjusted
            else:
                return overlay_data
        
        return main_adjusted

    def cleanup(self) -> None:
        self.main.cleanup()
        self.overlay.cleanup()


class GuildMusicState:
    def __init__(self):
        self.queue = []  # List of (url_or_path, title, is_stream)
        self.is_looping = False
        self.current = None  # (url_or_path, title, is_stream)
        self.volume = 0.06
        self.voice_client: Optional[discord.VoiceClient] = None
        self.history = [] # List of (url_or_path, title, is_stream)

class VoiceManager:
    """Manages Discord voice clients for playback, recording, and music queue."""

    def __init__(self, bot: discord.Client, tts: VoiceVoxClient, stt: WhisperClient) -> None:
        self._bot = bot
        self._tts = tts
        self._stt = stt
        self._edge_tts = EdgeTTSClient()
        self._gtts = GTTSClient()
        self._music_states: Dict[int, GuildMusicState] = defaultdict(GuildMusicState)
        self._listener = HotwordListener(stt, bot.loop)
        self._user_speakers: Dict[int, int] = {}  # user_id -> speaker_id

    def get_music_state(self, guild_id: int) -> GuildMusicState:
        return self._music_states[guild_id]

    def set_hotword_callback(self, callback: HotwordCallback) -> None:
        self._listener.set_callback(callback)

    def set_user_speaker(self, user_id: int, speaker_id: int) -> None:
        """Set the preferred VoiceVox speaker ID for a user."""
        self._user_speakers[user_id] = speaker_id

    async def ensure_voice_client(self, member: discord.Member) -> Optional[discord.VoiceClient]:
        if member.voice is None or member.voice.channel is None:
            raise VoiceConnectionError("ユーザーがボイスチャンネルに参加していません。")

        channel = member.voice.channel
        guild = member.guild
        voice_client = guild.voice_client

        # Retry attempts for voice connection
        last_error = None
        for attempt in range(1, 4):
            try:
                # Force cleanup of zombies
                if attempt > 1 and voice_client and voice_client.is_connected():
                     await voice_client.disconnect(force=True)
                     voice_client = None

                if voice_client and voice_client.channel != channel:
                    await voice_client.move_to(channel)
                elif not voice_client or not voice_client.is_connected():
                    # IMPORTANT: self_deaf=True helps stability
                    try:
                        voice_client = await channel.connect(timeout=30.0, reconnect=True, self_deaf=True)
                    except discord.ClientException:
                        # Race condition: already connected
                        voice_client = guild.voice_client
                
                # Success
                self._music_states[guild.id].voice_client = voice_client
                return voice_client

            except asyncio.TimeoutError as e:
                logger.warning(f"Voice connection attempt {attempt}/3 timed out. Retrying...")
                last_error = e
                # Try to force disconnect if it exists
                if guild.voice_client:
                    try:
                        await guild.voice_client.disconnect(force=True)
                    except:
                        pass
                await asyncio.sleep(2)
                # Refresh voice client state
                voice_client = guild.voice_client
            except discord.ClientException as e:
                # Already connected?
                if guild.voice_client and guild.voice_client.is_connected():
                     voice_client = guild.voice_client
                     break
                else:
                    logger.error(f"Voice ClientException: {e}")
                    raise VoiceConnectionError(f"接続エラー (ClientException): {e}")
            except Exception as e:
                logger.exception(f"Unexpected voice error attempt {attempt}: {e}")
                last_error = e
                await asyncio.sleep(1)

        # If we get here, we failed
        logger.error("Failed to connect to voice after 3 attempts.")
        raise VoiceConnectionError(f"ボイスチャンネルへの接続に失敗しました (タイムアウト/エラー): {last_error}")

    async def play_tts(self, member: discord.Member, text: str) -> bool:
        if not text or not text.strip():
            return False
            
        # Clean and Truncate Text
        text = self.clean_for_tts(text)
        if not text:
            return False

        voice_client = await self.ensure_voice_client(member)
        # Relaxed check: If member isn't in VC, try to use existing bot connection in the guild
        if voice_client is None:
             if member.guild.voice_client and member.guild.voice_client.is_connected():
                 voice_client = member.guild.voice_client
             else:
                 return False

        # TTS should interrupt music? Or mix? For now, TTS plays over music if possible, 
        # but standard Discord bot behavior usually stops music for TTS or plays in parallel if using a specific library.
        # discord.py's VoiceClient only supports one source at a time.
        # So TTS will stop music. This is a limitation. 
        # To fix this properly requires mixing, which is complex.
        # For now, we will just play TTS and it might cut off music.
        # OR we can pause music?
        # Let's just play it. If music is playing, it will be stopped.
        
        try:
            speaker_id = self._user_speakers.get(member.id)
            audio = await self._tts.synthesize(text, speaker_id=speaker_id)
        except Exception as exc:
            logger.warning(f"VOICEVOX synthesis failed: {exc}. Falling back to Edge TTS.")
            try:
                audio = await self._edge_tts.synthesize(text)
            except Exception as edge_exc:
                logger.warning(f"Edge TTS also failed: {edge_exc}. Falling back to gTTS.")
                try:
                    audio = await self._gtts.synthesize(text)
                except Exception as gtts_exc:
                    logger.error(f"gTTS also failed: {gtts_exc}")
                    return False

        # Play TTS immediately
        # If music is playing, mix it!
        if voice_client.is_playing() and voice_client.source:
             # Wrap current source
             current_source = voice_client.source
             # We need to create a source for the TTS audio
             # _play_raw_audio logic needs to be adapted to return the source instead of playing it
             tts_source = self._create_source_from_bytes(audio)
             
             # Create mixed source
             mixed = MixingAudioSource(current_source, tts_source, target_volume=0.2, fade_duration=0.5)
             
             # Hotswap source (this is safe in discord.py as long as we do it atomically)
             voice_client.source = mixed
        else:
             await self._play_raw_audio(voice_client, audio)
        
        return True

    def _create_source_from_bytes(self, audio: bytes) -> discord.AudioSource:
        # Create a temporary file for the audio
        # Note: We need to keep the file alive while playing. 
        # FFmpegPCMAudio opens it.
        # We can use a custom cleanup to delete it.
        
        # For simplicity, we use the same tempfile logic but return the source
        f = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".wav")
        f.write(audio)
        f.close() # Close handle, let ffmpeg open by path
        path = f.name
        
        def cleanup():
            if os.path.exists(path):
                try:
                    os.remove(path)
                except: pass

        # We need a wrapper to call cleanup when done
        source = discord.FFmpegPCMAudio(path)
        # Monkey patch cleanup? Or create a wrapper class?
        # discord.py's FFmpegPCMAudio doesn't have a callback for cleanup on its own cleanup.
        # But we can override cleanup.
        original_cleanup = source.cleanup
        def new_cleanup():
            original_cleanup()
            cleanup()
        source.cleanup = new_cleanup
        return source

    async def _play_raw_audio(self, voice_client: discord.VoiceClient, audio: bytes) -> None:
        # Helper for TTS which uses raw bytes
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".wav") as tmp:
            tmp.write(audio)
            path = tmp.name
        
        def cleanup(error):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except: pass
            if error:
                logger.error(f"Player error: {error}")
            
            # Check if there is music in the queue for this guild
            if voice_client and voice_client.guild:
                 guild_id = voice_client.guild.id
                 # Schedule next song check
                 future = asyncio.run_coroutine_threadsafe(self._schedule_next(guild_id), self._bot.loop)
                 try:
                     future.result()
                 except: pass

        source = discord.FFmpegPCMAudio(path)
        if voice_client.is_playing():
            voice_client.stop()
        
        try:
            if not voice_client.is_connected():
                 logger.warning("Attempted to play audio on disconnected client.")
                 return

            voice_client.play(source, after=cleanup)
        except Exception as e:
            logger.error(f"Failed to play audio: {e}")
            # Ensure cleanup happens even if play fails
            cleanup(e)

    async def play_music(self, member: discord.Member, url_or_path: str, title: str, is_stream: bool) -> bool:
        """Add music to queue and start playing if idle."""
        voice_client = await self.ensure_voice_client(member)
        if not voice_client:
            return False

        state = self.get_music_state(member.guild.id)
        state.voice_client = voice_client
        
        # Add to queue
        state.queue.append((url_or_path, title, is_stream))
        
        if not voice_client.is_playing():
            self._play_next(member.guild.id)
            
        return True

    def _play_next(self, guild_id: int):
        state = self.get_music_state(guild_id)
        if not state.voice_client:
            return

        # Check if currently playing (e.g. TTS)
        if state.voice_client.is_playing():
            # If playing, wait and retry later
            asyncio.run_coroutine_threadsafe(self._schedule_next(guild_id), self._bot.loop)
            return

        # Determine next song
        if state.is_looping and state.current:
            # Replay current
            url_or_path, title, is_stream = state.current
        elif state.queue:
            # Save current to history before switching
            if state.current:
                state.history.insert(0, state.current)
                if len(state.history) > 20: # Limit history
                    state.history.pop()
            
            # Get next from queue
            url_or_path, title, is_stream = state.queue.pop(0)
            state.current = (url_or_path, title, is_stream)
        else:
            # Queue empty
            if state.current:
                state.history.insert(0, state.current)
                if len(state.history) > 20: 
                    state.history.pop()
            state.current = None
            return

        # Create Source
        try:
            if is_stream:
                # FFmpeg options for reconnection
                before_options = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                source = discord.FFmpegPCMAudio(url_or_path, before_options=before_options)
            else:
                source = discord.FFmpegPCMAudio(url_or_path)
                # Cleanup local file after playback
                original_cleanup = source.cleanup
                def cleanup():
                    original_cleanup()
                    if os.path.exists(url_or_path):
                        try:
                            os.remove(url_or_path)
                        except: pass
                source.cleanup = cleanup
            
            # Apply Volume
            source = discord.PCMVolumeTransformer(source, volume=state.volume)
            
            def after_callback(error):
                if error:
                    logger.error(f"Player error: {error}")
                # Schedule next song
                future = asyncio.run_coroutine_threadsafe(self._schedule_next(guild_id), self._bot.loop)
                try:
                    future.result()
                except: pass

            state.voice_client.play(source, after=after_callback)
            logger.info(f"Playing: {title} (Volume: {state.volume})")

        except Exception as e:
            logger.exception(f"Failed to play music: {e}")
            # Try next one
            self._play_next(guild_id)

    async def _schedule_next(self, guild_id: int):
        await asyncio.sleep(1) # Wait a bit
        self._play_next(guild_id)

    def stop_music(self, guild_id: int):
        state = self.get_music_state(guild_id)
        state.queue.clear()
        state.current = None
        state.is_looping = False
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()

    def skip_music(self, guild_id: int):
        state = self.get_music_state(guild_id)
        # Disable loop to ensure we skip to the next track
        state.is_looping = False
        
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop() # This triggers after_callback -> _play_next

    def replay_previous(self, guild_id: int) -> bool:
        """Play the last song from history."""
        state = self.get_music_state(guild_id)
        if not state.history:
            return False
        
        # Get last track
        last_track = state.history.pop(0)
        
        # If currently playing, we want to play this NOW.
        # So we push current to queue (front), push last_track to queue (front), then skip?
        # Or simpler: Push last_track to FRONT of queue, then skip current.
        
        # Wait, if we are playing song A. History has B.
        # User says "Play prev".
        # We want to play B.
        # Should A go to history? Yes, skip() handles that naturally via _play_next logic we just added?
        # Wait, our _play_next logic saves current to history ONLY if queue pop happens or queue empty.
        # If we skip, `stop()` triggers `_play_next`.
        # correct.
        
        state.queue.insert(0, last_track)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop() # Triggers _play_next which picks up the text track
        else:
            self._play_next(guild_id)
            
        return True

    def stop_playback(self, guild_id: int):
        """Stop current playback without clearing queue (for Barge-in)."""
        state = self.get_music_state(guild_id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.stop()

    def clean_for_tts(self, text: str) -> str:
        """Clean text for TTS (remove URLs, code blocks, etc.)."""
        import re
        # Remove Code Blocks
        text = re.sub(r"```[\s\S]*?```", "コードブロック", text)
        text = re.sub(r"`.*?`", "コード", text)
        # Remove URLs
        text = re.sub(r"https?://\S+", "URL省略", text)
        # Replace Custom Emojis with "絵文字"
        text = re.sub(r"<a?:\w+:\d+>", "絵文字", text)
        # Remove internal tags just in case
        text = re.sub(r"<\|.*?\|>", "", text)
        
        # Truncate to 60 chars
        if len(text) > 60:
            text = text[:60] + "以下略"
            
        return text.strip()

    def set_loop(self, guild_id: int, enabled: bool):
        state = self.get_music_state(guild_id)
        state.is_looping = enabled

    def get_queue_info(self, guild_id: int) -> dict:
        state = self.get_music_state(guild_id)
        return {
            "current": state.current[1] if state.current else None,
            "queue": [item[1] for item in state.queue],
            "is_looping": state.is_looping,
            "volume": state.volume
        }

    def _on_voice_frame(
        self,
        guild: discord.Guild,
        user: Optional[discord.User],
        data: Any, # voice_recv.VoiceData,
    ) -> None:
        if not isinstance(user, discord.Member):
            # Attempt to resolve user -> member
            if user is not None:
                member = guild.get_member(user.id)
            else:
                member = None
        else:
            member = user

        if member is None:
            return

        pcm = data.pcm or b""
        if not pcm:
            return

        self._listener.feed(member, pcm)
