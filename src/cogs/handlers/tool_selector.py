import logging
import os
import json
import asyncio
from typing import List, Dict, Any, Optional

from src.utils.llm_client import LLMClient
# S5 Optimization: Use Registry instead of heavy ToolHandler import
from src.cogs.tools.registry import get_tool_schemas

logger = logging.getLogger(__name__)

class ToolSelector:
    """
    RAG-style Tool Selector (Router).
    Analyzes user prompt and selects relevant tools based on intent.
    [v4.0 Architecture Update]
    - S1: Deterministic (Temperature=0, Strict JSON)
    - S2: Safety Fallback (Default to Safe Tools on Error)
    - S3: Granular Categories (Split Web/Media for security)
    """

    def __init__(self, bot):
        self.bot = bot
        self.last_route_meta: Dict[str, Any] = {}
        # Use a lightweight but capable model for routing
        # S4: Fetch from bot config with fallback to specific reliable models
        bot_cfg = getattr(self.bot, "config", None)
        self.model_name = getattr(bot_cfg, "standard_model", "gpt-5-mini")
        if not self.model_name or self.model_name == "gpt-5-mini":
             # If config says gpt-4o-mini but it fails (404), we might want to track this.
             # In some environments, the user's provider might not support this name.
             # Check if we have an environment override.
             self.model_name = os.getenv("ROUTER_MODEL", self.model_name)

        # Access key from bot config
        api_key = (getattr(bot_cfg, "openai_api_key", None) or os.getenv("OPENAI_API_KEY"))

        # Use Configured Base URL
        base_url = getattr(bot_cfg, "openai_base_url", "https://api.openai.com/v1")

        self.llm_client = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model=self.model_name
        )

    async def select_tools(self, prompt: str, available_tools: Optional[List[dict]] = None, platform: str = "discord", rag_context: str = "", correlation_id: Optional[str] = None) -> List[dict]:
        """
        Analyzes prompt and selects relevant tool CATEGORIES (Granular).
        """
        import time
        import uuid
        import hashlib

        start_time_total = time.perf_counter()
        # S4-1: Use provided correlation_id or generate a request short-id
        trace_id = correlation_id or str(uuid.uuid4())[:8]

        # S5: Use Registry if no tools provided
        if available_tools is None:
             available_tools = get_tool_schemas()

        if not available_tools:
            return []

        # S6: Generate Tools Bundle ID (Canonical Hash)
        # Sort by name first
        sorted_tools = sorted(available_tools, key=lambda x: x.get("name", ""))
        tools_json = json.dumps(sorted_tools, sort_keys=True, separators=(",", ":"))
        tools_bundle_id = hashlib.sha256(tools_json.encode()).hexdigest()[:16]

        # 1. Define Granular Categories (S3)
        categories = {
            "WEB_READ": {
                "desc": "READ-ONLY Web Access. Browse, Screenshot, Dump content. NO downloading/saving files.",
                "tools": []
            },
            "WEB_FETCH": {
                "desc": "FILE DOWNLOADING & RECORDING. Select ONLY if user explicitly asks to 'Save', 'Download', 'Record' or 'Keep' media.",
                "tools": []
            },
            "MEDIA_ANALYZE": {
                "desc": "VIEWING/ANALYZING Images or Video. No generation.",
                "tools": []
            },
            "MEDIA_CREATE": {
                "desc": "GENERATING/EDITING Images, Video, Music. (DALL-E, Sora, Suno).",
                "tools": []
            },
            "VOICE_AUDIO": {
                "desc": "Voice Channel (VC) operations. Join, Leave, Speak (TTS), Play Music.",
                "tools": []
            },
            "DISCORD_SERVER": {
                "desc": "Server Management. Ban, Kick, Roles, User Info, Channel Ops.",
                "tools": []
            },
            "CODEBASE": {
                "desc": "Local codebase inspection tools (grep/find/read/tree). Select only for code/repo/debug requests.",
                "tools": [],
            },
            "MCP": {
                "desc": "Remote MCP (Model Context Protocol) tools from connected MCP servers.",
                "tools": [],
            },
            "SYSTEM_UTIL": {
                "desc": "Safe System Utils. Reminders, Memory, Help, Status checks. (SAFE DEFAULT)",
                "tools": []
            },
            "OTHER": {"desc": "Anything else.", "tools": []}
        }

        # --- CLASSIFICATION LOGIC (Mapping Tools to Categories) ---
        # Use sorted_tools here to be deterministic
        safe_system_tools: set[str] = {
            # Prefer keeping SYSTEM_UTIL small and actually safe.
            "say",
            "weather",
            "read_chat_history",
            "read_web_page",
            "get_logs",
            "system_info",
            "router_health",
            "check_privilege",
        }

        for tool in sorted_tools:
            name = tool["name"].lower()
            tags = set(tool.get("tags", []))

            # MCP remote tools
            if ("mcp" in tags) or name.startswith("mcp__"):
                categories["MCP"]["tools"].append(tool)
                continue

            # Web Split
            if name.startswith("web_"):
                if any(x in name for x in ["download", "record", "save", "fetch"]):
                    categories["WEB_FETCH"]["tools"].append(tool)
                else:
                    categories["WEB_READ"]["tools"].append(tool)

            # Media Split
            elif any(x in name for x in ["generate", "create", "imagine", "sora", "painting"]):
                 categories["MEDIA_CREATE"]["tools"].append(tool)
            elif any(x in name for x in ["vision", "analyze", "ocr", "describe"]):
                 categories["MEDIA_ANALYZE"]["tools"].append(tool)

            # Voice/Music
            elif any(x in name for x in ["voice", "speak", "tts", "music", "join", "leave"]) or "vc" in tags:
                 categories["VOICE_AUDIO"]["tools"].append(tool)

            # Codebase / local search
            elif ("code" in tags) or name.startswith("code_") or any(x in name for x in ["grep", "find", "read", "tree"]):
                 categories["CODEBASE"]["tools"].append(tool)

            # Discord
            elif any(x in name for x in ["ban", "kick", "role", "user", "server", "channel", "wipe"]):
                 categories["DISCORD_SERVER"]["tools"].append(tool)

            # System/Default
            elif (name in safe_system_tools) or ("system" in tags) or ("monitor" in tags) or ("health" in tags):
                 categories["SYSTEM_UTIL"]["tools"].append(tool)
            else:
                 categories["OTHER"]["tools"].append(tool)

        # 2. Build Prompt (S6: Prefix Stabilization)
        # Construct STATIC parts first for KV Cache optimization

        # Sort categories for stability
        sorted_cats = sorted(categories.items()) # List of tuples, keys sorted alphabetically

        cat_prompt_list = []
        for cat_key, cat_data in sorted_cats:
            if cat_data["tools"]:
                cat_prompt_list.append(f"- {cat_key}: {cat_data['desc']}")

        # Static System Prompt (Strictly Canonical)
        #
        # IMPORTANT: Do not rely on keyword heuristics in the bot for routing.
        # The router should infer intent (screenshot/control/download) conceptually and emit it as JSON.
        system_prompt = (
            f"You are the ORA System Category Router. Your goal is to select the TOOL CATEGORIES required to fulfill the user's intent.\n"
            f"Current Platform: {platform.upper()}\n"
            f"Instructions:\n"
            f"1. **SAFETY FIRST**: If user asks to download/save, use WEB_FETCH. If just looking, use WEB_READ.\n"
            f"2. ANALYZE the User's GOAL (Concept-Based). Input may be in ANY language.\n"
            f"3. SELECT ALL Tool Categories required.\n"
            f"4. **OUTPUT FORMAT** (JSON ONLY, no markdown):\n"
            f"   Preferred: {{\"categories\":[...],\"intents\":{{\"screenshot\":true|false,\"browser_control\":true|false,\"download\":true|false}}}}\n"
            f"   Example: {{\"categories\":[\"WEB_READ\"],\"intents\":{{\"screenshot\":true,\"browser_control\":false,\"download\":false}}}}\n\n"
            f"Available Categories:\n" + "\n".join(cat_prompt_list) + "\n\n"
            f"[FEW-SHOT EXAMPLES]\n"
            f"- 'Save this video' -> {{\"categories\":[\"WEB_FETCH\"],\"intents\":{{\"download\":true,\"screenshot\":false,\"browser_control\":false}}}}\n"
            f"- 'Screenshot this' -> {{\"categories\":[\"WEB_READ\"],\"intents\":{{\"screenshot\":true,\"browser_control\":false,\"download\":false}}}}\n"
            f"- 'Open the browser and click X' -> {{\"categories\":[\"WEB_READ\"],\"intents\":{{\"browser_control\":true,\"screenshot\":false,\"download\":false}}}}\n"
            f"- 'Who is this user?' -> {{\"categories\":[\"DISCORD_SERVER\"],\"intents\":{{\"screenshot\":false,\"browser_control\":false,\"download\":false}}}}\n"
             f"- 'Play music' -> {{\"categories\":[\"VOICE_AUDIO\"],\"intents\":{{\"screenshot\":false,\"browser_control\":false,\"download\":false}}}}\n"
             f"- '動画を保存して' -> {{\"categories\":[\"WEB_FETCH\"],\"intents\":{{\"download\":true,\"screenshot\":false,\"browser_control\":false}}}}\n"
             f"- 'このページをスクショして' -> {{\"categories\":[\"WEB_READ\"],\"intents\":{{\"screenshot\":true,\"browser_control\":false,\"download\":false}}}}\n"
             f"- 'Use an MCP tool' -> {{\"categories\":[\"MCP\"],\"intents\":{{\"screenshot\":false,\"browser_control\":false,\"download\":false}}}}\n"
         )

        # S6: Prefix Hash for Cache Hit Verification
        prefix_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]

        user_content = f"{rag_context}\nUser Prompt: {prompt}" if rag_context else f"User Prompt: {prompt}"
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]

        log_payload = {
            "request_id": trace_id,
            "correlation_id": correlation_id,
            "input_snippet": prompt[:50],
            "model": self.model_name,
            "retry_count": 0,
            "fallback_triggered": False,
            "selected_categories": [],
            "router_roundtrip_ms": 0, # LLM Time
            "router_local_ms": 0,     # Total - LLM
            "prefix_hash": prefix_hash,
            "tools_bundle_id": tools_bundle_id
        }

        try:
            # 3. Call LLM (Deterministic S1 with Retry S4)
            # Force temperature=0 for stability
            # S4: Retry Loop (Max 2 attempts) for JSON validity
            max_retries = 2
            selected_categories = []
            router_intents: Dict[str, bool] = {"screenshot": False, "browser_control": False, "download": False}

            for attempt in range(max_retries + 1):
                t0_llm = time.perf_counter()
                response_text, _, _ = await self.llm_client.chat(messages, temperature=0.0)
                t1_llm = time.perf_counter()

                # Accumulate roundtrip time (last successful or attempted call)
                log_payload["router_roundtrip_ms"] = round((t1_llm - t0_llm) * 1000, 2)

                if not response_text:
                    if attempt < max_retries:
                        logger.warning(f"Router returned empty response (Attempt {attempt+1}). Retrying...")
                        log_payload["retry_count"] += 1
                        continue
                    else:
                        raise ValueError("Empty response from Router after retries")

                # 4. Parse JSON (Strict S1/S2)
                clean_text = response_text.replace("```json", "").replace("```", "").strip()
                # Handle list-like strings that might be wrapped in quotes or brackets
                if not clean_text.startswith("[") and "[" in clean_text:
                     start = clean_text.find("[")
                     end = clean_text.rfind("]") + 1
                     clean_text = clean_text[start:end]

                try:
                    parsed = json.loads(clean_text)
                    # Backward compatible: accept either list OR object.
                    if isinstance(parsed, list):
                        cats_raw = parsed
                    elif isinstance(parsed, dict):
                        cats_raw = parsed.get("categories") or parsed.get("selected_categories") or []
                        intents_raw = parsed.get("intents") or {}
                        if isinstance(intents_raw, dict):
                            for k in ("screenshot", "browser_control", "download"):
                                try:
                                    router_intents[k] = bool(intents_raw.get(k, False))
                                except Exception:
                                    router_intents[k] = False
                    else:
                        cats_raw = []

                    if isinstance(cats_raw, list):
                        # S4: Filter Unknown Categories (Strict Allowlist)
                        valid_keys = set(categories.keys())
                        selected_categories = [k for k in cats_raw if k in valid_keys]
                        if len(selected_categories) < len(cats_raw):
                            logger.warning(f"Filtered out unknown categories: {set(cats_raw) - set(selected_categories)}")
                        break  # Success

                    logger.warning(f"Router returned invalid JSON shape: {type(parsed)}")
                except json.JSONDecodeError:
                    logger.warning(f"Router JSON Decode Error: {clean_text}")

                if attempt < max_retries:
                    # Optional: Add error feedback to prompt? Simplified: just retry.
                    logger.warning(f"Retrying Router (Attempt {attempt+1})...")
                    log_payload["retry_count"] += 1
                    continue

            # Use 'selected_categories' from loop
            if not selected_categories and not response_text: # actually if loop finished without break and no valid cat
                 # If we are here, we might have failed parsing fully
                 if not selected_categories:
                     raise ValueError("Failed to parse valid categories after retries")

        except Exception as e:
            logger.warning(f"⚠️ Router Failed via LLM ({e}). Invoking Safety Fallback.", extra={"error": str(e)})
            log_payload["fallback_triggered"] = True

            # FALLBACK (S2): Do not return nothing. Return SAFE defaults + Heuristics.
            selected_categories = ["SYSTEM_UTIL"] # Always allow system safe tools

            # -- ROBUST HEURISTICS (S2/S3/S4) --
            # Only map keywords to SAFE categories or necessary functional ones.
            # S4 Critical: WEB_FETCH is allowed on fallback ONLY if highly certain
            import re

            lower_p = prompt.strip().lower()

            # [DEBUG] Log raw prompt for fallback analysis
            logger.info(f"Fallback Analysis Prompt: {lower_p}")

            # Robust URL detection (e.g. contains http:// or https://)
            has_url = re.search(r'https?://[^\s]+', lower_p) is not None

            # Simple Browsing & Searching (Safe)
            # Expanded Japanese keywords: 検索, 調べて, 調査, 教えて, 見せて, 探し, wiki, whois, クローム, 記事, サイト
            search_keywords = ["検索", "調べて", "調査", "教えて", "見せて", "探し", "wiki", "google", "search", "browse", "whois", "誰", "何者", "クローム", "chrome", "記事", "サイト"]
            if has_url or any(k in lower_p for k in search_keywords) or any(k in lower_p for k in ["http", "google", "開いて", "スクショ", "撮って", "screenshot"]):
                 selected_categories.append("WEB_READ")

            # [CRITICAL UPDATE] WEB_FETCH allows on fallback ONLY if highly certain
            # If prompt has URL AND download-related keywords, allow it.
            # Expanded Japanese keywords: 保存, ダウンロード, 落として, 録画, download, save, record, 持ってきて
            download_keywords = ["save", "download", "fetch", "record", "保存", "ダウンロード", "落として", "録画", "持ってきて"]
            if (has_url or any(k in lower_p for k in ["動画", "ビデオ", "mp4"])) and any(k in lower_p for k in download_keywords):
                 selected_categories.append("WEB_FETCH")

            # MCP (explicit)
            if "mcp" in lower_p:
                selected_categories.append("MCP")

            # Voice (Functional)
            if any(k in lower_p for k in ["vc", "join", "leave", "music", "play", "speak", "voice", "歌って", "流して"]):
                 selected_categories.append("VOICE_AUDIO")

            # Discord (Safe-ish Info)
            # Expanded: ロール, 権限, 誰, 何
            if any(k in lower_p for k in ["server", "user", "info", "role", "whois", "鯖", "ユーザー", "誰", "ロール", "権限", "何"]):
                 selected_categories.append("DISCORD_SERVER")

            # Note: We do NOT auto-add WEB_FETCH (Download) on fallback for security.
            # User must re-prompt if Router fails on a sensitive action.

        # 5. Expand Categories -> Tools
        # (If LLM succeeded, we trust it. If failed, we use the fallback list above)

        final_tools = []
        seen_tools = set()

        for cat_key in selected_categories:
            if cat_key in categories:
                # Tools inside buckets are already sorted by insertion order from sorted_tools
                for tool in categories[cat_key]["tools"]:
                    if tool["name"] not in seen_tools:
                        final_tools.append(tool)
                        seen_tools.add(tool["name"])

        # Narrowing:
        # The router can over-expose remote browser tools when a URL is present.
        # Primary signal is the router's inferred intents. Keyword checks are fallback-only.
        p_low = (prompt or "").lower()

        wants_screenshot = bool(router_intents.get("screenshot", False))
        wants_browser_control = bool(router_intents.get("browser_control", False))
        wants_download = bool(router_intents.get("download", False))

        # Fallback only (when router intent is all false): minimal keyword heuristics
        if not (wants_screenshot or wants_browser_control or wants_download):
            wants_screenshot = any(k in p_low for k in ["スクショ", "スクリーンショット", "screenshot", "画面", "キャプチャ", "撮って", "撮影", "撮ってきて", "撮って来て"])
            wants_browser_control = any(k in p_low for k in ["webひらいて", "web操作", "ブラウザ", "remote", "操作して", "開いて操作"])
        is_code_review = ("github.com" in p_low or "gitlab.com" in p_low) and any(k in p_low for k in ["コード", "repo", "リポジトリ", "review", "監査", "読んで"])

        remote_browser_tools = {
            "web_remote_control",
            "web_action",
            "web_navigate",
            "web_set_view",
            "web_record_screen",
            "web_screenshot",
        }
        if is_code_review and not wants_screenshot and not wants_browser_control:
            final_tools = [t for t in final_tools if t.get("name") not in remote_browser_tools]
        elif not wants_screenshot and not wants_browser_control:
            final_tools = [t for t in final_tools if t.get("name") not in remote_browser_tools]
        else:
            # If only screenshot is requested, allow screenshot but still avoid remote control unless asked.
            if wants_screenshot and not wants_browser_control:
                final_tools = [t for t in final_tools if t.get("name") not in (remote_browser_tools - {"web_screenshot"})]

        # Hard cap tool exposure to avoid "Tool Selection: 72 -> 29 tools" class issues.
        max_tools = int(os.getenv("ORA_ROUTER_MAX_TOOLS", "10") or "10")
        if len(final_tools) > max_tools:
            final_tools = self._cap_tools(
                final_tools,
                prompt,
                max_tools=max_tools,
                want_download=wants_download,
                want_screenshot=wants_screenshot,
                want_browser_control=wants_browser_control,
            )

        # S6: Structured Logging (Timing Split)
        end_time_total = time.perf_counter()
        total_ms = round((end_time_total - start_time_total) * 1000, 2)
        log_payload["router_local_ms"] = round(total_ms - log_payload["router_roundtrip_ms"], 2)
        log_payload["selected_categories"] = selected_categories

        # Complexity estimation (for Agentic task planning gate)
        complexity, reasons = self._assess_complexity(prompt, selected_categories, final_tools)
        log_payload["complexity"] = complexity
        if reasons:
            log_payload["complexity_reasons"] = reasons
        self.last_route_meta = {
            "complexity": complexity,
            "reasons": reasons,
            "selected_categories": list(selected_categories),
            "selected_tool_count": len(final_tools),
            "intents": {
                "screenshot": bool(wants_screenshot),
                "browser_control": bool(wants_browser_control),
                "download": bool(wants_download),
            },
        }

        logger.info(f"🧩 Router Decision", extra={"router_event": log_payload})

        # S7: Proactive Monitoring Integration
        try:
            from src.cogs.handlers.router_monitor import router_monitor
            router_monitor.add_event(log_payload)
        except Exception as e:
            logger.error(f"Failed to push metrics to RouterMonitor: {e}")

        return final_tools

    def _cap_tools(
        self,
        tools: List[dict],
        prompt: str,
        max_tools: int = 10,
        *,
        want_download: Optional[bool] = None,
        want_screenshot: Optional[bool] = None,
        want_browser_control: Optional[bool] = None,
    ) -> List[dict]:
        """
        Keep toolsets small and stable. Prefer the tools that most directly match the user's wording.
        """
        p = (prompt or "").lower()
        # Prefer router intents; keyword checks are fallback-only.
        if want_download is None:
            want_download = any(k in p for k in ["保存", "ダウンロード", "download", "save", "mp3", "mp4", "record", "録画"])
        if want_screenshot is None:
            want_screenshot = any(k in p for k in ["スクショ", "スクリーンショット", "screenshot", "キャプチャ", "撮って", "撮影", "撮ってきて", "撮って来て"])
        if want_browser_control is None:
            want_browser_control = any(k in p for k in ["webひらいて", "web操作", "ブラウザ", "remote", "操作して", "開いて操作"])
        want_web = any(k in p for k in ["http://", "https://", "web", "ブラウザ", "開いて", "サイト"])
        want_code = any(k in p for k in ["コード", "repo", "リポジトリ", "github", "gitlab", "バグ", "エラー", "stack trace"])
        want_mcp = "mcp" in p or "model context protocol" in p

        def score(t: dict) -> int:
            name = (t.get("name") or "").lower()
            tags = set((t.get("tags") or []))
            s = 0
            # Primary matches
            if want_download and ("download" in name or "save" in name or "record" in name):
                s += 50
            if want_screenshot and ("screenshot" in name):
                s += 40
            if want_browser_control and (name in {"web_remote_control", "web_action", "web_set_view"}):
                s += 35
            if want_web and ("web" in tags or name.startswith("web_") or "web" in name):
                s += 20
            if want_code and (name.startswith("code_") or "code" in tags):
                s += 20
            if want_mcp and ("mcp" in tags or name.startswith("mcp__")):
                s += 30
            # Safety bias
            if "system" in tags or "monitor" in tags or name in {"say", "weather", "read_web_page", "read_chat_history"}:
                s += 5
            # Prefer narrower tools
            if name in {"web_remote_control", "web_action"}:
                s -= 10
            return s

        ranked = sorted(tools, key=lambda t: (-score(t), (t.get("name") or "")))
        return ranked[: max(1, max_tools)]

    def _assess_complexity(self, prompt: str, selected_categories: List[str], selected_tools: List[dict]) -> tuple[str, List[str]]:
        """
        Return ("high"|"medium"|"low", reasons[]) for light-weight orchestration.
        """
        reasons: List[str] = []
        p = (prompt or "").lower()

        # Treat "what is this? <url>" as low complexity even if the router selects many safe tools.
        # This prevents unsolicited "execution plan" behavior for simple URL explanations.
        try:
            url_like = ("http://" in p) or ("https://" in p)
            short = len(p) <= 160
            ask_what = any(k in p for k in ["これなに", "これ何", "何これ", "what is this", "what's this"])
            wants_heavy = any(k in p for k in ["保存", "ダウンロード", "download", "save", "スクショ", "screenshot", "web操作", "remote"])
            if url_like and short and ask_what and not wants_heavy:
                return "low", ["simple_url_explain"]
        except Exception:
            pass

        if len(selected_categories) >= 3:
            reasons.append("multi_category(>=3)")
        if len(selected_tools) >= 5:
            reasons.append("multi_tool(>=5)")

        sequence_markers = [
            "してから", "そのあと", "次に", "まず", "最後に",
            "then", "after that", "first", "next", "finally",
            "and then", "step", "workflow",
        ]
        if any(m in p for m in sequence_markers):
            reasons.append("sequential_intent")

        if "WEB_FETCH" in selected_categories and "WEB_READ" in selected_categories:
            reasons.append("read_and_fetch_combo")
        if "VOICE_AUDIO" in selected_categories and ("WEB_READ" in selected_categories or "WEB_FETCH" in selected_categories):
            reasons.append("voice_plus_web_combo")

        if len(reasons) >= 2:
            return "high", reasons
        if len(reasons) == 1:
            return "medium", reasons
        return "low", reasons


