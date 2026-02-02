import asyncio
import io
import discord
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def generate_image(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Generate image via CreativeCog."""
    prompt = args.get("prompt")
    if not prompt: return "❌ Missing prompt."
    
    if status_manager: await status_manager.next_step(f"Generating: {prompt[:20]}...")
    
    if not bot: return "❌ Bot instance missing."
    creative_cog = bot.get_cog("CreativeCog")
    if not creative_cog: return "❌ CreativeCog offline."
    
    try:
        # Assuming generate_video returns bytes of mp4/gif/image
        # If it's DALL-E, it might differ. The original code called 'generate_video'.
        data = await bot.loop.run_in_executor(None, lambda: creative_cog.comfy_client.generate_video(prompt, ""))
        if data:
            f = discord.File(io.BytesIO(data), filename="generated.mp4")
            await message.reply(content=f"🎨 **Generated**: {prompt}", file=f)
            return "Generation complete. [SILENT_COMPLETION]"
        return "❌ Generation returned no data."
    except Exception as e:
        return f"❌ Gen Error: {e}"

async def layer_separation(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """Separate layers of an image."""
    # Logic extracted from _handle_layer
    target_img = message.attachments[0] if message.attachments else None
    if not target_img and message.reference:
        ref = await message.channel.fetch_message(message.reference.message_id)
        if ref.attachments:
            target_img = ref.attachments[0]
            
    if not target_img: return "❌ No image found."
    
    if status_manager: await status_manager.next_step("Separating Layers...")
    
    if not bot: return "❌ Bot instance missing."
    creative_cog = bot.get_cog("CreativeCog")
    if not creative_cog: return "❌ CreativeCog offline."
    
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("file", await target_img.read(), filename=target_img.filename)
            async with session.post(creative_cog.layer_api, data=data) as resp:
                if resp.status == 200:
                    f = discord.File(io.BytesIO(await resp.read()), filename=f"layers_{target_img.filename}.zip")
                    await message.reply("✅ Layers Separated!", file=f)
                    return "Layering complete. [SILENT_COMPLETION]"
                return f"❌ API Error: {resp.status}"
    except Exception as e:
        return f"❌ Layer Error: {e}"
