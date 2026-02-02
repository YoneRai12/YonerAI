import discord


async def execute(args: dict, message: discord.Message) -> str:
    """
    Sends a message.
    """
    # Permission Check
    ora_cog = message.client.get_cog("ORACog")
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "sub_admin"):
             return "PERMISSION_DENIED"

    content = args.get("message")
    ch_name = args.get("channel_name")
    target = message.channel
    
    if ch_name:
        found = discord.utils.find(lambda c: ch_name.lower() in c.name.lower(), message.guild.text_channels)
        if found: 
            target = found
        else: 
            return f"Channel '{ch_name}' not found."
            
    await target.send(content)
    return f"Message sent to {target.name}: {content} [SILENT_COMPLETION]"
