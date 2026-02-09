async def execute(args: dict, message, bot=None) -> str:
    """
    Executes system control actions.
    """
    action = args.get("action")
    value = args.get("value")
    client = bot or getattr(message, "client", None)
    
    # Permission Check
    ora_cog = client.get_cog("ORACog") if client else None
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "creator"):
             return "PERMISSION_DENIED"
    
    sys_cog = client.get_cog("SystemCog") if client else None
    if not sys_cog:
        return "SystemCog offline."
        
    res = await sys_cog.execute_tool(message.author.id, action, value)
    status = "✅" if res.get("status") else "❌"
    return f"{status} {res.get('message')}"
