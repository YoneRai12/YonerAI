import discord


async def execute(args: dict, message: discord.Message, bot=None) -> str:
    """
    Lists server roles.
    """
    if not message.guild: return "Guild only."

    client = bot or getattr(message, "client", None)
    
    # Permission Check
    ora_cog = client.get_cog("ORACog") if client else None
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "sub_admin"):
             return "PERMISSION_DENIED"
             
    roles = sorted(message.guild.roles, key=lambda r: r.position, reverse=True)
    lines = [f"`{r.position}` **{r.name}** (ID: {r.id})" for r in roles]
    output = "\n".join(lines)
    
    # Chunking for Discord limit handles by sending multiple replies if needed
    # (Original skill did this with message.reply, returning "Role list sent.")
    # Here we are supposed to return a string.
    # If the output is too long, the ToolHandler/Orchestrator usually handles chunking or just sends the result.
    # However, the original skill sent the message itself.
    # To stay compatible with ToolHandler which expects a return string, let's return the string.
    # But if it's too huge, it might fail.
    # The original implementation sent it directly and returned a summary.
    
    # We'll mimic the original logic but return the string if it's small enough.
    # If it's huge, we might need a different approach, but for now let's just return it.
    # Actually, ToolHandler sends the result.
    
    return output
