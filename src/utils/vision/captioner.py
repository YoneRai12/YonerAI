
import logging

from src.utils.unified_client import UnifiedClient

logger = logging.getLogger(__name__)

class ImageCaptioner:
    """
    Handles Multi-Modal understanding (Image/Video) using the VLM (Qwen2.5-VL).
    """
    def __init__(self, llm_client: UnifiedClient):
        self.llm = llm_client
        # Read from Config
        self.provider = self.llm.config.vision_provider
        
        # Models
        self.vision_model_local = "Qwen/Qwen2.5-VL-32B-Instruct-AWQ"
        self.vision_model_openai = "gpt-5-mini" # Stable Lane (2.5M tokens/day)

    async def describe_media(self, url: str, media_type: str = "image") -> str:
        """
        Generates a description for the given media URL.
        media_type: "image" or "video"
        """
        prompt = "この画像を詳細に描写してください。何が映っていますか？"
        if media_type == "video":
            prompt = "この動画の内容を詳細に要約してください。何が起きていますか？"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": url}}
                ]
            }
        ]

        # Select Model based on Provider
        if self.provider == "openai":
            model = self.vision_model_openai
        else:
            model = self.vision_model_local

        try:
            logger.info(f"Vision Analysis ({self.provider}): {model} for {media_type}")
            
            content, _, _ = await self.llm.chat(
                provider=self.provider,
                messages=messages,
                model=model,
                temperature=0.7,
                max_tokens=500
            )
            return content if content else "(認識失敗: 応答なし)"
        except Exception as e:
            logger.error(f"Vision Analysis Failed ({self.provider}): {e}")
            return f"(認識エラー: {e})"
