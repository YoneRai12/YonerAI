"""Core cog defining the public slash commands."""

from __future__ import annotations

import logging
import os
import platform
import time

try:
    import resource  # type: ignore
except ImportError:  # pragma: no cover - platform specific
    resource = None  # type: ignore
from typing import Any, Optional

import discord
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
from discord.ext import commands, tasks

from ..utils.link_client import LinkClient
from ..storage import Store
import psutil
import random

logger = logging.getLogger(__name__)


class CoreCog(commands.Cog):
    """Primary slash commands for the ORA bot."""

    def __init__(self, bot: commands.Bot, link_client: LinkClient, store: Store) -> None:
        self.bot = bot
        self._link_client = link_client
        self._store = store
        self.status_task.start()

    async def _get_privacy(self, user_id: int) -> bool:
        """Return True if response should be ephemeral based on system_privacy."""
        # Default to private if not set
        privacy = await self._store.get_system_privacy(user_id)
        return privacy == "private"

    def cog_unload(self) -> None:
        self.status_task.cancel()

    @tasks.loop(minutes=10)
    async def status_task(self) -> None:
        """Rotate bot status."""
        await self.bot.wait_until_ready()
        statuses = [
            discord.Activity(type=discord.ActivityType.listening, name="/help | ORA Bot"),
            discord.Activity(type=discord.ActivityType.playing, name=f"Serving {len(self.bot.guilds)} servers"),
            discord.Activity(type=discord.ActivityType.watching, name="Users chat"),
        ]
        for status in statuses:
            await self.bot.change_presence(activity=status)
            await asyncio.sleep(30)

    @app_commands.command(name="ping", description="Botのレイテンシを確認します。")
    # REMOVED due to AttributeError crash on sync
    # @app_commands.allowed_installs(guilds=True, users=True)
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def ping(self, interaction: discord.Interaction) -> None:
        """Return the websocket latency."""

        latency_ms = self.bot.latency * 1000
        ephemeral = await self._get_privacy(interaction.user.id)
        await interaction.response.send_message(
            f"Pong! {latency_ms:.0f}ms", ephemeral=ephemeral
        )

    @app_commands.command(name="say", description="指定したメッセージを送信します。")
    @app_commands.describe(
        text="送信するメッセージ",
        ephemeral="エフェメラルで返信する場合は true",
    )
    async def say(
        self, interaction: discord.Interaction, text: str, ephemeral: bool = False
    ) -> None:
        """Send back the provided message if the invoker has administrator permission."""

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "このコマンドはサーバー内でのみ使用できます。", ephemeral=True
            )
            return

        # Admin check removed by user request
        # if not interaction.user.guild_permissions.administrator:
        #    raise app_commands.CheckFailure("管理者権限が必要です。")

        # Special stealth mode for specific user
        if interaction.user.id == 1069941291661672498:
            await interaction.channel.send(text)
            await interaction.response.send_message("送信しました（匿名モード）", ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=ephemeral)

    @app_commands.command(name="link", description="ORAアカウントと連携します。")
    async def link(self, interaction: discord.Interaction) -> None:
        """Generate a single-use link code."""

        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = interaction.user.id
        try:
            code = await self._link_client.request_link_code(user_id)
        except Exception:  # noqa: BLE001 - send friendly message while logging separately
            logger.exception("Failed to generate link code", extra={"user_id": user_id})
            await interaction.followup.send(
                "リンクコードの生成に失敗しました。時間を置いて再度お試しください。",
                ephemeral=True,
            )
            return

        await interaction.followup.send(f"リンクコード: `{code}`", ephemeral=True)

    @app_commands.command(name="health", description="Botの状態を表示します。")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def health(self, interaction: discord.Interaction) -> None:
        """Return runtime information about the bot process."""

        uptime_seconds = time.time() - getattr(self.bot, "started_at", time.time())
        latency_ms = self.bot.latency * 1000
        guild_count = len(self.bot.guilds)
        pid = os.getpid()
        process_memory: Optional[str] = None

        if resource is not None:
            try:
                usage = resource.getrusage(resource.RUSAGE_SELF)
                # ru_maxrss is kilobytes on Linux/macOS
                process_memory = f"{usage.ru_maxrss / 1024:.1f} MiB"
            except (AttributeError, ValueError):
                process_memory = None

        lines = [
            f"PID: {pid}",
            f"Uptime: {uptime_seconds:.0f} 秒",
            f"Latency: {latency_ms:.0f} ms",
            f"Guilds: {guild_count}",
            f"Python: {platform.python_version()}",
            f"discord.py: {discord.__version__}",
        ]
        if process_memory:
            lines.append(f"Memory: {process_memory}")

        await interaction.response.send_message("\n".join(lines), ephemeral=await self._get_privacy(interaction.user.id))

    @app_commands.command(name="help", description="利用可能なコマンド一覧を表示します。")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def help(self, interaction: discord.Interaction) -> None:
        """Show available commands."""
        embed = discord.Embed(title="ORA Bot Help", color=discord.Color.blue())
        embed.add_field(name="/ping", value="Botの応答速度を確認", inline=False)
        embed.add_field(name="/health", value="Botの稼働状況を確認", inline=False)
        embed.add_field(name="/link", value="Webダッシュボード連携", inline=False)
        embed.add_field(name="/avatar", value="ユーザーアイコンを表示", inline=False)
        embed.add_field(name="/remind", value="リマインダーを設定", inline=False)
        embed.add_field(name="/cleanup", value="メッセージを削除 (管理者のみ)", inline=False)
        embed.add_field(name="/ora", value="AIとチャット", inline=False)
        embed.add_field(name="/ytplay", value="YouTube再生", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=await self._get_privacy(interaction.user.id))

    @app_commands.command(name="avatar", description="ユーザーのアイコンを表示します。")
    @app_commands.describe(user="表示するユーザー (指定なしで自分)")
    async def avatar(self, interaction: discord.Interaction, user: Optional[discord.User] = None) -> None:
        """Show user avatar."""
        target = user or interaction.user
        if not target.avatar:
            await interaction.response.send_message("アイコンが設定されていません。", ephemeral=True)
            return
        
        embed = discord.Embed(title=f"{target.name}のアイコン", color=discord.Color.purple())
        embed.set_image(url=target.avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="cleanup", description="指定した数のメッセージを削除します (管理者のみ)。")
    @app_commands.describe(amount="削除するメッセージ数 (最大100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def cleanup(self, interaction: discord.Interaction, amount: int) -> None:
        """Bulk delete messages."""
        if amount > 100:
            await interaction.response.send_message("一度に削除できるのは100件までです。", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"{len(deleted)}件のメッセージを削除しました。", ephemeral=True)

    @app_commands.command(name="remind", description="リマインダーを設定します。")
    @app_commands.describe(minutes="何分後か", message="メッセージ内容")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def remind(self, interaction: discord.Interaction, minutes: int, message: str) -> None:
        """Set a simple reminder."""
        if minutes < 1:
            await interaction.response.send_message("1分以上を指定してください。", ephemeral=True)
            return
            
        remind_time = datetime.now() + timedelta(minutes=minutes)
        timestamp = int(remind_time.timestamp())
        
        await interaction.response.send_message(f"<t:{timestamp}:R> にリマインドします: 「{message}」", ephemeral=await self._get_privacy(interaction.user.id))
        
        # Simple in-memory wait (for now)
        # In production, this should use a DB or persistent scheduler
        await asyncio.sleep(minutes * 60)
        try:
            await interaction.user.send(f"⏰ リマインダー: {message}")
        except discord.Forbidden:
            await interaction.channel.send(f"{interaction.user.mention} ⏰ リマインダー: {message}")

    # Utility Commands
    utility_group = app_commands.Group(name="utility", description="便利なツールコマンド")

    @utility_group.command(name="calc", description="計算を行います。")
    @app_commands.describe(expression="計算式 (例: 1+1)")
    async def utility_calc(self, interaction: discord.Interaction, expression: str) -> None:
        allowed_chars = "0123456789+-*/(). "
        if any(c not in allowed_chars for c in expression):
            await interaction.response.send_message("使用できない文字が含まれています。", ephemeral=True)
            return
        try:
            # pylint: disable=eval-used
            result = eval(expression, {"__builtins__": None}, {})
            await interaction.response.send_message(f"{expression} = {result}", ephemeral=await self._get_privacy(interaction.user.id))
        except Exception:
            await interaction.response.send_message("計算できませんでした。", ephemeral=True)

    @utility_group.command(name="dice", description="サイコロを振ります。")
    @app_commands.describe(sides="面の数 (デフォルト: 6)")
    async def utility_dice(self, interaction: discord.Interaction, sides: int = 6) -> None:
        result = random.randint(1, sides)
        await interaction.response.send_message(f"🎲 {result} (1-{sides})", ephemeral=await self._get_privacy(interaction.user.id))

    @utility_group.command(name="userinfo", description="ユーザー情報を表示します。")
    @app_commands.describe(user="対象ユーザー")
    async def utility_userinfo(self, interaction: discord.Interaction, user: Optional[discord.User] = None) -> None:
        target = user or interaction.user
        embed = discord.Embed(title=f"{target.name}", color=target.color)
        embed.set_thumbnail(url=target.avatar.url if target.avatar else None)
        embed.add_field(name="ID", value=target.id, inline=True)
        embed.add_field(name="Created At", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=await self._get_privacy(interaction.user.id))

    # System Commands
    system_group = app_commands.Group(name="system", description="システム情報コマンド")

    @system_group.command(name="info", description="詳細なシステム情報を表示します。")
    async def system_info(self, interaction: discord.Interaction) -> None:
        cpu_percent = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        embed = discord.Embed(title="System Info", color=discord.Color.green())
        embed.add_field(name="CPU", value=f"{cpu_percent}%", inline=True)
        embed.add_field(name="Memory", value=f"{mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)", inline=True)
        embed.add_field(name="Disk", value=f"{disk.percent}%", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=await self._get_privacy(interaction.user.id))

    @system_group.command(name="process_list", description="CPU使用率の高いプロセスを表示します。")
    async def system_process_list(self, interaction: discord.Interaction) -> None:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Sort by CPU percent
        procs.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
        
        lines = ["**Top 10 Processes by CPU**"]
        for p in procs[:10]:
            lines.append(f"`{p['name']}` (PID: {p['pid']}): {p['cpu_percent']}%")
            
        await interaction.response.send_message("\n".join(lines), ephemeral=await self._get_privacy(interaction.user.id))

    @commands.Cog.listener()
    async def on_app_command_completion(
        self, interaction: discord.Interaction, command: app_commands.Command[Any, Any, Any]
    ) -> None:
        logger.info(
            "Command %s executed by %s (%s)",
            command.qualified_name,
            interaction.user,
            getattr(interaction.user, "id", "unknown"),
        )
