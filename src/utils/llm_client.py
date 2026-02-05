"""OpenAI-compatible client for LM Studio."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class TransientHTTPError(RuntimeError):
    pass


# Global semaphore for rate limiting
_SEM = asyncio.Semaphore(10)


def _mask_url(url: str) -> str:
    """Masks host/IP in URL to [RESTRICTED]."""
    import re
    # Simple regex to replace host:port or just host
    return re.sub(r'://[^/]+', '://[RESTRICTED]', url)


async def robust_json_request(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Any = None,
    total_retry_budget: float = 300.0,
    max_attempts: int = 5,
    # Injectables for testing
    _sleep_func=asyncio.sleep,
    _time_func=time.monotonic,
) -> Any:
    start_time = _time_func()
    deadline = start_time + total_retry_budget

    backoff = 1.0
    last_err = None

    for attempt in range(1, max_attempts + 1):
        # 1. Check Budget
        now = _time_func()
        remaining = deadline - now

        if remaining <= 0:
            raise asyncio.TimeoutError(f"Total retry budget ({total_retry_budget}s) exceeded")

        # 2. Determine Per-Attempt Timeout
        # Min of 300s or remaining budget (Large models take time to load)
        req_timeout_val = min(300.0, remaining)

        # 3. Acquire Semaphore
        try:
            async with _SEM:
                # 4. Execute Request
                # Short connect timeout to detect locally down services immediately
                timeout = aiohttp.ClientTimeout(total=req_timeout_val, connect=2.0, sock_connect=2.0, sock_read=300.0)

                try:
                    async with session.request(
                        method, url, headers=headers, params=params, json=json_data, timeout=timeout
                    ) as resp:
                        status = resp.status

                        # 5. Handle Retry-After
                        if status == 429 or 500 <= status < 600:
                            retry_after = float(resp.headers.get("Retry-After", 0))
                            if retry_after > 0:
                                # Check if we can afford to wait
                                current_remaining = deadline - _time_func()
                                if current_remaining < 0:
                                    logger.warning(
                                        f"Retry-After ({retry_after}s) > Remaining ({current_remaining:.2f}s). Aborting."
                                    )
                                    raise TransientHTTPError(f"Retry-After {retry_after}s exceeds budget")
                                await _sleep_func(retry_after)
                                continue

                            raise TransientHTTPError(f"Transient status {status}")

                        if 400 <= status < 500:
                            text = await resp.text()
                            raise RuntimeError(f"Non-retryable status {status}: {text[:200]}")

                        # 6. Parse JSON
                        try:
                            return await resp.json(content_type=None)
                        except Exception as e:
                            text = await resp.text()
                            logger.error(f"JSON decode failed: {e}. Body: {text[:100]}...")
                            raise

                except asyncio.CancelledError:
                    raise  # Propagate immediately
                except RuntimeError as re:
                    # Don't retry RuntimeErrors (which include our 4xx non-retryable errors)
                    raise re
                except Exception as e:
                    last_err = e
                    masked_url = _mask_url(url)
                    msg = str(e).replace("127.0.0.1", "[RESTRICTED]").replace("localhost", "[RESTRICTED]")
                    logger.warning(f"Request failed (Attempt {attempt}/{max_attempts}) for {masked_url}: {msg}")
                    # Fallthrough to retry logic

        except asyncio.CancelledError:
            raise  # Propagate immediately from semaphore wait

        # 7. Backoff
        if attempt < max_attempts:
            # Calculate backoff
            sleep_time = min(backoff + random.random() * 0.5, 8.0)

            # Check if sleep fits in budget
            now = _time_func()
            if now + sleep_time > deadline:
                logger.warning("Backoff sleep would exceed budget. Aborting.")
                break

            await _sleep_func(sleep_time)
            backoff *= 2.0

    raise last_err or RuntimeError("Max attempts reached")


class LLMClient:
    """Minimal async client for OpenAI-compatible chat completions."""

    def __init__(
        self, base_url: str, api_key: str, model: str, session: Optional[aiohttp.ClientSession] = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._session = session

    async def chat(
        self, messages: List[Dict[str, Any]], temperature: Optional[float] = 0.7, **kwargs
    ) -> tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        # Allow model override
        model_name = kwargs.get("model", self._model)
        payload: Dict[str, Any] = {}

        # Known Cloud Models (2026 Update)
        # Tier A: gpt-5.1, gpt-5, gpt-4.1, gpt-4o, o1, o3
        # Tier B: gpt-5.1-mini, gpt-4.1-mini, o4-mini, etc.
        is_cloud_model = any(m in model_name for m in [
            "gpt-5", "gpt-4.1", "gpt-4o", "o1-", "o3-", "o4-", "chatgpt"
        ])

        # Current Base URL and Key (Default to Local)
        request_base_url = self._base_url
        request_api_key = self._api_key

        if is_cloud_model:
            import os

            # Override with OpenAI Config
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                logger.info(f"☁️ Routing '{model_name}' to OpenAI Cloud API.")
                request_base_url = "https://api.openai.com/v1"
                request_api_key = openai_key
            else:
                logger.warning(f"⚠️ Cloud model '{model_name}' requested but OPENAI_API_KEY is missing. Trying Local...")

        # Determine Endpoint and Payload Structure
        # FIX: Codex (gpt-5.1-codex) and all GPT-5/O-Series are Next-Gen Agentic Models using /responses
        # User confirmed Request Format is different for these.
        # Note: Official OpenAI o1 uses chat/completions, but 'gpt-5.1-codex' (Local) uses /responses.
        # We need to distinguish "Real Cloud o1" from "Local NextGen".

        # If we are routing to Cloud, we typically use standard /chat/completions (even for o1-preview currently).
        # v1/responses is predominantly for the Local Manager (LMS/vLLM custom).

        is_next_gen_local = any(x in model_name for x in ["gpt-5", "codex"]) and not is_cloud_model
        # Fix: Ensure we don't treat 'gpt-5.1-codex' as legacy davinci completion
        is_legacy_completions = (
            any(x in model_name for x in ["davinci", "curie", "babbage", "ada"])
            and "chat" not in model_name
            and "gpt" not in model_name
        )

        if is_next_gen_local:
            # New "v1/responses" Endpoint (Agentic)
            url = f"{request_base_url}/responses"

            # Convert Messages to Input/Instructions
            instructions = ""
            input_msgs = []

            for m in messages:
                if m["role"] == "system":
                    instructions += m["content"] + "\n"
                else:
                    # Sanitize: /responses does not support 'tool_calls' in history
                    # We must flatten it into text content.
                    clean_m = {"role": m["role"], "content": m.get("content", "") or ""}

                    # Flatten Tool Calls
                    if "tool_calls" in m and m["tool_calls"]:
                        tools_str = "\n".join(
                            [
                                f"[Tool Call: {tc['function']['name']}({tc['function']['arguments']})]"
                                for tc in m["tool_calls"]
                            ]
                        )
                        clean_m["content"] += f"\n{tools_str}"

                    # Flatten Tool Outputs (if role is tool)
                    if m["role"] == "tool":
                        # CRITICAL: Codex /responses endpoint REJECTS "role": "tool".
                        # Map it to "user" (Simulator pattern).
                        clean_m["role"] = "user"
                        clean_m["content"] = f"[Tool Output]\n{clean_m['content']}"

                    input_msgs.append(clean_m)

            payload = {
                "model": model_name,
                "input": input_msgs,
            }

            # Remap content parts for v1/responses (input_text/input_image)
            # User confirmed 'text' is invalid for these endpoints.
            for item in payload["input"]:
                if isinstance(item.get("content"), list):
                    for part in item["content"]:
                        if isinstance(part, dict) and "type" in part:
                            if part["type"] == "text":
                                part["type"] = "input_text"
                            elif part["type"] == "image_url":
                                part["type"] = "input_image"
                                if "image_url" in part and isinstance(part["image_url"], dict):
                                     part["url"] = part["image_url"].get("url")

            if instructions.strip():
                payload["instructions"] = instructions.strip()

        elif is_legacy_completions:
            # Legacy "v1/completions" Endpoint
            url = f"{request_base_url}/completions"

            # Convert Messages to String Prompt
            prompt_text = ""
            for m in messages:
                role = m["role"].upper()
                content = m["content"]
                prompt_text += f"### {role}:\n{content}\n\n"
            prompt_text += "### ASSISTANT:\n"

            payload = {
                "model": model_name,
                "prompt": prompt_text,
                "max_tokens": 4096,
                "stop": ["### USER:", "### SYSTEM:"],
            }

            if temperature is not None:
                payload["temperature"] = temperature

        else:
            # Standard "v1/chat/completions" Endpoint
            url = f"{request_base_url}/chat/completions"

            # [LATEST 2025]: Reasoning models (o1/o3/o4) and latest gpt-4o support 'developer' role.
            # Local ORA Models (gpt-5/codex) often expect 'input_text' schema even in chat/completions.
            is_ora_vision = any(x in model_name for x in ["gpt-5", "codex"]) and not is_cloud_model
            should_map_developer = any(x in model_name for x in ["gpt-5", "gpt-4.1", "o1", "o3", "o4", "gpt-4o"])

            final_messages = []
            for m in messages:
                new_m = m.copy()

                # Dynamic Vision Schema Resolution
                if isinstance(new_m.get("content"), list):
                    new_content = []
                    for part in new_m["content"]:
                        if isinstance(part, dict) and "type" in part:
                            new_part = part.copy()
                            # Remap types for ORA vs Standard OpenAI
                            if is_ora_vision:
                                if new_part["type"] == "text":
                                    new_part["type"] = "input_text"
                                elif new_part["type"] == "image_url":
                                    new_part["type"] = "input_image"
                                    if "image_url" in new_part and isinstance(new_part["image_url"], dict):
                                        new_part["url"] = new_part["image_url"].get("url")
                            else:
                                # Standard OpenAI
                                if new_part["type"] == "input_text":
                                    new_part["type"] = "text"
                                elif new_part["type"] == "input_image":
                                    new_part["type"] = "image_url"
                            new_content.append(new_part)
                        else:
                            new_content.append(part)
                    new_m["content"] = new_content

                # Role Mapping
                if should_map_developer and new_m.get("role") == "system":
                    new_m["role"] = "developer"

                final_messages.append(new_m)

            payload = {
                "model": model_name,
                "messages": final_messages,
                "stream": False,
            }

            # Temperature and Token Handling
            # [LATEST 2025]: Reasoning models REQUIRE temperature=1.0 or omission.
            # Including temperature < 1.0 leads to 400 Bad Request.
            # GPT-5 and O-Series also require 'max_completion_tokens'.
            should_omit_temp = any(x in model_name for x in ["gpt-5", "gpt-4.1", "o1-", "o3-", "o4-"])

            if temperature is not None and not should_omit_temp:
                payload["temperature"] = temperature

            # [LATEST 2025]: O-Series exclusively uses 'max_completion_tokens'.
            if should_omit_temp:
                if "max_tokens" in kwargs:
                    payload["max_completion_tokens"] = kwargs.pop("max_tokens")
                elif "max_completion_tokens" in kwargs:
                    payload["max_completion_tokens"] = kwargs.pop("max_completion_tokens")
                # Top_p must also be 1.0 or omitted for reasoning models
                if "top_p" in kwargs:
                    kwargs.pop("top_p")
            else:
                if "max_completion_tokens" in kwargs:
                    payload["max_tokens"] = kwargs.pop("max_completion_tokens")
                elif "max_tokens" in kwargs:
                    payload["max_tokens"] = kwargs.pop("max_tokens")

        # Inject Tools and other kwargs (Common to both)
        # We exclude keys already handled or standard internally (model, messages, input, instructions)
        excluded_keys = {"model", "messages", "input", "instructions", "temperature", "stream"}

        # FIX: Legacy completions do NOT support 'tools'
        if is_legacy_completions:
            excluded_keys.add("tools")
            excluded_keys.add("tool_choice")

        # Parameter Mapping for v1/responses
        if is_next_gen_local:
            # Responses API STRICTLY requires 'max_output_tokens'.
            # It REJECTS 'max_completion_tokens' and 'max_tokens'.

            # 1. Extract intent from any of the possible keys
            val = (
                kwargs.pop("max_tokens", None)
                or kwargs.pop("max_completion_tokens", None)
                or kwargs.pop("max_output_tokens", None)
            )

            # 2. Set strictly 'max_output_tokens'
            if val is not None:
                kwargs["max_output_tokens"] = val

            # 3. Ensure forbidden keys are GONE
            # (popping above handles it, but safety check)
            if "max_completion_tokens" in kwargs:
                del kwargs["max_completion_tokens"]
            if "max_tokens" in kwargs:
                del kwargs["max_tokens"]

        # Flatten tool schema for v1/responses endpoint (Agentic)
        # Some endpoints (like gpt-5/o1 proxies) expect 'name' and 'type' at the same level.
        if is_next_gen_local and "tools" in kwargs:
            flattened_tools = []
            for t in kwargs["tools"]:
                if isinstance(t, dict) and t.get("type") == "function" and "function" in t:
                    # Flatten 'function' fields into the top level while keeping 'type'
                    new_tool = t.copy()
                    func_data = new_tool.pop("function")
                    if isinstance(func_data, dict):
                        new_tool.update(func_data)
                    flattened_tools.append(new_tool)
                else:
                    flattened_tools.append(t)
            kwargs["tools"] = flattened_tools

        for k, v in kwargs.items():
            if k not in excluded_keys:
                payload[k] = v

        # Use provided session or create temporary one
        if self._session:
            try:
                # Debug Logging
                logger.debug(f"Req: {url} | Model: {model_name} | NextGen: {is_next_gen_local}")

                data = await robust_json_request(
                    self._session,
                    "POST",
                    url,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {request_api_key}"},
                    json_data=payload,
                )

                # Check for wrapped error (OpenAI sometimes returns 200 OK with error body?)
                # Usually robust_json_request handles status codes.
                if "error" in data:
                    raise RuntimeError(f"API Returned Error: {data['error']}")

                # Parse Response Content
                content = None
                tool_calls = None

                # Check for Standard ChatCompletion
                if "choices" in data and len(data["choices"]) > 0:
                    msg_data = data["choices"][0]["message"]
                    content = msg_data.get("content")
                    tool_calls = msg_data.get("tool_calls")

                # Check for Agentic /responses "output"
                elif "output" in data:
                    out_val = data["output"]
                    if isinstance(out_val, list):
                        # Agentic API returns a stream of items (Reasoning, Message, etc.)
                        # We need to extract the 'message' content.
                        extracted_text = []
                        for item in out_val:
                            if not isinstance(item, dict):
                                continue

                            item_type = item.get("type")

                            # Handle 'message' items (The actual response)
                            if item_type == "message":
                                msg_content = item.get("content")
                                if isinstance(msg_content, list):
                                    for part in msg_content:
                                        if isinstance(part, dict) and part.get("type") == "output_text":
                                            if "text" in part:
                                                extracted_text.append(part["text"])
                                        elif isinstance(part, str):
                                            extracted_text.append(part)
                                elif isinstance(msg_content, str):
                                    extracted_text.append(msg_content)

                        content = "".join(extracted_text)
                    else:
                        content = str(out_val)

                    # Tool calls might be top-level or inside output?
                    # Generally /responses output is the text result.
                    tool_calls = data.get("tool_calls")

                # Fallback / Error
                else:
                    # If 'choices' missing, log the structure for debugging
                    logger.error(f"Invalid API Response Keys: {list(data.keys())} | Raw: {str(data)[:200]}...")
                    raise KeyError("Response parsing failed: No 'choices' or 'output' found.")

                usage = data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
                return content, tool_calls, usage

            except Exception as e:
                # 404 Fallback Logic for v1/responses
                # If we hit 404 on chat/completions but message says "use v1/responses", retry!
                err_str = str(e).lower()
                if "404" in err_str and "v1/responses" in err_str and not is_next_gen_local:
                    logger.warning(
                        f"Caught 404 indicating endpoint mismatch for {model_name}. Retrying with /responses..."
                    )
                    # Recursive call? Or just manually construct
                    # Let's recurse but FORCE next_gen treatment?
                    # Actually, better to just modify logic. But simplest is to act like is_next_gen=True here.

                    # Manually switch URL and Payload specific to this fallback
                    new_url = f"{request_base_url}/responses"

                    # Convert Payload
                    instructions = ""
                    input_msgs = []
                    for m in messages:
                        if m["role"] == "system":
                            instructions += m["content"] + "\n"
                        else:
                            # Sanitize: /responses does not support 'tool_calls' in history
                            # We must flatten it into text content.
                            clean_m = {"role": m["role"], "content": m.get("content", "") or ""}

                            # Flatten Tool Calls
                            if "tool_calls" in m and m["tool_calls"]:
                                tools_str = "\n".join(
                                    [
                                        f"[Tool Call: {tc['function']['name']}({tc['function']['arguments']})]"
                                        for tc in m["tool_calls"]
                                    ]
                                )
                                clean_m["content"] += f"\n{tools_str}"

                            # Flatten Tool Outputs (if role is tool)
                            if m["role"] == "tool":
                                # Codex /responses endpoint REJECTS "role": "tool".
                                clean_m["role"] = "user"
                                clean_m["content"] = f"[Tool Output]\n{clean_m['content']}"

                            input_msgs.append(clean_m)

                    new_payload = {"model": model_name, "input": input_msgs}
                    if instructions.strip():
                        new_payload["instructions"] = instructions.strip()
                    if "tools" in kwargs:
                        new_payload["tools"] = kwargs["tools"]

                    # Retry Request
                    data = await robust_json_request(
                        self._session,
                        "POST",
                        new_url,
                        headers={"Content-Type": "application/json", "Authorization": f"Bearer {request_api_key}"},
                        json_data=new_payload,
                    )

                    if data.get("object") == "response":
                        logger.debug(f"DEBUG v1/responses KEYS: {list(data.keys())}")
                        logger.debug(f"DEBUG v1/responses USAGE: {data.get('usage')}")
                        content = data.get("output")
                        if isinstance(content, list):
                            content = "".join([str(c) for c in content])
                        return content, None, data.get("usage", {})

                    msg_data = data["choices"][0]["message"]
                    return msg_data.get("content"), msg_data.get("tool_calls"), data.get("usage", {})

                raise RuntimeError(f"LLM request failed ({model_name}): {str(e).replace('127.0.0.1', '[RESTRICTED]')}") from e
        else:
            async with aiohttp.ClientSession() as session:
                try:
                    data = await robust_json_request(
                        session,
                        "POST",
                        url,
                        headers={"Content-Type": "application/json", "Authorization": f"Bearer {request_api_key}"},
                        json_data=payload,
                    )

                    if data.get("error"):
                        raise RuntimeError(f"API Returned Error: {data['error']}")

                    if data.get("object") == "response":
                        # New v1/responses Schema
                        logger.debug(f"DEBUG v1/responses Keys: {list(data.keys())}")
                        logger.debug(f"DEBUG v1/responses Usage: {data.get('usage')}")
                        content = data.get("output")
                        if isinstance(content, list):
                            # v1/responses returns a list of objects (Reasoning, Message, etc.)
                            # We only want the TEXT content from the Message object
                            try:
                                logger.debug(f"DEBUG v1/responses OUTPUT LIST: {str(content)[:500]}")
                            except Exception:
                                pass

                            final_text = ""
                            tool_calls = None  # Initialize before loop
                            for item in content:
                                if isinstance(item, dict):
                                    # Debug unknown types - FORCE LOGGING
                                    logger.debug(f"DEBUG v1/responses ITEM: {str(item)[:10000]}")

                                    # Ultra Greedy: Check ANY dict for content/text
                                    # Try "content"
                                    if "content" in item:
                                        msg_content = item["content"]
                                        if isinstance(msg_content, list):
                                            for part in msg_content:
                                                if isinstance(part, str):
                                                    final_text += part
                                                elif isinstance(part, dict):
                                                    # Greedy: grab text/content from part
                                                    # Logged type was 'output_text', so we check for 'text' field which it had.
                                                    final_text += part.get("text", "") or part.get("content", "")
                                        elif isinstance(msg_content, str):
                                            final_text += msg_content

                                    # Try "text" field directly
                                    elif "text" in item:
                                        final_text += item["text"]

                                    # Option B: Item IS a content part
                                    elif item.get("type") == "text":
                                        final_text += item.get("text", "")

                                    # Option C: Tool Call (Agentic API)
                                    # Typical format: { "type": "tool_call", "tool_call": { "id": "...", "function": { "name": "...", "arguments": "..." } } }
                                    # Or: { "type": "function_call", ... } depending on version.
                                    # Let's handle the "type": "tool_call" which structure matches standard tool_calls.
                                    elif item.get("type") == "tool_call":
                                        if tool_calls is None:
                                            tool_calls = []
                                        tc = item.get("tool_call", item)
                                        tool_calls.append(tc)

                                    # Option D: Function Call (Codex Agentic)
                                    # Format: {'id': '...', 'type': 'function_call', 'name': '...', 'arguments': '...'}
                                    elif item.get("type") == "function_call":
                                        if tool_calls is None:
                                            tool_calls = []
                                        # Transform to Standard OpenAI tool_call format
                                        std_tc = {
                                            "id": item.get("call_id", item.get("id", "call_unknown")),
                                            "type": "function",
                                            "function": {"name": item.get("name"), "arguments": item.get("arguments")},
                                        }
                                        tool_calls.append(std_tc)

                                elif isinstance(item, str):
                                    final_text += item

                            # DEBUG: Increase log limit for visibility
                            logger.debug(f"Combined Text Length: {len(final_text)}")
                            content = final_text

                        usage = data.get("usage", {})
                        return content, tool_calls, usage

                    try:
                        msg_data = data["choices"][0]["message"]
                        content = msg_data.get("content")
                        tool_calls = msg_data.get("tool_calls")
                        usage = data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
                        return content, tool_calls, usage
                    except (KeyError, IndexError, TypeError) as exc:
                        logger.error(f"Invalid API Response Keys: {list(data.keys())} | Raw: {str(data)[:200]}...")
                        raise RuntimeError(f"LLM応答の形式が不正です ({model_name}): {exc}") from exc
                except Exception as e:
                    raise e

    async def unload_model(self) -> None:
        """Attempt to unload the model from VRAM (LM Studio / Ollama / vLLM)."""
        logger.info(f"🛑 Unloading model/service for: {self._model}")

        # 1. Try vLLM (WSL2) Unload
        try:
            # Kill python3 process running vllm
            cmd = "wsl -d Ubuntu-22.04 pkill -f vllm"
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            if proc.returncode == 0:
                logger.info("✅ vLLM Stopped.")
        except Exception as e:
            logger.debug(f"vLLM stop skipped or failed: {e}")

        # 2. Try LM Studio specific endpoint
        urls = [
            f"{self._base_url}/internal/model/unload",  # LM Studio
            f"{self._base_url}/chat/completions",      # Ollama fallback (keep_alive=0)
        ]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        # Ollama payload
        ollama_payload = {"model": self._model, "keep_alive": 0}

        # Use throw-away session or existing
        ctx = self._session if self._session else aiohttp.ClientSession()

        try:
            # We need to handle session context manager manually depending on if we own it
            session = ctx
            if not self._session:
                await session.__aenter__()

            try:
                # A. Try LM Studio Unload
                try:
                    async with session.post(urls[0], headers=headers, json={}, timeout=2) as resp:
                        if resp.status == 200:
                            logger.info("✅ LM Studio Model Unloaded.")
                except Exception:
                    pass

                # B. Try Ollama Unload
                try:
                    async with session.post(urls[1], headers=headers, json=ollama_payload, timeout=2) as resp:
                        if resp.status == 200:
                            logger.info("✅ Ollama Model Unloaded (keep_alive=0).")
                except Exception:
                    pass

            finally:
                if not self._session:
                    await session.__aexit__(None, None, None)

            # C. Try 'lms' CLI (LM Studio 0.3+)
            try:
                proc = await asyncio.create_subprocess_exec(
                    "lms", "unload", "--all", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
            except Exception:
                pass

            # D. NUCLEAR OPTION: Taskkill LM Studio
            try:
                proc = await asyncio.create_subprocess_exec(
                    "taskkill", "/F", "/IM", "LM Studio.exe",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Failed to fully unload model: {e}")
