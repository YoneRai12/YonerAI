from src.services.log_service import LogService


async def execute(args: dict, message) -> str:
    """
    Retrieves system logs.
    """
    lines = int(args.get("lines", 50))
    # Initialize LogService with the bot's config found in message.client
    
    # Permission Check
    ora_cog = message.client.get_cog("ORACog")
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "creator"):
             return "PERMISSION_DENIED"
    
    log_service = LogService(message.client.config)
    return log_service.get_logs(lines)
