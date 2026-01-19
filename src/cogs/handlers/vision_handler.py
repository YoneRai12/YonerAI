import base64
import io
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiofiles
import aiohttp
import discord
from PIL import Image

logger = logging.getLogger(__name__)

class VisionHandler:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.supported_text_ext = {'.txt', '.md', '.py', '.js', '.json', '.html', '.css', '.csv', '.xml', '.yaml', '.yml', '.sh', '.bat', '.ps1'}
        self.supported_img_ext = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}

    async def process_attachments(self, attachments: List[discord.Attachment], is_reference: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process attachments and return (prompt_suffix, image_payloads).
        """
        prompt_suffix = ""
        image_payloads = []

        for i, attachment in enumerate(attachments):
            ext = "." + attachment.filename.split(".")[-1].lower() if "." in attachment.filename else ""
            
            # TEXT PROCESSING
            if ext in self.supported_text_ext or (attachment.content_type and "text" in attachment.content_type):
                if attachment.size > 1024 * 1024: 
                    continue
                try:
                    content = await attachment.read()
                    text_content = content.decode('utf-8', errors='ignore')
                    header = f"[Referenced File: {attachment.filename}]" if is_reference else f"[Attached File: {attachment.filename}]"
                    prompt_suffix += f"\n\n{header}\n{text_content}\n"
                except Exception:
                    pass

            # IMAGE PROCESSING
            elif ext in self.supported_img_ext:
                if attachment.size > 8 * 1024 * 1024:
                    continue
                
                try:
                    image_data = await attachment.read()
                    
                    # Cache to disk
                    timestamp = int(time.time())
                    safe_filename = f"{timestamp}_{attachment.filename}"
                    cache_path = self.cache_dir / safe_filename
                    async with aiofiles.open(cache_path, "wb") as f:
                        await f.write(image_data)
                    
                    # Optimize & Encode
                    b64_img = await self._optimize_and_encode(image_data)
                    if b64_img:
                        payload = {
                            "type": "image_url", 
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                        }
                        image_payloads.append(payload)

                        header = f"[Referenced Image: {attachment.filename}]" if is_reference else f"[Attached Image {i+1}: {attachment.filename}]"
                        prompt_suffix += f"\n\n{header}\n(Image loaded into Qwen2.5-VL Vision Context)\n"
                    
                except Exception as e:
                    logger.error(f"Image process failed: {e}")

        return prompt_suffix, image_payloads

    async def process_embeds(self, embeds: List[discord.Embed], is_reference: bool = False) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Process images in embeds.
        """
        prompt_suffix = ""
        image_payloads = []
        
        for embed in embeds:
            image_url = None
            if embed.image and embed.image.url:
                image_url = embed.image.url
            elif embed.thumbnail and embed.thumbnail.url:
                image_url = embed.thumbnail.url
            
            if not image_url:
                continue
                
            try:
                # Download
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url, timeout=5) as resp:
                        if resp.status != 200:
                            continue
                        image_data = await resp.read()
                
                # Optimize & Encode
                b64_img = await self._optimize_and_encode(image_data)
                if b64_img:
                     payload = {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                     }
                     image_payloads.append(payload)
                     prompt_suffix += "\n\n[Embed Image]\n(Image loaded into Qwen2.5-VL Vision Context)\n"

            except Exception as e:
                logger.warning(f"Failed to process embed image {image_url}: {e}")
        
        return prompt_suffix, image_payloads

    async def _optimize_and_encode(self, image_data: bytes) -> Optional[str]:
        """Resize logic."""
        try:
             # Load image with PIL
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB (in case of RGBA/PNG)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Resize if too large (Max 1024x1024)
                max_size = 1024
                if max(img.size) > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Save to buffer as JPEG
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                optimized_data = buffer.getvalue()
            
            return base64.b64encode(optimized_data).decode('utf-8')
        except Exception as e:
            logger.error(f"Vision Encode Error: {e}")
            return None
