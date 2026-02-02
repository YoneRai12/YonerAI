import logging
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
        # Use a lightweight model for routing
        self.model_name = "gpt-5.1-codex-mini" 
        
        # Access key from bot config
        api_key = self.bot.config.openai_api_key or os.getenv("OPENAI_API_KEY")
        
        # Use Configured Base URL
        base_url = getattr(self.bot.config, "openai_base_url", "https://api.openai.com/v1")
        
        self.llm_client = LLMClient(
            base_url=base_url,
            api_key=api_key,
            model=self.model_name
        )

    async def select_tools(self, prompt: str, available_tools: Optional[List[dict]] = None, platform: str = "discord", rag_context: str = "") -> List[dict]:
        """
        Analyzes prompt and selects relevant tool CATEGORIES (Granular).
        """
        import time
        import uuid
        import hashlib
        
        start_time_total = time.perf_counter()
        request_id = str(uuid.uuid4())[:8]

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
            "SYSTEM_UTIL": {
                "desc": "Safe System Utils. Reminders, Memory, Help, Status checks. (SAFE DEFAULT)",
                "tools": []
            },
            "OTHER": {"desc": "Anything else.", "tools": []}
        }

        # --- CLASSIFICATION LOGIC (Mapping Tools to Categories) ---
        # Use sorted_tools here to be deterministic
        for tool in sorted_tools:
            name = tool["name"].lower()
            tags = set(tool.get("tags", []))
            
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
            
            # Discord
            elif any(x in name for x in ["ban", "kick", "role", "user", "server", "channel", "wipe"]):
                 categories["DISCORD_SERVER"]["tools"].append(tool)
            
            # System/Default
            else:
                 categories["SYSTEM_UTIL"]["tools"].append(tool)

        # 2. Build Prompt (S6: Prefix Stabilization)
        # Construct STATIC parts first for KV Cache optimization
        
        # Sort categories for stability
        sorted_cats = sorted(categories.items()) # List of tuples, keys sorted alphabetically
        
        cat_prompt_list = []
        for cat_key, cat_data in sorted_cats:
            if cat_data["tools"]: 
                cat_prompt_list.append(f"- {cat_key}: {cat_data['desc']}")
        
        # Static System Prompt (Strictly Canonical)
        system_prompt = (
            f"You are the ORA System Category Router. Your goal is to select the TOOL CATEGORIES required to fulfill the user's intent.\n"
            f"Current Platform: {platform.upper()}\n"
            f"Instructions:\n"
            f"1. **SAFETY FIRST**: If user asks to download/save, use WEB_FETCH. If just looking, use WEB_READ.\n"
            f"2. ANALYZE the User's GOAL (Concept-Based). Input may be in ANY language.\n"
            f"3. SELECT ALL Tool Categories required.\n"
            f"4. **OUTPUT FORMAT**: JSON Array of strings ONLY. No markdown. Example: [\"WEB_READ\", \"SYSTEM_UTIL\"]\n\n"
            f"Available Categories:\n" + "\n".join(cat_prompt_list) + "\n\n"
            f"[FEW-SHOT EXAMPLES]\n"
            f"- 'Save this video' -> [\"WEB_FETCH\"]\n"
            f"- 'Screenshot this' -> [\"WEB_READ\"]\n"
            f"- 'Who is this user?' -> [\"DISCORD_SERVER\"]\n"
            f"- 'Play music' -> [\"VOICE_AUDIO\"]\n"
        )
        
        # S6: Prefix Hash for Cache Hit Verification
        prefix_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]

        user_content = f"{rag_context}\nUser Prompt: {prompt}" if rag_context else f"User Prompt: {prompt}"
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}]

        log_payload = {
            "request_id": request_id,
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
                    if isinstance(parsed, list):
                        # S4: Filter Unknown Categories (Strict Allowlist)
                        valid_keys = set(categories.keys())
                        selected_categories = [k for k in parsed if k in valid_keys]
                        
                        if len(selected_categories) < len(parsed):
                            logger.warning(f"Filtered out unknown categories: {set(parsed) - set(selected_categories)}")
                        
                        break # Success
                    else:
                        logger.warning(f"Router returned non-list: {type(parsed)}")
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
            # S4 Critical: WEB_FETCH is STRICTLY EXCLUDED from Heuristics.
            lower_p = prompt.strip().lower()
            
            # Simple Browsing (Safe)
            if any(k in lower_p for k in ["http", "browse", "google", "search", "見せて", "開いて"]):
                 selected_categories.append("WEB_READ")
            
            # Voice (Functional)
            if any(k in lower_p for k in ["vc", "join", "leave", "music", "play", "speak", "voice"]):
                 selected_categories.append("VOICE_AUDIO")
                 
            # Discord (Safe-ish Info)
            if any(k in lower_p for k in ["server", "user", "info", "role", "whois"]):
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
        
        # S6: Structured Logging (Timing Split)
        end_time_total = time.perf_counter()
        total_ms = round((end_time_total - start_time_total) * 1000, 2)
        log_payload["router_local_ms"] = round(total_ms - log_payload["router_roundtrip_ms"], 2)
        log_payload["selected_categories"] = selected_categories
        
        logger.info(f"🧩 Router Decision", extra={"router_event": log_payload})
        
        # S7: Proactive Monitoring Integration
        try:
            from src.cogs.handlers.router_monitor import router_monitor
            router_monitor.add_event(log_payload)
        except Exception as e:
            logger.error(f"Failed to push metrics to RouterMonitor: {e}")
            
        return final_tools


