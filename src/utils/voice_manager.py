"""Utilities for managing Discord voice connections, TTS playback, and STT hotword detection."""

from __future__ import annotations

import asyncio
import audioop
import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional

import discord

from ..config import STATE_DIR
from .edge_tts_client import EdgeTTSClient
from .gtts_client import GTTSClient

# from discord.ext import voice_recv
from .stt_client import WhisperClient
from .t5_tts_client import T5TTSClient
from .tts_client import VoiceVoxClient


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
    def __init__(self, main_source: discord.AudioSource, overlay_source: discord.AudioSource, target_volume: float = 0.2, fade_duration: float = 0.5, on_finish: Optional[Callable[[], None]] = None) -> None:
        self.main = main_source
        self.overlay = overlay_source
        self.target_volume = target_volume
        self.current_volume = 1.0
        self.fade_duration = fade_duration
        self.overlay_finished = False
        self.fading_in = False
        self.on_finish = on_finish
        self.callback_fired = False
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
                # Trigger callback once
                if self.on_finish and not self.callback_fired:
                    self.callback_fired = True
                    # Execute callback (might need to be non-blocking or just standard func)
                    try:
                        self.on_finish()
                    except Exception as e:
                        logger.error(f"MixingAudioSource callback error: {e}")
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
                    # audioop.add requires same length
                    len_main = len(main_adjusted)
                    len_overlay = len(overlay_data)
                    
                    if len_main == len_overlay:
                        return audioop.add(main_adjusted, overlay_data, 2)
                    elif len_main > len_overlay:
                        # Pad overlay with silence
                        padding = b"\x00" * (len_main - len_overlay)
                        return audioop.add(main_adjusted, overlay_data + padding, 2)
                    else:
                        # Pad main with silence (should rare for standard 20ms frames)
                        padding = b"\x00" * (len_overlay - len_main)
                        return audioop.add(main_adjusted + padding, overlay_data, 2)
                except Exception as e:
                    logger.error(f"Mixing failed: {e}")
                    return main_adjusted
            else:
                return overlay_data
        
        return main_adjusted

    def cleanup(self) -> None:
        self.main.cleanup()
        self.overlay.cleanup()


class GuildMusicState:
    def __init__(self):
        self.queue = []  # List of (url_or_path, title, is_stream, duration)
        self.is_looping = False
        self.current = None  # (url_or_path, title, is_stream, duration)
        self.current_start_time = 0.0 # Unix timestamp
        self.current_track_duration = 0.0 # Saved duration for current track
        self.volume = 0.15 # Default volume boosted from 0.06
        self.voice_client: Optional[discord.VoiceClient] = None
        self.history = [] # List of (url_or_path, title, is_stream)
        self.tts_volume = 1.0 # Default TTS volume (100%)
        # TTS Queue
        self.tts_queue = [] # List of (member, text, speed, model_type, cache_key, msg_type)
        self.tts_processing = False
        self.speed = 1.0
        self.pitch = 1.0
        self.start_offset = 0.0
        self.current_tts_type: str = "chat" # Track current playback type for Anti-Spam

# ... (VoiceManager methods) ...

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
            url_or_path, title, is_stream, duration = state.current
        elif state.queue:
            # Save current to history before switching
            if state.current:
                state.history.insert(0, state.current)
                if len(state.history) > 20: # Limit history
                    state.history.pop()
            
            # Get next from queue
            url_or_path, title, is_stream, duration = state.queue.pop(0)
            state.current = (url_or_path, title, is_stream, duration)
            state.current_track_duration = duration if duration else 0.0
        else:
            # Queue empty
            if state.current:
                state.history.insert(0, state.current)
                if len(state.history) > 20: 
                    state.history.pop()
            state.current = None
            state.current_start_time = 0.0
            return

        # Create Source
        try:
            # FFmpeg Filters Calculation
            filters = []
            
            # 1. Speed (atempo)
            # FFmpeg `atempo` is limited to 0.5 - 2.0 per instance. Chain them for larger values.
            # We will cap it for safety between 0.5 and 2.0 for now, or implement chaining if needed.
            # actually we can chain: "atempo=2.0,atempo=1.5"
            current_speed = state.speed
            if abs(current_speed - 1.0) > 0.01:
                 # Limitation hack: just support 0.5-2.0 for now to keep code simple
                 current_speed = max(0.5, min(2.0, current_speed))
                 filters.append(f"atempo={current_speed}")

            # 2. Pitch (asetrate)
            if state.pitch != 1.0:
                # asetrate = 48000 * pitch
                # aresample = 48000 (resample back to 48k)
                # But this changes speed too by factor 'pitch'.
                # To keep speed at 'speed', we need to adjust temp:
                # final_speed = speed
                # pitch_speed_change = pitch
                # required_tempo_change = speed / pitch
                
                # Filters
                filters.append("aresample=48000")
                filters.append(f"asetrate={48000 * state.pitch}")
                filters.append("aresample=48000")
                
                # Adjust tempo compensation
                tempo_comp = state.speed / state.pitch
                if abs(tempo_comp - 1.0) > 0.01:
                    filters.append(f"atempo={tempo_comp}")
            
            ffmpeg_opts = {
                "before_options": "",
                "options": "-vn"
            }
            
            if is_stream:
                ffmpeg_opts["before_options"] += " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            
            # Apply filters
            if filters:
                 ffmpeg_opts["options"] += f' -filter:a "{",".join(filters)}"'
            
            # Apply Seek / Start Offset
            if state.start_offset > 0:
                ffmpeg_opts["before_options"] += f" -ss {state.start_offset}"
                state.current_start_time = time.time() - state.start_offset
                state.start_offset = 0.0 # Reset
            else:
                state.current_start_time = time.time()
                
            source = discord.FFmpegPCMAudio(url_or_path, **ffmpeg_opts)
            
            if not is_stream:
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
            import time
            state.current_start_time = time.time()
            logger.info(f"Playing: {title} (Volume: {state.volume})")
            
            # Notifying dashboard update? 
            # Ideally VoiceManager emits an event, but MediaCog handles updates.

        except Exception as e:
            logger.exception(f"Failed to play music: {e}")
            # Try next one
            self._play_next(guild_id)

class VoiceManager:
    """Manages Discord voice clients for playback, recording, and music queue."""

    def __init__(self, bot: discord.Client, tts: VoiceVoxClient, stt: WhisperClient) -> None:
        self._bot = bot
        self._tts = tts
        self._stt = stt
        self._edge_tts = EdgeTTSClient()
        self._gtts = GTTSClient()
        t5_local_path = r"L:\ai_models\huggingface\Aratako_T5Gemma-TTS-2b-2b"
        if os.path.exists(os.path.join(t5_local_path, "config.json")):
             logger.info(f"Using Local T5Gemma Model: {t5_local_path}")
             self._t5_tts = T5TTSClient(t5_local_path)
        else:
             self._t5_tts = T5TTSClient("Aratako/T5Gemma-TTS-2b-2b") # High Quality T5
        self._music_states: Dict[int, GuildMusicState] = defaultdict(GuildMusicState)
        self._listener = HotwordListener(stt, bot.loop)
        self._user_speakers: Dict[int, int] = {}  # user_id -> speaker_id
        self._guild_speakers: Dict[int, int] = {} # guild_id -> speaker_id
        self.state_path = Path(STATE_DIR) / "user_voices.json"
        self.guild_state_path = Path(STATE_DIR) / "guild_voices.json"
        self.load_speakers()
        self.load_guild_speakers()

        # Persist auto-read channels here so they survive MediaCog reloads
        self.auto_read_channels: Dict[int, int] = {}  # guild_id -> channel_id
        self.has_warned_voicevox = False

        # Audio Cache for static notifications (join/leave)
        self.cache_dir = Path("src/data/cache/audio_notify")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_music_state(self, guild_id: int) -> GuildMusicState:
        return self._music_states[guild_id]

    def set_hotword_callback(self, callback: HotwordCallback) -> None:
        self._listener.set_callback(callback)

    def load_speakers(self):
        """Load speaker preferences from JSON."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Convert keys to int (JSON keys are strings)
                    self._user_speakers = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(self._user_speakers)} user voice preferences.")
            except Exception as e:
                logger.error(f"Failed to load user voices: {e}")

    def save_speakers(self):
        """Save speaker preferences to JSON."""
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self._user_speakers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save user voices: {e}")

    def load_guild_speakers(self):
        """Load guild speaker preferences from JSON."""
        if self.guild_state_path.exists():
            try:
                with open(self.guild_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._guild_speakers = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(self._guild_speakers)} guild voice preferences.")
            except Exception as e:
                logger.error(f"Failed to load guild voices: {e}")

    def save_guild_speakers(self):
        """Save guild speaker preferences to JSON."""
        try:
            self.guild_state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.guild_state_path, "w", encoding="utf-8") as f:
                json.dump(self._guild_speakers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save guild voices: {e}")

    async def get_speakers(self) -> list[dict]:
        """Fetch available speakers from VoiceVox Engine."""
        return await self._tts.get_speakers()

    def set_user_speaker(self, user_id: int, speaker_id: int) -> None:
        """Set the preferred VoiceVox speaker ID for a user."""
        self._user_speakers[user_id] = speaker_id
        self.save_speakers()

    def set_guild_speaker(self, guild_id: int, speaker_id: int) -> None:
        """Set the preferred VoiceVox speaker ID for a guild."""
        self._guild_speakers[guild_id] = speaker_id
        self.save_guild_speakers()

    async def search_speaker(self, query: str) -> Optional[dict]:
        """Search for a speaker by name (fuzzy match)."""
        query = query.lower().strip()

        # Virtual Speaker: T5Gemma
        if any(w in query for w in ["t5", "gemma", "high quality", "高音質", "human", "人間", "real", "リアル", "person"]):
            return {"name": "T5Gemma (High Quality)", "style": "Generative", "id": -1}

        speakers = await self.get_speakers()
        if not speakers:
             return None
        
        best_match = None
        # ... logic continues ...
        
        for sp in speakers:
            name = sp.get("name", "").lower()
            # Exact match
            if name == query:
                return {"id": sp["styles"][0]["id"], "name": sp["name"], "style": sp["styles"][0]["name"]}
            
            # Partial match
            if query in name:
                # Prefer exact contained matches or first found
                if not best_match:
                     best_match = {"id": sp["styles"][0]["id"], "name": sp["name"], "style": sp["styles"][0]["name"]}
        
        return best_match

    async def ensure_voice_client(self, member: discord.Member, allow_move: bool = True) -> Optional[discord.VoiceClient]:
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
                    if allow_move:
                        # Automatically move to the user's channel
                        logger.info(f"Moving voice client from {voice_client.channel.name} to {channel.name}")
                        await voice_client.move_to(channel)
                    else:
                        # If move not allowed, return existing client (even if wrong channel)
                        # The caller (play_tts) implies this is fine (user moved away but bot stays)
                        logger.info(f"User is in {channel.name} but bot stays in {voice_client.channel.name} (allow_move=False)")
                        pass

                elif not voice_client or not voice_client.is_connected():
                    # IMPORTANT: self_deaf=True helps stability
                    try:
                        voice_client = await channel.connect(timeout=30.0, reconnect=True, self_deaf=False)
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

    async def play_tts(self, member: discord.Member, text: str, speed: float = 1.0, model_type: str = "standard", cache_key: str = None, msg_type: str = "chat") -> bool:
        if not text or not text.strip():
            return False
            
        # Clean and Truncate Text
        text = self.clean_for_tts(text)
        if not text:
            return False

        try:
            # 2. Relaxed Connection Logic
            voice_client = None
            if member.voice and member.voice.channel:
                 try:
                     voice_client = await self.ensure_voice_client(member, allow_move=False)
                 except VoiceConnectionError:
                     pass
            
            if not voice_client:
                 if member.guild.voice_client and member.guild.voice_client.is_connected():
                     voice_client = member.guild.voice_client
                 else:
                     return False
                     
            # 3. Add to Queue with Anti-Spam (Debounce)
            state = self.get_music_state(member.guild.id)

            if msg_type == "system_join_leave":
                # DEBOUNCE: Remove pending join/leave messages from THIS member to prevent pile-up.
                # Only keep the newest one (which we are about to add).
                # Queue item structure: (member, text, speed, model_type, cache_key, msg_type)
                new_queue = []
                for item in state.tts_queue:
                    # Backward compatibility check
                    if len(item) == 6:
                        (m, t, s, mt, ck, mtype) = item
                        if m.id == member.id and mtype == "system_join_leave":
                            logger.info(f"🚫 [Anti-Spam] Dropped pending Join/Leave msg for {member.display_name}")
                            continue
                    new_queue.append(item)
                state.tts_queue = new_queue

                # CANCEL CURRENT: If currently reading a Join/Leave message, stop it immediately.
                # We need to track what is currently playing.
                if state.current_tts_type == "system_join_leave":
                     if voice_client.is_playing():
                         logger.info("🚫 [Anti-Spam] Stopping current Join/Leave reading for new event.")
                         voice_client.stop() # This triggers after_callback -> next item

            state.tts_queue.append((member, text, speed, model_type, cache_key, msg_type))
            
            # 4. Trigger Processing if Idle
            if not state.tts_processing:
                await self._process_tts_queue(member.guild.id)
                
            return True
        except Exception as e:
            logger.error(f"play_tts error: {e}")
            return False

    async def _process_tts_queue(self, guild_id: int):
        state = self.get_music_state(guild_id)
        if not state.tts_queue:
            state.tts_processing = False
            return
            
        state.tts_processing = True
        
        # Pop next item
        item = state.tts_queue.pop(0)
        
        # Validate Queue Item
        # Support variable length for backward compatibility
        model_type = "standard"
        cache_key = None
        msg_type = "chat"
        
        if len(item) == 6:
             member, text, speed, model_type, cache_key, msg_type = item
        elif len(item) == 5:
             member, text, speed, model_type, cache_key = item
        elif len(item) == 4:
             member, text, speed, model_type = item
        elif len(item) == 3:
             member, text, speed = item
        else:
             member, text = item
             speed = 1.0
        
        # Track Current Type
        state.current_tts_type = msg_type

        # -- Resolve Speaker Preference (User > Guild > Default) --
        # We check preferences here to potentially override the model_type
        # e.g., if user selected "T5Gemma" (id=-1), we force t5 mode.
        speaker_id = self._user_speakers.get(member.id)
        if speaker_id is None:
            speaker_id = self._guild_speakers.get(member.guild.id)
        
        # Virtual ID Check
        if speaker_id == -1:
            model_type = "t5"

        try:
            audio = None
            
            # [CACHE CHECK]
            if cache_key:
                cache_file = self.cache_dir / f"{cache_key}.mp3"
                if cache_file.exists():
                    logger.info(f"Using cached audio for {cache_key}")
                    try:
                        with open(cache_file, "rb") as f:
                            audio = f.read()
                    except Exception as e:
                        logger.error(f"Failed to read cache {cache_key}: {e}")
            
            if not audio:
                # Generate Audio
                if model_type == "t5":
                     # T5Gemma Exclusive Mode
                     try:
                         audio = await self._t5_tts.synthesize(text, speed_scale=speed)
                     except Exception as e:
                         logger.error(f"T5Gemma synthesis failed: {e}")
                         logger.warning("Falling back to EdgeTTS for T5 request.")
                         audio = await self._edge_tts.synthesize(text)
                else:
                    # Standard Mode
                    try:
                        audio = await self._tts.synthesize(text, speaker_id=speaker_id, speed_scale=speed)
                    except Exception as vv_exc:
                         if not self.has_warned_voicevox:
                             logger.warning(f"VoiceVox synthesis failed: {vv_exc}. Falling back to EdgeTTS.")
                             self.has_warned_voicevox = True
                         try:
                             audio = await self._edge_tts.synthesize(text)
                         except Exception as edge_exc:
                             logger.warning(f"Edge TTS failed: {edge_exc}. Falling back to gTTS.")
                             try:
                                 audio = await self._gtts.synthesize(text)
                             except Exception as gtts_exc:
                                 logger.error(f"All Standard TTS engines failed: {gtts_exc}")
                                 state.tts_processing = False
                                 return

                # [CACHE SAVE]
                if cache_key and audio:
                    try:
                        cache_file = self.cache_dir / f"{cache_key}.mp3"
                        with open(cache_file, "wb") as f:
                            f.write(audio)
                        logger.info(f"Saved cache for {cache_key}")
                    except Exception as e:
                        logger.error(f"Failed to save cache {cache_key}: {e}")


        except Exception as e:
            logger.error(f"TTS Synthesis Critical Error: {e}")
            state.tts_processing = False
            return

        # Get Voice Client
        voice_client = state.voice_client
        if not voice_client or not voice_client.is_connected():
            state.tts_processing = False
            return

        # Prepare Callback
        def on_complete(error=None):
            if error:
                logger.error(f"TTS Playback Error: {error}")
            # Schedule next item
            future = asyncio.run_coroutine_threadsafe(self._process_tts_queue(guild_id), self._bot.loop)
            try:
                future.result()
            except: pass

        try:
            # Create Source
            tts_source = self._create_source_from_bytes(audio)
            tts_source = discord.PCMVolumeTransformer(tts_source, volume=state.tts_volume)
            
            if voice_client.is_playing() and voice_client.source:
                # Mixing Mode (Music is playing)
                logger.info("Mixing TTS with active music (Ducking to 50%)")
                current_source = voice_client.source
                
                # Create mixed source with callback
                mixed = MixingAudioSource(
                    current_source, 
                    tts_source, 
                    target_volume=0.5, 
                    fade_duration=0.5,
                    on_finish=lambda: on_complete() # Lambda to allow no-arg call
                )
                
                # Hotswap
                voice_client.source = mixed
                logger.info("Swapped audio source to Mixed source.")
            else:
                # Raw Mode (No music)
                logger.info("Playing TTS in Raw mode (No music)")
                # We reuse _play_raw_audio logic but with custom callback?
                voice_client.play(tts_source, after=on_complete)
                
        except Exception as e:
            logger.error(f"Failed to play TTS: {e}")
            # Ensure we don't stall queue
            on_complete(e)

    def _create_source_from_bytes(self, audio: bytes) -> discord.AudioSource:
        # Create a temporary file for the audio
        # Note: We need to keep the file alive while playing. 
        # FFmpegPCMAudio opens it.
        # We can use a custom cleanup to delete it.
        
        # For simplicity, we use the same tempfile logic but return the source
        f = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".mp3")
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
        
        # Apply Volume
        if voice_client.guild:
            state = self.get_music_state(voice_client.guild.id)
            source = discord.PCMVolumeTransformer(source, volume=state.tts_volume)

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

    async def play_music(self, member: discord.Member, url_or_path: str, title: str, is_stream: bool, duration: float = 0.0) -> bool:
        """Add music to queue and start playing if idle."""
        voice_client = await self.ensure_voice_client(member)
        if not voice_client:
            return False

        state = self.get_music_state(member.guild.id)
        state.voice_client = voice_client
        
        # Add to queue
        state.queue.append((url_or_path, title, is_stream, duration))
        
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
            url_or_path, title, is_stream, duration = state.current
            state.current_track_duration = duration if duration else 0.0
        elif state.queue:
            # Save current to history before switching
            if state.current:
                state.history.insert(0, state.current)
                if len(state.history) > 20: # Limit history
                    state.history.pop()
            
            # Get next from queue
            url_or_path, title, is_stream, duration = state.queue.pop(0)
            state.current = (url_or_path, title, is_stream, duration)
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

        return text.strip()

    def clean_for_tts(self, text: str) -> str:
        """Clean text for TTS (remove URLs, code blocks, and parentheses)."""
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
        
        # Remove content inside parentheses (Half-width and Full-width)
        # Non-greedy match to avoid eating entire sentences if multiple parens exist
        text = re.sub(r"\(.*?\)", "", text)
        text = re.sub(r"（.*?）", "", text)
        
        # Remove Hyphens and Whitespace (Half/Full width)
        # Requested by user to stop reading "minus" or "space"
        text = re.sub(r"[-−\s　]", "", text)
        
        # Truncate to 60 chars
        if len(text) > 60:
            text = text[:60] + "以下略"
            
        return text.strip()

    def set_loop(self, guild_id: int, enabled: bool):
        state = self.get_music_state(guild_id)
        state.is_looping = enabled

    def set_speed_pitch(self, guild_id: int, speed: float, pitch: float):
        state = self.get_music_state(guild_id)
        
        # Calculate current position before updating state
        current_pos = 0.0
        if state.voice_client and state.voice_client.is_playing() and state.current_start_time > 0:
             import time
             elapsed_real = time.time() - state.current_start_time
             # Adjusted for previous speed?
             # If we were playing at x2.0 for 10s, we are at 20s mark in file.
             # So elapsed_file = elapsed_real * state.speed
             current_pos = elapsed_real * state.speed
             
        state.speed = speed
        state.pitch = pitch
        
        # Restart current track to apply effects
        if state.current and state.voice_client and state.voice_client.is_playing():
             # Resume from current position
             state.start_offset = current_pos
             
             # Re-queue current to front
             state.queue.insert(0, state.current)
             state.current = None
             state.voice_client.stop()

    def seek_music(self, guild_id: int, seconds: float):
        state = self.get_music_state(guild_id)
        if not state.current:
            return
            
        state.start_offset = max(0.0, seconds)
        
        # Push current back to queue to be picked up by _play_next
        state.queue.insert(0, state.current)
        state.current = None # Reset current so _play_next picks from queue
        
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()
        else:
            # If not playing, force start?
            # _play_next called by stop() callback usually.
            pass

    def toggle_loop(self, guild_id: int) -> bool:
        """Toggle loop mode and return new state."""
        state = self.get_music_state(guild_id)
        state.is_looping = not state.is_looping
        return state.is_looping

    def stop_player(self, guild_id: int):
        """Alias for stop_music."""
        self.stop_music(guild_id)

    def skip_track(self, guild_id: int):
        """Alias for skip_music."""
        self.skip_music(guild_id)

    def shuffle_queue(self, guild_id: int):
        """Shuffle the current queue."""
        import random
        state = self.get_music_state(guild_id)
        if state.queue:
            random.shuffle(state.queue)

    def get_queue_info(self, guild_id: int) -> dict:
        state = self.get_music_state(guild_id)
        current_title = state.current[1] if state.current else None
        # Prefer the explicitly stored duration, fallback to tuple extraction
        current_duration = state.current_track_duration
        if current_duration == 0.0 and state.current and len(state.current) > 3:
             current_duration = state.current[3]
        
        # Safe access for duration in queue
        queue_list = []
        for item in state.queue:
             # item is (url, title, stream, duration)
             queue_list.append({"title": item[1], "duration": item[3] if len(item)>3 else 0.0})

        return {
            "current": current_title,
            "current_duration": current_duration, 
            "queue": queue_list, # List of dicts
            "is_looping": state.is_looping,
            "current_start_time": state.current_start_time,
            "volume": state.volume,
            "tts_volume": state.tts_volume,
            "speed": state.speed,
            "pitch": state.pitch
        }

    def set_speed_pitch(self, guild_id: int, speed: float = 1.0, pitch: float = 1.0):
        """Set speed/pitch and restart current track at approximate position."""
        state = self.get_music_state(guild_id)
        
        # Clamp values for safety
        speed = max(0.5, min(2.0, speed))
        pitch = max(0.5, min(2.0, pitch))
        
        state.speed = speed
        state.pitch = pitch
        
        # Apply immediately if playing
        if state.voice_client and state.voice_client.is_playing() and state.current:
            # We need to seek to current position?
            # Calculating current position is hard because speed changes heavily affect it.
            # Assuming simple restart for now is safer, OR we try to estimate.
            
            import time
            elapsed = time.time() - state.current_start_time
            # Apply previous speed factor to get "Real" audio time elapsed?
            # Too complex. Let's just restart the track with new settings (User knows "Tune" might reset)
            # OR we implement 'ss' option?
            
            # Let's try to 'seek' if possible.
            # If it's a stream, we can't really seek easily without restarting stream.
            
            # RESTART STRATEGY:
            # 1. Stop current (which triggers _play_next)
            # 2. _play_next sees state.current.
            # 3. But wait, `stop()` usually clears `state.current` or `_play_next` advances queue?
            # Check `_play_next` logic:
            # `if state.is_looping and state.current:` -> Replays.
            # Else pops from Queue.
            
            # If we want to restart CURRENT track, we must ensure it stays as `state.current` 
            # AND `_play_next` decides to play `state.current` again instead of popping.
            
            # HACK: Push current back to front of queue?
            # state.queue.insert(0, state.current)
            # state.voice_client.stop() 
            # -> `stop` triggers `after` -> `_play_next` -> pops from queue (which is our track).
            
            # But wait, `_play_next` logic at line 208:
            # `elif state.queue:` -> Pops.
            
            # So yes, pushing to front of queue works.
            
            if state.current:
                state.queue.insert(0, state.current)
                # Force stop to trigger next
                state.voice_client.stop()


    def set_music_volume(self, guild_id: int, volume: float):
        """Set music volume (0.0 to 2.0)."""
        state = self.get_music_state(guild_id)
        state.volume = max(0.0, min(2.0, volume))
        # Update current playback if possible
        if state.voice_client and state.voice_client.source:
            # Check if source is transformer or Mixed
            source = state.voice_client.source
            if isinstance(source, discord.PCMVolumeTransformer):
                source.volume = state.volume
            elif isinstance(source, MixingAudioSource):
                # If mixed, music is 'main'
                if isinstance(source.main, discord.PCMVolumeTransformer):
                    source.main.volume = state.volume

    def set_tts_volume(self, guild_id: int, volume: float):
        """Set TTS volume (0.0 to 2.0)."""
        state = self.get_music_state(guild_id)
        state.tts_volume = max(0.0, min(2.0, volume))
        # Update current playback if possible
        if state.voice_client and state.voice_client.source:
             source = state.voice_client.source
             # If pure TTS (via _play_raw_audio wrapped)
             if isinstance(source, discord.PCMVolumeTransformer) and not isinstance(source, MixingAudioSource):
                 # Limitation: We don't know if current transformer is Music or TTS just by type.
                 # But usually Music is playing. TTS is short.
                 # If TTS is playing alone, we can update it.
                 # But risk: Music might be playing and we stick TTS volume to it.
                 # Practical fix: TTS is short, so immediate update is less critical than Music.
                 pass

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
            url_or_path, title, is_stream, duration = state.current
        elif state.queue:
            # Save current to history before switching
            if state.current:
                state.history.insert(0, state.current)
                if len(state.history) > 20: # Limit history
                    state.history.pop()
            
            # Get next from queue
            url_or_path, title, is_stream, duration = state.queue.pop(0)
            state.current = (url_or_path, title, is_stream, duration)
            state.current_track_duration = duration if duration else 0.0
        else:
            # Queue empty
            if state.current:
                state.history.insert(0, state.current)
                if len(state.history) > 20: 
                    state.history.pop()
            state.current = None
            state.current_start_time = 0.0
            return

        # Create Source
        try:
            # FFmpeg Filters Calculation
            filters = []
            
            # 1. Speed (atempo)
            # FFmpeg `atempo` is limited to 0.5 - 2.0 per instance. Chain them for larger values.
            # We will cap it for safety between 0.5 and 2.0 for now, or implement chaining if needed.
            # actually we can chain: "atempo=2.0,atempo=1.5"
            current_speed = state.speed
            if abs(current_speed - 1.0) > 0.01:
                 # Limitation hack: just support 0.5-2.0 for now to keep code simple
                 current_speed = max(0.5, min(2.0, current_speed))
                 filters.append(f"atempo={current_speed}")

            # 2. Pitch (asetrate)
            if state.pitch != 1.0:
                # asetrate = 48000 * pitch
                # aresample = 48000 (resample back to 48k)
                # But this changes speed too by factor 'pitch'.
                # To keep speed at 'speed', we need to adjust temp:
                # final_speed = speed
                # pitch_speed_change = pitch
                # required_tempo_change = speed / pitch
                
                # Filters
                filters.append("aresample=48000")
                filters.append(f"asetrate={48000 * state.pitch}")
                filters.append("aresample=48000")
                
                # Adjust tempo compensation
                tempo_comp = state.speed / state.pitch
                if abs(tempo_comp - 1.0) > 0.01:
                    filters.append(f"atempo={tempo_comp}")
            
            ffmpeg_opts = {
                "before_options": "",
                "options": "-vn"
            }
            
            if is_stream:
                ffmpeg_opts["before_options"] += " -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            
            # Apply filters
            if filters:
                 ffmpeg_opts["options"] += f' -filter:a "{",".join(filters)}"'
            
            # Apply Seek / Start Offset
            if state.start_offset > 0:
                ffmpeg_opts["before_options"] += f" -ss {state.start_offset}"
                state.current_start_time = time.time() - state.start_offset
                state.start_offset = 0.0 # Reset
            else:
                state.current_start_time = time.time()
                
            source = discord.FFmpegPCMAudio(url_or_path, **ffmpeg_opts)
            
            if not is_stream:
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
            state.current_start_time = time.time()
            logger.info(f"Playing: {title} (Volume: {state.volume})")
            
            # Notifying dashboard update? 
            # Ideally VoiceManager emits an event, but MediaCog handles updates.

        except Exception as e:
            logger.exception(f"Failed to play music: {e}")
            # Try next one
            self._play_next(guild_id)
