
import logging
from typing import Any, Dict, List, Optional

from src.config import Config

from .google_client import GoogleClient
from .llm_client import LLMClient

logger = logging.getLogger("ORA.UnifiedClient")

class UnifiedClient:
    """
    Manages connections to multiple LLM providers (Lanes).
    Lane A: Gemini Trial (Burn) -> GoogleClient
    Lane B: OpenAI Shared (Stable) -> LLMClient (to OpenAI API)
    Lane C: Local (Private) -> LLMClient (to Local vLLM)
    """
    def __init__(self, config: Config, local_llm: LLMClient, google_client: Optional[GoogleClient]):
        self.config = config
        self.local_llm = local_llm
        self.google_client = google_client
        
        # Initialize OpenAI Client if Key exists
        self.openai_client: Optional[LLMClient] = None
        if self.config.openai_api_key:
            self.openai_client = LLMClient(
                base_url="https://api.openai.com/v1",
                api_key=self.config.openai_api_key,
                model="gpt-5-mini" # Best Performance in Stable Lane (2.5M limit)
            )
            logger.info("✅ UnifiedClient: OpenAI Adapter initialized.")
        else:
            logger.info("ℹ️ UnifiedClient: OpenAI API Key missing. OpenAI Lane disabled.")

    async def chat(self, provider: str, messages: List[Dict[str, Any]], **kwargs) -> tuple[Optional[str], Optional[List[Dict[str, Any]]], Dict[str, Any]]:
        """
        Unified chat interface.
        Returns: (content, tool_calls, usage_dict)
        """
        try:
            if provider == "local":
                # Returns (content, tool_calls, usage)
                return await self.local_llm.chat(messages, **kwargs)
            
            elif provider == "gemini_trial":
                if not self.google_client:
                    raise RuntimeError("Gemini Client not initialized.")
                model_name = kwargs.get("model_name", "gemini-1.5-pro")
                # Returns (content, tool_calls, usage)
                return await self.google_client.chat(messages, model_name=model_name)

            elif provider == "openai":
                if not self.openai_client:
                    raise RuntimeError("OpenAI Client not initialized.")
                # Returns (content, tool_calls, usage)
                return await self.openai_client.chat(messages, **kwargs)
            
            else:
                 logger.error(f"Unknown provider: {provider}")
                 return None, None, {}

        except Exception as e:
            logger.error(f"UnifiedClient Error ({provider}): {e}")
            raise e
