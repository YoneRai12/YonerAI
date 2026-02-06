import asyncio
import datetime
import json
import logging
from typing import Optional

import discord

from src.cogs.handlers.tool_selector import ToolSelector
from src.cogs.handlers.rag_handler import RAGHandler
from src.cogs.handlers.swarm_orchestrator import SwarmOrchestrator
from src.utils.agent_trace import trace_event
from src.utils.core_client import core_client, extract_text_from_core_data

logger = logging.getLogger(__name__)


class ChatHandler:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        self.tool_selector = ToolSelector(self.bot)
        self.rag_handler = RAGHandler(self.bot)
        self.swarm = SwarmOrchestrator(self.bot, self.tool_selector.llm_client)
        logger.info("ChatHandler v3.9.2 (RAG Enabled) Initialized")

    @staticmethod
    def _sanitize_args_for_audit(args: dict) -> str:
        """Mask sensitive keys and keep payload short for Discord audit posts."""
        sensitive_markers = ("token", "secret", "password", "api_key", "authorization", "cookie")

        def scrub(value):
            if isinstance(value, dict):
                out = {}
                for k, v in value.items():
                    lk = str(k).lower()
                    if any(m in lk for m in sensitive_markers):
                        out[k] = "[REDACTED]"
                    else:
                        out[k] = scrub(v)
                return out
            if isinstance(value, list):
                return [scrub(v) for v in value]
            return value

        safe = scrub(args or {})
        text = json.dumps(safe, ensure_ascii=False)
        return text[:700] + ("..." if len(text) > 700 else "")

    async def _notify_agent_activity(self, title: str, description: str, color: int = 0x2B6CB0) -> None:
        cfg = getattr(self.bot, "config", None)
        if not cfg:
            return
        target_id = getattr(cfg, "feature_proposal_channel_id", None) or getattr(cfg, "log_channel_id", None)
        if not target_id:
            return
        channel = self.bot.get_channel(target_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(target_id)
            except Exception:
                return
        if not channel or not hasattr(channel, "send"):
            return
        # Discord embed title hard limit is 256 chars.
        safe_title = (title or "").strip()
        if len(safe_title) > 256:
            safe_title = safe_title[:253] + "..."
        embed = discord.Embed(title=safe_title or "ORA", description=description[:3900], color=color)
        embed.timestamp = discord.utils.utcnow()
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"Agent activity notify skipped: {e}")

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
        # 1. Initialize StatusManager and Request Tracking
        from src.utils.ui import EmbedFactory, StatusManager
        import uuid
        correlation_id = str(uuid.uuid4())
        logger.info(f"🆕 [Chat] New Request | CorrelationID: {correlation_id} | User: {message.author.id}")
        trace_event(
            "chat.request_received",
            correlation_id=correlation_id,
            user_id=str(message.author.id),
            guild_id=str(message.guild.id) if message.guild else None,
            channel_id=str(message.channel.id),
            prompt=prompt,
        )

        status_manager = StatusManager(message.channel, existing_message=existing_status_msg)

        # Dynamic task board: do not hardcode 3 steps for every request.
        # Keep it short for simple chats; expand only when the request implies multi-step work.
        p_low = (prompt or "").lower()
        tasks = ["依頼を解析"]
        if message.attachments:
            tasks.append("添付を解析")
        if any(k in p_low for k in ["ログ", "trace", "エラー", "stack", "例外"]):
            tasks += ["ログ/状況を確認", "原因を特定", "修正案を提示"]
        elif any(k in p_low for k in ["保存", "ダウンロード", "download", "save", "mp3", "mp4", "動画"]):
            tasks += ["保存/ダウンロードを実行", "結果を整理"]
        elif any(k in p_low for k in ["スクショ", "スクリーンショット", "screenshot", "webひらいて", "web操作", "ブラウザ"]):
            tasks += ["ページを開く", "スクショ/操作を実行"]
        # Always end with a reply step.
        tasks.append("回答を返す")

        # De-dup + clamp
        seen = set()
        tasks = [t for t in tasks if not (t in seen or seen.add(t))]
        tasks = tasks[:8]

        await status_manager.start_task_board(
            "⚡ ORA Universal Brain • 実行ステータス",
            tasks,
            footer="Sanitized & Powered by ORA Universal Brain",
        )
        await status_manager.set_task_state(1, "running", "Coreへ接続中")

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
            from src.utils.access_control import is_owner

            client_context = {
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "server_name": message.guild.name if message.guild else "Direct Message",
                "guild_id": str(message.guild.id) if message.guild else None,
                "channel_id": str(message.channel.id),
                "channel_name": message.channel.name if hasattr(message.channel, "name") else "DM",
                # ORA "admin" means creator/owner (ADMIN_USER_ID), not guild permissions.
                "is_admin": is_owner(self.bot, message.author.id),
            }

            # 3. Call Core API
            # [MEMORY INJECTION] Fetch User Profile
            memory_context = ""
            channel_memory_context = ""
            guild_memory_context = ""
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
                        l2 = user_profile.get("layer2_user_memory", {}) if isinstance(user_profile, dict) else {}
                        facts = ""
                        interests = ""
                        try:
                            if isinstance(l2, dict):
                                facts = "; ".join([str(x) for x in (l2.get("facts") or []) if str(x).strip()])[:800]
                                interests = "; ".join([str(x) for x in (l2.get("interests") or []) if str(x).strip()])[:400]
                        except Exception:
                            pass

                        memory_context = f"""
[USER PROFILE]
Name: {name}
Impression: {impression}
Traits: {traits}
Facts: {facts}
Interests: {interests}
"""

                    # Channel-level memory (summary/topics/atmosphere)
                    try:
                        ch_profile = await asyncio.wait_for(
                            memory_cog.get_channel_profile(message.channel.id),
                            timeout=1.0,
                        )
                        if isinstance(ch_profile, dict) and ch_profile:
                            c_sum = (ch_profile.get("summary") or "").strip()
                            c_atm = (ch_profile.get("atmosphere") or "").strip()
                            c_topics = ch_profile.get("topics") or []
                            if not isinstance(c_topics, list):
                                c_topics = []
                            c_topics_s = ", ".join([str(x) for x in c_topics if str(x).strip()])[:200]

                            lines = []
                            if c_sum:
                                lines.append(f"- Summary: {c_sum[:500]}")
                            if c_topics_s:
                                lines.append(f"- Topics: {c_topics_s}")
                            if c_atm:
                                lines.append(f"- Atmosphere: {c_atm[:120]}")

                            if lines:
                                channel_memory_context = "\n[CHANNEL MEMORY]\n" + "\n".join(lines) + "\n"
                    except Exception:
                        pass

                    # Guild/server-level memory (high-level server identity / dominant topics)
                    try:
                        if message.guild and hasattr(memory_cog, "get_guild_profile"):
                            g_profile = await asyncio.wait_for(
                                memory_cog.get_guild_profile(message.guild.id),
                                timeout=1.0,
                            )
                            if isinstance(g_profile, dict) and g_profile:
                                g_hint = (g_profile.get("hint") or "").strip()
                                g_topics = g_profile.get("topics") or []
                                if not isinstance(g_topics, list):
                                    g_topics = []
                                g_topics_s = ", ".join([str(x) for x in g_topics if str(x).strip()])[:250]
                                lines = []
                                if g_hint:
                                    lines.append(f"- Hint: {g_hint[:500]}")
                                if g_topics_s:
                                    lines.append(f"- Topics: {g_topics_s}")
                                if lines:
                                    guild_memory_context = "\n[GUILD MEMORY]\n" + "\n".join(lines) + "\n"
                    except Exception:
                        pass

                    # Light heuristic: if the creator/sub-admin explicitly states server identity
                    # (e.g., "ここはVALORANTの鯖"), persist it as a guild hint to bias acronym disambiguation.
                    try:
                        from src.utils.access_control import is_owner, is_sub_admin
                        if message.guild and hasattr(memory_cog, "set_guild_hint"):
                            txt = (message.content or "").strip()
                            low = txt.lower()
                            if (("この鯖" in txt) or ("このサーバ" in txt) or ("ここは" in txt)) and any(k in low for k in ["valorant", "valo", "バロ", "バロラント"]):
                                if is_owner(self.bot, message.author.id) or is_sub_admin(self.bot, message.author.id):
                                    await memory_cog.set_guild_hint(
                                        message.guild.id,
                                        "This server is primarily VALORANT-related (Valorant-focused context).",
                                    )
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Memory Fetch Failed: {e}")

            # [SOURCE INJECTION] Explicitly state this is Discord
            # [Moltbook] Inject Soul (Persona) if available
            soul_injection = getattr(self.cog, "soul_prompt", "")
            if soul_injection:
                soul_injection = f"\n[SYSTEM IDENTITY]\n{soul_injection}\n"

            # [DEVICE AWARENESS]
            is_mobile = False
            if message.guild and isinstance(message.author, discord.Member):
                if message.author.is_on_mobile():
                    is_mobile = True

            system_context = f"""
 {soul_injection}
 [ソース: DISCORD]
 [サーバー: {message.guild.name if message.guild else 'Direct Message'}]
 [チャンネル: {message.channel.name if hasattr(message.channel, 'name') else 'DM'}]

[エージェント指令: Codex Harness アーキテクチャ]
あなたは OpenAI Codex Harness に基づく自律型エージェントです。『Everything is controlled by code』の原則に従い、全ての操作を『スキル（Skill）』として制御してください。

- **Agentic Search (自律型探索)**: RAG などの固定的なインデックスに頼るのではなく、`code_grep`, `code_find`, `code_read`, `code_tree` といったスキルを能動的に使い、コードベースやデータを直接調査してください。
- **vibes (感覚) での判断**: ベクター検索の結果よりも、あなたが実際にファイルを見て文脈（Context）を理解し、判断することを優先してください。
- **最強の視覚能力**: あなたは提供された `image_url` を直接解析できます。視覚情報を前提とした高度な推論を行ってください。
- **4K対応**: 高画質要求には `resolution: "4K"` を指定。
- **自己視覚フィードバック**: 実行したスキルの成果（スクショ等）は即座にフィードバックされます。

[エージェントプロトコル: 実行計画の表示]
複雑な手順が必要な場合、返答の冒頭に「📋 **エージェント実行計画 (Skill Plan)**:」を提示してください。

[Harness Event Protocol]
あなたの思考（Thought）と進捗（Progress）は、リアルタイムで Harness ストリームへ送出されます。

 [運用ルール: CAPTCHA / Anti-Bot]
 ブラウザ操作中に CAPTCHA や「I'm not a robot / unusual traffic」などの検知が出た場合、
 回避・突破を試みてはいけません。代わりに次の方針で自律的に解決してください:
 1) 直接ブラウザ検索を停止
 2) `web_search` / `read_web_page` などAPI系ツールへ切替
 3) 必要ならユーザーに手動確認を依頼し、確認後に次のタスクへ進む

 [権限/安全ポリシー]
 - このシステムはユーザーごとにツール権限が制限されます。許可されていないツールは選ばず、実行もできません。
 - 非オーナー（製作者）ユーザーに対しては、破壊・削除・侵入・トークン要求などの危険な手順/スクリプトの提示をしないでください。
   その場合は「できない」旨と、安全な代替（一般的説明、公式手順、オーナーへのエスカレーション）だけを提案してください。

 [デバイス情報]
 {"[MOBILE] ユーザーはモバイル端末を使用しています。回答は簡潔にまとめ、複雑な表やフォーマットは避けてください。" if is_mobile else "[DESKTOP] ユーザーはPCを使用しています。詳細な解説とリッチなフォーマットが可能です。"}

  {memory_context}
  {guild_memory_context}
  {channel_memory_context}
  """

            # Prepend to prompt
            full_prompt = system_context.strip() + "\n\n" + prompt

            # [Vision Integration] Process Attachments & References
            vision_suffix = ""
            image_payloads = []

            try:
                # 1. Current Message
                # 1. Current Message
                # PERF: Unified GPT-5 Environment. Direct Image payload is sent.
                # We skip the captioning suffix to avoid redundant LLM calls and latency.
                if message.attachments:
                    # Only collect bytes/base64, don't trigger describe_media
                    _, imgs = await self.cog.vision_handler.process_attachments(message.attachments)
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
            # Tool visibility is creator-locked: non-owner users only get safe allowlist tools.
            discord_tools = self.cog.get_context_tools("discord", user_id=message.author.id)

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
                rag_context=rag_context,
                correlation_id=correlation_id
            )
            trace_event(
                "chat.tools_selected",
                correlation_id=correlation_id,
                available=len(discord_tools),
                selected=len(selected_tools),
                selected_names=[t.get("name") for t in selected_tools if isinstance(t, dict)],
            )

            # If router judges the request complex, force explicit plan-first behavior.
            route_meta = getattr(self.tool_selector, "last_route_meta", {}) or {}
            if route_meta.get("complexity") == "high":
                full_prompt_with_rag = (
                    "[ORCHESTRATION POLICY: COMPLEX TASK]\n"
                    "この依頼は複雑です。必ず最初に『📋 エージェント実行計画』を短く提示してから、"
                    "必要なツール呼び出しを開始してください。\n\n"
                ) + full_prompt_with_rag

            # [SWARM] Optional high-complexity pre-orchestration
            if self.swarm.should_run(route_meta, prompt):
                await status_manager.add_timeline("Swarm: タスク分解中")
                trace_event("swarm.triggered", correlation_id=correlation_id, route_meta=route_meta)
                try:
                    swarm_output = await self.swarm.run(
                        prompt=prompt,
                        rag_context=rag_context,
                        provider_id=str(message.author.id),
                        display_name=message.author.display_name,
                        context_binding=context_binding,
                        client_context=client_context,
                        correlation_id=correlation_id,
                    )
                    if swarm_output.get("ok") and swarm_output.get("summary"):
                        await status_manager.add_timeline("Swarm: 結果統合完了")
                        summary = swarm_output["summary"]
                        full_prompt_with_rag = (
                            "[SWARM PRE-ANALYSIS]\n"
                            f"{summary}\n\n"
                            "[Use the above as precomputed parallel analysis context.]\n\n"
                            + full_prompt_with_rag
                        )
                    else:
                        await status_manager.add_timeline("Swarm: Guardrailsで停止")
                except Exception as e:
                    logger.warning(f"Swarm pre-analysis failed: {e}")
                    await status_manager.add_timeline("Swarm: 失敗 -> 通常処理へ")
                    trace_event("swarm.exception", correlation_id=correlation_id, error=str(e))

            # If tools were filtered, log it
            if len(selected_tools) != len(discord_tools):
                logger.info(f"Tool Selection: {len(discord_tools)} -> {len(selected_tools)} tools")

            bot_cfg = getattr(self.bot, "config", None)
            preferred_model = getattr(bot_cfg, "openai_default_model", "gpt-5-mini")

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
                available_tools=selected_tools,  # Use RAG selected tools
                source="discord",
                llm_preference=preferred_model,
                correlation_id=correlation_id
            )

            if "error" in response:
                await status_manager.finish()
                await message.reply(f"❌ Core API 接続エラー: {response['error']}")
                trace_event("chat.core_send_error", correlation_id=correlation_id, error=response["error"])
                return

            run_id = response.get("run_id")
            await status_manager.set_task_state(1, "done", f"run_id={run_id[:8] if run_id else 'N/A'}")
            await status_manager.set_task_state(2, "running", "待機中")
            trace_event("chat.run_created", correlation_id=correlation_id, run_id=run_id)

            # 4. Process SSE Events (Streaming/Incremental Updates)
            full_content = ""
            model_name = "ORA Universal Brain"
            download_summaries = []
            tool_feedback_summaries = []
            if hasattr(self, "_plan_sent"):
                del self._plan_sent

            async for event in core_client.stream_events(run_id):
                ev_type = event.get("event")
                ev_data = event.get("data", {})

                if ev_type == "delta":
                    full_content += ev_data.get("text", "")

                    # [VISUALIZATION] Check if content is an Execution Plan (Relaxed Match)
                    has_plan_header = "Execution Plan" in full_content or "実行計画" in full_content
                    if has_plan_header and "1." in full_content and not hasattr(self, "_plan_sent"):
                        # Only send ONCE per run
                        msg_lines = full_content.split("\n")
                        plan_lines = [line.strip() for line in msg_lines if line.strip().startswith("1.") or line.strip().startswith("2.") or line.strip().startswith("3.") or line.strip().startswith("-")]

                        if plan_lines:
                             embed = discord.Embed(
                                 title="🤖 Harness Agent Execution Plan",
                                 description="\n".join(plan_lines),
                                 color=0x00ffff # Cyan (Codex Style)
                             )
                             embed.set_footer(text="OpenAI Codex Harness Architecture")
                             await message.reply(embed=embed)
                             self._plan_sent = True

                elif ev_type == "thought":
                    # Stream thoughts to a separate log or specific UI element
                    thought_text = ev_data.get("text", "")
                    logger.info(f"🧠 [Harness Thought] {thought_text[:100]}...")
                    trace_event("chat.thought", correlation_id=correlation_id, run_id=run_id, text=thought_text)

                elif ev_type == "progress":
                    # Update status bar with Harness Progress
                    status_text = ev_data.get("status", "")
                    await status_manager.set_task_state(2, "running", status_text)
                    await status_manager.add_timeline(f"Progress: {status_text}")
                    trace_event("chat.progress", correlation_id=correlation_id, run_id=run_id, status=status_text)

                elif ev_type == "meta":
                     model_name = ev_data.get("model", model_name)

                elif ev_type == "dispatch":
                    # TOOL CALL detected!
                    tool_name = ev_data.get("tool")
                    tool_args = ev_data.get("args", {})
                    tool_call_id = ev_data.get("tool_call_id")
                    logger.info(f"🚀 [Dispatch] CID: {correlation_id} | Tool: {tool_name}")
                    await status_manager.set_task_state(2, "running", f"{tool_name} 実行中")
                    await status_manager.add_timeline(f"Dispatch: {tool_name}")
                    safe_args = self._sanitize_args_for_audit(tool_args if isinstance(tool_args, dict) else {})
                    trace_event(
                        "chat.dispatch",
                        correlation_id=correlation_id,
                        run_id=run_id,
                        tool=tool_name,
                        tool_call_id=tool_call_id,
                        args=tool_args if isinstance(tool_args, dict) else {},
                    )
                    asyncio.create_task(
                        self._notify_agent_activity(
                            "🧩 Agent Dispatch",
                            f"CID: `{correlation_id}`\nRun: `{run_id}`\nTool: `{tool_name}`\nArgs: `{safe_args}`",
                            color=0x805AD5,
                        )
                    )

                    # Call ToolHandler (Handles music, imagine, tts, etc.)
                    # We pass the message context so it knows where to reply or join voice.
                    # [FIX] Use await instead of create_task to ensure SEQUENTIAL execution.
                    # This is critical for chains like "Screenshot -> Download -> Screenshot".
                    tool_result = await self.cog.tool_handler.handle_dispatch(
                         tool_name=tool_name,
                         args=tool_args,
                         message=message,
                         status_manager=status_manager,
                         correlation_id=correlation_id,
                         tool_call_id=tool_call_id,
                     )

                    if isinstance(tool_result, dict):
                        dl_meta = tool_result.get("download_meta")
                        if isinstance(dl_meta, dict):
                            summary = dl_meta.get("assistant_summary")
                            if isinstance(summary, str) and summary.strip():
                                download_summaries.append(summary.strip())
                        result_txt = tool_result.get("result")
                        if isinstance(result_txt, str) and result_txt.strip():
                            cleaned = result_txt.replace("[SILENT_COMPLETION]", "").strip()
                            if cleaned:
                                tool_feedback_summaries.append(cleaned)
                    elif isinstance(tool_result, str):
                        cleaned = tool_result.replace("[SILENT_COMPLETION]", "").strip()
                        if cleaned:
                            tool_feedback_summaries.append(cleaned)
                    trace_event(
                        "chat.tool_result",
                        correlation_id=correlation_id,
                        run_id=run_id,
                        tool=tool_name,
                        result_preview=str(tool_result)[:400],
                    )

                    # [FIX/AGENTIC] Submit Tool Result back to Core to break deadlock
                    if run_id:
                        logger.info(f"📤 Auto-submitting tool output for {tool_name} to Core...")
                        await core_client.submit_tool_output(
                            run_id=run_id,
                            tool_name=tool_name,
                            result=tool_result or "[Success]",
                            tool_call_id=tool_call_id,
                        )
                        await status_manager.add_timeline(f"Submitted: {tool_name}")
                        trace_event(
                            "chat.tool_submitted",
                            correlation_id=correlation_id,
                            run_id=run_id,
                            tool=tool_name,
                            tool_call_id=tool_call_id,
                        )
                        asyncio.create_task(
                            self._notify_agent_activity(
                                "✅ Agent Tool Completed",
                                f"CID: `{correlation_id}`\nRun: `{run_id}`\nTool: `{tool_name}`\nStatus: submitted to Core",
                                color=0x2F855A,
                            )
                        )

                elif ev_type == "final":
                    final_text = extract_text_from_core_data(ev_data) or ""
                    if isinstance(final_text, str) and final_text.strip():
                        full_content = final_text
                    model_name = ev_data.get("model", model_name)
                    await status_manager.set_task_state(2, "done", "ツール連携完了")
                    await status_manager.set_task_state(3, "running", "最終回答を整形中")
                    trace_event("chat.final_event", correlation_id=correlation_id, run_id=run_id, model=model_name)
                    break

                elif ev_type == "error":
                    await status_manager.set_task_state(2, "failed", ev_data.get("message", "error"))
                    await status_manager.set_task_state(3, "failed", "Coreエラー")
                    await status_manager.finish()
                    await message.reply(f"⚠️ Core Error: {ev_data.get('message', 'Unknown error')}")
                    trace_event("chat.core_error_event", correlation_id=correlation_id, run_id=run_id, data=ev_data)
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
                trace_event("chat.empty_response", correlation_id=correlation_id, run_id=run_id)
                return

            # If Core generated only a generic dispatch sentence, replace it with concrete download metadata summary.
            if download_summaries:
                generic_markers = [
                    "保存処理をdiscordクライアントにディスパッチ",
                    "保存が完了したら",
                    "ディスパッチしました",
                ]
                low = (full_content or "").lower()
                if (not full_content.strip()) or any(m in low for m in generic_markers):
                    full_content = "\n".join(download_summaries[-2:])

            # General fallback: if core final is empty, surface concrete tool feedback.
            if not (full_content or "").strip() and tool_feedback_summaries:
                uniq = []
                for t in tool_feedback_summaries:
                    if t not in uniq:
                        uniq.append(t)
                full_content = "\n".join(uniq[-2:])

            if not (full_content or "").strip():
                full_content = "ツール処理は実行されましたが、最終テキスト応答が空でした。必要なら結果を再表示します。"

            # Send as Embed Cards
            # Split if > 4000 chars
            remaining = full_content
            await status_manager.set_task_state(3, "done", "回答完了")
            while remaining:
                chunk = remaining[:4000]
                remaining = remaining[4000:]
                embed = EmbedFactory.create_chat_embed(chunk, model_name=model_name)
                await message.reply(embed=embed)
            trace_event(
                "chat.reply_sent",
                correlation_id=correlation_id,
                run_id=run_id,
                model=model_name,
                reply_length=len(full_content or ""),
            )

            # 6. Post-Process Actions (Voice, etc.)
            # [MEMORY UPDATE] Inject AI response into MemoryCog buffer
            try:
                memory_cog = self.bot.get_cog("MemoryCog")
                if memory_cog:
                    # Note: MemoryCog expects visibility scope; use same public/private decision as MemoryCog does.
                    is_pub = memory_cog.is_public(message.channel) if hasattr(memory_cog, "is_public") else True
                    asyncio.create_task(
                        memory_cog.add_ai_message(
                            user_id=message.author.id,
                            content=full_content,
                            guild_id=message.guild.id if message.guild else None,
                            channel_id=message.channel.id,
                            channel_name=message.channel.name if hasattr(message.channel, "name") else "DM",
                            guild_name=message.guild.name if message.guild else "Direct Message",
                            is_public=is_pub,
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
            trace_event("chat.exception", correlation_id=correlation_id, error=str(e))

    # --- END OF THIN CLIENT ---
