import os
import asyncio
import logging
from typing import Optional, List, Union
# We assume openai is installed
try:
    from openai import AsyncOpenAI
    import openai
except ImportError:
    AsyncOpenAI = None
    openai = None

logger = logging.getLogger(__name__)

class MediaAPIClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_TOKEN")
        self.client: Optional[AsyncOpenAI] = None
        if self.api_key and AsyncOpenAI:
            self.client = AsyncOpenAI(api_key=self.api_key)
        else:
            logger.warning("OPENAI_TOKEN not set or openai package missing. Media API disabled.")

    async def generate_image(self, prompt: str, size: str = "1024x1024", model: str = "dall-e-3") -> str:
        """Generates an image using DALL-E 3. Returns URL."""
        if not self.client:
            return "Error: OpenAI API not configured."

        try:
            response = await self.client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality="standard",
                n=1,
            )
            return response.data[0].url
        except Exception as e:
            return f"Image Generation Error: {e}"

    async def generate_video(self, prompt: str, model: str = "sora-2", seconds: int = 4) -> str:
        """Generates a video using Sora (Beta/Private API)."""
        if not self.client:
            return "Error: OpenAI API not configured."

        # NOTE: This endpoint is hypothetical/beta. MeteoBOT uses client.videos.*
        # If the user doesn't have access, this will fail.
        if not hasattr(self.client, "videos"):
             return "Error: Sora API (client.videos) not available in this OpenAI SDK version or access level."

        try:
            # MeteoBOT pattern: create_and_poll or create -> poll
            # We will try a simplified flow if create_and_poll exists
            if hasattr(self.client.videos, "create_and_poll"):
                video = await self.client.videos.create_and_poll(
                    model=model,
                    prompt=prompt,
                    # seconds=seconds # Hypothetical param
                )
                # Assuming video object has .id or similar and we need to retrieve content
                # For now, just returning the result object string/ID as proof of concept if we can't download
                return f"Video generated. ID: {getattr(video, 'id', 'Unknown')}. (Download not fully implemented in ORA yet)"
            
            # Fallback to create
            video = await self.client.videos.create(model=model, prompt=prompt)
            return f"Video generation started. ID: {getattr(video, 'id', 'Unknown')}. Please check status later (Async polling not fully ported)."

        except Exception as e:
            return f"Video Generation Error: {e}"

# Global instance
media_api = MediaAPIClient()
