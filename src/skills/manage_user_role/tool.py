import re

import discord


async def execute(args: dict, message: discord.Message) -> str:
    """
    Adds or removes roles from a user.
    """
    if not message.guild:
        return "Error: Server context required."
        
    # Permission Check
    ora_cog = message.client.get_cog("ORACog")
    if ora_cog:
        if not await ora_cog._check_permission(message.author.id, "sub_admin"):
             return "PERMISSION_DENIED"

    user_query = args.get("user_query")
    role_query = args.get("role_query")
    action = args.get("action")
    
    if not user_query or not role_query or not action:
        return "Error: Missing arguments."

    guild = message.guild
    target_members = []
    
    # Resolve User
    id_matches = re.findall(r"<@!?(\d+)>", user_query)
    if id_matches:
        for uid in id_matches:
            m = guild.get_member(int(uid))
            if m: target_members.append(m)
    else:
        if user_query.isdigit():
            m = guild.get_member(int(user_query))
            if m: target_members.append(m)
        if not target_members:
            m = discord.utils.find(lambda m: m.name == user_query or m.display_name == user_query, guild.members)
            if m: target_members.append(m)
    
    if not target_members:
        return f"Error: User '{user_query}' not found."

    # Resolve Role
    target_role = None
    role_id_match = re.search(r"<@&(\d+)>", role_query)
    if role_id_match:
        target_role = guild.get_role(int(role_id_match.group(1)))
    elif role_query.isdigit():
        target_role = guild.get_role(int(role_query))
    
    if not target_role:
        clean_role_name = role_query.replace("@", "").replace("＠", "").strip()
        target_role = discord.utils.find(lambda r: r.name.lower() == clean_role_name.lower(), guild.roles)
    
    if not target_role: return f"Error: Role '{role_query}' not found."

    if not guild.me.guild_permissions.manage_roles: return "Error: I do not have permission."
    if target_role >= guild.me.top_role: return "Error: Role is too high for me to manage."

    results = []
    for target_member in target_members:
        try:
            if action == "add":
                if target_role in target_member.roles:
                    results.append(f"{target_member.display_name}: Already has role.")
                else:
                    await target_member.add_roles(target_role, reason=f"AI Action by {message.author.display_name}")
                    results.append(f"✅ {target_member.display_name}: Added **{target_role.name}**")
            elif action == "remove":
                if target_role not in target_member.roles:
                    results.append(f"{target_member.display_name}: No role to remove.")
                else:
                    await target_member.remove_roles(target_role, reason=f"AI Action by {message.author.display_name}")
                    results.append(f"✅ {target_member.display_name}: Removed **{target_role.name}**")
        except Exception as e:
            results.append(f"❌ {target_member.display_name}: Error {e}")
    return "\n".join(results)
