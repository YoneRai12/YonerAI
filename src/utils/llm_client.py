"""OpenAI-compatible client for LM Studio."""

from __future__ import annotations

import time
import asyncio
import json
import logging
import random
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

class TransientHTTPError(RuntimeError):
    pass

# Global semaphore for rate limiting
_SEM = asyncio.Semaphore(10)

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
    _sleep_func = asyncio.sleep,
    _time_func = time.monotonic
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
                timeout = aiohttp.ClientTimeout(
                    total=req_timeout_val,
                    connect=5.0,
                    sock_connect=5.0,
                    sock_read=300.0
                )
                
                try:
                    async with session.request(
                        method, 
                        url, 
                        headers=headers, 
                        params=params,
                        json=json_data, 
                        timeout=timeout
                    ) as resp:
                        status = resp.status
                        
                        # 5. Handle Retry-After
                        if status == 429 or 500 <= status < 600:
                            retry_after = float(resp.headers.get("Retry-After", 0))
                            if retry_after > 0:
                                # Check if we can afford to wait
                                current_remaining = deadline - _time_func()
                                if retry_after > current_remaining:
                                    logger.warning(f"Retry-After ({retry_after}s) > Remaining ({current_remaining:.2f}s). Aborting.")
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
                    raise # Propagate immediately
                except RuntimeError as re:
                    # Don't retry RuntimeErrors (which include our 4xx non-retryable errors)
                    raise re
                except Exception as e:
                    last_err = e
                    logger.warning(f"Request failed (Attempt {attempt}/{max_attempts}): {e}")
                    # Fallthrough to retry logic
                    
        except asyncio.CancelledError:
            raise # Propagate immediately from semaphore wait
            
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

    def __init__(self, base_url: str, api_key: str, model: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._session = session

    async def chat(self, messages: List[Dict[str, Any]], temperature: Optional[float] = 0.7, **kwargs) -> tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        # Allow model override
        model_name = kwargs.get("model", self._model)
        # Determine Endpoint and Payload Structure
        # We treat 'o1' and 'o3' as next_gen (v1/responses) ONLY if specifically configured?
        # User feedback indicates gpt-5.1 etc should use Standard Endpoint but NO temperature.
        # So we remove "gpt-5" from this check.
        is_next_gen = any(x in model_name for x in ["o1-", "o3-"]) and "gpt-5" not in model_name

        if is_next_gen:
            # New "v1/responses" Endpoint (Agentic)
            url = f"{self._base_url}/responses"
            
            # Convert Messages to Input/Instructions
            # "instructions" = System Prompt
            # "input" = User/Assistant Conversation
            instructions = ""
            input_msgs = []
            
            for m in messages:
                if m["role"] == "system":
                    instructions += m["content"] + "\n"
                else:
                    input_msgs.append(m)
            
            payload: Dict[str, Any] = {
                "model": model_name,
                "input": input_msgs,
            }
            if instructions.strip():
                payload["instructions"] = instructions.strip()

        else:
            # Standard "v1/chat/completions" Endpoint
            url = f"{self._base_url}/chat/completions"
            
            # Message Role Mapping (system -> developer for o1/gpt-5)
            should_map_developer = any(x in model_name for x in ["gpt-5", "o1", "o3"])
            final_messages = []
            if should_map_developer:
                for m in messages:
                    new_m = m.copy()
                    if new_m.get("role") == "system":
                        new_m["role"] = "developer"
                    final_messages.append(new_m)
            else:
                 final_messages = messages

            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": final_messages,
                "stream": False,
            }
            # Temperature Handling: STRICTLY REMOVE for Next-Gen Models (User Request: "Don't send temperature")
            # This includes gpt-5 family, o1/o3 family, and codex family as per user report.
            # Models: gpt-5.1, gpt-5.1-codex, gpt-5, gpt-5-codex, gpt-5-chat-latest, gpt-4.1, o1, o3, codex-mini-latest
            # Mini variants included.
            
            # Simple keyword matching:
            should_omit_temp = any(x in model_name for x in ["gpt-5", "gpt-4.1", "o1", "o3", "codex", "o4"])
            
            if temperature is not None and not should_omit_temp:
                payload["temperature"] = temperature
            
            if should_omit_temp:
                 if "max_tokens" in kwargs:
                     try:
                         # Many of these models prefer 'max_completion_tokens' or 'max_output_tokens' 
                         # But let's stick to standard behavior unless we know the endpoint is different.
                         # Standard v1/chat/completions for o1 uses 'max_completion_tokens'
                         kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                     except: pass

        # Inject Tools and other kwargs (Common to both)
        # We exclude keys already handled or standard internally (model, messages, input, instructions)
        excluded_keys = {"model", "messages", "input", "instructions", "temperature", "stream"}
        
        # Parameter Mapping for v1/responses
        if is_next_gen:
            # Responses API uses 'max_output_tokens' instead of 'max_tokens' or 'max_completion_tokens'
            if "max_tokens" in kwargs:
                kwargs["max_output_tokens"] = kwargs.pop("max_tokens")
            if "max_completion_tokens" in kwargs:
                kwargs["max_output_tokens"] = kwargs.pop("max_completion_tokens")

        # Flatten tool schema for v1/responses endpoint (Agentic)
        # Some endpoints (like gpt-5/o1 proxies) expect 'name' and 'type' at the same level.
        if is_next_gen and "tools" in kwargs:
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
                logger.debug(f"Req: {url} | Model: {model_name} | NextGen: {is_next_gen}")
                
                data = await robust_json_request(self._session, "POST", url, headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}, json_data=payload)
                
                # Check for wrapped error (OpenAI sometimes returns 200 OK with error body?)
                # Usually robust_json_request handles status codes.
                if "error" in data:
                     raise RuntimeError(f"API Returned Error: {data['error']}")
                
                try:
                    msg_data = data["choices"][0]["message"]
                    content = msg_data.get("content")
                except KeyError:
                     # If 'choices' missing, log the structure for debugging
                     logger.error(f"Invalid API Response Keys: {list(data.keys())} | Raw: {str(data)[:200]}...")
                     raise
                tool_calls = msg_data.get("tool_calls")
                usage = data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
                return content, tool_calls, usage

            except Exception as e:
                # 404 Fallback Logic for v1/responses
                # If we hit 404 on chat/completions but message says "use v1/responses", retry!
                err_str = str(e).lower()
                if "404" in err_str and "v1/responses" in err_str and not is_next_gen:
                    logger.warning(f"Caught 404 indicating endpoint mismatch for {model_name}. Retrying with /responses...")
                    # Recursive call? Or just manually construct
                    # Let's recurse but FORCE next_gen treatment? 
                    # Actually, better to just modify logic. But simplest is to act like is_next_gen=True here.
                    
                    # Manually switch URL and Payload specific to this fallback
                    new_url = f"{self._base_url}/responses"
                    
                    # Convert Payload
                    instructions = ""
                    input_msgs = []
                    for m in messages:
                        if m["role"] == "system":
                            instructions += m["content"] + "\n"
                        else:
                            input_msgs.append(m)
                    
                    new_payload = {
                        "model": model_name,
                        "input": input_msgs
                    }
                    if instructions.strip():
                        new_payload["instructions"] = instructions.strip()
                    if "tools" in kwargs:
                        new_payload["tools"] = kwargs["tools"]
                        
                    # Retry Request
                    data = await robust_json_request(self._session, "POST", new_url, headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}, json_data=new_payload)
                    
                    if data.get("object") == "response":
                         logger.info(f"DEBUG v1/responses KEYS: {list(data.keys())}")
                         logger.info(f"DEBUG v1/responses USAGE: {data.get('usage')}")
                         content = data.get("output")
                         if isinstance(content, list):
                             content = "".join([str(c) for c in content])
                         return content, None, data.get("usage", {})
                         
                    msg_data = data["choices"][0]["message"]
                    return msg_data.get("content"), msg_data.get("tool_calls"), data.get("usage", {})

                raise RuntimeError(f"LLM request failed ({model_name}): {e}") from e
        else:
            async with aiohttp.ClientSession() as session:
                try:
                    data = await robust_json_request(session, "POST", url, headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"}, json_data=payload)
                    
                    if data.get("error"):
                        raise RuntimeError(f"API Returned Error: {data['error']}")
                    
                    if data.get("object") == "response":
                        # New v1/responses Schema
                        logger.info(f"DEBUG v1/responses Keys: {list(data.keys())}")
                        logger.info(f"DEBUG v1/responses Usage: {data.get('usage')}")
                        content = data.get("output")
                        if isinstance(content, list):
                             # v1/responses returns a list of objects (Reasoning, Message, etc.)
                             # We only want the TEXT content from the Message object
                             try:
                                 logger.debug(f"DEBUG v1/responses OUTPUT LIST: {str(content)[:500]}")
                             except: pass

                             final_text = ""
                             for item in content:
                                 if isinstance(item, dict):
                                     # Debug unknown types - FORCE LOGGING
                                     logger.warning(f"DEBUG v1/responses ITEM: {str(item)[:10000]}")
                                     
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
                                          
                                 elif isinstance(item, str):
                                     final_text += item
                             
                             # DEBUG: Increase log limit for visibility
                             logger.debug(f"Combined Text Length: {len(final_text)}")
                             content = final_text
                        
                        tool_calls = None 
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
        """Attempt to unload the model from VRAM (LM Studio / Ollama)."""
        # Try LM Studio specific endpoint first
        urls = [
            f"{self._base_url}/internal/model/unload", # LM Studio
            f"{self._base_url}/chat/completions"       # Ollama fallback (keep_alive=0)
        ]
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        
        # Ollama payload
        ollama_payload = {
            "model": self._model,
            "keep_alive": 0
        }

        # Use throw-away session or existing
        ctx = self._session if self._session else aiohttp.ClientSession()
        
        try:
            # We need to handle session context manager manually depending on if we own it
            session = ctx
            if not self._session:
                 await session.__aenter__()

            try:
                # 1. Try LM Studio Unload
                try:
                    async with session.post(urls[0], headers=headers, json={}, timeout=2) as resp:
                        if resp.status == 200:
                            logger.info("✅ LM Studio Model Unloaded.")
                            return
                except:
                    pass

                # 2. Try Ollama Unload
                try:
                    async with session.post(urls[1], headers=headers, json=ollama_payload, timeout=2) as resp:
                        if resp.status == 200:
                            logger.info("✅ Ollama Model Unloaded (keep_alive=0).")
                            return
                except:
                    pass
                
                
                logger.warning("Could not unload model (API did not respond to known offload commands).")

            finally:
                if not self._session:
                    await session.__aexit__(None, None, None)

            # 3. Try 'lms' CLI (Definitive Fix for LM Studio 0.3+)
            try:
                # Run 'lms unload --all' asynchronously
                proc = await asyncio.create_subprocess_exec(
                    "lms", "unload", "--all",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                     logger.info("✅ 'lms unload --all' executed successfully.")
                else:
                     logger.warning(f"'lms' CLI failed with code {proc.returncode}: {stderr.decode()}")
            except Exception as cli_e:
                 logger.warning(f"Failed to run 'lms' CLI: {cli_e}")

            # 4. NUCLEAR OPTION: Taskkill
            # User request: "VRAMからkillしてよ" (Kill from VRAM)
            try:
                proc = await asyncio.create_subprocess_exec(
                    "taskkill", "/F", "/IM", "LM Studio.exe",
                    stdout=asyncio.subprocess.PIPE, 
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                logger.info("☢️ Nuclear Option Executed: Killed 'LM Studio.exe'")
            except Exception as tk_e:
                logger.warning(f"Failed to taskkill: {tk_e}")
                
        except Exception as e:
            logger.warning(f"Failed to unload model: {e}")

    async def start_service(self) -> None:
        """Starts the LLM service (vLLM on WSL2)."""
        try:
            logger.info("🚀 Starting vLLM Service (WSL2)...")
            
            # Use 'wsl' command to launch vLLM in background (nohup or detached)
            # We use 'start' to detach from Python process
            cmd = (
                "wsl -d Ubuntu-22.04 nohup python3 -m vllm.entrypoints.openai.api_server "
                "--model Qwen/Qwen2.5-VL-32B-Instruct-AWQ --quantization awq --dtype half --gpu-memory-utilization 0.90 "
                "--max-model-len 2048 --enforce-eager --disable-custom-all-reduce --tensor-parallel-size 1 --port 8000 "
                "--trust-remote-code > vllm.log 2>&1 &"
            )
            
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Wait for it to spin up? (It takes ~20s)
            # We won't block here, the first request will just fail/retry.
            # But we should give it a head start.
            logger.info("⏳ Waiting 10s for vLLM to initialize...")
            await asyncio.sleep(10) 
            logger.info("✅ vLLM Launch signal sent.")
            
        except Exception as e:
            logger.error(f"Failed to start LLM service: {e}")

    async def unload_model(self):
        """Stops the LLM service (vLLM) to free VRAM."""
        try:
            logger.info("🛑 Stopping vLLM Service (pkill)...")
            # Kill python3 process running vllm
            cmd = "wsl -d Ubuntu-22.04 pkill -f vllm"
            
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            logger.info("✅ vLLM Stopped.")
            
        except Exception as e:
            logger.warning(f"Failed to stop vLLM: {e}")


