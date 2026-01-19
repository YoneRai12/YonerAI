import asyncio
import time
from typing import List, Optional

import discord


class StatusManager:
    """Manages the interactive 'Thinking' status message."""

    # Custom Emojis (User Uploaded)
    EMOJI_PROCESSING = "<a:rode:1449406298788597812>"
    EMOJI_DONE = "<a:conp:1449406158883389621>"

    def __init__(self, channel: discord.abc.Messageable):
        self.channel = channel
        self.message: Optional[discord.Message] = None
        self.steps: List[dict] = []  # List of {"label": str, "done": bool}
        self._lock = asyncio.Lock()
        self._last_update_time = 0.0
        self._update_task = None

    async def start(self, label: str = "思考中", mode: str = "normal"):
        """
        Send the initial status message.
        mode: "normal" | "override"
        """
        self.steps = [{"label": label, "done": False}]
        self.mode = mode

        embed = self._build_embed()
        try:
            self.message = await self.channel.send(embed=embed)
        except Exception:
            pass  # Ignore if permission error etc.

    async def next_step(self, label: str, force: bool = False):
        """Mark current step as done and add a new step. Set force=True for animations."""
        async with self._lock:
            if not self.message:
                return

            # Mark last step as done
            if self.steps:
                self.steps[-1]["done"] = True

            # Add new step
            self.steps.append({"label": label, "done": False})

            await self._update(force=force)

    async def update_current(self, label: str, force: bool = False):
        """Update the text of the *current* running step. Set force=True for animations."""
        async with self._lock:
            if not self.message or not self.steps:
                return

            self.steps[-1]["label"] = label
            await self._update(force=force)

    async def finish(self):
        """Mark all as done and delete the message."""
        async with self._lock:
            if not self.message:
                return

            try:
                # Instead of deleting, we might want to keep the final log if debug mode?
                # But standard behavior is delete.
                await self.message.delete()
            except Exception:
                pass
            self.message = None

    async def _update(self, force: bool = False):
        """Edit the message with current steps (Debounced)."""
        if not self.message:
            return

        now = time.time()

        # Immediate update if Forced
        if force:
            await self._force_update()
            return

        # RATE LIMIT PREVENTER: Max 1 update per 2.0 seconds
        if now - self._last_update_time < 2.0:
            # If a task is already waiting to update, let it handle it.
            if self._update_task and not self._update_task.done():
                return

            # Create a delayed update task
            async def delayed():
                await asyncio.sleep(2.0 - (time.time() - self._last_update_time))
                await self._force_update()

            self._update_task = asyncio.create_task(delayed())
            return

        await self._force_update()

    async def _force_update(self):
        """Internal immediate update."""
        if not self.message:
            return

        # Guard for deleted message
        try:
            embed = self._build_embed()
            await self.message.edit(embed=embed)
            self._last_update_time = time.time()
        except discord.NotFound:
            # Message was deleted (e.g. by finish()), stop updating
            self.message = None
        except Exception:
            pass

    def _build_embed(self) -> discord.Embed:
        # Build text description
        lines = []
        for step in self.steps:
            icon = self.EMOJI_DONE if step["done"] else self.EMOJI_PROCESSING
            # Format: icon **Label**
            lines.append(f"{icon} **{step['label']}**")

        desc = "\n".join(lines)

        # Style based on Mode
        if hasattr(self, "mode") and self.mode == "override":
            title = "🚨 SYSTEM OVERRIDE"
            color = 0xFF0000  # Red
            footer = "⚠️ 警告: セーフティ・リミッター解除中"
        else:
            title = "⚙️ System Processing"
            color = 0x2ECC71  # Green
            footer = "ORA Universal Brain"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
        )
        embed.set_footer(text=footer)
        return embed


class EmbedFactory:
    """Factory for creating consistent Discord Embeds."""

    @staticmethod
    def create_search_embed(query: str, results: List[dict]) -> discord.Embed:
        """
        Create a card for search results.
        results: List of {"title": str, "link": str, "snippet": str}
        """
        embed = discord.Embed(
            title=f"🔍 検索結果: {query}",
            color=0x4285F4,  # Google Blue
            timestamp=discord.utils.utcnow(),
        )

        # Set Thumbnail from First Result if available
        if results and "thumbnail" in results[0] and results[0]["thumbnail"]:
            embed.set_thumbnail(url=results[0]["thumbnail"])

        # Add Top 3-5 Results
        for i, res in enumerate(results[:5]):
            title = res.get("title", "No Title")
            link = res.get("link", "")
            snippet = res.get("snippet", "")

            # Format: Snippet...
            #         [🔗 サイトを見る](Link)
            field_val = f"{snippet[:150]}..." if len(snippet) > 150 else snippet
            if link:
                field_val += f"\n[🔗 サイトを見る]({link})"

            embed.add_field(name=f"{i + 1}. {title}", value=field_val, inline=False)

        embed.set_footer(text="Powered by Google Search")
        return embed

    @staticmethod
    def create_info_embed(
        title: str, description: str, fields: Optional[dict] = None, color: int = 0x95A5A6
    ) -> discord.Embed:
        """Create a generic info card."""
        embed = discord.Embed(
            title=f"ℹ️ {title}", description=description, color=color, timestamp=discord.utils.utcnow()
        )

        if fields:
            for k, v in fields.items():
                val_str = str(v)
                if len(val_str) > 1000:
                    val_str = val_str[:1000] + "..."
                embed.add_field(name=k, value=val_str, inline=True)

        return embed

    @staticmethod
    def create_news_embed(source_name: str, articles: List[dict]) -> discord.Embed:
        """
        Create a card for news.
        articles: List of {"title": str, "url": str, "image_url": str (opt)}
        """
        embed = discord.Embed(
            title=f"📰 今日のニュース ({source_name})",
            color=0xE74C3C,  # News Red
            timestamp=discord.utils.utcnow(),
        )

        for i, art in enumerate(articles[:5]):
            embed.add_field(name=f"{i + 1}. {art['title']}", value=f"[記事を読む]({art['url']})", inline=False)

        # Set image from first article if available
        if articles and "image_url" in articles[0] and articles[0]["image_url"]:
            embed.set_image(url=articles[0]["image_url"])

        return embed

    @staticmethod
    def create_chat_embed(content: str, footer_text: Optional[str] = None) -> discord.Embed:
        """
        Create a card for normal chat responses.
        """
        # Truncate if too long (Embed limit is 4096)
        if len(content) > 4000:
            content = content[:4000] + "..."

        embed = discord.Embed(
            description=content,
            color=0x7289DA,  # Blurple or Brand Color
            timestamp=discord.utils.utcnow(),
        )

        if footer_text:
            embed.set_footer(text=footer_text)

        return embed
