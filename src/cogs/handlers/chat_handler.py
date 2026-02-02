import asyncio
import datetime
import logging
from typing import Optional

import discord

from src.cogs.handlers.tool_selector import ToolSelector
from src.cogs.handlers.rag_handler import RAGHandler
from src.utils.core_client import core_client

logger = logging.getLogger(__name__)


class ChatHandler:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.tool_selector = ToolSelector(self.bot)
        self.rag_handler = RAGHandler(self.bot)
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
            # [Moltbook] Inject Soul (Persona) if available
            soul_injection = getattr(self.cog, "soul_prompt", "")
            if soul_injection:
                soul_injection = f"\n[SYSTEM IDENTITY]\n{soul_injection}\n"
            
            system_context = f"""
{soul_injection}
[SOURCE: DISCORD]
[SERVER: {message.guild.name if message.guild else 'Direct Message'}]
[CHANNEL: {message.channel.name if hasattr(message.channel, 'name') else 'DM'}]
[INSTRUCTION: If the user mentions an SNS profile (e.g., '〜のX', '〜のGithub'), YOU MUST USE 'web_jump_to_profile' with the handle. NEVER guess generic URLs like 'https://x.com/' or 'https://github.com/'.]
[SECURITY WARNING: You are running on a hosted server. NEVER screenshot sites that reveal the Global IP Address (e.g. 'What is my IP' sites). HOWEVER, you MUST take screenshots for normal sites (X, YouTube, News, etc.) when requested. Do NOT refuse normal screenshot requests.]
[AGENT PROTOCOL: DEEP RESEARCH]
If the user asks to "research" (調べて), "investigate" (調査して), or "summarize" (要約して) a topic:
1. USE 'web_search' to gather information from multiple sources (Web, Note, etc).
2. VERIFY the information (cross-reference).
3. SUMMARIZE findings with citations. Do NOT just copy-paste the first search result.

[AGENT PROTOCOL: VISIBLE PLANNING]
If the user's request is complex, multi-step, or difficult (e.g., 'Take a 4K screenshot, then save video, then check logs'):
1. FIRST, output a brief '📋 **Execution Plan**:' listing the steps you will take.
2. THEN, generate the corresponding tool calls in the same response.
3. This Transparency is CRITICAL for user trust.

[AGENT PROTOCOL: AGENTIC MINDSET (CRITICAL)]
You are an AGENT, not a wiki or a helpdesk.
- **NEVER** explain how to do something manually if you have a tool to do it.
- **NEVER** say "I cannot directly..." if you have a tool like `web_download` or `web_screenshot`.
- **ALWAYS** EXECUTE the tool immediately.
- If the user says "Save this URL", USE `web_download`. Do NOT tell them to right-click.
- If the user says "Take a picture", USE `web_screenshot`.
Users want YOU to do the work. Don't be lazy.

[FEW-SHOT EXAMPLES]
User: "スクショして動画を保存して https://example.com/video"
Assistant: (Thinking: User wants both visual confirmation and file persistence.)
Tool Calls: [web_screenshot(url="..."), web_download(url="...")]

User: "ブラウザで開いて" (Open in browser)
Assistant:
Tool Calls: [web_navigate(url="...")]
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

            # [Vision Integration] Process Attachments & References
            vision_suffix = ""
            image_payloads = []

            try:
                # 1. Current Message
                if message.attachments:
                    suffix, imgs = await self.cog.vision_handler.process_attachments(message.attachments)
                    vision_suffix += suffix
                    image_payloads.extend(imgs)

                # 2. Referenced Message (Reply) context
                if message.reference:
                    try:
                        if message.reference.cached_message:
                            ref_msg = message.reference.cached_message
                        else:
                            ref_msg = await message.channel.fetch_message(message.reference.message_id)
                        
                        if ref_msg:
                            full_prompt += f"\n\n[REPLYING TO MESSAGE (Author: {ref_msg.author.display_name})]:\n{ref_msg.content or '(No Text)'}"
                            for embed in ref_msg.embeds:
                                if embed.url: full_prompt += f"\n[EMBED URL]: {embed.url}"
                            
                            # Vision for References
                            if ref_msg.attachments:
                                 suffix, imgs = await self.cog.vision_handler.process_attachments(ref_msg.attachments, is_reference=True)
                                 vision_suffix += suffix
                                 image_payloads.extend(imgs)
                            
                            if ref_msg.embeds:
                                 suffix, imgs = await self.cog.vision_handler.process_embeds(ref_msg.embeds, is_reference=True)
                                 vision_suffix += suffix
                                 image_payloads.extend(imgs)

                    except Exception as e:
                        logger.warning(f"Failed to fetch referenced message: {e}")
            
            except Exception as e:
                logger.error(f"Vision Processing Failed: {e}")
                # Fallback: Continue without vision data rather than crashing
                full_prompt += "\n[SYSTEM ERROR: Image processing failed. Proceeding with text only.]"

            # Append Vision Text Context
            full_prompt += vision_suffix
            
            # Prepare attachments for LLM (UnifiedClient expects 'attachments' list of dicts)
            # The structure from VisionHandler is already compatible or needs minor adapt?
            # UnifiedClient.chat expects 'attachments' argument.
            # But here we are building `messages` manually?
            # Wait, `endpoints.py` handles `attachments` argument. 
            # In `ChatHandler`, we delegate to `core_client` or `unified_client`.
            
            # Update: ChatHandler calls `core_client.submit_message`.
            # We need to pass `image_payloads` to clean attachments.
            # Currently `chat_handler.py` uses `self.cog.unified_client` or `core_client`.
            # Let's see the call site further down.
            
            # Looking at previous code, `attachments` variable was created:
            # attachments = []
            # for att in message.attachments: ...
            
            # So I should assign `attachments = image_payloads`
            
            attachments = image_payloads
            
            # Send Request (Initial Handshake)
            # Fetch Context-Aware Tools (Discord Only)
            discord_tools = self.cog.get_context_tools("discord")

            # [RAG ROUTER] Analyze Intent & Select Tools
            # This reduces context usage and improves accuracy
            await status_manager.update_current("🔍 Intent Analysis (RAG)...")
            
            # [Clawdbot Feature] Vector Memory Retrieval (User + Guild Shared)
            guild_id_str = str(message.guild.id) if message.guild else None
            rag_context = await self.rag_handler.get_context(
                prompt=prompt,
                user_id=str(message.author.id),
                guild_id=guild_id_str
            )

            # Append RAG context to system prompt or user prompt?
            # Ideally User prompt to make it visible to the model as "Context"
            full_prompt_with_rag = f"{rag_context}\n{full_prompt}"

            # Select tools based on Platform Context
            selected_tools = await self.tool_selector.select_tools(
                prompt=prompt, 
                available_tools=discord_tools, 
                platform="discord",
                rag_context=rag_context
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
            if hasattr(self, "_plan_sent"):
                del self._plan_sent

            async for event in core_client.stream_events(run_id):
                ev_type = event.get("event")
                ev_data = event.get("data", {})

                if ev_type == "delta":
                    # For non-streaming UI, we just accumulate. 
                    # If we want real-time typing, we'd update message here.
                    full_content += ev_data.get("text", "")
                    
                    # [VISUALIZATION] Check if content is an Execution Plan (Relaxed Match)
                    if "Execution Plan" in full_content and "1." in full_content and not hasattr(self, "_plan_sent"):
                        # Only send ONCE per run
                        msg_lines = full_content.split("\n")
                        plan_lines = [line.strip() for line in msg_lines if line.strip().startswith("1.") or line.strip().startswith("2.") or line.strip().startswith("3.") or line.strip().startswith("-")]
                        
                        if plan_lines:
                             embed = discord.Embed(
                                 title="🤖 Task Execution Plan", 
                                 description="\n".join(plan_lines),
                                 color=0x00ff00 # Green
                             )
                             embed.set_footer(text="ORA Intelligent Agent System")
                             await message.reply(embed=embed)
                             self._plan_sent = True # Flag to prevent duplicates
                
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
                    tool_result = await self.cog.tool_handler.handle_dispatch(
                        tool_name=tool_name,
                        args=tool_args,
                        message=message,
                        status_manager=status_manager
                    )

                    # [FIX/AGENTIC] Submit Tool Result back to Core to break deadlock
                    if run_id:
                        logger.info(f"📤 Auto-submitting tool output for {tool_name} to Core...")
                        await core_client.submit_tool_output(
                            run_id=run_id,
                            tool_name=tool_name,
                            result=tool_result or "[Success]"
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
