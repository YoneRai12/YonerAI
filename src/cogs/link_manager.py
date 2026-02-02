import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class LinkManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sent_on_startup = False

    async def _get_tunnel_url(self, service_name: str, fallback: str) -> str:
        """Extracts the latest Quick Tunnel URL from the service's log file with retries."""
        import os
        import re
        import asyncio
        
        cfg = self.bot.config
        log_dir = cfg.log_dir
        log_path = os.path.join(log_dir, f"cf_{service_name}.log")
        
        # Cloudflare might take a few seconds to write the URL
        for attempt in range(3):
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Find the most recent URL in the log
                        matches = re.findall(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                        if matches:
                            url = matches[-1]
                            logger.info(f"✅ Extracted Cloudflare URL for {service_name}: {url}")
                            return url
                except Exception as e:
                    logger.error(f"Failed to parse tunnel log for {service_name}: {e}")
            
            if attempt < 2:
                logger.info(f"⏳ Waiting for Cloudflare URL in {log_path} (Attempt {attempt+1}/3)...")
                await asyncio.sleep(5)
        
        return fallback

    async def get_link_map(self):
        """Dynamic link map using latest Cloudflare URLs and Config."""
        cfg = self.bot.config
        
        # 1. Cloudflare Dynamic Bases
        # Dashboard (3333) proxies docs, api, etc.
        dash_cf = await self._get_tunnel_url("dash", cfg.public_base_url or "http://localhost:3333")
        
        # Web Chat is on 3000 (now 'ora-chat') -> cf_chat.log
        # Note: 'ora-main' is Named Tunnel for 8000 (Web Control)
        chat_cf = await self._get_tunnel_url("chat", "http://localhost:3000")
        
        # ComfyUI is on 8188 -> cf_comfy.log
        comfy_cf = await self._get_tunnel_url("comfy", "http://localhost:8188")
        
        # 2. Meteor (Strictly for Web Control only)
        # This is served by 'ora-main' Named Tunnel
        if cfg.tunnel_hostname:
            meteor_base = f"https://{cfg.tunnel_hostname.strip()}"
        else:
            meteor_base = dash_cf

        mapping = {}
        
        # --- LINK CHANNELS (With URLs) ---
        
        # 1. ORA 管理ダッシュボード (1454335076048568401)
        if cfg.startup_notify_channel_id:
            mapping[cfg.startup_notify_channel_id] = {
                "title": "🚀 ORA 管理ダッシュボード",
                "url": f"{dash_cf}/dashboard",
                "desc": "コスト追跡、ユーザープロファイル、およびシステムステータスのリアルタイム表示。",
                "color": discord.Color.blue()
            }
            
        # 2. ORA API ダッシュボード (1467111844178169999)
        if cfg.config_ui_notify_id:
            mapping[cfg.config_ui_notify_id] = {
                "title": "🚀 ORA API ダッシュボード",
                "url": f"{dash_cf}/dashboard",
                "desc": "システム全体のAPI利用状況および管理インターフェース。",
                "color": discord.Color.green()
            }
            
        # 3. ORA WEB チャット (1463508481763180751)
        if cfg.web_chat_notify_id:
            mapping[cfg.web_chat_notify_id] = {
                "title": "🛡️ ORA WEB チャット",
                "url": f"{chat_cf}/", 
                "desc": "ORAとの対話用ダイレクトWebインターフェース。",
                "color": discord.Color.gold()
            }
            
        # 4. ORA WEB Control Sandbox (1467163318845440062)
        # METEOR DOMAIN STRICTLY HERE (Named Tunnel)
        if cfg.ora_web_notify_id:
            mapping[cfg.ora_web_notify_id] = {
                "title": "🛡️ ORA WEB Control Sandbox",
                "url": f"{meteor_base}/static/operator.html",
                "desc": "ブラウジングおよびリモート操作用のサンドボックス環境。",
                "color": discord.Color.purple()
            }
            
        # 5. ORA API 管理パネル (Swagger) (1463508972974903306)
        if cfg.ora_api_notify_id:
            mapping[cfg.ora_api_notify_id] = {
                "title": "🛡️ ORA API 管理パネル",
                "url": f"{dash_cf}/docs",
                "desc": "インタラクティブなAPIドキュメントおよびテストインターフェース (Swagger UI)。",
                "color": discord.Color.teal()
            }
            
        # 6. ORA ComfyUI (1467112543486214165)
        if cfg.config_page_notify_id:
            mapping[cfg.config_page_notify_id] = {
                "title": "🎨 ORA ComfyUI",
                "url": f"{comfy_cf}/",
                "desc": "画像・動画生成用のノードベースUI環境。",
                "color": discord.Color.orange()
            }

        # --- STATUS ONLY CHANNELS ---
        
        # 7. Self-Evolution System (1459561969261744270)
        if cfg.feature_proposal_channel_id:
            mapping[cfg.feature_proposal_channel_id] = {
                "title": "🛡️ Self-Evolution System",
                "url": None, # NO LINK
                "desc": "自己進化機能は正常に稼働中です。",
                "color": discord.Color.magenta()
            }
            
        # 8. System Activity Logs (1455097004433604860)
        if cfg.log_channel_id:
            mapping[cfg.log_channel_id] = {
                "title": "🛡️ System Activity Logs",
                "url": None, # NO LINK
                "desc": "システムログの監視を開始しました。",
                "color": discord.Color.dark_grey()
            }

        return mapping

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.sent_on_startup:
            # Wait longer for tunnels to stabilize and write logs
            import asyncio
            # Tunnels start with 5s gap x 4 = 20s minimum. Give 40s buffer.
            await asyncio.sleep(40)
            logger.info("🚀 Broadcasting dynamic system links and status to active channels...")
            await self._broadcast_links()
            self.sent_on_startup = True

    @app_commands.command(name="broadcast_system_links", description="Broadcasts system URLs to their respective channels.")
    @app_commands.checks.has_permissions(administrator=True)
    async def broadcast_system_links(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        results = await self._broadcast_links()
        await interaction.followup.send("Broadcast Complete:\n" + "\n".join(results))

    async def _broadcast_links(self):
        results = []
        # MUST AWAIT NOW
        link_map = await self.get_link_map()
        
        for channel_id, data in link_map.items():
            channel = self.bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception as e:
                    results.append(f"❌ Channel {channel_id}: Error {e}")
                    continue

            if hasattr(channel, 'send'):
                try:
                    title = data["title"]
                    url = data["url"]
                    desc = data["desc"]
                    color = data["color"]
                    
                    embed = discord.Embed(
                        title=title,
                        description=desc,
                        color=color
                    )
                    
                    if url:
                        embed.url = url
                        embed.add_field(name="アクセスURL", value=f"[ここをクリックして開く]({url})", inline=False)
                    else:
                        embed.set_footer(text="System Online • Monitoring Active")

                    await channel.send(embed=embed)
                    results.append(f"✅ Sent to {channel.name} ({channel_id})")
                except Exception as e:
                    results.append(f"❌ Failed to send to {channel.name}: {e}")
            else:
                 results.append(f"⚠️ Channel {channel_id} is not a text channel")
        return results

async def setup(bot: commands.Bot):
    await bot.add_cog(LinkManager(bot))
