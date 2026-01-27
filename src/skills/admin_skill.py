import re
from typing import Optional

import discord


class AdminSkill:
    def __init__(self, bot):
        self.bot = bot

    async def execute(self, tool_name: str, args: dict, message: discord.Message) -> Optional[str]:
        if tool_name == "manage_user_role":
            return await self._handle_role_management(args, message)
        elif tool_name == "create_channel":
            return await self._handle_create_channel(args, message)
        elif tool_name == "cleanup_messages":
            return await self._handle_cleanup(args, message)
        elif tool_name == "say":
            return await self._handle_say(args, message)
        elif tool_name == "manage_user_voice":
            return await self._handle_user_voice(args, message)
        elif tool_name == "get_role_list":
            return await self._handle_get_role_list(message)
        return None

    async def _handle_role_management(self, args: dict, message: discord.Message) -> str:
        if not message.guild:
            return "Error: Server context required."
        user_query = args.get("user_query")
        role_query = args.get("role_query")
        action = args.get("action")
        
        if not user_query or not role_query or not action:
            return "Error: Missing arguments."

        guild = message.guild
        target_members = []
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

    async def _handle_create_channel(self, args: dict, message: discord.Message) -> str:
        if not message.guild: return "Error: Server context required."
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

    async def _handle_cleanup(self, args: dict, message: discord.Message) -> str:
        count = int(args.get("count", 10))
        deleted = await message.channel.purge(limit=min(100, max(1, count)))
        return f"🗑️ Deleted {len(deleted)} messages. [SILENT_COMPLETION]"

    async def _handle_say(self, args: dict, message: discord.Message) -> str:
        content = args.get("message")
        ch_name = args.get("channel_name")
        target = message.channel
        if ch_name:
            found = discord.utils.find(lambda c: ch_name.lower() in c.name.lower(), message.guild.text_channels)
            if found: target = found
            else: return f"Channel '{ch_name}' not found."
        await target.send(content)
        return f"Message sent to {target.name}: {content} [SILENT_COMPLETION]"

    async def _handle_user_voice(self, args: dict, message: discord.Message) -> str:
        target_str = args.get("target_user")
        action = args.get("action")
        if not target_str or not action: return "Missing args."
        
        guild = message.guild
        member = None
        match = re.search(r"<@!?(\d+)>", target_str)
        if match: member = guild.get_member(int(match.group(1)))
        elif target_str.isdigit(): member = guild.get_member(int(target_str))
        else: member = discord.utils.find(lambda m: target_str.lower() in m.display_name.lower(), guild.members)
        
        if not member: return "User not found."
        try:
            if action == "mute_mic": await member.edit(mute=True); return f"Muted {member.display_name}."
            elif action == "unmute_mic": await member.edit(mute=False); return f"Unmuted {member.display_name}."
            elif action == "disconnect": 
                if member.voice: await member.move_to(None); return f"Disconnected {member.display_name}."
            return f"Unknown action {action}"
        except Exception as e: return f"Error: {e}"

    async def _handle_get_role_list(self, message: discord.Message) -> str:
        if not message.guild: return "Guild only."
        roles = sorted(message.guild.roles, key=lambda r: r.position, reverse=True)
        lines = [f"`{r.position}` **{r.name}** (ID: {r.id})" for r in roles]
        output = "\n".join(lines)
        chunk_size = 1900
        for i in range(0, len(output), chunk_size):
            await message.reply(output[i:i+chunk_size])
        return "Role list sent. [SILENT_COMPLETION]"
