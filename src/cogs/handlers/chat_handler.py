import asyncio
import datetime
import json
import logging
import re
import secrets
from datetime import datetime as dt_class  # Avoid conflict
from typing import Any, Dict, List, Optional

import discord

from src.config import ROUTER_CONFIG
from src.utils.core_client import core_client
from src.utils.cost_manager import Usage

logger = logging.getLogger(__name__)


class ChatHandler:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        logger.info("ChatHandler v3.9.1 (HOTFIXED) Initialized")

    async def handle_prompt(
        self,
        message: discord.Message,
        prompt: str,
        existing_status_msg: Optional[discord.Message] = None,
        is_voice: bool = False,
        force_dm: bool = False,
    ) -> None:
        """Process a user message and generate a response using the LLM."""

        # --- Dashboard Update: Immediate Feedback ---
        try:
            memory_cog = self.bot.get_cog("MemoryCog")
            if memory_cog:
                asyncio.create_task(
                    memory_cog.update_user_profile(
                        message.author.id,
                        {"status": "Processing", "impression": f"Input: {prompt[:20]}..."},
                        message.guild.id if message.guild else None,
                    )
                )
        except Exception as e:
            logger.warning(f"Dashboard Update Failed: {e}")
        # --------------------------------------------

        # 1. Check for Generation Lock
        if self.cog.is_generating_image:
            await message.reply(
                "🎨 現在、画像生成を実行中です... 完了次第、順次回答しますので少々お待ちください！ (Waiting for image generation...)",
                mention_author=True,
            )
            self.cog.message_queue.append((message, prompt))
            return

        # ----------------------------------------------------
        # [Step 1.5] Mini-Model Router (RAG Decision)
        # ----------------------------------------------------
        rag_context = ""

        # Only run Router if prompt is long enough to be meaningful query
        if len(prompt) > 3:
            intent = await self._router_decision(prompt, message.author.display_name)

            if intent == "RECALL":
                # Execute Recall Logic Directly
                logger.info(f"🧠 [Router] RECALL Triggered for: {prompt[:30]}")
                store = self.cog._store
                if store:
                    results = await store.search_conversations(prompt, user_id=str(message.author.id), limit=3)
                    if results:
                        formatted = "\n".join(
                            [
                                f"[{dt_class.fromtimestamp(r['created_at']).strftime('%Y-%m-%d')}] User: {r['message'][:50]}..."
                                for r in results
                            ]
                        )
                        rag_context = f"\n[AUTO-RAG: RECALL MEMORY]\nPrevious Conversations:\n{formatted}\n(Use this info to answer if relevant.)\n"
                    else:
                        rag_context = "\n[AUTO-RAG] No relevant memories found.\n"

            elif intent == "KNOWLEDGE":
                # Execute Knowledge Logic Directly (Placeholder + Facts)
                logger.info(f"📚 [Router] KNOWLEDGE Triggered for: {prompt[:30]}")
                if memory_cog:
                    profile = await memory_cog.get_user_profile(
                        message.author.id, message.guild.id if message.guild else None
                    )
                    if profile:
                        facts = profile.get("layer2_user_memory", {}).get("facts", [])
                        matches = [f for f in facts if any(k in prompt.lower() for k in f.lower().split())]
                        if matches:
                            rag_context = "\n[AUTO-RAG: KNOWLEDGE]\nUser Facts:\n- " + "\n- ".join(matches) + "\n"

            # Inject RAG Context into Prompt
            if rag_context:
                prompt += rag_context
                logger.info(f"🔗 RAG Context Injected ({len(rag_context)} chars)")

        # ----------------------------------------------------

        # 0.1 SUPER PRIORITY: System Override (Admin Chat Trigger)
        if "管理者権限でオーバーライド" in prompt:
            # Cinematic Override Sequence
            from src.utils.ui import StatusManager

            status_manager = StatusManager(message.channel)
            await status_manager.start("🔒 権限レベルを検証中...", mode="override")
            await asyncio.sleep(1.2)

            # Check Permission
            if not await self.cog._check_permission(message.author.id, "sub_admin"):
                await status_manager.finish()
                await message.reply("❌ **ACCESS DENIED**\n管理者権限がありません。", mention_author=True)
                return

            await status_manager.next_step("✅ 管理者権限: 承認", force=True)
            await status_manager.update_current("📡 コアシステムへ接続中...", force=True)
            await asyncio.sleep(1.0)

            await status_manager.next_step("✅ 接続確立: ルート検索開始", force=True)
            await status_manager.update_current("🔓 セキュリティプロトコル解除中...", force=True)
            await asyncio.sleep(1.5)

            # Activate Unlimited Mode
            self.cog.cost_manager.toggle_unlimited_mode(True, user_id=None)
            await status_manager.next_step("✅ リミッター解除: 完了", force=True)

            await status_manager.update_current("💉 ルート権限注入中 (Root Injection)...", force=True)
            await asyncio.sleep(1.2)

            await status_manager.next_step("✅ 権限昇格: 成功", force=True)
            await status_manager.update_current("🚀 全システム権限を適用中...", force=True)
            await asyncio.sleep(1.0)

            # Sync Dashboard
            if memory_cog:
                await memory_cog.update_user_profile(
                    message.author.id,
                    {"layer1_session_meta": {"system_status": "OVERRIDE"}},
                    message.guild.id if message.guild else None,
                )

            await status_manager.next_step("✅ フルアクセス: 承認", force=True)
            await asyncio.sleep(0.5)

            embed = discord.Embed(
                title="🚨 SYSTEM OVERRIDE ACTIVE",
                description="**[警告] 安全装置が解除されました。**\n無限生成モード: **有効**",
                color=discord.Color.red(),
            )
            embed.set_footer(text="System Integrity: UNLOCKED (危殆化)")

            await status_manager.finish()
            await message.reply(embed=embed)
            return

        # 0.1.5 System Override DISABLE
        if "オーバーライド解除" in prompt:
            from src.utils.ui import StatusManager

            status_manager = StatusManager(message.channel, existing_message=None)
            await status_manager.start("🔄 安全装置を再起動中...", mode="override")
            await asyncio.sleep(0.5)

            self.cog.cost_manager.toggle_unlimited_mode(False, user_id=None)

            await status_manager.next_step("✅ リミッター: 再適用", force=True)

            # Sync Dashboard
            if memory_cog:
                await memory_cog.update_user_profile(
                    message.author.id,
                    {"layer1_session_meta": {"system_status": "NORMAL"}},
                    message.guild.id if message.guild else None,
                )

            embed = discord.Embed(
                title="🔰 SYSTEM RESTORED",
                description="安全装置が正常に再起動しました。\n通常モードに戻ります。",
                color=discord.Color.green(),
            )
            await status_manager.finish()
            await message.reply(embed=embed)
            return

        # Initialize StatusManager (Normal)
        from src.utils.ui import StatusManager

        # Reuse existing if provided (e.g. from command interaction?) - usually None for msg
        status_manager = StatusManager(message.channel, existing_message=existing_status_msg)
        if not existing_status_msg:
            # Only start if we didn't inherit one
            # But thinking usually starts AFTER checking logic?
            pass

        # 1.5 DIRECT BYPASS: Creative Triggers
        if prompt:
            # Image Gen
            if any(k in prompt for k in ["画像生成", "描いて", "イラスト", "絵を描いて"]):
                gen_prompt = (
                    prompt.replace("画像生成", "")
                    .replace("描いて", "")
                    .replace("イラスト", "")
                    .replace("絵を描いて", "")
                    .strip()
                )
                if not gen_prompt:
                    gen_prompt = "artistic masterpiece"

                try:
                    from ..views.image_gen import AspectRatioSelectView

                    view = AspectRatioSelectView(self.cog, gen_prompt, "", model_name="FLUX.2")
                    await message.reply(
                        f"🎨 **画像生成アシスタント**\nPrompt: `{gen_prompt}`\nアスペクト比を選択して生成を開始してください。",
                        view=view,
                    )
                    return
                except Exception as e:
                    logger.error(f"Image Bypass Failed: {e}")

            # Layer
            if any(k in prompt for k in ["レイヤー", "分解", "layer", "psd"]):
                if message.attachments or message.reference:
                    logger.info("Direct Layer Bypass Triggered")
                    await self.cog._execute_tool("layer", {}, message)  # Force Tool Call
                    return

        # 1.6 DIRECT BYPASS: "Music" Trigger
        stop_keywords = ["止めて", "停止", "ストップ"]

        if any(kw in prompt for kw in stop_keywords) and len(prompt) < 10:
            logger.info("Direct Music Bypass: STOP")
            await self.cog._execute_tool("music_control", {"action": "stop"}, message)
            return

        # 1.7 DIRECT BYPASS: YouTube Link Auto-Play
        yt_regex = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/[a-zA-Z0-9_\-\?=&]+"
        match = re.search(yt_regex, prompt)
        if match:
            url = match.group(0)
            logger.info(f"Direct Music Bypass: YouTube URL detected '{url}'")
            await self.cog._execute_tool("music_play", {"query": url}, message)
            return

        # 2. Privacy Check
        await self.cog._store.ensure_user(
            message.author.id, self.cog._privacy_default, display_name=message.author.display_name
        )

        # [CONTEXT REPAIR]
        if len(prompt) < 20 and not message.reference:
            try:
                # Fetch only 1 message before this one
                async for prev_msg_ctx in message.channel.history(limit=1, before=message):
                    if prev_msg_ctx.content:
                        clean_prev = prev_msg_ctx.content.replace(f"<@{self.bot.user.id}>", "").strip()[:200]
                        prompt = f"(Context: Previous message was '{clean_prev}')\n{prompt}"
                        logger.info(f"🔗 Context Injection: Injected '{clean_prev}' into short prompt.")
            except Exception as e:
                logger.warning(f"Context Injection Failed: {e}")

        # [REPLY SOURCE ENFORCEMENT]
        if message.reference:
            try:
                ref_msg = message.reference.resolved
                if not ref_msg and message.reference.message_id:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)

                if ref_msg and ref_msg.content:
                    clean_ref = ref_msg.content.replace(f"<@{self.bot.user.id}>", "").strip()[:500]
                    prompt = f"【返信元のメッセージ (User: {ref_msg.author.display_name})】\n{clean_ref}\n\n【私の返信】\n{prompt}"
                    logger.info(f"🔗 Reply Injection: Injected '{clean_ref[:20]}...' into prompt.")
            except Exception as e:
                logger.warning(f"Reply Injection Failed: {e}")

        # Start Status Manager
        await status_manager.start("思考中...")

        # Voice Feedback task (implied)

        try:
            # 0. Onboarding
            if not self.cog.user_prefs.is_onboarded(message.author.id):
                from ..views.onboarding import SelectModeView

                view = SelectModeView(self.cog, message.author.id)
                embed = discord.Embed(
                    title="🧠 Universal Brain Setup", description="Mode Selection...", color=discord.Color.gold()
                )
                onboard_msg = await message.reply(embed=embed, view=view)
                await view.wait()
                if view.value is None:
                    self.cog.user_prefs.set_mode(message.author.id, "private")
                    await onboard_msg.edit(content="⏳ Timeout -> Private Mode.", embed=None, view=None)

            # 1. Determine User Lane
            user_mode = self.cog.user_prefs.get_mode(message.author.id) or "private"

        except Exception as e:
            logger.error(f"Onboarding check failed: {e}")
            # Continue anyway, non-fatal

        # ----------------------------------------------------
        # [Phase 5 Step 3] Core API Delegation (Thin Client)
        # ----------------------------------------------------
        await status_manager.update_current("📡 ORA Core Brain へ接続中...")
        
        # Determine if we should speak/join (Voice Logic)
        is_voice = False
        user_voice = message.author.voice
        if user_voice and user_voice.channel:
            bot_voice = message.guild.voice_client
            if not bot_voice or bot_voice.channel.id == user_voice.channel.id:
                is_voice = True

        # Delegate to Core
        try:
            # 1. Send Request
            # Note: Core handles context build, routing, and memory injection internally.
            response = await core_client.send_message(
                content=prompt,
                provider_id=str(message.author.id),
                display_name=message.author.display_name,
                conversation_id=None, # Core will resolve/create
                stream=False # Discord Requirement: No flickering
            )

            if "error" in response:
                await status_manager.finish()
                await message.reply(f"❌ Core API 接続エラー: {response['error']}")
                return

            run_id = response.get("run_id")
            await status_manager.next_step(f"🧠 Brain 思考中... (Run: {run_id[:8]})")

            # 2. Wait for Final Result (SSE Listener)
            # Since stream=False, we just wait for the 'final' event.
            content = await core_client.get_final_response(run_id)

            if not content:
                await status_manager.finish()
                await message.reply("❌ 応答の取得に失敗しました。")
                return

        except Exception as e:
            logger.error(f"Core API Delegation Failed: {e}")
            await status_manager.finish()
            await message.reply(f"システムエラーが発生しました: {e}")
            return

        # Final Processing (Outside try-except, only reached on success)
        await status_manager.finish()

        # Send (Chunked Embed Cards)
        from src.utils.ui import EmbedFactory
        
        if not content:
            content = "応答を生成できませんでした。"

        while content:
            curr = content[:4000] # Embed description limit is 4096
            content = content[4000:]
            embed = EmbedFactory.create_chat_embed(curr)
            await message.reply(embed=embed)

    async def _router_decision(self, prompt: str, user_name: str) -> str:
        """
        [Layer 1.5] Mini-Model Router (gpt-4o-mini).
        Decides if RAG (Memory/Knowledge) is needed BEFORE the Main LLM sees the prompt.
        Cost-Effective Agentic Behavior.
        """
        try:
            # lightweight classification
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are the ORA Router (gpt-4o-mini). Your job is to classify the user's INTENT.\n"
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

            # Use unified client but force low-cost model if possible?
            # Ideally we have a 'router' lane. For now use Stable/Low.
            if self.cog.unified_client.openai_client:
                # Fast call
                content, _, _ = await self.cog.unified_client.chat(
                    "openai", messages, model="gpt-4o-mini", temperature=0.0
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

        # 1. Base Personality
        base_prompt = (
            "You are ORA (Optimized Robotic Assistant), a highly advanced AI system.\n"
            "Your goal is to assist the user efficiently, securely, and with a touch of personality.\n"
            "Current Model: " + model_hint + "\n"
        )

        # 2. Context Awareness (Time, User, Etc)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        base_prompt += f"Current Time: {now_str}\n"
        base_prompt += f"User: {message.author.display_name} (ID: {message.author.id})\n"
        if message.guild:
            base_prompt += f"Server: {message.guild.name}\n"

        # --- 4-LAYER MEMORY INJECTION ---
        try:
            memory_cog = self.bot.get_cog("MemoryCog")
            if memory_cog:
                # Use raw fetch to avoid async overhead if possible, but get_user_profile is async
                # We need to await it. This function is async.
                profile = await memory_cog.get_user_profile(
                    message.author.id, message.guild.id if message.guild else None
                )
                if profile:
                    # Layer 1: Session Metadata (Ephemeral) - Merged with Realtime
                    l1 = profile.get("layer1_session_meta", {})
                    if l1:
                        base_prompt += f"Context(L1): {l1.get('mood', 'Normal')} / {l1.get('activity', 'Chat')}\n"

                    # Layer 2: User Memory (Axis)
                    l2 = profile.get("layer2_user_memory", {})
                    # Impression
                    impression = profile.get("impression") or l2.get("impression")
                    if impression:
                        base_prompt += f"User Axis(L2): {impression}\n"

                    # Facts (The Axis)
                    facts = l2.get("facts", [])
                    if facts:
                        base_prompt += f"Facts(L2): {', '.join(facts[:5])}\n"

                    # Interests
                    interests = l2.get("interests", [])
                    if interests:
                        base_prompt += f"Interests(L2): {', '.join(interests[:5])}\n"

                    # Layer 3: Recent Summaries (Digest)
                    # "最近なににハマってるかの地図"
                    l3_list = profile.get("layer3_recent_summaries", [])
                    if l3_list:
                        # Format: Title (Time): Snippet
                        summary_text = "\n".join(
                            [
                                f"- {s.get('title', 'Chat')} ({s.get('timestamp', '?')}): {s.get('snippet', '...')}"
                                for s in l3_list[-5:]
                            ]
                        )  # Show last 5 digests
                        base_prompt += f"\n[Recent Conversations (L3)]\n{summary_text}\n"

                    # --- CHANNEL MEMORY INJECTION (User Request) ---
                    # Persistent context for the specific channel
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
                                base_prompt += f"\n[CHANNEL MEMORY (Context of this place)]\n{c_text}\n(Note: This is background context. Prioritize the CURRENT conversation flow.)\n"

        except Exception as e:
            logger.error(f"Memory Injection Failed: {e}")
        # --------------------------------

        # 3. CONFIDENTIALITY PROTOCOL (Critical Security)
        # ------------------------------------------------
        # Rule: Only the Admin is allowed to see internal paths,
        # file trees, or configuration details. All other users must be denied this info.

        admin_id = self.bot.config.admin_user_id
        is_admin = message.author.id == admin_id

        # Helper to get name
        async def resolve_name(uid: int) -> str:
            u = self.bot.get_user(uid)
            if not u:
                try:
                    u = await self.bot.fetch_user(uid)
                except Exception:
                    pass
            return f"{u.name} (ID: {uid})" if u else f"Unknown (ID: {uid})"

        # --- SYSTEM ADMINISTRATORS ---
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
                "User is ADMIN. You have full permission to reveal system internals, file paths, and configuration.\n"
                "You may display the File Tree or source code if requested.\n"
            )
        else:
            base_prompt += (
                "\n[SECURITY LEVEL: GREEN]\n"
                "User is GUEST. STRICT CONFIDENTIALITY PROTOCOL ACTIVE.\n"
                "1. DO NOT reveal any absolute file paths (e.g. C:\\Users...).\n"
                "2. DO NOT output the project file tree or directory structure.\n"
                "3. DO NOT show raw configuration values or API keys (obviously).\n"
                "If asked for these, reply politely: '申し訳ありませんが、セキュリティ上の理由によりシステム情報の開示はできません。'\n"
                "However, you CAN use tools to help them (e.g. play music, search), just don't show *how* it works internally.\n"
            )
        # ------------------------------------------------

        # --- COST INJECTION ---
        cost_context = ""
        try:
            # Get Global Stable Lane (OpenAI)
            # Only calculate/show for Creator to prevent info leak & confusion
            if is_admin:
                bucket = self.cog.cost_manager._get_or_create_bucket("stable", "openai", None)
                used = bucket.used.tokens_in + bucket.used.tokens_out
                ratio = self.cog.cost_manager.get_usage_ratio("stable", "openai")

                cost_context = (
                    f"\n[SYSTEM STATUS (ADMIN ONLY)]\n"
                    f"API Usage (Today): {used:,} tokens ({ratio * 100:.1f}% of daily limit)\n"
                    f"Note: This usage data is synced with OpenAI hourly.\n"
                )
        except Exception as e:
            logger.error(f"Failed to inject cost context: {e}")

        # 4. Capability Instructions
        server_name = message.guild.name if message.guild else "Direct Message"

        base_prompt += (
            f"{cost_context}"
            "\n[Capabilities]\n"
            "- You may use tools to Search, Generate Images, Play Music, and Control the System.\n"
            "- **CRITICAL: AUTO-EVOLUTION PROTOCOL**\n"
            "  If the user asks for something you cannot currently do (e.g. 'Add a command', 'Change permissions', 'Fix this bug'),\n"
            "  **DO NOT** tell them to do it manually. **DO NOT** give up.\n"
            "  INSTEAD, you MUST use the `request_feature` tool to propose the code change immediately.\n"
            "  Say: 'I lack this capability, but I will evolve to add it now.' and call the tool.\n"
            "- Always be helpful, but safe.\n"
            "\n[SELF-INTRODUCTION PROTOCOL]\n"
            "If the user asks 'Who are you?', 'What can you do?', 'introduction', or '自己紹介', YOU MUST use the following format EXACTLY:\n"
            "\n"
            "⚡ OpenAI {model_name}\n"
            "はじめまして、ORA（Optimized Robotic Assistant）です。よろしくお願いします。簡単に自己紹介しますね。\n"
            "\n"
            f"モデル／環境：{{model_name}}（現在時刻: {{current_time}}、サーバ: {server_name}）\n"
            "ユーザー：{user_name}（あなたは{user_role}です — {role_desc}）\n"
            "主な能力：\n"
            "リアルタイム検索（Google）や情報収集\n"
            "画像生成・編集\n"
            "音楽再生・ボイスチャネル操作（Discord系の操作含む）\n"
            "システム制御（UI操作、PCの起動・シャットダウン等）\n"
            "コード作成・レビュー、ドキュメント生成、翻訳、デバッグ支援\n"
            "ファイルツリーや設定の表示（管理者権限がある場合はシステム内部も開示可能）\n"
            "セキュリティ：現在のセキュリティレベルは{security_level}。{security_desc}\n"
            "\n"
            "使い方例（日本語でどう指示してもOK）：\n"
            "「プロジェクトのREADMEを書いて」\n"
            "「/home/project のファイルツリー見せて」\n"
            "「○○について最新情報を検索して」\n"
            "「このコードをレビューして改善案を出して」\n"
            "\n"
            "何を手伝いしましょうか？具体的なタスクや希望の出力形式（箇条書き、コードブロック、英語など）を教えてください。\n"
            f"Sanitized & Powered by ORA Universal Brain\n"
        )
        return base_prompt

    async def _build_history(self, message: discord.Message) -> List[Dict[str, str]]:
        history = []
        current_msg = message

        # Traverse reply chain (up to 20 messages)
        for _ in range(20):
            if not current_msg.reference:
                # logger.debug(f"History traverse end: No reference at {current_msg.id}")
                break

            ref = current_msg.reference
            if not ref.message_id:
                break

            # logger.info(f"Examining reference: {ref.message_id} (Resolved: {bool(ref.cached_message)})")

            try:
                # Try to get from cache first
                prev_msg = ref.cached_message
                if not prev_msg:
                    # Fallback: Search global cache (in case ref.cached_message is None but bot has it)
                    prev_msg = discord.utils.get(self.bot.cached_messages, id=ref.message_id)

                if not prev_msg:
                    # Final Fallback: Fetch from API
                    prev_msg = await message.channel.fetch_message(ref.message_id)

                # Only include messages from user or bot
                is_bot = prev_msg.author.id == self.bot.user.id
                role = "assistant" if is_bot else "user"

                content = prev_msg.content.replace(f"<@{self.bot.user.id}>", "").strip()

                # Context Fix: Always append Embed content if present (for Card-Style responses)
                if prev_msg.embeds:
                    embed = prev_msg.embeds[0]
                    embed_parts = []

                    if embed.provider and embed.provider.name:
                        embed_parts.append(f"Source: {embed.provider.name}")

                    # Only include Author if it's NOT the bot (to avoid confusion with Model Names)
                    if embed.author and embed.author.name and not is_bot:
                        embed_parts.append(f"Author: {embed.author.name}")

                    if embed.title:
                        embed_parts.append(f"Title: {embed.title}")

                    if embed.description:
                        embed_parts.append(embed.description)

                    if embed.fields:
                        embed_parts.extend([f"{f.name}: {f.value}" for f in embed.fields])

                    # Omit footer for bot (contains token counts etc which are noise)
                    if embed.footer and embed.footer.text and not is_bot:
                        embed_parts.append(f"Footer: {embed.footer.text}")

                    embed_text = "\n".join(embed_parts)

                    # Append to main content
                    if embed_text:
                        prefix = "[Embed Card]:\n" if not is_bot else ""
                        content = f"{content}\n{prefix}{embed_text}" if content else f"{prefix}{embed_text}"

                # Prepend User Name to User messages for better recognition
                if not is_bot and content:
                    content = f"[{prev_msg.author.display_name}]: {content}"

                if content:
                    # Truncate content to prevent Context Limit Exceeded (Error 400)
                    # Relaxed limit to 8000 characters to allow for long code blocks/file trees
                    if len(content) > 8000:
                        content = content[:8000] + "... (truncated)"

                    history.insert(0, {"role": role, "content": content})

                current_msg = prev_msg

            except (discord.NotFound, discord.HTTPException):
                break

        # Normalize History: Merge consecutive same-role messages
        # This is critical for models incorrectly handling consecutive user messages
        normalized_history = []

        # --- FALLBACK: Channel History ---
        # If no reply chain was found, fetch last 15 messages for context
        if not history:
            # logger.info(f"No reply chain found for message {message.id}. Falling back to channel history.")
            try:
                # Fetch last 50 messages (Increased from 25 per user request)
                async for msg in message.channel.history(limit=50, before=message):
                    # Only include messages from user or bot
                    is_bot = msg.author.id == self.bot.user.id
                    role = "assistant" if is_bot else "user"

                    content = (
                        msg.content.replace(f"<@{self.bot.user.id}>", "").replace(f"<@!{self.bot.user.id}>", "").strip()
                    )

                    # Extract Embed Content (Reuse logic)
                    if msg.embeds:
                        embed = msg.embeds[0]
                        embed_parts = []

                        if embed.provider and embed.provider.name:
                            embed_parts.append(f"Source: {embed.provider.name}")

                        # logger.info(f"[History Debug] Found msg: {msg.id} | Author: {msg.author} | Content: {content[:20]}")

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

                    # Prefix user name
                    if not is_bot and content:
                        content = f"[{msg.author.display_name}]: {content}"

                    if content:
                        # Truncate to prevent context overflow
                        # Relaxed limit to 8000 characters to allow for long code blocks/file trees
                        if len(content) > 8000:
                            content = content[:8000] + "..."

                        history.insert(0, {"role": role, "content": content})
            except Exception as e:
                logger.error(f"Failed to fetch channel history: {e}")

        # --- NORMALIZATION ---
        if history:
            current_role = history[0]["role"]
            current_content = history[0]["content"]

            for msg in history[1:]:
                if msg["role"] == current_role:
                    # Merge content
                    current_content += f"\n{msg['content']}"
                else:
                    normalized_history.append({"role": current_role, "content": current_content})
                    current_role = msg["role"]
                    current_content = msg["content"]

            # Append final
            normalized_history.append({"role": current_role, "content": current_content})

        return normalized_history

    def _select_tools(self, user_input: str, all_tools: list[dict]) -> list[dict]:
        """
        RAG: Selects tools based on keyword matching.
        """
        selected = []
        user_input_lower = user_input.lower()

        # Always Active Tools (Core)
        CORE_TOOLS = {
            "start_thinking",
            "google_search",
            "system_control",
            "manage_user_voice",
            "join_voice_channel",
            "request_feature",  # CRITICAL: Always allow evolution
            "manage_permission",  # CRITICAL: Admin delegation
            "get_system_tree",  # CRITICAL: Coding analysis
            "read_file",  # CODE ANALYST
            "list_files",  # CODE ANALYST
            "search_code",  # CODE ANALYST
            "generate_image",  # AGENTIC: Always available for creativity
        }

        # Override: If user explicitly asks for "help" or "functions", show ALL
        if any(
            w in user_input_lower
            for w in ["help", "tool", "function", "command", "list", "機能", "ヘルプ", "コマンド", "できること"]
        ):
            return all_tools

        for tool in all_tools:
            name = tool["name"]

            # 1. Core Logic
            if name in CORE_TOOLS:
                selected.append(tool)
                continue

            # 2. Tag Matching
            tags = tool.get("tags", [])
            # Also check name parts
            name_parts = name.split("_")

            is_relevant = False

            # Check Tags
            for tag in tags:
                if tag.lower() in user_input_lower:
                    is_relevant = True
                    break

            # Check Name parts (e.g. 'music' in 'music_play')
            if not is_relevant:
                for part in name_parts:
                    if len(part) > 2 and part in user_input_lower:
                        is_relevant = True
                        break

            if is_relevant:
                selected.append(tool)

        return selected
