import re

import discord


async def execute(args: dict, message: discord.Message) -> str:
    """
    Manages user voice state.
    """
    # Permission Check
    ora_cog = message.client.get_cog("ORACog")
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "sub_admin"):
             return "PERMISSION_DENIED"

    target_str = args.get("target_user")
    action = args.get("action")
    if not target_str or not action: return "Missing args."
    
    guild = message.guild
    member = None
    match = re.search(r"<@!?(\d+)>", target_str)
    if match: 
        member = guild.get_member(int(match.group(1)))
    elif target_str.isdigit(): 
        member = guild.get_member(int(target_str))
    else: 
        member = discord.utils.find(lambda m: target_str.lower() in m.display_name.lower(), guild.members)
    
    if not member: return "User not found."
    
    try:
        if action == "mute_mic": 
            await member.edit(mute=True)
            return f"Muted {member.display_name}."
        elif action == "unmute_mic": 
            await member.edit(mute=False)
            return f"Unmuted {member.display_name}."
        elif action == "disconnect": 
            if member.voice: 
                await member.move_to(None)
                return f"Disconnected {member.display_name}."
            else:
                return f"{member.display_name} is not in a voice channel."
        return f"Unknown action {action}"
    except Exception as e: 
        return f"Error: {e}"
