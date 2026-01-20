import os
import asyncio
from typing import AsyncGenerator
from openai import AsyncOpenAI
from ora_core.database.models import AuthorRole

class OmniEngine:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            # Fallback or Error handling
            print("Warning: OPENAI_API_KEY not found in env.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini" # Fast default

    async def generate_stream(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """
        Generates a streaming response from OpenAI.
        """
        if not self.api_key:
            yield "Critical Error: API Key missing. Please check .env file."
            return

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.7
            )
            
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        except Exception as e:
            yield f"\n[System Error: {str(e)}]"

# Singleton instance
omni_engine = OmniEngine()
