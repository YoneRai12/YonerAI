import asyncio
import io
import logging

import discord
from discord.ui import Button, View

from src.utils.comfy_client import ComfyWorkflow

logger = logging.getLogger(__name__)


class StyleSelectView(View):
    def __init__(self, cog, interaction, prompt, negative_prompt, width, height, is_flux=True, is_high_quality=False):
        super().__init__(timeout=None)
        self.cog = cog
        self.original_interaction = interaction
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.width = width
        self.height = height
        self.is_flux = is_flux
        self.is_high_quality = is_high_quality

    async def start_generation(self, interaction: discord.Interaction, style: str):
        await interaction.response.defer()

        # Disable buttons
        for child in self.children:
            child.disabled = True
        await self.original_interaction.edit_original_response(view=self)

        # Apply Style Modifiers
        final_prompt = self.prompt
        style_suffix = ""

        if style == "natural":
            style_suffix = ", beautiful mountain landscape, nature, national geographic photo, 8k, masterpiece"
        elif style == "future":
            style_suffix = ", futuristic cyberpunk city, neon lights, scifi, highly detailed, 8k"
        elif style == "animal":
            style_suffix = ", cute fluffy, soft lighting, depth of field, studio photography, 8k"
        elif style == "real":
            style_suffix = ", photorealistic, cinematic lighting, 8k, masterpiece, highly detailed"

        if style != "raw":
            final_prompt += style_suffix

        # Translate to English if needed
        mode_label = "Native"
        if self.cog.llm and any(ord(c) > 128 for c in final_prompt):
            try:
                translation_prompt = (
                    f"Translate the following image prompt to English for Stable Diffusion. "
                    f"Output ONLY the translated English text, no explanations.\n\nPrompt: {final_prompt}"
                )
                translated = await self.cog.llm.chat(
                    messages=[{"role": "user", "content": translation_prompt}], temperature=0.1
                )
                final_prompt = translated.strip()
                mode_label = "Translated"
            except Exception as e:
                # Log error but proceed with original
                print(f"Translation failed: {e}")

        # Quality Modifiers
        if self.is_high_quality:
            final_prompt += ", best quality, ultra detailed, 8k, highres, sharp focus"

        # SAFETY ENFORCEMENT
        safe_negative = "nsfw, nude, naked, porn, hentai, sexual, exposed, breasts, genitals, low quality, bad anatomy"
        if self.negative_prompt:
            safe_negative = f"{self.negative_prompt}, {safe_negative}"

        # Lock Bot & Switch Context
        self.cog.is_generating_image = True

        # 1. SWITCH TO IMAGE CONTEXT (Kills vLLM, Starts Comfy)
        await interaction.followup.send(
            f"🎨 **生成開始 (Flux Engine)**\nMode: `{mode_label}`\nStyle: `{style.upper()}`\nSize: `{self.width}x{self.height}`\nPrompt(Eng): `{final_prompt[:100]}...`\n(🚀 GPUコンテキスト切替中... vLLM停止 -> Comfy起動)"
        )

        try:
            await self.cog.resource_manager.switch_context("image")
        except Exception as e:
            await interaction.followup.send(f"❌ コンテキスト切替エラー: {e}")
            self.cog.is_generating_image = False
            return

        try:
            # Initialize Comfy Client
            workflow = ComfyWorkflow(
                server_address=self.cog.bot.config.sd_api_url.replace("http://", "").replace("/", "")
            )

            # Execute Generation in Thread
            image_data = await asyncio.to_thread(
                workflow.generate_image,
                positive_prompt=final_prompt,
                negative_prompt=safe_negative,
                steps=steps,
                width=self.width,
                height=self.height,
            )

            if image_data:
                file = discord.File(io.BytesIO(image_data), filename=f"flux_gen_{style}.png")
                await interaction.followup.send("✅ **生成完了!**", file=file)
            else:
                await interaction.followup.send("❌ 生成に失敗しました (ComfyUIからのデータなし)")

        except Exception as e:
            await interaction.followup.send(f"❌ エラー: {e}")

        finally:
            self.cog.is_generating_image = False

            # 2. SWITCH BACK TO LLM CONTEXT (Kills Comfy, Starts vLLM)
            await interaction.followup.send(
                "🔄 **処理完了**: 脳神経(LLM)を再起動して復帰します... (少々お待ちください)"
            )
            logger.info("🔄 Switching back to LLM Context...")
            try:
                await self.cog.resource_manager.switch_context("llm")
            except Exception as e:
                logger.error(f"Failed to restore LLM context: {e}")
                await interaction.followup.send(f"⚠️ LLM復帰に失敗しました: {e}")

            asyncio.create_task(self.cog.process_message_queue())

    @discord.ui.button(label="おまかせ (Auto)", style=discord.ButtonStyle.primary)
    async def style_auto(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()

        # Disable buttons temporarily
        for child in self.children:
            child.disabled = True
        await self.original_interaction.edit_original_response(view=self)

        determined_style = "real"  # Fallback

        # Use LLM to decide style if available (Before Unload)
        if self.cog.llm:
            try:
                classification_prompt = (
                    f"Classify the following image prompt into one of these styles: 'natural', 'future', 'animal', 'real'. "
                    f"Output ONLY the style name (lowercase). If unsure, output 'real'.\n\nPrompt: {self.prompt}"
                )

                response = await self.cog.llm.chat(
                    messages=[{"role": "user", "content": classification_prompt}], temperature=0.1
                )

                clean_style = response.strip().lower()
                valid_styles = ["natural", "future", "animal", "real"]

                for vs in valid_styles:
                    if vs in clean_style:
                        determined_style = vs
                        break

                await interaction.followup.send(
                    f"🤖 **AI判断**: `{determined_style}` スタイルで生成します...", ephemeral=True
                )

            except Exception:
                # Fallback to simple heuristic
                p = self.prompt.lower()
                if "cat" in p or "dog" in p or "animal" in p:
                    determined_style = "animal"
                elif "city" in p or "robot" in p or "cyber" in p:
                    determined_style = "future"
                elif "forest" in p or "mountain" in p or "sky" in p:
                    determined_style = "natural"

        # Proceed with generation (Unload happens inside start_generation)
        await self.start_generation(interaction, determined_style)

    @discord.ui.button(label="自然 (Nature)", style=discord.ButtonStyle.secondary)
    async def style_nature(self, interaction: discord.Interaction, button: Button):
        await self.start_generation(interaction, "natural")

    @discord.ui.button(label="未来 (Future)", style=discord.ButtonStyle.secondary)
    async def style_future(self, interaction: discord.Interaction, button: Button):
        await self.start_generation(interaction, "future")

    @discord.ui.button(label="動物 (Animal)", style=discord.ButtonStyle.secondary)
    async def style_animal(self, interaction: discord.Interaction, button: Button):
        await self.start_generation(interaction, "animal")

    @discord.ui.button(label="リアル (Real)", style=discord.ButtonStyle.secondary)
    async def style_real(self, interaction: discord.Interaction, button: Button):
        await self.start_generation(interaction, "real")


class QualitySelectView(View):
    def __init__(self, cog, interaction, prompt, negative_prompt, width, height):
        super().__init__(timeout=None)
        self.cog = cog
        self.original_interaction = interaction
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.base_width = width
        self.base_height = height

    def _calculate_res(self, scale_keyword: str):
        # Calculate Aspect Ratio
        ratio = self.base_width / self.base_height

        # Define Target Long Edge (Approximate for 16:9)
        # FHD: 1920, WQHD: 2560, 4K: 3840
        if scale_keyword == "FHD":
            target_long = 1920 if ratio >= 1 else 1080
        elif scale_keyword == "WQHD":
            target_long = 2560 if ratio >= 1 else 1440
        elif scale_keyword == "4KUHD":
            target_long = 3840 if ratio >= 1 else 2160
        else:
            return self.base_width, self.base_height

        if ratio >= 1:  # Landscape or Square
            w = target_long
            h = int(w / ratio)
        else:  # Portrait
            h = target_long
            w = int(h * ratio)

        # Ensure divisible by 64 (Flux requirement)
        w = ((w + 32) // 64) * 64
        h = ((h + 32) // 64) * 64
        return w, h

    async def proceed(self, interaction: discord.Interaction, label: str):
        w, h = self._calculate_res(label)

        # High Quality flag is True for WQHD/4K to increase steps
        is_high_quality = label in ["WQHD", "4KUHD"]

        view = StyleSelectView(
            self.cog, interaction, self.prompt, self.negative_prompt, w, h, is_high_quality=is_high_quality
        )
        await interaction.response.edit_message(
            content=f"✅ 画質: **{label}** ({w}x{h})\n最後に**スタイル**を選んでください。", view=view
        )

    @discord.ui.button(label="FHD (約20秒)", style=discord.ButtonStyle.secondary)
    async def fhd(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, "FHD")

    @discord.ui.button(label="WQHD (約40秒)", style=discord.ButtonStyle.primary)
    async def wqhd(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, "WQHD")

    @discord.ui.button(label="4KUHD (約80秒)", style=discord.ButtonStyle.danger)
    async def uhd(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, "4KUHD")


class AspectRatioSelectView(View):
    def __init__(self, cog, prompt, negative_prompt, model_name=""):
        super().__init__(timeout=None)
        self.cog = cog
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.model_name = "FLUX.2"

    async def proceed(self, interaction: discord.Interaction, w, h, label):
        # Next Step: Quality Selection
        view = QualitySelectView(self.cog, interaction, self.prompt, self.negative_prompt, w, h)
        await interaction.response.edit_message(
            content=f"✅ 比率: **{label}**\n次は**画質**を選んでください。", view=view
        )

    @discord.ui.button(label="正方形 (1:1)", style=discord.ButtonStyle.secondary)
    async def square(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 1024, 1024, "正方形 1:1")

    @discord.ui.button(label="縦長 (2:3)", style=discord.ButtonStyle.secondary)
    async def portrait(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 832, 1216, "縦長 2:3")

    @discord.ui.button(label="横長 (3:2)", style=discord.ButtonStyle.secondary)
    async def landscape(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 1216, 832, "横長 3:2")

    @discord.ui.button(label="PC/TV (16:9)", style=discord.ButtonStyle.success)
    async def wide(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 1344, 768, "ワイド 16:9")

    @discord.ui.button(label="映画 (21:9)", style=discord.ButtonStyle.success)
    async def cinema(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 1536, 640, "シネマ 21:9")

    @discord.ui.button(label="スマホ (9:16)", style=discord.ButtonStyle.success)
    async def mobile(self, interaction: discord.Interaction, button: Button):
        await self.proceed(interaction, 768, 1344, "スマホ 9:16")
