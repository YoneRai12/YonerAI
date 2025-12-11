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

    async def chat(self, messages: List[Dict[str, Any]], temperature: float = 0.7) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        
        # Use provided session or create temporary one
        if self._session:
            try:
                data = await robust_json_request(self._session, "POST", url, headers=headers, json_data=payload)
                return str(data["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError("LLM応答の形式が不正です。") from exc
        else:
            async with aiohttp.ClientSession() as session:
                try:
                    data = await robust_json_request(session, "POST", url, headers=headers, json_data=payload)
                    return str(data["choices"][0]["message"]["content"])
                except (KeyError, IndexError, TypeError) as exc:
                    raise RuntimeError("LLM応答の形式が不正です。") from exc
