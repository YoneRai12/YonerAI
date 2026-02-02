import discord


async def execute(args: dict, message: discord.Message) -> str:
    """
    Deletes messages.
    """
    # Permission Check
    ora_cog = message.client.get_cog("ORACog")
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "sub_admin"):
             return "PERMISSION_DENIED"
             
    count = int(args.get("count", 10))
    deleted = await message.channel.purge(limit=min(100, max(1, count)))
    return f"🗑️ Deleted {len(deleted)} messages. [SILENT_COMPLETION]"
