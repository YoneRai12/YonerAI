
import discord
from discord.ui import View, Button
import json
import asyncio

class ResolutionSelectView(View):
    def __init__(self, cog, interaction, prompt, negative_prompt, width, height):
        super().__init__(timeout=None)
        self.cog = cog
        self.original_interaction = interaction
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.width = width
        self.height = height

    async def start_generation(self, interaction: discord.Interaction, scale: float):
        await interaction.response.defer()
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        await self.original_interaction.edit_original_response(view=self)

        # Calculate Highres Fix dimensions
        # scale 1.5 -> FHD ish
        # scale 2.0 -> WQHD
        # scale 3.0 -> 4K
        
        # We use 'enable_hr' and 'hr_scale'
        # Base size is what we start with (512 or 768)
        
        # SAFETY ENFORCEMENT
        # Inject strong safety guidelines
        safe_prompt = f"{self.prompt}, (safe for work:1.2)"
        
        # Explicitly ban NSFW concepts with high weight
        hidden_negative = (
            ", (nsfw:2.0), (nude:2.0), (naked:2.0), (sexual:2.0), (porn:2.0), (hentai:2.0), "
            "(exposed:2.0), (breasts:2.0), (genitals:2.0), (penis:2.0), (vagina:2.0), "
            "(sexual act:2.0), (nsfw content:2.0)"
        )
        safe_negative = f"{self.negative_prompt}{hidden_negative}"

        payload = {
            "prompt": safe_prompt,
            "negative_prompt": safe_negative,
            "steps": 30,
            "width": self.width,
            "height": self.height,
            "sampler_name": "DPM++ 2M Karras",
            "cfg_scale": 7,
            "enable_hr": True,
            "hr_scale": scale,
            "hr_upscaler": "R-ESRGAN 4x+", 
            "hr_second_pass_steps": 15,
            "denoising_strength": 0.55
        }

        # Lock Bot
        self.cog.is_generating_image = True
        await interaction.followup.send(f"🎨 **画像生成を開始します...**\nプロンプト: `{self.prompt}`\n設定: `{self.width}x{self.height}` -> `Scalar x{scale}`\n(生成中は他の会話が待機状態になります)")
        
        # Offload LLM to save VRAM
        try:
            await self.cog._llm.unload_model() # Using _llm since it's private in cog usually, or public?
            # Cog init: self._llm = llm. So it's _llm.
            # But wait, looking at ora.py: self._llm = llm
            # But standard public access? Let's check if it has a property.
            # Usually cogs don't expose it.
            # Accessing privates in Python is fine.
        except Exception as e:
            print(f"Failed to offload LLM: {e}")

        try:
            # Call API
            url = f"{self.cog.bot.config.sd_api_url}/sdapi/v1/txt2img"
            async with self.cog.bot.session.post(url, json=payload, timeout=300) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    await interaction.followup.send(f"❌ エラーが発生しました: {resp.status}\n{text[:100]}")
                    return

                data = await resp.json()
                if "images" in data:
                    from src.utils.image_tools import decode_base64_image
                    
                    files = []
                    for i, img_str in enumerate(data["images"]):
                        img_data = decode_base64_image(img_str)
                        files.append(discord.File(img_data, filename=f"gen_{i}.png"))
                    
                    await interaction.followup.send(f"✅ **生成完了!**", files=files)
                else:
                    await interaction.followup.send("❌ 画像データが含まれていませんでした。")

        except Exception as e:
            await interaction.followup.send(f"❌ 予期せぬエラー: {e}")
        
        finally:
            # Unlock Bot and Process Queue
            self.cog.is_generating_image = False
            await interaction.followup.send("🔓 **生成終了: 待機していた会話を再開します。**")
            # Process queue in background
            asyncio.create_task(self.cog.process_message_queue())

    @discord.ui.button(label="FHD (10s)", style=discord.ButtonStyle.primary, custom_id="res_fhd")
    async def fhd_button(self, interaction: discord.Interaction, button: Button):
        await self.start_generation(interaction, 1.5) # approx 1.5x upscaling

    @discord.ui.button(label="WQHD (30s)", style=discord.ButtonStyle.success, custom_id="res_wqhd")
    async def wqhd_button(self, interaction: discord.Interaction, button: Button):
        await self.start_generation(interaction, 2.0) # 2x upscaling

    @discord.ui.button(label="4K (60s)", style=discord.ButtonStyle.danger, custom_id="res_4k")
    async def four_k_button(self, interaction: discord.Interaction, button: Button):
        await self.start_generation(interaction, 3.0) # 3x upscaling


class AspectRatioSelectView(View):
    def __init__(self, cog, prompt, negative_prompt):
        super().__init__(timeout=None)
        self.cog = cog
        self.prompt = prompt
        self.negative_prompt = negative_prompt

    async def proceed(self, interaction: discord.Interaction, w, h, label):
        await interaction.response.edit_message(content=f"✅ 比率を選択: **{label}**\n次は画質(解像度)を選んでください。", view=ResolutionSelectView(self.cog, interaction, self.prompt, self.negative_prompt, w, h))

    @discord.ui.button(label="正方形 (1:1)", style=discord.ButtonStyle.secondary)
    async def square(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 512, 512, "正方形")

    @discord.ui.button(label="縦長 (2:3)", style=discord.ButtonStyle.secondary)
    async def portrait(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 512, 768, "縦長")

    @discord.ui.button(label="横長 (3:2)", style=discord.ButtonStyle.secondary)
    async def landscape(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 768, 512, "横長 (3:2)")

    @discord.ui.button(label="ワイド (16:9)", style=discord.ButtonStyle.secondary, row=1)
    async def wide(self, interaction: discord.Interaction, button: Button):
        # 16:9 -> 912x512 is close to 16:9 (1.78) for SD1.5
        # Or 854x480? Let's use 912x512.
        await self.proceed(interaction, 912, 512, "ワイド (16:9)")

    @discord.ui.button(label="スマホ縦 (9:16)", style=discord.ButtonStyle.secondary, row=1)
    async def mobile_portrait(self, interaction: discord.Interaction, button: Button):
        # 9:16 -> 512x912
        await self.proceed(interaction, 512, 912, "スマホ縦 (9:16)")
