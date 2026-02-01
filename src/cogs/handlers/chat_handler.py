import asyncio
import datetime
import logging
from typing import Optional

import discord

from src.cogs.handlers.tool_selector import ToolSelector
from src.utils.core_client import core_client

logger = logging.getLogger(__name__)


class ChatHandler:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.tool_selector = ToolSelector(self.bot)
        logger.info("ChatHandler v3.9.2 (RAG Enabled) Initialized")

    async def handle_prompt(
        self,
        message: discord.Message,
        prompt: str,
        existing_status_msg: Optional[discord.Message] = None,
        is_voice: bool = False,
        force_dm: bool = False,
    ) -> None:
        """
        [Thin Client] Process a user message by delegating to ORA Core.
        Discord handles UI (Status, Voice, Embeds) while Core handles Brain.
        """
        from src.utils.ui import EmbedFactory, StatusManager

        # 1. Initialize StatusManager
        status_manager = StatusManager(message.channel, existing_message=existing_status_msg)
        await status_manager.start("📡 ORA Core Brain へ接続中...")

        # 2. Determine Context Binding
        kind = "channel"
        ext_id = f"{message.guild.id}:{message.channel.id}" if message.guild else f"dm:{message.author.id}"
        
        if not message.guild:
            kind = "dm"
        elif hasattr(message.channel, "parent_id") and message.channel.parent_id:
            kind = "thread"
            ext_id = f"{message.guild.id}:{message.channel.parent_id}:{message.channel.id}"

        context_binding = {
            "provider": "discord",
            "kind": kind,
            "external_id": ext_id
        }

        try:
            # 2.5 Build Rich Client Context for Brain
            client_context = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "server_name": message.guild.name if message.guild else "Direct Message",
                "guild_id": str(message.guild.id) if message.guild else None,
                "channel_id": str(message.channel.id),
                "channel_name": message.channel.name if hasattr(message.channel, "name") else "DM",
                "is_admin": message.author.guild_permissions.administrator if message.guild else True
            }

            # 3. Call Core API
            # [MEMORY INJECTION] Fetch User Profile
            memory_context = ""
            try:
                memory_cog = self.cog.bot.get_cog("MemoryCog")
                if memory_cog:
                    # Use a timeout to prevent hanging if file lock issue
                    user_profile = await asyncio.wait_for(
                        memory_cog.get_user_profile(message.author.id, message.guild.id if message.guild else None),
                        timeout=1.0
                    )
                    
                    if user_profile:
                        # Extract key info
                        name = user_profile.get("name", message.author.display_name)
                        impression = user_profile.get("impression", "None")
                        traits = ", ".join(user_profile.get("traits", []))
                        
                        memory_context = f"""
[USER PROFILE]
Name: {name}
Impression: {impression}
Traits: {traits}
"""
            except Exception as e:
                logger.warning(f"Memory Fetch Failed: {e}")

            # [SOURCE INJECTION] Explicitly state this is Discord
            system_context = f"""
[SOURCE: DISCORD]
[SERVER: {message.guild.name if message.guild else 'Direct Message'}]
[CHANNEL: {message.channel.name if hasattr(message.channel, 'name') else 'DM'}]
[INSTRUCTION: If the user mentions an SNS profile (e.g., '〜のX', '〜のGithub'), YOU MUST USE 'web_jump_to_profile' with the handle. NEVER guess generic URLs like 'https://x.com/' or 'https://github.com/'.]
[SECURITY WARNING: You are running on a hosted server. NEVER screenshot or display pages that reveal the HOST SERVER's Global IP Address (e.g. 'What is my IP' sites). If the user asks for 'my IP', explain that you cannot show the server's IP for security reasons.]
[AGENT PROTOCOL: DEEP RESEARCH]
If the user asks to "research" (調べて), "investigate" (調査して), or "summarize" (要約して) a topic:
1. USE 'web_search' to gather information from multiple sources (Web, Note, etc).
2. VERIFY the information (cross-reference).
3. SUMMARIZE findings with citations. Do NOT just copy-paste the first search result.
{memory_context}
"""
            # [DEVICE AWARENESS]
            is_mobile = False
            if message.guild and isinstance(message.author, discord.Member):
                if message.author.is_on_mobile():
                    is_mobile = True
            
            if is_mobile:
                system_context += "\n[DEVICE: MOBILE] User is on a mobile device. Keep responses CONCISE and avoid complex formatting."

            # Prepend to prompt
            full_prompt = system_context.strip() + "\n\n" + prompt

            # [CONTEXT INJECTION] Referenced Message (Reply)
            if message.reference:
                try:
                    if message.reference.cached_message:
                        ref_msg = message.reference.cached_message
                    else:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    
                    if ref_msg and ref_msg.content:
                         full_prompt += f"\n\n[REPLYING TO MESSAGE (Author: {ref_msg.author.display_name})]:\n{ref_msg.content}"
                         for embed in ref_msg.embeds:
                             if embed.url: full_prompt += f"\n[EMBED URL]: {embed.url}"
                except Exception as e:
                    logger.warning(f"Failed to fetch referenced message: {e}")

            # Prepare attachments
            attachments = []
            for att in message.attachments:
                attachments.append({"type": "image_url", "url": att.url})
            
            # Send Request (Initial Handshake)
            # Fetch Context-Aware Tools (Discord Only)
            discord_tools = self.cog.get_context_tools("discord")

            # [RAG ROUTER] Analyze Intent & Select Tools
            # This reduces context usage and improves accuracy
            await status_manager.update_current("🔍 Intent Analysis (RAG)...")
            
            # [Clawdbot Feature] Vector Memory Retrieval (User + Guild Shared)
            rag_context = ""
            if hasattr(self.bot, "vector_memory") and self.bot.vector_memory:
                guild_id_str = str(message.guild.id) if message.guild else None
                memories = await self.bot.vector_memory.search_memory(
                    query= prompt,
                    user_id=str(message.author.id),
                    guild_id=guild_id_str,
                    limit=3
                )
                if memories:
                    rag_context = "\n[Relevant Past Memories]:\n" + "\n".join([f"- {m}" for m in memories]) + "\n"
                    logger.info(f"RAG: Injected {len(memories)} memories.")

            # Append RAG context to system prompt or user prompt?
            # Ideally User prompt to make it visible to the model as "Context"
            full_prompt_with_rag = f"{rag_context}\n{full_prompt}"

            # Select tools based on Platform Context
            selected_tools = await self.tool_selector.select_tools(
                prompt=prompt, 
                available_tools=discord_tools, 
                platform="discord"
            )

            # If tools were filtered, log it
            if len(selected_tools) != len(discord_tools):
                logger.info(f"Tool Selection: {len(discord_tools)} -> {len(selected_tools)} tools")

            response = await core_client.send_message(
                content=full_prompt_with_rag,
                provider_id=str(message.author.id),
                display_name=message.author.display_name,
                conversation_id=None, 
                idempotency_key=f"discord:{message.id}",
                context_binding=context_binding,
                attachments=attachments,
                stream=False, # User requested no streaming
                client_context=client_context,
                available_tools=selected_tools  # Use RAG selected tools
            )

            if "error" in response:
                await status_manager.finish()
                await message.reply(f"❌ Core API 接続エラー: {response['error']}")
                return

            run_id = response.get("run_id")
            await status_manager.update_current(f"🧠 ORA Brain が考え中... (ID: {run_id[:8]})")

            # 4. Process SSE Events (Streaming/Incremental Updates)
            full_content = ""
            model_name = "ORA Universal Brain"

            async for event in core_client.stream_events(run_id):
                ev_type = event.get("event")
                ev_data = event.get("data", {})

                if ev_type == "delta":
                    # For non-streaming UI, we just accumulate. 
                    # If we want real-time typing, we'd update message here.
                    full_content += ev_data.get("text", "")
                
                elif ev_type == "meta":
                     model_name = ev_data.get("model", model_name)

                elif ev_type == "dispatch":
                    # TOOL CALL detected!
                    tool_name = ev_data.get("tool")
                    tool_args = ev_data.get("args", {})
                    logger.info(f"🚀 Dispatching tool action: {tool_name}")
                    
                    # Call ToolHandler (Handles music, imagine, tts, etc.)
                    # We pass the message context so it knows where to reply or join voice.
                    # [FIX] Use await instead of create_task to ensure SEQUENTIAL execution.
                    # This is critical for chains like "Screenshot -> Download -> Screenshot".
                    await self.cog.tool_handler.handle_dispatch(
                        tool_name=tool_name,
                        args=tool_args,
                        message=message,
                        status_manager=status_manager
                    )

                elif ev_type == "final":
                    full_content = ev_data.get("text", "")
                    model_name = ev_data.get("model", model_name)
                    break

                elif ev_type == "error":
                    await status_manager.finish()
                    await message.reply(f"⚠️ Core Error: {ev_data.get('message', 'Unknown error')}")
                    return

            # 5. Final Output Handover
            try:
                # [FIX] Flush any buffered files (Smart Bundling)
                if status_manager and hasattr(status_manager, "flush_files"):
                    try:
                        await status_manager.flush_files(message)
                    except Exception as e:
                        logger.error(f"Failed to flush files: {e}")
                        await message.reply(f"⚠️ ファイル送信中にエラーが発生しました: {e}")
            finally:
                # Always finish status manager
                await status_manager.finish()
            
            if not full_content and not response.get("run_id"): # If we had tools, content might be empty but OK
                await message.reply("❌ 応答を生成できませんでした。")
                return

            # Send as Embed Cards
            # Split if > 4000 chars
            remaining = full_content
            while remaining:
                chunk = remaining[:4000]
                remaining = remaining[4000:]
                embed = EmbedFactory.create_chat_embed(chunk, model_name=model_name)
                await message.reply(embed=embed)
            
            # 6. Post-Process Actions (Voice, etc.)
            # [MEMORY UPDATE] Inject AI response into MemoryCog buffer
            try:
                memory_cog = self.bot.get_cog("MemoryCog")
                if memory_cog:
                    asyncio.create_task(
                        memory_cog.add_ai_message(
                            user_id=message.author.id,
                            content=full_content,
                            guild_id=message.guild.id if message.guild else None,
                            channel_id=message.channel.id,
                            channel_name=message.channel.name if hasattr(message.channel, "name") else "DM",
                            guild_name=message.guild.name if message.guild else "Direct Message",
                            is_public=message.author.guild_permissions.administrator if message.guild else True # Use same logic as context
                        )
                    )
            except Exception as e:
                logger.warning(f"Failed to update MemoryCog: {e}")

            # Check if user is in VC and if we should speak
            if is_voice:
                # [REQUESTED FEATURE] Suppress AI speech if this channel is an Auto-Read channel
                # User wants "Reading Bot" behavior where AI text response is just text, unless specifically asked?
                # Or simply "Don't read AI response".
                should_speak = True
                if message.guild and hasattr(self.bot, "voice_manager"):
                    auto_channel_id = self.bot.voice_manager.auto_read_channels.get(message.guild.id)
                    if auto_channel_id == message.channel.id:
                        should_speak = False
                
                # [FIX] Accessed via bot instance as it's a shared resource now
                if should_speak and hasattr(self.bot, "voice_manager"):
                    await self.bot.voice_manager.play_tts(message.author, full_content)
                else:
                    logger.warning("VoiceManager not found on Bot instance.")

        except Exception as e:
            logger.error(f"Core API Delegation Failed: {e}", exc_info=True)
            await status_manager.finish()
            await message.reply(f"システムエラー: {e}")

    # --- END OF THIN CLIENT ---
