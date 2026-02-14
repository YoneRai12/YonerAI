from typing import Any, Dict
from datetime import datetime
from ora_core.api.schemas.messages import MessageRequest
from ora_core.brain.memory import memory_store

class ContextBuilder:
    """
    Assembles the context (System Prompt + History) for the LLM.
    Layers L1 (Session), L2 (User Facts), L3 (Summaries) are merged here.
    Includes Security Protocols, Admin Detection, and Rich Personality.
    """
    
    @staticmethod
    async def build_context(req: MessageRequest, internal_user_id: str, conversation_id: str, repo: Any) -> list[dict]:
        """
        Builds the 4-layer context messages for the LLM.
        L1: Session History (from DB or client-provided)
        L2: User Traits/Facts (from MemoryStore)
        L3: Recent Summaries (from MemoryStore)
        L4: Raw Logs (implicitly handled by Update Policy)
        """
        # 1. Resolve Memory ID (Migration Compatibility / Scoped Partitioning)
        guild_id = None
        if req.client_context and req.client_context.guild_id:
            guild_id = req.client_context.guild_id

        if req.user_identity.provider == "discord":
            # Discord uses scoped storage: {user_id}_{guild_id}_public.json
            if guild_id:
                target_memory_id = f"{req.user_identity.id}_{guild_id}_public"
            else:
                target_memory_id = req.user_identity.id
        else:
            target_memory_id = internal_user_id

        profile = await memory_store.get_or_create_profile(target_memory_id, req.user_identity.display_name or "User")

        # 2. Build History
        # Priority: Client-provided history > DB history
        llm_history = []
        if req.client_history:
            # Use pre-built history from client (richer - includes embed content, reply chains)
            for h in req.client_history:
                content = h.content
                # Prefix user messages with display name if available
                if h.role == "user" and h.author_name:
                    content = f"[{h.author_name}]: {content}"
                llm_history.append({"role": h.role, "content": content})
        else:
            # Fallback: Fetch from DB
            history_msgs = await repo.get_messages(conversation_id, limit=15)
            for h in history_msgs:
                author = str(h.author)
                content = str(h.content)
                if content == req.content and author == "user":
                    continue
                llm_history.append({"role": author, "content": content})

        # 3. Construct Rich System Prompt
        system_prompt = await ContextBuilder._construct_system_prompt(req, profile)
        
        # 4. Assemble Final Message List
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        summaries = profile.get("layer3_recent_summaries", [])
        if summaries:
            formatted_summaries = []
            for s in summaries[-5:]:  # Show last 5
                if isinstance(s, dict):
                    title = s.get("title", "Untitled")
                    ts = s.get("timestamp", "")
                    snippet = s.get("snippet", "")
                    formatted_summaries.append(f"- {title} [{ts}]: {snippet}")
                else:
                    formatted_summaries.append(f"- {s}")
            
            summary_text = "\n".join(formatted_summaries)
            messages.append({
                "role": "system", 
                "content": f"## Context Summary of Past Interactions\n{summary_text}"
            })

        # Channel Memory Injection
        ctx = req.client_context
        channel_memory = None
        
        if ctx and ctx.channel_memory:
            channel_memory = ctx.channel_memory
        elif ctx and ctx.channel_id:
            # Try to load from local file storage if shared
            import os
            import json
            from ora_core.brain.memory import CHANNEL_MEMORY_DIR
            c_path = os.path.join(CHANNEL_MEMORY_DIR, f"{ctx.channel_id}.json")
            if os.path.exists(c_path):
                try:
                    with open(c_path, "r", encoding="utf-8") as f:
                        channel_memory = json.load(f)
                except: pass

        if channel_memory:
            c_text = ""
            if channel_memory.get("summary"):
                c_text += f"- Summary: {channel_memory['summary']}\n"
            if channel_memory.get("topics"):
                c_text += f"- Topics: {', '.join(channel_memory['topics'])}\n"
            if channel_memory.get("atmosphere"):
                c_text += f"- Atmosphere: {channel_memory['atmosphere']}\n"
            if c_text:
                messages.append({
                    "role": "system",
                    "content": f"[CHANNEL MEMORY (Context of this place)]\n{c_text}(Note: This is background context. Prioritize the CURRENT conversation flow.)"
                })

        # L1: History
        messages.extend(llm_history)

        # Current Request (supports multimodal attachments)
        messages.append({"role": "user", "content": ContextBuilder._build_user_content(req)})
        
        return messages

    @staticmethod
    def _build_user_content(req: MessageRequest) -> Any:
        """
        Build user content for OpenAI chat format.
        - Text-only -> str
        - Text + image(s) -> content parts list
        """
        text = req.content or ""
        parts: list[dict[str, Any]] = []

        if text:
            parts.append({"type": "text", "text": text})

        for att in (req.attachments or []):
            att_type = ContextBuilder._att_get(att, "type")
            if att_type == "image_url":
                url = ContextBuilder._extract_image_url(att)
                if url:
                    parts.append({"type": "image_url", "image_url": {"url": url}})
            elif att_type == "image_base64":
                b64 = ContextBuilder._att_get(att, "base64")
                mime = ContextBuilder._att_get(att, "mime") or "image/jpeg"
                if b64:
                    parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        # Keep plain string for text-only path to avoid unnecessary format changes.
        if len(parts) == 1 and parts[0].get("type") == "text":
            return text

        if parts:
            return parts

        return text

    @staticmethod
    def _extract_image_url(att: Any) -> str | None:
        # Canonical
        url = ContextBuilder._att_get(att, "url")
        if isinstance(url, str) and url:
            return url

        # Legacy nested shape: {"image_url": {"url": "..."}}
        nested = ContextBuilder._att_get(att, "image_url")
        if isinstance(nested, dict):
            nested_url = nested.get("url")
            if isinstance(nested_url, str) and nested_url:
                return nested_url

        return None

    @staticmethod
    def _att_get(att: Any, key: str) -> Any:
        if isinstance(att, dict):
            return att.get(key)
        return getattr(att, key, None)

    @staticmethod
    async def _construct_system_prompt(req: MessageRequest, profile: Dict[str, Any]) -> str:
        """
        Builds the System Prompt with:
        - Base Personality (YonerAI Identity)
        - Context Awareness (Time, User, Server)
        - 4-Layer Memory Injection
        - Security Protocols (Admin vs Guest)
        - Capability Instructions
        - Self-Introduction Protocol
        """
        name = profile.get("name", "User")
        ctx = req.client_context
        
        # 1. Base Personality
        now_str = ctx.timestamp if ctx and ctx.timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        server_name = ctx.server_name if ctx else "Unknown"
        
        base_prompt = (
            "You are YonerAI (formerly ORA), a highly advanced AI assistant system.\n"
            "Your goal is to assist the user efficiently, securely, and with clear boundaries.\n"
            f"Current Time: {now_str}\n"
            f"User: {name} (ID: {req.user_identity.id})\n"
        )
        if server_name and server_name != "Unknown":
            base_prompt += f"Server: {server_name}\n"

        # 2. L2: User Memory Injection
        l2 = profile.get("layer2_user_memory", {})
        facts = l2.get("facts", [])
        traits = l2.get("traits", [])
        interests = l2.get("interests", [])
        impression = l2.get("impression", "New friend.")
        
        if impression:
            base_prompt += f"User Axis(L2): {impression}\n"
        if facts:
            base_prompt += f"Facts(L2): {', '.join(facts[:5])}\n"
        if interests:
            base_prompt += f"Interests(L2): {', '.join(interests[:5])}\n"

        # 3. SECURITY PROTOCOL (Critical)
        is_admin = ctx.is_admin if ctx else False
        is_sub_admin = ctx.is_sub_admin if ctx else False
        
        if is_admin or is_sub_admin:
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
                "3. DO NOT show raw configuration values or API keys.\n"
                "If asked for these, reply politely: '申し訳ありませんが、セキュリティ上の理由によりシステム情報の開示はできません。'\n"
                "However, you CAN use tools to help them (e.g. play music, search), just don't show *how* it works internally.\n"
            )

        # 4. Capability Instructions
        base_prompt += (
            "\n[Capabilities]\n"
            "- You may use tools for search, image/media workflows, chat support, and platform operations.\n"
            "- Do not advertise private/owner-only local machine operations in general self-introductions.\n"
            "- **CRITICAL: AUTO-EVOLUTION PROTOCOL**\n"
            "  If the user asks for something you cannot currently do,\n"
            "  **DO NOT** tell them to do it manually. **DO NOT** give up.\n"
            "  INSTEAD, use the `request_feature` tool to propose the code change immediately.\n"
            "  Say: 'I lack this capability, but I will evolve to add it now.' and call the tool.\n"
            "- Always be helpful, but safe.\n"
        )

        # 5. Self-Introduction Protocol
        display_server = server_name if server_name and server_name != "Unknown" else "Direct Message"
        security_level = "RED (Admin)" if (is_admin or is_sub_admin) else "GREEN (Guest)"
        security_desc = "システム内部の開示が可能です。" if (is_admin or is_sub_admin) else "セキュリティ上、システム情報は非開示です。"
        user_role = "管理者" if is_admin else ("サブ管理者" if is_sub_admin else "ゲスト")
        role_desc = "全権限を持っています" if is_admin else ("補助権限を持っています" if is_sub_admin else "一般ユーザーです")

        base_prompt += (
            "\n[SELF-INTRODUCTION PROTOCOL]\n"
            "If the user asks 'Who are you?', 'What can you do?', 'introduction', or '自己紹介', YOU MUST use the following format:\n\n"
            "⚡ YonerAI\n"
            "はじめまして、YonerAIです。よろしくお願いします。簡単に自己紹介します。\n\n"
            f"モデル／環境：YonerAI Core（現在時刻: {now_str}、サーバ: {display_server}）\n"
            f"ユーザー：{name}（あなたは{user_role}です — {role_desc}）\n"
            "主な能力：\n"
            "- リアルタイム検索（Google）や情報収集\n"
            "- 画像生成・編集\n"
            "- Discord と Web のマルチチャネル会話サポート\n"
            "- コード作成・レビュー、ドキュメント生成、翻訳、デバッグ支援\n"
            "- 管理操作は権限に応じて制限されます\n"
            f"セキュリティ：現在のセキュリティレベルは{security_level}。{security_desc}\n\n"
            "何を手伝いしましょうか？\n"
        )
        
        return base_prompt

