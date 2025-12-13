import discord
import asyncio
from typing import List, Optional

# Emojis
EMOJI_LOAD = "<a:ld_load:864751547368079400>"
EMOJI_DONE = "<a:ld_accept:864751671510564885>"

class StatusManager:
    """Manages the interactive 'Thinking' status message."""
    
    def __init__(self, channel: discord.abc.Messageable):
        self.channel = channel
        self.message: Optional[discord.Message] = None
        self.steps: List[dict] = [] # List of {"label": str, "done": bool}
        self._lock = asyncio.Lock()

    async def start(self, label: str = "思考中..."):
        """Send the initial status message."""
        self.steps = [{"label": label, "done": False}]
        content = self._build_content()
        try:
            self.message = await self.channel.send(content)
        except Exception:
            pass # Ignore if permission error etc.

    async def next_step(self, label: str):
        """Mark current step as done and add a new step."""
        async with self._lock:
            if not self.message:
                return
            
            # Mark last step as done
            if self.steps:
                self.steps[-1]["done"] = True
            
            # Add new step
            self.steps.append({"label": label, "done": False})
            
            await self._update()

    async def update_current(self, label: str):
        """Update the text of the *current* running step."""
        async with self._lock:
            if not self.message or not self.steps:
                return
            
            self.steps[-1]["label"] = label
            await self._update()

    async def finish(self):
        """Mark all as done and delete the message."""
        async with self._lock:
            if not self.message:
                return
            
            try:
                await self.message.delete()
            except Exception:
                pass
            self.message = None

    async def _update(self):
        """Edit the message with current steps."""
        if not self.message:
            return
        
        content = self._build_content()
        try:
            await self.message.edit(content=content)
        except Exception:
            pass

    def _build_content(self) -> str:
        lines = []
        for step in self.steps:
            icon = EMOJI_DONE if step["done"] else EMOJI_LOAD
            lines.append(f"{icon} {step['label']}")
        return "\n".join(lines)

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
            color=0x4285F4, # Google Blue
            timestamp=discord.utils.utcnow()
        )
        
        # Add Top 3-5 Results
        for i, res in enumerate(results[:5]):
            title = res.get("title", "No Title")
            link = res.get("link", "")
            snippet = res.get("snippet", "")
            
            # Format: [Title](Link)
            #         Snippet...
            field_val = f"{snippet[:100]}..." if len(snippet) > 100 else snippet
            embed.add_field(
                name=f"{i+1}. {title}",
                value=f"[{field_val}]({link})",
                inline=False
            )
            
        embed.set_footer(text="Powered by Google Search")
        return embed

    @staticmethod
    def create_info_embed(title: str, description: str, fields: Optional[dict] = None, color: int = 0x95A5A6) -> discord.Embed:
        """Create a generic info card."""
        embed = discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=color,
            timestamp=discord.utils.utcnow()
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
            color=0xE74C3C, # News Red
            timestamp=discord.utils.utcnow()
        )
        
        for i, art in enumerate(articles[:5]):
             embed.add_field(
                 name=f"{i+1}. {art['title']}",
                 value=f"[記事を読む]({art['url']})",
                 inline=False
             )
        
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
            color=0x7289DA, # Blurple or Brand Color
            timestamp=discord.utils.utcnow()
        )
        
        if footer_text:
            embed.set_footer(text=footer_text)
            
        return embed

