import logging

logger = logging.getLogger(__name__)

class ChatSkill:
    """Skill for interacting with Discord Chat History directly."""
    
    def __init__(self, bot):
        self.bot = bot

    async def read_recent_messages(self, channel_id: int, limit: int = 20) -> str:
        """
        Fetch the most recent messages from a channel to understand context.
        Includes messages from other bots.
        """
        try:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                # Try fetching if not in cache
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    return "Error: Channel not found or inaccessible."

            if not hasattr(channel, "history"):
                return "Error: This channel type does not support history reading."

            logger.info(f"ChatSkill: Reading last {limit} messages from {channel.name} ({channel_id})")
            
            messages = []
            async for msg in channel.history(limit=limit):
                author_name = msg.author.display_name
                if msg.author.bot:
                    author_name += " [BOT]"
                
                # Format: [Time] User: Content
                timestamp = msg.created_at.strftime("%H:%M:%S")
                content = msg.content
                
                # Add attachment info if any
                if msg.attachments:
                    att_info = ", ".join([a.filename for a in msg.attachments])
                    content += f" (Attachments: {att_info})"
                
                messages.append(f"[{timestamp}] {author_name}: {content}")
            
            # Reverse to chronological order (oldest -> newest)
            messages.reverse()
            
            history_text = "\n".join(messages)
            return f"### Recent Chat History (Last {limit} messages) in #{channel.name}\n\n{history_text}"

        except Exception as e:
            logger.error(f"ReadHistory Error: {e}")
            return f"Error reading history: {str(e)}"
