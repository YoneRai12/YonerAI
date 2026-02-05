import logging

from src.utils.unified_client import UnifiedClient

logger = logging.getLogger(__name__)


class ImageCaptioner:
    """
    Handles Multi-Modal understanding (Image/Video) using the VLM (gpt-5-mini).
    """

    def __init__(self, llm_client: UnifiedClient):
        self.llm = llm_client
        # Read from Config
        self.provider = self.llm.config.vision_provider

        # Models (2026 Tiers)
        self.vision_model_local = "gpt-5.1-codex-mini"
        self.vision_model_openai = "gpt-5-mini"  # Unified on GPT-5-mini per user request

    async def describe_media(self, url: str, media_type: str = "image") -> str:
        """
        Generates a description for the given media URL.
        media_type: "image" or "video"
        """
        prompt = "あなたは高度な視覚認識エンジンです。現在、目の前の画像が完全に見えています。この画像を日本語で詳細に描写してください。何が映っていますか？"
        if media_type == "video":
            prompt = "この動画の内容を詳細に要約してください。何が起きていますか？"

        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}],
            }
        ]

        # Standardize on OpenAI (S2/S4/User Request)
        model = self.vision_model_openai
        target_provider = "openai"

        try:
            logger.info(f"Vision Analysis (OpenAI 2026): {model} for {media_type}")

            # Note: We use temperature=1.0 for reasoning compatibility
            content, _, _ = await self.llm.chat(
                provider=target_provider, messages=messages, model=model, temperature=1.0, max_tokens=1000
            )

            return content if content else "(認識失敗: OpenAI 側で解析できませんでした)"
        except Exception as e:
            err_msg = str(e)
            logger.error(f"Vision Analysis Failed (OpenAI): {e}")
            return f"(認識エラー: {err_msg})"
