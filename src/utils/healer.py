import logging
import traceback
import discord
from typing import Optional
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

class Healer:
    def __init__(self, bot, llm: LLMClient):
        self.bot = bot
        self.llm = llm

    async def handle_error(self, ctx, error: Exception):
        """
        Analyzes the error, sends report to specific channel, and proposes a fix.
        """
        # Target Channel for Auto-Healer
        LOG_CHANNEL_ID = 1386994311400521768
        
        # Get traceback
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(f"Healer caught error: {error}")

        # Ask LLM for analysis and patch
        try:
            prompt = f"""
            You are an expert Python debugger for a Discord Bot.
            
            Error: {str(error)}
            Traceback:
            {tb[-1500:]}
            
            Context: Command '{ctx.command}' invoked by {ctx.author}.
            
            Task:
            1. Analyze the root cause.
            2. Provide a concrete CODE FIX in a code block.
            3. If it's a simple fix, provide the git diff or replaced lines.
            
            Output Format:
            **Analysis**: [One sentence cause]
            **Fix**:
            ```python
            [Code snippet]
            ```
            """
            
            analysis = await self.llm.chat(messages=[{"role": "user", "content": prompt}], temperature=0.0)
            
            # Send to Channel
            channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if not channel:
                # Fallback to fetch if not cached
                try:
                    channel = await self.bot.fetch_channel(LOG_CHANNEL_ID)
                except Exception:
                    logger.error(f"Healer could not find channel {LOG_CHANNEL_ID}")
                    return

            if channel:
                embed = discord.Embed(title="🚑 Auto-Healer Report", color=discord.Color.red())
                embed.description = f"**Error Event Detected**\n`{str(error)}`\n\n{analysis[:1800]}"
                embed.set_footer(text=f"Invoked by {ctx.author}")
                
                await channel.send(embed=embed)
                # Ensure log is saved
                logger.info(f"Sent Healer report to {channel.name}")

        except Exception as e:
            logger.error(f"Healer failed to analyze: {e}")
