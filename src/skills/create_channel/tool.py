import re

import discord


async def execute(args: dict, message: discord.Message) -> str:
    """
    Creates a new channel.
    """
    if not message.guild: return "Error: Server context required."
    
    # Permission Check
    ora_cog = message.client.get_cog("ORACog")
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "sub_admin"):
             return "PERMISSION_DENIED"

    name = args.get("name")
    channel_type = args.get("channel_type", "voice")
    private = args.get("private", False)
    users_to_add = args.get("users_to_add", "")
    
    guild = message.guild
    overwrites = {}
    if private:
        overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False, connect=False, view_channel=False)
        overwrites[guild.me] = discord.PermissionOverwrite(read_messages=True, connect=True, view_channel=True, manage_channels=True)
        overwrites[message.author] = discord.PermissionOverwrite(read_messages=True, connect=True, view_channel=True, manage_channels=True)
        if users_to_add:
             ids = re.findall(r"\d{17,20}", users_to_add)
             for uid in ids:
                 target = guild.get_member(int(uid)) or guild.get_role(int(uid))
                 if target: overwrites[target] = discord.PermissionOverwrite(read_messages=True, connect=True, view_channel=True)
    
    try:
        if channel_type == "voice":
            ch = await guild.create_voice_channel(name, overwrites=overwrites)
        else:
            ch = await guild.create_text_channel(name, overwrites=overwrites)
        return f"✅ Created {channel_type} channel: {ch.mention}"
    except Exception as e:
        return f"Error creating channel: {e}"
