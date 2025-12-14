import asyncio
import logging
import time
import io
import wave
import discord
from discord.ext import commands, voice_recv
from discord import app_commands
import numpy as np

logger = logging.getLogger(__name__)

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("openai-whisper not installed. Voice recognition will be disabled.")

from collections import defaultdict

class UserVoiceBuffer:
    def __init__(self):
        self.buffer = bytearray()
        self.last_packet_time = time.time()
        self.speaking = False
        self.speaking_frames = 0
        self.last_stop_time = 0

class VoiceSink(voice_recv.AudioSink):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
        self.user_data = defaultdict(UserVoiceBuffer)
        self.sample_rate = 48000
        self.channels = 2 # Discord sends stereo
        self.sample_width = 2 # 16-bit PCM
        self.conversation_mode = False

    def wants_opus(self) -> bool:
        return False

    def write(self, user: discord.User, data: voice_recv.VoiceData):
        if user is None:
            return

        ud = self.user_data[user.id]
        ud.last_packet_time = time.time()
        ud.buffer.extend(data.pcm)
        
        # Barge-in Logic
        ud.speaking_frames += 1
        
        # Threshold: 5 frames (~100ms)
        if ud.speaking_frames >= 5:
            if not ud.speaking:
                ud.speaking = True
                logger.info(f"User {user.name} started speaking.")
                
                # Trigger Barge-in (Stop TTS)
                # Check cooldown (500ms)
                if time.time() - ud.last_stop_time > 0.5:
                    media_cog = self.cog.bot.get_cog("MediaCog")
                    if media_cog:
                        # Stop playback
                        media_cog._voice_manager.stop_playback(user.guild.id)
                        ud.last_stop_time = time.time()
                        logger.info("Barge-in triggered: Stopped playback.")

    def cleanup(self):
        pass

class VoiceRecvCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.model = None
        self.active_sinks = {} # guild_id -> VoiceSink
        self.processing_tasks = {} # guild_id -> Task

        if WHISPER_AVAILABLE:
            try:
                # Try loading on GPU first
                logger.info("Loading Whisper model (small) on GPU...")
                self.model = whisper.load_model("small")
                logger.info("Whisper model loaded on GPU.")
            except Exception as e:
                logger.warning(f"Failed to load Whisper on GPU: {e}")
                logger.info("Falling back to CPU (small model)...")
                self.model = whisper.load_model("small", device="cpu")
                logger.info("Whisper model loaded on CPU.")
            
            # Suppress RTCP spam from voice_recv
            logging.getLogger("discord.ext.voice_recv").setLevel(logging.WARNING)

    @app_commands.command(name="listen", description="ボイスチャンネルで全員の声を聞き取ります。")
    async def listen(self, interaction: discord.Interaction):
        # Admin check
        # if self.bot.config.admin_user_id and interaction.user.id != self.bot.config.admin_user_id:
        #     await interaction.response.send_message("この機能は管理者専用です。", ephemeral=True)
        #     return

        if not interaction.user.voice:
            await interaction.response.send_message("ボイスチャンネルに参加してから実行してください。", ephemeral=True)
            return

        if not WHISPER_AVAILABLE:
            await interaction.response.send_message("Whisperがインストールされていないため、この機能は使用できません。", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        vc = interaction.guild.voice_client
        if not vc:
            try:
                # Connect with voice_recv capability
                vc = await interaction.user.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
            except Exception as e:
                await interaction.followup.send(f"接続に失敗しました: {e}")
                return
        else:
            if not isinstance(vc, voice_recv.VoiceRecvClient):
                await interaction.followup.send("既に通常の接続がされています。一度切断してから再実行してください。")
                return

        # Start listening (Multi-User)
        sink = VoiceSink(self)
        self.active_sinks[interaction.guild.id] = sink
        vc.listen(sink)
        
        self.processing_tasks[interaction.guild.id] = asyncio.create_task(self.process_audio_loop(interaction.guild.id, interaction.channel))

        await interaction.followup.send(f"👂 チャンネル内の全員の声を聞き取っています...", ephemeral=True)
        
        # Announce
        media_cog = self.bot.get_cog("MediaCog")
        if media_cog:
            await media_cog.speak_text(interaction.user, "音声認識を開始します。")

    @app_commands.command(name="conversation", description="会話モードを切り替えます (ウェイクワードなしで応答)")
    @app_commands.describe(mode="ON/OFF")
    @app_commands.choices(mode=[
        app_commands.Choice(name="ON", value="on"),
        app_commands.Choice(name="OFF", value="off"),
    ])
    async def conversation(self, interaction: discord.Interaction, mode: str):
        """Toggle conversation mode (respond to all speech)."""
        guild_id = interaction.guild.id
        if guild_id not in self.active_sinks:
            await interaction.response.send_message("まずは `/listen` で音声認識を開始してください。", ephemeral=True)
            return
            
        sink = self.active_sinks[guild_id]
        sink.conversation_mode = (mode == "on")
        
        status = "ON" if sink.conversation_mode else "OFF"
        await interaction.response.send_message(f"会話モードを {status} にしました。{'ウェイクワードなしで全員の会話に応答します。' if sink.conversation_mode else 'ORAと呼びかけた時だけ応答します。'}", ephemeral=True)


    @app_commands.command(name="stop_listen", description="音声認識を終了します。")
    async def stop_listen(self, interaction: discord.Interaction):
        if interaction.guild.id in self.processing_tasks:
            self.processing_tasks[interaction.guild.id].cancel()
            del self.processing_tasks[interaction.guild.id]
        
        if interaction.guild.id in self.active_sinks:
            del self.active_sinks[interaction.guild.id]

        vc = interaction.guild.voice_client
        if vc and isinstance(vc, voice_recv.VoiceRecvClient):
            vc.stop_listening()
        
        await interaction.response.send_message("音声認識を終了しました。", ephemeral=True)

    async def process_audio_loop(self, guild_id: int, text_channel: discord.TextChannel):
        """Monitor buffer and transcribe when silence is detected."""
        logger.info(f"Started audio processing loop for guild {guild_id}")
        from src.web.endpoints import manager
        
        while True:
            await asyncio.sleep(0.5)
            
            sink = self.active_sinks.get(guild_id)
            if not sink:
                break
                
            # Iterate over all users in the sink
            # Create a list of items to avoid runtime error if dict changes during iteration
            # But keys (users) change rarely.
            user_items = list(sink.user_data.items())
            
            for user_id, ud in user_items:
                # Check for silence (no packets for 1.0 second)
                if ud.speaking and (time.time() - ud.last_packet_time > 1.0):
                    # Silence detected for this user
                    ud.speaking = False
                    ud.speaking_frames = 0
                    
                    # Get data and clear buffer
                    audio_data = bytes(ud.buffer)
                    ud.buffer = bytearray()
                    
                    if len(audio_data) < 48000 * 2 * 0.5: # Ignore < 0.5s
                        continue

                    # Transcribe in thread (Concurrent for each user)
                    asyncio.create_task(self._handle_transcription(user_id, audio_data, sink, text_channel, manager))

    async def _handle_transcription(self, user_id, audio_data, sink, text_channel, manager):
        """Handle transcription for a single user."""
        text = await asyncio.to_thread(self.transcribe, audio_data)
        
        if text:
            # Broadcast to Web UI
            await manager.broadcast(f"TRANSCRIPTION({user_id}):{text}")

            # Wake Word Check (Simple)
            keywords = ["ORA", "オラ", "おら", "オーラ"]
            is_wake = any(k in text for k in keywords)
            
            # Check conversation mode
            is_conversation = getattr(sink, "conversation_mode", False)
            
            should_respond = is_wake or is_conversation
            
            if should_respond:
                # Send to ORA
                ora_cog = self.bot.get_cog("ORACog")
                if ora_cog:
                    member = text_channel.guild.get_member(user_id)
                    if member:
                        logger.info(f"Recognized speech from {member.display_name}: {text}")
                        # Create dummy message
                        dummy_message = await text_channel.send(f"🎤 {member.display_name}: {text}")
                        dummy_message.author = member
                        dummy_message.content = text
                        
                        # Trigger ORA (Voice Mode)
                        await ora_cog.handle_prompt(dummy_message, text, is_voice=True)

    def transcribe(self, pcm_data: bytes) -> str:
        """Convert PCM to float32 and transcribe with Whisper."""
        if not pcm_data:
            return ""
        try:
            # Convert PCM 16-bit stereo to float32 mono
            audio_np = np.frombuffer(pcm_data, dtype=np.int16).flatten().astype(np.float32) / 32768.0
            
            # Stereo to Mono
            audio_np = audio_np.reshape(-1, 2)
            audio_np = audio_np.mean(axis=1)
            
            # Resample to 16kHz (Simple decimation)
            audio_16k = audio_np[::3]
            
            # Use FP16 on GPU for speed, disable on CPU to avoid warnings
            is_cpu = self.model.device.type == "cpu"
            result = self.model.transcribe(audio_16k, language="ja", fp16=not is_cpu)
            return result["text"].strip()
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceRecvCog(bot))
