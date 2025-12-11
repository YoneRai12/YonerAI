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

class VoiceSink(voice_recv.AudioSink):
    def __init__(self, cog, user_id: int):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.buffer = bytearray()
        self.last_packet_time = time.time()
        self.speaking = False
        self.sample_rate = 48000
        self.channels = 2 # Discord sends stereo
        self.sample_width = 2 # 16-bit PCM

    def wants_opus(self) -> bool:
        return False

    def write(self, user: discord.User, data: voice_recv.VoiceData):
        if user is None or user.id != self.user_id:
            return

        self.last_packet_time = time.time()
        self.buffer.extend(data.pcm)
        
        # Barge-in Logic
        # Count consecutive frames to avoid noise trigger
        # We don't have a frame counter here, but we can use a simple counter on the sink
        if not hasattr(self, "speaking_frames"):
             self.speaking_frames = 0
             self.last_stop_time = 0

        self.speaking_frames += 1
        
        # Threshold: 5 frames (~100ms)
        if self.speaking_frames >= 5:
            if not self.speaking:
                self.speaking = True
                logger.info(f"User {user.name} started speaking.")
                
                # Trigger Barge-in (Stop TTS)
                # Check cooldown (500ms)
                if time.time() - self.last_stop_time > 0.5:
                    media_cog = self.cog.bot.get_cog("MediaCog")
                    if media_cog:
                        # Stop playback only
                        media_cog._voice_manager.stop_playback(user.guild.id)
                        self.last_stop_time = time.time()
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
            # Load small model for speed/accuracy balance on RTX 5080
            # 'base' or 'small' is usually fast enough for real-time
            logger.info("Loading Whisper model (small)...")
            self.model = whisper.load_model("small")
            logger.info("Whisper model loaded.")

    @app_commands.command(name="listen", description="ボイスチャンネルであなたの声を聞き取ります。")
    async def listen(self, interaction: discord.Interaction):
        # Admin check
        if self.bot.config.admin_user_id and interaction.user.id != self.bot.config.admin_user_id:
            await interaction.response.send_message("この機能は管理者専用です。", ephemeral=True)
            return

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

        # Start listening
        sink = VoiceSink(self, interaction.user.id)
        self.active_sinks[interaction.guild.id] = sink
        vc.listen(sink)
        
        self.processing_tasks[interaction.guild.id] = asyncio.create_task(self.process_audio_loop(interaction.guild.id, interaction.channel))

        await interaction.followup.send(f"👂 {interaction.user.display_name} さんの声を聞き取っています...", ephemeral=True)
        
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
        await interaction.response.send_message(f"会話モードを {status} にしました。{'ウェイクワードなしで応答します。' if sink.conversation_mode else 'ORAと呼びかけた時だけ応答します。'}", ephemeral=True)


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
                
            # Check for silence (no packets for 1.0 second)
            # Check for silence (no packets for 1.0 second)
            if sink.speaking and (time.time() - sink.last_packet_time > 1.0):
                logger.info("Silence detected. Transcribing...")
                sink.speaking = False
                if hasattr(sink, "speaking_frames"):
                    sink.speaking_frames = 0
                
                # Get data and clear buffer
                audio_data = bytes(sink.buffer)
                sink.buffer = bytearray()
                
                if len(audio_data) < 48000 * 2 * 0.5: # Ignore < 0.5s
                    continue

                # Transcribe in thread
                text = await asyncio.to_thread(self.transcribe, audio_data)
                
                if text:
                    logger.info(f"Transcribed: {text}")
                    # Broadcast to Web UI
                    await manager.broadcast(f"TRANSCRIPTION:{text}")

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
                            member = text_channel.guild.get_member(sink.user_id)
                            if member:
                                # Create dummy message
                                dummy_message = await text_channel.send(f"🎤 {member.display_name}: {text}")
                                dummy_message.author = member
                                dummy_message.content = text
                                
                                # Trigger ORA
                                # Trigger ORA
                                await ora_cog.handle_prompt(dummy_message, text, is_voice=True)
                    else:
                        # Just log/stream, don't respond
                        pass

    def transcribe(self, pcm_data: bytes) -> str:
        """Convert PCM to float32 and transcribe with Whisper."""
        if not pcm_data:
            return ""
        try:
            # Convert PCM 16-bit stereo to float32 mono
            audio_np = np.frombuffer(pcm_data, dtype=np.int16).flatten().astype(np.float32) / 32768.0
            
            # Stereo to Mono (take average or just left channel? Whisper expects mono)
            # Data is L, R, L, R...
            # Reshape to (N, 2)
            audio_np = audio_np.reshape(-1, 2)
            # Mean of channels
            audio_np = audio_np.mean(axis=1)
            
            # Whisper expects 16kHz
            # We have 48kHz. Simple decimation (take every 3rd sample) is crude but might work for speech.
            # Better to use scipy.signal.resample, but let's try simple slicing first to avoid dependency.
            audio_16k = audio_np[::3]
            
            result = self.model.transcribe(audio_16k, language="ja")
            return result["text"].strip()
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceRecvCog(bot))
