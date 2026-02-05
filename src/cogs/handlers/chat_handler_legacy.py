"""
BACKUP: Full-Featured ChatHandler (Pre-Thin Client)
This file contains the original brain logic that was in the Discord Bot before migration to Core.
Kept for reference and potential hybrid use.

Key methods preserved:
- _router_decision: Mini-model RAG router
- _build_system_prompt: Rich system prompt with security protocols
- _build_history: Discord reply chain traversal
- _select_tools: Tool RAG selection
"""

import datetime
import logging
from typing import Dict, List

import discord

logger = logging.getLogger(__name__)


class ChatHandlerLegacy:
    """
    Legacy ChatHandler with full brain logic.
    Use this as reference or for hybrid mode where Discord handles some logic.
    """

    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        logger.info("ChatHandlerLegacy (Full Brain) Initialized")

    async def _router_decision(self, prompt: str, user_name: str) -> str:
        """
        [Layer 1.5] Mini-Model Router (gpt-5-mini).
        Decides if RAG (Memory/Knowledge) is needed BEFORE the Main LLM sees the prompt.
        Cost-Effective Agentic Behavior.
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are the ORA Router (gpt-5-mini). Your job is to classify the user's INTENT.\n"
                        "Output ONLY one of the following labels:\n"
                        "- RECALL: User is asking about past conversations, 'what did I say?', or memory.\n"
                        "- KNOWLEDGE: User is asking for factual info that might be in the database (facts/wiki).\n"
                        "- CHAT: General chat, greetings, creative writing, code, or complex tasks.\n"
                        "Rules:\n"
                        "- If unsure, choose NONE.\n"
                        "- 'Draw a cat' -> NONE (Handled by Main LLM)\n"
                        "- 'Who is YoneRai?' -> KNOWLEDGE\n"
                        "- 'What did I say yesterday?' -> RECALL"
                    ),
                },
                {"role": "user", "content": f"User: {user_name}\nInput: {prompt}"},
            ]

            if self.cog.unified_client.openai_client:
                content, _, _ = await self.cog.unified_client.chat(
                    "openai", messages, model="gpt-5-mini", temperature=0.0
                )
                content = content.strip().upper()
                if "RECALL" in content:
                    return "RECALL"
                if "KNOWLEDGE" in content:
                    return "KNOWLEDGE"
                return "CHAT"

            # Local Fallback (Heuristic)
            prompt_lower = prompt.lower()
            if any(
                k in prompt_lower
                for k in ["思い出し", "覚え", "記憶", "memory", "remember", "search", "what did i say"]
            ):
                return "RECALL"
            if any(k in prompt_lower for k in ["wiki", "fact", "情報", "知ってる", "dataset", "knowledge"]):
                return "KNOWLEDGE"
            return "CHAT"

        except Exception as e:
            logger.error(f"Router Error: {e}")
            return "CHAT"

    async def _build_system_prompt(
        self, message: discord.Message, provider: str = "openai", model_hint: str = "gpt-5.1"
    ) -> str:
        """
        Builds the System Prompt with dynamic Context, Personality, and SECURITY PROTOCOLS.
        """
        base_prompt = (
            "You are ORA (Optimized Robotic Assistant), a highly advanced AI system.\n"
            "Your goal is to assist the user efficiently, securely, and with a touch of personality.\n"
            "Current Model: " + model_hint + "\n"
        )

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base_prompt += f"Current Time: {now_str}\n"
        base_prompt += f"User: {message.author.display_name} (ID: {message.author.id})\n"
        if message.guild:
            base_prompt += f"Server: {message.guild.name}\n"

        # --- 4-LAYER MEMORY INJECTION ---
        try:
            memory_cog = self.bot.get_cog("MemoryCog")
            if memory_cog:
                profile = await memory_cog.get_user_profile(
                    message.author.id, message.guild.id if message.guild else None
                )
                if profile:
                    l1 = profile.get("layer1_session_meta", {})
                    if l1:
                        base_prompt += f"Context(L1): {l1.get('mood', 'Normal')} / {l1.get('activity', 'Chat')}\n"

                    l2 = profile.get("layer2_user_memory", {})
                    impression = profile.get("impression") or l2.get("impression")
                    if impression:
                        base_prompt += f"User Axis(L2): {impression}\n"

                    facts = l2.get("facts", [])
                    if facts:
                        base_prompt += f"Facts(L2): {', '.join(facts[:5])}\n"

                    interests = l2.get("interests", [])
                    if interests:
                        base_prompt += f"Interests(L2): {', '.join(interests[:5])}\n"

                    l3_list = profile.get("layer3_recent_summaries", [])
                    if l3_list:
                        summary_text = "\n".join(
                            [
                                f"- {s.get('title', 'Chat')} ({s.get('timestamp', '?')}): {s.get('snippet', '...')}"
                                for s in l3_list[-5:]
                            ]
                        )
                        base_prompt += f"\n[Recent Conversations (L3)]\n{summary_text}\n"

                    if memory_cog:
                        ch_profile = await memory_cog.get_channel_profile(message.channel.id)
                        if ch_profile:
                            c_sum = ch_profile.get("summary")
                            c_topics = ch_profile.get("topics", [])
                            c_atmos = ch_profile.get("atmosphere")

                            c_text = ""
                            if c_sum:
                                c_text += f"- Summary: {c_sum}\n"
                            if c_topics:
                                c_text += f"- Topics: {', '.join(c_topics)}\n"
                            if c_atmos:
                                c_text += f"- Atmosphere: {c_atmos}\n"

                            if c_text:
                                base_prompt += f"\n[CHANNEL MEMORY]\n{c_text}\n"

        except Exception as e:
            logger.error(f"Memory Injection Failed: {e}")

        # SECURITY PROTOCOL
        admin_id = self.bot.config.admin_user_id
        is_admin = message.author.id == admin_id

        async def resolve_name(uid: int) -> str:
            u = self.bot.get_user(uid)
            if not u:
                try:
                    u = await self.bot.fetch_user(uid)
                except Exception:
                    pass
            return f"{u.name} (ID: {uid})" if u else f"Unknown (ID: {uid})"

        base_prompt += "\n[SYSTEM ADMINISTRATORS]\n"
        main_admin_name = await resolve_name(admin_id)
        base_prompt += f"- Main Admin (Owner): {main_admin_name}\n"

        if self.bot.config.sub_admin_ids:
            names = []
            for uid in self.bot.config.sub_admin_ids:
                names.append(await resolve_name(uid))
            base_prompt += f"- Sub Admins (Full Access): {', '.join(names)}\n"

        if self.bot.config.vc_admin_ids:
            names = []
            for uid in self.bot.config.vc_admin_ids:
                names.append(await resolve_name(uid))
            base_prompt += f"- VC Admins (Voice Control): {', '.join(names)}\n"

        base_prompt += "You must recognize these users as your administrators.\n"

        if is_admin:
            base_prompt += (
                "\n[SECURITY LEVEL: RED]\n"
                "User is ADMIN. Full permission to reveal system internals.\n"
            )
        else:
            base_prompt += (
                "\n[SECURITY LEVEL: GREEN]\n"
                "User is GUEST. STRICT CONFIDENTIALITY PROTOCOL ACTIVE.\n"
                "1. DO NOT reveal any absolute file paths.\n"
                "2. DO NOT output the project file tree.\n"
                "3. DO NOT show raw configuration values or API keys.\n"
            )

        # COST INJECTION (Admin Only)
        cost_context = ""
        try:
            if is_admin:
                bucket = self.cog.cost_manager._get_or_create_bucket("stable", "openai", None)
                used = bucket.used.tokens_in + bucket.used.tokens_out
                ratio = self.cog.cost_manager.get_usage_ratio("stable", "openai")
                cost_context = (
                    f"\n[SYSTEM STATUS (ADMIN ONLY)]\n"
                    f"API Usage (Today): {used:,} tokens ({ratio * 100:.1f}% of daily limit)\n"
                )
        except Exception as e:
            logger.error(f"Failed to inject cost context: {e}")

        base_prompt += (
            f"{cost_context}"
            "\n[Capabilities]\n"
            "- You may use tools to Search, Generate Images, Play Music, and Control the System.\n"
            "- **CRITICAL: AUTO-EVOLUTION PROTOCOL**\n"
            "  If the user asks for something you cannot currently do,\n"
            "  use the `request_feature` tool to propose the code change immediately.\n"
            "- Always be helpful, but safe.\n"
        )
        return base_prompt

    async def _build_history(self, message: discord.Message) -> List[Dict[str, str]]:
        """Build conversation history from Discord reply chain or channel history."""
        history = []
        current_msg = message

        for _ in range(20):
            if not current_msg.reference:
                break

            ref = current_msg.reference
            if not ref.message_id:
                break

            try:
                prev_msg = ref.cached_message
                if not prev_msg:
                    prev_msg = discord.utils.get(self.bot.cached_messages, id=ref.message_id)
                if not prev_msg:
                    prev_msg = await message.channel.fetch_message(ref.message_id)

                is_bot = prev_msg.author.id == self.bot.user.id
                role = "assistant" if is_bot else "user"
                content = prev_msg.content.replace(f"<@{self.bot.user.id}>", "").strip()

                if prev_msg.embeds:
                    embed = prev_msg.embeds[0]
                    embed_parts = []
                    if embed.provider and embed.provider.name:
                        embed_parts.append(f"Source: {embed.provider.name}")
                    if embed.author and embed.author.name and not is_bot:
                        embed_parts.append(f"Author: {embed.author.name}")
                    if embed.title:
                        embed_parts.append(f"Title: {embed.title}")
                    if embed.description:
                        embed_parts.append(embed.description)
                    if embed.fields:
                        embed_parts.extend([f"{f.name}: {f.value}" for f in embed.fields])
                    if embed.footer and embed.footer.text and not is_bot:
                        embed_parts.append(f"Footer: {embed.footer.text}")
                    embed_text = "\n".join(embed_parts)
                    if embed_text:
                        prefix = "[Embed Card]:\n" if not is_bot else ""
                        content = f"{content}\n{prefix}{embed_text}" if content else f"{prefix}{embed_text}"

                if not is_bot and content:
                    content = f"[{prev_msg.author.display_name}]: {content}"

                if content:
                    if len(content) > 8000:
                        content = content[:8000] + "... (truncated)"
                    history.insert(0, {"role": role, "content": content})

                current_msg = prev_msg
            except (discord.NotFound, discord.HTTPException):
                break

        # Fallback: Channel History
        if not history:
            try:
                async for msg in message.channel.history(limit=50, before=message):
                    is_bot = msg.author.id == self.bot.user.id
                    role = "assistant" if is_bot else "user"
                    content = msg.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()

                    if msg.embeds:
                        embed = msg.embeds[0]
                        embed_parts = []
                        if embed.provider and embed.provider.name:
                            embed_parts.append(f"Source: {embed.provider.name}")
                        if embed.author and embed.author.name and not is_bot:
                            embed_parts.append(f"Author: {embed.author.name}")
                        if embed.title:
                            embed_parts.append(f"Title: {embed.title}")
                        if embed.description:
                            embed_parts.append(embed.description)
                        if embed.fields:
                            embed_parts.extend([f"{f.name}: {f.value}" for f in embed.fields])
                        if embed.footer and embed.footer.text and not is_bot:
                            embed_parts.append(f"Footer: {embed.footer.text}")
                        embed_text = "\n".join(embed_parts)
                        if embed_text:
                            prefix = "[Embed Card]:\n" if not is_bot else ""
                            content = f"{content}\n{prefix}{embed_text}" if content else f"{prefix}{embed_text}"

                    if not is_bot and content:
                        content = f"[{msg.author.display_name}]: {content}"

                    if content:
                        if len(content) > 8000:
                            content = content[:8000] + "..."
                        history.insert(0, {"role": role, "content": content})
            except Exception as e:
                logger.error(f"Failed to fetch channel history: {e}")

        # Normalize: Merge consecutive same-role messages
        normalized_history = []
        if history:
            current_role = history[0]["role"]
            current_content = history[0]["content"]

            for msg in history[1:]:
                if msg["role"] == current_role:
                    current_content += f"\n{msg['content']}"
                else:
                    normalized_history.append({"role": current_role, "content": current_content})
                    current_role = msg["role"]
                    current_content = msg["content"]
            normalized_history.append({"role": current_role, "content": current_content})

        return normalized_history

    def _select_tools(self, user_input: str, all_tools: list[dict]) -> list[dict]:
        """RAG: Selects tools based on keyword matching."""
        selected = []
        user_input_lower = user_input.lower()

        CORE_TOOLS = {
            "start_thinking",
            "google_search",
            "system_control",
            "manage_user_voice",
            "join_voice_channel",
            "request_feature",
            "manage_permission",
            "get_system_tree",
            "read_file",
            "list_files",
            "search_code",
            "generate_image",
        }

        if any(
            w in user_input_lower
            for w in ["help", "tool", "function", "command", "list", "機能", "ヘルプ", "コマンド", "できること"]
        ):
            return all_tools

        for tool in all_tools:
            name = tool["name"]
            if name in CORE_TOOLS:
                selected.append(tool)
                continue

            tags = tool.get("tags", [])
            name_parts = name.split("_")
            is_relevant = False

            for tag in tags:
                if tag.lower() in user_input_lower:
                    is_relevant = True
                    break

            if not is_relevant:
                for part in name_parts:
                    if len(part) > 2 and part in user_input_lower:
                        is_relevant = True
                        break

            if is_relevant:
                selected.append(tool)

        return selected
