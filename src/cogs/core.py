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
import asyncio
import ast
import random
from datetime import datetime, timedelta
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ..storage import Store
from ..utils.link_client import LinkClient

logger = logging.getLogger(__name__)


class CoreCog(commands.Cog):
    """Primary slash commands for the ORA bot."""

    def __init__(self, bot: commands.Bot, link_client: LinkClient, store: Store) -> None:
        self.bot = bot
        self._link_client = link_client
        self._store = store
        
        # S8-B: Inject bot for Router Alert Delivery
        try:
            from .handlers.router_monitor import router_monitor
            router_monitor.set_bot(bot)
        except ImportError:
            logger.warning("RouterHealthMonitor not found (S8 skipped).")
            
        self.status_task.start()

    async def _get_privacy(self, user_id: int) -> bool:
        """Return True if response should be ephemeral based on system_privacy."""
        # Default to private if not set
        privacy = await self._store.get_system_privacy(user_id)
        return privacy == "private"

    def cog_unload(self):  # type: ignore[override]
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
        await interaction.response.send_message(f"Pong! {latency_ms:.0f}ms", ephemeral=ephemeral)

    @app_commands.command(name="say", description="指定したメッセージを送信します。")
    @app_commands.describe(
        text="送信するメッセージ",
        ephemeral="エフェメラルで返信する場合は true",
    )
    async def say(self, interaction: discord.Interaction, text: str, ephemeral: bool = False) -> None:
        """Send back the provided message if the invoker has administrator permission."""

        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            return

        if not interaction.user.guild_permissions.administrator:
            raise app_commands.CheckFailure("管理者権限が必要です。")

        await interaction.response.send_message(text, ephemeral=ephemeral)

    @app_commands.command(name="link", description="ORAアカウントとWebダッシュボードを連携します。")
    async def link(self, interaction: discord.Interaction) -> None:
        """Generate a single-use link code."""

        await interaction.response.defer(ephemeral=True, thinking=True)
        user_id = interaction.user.id
        try:
            code = await self._link_client.request_link_code(user_id)
            
            dashboard_url = getattr(self.bot.config, "public_base_url", "http://localhost:3000")
            
            embed = discord.Embed(
                title="🔐 ORA アカウント連携",
                description=(
                    "Webダッシュボードと連携して、記憶や履歴を共有します。\n\n"
                    f"**連携コード: `{code}`**\n"
                    "有効期限: 15分間\n\n"
                    "**【手順】**\n"
                    f"1. [Webダッシュボード]({dashboard_url}/dashboard) にアクセス\n"
                    "2. Googleアカウントでログイン\n"
                    "3. 設定画面の「Discord連携」欄に上記のコードを入力してください。"
                ),
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.exception("Failed to generate link code", extra={"user_id": user_id})
            await interaction.followup.send(
                f"リンクコードの生成に失敗しました: {e}\n時間を置いて再度お試しください。",
                ephemeral=True,
            )

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

        await interaction.response.send_message(
            "\n".join(lines), ephemeral=await self._get_privacy(interaction.user.id)
        )

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

        await interaction.response.send_message(
            f"<t:{timestamp}:R> にリマインドします: 「{message}」",
            ephemeral=await self._get_privacy(interaction.user.id),
        )

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
        if len(expression) > 200 or any(c not in allowed_chars for c in expression):
            await interaction.response.send_message("使用できない文字が含まれています。", ephemeral=True)
            return
        try:
            tree = ast.parse(expression, mode="eval")

            def _eval(node: ast.AST) -> float:
                if isinstance(node, ast.Expression):
                    return _eval(node.body)
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return float(node.value)
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                    v = _eval(node.operand)
                    return v if isinstance(node.op, ast.UAdd) else -v
                if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                    left = _eval(node.left)
                    right = _eval(node.right)
                    if isinstance(node.op, ast.Add):
                        return left + right
                    if isinstance(node.op, ast.Sub):
                        return left - right
                    if isinstance(node.op, ast.Mult):
                        return left * right
                    # Div
                    return left / right
                raise ValueError("unsupported_expression")

            result = _eval(tree)
            # Display integers cleanly when possible.
            if abs(result - int(result)) < 1e-12:
                result = int(result)
            await interaction.response.send_message(
                f"{expression} = {result}", ephemeral=await self._get_privacy(interaction.user.id)
            )
        except Exception:
            await interaction.response.send_message("計算できませんでした。", ephemeral=True)

    @utility_group.command(name="dice", description="サイコロを振ります。")
    @app_commands.describe(sides="面の数 (デフォルト: 6)")
    async def utility_dice(self, interaction: discord.Interaction, sides: int = 6) -> None:
        result = random.randint(1, sides)
        await interaction.response.send_message(
            f"🎲 {result} (1-{sides})", ephemeral=await self._get_privacy(interaction.user.id)
        )

    @utility_group.command(name="userinfo", description="ユーザー情報を表示します。")
    @app_commands.describe(user="対象ユーザー")
    async def utility_userinfo(self, interaction: discord.Interaction, user: Optional[discord.User] = None) -> None:
        target = user or interaction.user
        embed = discord.Embed(title=f"{target.name}", color=target.color)
        embed.set_thumbnail(url=target.avatar.url if target.avatar else None)
        embed.add_field(name="ID", value=target.id, inline=True)
        embed.add_field(name="Created At", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=await self._get_privacy(interaction.user.id))

    @app_commands.command(name="debug_logs", description="Retrieve system logs (Admin only).")
    @app_commands.describe(
        stream="Log stream to retrieve (all, success, error, guild)", lines="Number of lines to retrieve (default: 50)"
    )
    @app_commands.default_permissions(administrator=True)
    async def debug_logs(self, interaction: discord.Interaction, stream: str = "all", lines: int = 50):
        """Retrieve recent log entries."""
        if not self._check_admin(interaction):
            return await interaction.response.send_message("Permission denied.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # Map stream to filename
        if stream == "guild":
            if not interaction.guild:
                return await interaction.followup.send("Guild logs can only be retrieved within a server.")
            log_file = os.path.join(r"L:\ORA_Logs\guilds", f"{interaction.guild.id}.log")
        elif stream == "success":
            log_file = r"L:\ORA_Logs\ora_success.log"
        elif stream == "error":
            log_file = r"L:\ORA_Logs\ora_error.log"
        else:  # default to all
            log_file = r"L:\ORA_Logs\ora_all.log"

        if not os.path.exists(log_file):
            return await interaction.followup.send(f"Log file not found: `{log_file}`")

        try:
            # Read last N lines efficiently
            # For large files, reading all lines is bad.
            # Simple tail implementation:
            with open(log_file, "rb") as f:
                # Seek to end
                f.seek(0, 2)
                file_size = f.tell()

                # If file is empty
                if file_size == 0:
                    return await interaction.followup.send("Log file is empty.")

                # Read backwards
                lines_found = 0
                block_size = 1024
                blocks = []

                # Start from end
                pointer = file_size

                while pointer > 0 and lines_found < lines:
                    read_size = min(block_size, pointer)
                    pointer -= read_size
                    f.seek(pointer)
                    block = f.read(read_size)
                    blocks.append(block)
                    lines_found += block.count(b"\n")

                # Decode and split
                text = b"".join(reversed(blocks)).decode("utf-8", errors="ignore")
                all_lines = text.splitlines()

                # Get last N lines
                result_lines = all_lines[-lines:]
                content = "\n".join(result_lines)

            # Send as file if too long
            if len(content) > 1900:
                # Create a temporary file object in memory
                from io import BytesIO

                file_obj = discord.File(BytesIO(content.encode("utf-8")), filename=f"{stream}_tail.log")
                await interaction.followup.send(f"Log Output ({stream}):", file=file_obj)
            else:
                await interaction.followup.send(f"Log Output ({stream}):\n```log\n{content}\n```")

        except Exception as e:
            logger.exception("Failed to read logs")
            await interaction.followup.send(f"Failed to read logs: {e}")

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

    @app_commands.command(name="messages", description="このチャンネルの最近のメッセージを表示します。")
    @app_commands.describe(count="表示する件数 (デフォルト10, 最大50)")
    async def messages(self, interaction: discord.Interaction, count: int = 10) -> None:
        """Fetch recent messages from the current channel."""
        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        if not hasattr(channel, "history"):
            await interaction.followup.send("このチャンネルではメッセージ履歴を取得できません。", ephemeral=True)
            return

        amount = max(1, min(50, count))
        try:
            history = [m async for m in channel.history(limit=amount)]
            history.reverse()  # Oldest first

            if not history:
                content = "メッセージが見つかりませんでした。"
            else:
                content = _format_messages(history)

            embed = discord.Embed(
                title="📝 最近のメッセージ", description=content, color=discord.Color.blue(), timestamp=datetime.now()
            )
            embed.set_footer(text=f"表示: {len(history)}件")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("メッセージ履歴を読む権限がありません。", ephemeral=True)
        except Exception as e:
            logger.exception("Failed to fetch messages")
            await interaction.followup.send(f"エラーが発生しました: {e}", ephemeral=True)


def _format_messages(messages: list[discord.Message], limit: int = 3900) -> str:
    lines = []
    total_len = 0

    for msg in messages:
        snippet = msg.content.replace("\n", " ").strip() if msg.content else ""
        if not snippet:
            extras = []
            if msg.attachments:
                extras.append(f"{len(msg.attachments)} attach")
            if msg.embeds:
                extras.append(f"{len(msg.embeds)} embeds")
            snippet = f"[{', '.join(extras)}]" if extras else "[no content]"

        # Sanitize / Truncate
        snippet = snippet.replace("`", "")  # Remove backticks
        if len(snippet) > 100:
            snippet = snippet[:97] + "..."

        author = msg.author.display_name
        ts = int(msg.created_at.timestamp())

        line = f"• <t:{ts}:t> **{author}**: {snippet}"

        if total_len + len(line) > limit:
            lines.append("...(truncated)")
            break

        lines.append(line)
        total_len += len(line) + 1

    return "\n".join(lines)
