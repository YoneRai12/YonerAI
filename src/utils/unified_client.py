import logging
import aiohttp
from typing import Any, Dict, List, Optional

from src.config import Config

from .google_client import GoogleClient
from .llm_client import LLMClient
from .connection_manager import ConnectionManager

logger = logging.getLogger("ORA.UnifiedClient")


class UnifiedClient:
    """
    Manages connections to multiple LLM providers (Lanes).
    Lane 0: ORA Core API (The Brain) -> Primary if healthy
    Lane A: Gemini Trial (Burn) -> GoogleClient
    Lane B: OpenAI Shared (Stable) -> LLMClient (to OpenAI API)
    Lane C: Local (Private) -> LLMClient (to Local vLLM)
    """

    def __init__(self, config: Config, local_llm: LLMClient, google_client: Optional[GoogleClient], connection_manager: Optional[ConnectionManager] = None):
        self.config = config
        self.local_llm = local_llm
        self.google_client = google_client
        self.connection_manager = connection_manager

        # Initialize OpenAI Client if Key exists
        self.openai_client: Optional[LLMClient] = None
        if self.config.openai_api_key:
            self.openai_client = LLMClient(
                base_url="https://api.openai.com/v1",
                api_key=self.config.openai_api_key,
                model=self.config.openai_default_model,  # Best Performance in Stable Lane
            )
            logger.info("✅ UnifiedClient: OpenAI Adapter initialized.")
        else:
            logger.info("ℹ️ UnifiedClient: OpenAI API Key missing. OpenAI Lane disabled.")

    def _apply_policy_guard(self, model_name: str, kwargs: Dict[str, Any]) -> None:
        """Applies model-specific policies (e.g. stripping temperature)."""
        if not hasattr(self.config, "model_policies") or not self.config.model_policies:
            return

        no_temp_list = self.config.model_policies.get("no_temperature_models", [])
        if model_name in no_temp_list:
            if "temperature" in kwargs:
                logger.warning(f"🛡️ Security: Stripped 'temperature' param for reasoning model '{model_name}'")
                kwargs.pop("temperature")

    async def chat(
        self, provider: str, messages: List[Dict[str, Any]], **kwargs
    ) -> tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Unified chat interface with Intelligent Priority & Fallback.
        """
        attempts = []
        
        # 0. Check Core API Health (If available)
        use_core_api = False
        if self.connection_manager:
            if await self.connection_manager.check_health():
                use_core_api = True
            
        # Determine Attempt Order
        if use_core_api:
             attempts.append("ora_core")
        
        # Fallback Order
        priority = self.config.llm_priority
        if priority == "cloud":
            if self.openai_client: attempts.append("openai")
            if self.google_client: attempts.append("gemini_trial")
            attempts.append("local")
        else:
            attempts.append("local")
            if self.openai_client: attempts.append("openai")
            if self.google_client: attempts.append("gemini_trial")
        
        # Optional: If a provider is explicitly requested, honor it (override start)
        if provider and provider in ["local", "openai", "gemini_trial"]:
             attempts.insert(0, provider)

        last_err = None
        for p in attempts:
            try:
                if p == "ora_core":
                    # Proxy to Core API
                    # Using local_llm client structure but pointing to Core
                    if not self.connection_manager or not self.connection_manager.api_base_url: continue
                    
                    # Core API expects messages and can handle tools
                    # We use a temporary LLMClient pointing to Core for convenience
                    session = await self.connection_manager.get_session()
                    core_client = LLMClient(
                        base_url=f"{self.connection_manager.api_base_url}", 
                        api_key="ora-internal-key",
                        model=self.config.llm_model,
                        session=session
                    )
                    # Note: /v1/chat/completions is standard, ensure Core API exposes it or /v1 routes
                    # Since Core uses OmniEngine, we assume it exposes standardized endpoints.
                    # The LLMClient appends /chat/completions automatically to base_url + /v1 usually.
                    # Let's verify base path. Config has ora_api_base_url e.g. http://localhost:8000
                    # We likely need http://localhost:8000/v1
                    
                    # Temp Override base_url for the call
                    core_client.base_url = f"{self.connection_manager.api_base_url}/v1"
                    
                    return await core_client.chat(messages, **kwargs)

                elif p == "local":
                    return await self.local_llm.chat(messages, **kwargs)

                elif p == "gemini_trial":
                    if not self.google_client: continue
                    model_name = kwargs.get("model_name", "gemini-1.5-pro")
                    return await self.google_client.chat(messages, model_name=model_name)

                elif p == "openai":
                    if not self.openai_client: continue
                    # Safety: If model name looks like a local model, swap for a cloud one
                    model_name = kwargs.get("model", "")
                    if "qwen" in model_name.lower() or "mistral" in model_name.lower() or not model_name:
                        kwargs["model"] = self.config.openai_default_model
                        model_name = self.config.openai_default_model # Update local var
                        if "max_tokens" in kwargs and kwargs["max_tokens"] > 16384:
                            kwargs["max_tokens"] = 16384
                    
                    # Apply Policy Guard
                    self._apply_policy_guard(model_name, kwargs)

                    return await self.openai_client.chat(messages, **kwargs)

            except Exception as e:
                logger.warning(f"UnifiedClient: Lane '{p}' failed: {e}. Trying next lane...")
                last_err = e
                continue

        logger.error(f"UnifiedClient: All lanes failed. Last error: {last_err}")
        return None, None, {}
