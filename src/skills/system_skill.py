from typing import Optional

import discord

from src.services.log_service import LogService


class SystemSkill:
    def __init__(self, bot):
        self.bot = bot
        self.log_service = LogService(bot.config)

    async def get_logs(self, lines: int = 50) -> str:
        """Get recent logs."""
        return self.log_service.get_logs(lines)

    async def system_control(self, action: str, value: Optional[str] = None):
        """Execute system control actions via SystemCog."""
        sys_cog = self.bot.get_cog("SystemCog")
        if not sys_cog:
            return "SystemCog offline."
        
        # Hardcoded admin check is usually done before calling this, 
        # but system_control is Creator Only (checked by ToolHandler/ORACog)
        # We assume permission is checked by the caller (ToolHandler).
        
        # We need to simulate the message.author.id? 
        # Actually sys_cog.execute_tool takes (user_id, action, value).
        # We might need to pass the user_id from the caller.
        return "Internal Error: SystemSkill needs user context. Please update call signature." 

    async def execute(self, tool_name: str, args: dict, message: discord.Message):
        if tool_name == "get_logs":
             return await self.get_logs(int(args.get("lines", 50)))
        
        elif tool_name == "system_control":
             # Delegate to SystemCog
             sys_cog = self.bot.get_cog("SystemCog")
             if not sys_cog:
                 return "SystemCog offline."
             res = await sys_cog.execute_tool(message.author.id, args.get("action"), args.get("value"))
             status = "✅" if res.get("status") else "❌"
             return f"{status} {res.get('message')}"
        
        return None
