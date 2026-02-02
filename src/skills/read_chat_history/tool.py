
import logging

import discord

logger = logging.getLogger(__name__)

async def execute(args: dict, message: discord.Message) -> str:
    limit = int(args.get("limit", 20))
    channel_id = args.get("channel_id")
    
    channel = None
    
    if channel_id:
        try:
            c_id = int(channel_id)
            if message.guild:
                channel = message.guild.get_channel(c_id)
                if not channel:
                    # Try fetch
                    try:
                        channel = await message.guild.fetch_channel(c_id)
                    except Exception:
                        pass
        except ValueError:
            return "Error: Invalid channel_id format."
    else:
        channel = message.channel
        
    if not channel:
        return "Error: Could not determine channel."

    if not hasattr(channel, "history"):
         return "Error: This channel type does not support history reading."

    try:
        logger.info(f"ChatSkill: Reading last {limit} messages from {channel.name} ({channel.id})")
        
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
        return f"Error reading history: {e}"
