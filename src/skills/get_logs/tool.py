from src.services.log_service import LogService


async def execute(args: dict, message, bot=None) -> str:
    """
    Retrieves system logs.
    """
    lines = int(args.get("lines", 50))
    # Initialize LogService with the bot's config found in message.client
    client = bot or getattr(message, "client", None)
    
    # Permission Check
    ora_cog = client.get_cog("ORACog") if client else None
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "creator"):
             return "PERMISSION_DENIED"
    
    if not client or not getattr(client, "config", None):
        return "Error: bot config unavailable."

    log_service = LogService(client.config)
    return log_service.get_logs(lines)
