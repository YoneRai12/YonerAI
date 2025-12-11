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
        Analyzes the error and proposes a fix to the Admin.
        """
        admin_id = self.bot.config.admin_user_id
        if not admin_id:
            return

        # Get traceback
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        
        # Log it
        logger.error(f"Healer caught error: {error}")

        # Ask LLM for analysis and patch
        try:
            prompt = f"""
            You are an expert Python debugger. The following error occurred in a Discord Bot:
            
            Error: {str(error)}
            Traceback:
            {tb[-1000:]}
            
            Context: Command '{ctx.command}' invoked by {ctx.author}.
            
            1. Analyze the cause.
            2. Propose a code fix (diff format).
            3. Keep it concise.
            """
            
            analysis = await self.llm.chat(messages=[{"role": "user", "content": prompt}], temperature=0.0)
            
            # Send DM to Admin
            user = self.bot.get_user(admin_id)
            if not user:
                user = await self.bot.fetch_user(admin_id)
            
            if user:
                embed = discord.Embed(title="🚑 Self-Healing Proposal", color=discord.Color.red())
                embed.description = f"**Error**: `{str(error)}`\n\n**Analysis**:\n{analysis[:1000]}..."
                embed.add_field(name="Action", value="Review the code and apply the fix manually (for now).")
                
                await user.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Healer failed to analyze: {e}")
