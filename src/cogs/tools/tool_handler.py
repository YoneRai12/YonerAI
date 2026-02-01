import asyncio
import io
import logging
from typing import Optional

import aiohttp
import discord

from src.skills.loader import SkillLoader
from src.skills.music_skill import MusicSkill

logger = logging.getLogger(__name__)

class ToolHandler:
    def __init__(self, bot, cog):
        self.bot = bot
        self.cog = cog
        
        # Initialize Skills
        self.music_skill = MusicSkill(bot)
        
        # [Clawdbot] Dynamic Skill Loader
        self.skill_loader = SkillLoader()
        self.skill_loader.load_skills()


    async def handle_dispatch(self, tool_name: str, args: dict, message: discord.Message, status_manager=None) -> None:
        """Entry point from SSE dispatch event."""
        result = await self.execute(tool_name, args, message, status_manager)
        
        if result and "[SILENT_COMPLETION]" not in result:
             logger.info(f"Tool {tool_name} completed with visible result.")
             # Ensure the user sees the result/error if it wasn't handled inside the tool
             try:
                 # Check if message was already replied to? (Hard to know, but safe to double reply or reply to original)
                 # Most tools return user-facing strings on error.
                 await message.reply(result)
             except Exception as e:
                 logger.error(f"Failed to send tool result to user: {e}")

        elif result:
             logger.info(f"Tool {tool_name} completed silently.")

    async def execute(self, tool_name: str, args: dict, message: discord.Message, status_manager=None) -> Optional[str]:
        """Executes a tool by delegating to the appropriate Skill or handling locally."""
        
        # [Clawdbot] Dynamic Skills (Priority)
        if tool_name in self.skill_loader.skills:
             return await self.skill_loader.execute_tool(tool_name, args, message, bot=self.bot)



        # Music Skill (Media, Voice, TTS)
        elif tool_name in {"music_play", "music_control", "music_tune", "music_seek", "music_queue", "tts_speak", "join_voice_channel", "leave_voice_channel", "speak", "join_voice", "leave_voice"}:
            return await self.music_skill.execute(tool_name, args, message)



        # --- Legacy / Unmigrated Tools (Keep Local) ---
        


        elif tool_name == "request_feature":
            return await self._handle_request_feature(args, message)

        elif tool_name == "imagine":
            return await self._handle_imagine(args, message, status_manager)
        elif tool_name == "layer":
            return await self._handle_layer(args, message, status_manager)

        elif tool_name == "summarize":
            return await self._handle_summarize(args, message)

        elif tool_name == "web_remote_control":
            return await self._handle_web_remote_control(args, message, status_manager)

        elif tool_name == "web_screenshot":
            return await self._handle_web_screenshot(args, message, status_manager)

        elif tool_name == "web_search":
            return await self._handle_web_search(args, message, status_manager)

        elif tool_name == "web_download":
            return await self._handle_web_download(args, message, status_manager)

        elif tool_name == "web_record_screen":
            return await self._handle_web_record_screen(args, message, status_manager)
        
        elif tool_name == "web_jump_to_profile":
            return await self._handle_web_jump_to_profile(args, message, status_manager)
        
        elif tool_name == "web_set_view":
            return await self._handle_web_set_view(args, message, status_manager)
        
        elif tool_name == "web_navigate":
            return await self._handle_web_navigate(args, message, status_manager)
        
        return None

    # --- Permission Helper ---
    async def _check_permission(self, user_id: int, level: str = "owner") -> bool:
        """Delegate to ORACog's permission check."""
        if hasattr(self.cog, "_check_permission"):
            return await self.cog._check_permission(user_id, level)
        return user_id == self.bot.config.admin_user_id

    # --- Local Handlers (To be migrated later) ---



    async def _handle_request_feature(self, args: dict, message: discord.Message) -> str:
        feature = args.get("feature_request")
        context = args.get("context")
        if not feature:
            return "Error: Missing feature argument."
        if hasattr(self.bot, "healer"):
            asyncio.create_task(self.bot.healer.propose_feature(feature, context, message.author))
            return f"✅ Feature Request '{feature}' sent."
        return "Healer offline."

    async def _handle_imagine(self, args: dict, message: discord.Message, status_manager) -> str:
        prompt = args.get("prompt")
        if not prompt:
            return "Error: Missing prompt."
        if status_manager:
            await status_manager.next_step(f"Generating Image: {prompt[:30]}...")
        creative_cog = self.bot.get_cog("CreativeCog")
        if not creative_cog:
            return "Creative system offline."
        try:
            mp4_data = await self.bot.loop.run_in_executor(None, lambda: creative_cog.comfy_client.generate_video(prompt, ""))
            if mp4_data:
                f = discord.File(io.BytesIO(mp4_data), filename="ora_imagine.mp4")
                await message.reply(content=f"🎨 **Generated Visual**: {prompt}", file=f)
                return "Image generated. [SILENT_COMPLETION]"
            return "Generation failed."
        except Exception as e:
            return f"Error: {e}"

    async def _handle_layer(self, args: dict, message: discord.Message, status_manager) -> str:
        target_img = message.attachments[0] if message.attachments else None
        if not target_img and message.reference:
            ref = await message.channel.fetch_message(message.reference.message_id)
            if ref.attachments:
                target_img = ref.attachments[0]
        if not target_img:
            return "Error: No image found."
        
        if status_manager:
            await status_manager.next_step("Separating Layers...")
        creative_cog = self.bot.get_cog("CreativeCog")
        if not creative_cog:
            return "Creative system offline."

        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field("file", await target_img.read(), filename=target_img.filename)
                async with session.post(creative_cog.layer_api, data=data) as resp:
                    if resp.status == 200:
                        f = discord.File(io.BytesIO(await resp.read()), filename=f"layers_{target_img.filename}.zip")
                        await message.reply("✅ Layers Separated!", file=f)
                        return "Layering complete. [SILENT_COMPLETION]"
                    return f"Failed: {resp.status}"
        except Exception as e:
            return f"Error: {e}"

    async def _handle_summarize(self, args: dict, message: discord.Message) -> str:
        memory_cog = self.bot.get_cog("MemoryCog")
        if not memory_cog:
            return "Memory offline."
        summary = await memory_cog.get_user_summary(message.author.id)
        if summary:
            await message.reply(f"📌 **Context Summary:**\n{summary}")
            return "Summary sent. [SILENT_COMPLETION]"
        return "No summary available."

    async def _handle_web_remote_control(self, args: dict, message: discord.Message, status_manager) -> str:
        """
        Starts an interactive remote control session on-demand.
        Returns a temporary link (30m expiry) directly to the user.
        Always use this when user specifically wants to 'control' or 'operate' the web.
        """
        if status_manager:
            await status_manager.next_step("ブラウザとトンネルを起動中...")
        
        # 1. Start Browser via Manager
        from src.utils.browser import browser_manager
        try:
            await browser_manager.start()
        except Exception as e:
            return f"❌ Failed to start browser: {e}"
        # 2. Start API Server (if not running)
        import sys
        
        # Check if port 8000 is listening
        is_api_running = False
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 8000))
        if result == 0:
            is_api_running = True
        sock.close()

        if not is_api_running:
            if status_manager: await status_manager.next_step("APIサーバーを起動中...")
            api_log_path = os.path.join(self.bot.config.log_dir, "api_server.log")
            try:
                # Ensure logs directory exists
                os.makedirs(os.path.dirname(api_log_path), exist_ok=True)
                
                # Use the specific venv uvicorn
                uvicorn_exe = r"L:\ORADiscordBOT_Env\Scripts\uvicorn.exe"
                if not os.path.exists(uvicorn_exe): uvicorn_exe = "uvicorn"

                subprocess.Popen(
                    [uvicorn_exe, "src.web.app:app", "--host", "0.0.0.0", "--port", "8000"],
                    cwd=os.getcwd(),
                    stdout=open(api_log_path, "w"),
                    stderr=subprocess.STDOUT,
                    shell=True
                )
                await asyncio.sleep(5) # Give Uvicorn more time to bind
                
                # Verify port is actually open
                import socket
                is_ready = False
                for _ in range(3):
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        if s.connect_ex(('127.0.0.1', 8000)) == 0:
                            is_ready = True
                            break
                    await asyncio.sleep(2)
                
                if not is_ready:
                    logger.warning("Uvicorn started but Port 8000 not reachable yet.")
            except Exception as e:
                return f"❌ Failed to start API Server: {e}"

        # 3. Start Cloudflare Tunnel (Always start fresh for reliability)
        import os
        import subprocess
        import re
        
        log_dir = getattr(self.bot.config, "log_dir", os.path.join(os.getcwd(), "logs"))
        os.makedirs(os.path.dirname(log_dir), exist_ok=True)
        
        public_url = None
        log_path = os.path.join(self.bot.config.log_dir, "cf_browser.log")
        
        # Kill any stray cloudflared instances first (Aggressive Cleanup)
        try:
             subprocess.run("taskkill /F /IM cloudflared.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
        
        # Kill existing tunnel for port 8000 (Surgical Kill)
        if status_manager: await status_manager.next_step("Cloudflareトンネルをリセット中...")
        try:
            cmd = "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*localhost:8000*' } | Select-Object -ExpandProperty ProcessId"
            proc = await asyncio.create_subprocess_shell(
                f"powershell -Command \"{cmd}\"",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            pids = stdout.decode().strip().split()
            for pid in pids:
                if pid:
                    subprocess.run(f"taskkill /PID {pid} /F", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Brief wait for cleanup
            await asyncio.sleep(1)
            
            # Also remote old log
            if os.path.exists(log_path):
                try: os.remove(log_path)
                except: pass
        except Exception as e:
            logger.warning(f"Failed to kill old tunnel: {e}")

        
        if not public_url:
            # Start fresh if not running or no URL found
            if status_manager:
                  await status_manager.next_step("Cloudflareトンネルを接続中...")
            
            # Note: We do NOT use taskkill here as it kills the Dashboard tunnel too.
            # We assume if the URL check failed, the old tunnel is dead or irrelevant.
            # We perform a targeted kill ONLY if we can identify the specific process, but for now
            # it is safer to just spawn a new one. Cloudflare allows multiple tunnels.
            
            try:
                # Truncate log file
                with open(log_path, "w", encoding="utf-8") as f:
                    pass
                
                cf_bin = "cloudflared"
                if os.path.exists("cloudflared.exe"):
                    cf_bin = os.path.abspath("cloudflared.exe")

                # Revert to hidden background process as per user preference
                cmd = [cf_bin, "tunnel", "--url", "http://localhost:8000"]
                subprocess.Popen(
                    cmd,
                    stdout=open(log_path, "w"),
                    stderr=subprocess.STDOUT,
                    shell=True, # Using shell=True for windows path handling if needed, but safer
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                for _ in range(15):
                    await asyncio.sleep(2)
                    if os.path.exists(log_path):
                        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            # Check for errors
                            if "Too Many Requests" in content:
                                if status_manager: await status_manager.update_current("レート制限検知。Ngrokへ切り替え中...", force=True)
                                logger.warning("Cloudflare Rate Limit detected. Attempting Ngrok fallback.")
                                
                                # Fallback to Ngrok
                                return await self._start_ngrok_tunnel(message, status_manager)
                                
                            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                            if match:
                                public_url = match.group(0)
                                break
                    if public_url: break
            except FileNotFoundError:
                  if status_manager: await status_manager.finish()
                  return "❌ Cloudflare Tunnel (`cloudflared`) not found. Please install it."
            except Exception as e:
                  if status_manager: await status_manager.finish()
                  return f"❌ Failed to start tunnel: {e}"

        obs_text = ""
        try:
            # Capture initial state
            obs = await browser_manager.agent.observe()
            # Clean URL for display
            display_url = obs.url
            if len(display_url) > 50:
                display_url = display_url[:47] + "..."
            obs_text = f"\n**Current Page**: {obs.title} (`{display_url}`)"
        except Exception:
            pass
            
        # [User Request] Default to Google Home for Remote Control Start
        try:
             await browser_manager.navigate("https://www.google.com")
             await asyncio.sleep(2)
             obs = await browser_manager.agent.observe()
             obs_text = f"\n**Current Page**: {obs.title} (Google)"
        except:
             pass
            
        if public_url:
            # [User Request] Web Operation Channel
            target_channel_id = getattr(self.bot.config, "ora_web_notify_id", None)
            
            direct_url = f"{public_url.rstrip('/')}/static/operator.html"
            
            # Success logic
            if status_manager: await status_manager.finish()
            
            reply_content = (
                f"🚀 **Remote Web Control Ready**\n"
                f"🔗 **Access**: {direct_url}\n"
                f"*(Expires in 30m)*"
            )
            
            # Send reply directly to the user/channel where requested
            await message.reply(reply_content)
            
            # Schedule expiration
            self.bot.loop.create_task(self._schedule_session_timeout(message, log_path))
            
            return "Remote control link sent. [SILENT_COMPLETION]"
        else:
            return "❌ Failed to obtain Cloudflare URL. Check `logs/cf_browser.log`."

    async def _start_ngrok_tunnel(self, message: discord.Message, status_manager) -> str:
        """Fallback: Starts Ngrok tunnel for port 8000."""
        import subprocess
        import json
        import shutil
        import os
        
        # 1. Locate Ngrok
        ngrok_bin = "ngrok"
        if os.path.exists("ngrok.exe"):
            ngrok_bin = os.path.abspath("ngrok.exe")
        elif os.path.exists("tools/ngrok/ngrok.exe"):
            ngrok_bin = os.path.abspath("tools/ngrok/ngrok.exe")
        elif not shutil.which("ngrok"):
             if status_manager: await status_manager.finish()
             return "❌ Ngrok not found. Please install Ngrok or add it to tools/ngrok/."

        # 2. Start Ngrok (Background)
        try:
            # Kill existing ngrok interacting with port 8000? 
            # Ngrok doesn't use --url arg like cloudflared, but we can kill all ngrok for now or rely on API check.
            subprocess.run("taskkill /IM ngrok.exe /F", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Start fresh
            # Using 'start' to ensure it runs headless/detached properly or just Popen
            subprocess.Popen(
                [ngrok_bin, "http", "8000"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # 3. Poll Local API for URL
            public_url = None
            async with aiohttp.ClientSession() as session:
                for i in range(10):
                    await asyncio.sleep(2)
                    try:
                        async with session.get("http://localhost:4040/api/tunnels", timeout=2) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                tunnels = data.get("tunnels", [])
                                if tunnels:
                                    public_url = tunnels[0].get("public_url")
                                    break
                    except:
                        pass
            
            if public_url:
                # The caller logic in _handle_web_remote_control                # [User Request] Web Operation Channel
                target_channel_id = 1467163318845440062
                
                direct_url = f"{public_url.rstrip('/')}/static/operator.html"
                
                # Get Observation
                obs_text = ""
                try:
                    from src.utils.browser import browser_manager
                    obs = await browser_manager.agent.observe()
                    obs_text = f"\n**Current Page**: {obs.title} (`{obs.url[:40]}...`)"
                except: pass

                if status_manager: await status_manager.finish()

                reply_content = (
                    f"🚀 **Remote Web Control Ready (Ngrok)**\n"
                    f"🔗 **Access Link**: {direct_url}\n"
                    f"{obs_text}\n"
                    f"*(Link expires in 30 minutes)*"
                )
                
                # Reply directly
                await message.reply(reply_content)

                # Schedule timeout
                asyncio.create_task(self._schedule_session_timeout(message, log_path))
                
                return "Remote control link sent. [SILENT_COMPLETION]"
            
            else:
                if status_manager: await status_manager.finish()
                return "❌ Failed to start Ngrok tunnel (No API response)."
                
        except Exception as e:
            if status_manager: await status_manager.finish()
            return f"❌ Ngrok Error: {e}"

    async def _schedule_session_timeout(self, message: discord.Message, log_path: str) -> None:
        """Waits 30 minutes then kills the browser tunnel."""
        await asyncio.sleep(1800) # 30 minutes
        
        # Check if tunnel is still active by log existence? 
        # Actually, we just kill cloudflared.exe.
        # But we should be careful not to kill Dashboard tunnel.
        # Ideally we would have stored the PID.
        # For now, we'll try to identify it or just warn user.
        # But wait, we can just delete the log file? No, that doesn't kill the tunnel.
        
        # Re-using the logic from start: "taskkill /IM cloudflared.exe" is bad.
        # We need to find the process that is writing to 'log_path'.
        # That's hard in Python without psutil.
        
        # Fallback: Just notify user it's "expired" and let them know?
        # User asked to "cut" the link.
        # If we can't kill specific process easily, we might have to accept killing all or require user to stop it.
        # HOWEVER, we can use the 'fuser' equivalent or just assume we kill the latest spawned one? No.
        
        # Let's try to find the process via command line args in tasklist?
        # "cloudflared tunnel --url http://localhost:8000"
        
        try:
            # Shutdown specific tunnel by command line matching
            import subprocess
            # WMI or PowerShell to find PID of cloudflared with specific args
            cmd = "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*localhost:8000*' } | Select-Object -ExpandProperty ProcessId"
            proc = await asyncio.create_subprocess_shell(
                f"powershell -Command \"{cmd}\"",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            pid = stdout.decode().strip()
            
            if pid:
                subprocess.run(f"taskkill /PID {pid} /F", shell=True)
                try:
                    target_id = self.bot.config.ora_web_notify_id
                    target = self.bot.get_channel(target_id) or await self.bot.fetch_channel(target_id)
                    if target:
                        await target.send("🔒 **Remote Web Control session expired** (30 mins). \nTunnel has been closed.")
                    else:
                        await message.reply("🔒 **Remote Web Control session expired** (30 mins). \nTunnel has been closed.")
                except: pass
                
                # Cleanup log
                if os.path.exists(log_path):
                    try: os.remove(log_path)
                    except: pass
        except Exception as e:
            logger.error(f"Failed to kill session tunnel: {e}")

    async def _handle_web_download(self, args: dict, message: discord.Message, status_manager) -> str:
        """Handles web_download: Downloads video/audio from current URL using yt-dlp with smart logic."""
        from src.utils.browser import browser_manager
        from src.utils.youtube import download_video_smart, download_youtube_audio
        from src.config import Config
        import os
        
        # 1. Determine Target URL
        url = args.get("url")
        if not url:
            # Use current browser URL if active
            if browser_manager.is_ready():
                 try:
                     obs = await browser_manager.agent.observe()
                     url = obs.url
                 except Exception:
                     pass
        
        if url:
             url = url.strip().strip('"').strip("'").strip("<").strip(">")
        
        if not url:
             return "❌ No URL specified and no active browser session."

        download_fmt = args.get("format", "video")
        
        # New Params for Continuation
        start_time = int(args.get("start_time", 0))
        force_compress = args.get("force_compress", False)
        
        label = "Image" if download_fmt == "image" else ("Audio" if download_fmt == "audio" else "Video")
        
        if status_manager: await status_manager.next_step(f"{label} Downloading... ({url})")
        
        # Load Config
        cfg = Config.load()
        proxy = cfg.browser_proxy if cfg.browser_proxy else None
        
        split_strategy = args.get("split_strategy", "auto") # "auto", "compress", "split_all"

        try:
            if download_fmt == "audio":
                # Use existing audio helper
                final_path, title, duration = await download_youtube_audio(url, proxy=proxy)
                next_start = None
                is_last = True
            else:
                # Video: Use Smart Downloader
                # Calculate max size based on Guild Limit
                limit_bytes = message.guild.filesize_limit if message.guild else 10*1024*1024
                # Safety margin 1MB
                safe_limit_mb = (limit_bytes / (1024*1024)) - 0.5
                if safe_limit_mb < 5: safe_limit_mb = 5 
                
                result = await download_video_smart(
                    url, 
                    start_time=start_time, 
                    force_compress=force_compress, 
                    max_size_mb=safe_limit_mb,
                    proxy=proxy,
                    split_strategy=split_strategy
                )
                final_path = result["path"]
                title = result["title"]
                next_start = result.get("next_start_time")
                is_last = result.get("is_last", True)
            
            if not final_path or not os.path.exists(final_path):
                 return "❌ Download failed (File not found)."

            # Upload / Buffer
            if status_manager: await status_manager.next_step("Buffering download...")
            
            content = f"🎵 **{label} Downloaded**\nTitle: **{title}**\nSource: <{url}>"
            if next_start:
                content += f"\n\n✂️ **Continuation Available**\nVideo was split to fit limits.\nTo get the next part, ask:\n`next part` or use tool with `start_time={next_start}`."

            if status_manager and hasattr(status_manager, "add_file"):
                # Buffer for smart bundling
                status_manager.add_file(final_path, os.path.basename(final_path), content)
                return f"Download buffered. Next start: {next_start} [SILENT_COMPLETION]"
            else:
                # Legacy / No-buffer
                f_obj = discord.File(final_path)
                await message.reply(content=content, file=f_obj)
                
                # Cleanup (Only if not buffered)
                try:
                    os.remove(final_path)
                except: pass
            
            # [FIX] Do NOT finish status_manager here. Let ChatHandler manage the lifecycle for sequential tools.
            # if status_manager: await status_manager.finish()
            
            return f"Download completed. Next start: {next_start} [SILENT_COMPLETION]"
            
        except Exception as e:
            if status_manager: await status_manager.finish()
            return f"❌ Download/Upload Error: {e}"

    async def _handle_web_screenshot(self, args: dict, message: discord.Message, status_manager) -> str:
        """Handles the web_screenshot tool: Takes a screenshot and returns ARIA snapshot."""
        if status_manager:
            await status_manager.next_step("Processing screenshot request...")
            
        from src.utils.browser import browser_manager
        import io
        import uuid
        import os
        import asyncio
        
        try:
            # Ensure active
            await browser_manager.ensure_active()
            
            # Optional Navigation
            target_url = args.get("url")
            if target_url:
                 target_url = target_url.strip().strip('"').strip("'").strip("<").strip(">")
            
            # View Settings
            dark_mode = args.get("dark_mode")
            width = args.get("width")
            height = args.get("height")
            scale = args.get("scale")
            delay = int(args.get("delay", 2))
            full_page = args.get("full_page", False)
            
            # New Params
            resolution = args.get("resolution")
            orientation = args.get("orientation", "landscape")
            
            # Resolution Mapping
            RES_MAP = {
                "SD": (640, 480),
                "HD": (1280, 720),
                "FHD": (1920, 1080),
                "2K": (2560, 1440),
                "4K": (3840, 2160),
                "8K": (7680, 4320)
            }
            
            if resolution and resolution in RES_MAP:
                base_w, base_h = RES_MAP[resolution]
                if orientation == "portrait" and base_w > base_h:
                    width = base_h
                    height = base_w
                else:
                    width = base_w
                    height = base_h
            
            # Preset handling (Legacy "mobile" flag or keywords)
            if args.get("mobile"):
                width = 375
                height = 812
                scale = 1.0
            
            # Apply View Settings
            if any([width, height, dark_mode is not None, scale]):
                await browser_manager.set_view(width=width, height=height, dark_mode=dark_mode, scale=scale)
            
            # Navigate if URL provided
            if target_url:
                if status_manager: await status_manager.next_step(f"Navigating to {target_url}...")
                await browser_manager.navigate(target_url)
            
            # Wait for content load + User specified delay
            if delay > 0:
                await asyncio.sleep(delay)
            
            # Take Screenshot
            if status_manager: await status_manager.update_current("Capturing screenshot...")
            
            # 1. Get Image Data
            image_bytes = await browser_manager.get_screenshot()
            if not image_bytes:
                return "❌ No screenshot data returned."
            
            # 2. Save to File (Prefer L:\ORA_Temp)
            l_temp = r"L:\ORA_Temp"
            final_dir = self.bot.config.temp_dir
            if os.path.exists("L:\\"):
                try:
                    os.makedirs(l_temp, exist_ok=True)
                    final_dir = l_temp
                except: pass
                
            filename = f"screenshot_{uuid.uuid4().hex[:8]}.jpg"
            file_path = os.path.join(final_dir, filename)
            
            with open(file_path, "wb") as f:
                f.write(image_bytes)
            
            # 2.5 Smart Compression (Dynamic Limit)
            # 2025 Update: Default limit is moving to 10MB for non-boosted / DMs.
            # We trust the guild's explicit limit if available.
            limit_bytes = 10 * 1024 * 1024 
            if message.guild:
                limit_bytes = message.guild.filesize_limit
            
            # Add safety margin (1MB) to be safe against request overhead
            safe_limit = limit_bytes - (1 * 1024 * 1024)
            file_size = len(image_bytes)
            
            if file_size > safe_limit:
                if status_manager: 
                    await status_manager.update_current(f"Compressing large image ({file_size/1024/1024:.1f}MB > {safe_limit/1024/1024:.1f}MB)...")
                try:
                    # Use ffmpeg to compress
                    import subprocess
                    compressed_path = file_path.replace(".jpg", "_comp.jpg")
                    
                    # Strategy 1: Aggressive JPEG Compression
                    cmd = [
                        "ffmpeg", "-y", "-i", file_path, 
                        "-q:v", "20",  # Increased compression (was 15)
                        compressed_path
                    ]
                    
                    process = await asyncio.create_subprocess_exec(
                        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                    )
                    await process.wait()
                    
                    # Strategy 2: Resize if STILL too big
                    if os.path.exists(compressed_path) and os.path.getsize(compressed_path) > safe_limit:
                        # Resize to 50% width/height
                        resized_path = file_path.replace(".jpg", "_resize.jpg")
                        cmd_resize = [
                             "ffmpeg", "-y", "-i", compressed_path,
                             "-vf", "scale=iw*0.5:ih*0.5",
                             "-q:v", "15",
                             resized_path
                        ]
                        proc_resize = await asyncio.create_subprocess_exec(
                             *cmd_resize, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                        )
                        await proc_resize.wait()
                        
                        if os.path.exists(resized_path):
                             compressed_path = resized_path # Use resized version
                    
                    # Final check
                    if os.path.exists(compressed_path):
                        # Even if larger (unlikely after resize), we try to send the smallest we have
                         if os.path.getsize(compressed_path) < file_size:
                            os.remove(file_path) # Remove original
                            file_path = compressed_path
                            filename = os.path.basename(file_path)
                            
                except Exception as e:
                    logger.error(f"Compression/Resize failed: {e}")
            
            # 3. Get Context info
            try:
                obs = await browser_manager.agent.observe()
                title = obs.title
                current_url = obs.url
                aria = obs.text_content[:200] + "..." if obs.text_content else "No Text"
            except:
                title = "Web Page"
                current_url = target_url or "Current Page"
                aria = "Context unavailable"

            # 4. Upload
            # 4. Upload / Buffer
            if status_manager: await status_manager.next_step("Buffering screenshot...")
            
            content = f"📸 **{title}**\nURL: <{current_url}>"
            if width and height:
                content += f"\nRes: {width}x{height}"
            if delay > 0:
                content += f" (Delayed {delay}s)"
                
            if status_manager and hasattr(status_manager, "add_file"):
                # Buffer for smart bundling
                status_manager.add_file(file_path, filename, content)
                return f"Screenshot buffered. Title: {title}\nARIA: {aria}\n[SILENT_COMPLETION]"
            else:
                # Legacy / No-buffer fallback
                f_obj = discord.File(file_path, filename=filename)  
                await message.reply(content=content, file=f_obj)
                
                # Cleanup (Only delete if sent immediately)
                try:
                    os.remove(file_path)
                except: pass

            
            # [FIX] Do NOT finish status_manager here. Let ChatHandler manage.
            # if status_manager: await status_manager.finish()
            return f"Screenshot taken. Title: {title}\nARIA: {aria}\n[SILENT_COMPLETION]"

        except Exception as e:
            if status_manager: await status_manager.finish()
            return f"❌ Screenshot failed: {e}"

    async def _handle_fs_action(self, args: dict, message: discord.Message, status_manager) -> str:
        """Handles filesystem actions: ls, cat, grep, tree, diff."""
        from src.utils.filesystem import fs_tools
        
        command = args.get("command")
        path = args.get("path", ".")
        arg2 = args.get("arg2", None) # For diff
        pattern = args.get("pattern", None) # For grep
        
        if not command:
            return "Error: command required (ls, cat, grep, tree, diff)"

        if status_manager:
            await status_manager.next_step(f"Filesystem: {command} {path}...")
            
        try:
            output = ""
            if command == "ls":
                output = fs_tools.ls(path)
            elif command == "cat":
                output = fs_tools.cat(path)
            elif command == "grep":
                if not pattern: return "Error: pattern required for grep"
                output = fs_tools.grep(pattern, path)
            elif command == "tree":
                output = fs_tools.tree(path)
            elif command == "diff":
                if not arg2: return "Error: arg2 required for diff"
                output = fs_tools.diff(path, arg2)
            else:
                return f"Error: Unknown filesystem command '{command}'"

            # Truncate for display if needed, but return full for AI usually?
            # AI context window is limited too.
            if len(output) > 1900:
                # Save to file if huge?
                header = f"Output too long ({len(output)} chars). Showing first 1900:\n"
                return header + output[:1900] + "\n..."
            
            return output if output else "[No Output]"

        except Exception as e:
            return f"Filesystem Error: {e}"

    async def _handle_web_record_screen(self, args: dict, message: discord.Message, status_manager) -> str:
        """Handles web_record_screen: Auto-records for a duration or manual start/stop."""
        from src.utils.browser import browser_manager
        import asyncio
        import os
        import logging
        
        logger = logging.getLogger(__name__)
        
        action = args.get("action", "start")
        duration = args.get("duration", 30) # Default 30s
        
        # [Auto Mode] If action is start and we want auto-recording
        if action == "start":
            if browser_manager.is_recording:
                return "⚠️ Screen recording is already active. Say 'Stop recording' to finish early."
            
            if status_manager: await status_manager.next_step(f"📷 Recording screen for {duration} seconds...")
            
            success = await browser_manager.start_recording()
            if not success:
                 return "❌ Failed to start recording."
            
            # Send initial feedback
            await message.reply(f"🔴 **Recording Started** ({duration}s auto-stop)\nPerforming browser actions now will be captured.")
            
            # Wait for duration
            await asyncio.sleep(duration)
            
            # Auto-Stop
            if status_manager: await status_manager.next_step("⏱️ Time's up! Stopping and processing...")
            video_path = await browser_manager.stop_recording()
            
            if not video_path or not os.path.exists(video_path):
                return "❌ Recording finished but file missing."
                
            # Check size and compress if needed
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            limit_mb = 25.0 # Safe limit for boosted servers, 8MB for free. 
            
            final_path = video_path
            
            if file_size_mb > limit_mb:
                if status_manager: await status_manager.next_step(f"Compressing video ({file_size_mb:.1f}MB)...")
                try:
                    # Simple compression using ffmpeg
                    compressed_path = video_path.replace(".webm", "_comp.mp4")
                    # crf 28 is decent compression, preset fast
                    cmd = f'ffmpeg -i "{video_path}" -vcodec libx264 -crf 30 -preset fast -acodec aac "{compressed_path}"'
                    proc = await asyncio.create_subprocess_shell(cmd)
                    await proc.communicate()
                    
                    if os.path.exists(compressed_path) and os.path.getsize(compressed_path) < os.path.getsize(video_path):
                        final_path = compressed_path
                except Exception as e:
                    logger.error(f"Compression failed: {e}")
            
            # Upload
            if status_manager: await status_manager.next_step("Uploading video...")
            try:
                f_obj = discord.File(final_path, filename=f"screen_record_{duration}s.mp4")
                await message.reply(content="⏹️ **Recording Finished**", file=f_obj)
            except Exception as e:
                return f"❌ Upload failed (too large?): {e}"
            
            # Cleanup
            try:
                if final_path != video_path: os.remove(final_path)
                os.remove(video_path)
            except: pass
                
            return "Screen recording completed. [SILENT_COMPLETION]"

        elif action == "stop":
            # Manual stop if user interrupted
            if not browser_manager.is_recording:
                return "⚠️ No active recording."
            video_path = await browser_manager.stop_recording()
            if video_path:
                 f_obj = discord.File(video_path, filename="screen_record_manual.webm")
                 await message.reply(content="⏹️ **Stopped Early**", file=f_obj)
                 return "Stopped. [SILENT_COMPLETION]"
            return "❌ Stop failed."
        
        return "❌ Invalid action."

    async def _handle_web_action(self, args: dict, message: discord.Message, status_manager) -> str:
        """Handles generic web actions (click, type, scroll, goto) via BrowserAgent."""
        from src.utils.browser import browser_manager
        
        action = args.get("action")
        
        # Start browser if needed
        if not browser_manager.is_ready():
             if status_manager: await status_manager.next_step("Starting Browser...")
             await browser_manager.start()

        if status_manager:
            await status_manager.next_step(f"Browser: {action}...")

        # Construct action dict for new agent.act()
        act_dict = {"type": action}
        
        # Map args
        if action == "scroll":
            if "scroll_amount" in args:
                act_dict["delta_y"] = args["scroll_amount"]
        
        # Copy other known keys
        valid_keys = {"url", "text", "key", "x", "y", "delta_x", "delta_y", "selector"}
        for k, v in args.items():
            if k in valid_keys:
                act_dict[k] = v
                
        # Access agent directly
        agent = browser_manager.agent
        if not agent:
             return "Error: Browser Agent not available."
             
        try:
             result = await agent.act(act_dict)
             if result.get("ok"):
                 # Action successful. Now capture screenshot to show result.
                 # Wait a moment for any render/scroll animation
                 await asyncio.sleep(1.0)
                 
                 # Observe & Screenshot
                 obs = await browser_manager.agent.observe()
                 image_bytes = await browser_manager.agent.page.screenshot(type='jpeg', quality=80)
                 
                 if image_bytes:
                     f = discord.File(io.BytesIO(image_bytes), filename="action_result.jpg")
                     if status_manager: await status_manager.complete()
                     await message.reply(content=f"✅ **Action '{action}' Completed**\nURL: <{obs.url}>", file=f)
                 
                 return f"Action '{action}' completed. [SILENT_COMPLETION]"
             else:
                 return f"Action failed: {result.get('error')}"
        except Exception as e:
             return f"Action Error: {e}"

    async def _handle_web_navigate(self, args: dict, message: discord.Message, status_manager) -> str:
        """
        Navigates the browser to a specific URL.
        Args:
           url (str): The full URL to visit (e.g., https://x.com/username, https://www.google.com). 
           Be specific: dont just go to landing pages if user asks for profiles.
        """
        from src.utils.browser import browser_manager
        
        url = args.get("url")
        if not url: return "Error: URL required."
        url = url.strip().strip('"').strip("'").strip("<").strip(">")
        
        # Start browser if needed
        if not browser_manager.is_ready():
             if status_manager: await status_manager.next_step("Starting Browser...")
             await browser_manager.start()

        if status_manager:
            await status_manager.next_step(f"Navigating to: {url}...")

        # Use navigate helper which returns title
        try:
             title = await browser_manager.navigate(url)
             display_url = url
             if len(display_url) > 50:
                  display_url = display_url[:47] + "..."
             return f"Navigated to: {title}\nURL: <{display_url}>"
        except Exception as e:
             return f"❌ Navigation Failed: {e}"

    async def _handle_web_jump_to_profile(self, args: dict, message: discord.Message, status_manager) -> str:
        """
        Constructs a URL for a specific SNS profile and navigates to it.
        """
        site = args.get("site", "").lower()
        handle = args.get("handle", "").strip().lstrip("@")
        
        if not site or not handle:
            return "Error: Site and handle (username) are required."
            
        patterns = {
            "x": "https://x.com/{handle}",
            "twitter": "https://x.com/{handle}",
            "github": "https://github.com/{handle}",
            "youtube": "https://www.youtube.com/@{handle}",
            "instagram": "https://www.instagram.com/{handle}/"
        }
        
        pattern = patterns.get(site)
        if not pattern:
            return f"Error: Site '{site}' is not yet supported for direct jump."
            
        url = pattern.format(handle=handle)
        
        from src.utils.browser import browser_manager
        
        # Start browser if needed
        if not browser_manager.is_ready():
             if status_manager: await status_manager.next_step("Starting Browser...")
             await browser_manager.start()

        if status_manager:
            await status_manager.next_step(f"Jumping to {site.upper()} profile: {handle}...")

        try:
             title = await browser_manager.navigate(url)
             # Automatically take a screenshot if it's a direct profile jump to show the user
             await self._handle_web_screenshot({}, message, status_manager)
             return f"✅ **Direct Jump Successful**\nProfile: {site.upper()} (@{handle})\nURL: <{url}>\nTitle: {title}"
        except Exception as e:
             return f"❌ Profile Jump Failed: {e}. I will try to search for the profile instead."

    async def _handle_web_set_view(self, args: dict, message: discord.Message, status_manager) -> str:
        """
        Configures browser orientation and color scheme.
        """
        from src.utils.browser import browser_manager
        
        orientation = args.get("orientation")
        mode = args.get("mode")
        
        if not orientation and not mode:
            return "Error: orientation or mode required."
            
        # 1. Viewport Config
        width, height = None, None
        if orientation == "vertical":
            width, height = 375, 812 # iPhone X size
        elif orientation == "horizontal":
            width, height = 1280, 720
            
        # 2. Color Scheme
        dark_mode = None
        if mode == "dark":
            dark_mode = True
        elif mode == "light":
            dark_mode = False
            
        try:
            await browser_manager.set_view(width=width, height=height, dark_mode=dark_mode)
            
            # Labeling
            parts = []
            if orientation: parts.append(f"Orientation: {orientation}")
            if mode: parts.append(f"Mode: {mode}")
            
            # Automatically take a screenshot to show the result
            await self._handle_web_screenshot({}, message, status_manager)
            
            return f"✅ **View Settings Applied**\n{', '.join(parts)}"
        except Exception as e:
            return f"❌ Failed to set view: {e}"

    async def _handle_web_search(self, args: dict, message: discord.Message, status_manager) -> str:
        """Handles web_search: Mimic human behavior to avoid CAPTCHA."""
        from src.utils.browser import browser_manager
        
        query = args.get("query")
        site = args.get("site", "google").lower()
        
        if not query: return "Error: query required."
        
        # Start browser if needed
        await browser_manager.ensure_active()
        
        target_url = None
        human_search = False
        
        if site == "google":
            if status_manager: await status_manager.next_step(f"Searching Google for '{query}'...")
            await browser_manager.navigate("https://www.google.com")
            await asyncio.sleep(2)
            
            # Mimic human typing
            page = browser_manager.agent.page
            try:
                # Try common selectors for search box
                # Google often uses textarea[name='q'] or input[name='q']
                await page.wait_for_selector("textarea[name='q'], input[name='q']", timeout=5000)
                await page.fill("textarea[name='q'], input[name='q']", query)
                await asyncio.sleep(0.5)
                await page.press("textarea[name='q'], input[name='q']", "Enter")
                await page.wait_for_load_state("networkidle", timeout=10000)
                human_search = True
                await page.wait_for_load_state("networkidle", timeout=10000)
                human_search = True
            except Exception as e:
                logger.warning(f"Human search failed for Google: {e}. (Skipping direct URL fallback to avoid CAPTCHA)")
                # If human search fails (e.g. selector not found), we are likely still on Google Homepage or some error page.
                # Returning current state is better than triggering a CAPTCHA ban with direct URL.
                human_search = True # Treat as "handled" so we don't trigger fallback

        
        elif site == "youtube":
            if status_manager: await status_manager.next_step(f"Searching YouTube for '{query}'...")
            await browser_manager.navigate("https://www.youtube.com")
            await asyncio.sleep(2)
            page = browser_manager.agent.page
            try:
                await page.wait_for_selector("input[id='search']", timeout=5000)
                await page.fill("input[id='search']", query)
                await page.press("input[id='search']", "Enter")
                await page.wait_for_load_state("networkidle", timeout=10000)
                human_search = True
            except Exception:
                pass

        if not human_search:
            # Fallback to Direct URL
            import urllib.parse
            q_enc = urllib.parse.quote(query)
            
            if site == "google": target_url = f"https://www.google.com/search?q={q_enc}"
            elif site == "youtube": target_url = f"https://www.youtube.com/results?search_query={q_enc}"
            elif site == "github": target_url = f"https://github.com/search?q={q_enc}"
            elif site == "yahoo": target_url = f"https://search.yahoo.co.jp/search?p={q_enc}"
            elif site == "twitter" or site == "x": target_url = f"https://twitter.com/search?q={q_enc}"
            elif site == "bing": target_url = f"https://www.bing.com/search?q={q_enc}"
            
            if target_url:
                if status_manager: await status_manager.next_step(f"Navigating to search results...")
                await browser_manager.navigate(target_url)
                await asyncio.sleep(2)

        # Apply View Settings (from args)
        width = args.get("width")
        height = args.get("height")
        dark_mode = args.get("dark_mode")
        scale = args.get("scale")
        if args.get("mobile"):
            width, height, scale = 375, 812, 1.0
            
        if any([width, height, dark_mode is not None, scale]):
             await browser_manager.set_view(width, height, dark_mode, scale)

        # Delegate final screenshot capture to shared logic or do it here?
        # Let's do it here to return the result directly
        
        obs = await browser_manager.agent.observe()
        image_bytes = await browser_manager.agent.page.screenshot(type='jpeg', quality=80)
        
        if not image_bytes: return "❌ No screenshot available."
        
        f = discord.File(io.BytesIO(image_bytes), filename="search_result.jpg")
        display_url = obs.url
        if len(display_url) > 50:
            display_url = display_url[:47] + "..."
        await message.reply(content=f"🔍 **{obs.title}**\nURL: <{display_url}>", file=f)
        return "Search completed. [SILENT_COMPLETION]"
    
    async def _handle_generate_video_api(self, args: dict, message: discord.Message, status_manager) -> str:
        """Handles API-based video generation (Sora)."""
        from src.utils.media_api import media_api
        prompt = args.get("prompt")
        if not prompt: return "Error: prompt required."
        
        if status_manager: await status_manager.next_step(f"Generating Video (API): {prompt}...")
        return await media_api.generate_video(prompt)


