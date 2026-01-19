import logging
import time
import asyncio
import json
import re
import secrets
import datetime
from datetime import datetime as dt_class # Avoid conflict
import discord
from typing import Optional, List, Dict, Any, Tuple

from src.utils.cost_manager import Usage
from src.config import ROUTER_CONFIG

logger = logging.getLogger(__name__)

class ChatHandler:
    def __init__(self, cog):
        self.cog = cog
        self.bot = cog.bot
        
    async def handle_prompt(self, message: discord.Message, prompt: str, existing_status_msg: Optional[discord.Message] = None, is_voice: bool = False, force_dm: bool = False) -> None:
        """Process a user message and generate a response using the LLM."""
        
        # --- Dashboard Update: Immediate Feedback ---
        try:
             memory_cog = self.bot.get_cog("MemoryCog")
             if memory_cog:
                 asyncio.create_task(memory_cog.update_user_profile(
                     message.author.id, 
                     {"status": "Processing", "impression": f"Input: {prompt[:20]}..."}, 
                     message.guild.id if message.guild else None
                 ))
        except Exception as e:
            logger.warning(f"Dashboard Update Failed: {e}")
        # --------------------------------------------
        
        # 1. Check for Generation Lock
        if self.cog.is_generating_image:
            await message.reply("🎨 現在、画像生成を実行中です... 完了次第、順次回答しますので少々お待ちください！ (Waiting for image generation...)", mention_author=True)
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
                        formatted = "\n".join([f"[{dt_class.fromtimestamp(r['created_at']).strftime('%Y-%m-%d')}] User: {r['message'][:50]}..." for r in results])
                        rag_context = f"\n[AUTO-RAG: RECALL MEMORY]\nPrevious Conversations:\n{formatted}\n(Use this info to answer if relevant.)\n"
                    else:
                         rag_context = "\n[AUTO-RAG] No relevant memories found.\n"
            
            elif intent == "KNOWLEDGE":
                # Execute Knowledge Logic Directly (Placeholder + Facts)
                logger.info(f"📚 [Router] KNOWLEDGE Triggered for: {prompt[:30]}")
                if memory_cog:
                     profile = await memory_cog.get_user_profile(message.author.id, message.guild.id if message.guild else None)
                     if profile:
                        facts = profile.get("layer2_user_memory", {}).get("facts", [])
                        matches = [f for f in facts if any(k in prompt.lower() for k in f.lower().split())]
                        if matches:
                            rag_context = f"\n[AUTO-RAG: KNOWLEDGE]\nUser Facts:\n- " + "\n- ".join(matches) + "\n"

            # Inject RAG Context into Prompt
            if rag_context:
                prompt += rag_context
                logger.info(f"🔗 RAG Context Injected ({len(rag_context)} chars)")

        # ----------------------------------------------------

        # 0.1 SUPER PRIORITY: System Override (Admin Chat Trigger)
        if "管理者権限でオーバーライド" in prompt:
             # Cinematic Override Sequence
             from ..managers.status_manager import StatusManager
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
                 await memory_cog.update_user_profile(message.author.id, {"layer1_session_meta": {"system_status": "OVERRIDE"}}, message.guild.id if message.guild else None)
             
             await status_manager.next_step("✅ フルアクセス: 承認", force=True)
             await asyncio.sleep(0.5)
             
             embed = discord.Embed(title="🚨 SYSTEM OVERRIDE ACTIVE", description="**[警告] 安全装置が解除されました。**\n無限生成モード: **有効**", color=discord.Color.red())
             embed.set_footer(text="System Integrity: UNLOCKED (危殆化)")
             
             await status_manager.finish() 
             await message.reply(embed=embed)
             return


        # 0.1.5 System Override DISABLE
        if "オーバーライド解除" in prompt:
             from ..managers.status_manager import StatusManager
             status_manager = StatusManager(message.channel)
             await status_manager.start("🔄 安全装置を再起動中...", mode="override")
             await asyncio.sleep(0.5)

             self.cog.cost_manager.toggle_unlimited_mode(False, user_id=None)
             
             await status_manager.next_step("✅ リミッター: 再適用", force=True)
             
             # Sync Dashboard
             if memory_cog:
                 await memory_cog.update_user_profile(message.author.id, {"layer1_session_meta": {"system_status": "NORMAL"}}, message.guild.id if message.guild else None)

             embed = discord.Embed(title="🔰 SYSTEM RESTORED", description="安全装置が正常に再起動しました。\n通常モードに戻ります。", color=discord.Color.green())
             await status_manager.finish()
             await message.reply(embed=embed)
             return

        # Initialize StatusManager (Normal)
        from ..managers.status_manager import StatusManager
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
                gen_prompt = prompt.replace("画像生成", "").replace("描いて", "").replace("イラスト", "").replace("絵を描いて", "").strip()
                if not gen_prompt: gen_prompt = "artistic masterpiece"
                
                try:
                     from ..views.image_gen import AspectRatioSelectView
                     view = AspectRatioSelectView(self.cog, gen_prompt, "", model_name="FLUX.2")
                     await message.reply(f"🎨 **画像生成アシスタント**\nPrompt: `{gen_prompt}`\nアスペクト比を選択して生成を開始してください。", view=view)
                     return 
                except Exception as e:
                     logger.error(f"Image Bypass Failed: {e}")
            
             # Layer
             if any(k in prompt for k in ["レイヤー", "分解", "layer", "psd"]):
                 if message.attachments or message.reference:
                     logger.info("Direct Layer Bypass Triggered")
                     await self.cog._execute_tool("layer", {}, message) # Force Tool Call
                     return

        # 1.6 DIRECT BYPASS: "Music" Trigger
        music_keywords = ["流して", "再生", "かけて"]
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
        await self.cog._store.ensure_user(message.author.id, self.cog._privacy_default, display_name=message.author.display_name)

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
                embed = discord.Embed(title="🧠 Universal Brain Setup", description="Mode Selection...", color=discord.Color.gold())
                onboard_msg = await message.reply(embed=embed, view=view)
                await view.wait()
                if view.value is None:
                    self.cog.user_prefs.set_mode(message.author.id, "private")
                    await onboard_msg.edit(content="⏳ Timeout -> Private Mode.", embed=None, view=None)

            # 1. Determine User Lane
            user_mode = self.cog.user_prefs.get_mode(message.author.id) or "private"
            
            # 2. Build Context
            system_prompt = await self.cog._build_system_prompt(message, model_hint="Ministral 3 (14B)")
            history = []
            try:
                history = await self.cog._build_history(message)
            except Exception as e:
                logger.error(f"History build failed: {e}")
            
            messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": prompt}]
            
            # Check Multimodal
            has_image = False
            if message.attachments:
                has_image = True

            # 4. Routing Decision (Universal Brain Router V3)
            target_provider = "local"
            clean_messages = messages
            selected_route = {"provider": "local", "lane": "stable", "model": None}
            
            logger.info(f"🧩 [Router] User Mode: {user_mode} | Has Image: {has_image}")
            
            if user_mode == "smart":
                pkt = self.cog.sanitizer.sanitize(prompt, has_image=has_image)
                if pkt.ok:
                    est_usd = len(prompt) / 4000 * 0.00001
                    est_usage = Usage(tokens_in=len(prompt)//4, usd=est_usd)
                    
                    can_burn_gemini = self.cog.cost_manager.can_call("burn", "gemini_trial", message.author.id, est_usage)
                    can_high_openai = self.cog.cost_manager.can_call("high", "openai", message.author.id, est_usage)
                    can_stable_openai = self.cog.cost_manager.can_call("stable", "openai", message.author.id, est_usage)
                    
                    if has_image:
                         if can_burn_gemini.allowed and self.bot.google_client:
                             target_provider = "gemini_trial"
                             target_model = ROUTER_CONFIG.get("vision_model", "gemini-2.0-flash-exp")
                             selected_route = {"provider": "gemini_trial", "lane": "burn", "model": target_model}
                             actual_sys = await self.cog._build_system_prompt(message, model_hint=target_model)
                             clean_messages = [{"role": "system", "content": actual_sys}, {"role": "user", "content": pkt.text}] 
                         else:
                             target_provider = "local"

                    elif self.cog.unified_client.openai_client:
                        prompt_lower = prompt.lower()
                        coding_kws = ROUTER_CONFIG.get("coding_keywords", [])
                        high_intel_kws = ROUTER_CONFIG.get("high_intel_keywords", [])
                        
                        is_code = any(k in prompt_lower for k in coding_kws)
                        is_high_intel = (len(prompt) > 50) or any(k in prompt_lower for k in high_intel_kws)
                        
                        if is_code:
                            if can_high_openai.allowed:
                                target_provider = "openai"
                                target_model = ROUTER_CONFIG.get("coding_model", "gpt-5.1-codex")
                                selected_route = {"provider": "openai", "lane": "high", "model": target_model}
                            elif can_stable_openai.allowed:
                                target_provider = "openai"
                                target_model = ROUTER_CONFIG.get("standard_model", "gpt-5-mini")
                                selected_route = {"provider": "openai", "lane": "stable", "model": target_model}
                        elif is_high_intel:
                             if can_high_openai.allowed:
                                target_provider = "openai"
                                target_model = ROUTER_CONFIG.get("high_intel_model", "gpt-5.1")
                                selected_route = {"provider": "openai", "lane": "high", "model": target_model}
                             elif can_stable_openai.allowed:
                                target_provider = "openai"
                                target_model = ROUTER_CONFIG.get("standard_model", "gpt-5-mini")
                                selected_route = {"provider": "openai", "lane": "stable", "model": target_model}
                        elif can_stable_openai.allowed:
                            target_provider = "openai"
                            target_model = ROUTER_CONFIG.get("standard_model", "gpt-5-mini")
                            selected_route = {"provider": "openai", "lane": "stable", "model": target_model}
                            
                        if target_provider == "openai":
                             actual_sys = await self.cog._build_system_prompt(message, model_hint=target_model, provider="openai")
                             clean_messages = [{"role": "system", "content": actual_sys}, {"role": "user", "content": pkt.text}]

            # 4. Execution
            content = None
            if target_provider == "gemini_trial":
                 await status_manager.next_step("🔥 Gemini (Vision) Analysis...")
                 rid = secrets.token_hex(4)
                 self.cog.cost_manager.reserve("burn", "gemini_trial", message.author.id, rid, est_usage)
                 try:
                     content, tool_calls, usage = await self.bot.google_client.chat(messages=clean_messages, model_name="gemini-1.5-pro")
                     self.cog.cost_manager.commit("burn", "gemini_trial", message.author.id, rid, est_usage)
                 except Exception as e:
                     self.cog.cost_manager.rollback("burn", "gemini_trial", message.author.id, rid)
                     target_provider = "local"

            elif target_provider == "openai":
                 lane = selected_route["lane"]
                 model = selected_route["model"]
                 icon = "💎" if lane == "high" else "⚡"
                 await status_manager.next_step(f"{icon} OpenAI Shared ({model})...")
                 
                 rid = secrets.token_hex(4)
                 self.cog.cost_manager.reserve(lane, "openai", message.author.id, rid, est_usage)
                 try:
                     candidate_tools = self.cog._select_tools(prompt, self.cog.tool_definitions)
                     candidate_tools = [t for t in candidate_tools if t['name'] not in ["recall_memory", "search_knowledge_base"]]
                     openai_tools = [{"type": "function", "function": {k:v for k,v in t.items() if k!="tags"}} for t in candidate_tools] if candidate_tools else None
                     
                     max_turns = 5
                     current_turn = 0
                     while current_turn < max_turns:
                         current_turn += 1
                         est_turn_cost = Usage(tokens_in=0, tokens_out=0, usd=0.01)
                         if not self.cog.cost_manager.can_call(lane, "openai", message.author.id, est_turn_cost).allowed:
                             break
                             
                         content, tool_calls, usage = await self.cog.unified_client.chat("openai", clean_messages, model=model, tools=openai_tools)
                         
                         if tool_calls:
                             clean_messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                             await status_manager.next_step(f"🛠️ ツール実行中 ({len(tool_calls)}件)...")
                             
                             for tc in tool_calls:
                                 func = tc.get("function", {})
                                 fname = func.get("name")
                                 fargs_str = func.get("arguments", "{}")
                                 call_id = tc.get("id")
                                 try: fargs = json.loads(fargs_str)
                                 except: fargs = {}
                                 
                                 if fname in ["recall_memory", "search_knowledge_base"]:
                                     # Not passed to OpenAI anyway
                                     pass
                                 
                                 # Execute Trigger
                                 tool_output = await self.cog._execute_tool(fname, fargs, message, status_manager)
                                 clean_messages.append({
                                     "role": "tool",
                                     "tool_call_id": call_id,
                                     "name": fname,
                                     "content": str(tool_output)
                                 })
                             continue
                         else:
                             # Commit
                             lane = selected_route.get("lane", "stable")
                             u_in = usage.get("prompt_tokens") or 0
                             u_out = usage.get("completion_tokens") or 0
                             actual_usd = (u_in * 0.0000025) + (u_out * 0.000010)
                             self.cog.cost_manager.commit(lane, "openai", message.author.id, rid, Usage(tokens_in=u_in, tokens_out=u_out, usd=actual_usd))
                             break
                 except Exception as e:
                     self.cog.cost_manager.rollback(lane, "openai", message.author.id, rid)
                     target_provider = "local"

            if target_provider == "local" or not content:
                 await status_manager.next_step("🏠 Local Brain (Ministral) で思考中...")
                 # Local logic simplified for brevity (Multimodal handled in original)
                 try:
                    content, _, _ = await asyncio.wait_for(
                        self.cog._llm.chat(messages=messages, temperature=0.7),
                        timeout=60.0
                    )
                 except asyncio.TimeoutError:
                    content = "Time out."

            # Final Processing
            await status_manager.finish()
            
            # Send (Chunked)
            while content:
                curr = content[:2000]
                content = content[2000:]
                await message.reply(curr)
                
        except Exception as e:
            logger.error(f"Chat Error: {e}")
            await status_manager.finish()
            await message.reply("システムエラーが発生しました。")
