import os
import asyncio
from typing import AsyncGenerator
from openai import AsyncOpenAI
from ora_core.database.models import AuthorRole
from ora_core.mcp.registry import tool_registry

class OmniEngine:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL") # if None, uses default OpenAI
        self.model = os.getenv("LLM_MODEL") or "gpt-4o-mini"
        
        if not self.api_key:
            print("Warning: LLM API Key not found in env.")
        
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    async def generate_response(self, messages: list[dict], client_type: str = "web"):
        """Non-streaming generation."""
        if not self.api_key:
            raise ValueError("Critical Error: API Key missing.")
        
        tools = self._get_tools_param(client_type)
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=False,
            temperature=0.7
        )

    def _get_tools_param(self, client_type: str) -> list[dict] | None:
        """Fetch tools from registry and format for OpenAI."""
        tools = tool_registry.list_tools_for_client(client_type)
        if not tools:
            return None
        
        openai_tools = []
        for t in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters # Already a dict with type/properties/required
                }
            })
        return openai_tools

    async def generate_stream(self, messages: list[dict], client_type: str = "web"):
        """Streaming generation (Yields chunks)."""
        if not self.api_key:
            yield "Critical Error: API Key missing."
            return

        tools = self._get_tools_param(client_type)
        
        try:
            response_stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                stream=True,
                temperature=0.7
            )
            async for chunk in response_stream:
                yield chunk
        except Exception as e:
            yield f"\n[System Error: {str(e)}]"

    async def generate(self, messages: list[dict], client_type: str = "web", stream: bool = True):
        # Deprecated: use specific methods. Kept for back-compat if needed, 
        # but caution: can't be both async def and async generator easily.
        if stream:
            return self.generate_stream(messages, client_type)
        else:
            return await self.generate_response(messages, client_type)

# Singleton instance
omni_engine = OmniEngine()
