from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import discord
from discord import ui

logger = logging.getLogger(__name__)


def _fmt_duration(sec: Optional[int]) -> str:
    if not sec or sec <= 0:
        return ""
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


class MusicPickView(ui.View):
    """
    Discord-native picker (scrollable select menu) for YouTube search results.
    """

    def __init__(
        self,
        *,
        cog: Any,
        requester_id: int,
        results: List[Dict[str, Any]],
        query: str,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog
        self.requester_id = int(requester_id)
        self.results = list(results or [])
        self.query = query
        self.message: Optional[discord.Message] = None

        options: list[discord.SelectOption] = []
        for idx, r in enumerate(self.results[:25]):
            title = str(r.get("title") or "(no title)")
            if len(title) > 95:
                title = title[:92] + "..."
            dur = _fmt_duration(r.get("duration"))
            desc = f"{dur}" if dur else "YouTube"
            options.append(discord.SelectOption(label=title, description=desc, value=str(idx)))

        self.select = ui.Select(
            placeholder="曲を選んでください (スクロールできます)",
            min_values=1,
            max_values=1,
            options=options or [discord.SelectOption(label="(no results)", value="-1")],
            custom_id="music_pick_select",
        )
        self.select.callback = self._on_select  # type: ignore[assignment]
        self.add_item(self.select)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="music_pick_cancel", row=1)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):  # type: ignore[override]
        await interaction.response.defer(ephemeral=True)
        for item in self.children:
            try:
                item.disabled = True  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass
        try:
            await interaction.followup.send("キャンセルしました。", ephemeral=True)
        except Exception:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and int(interaction.user.id) == int(self.requester_id):
            return True
        try:
            await interaction.response.send_message("これはリクエストした本人だけ操作できます。", ephemeral=True)
        except Exception:
            pass
        return False

    async def on_timeout(self) -> None:
        for item in self.children:
            try:
                item.disabled = True  # type: ignore[attr-defined]
            except Exception:
                pass
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

    async def _on_select(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            idx = int(self.select.values[0])
        except Exception:
            idx = -1
        if idx < 0 or idx >= len(self.results):
            try:
                await interaction.followup.send("選択が無効です。", ephemeral=True)
            except Exception:
                pass
            return

        picked = self.results[idx]
        url = str(picked.get("webpage_url") or "").strip()
        title = str(picked.get("title") or "").strip()
        if not url:
            try:
                await interaction.followup.send("URLが取れませんでした。", ephemeral=True)
            except Exception:
                pass
            return

        # Disable UI now (avoid double-click spam)
        for item in self.children:
            try:
                item.disabled = True  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass

        # Delegate to MediaCog helper. Use the picked URL to resolve stream and play.
        try:
            # MediaCog.play_from_ai expects a Context-like object; we can reuse the interaction's channel via a fake ctx.
            # But MediaCog already has ytplay/play helpers; simplest: call play_from_ai via ctx derived from bot.get_context(message).
            # Here, we just send a status message and ask the cog to enqueue via its existing helper.
            # The cog method will verify the user is in VC.
            ctx = await self.cog.bot.get_context(self.message) if self.message else None
            if ctx:
                await self.cog.play_from_ai(ctx, url)
            else:
                await interaction.followup.send(f"🎵 再生: {title}\n{url}")
        except Exception as e:
            logger.exception("Music pick play failed: %s", e)
            try:
                await interaction.followup.send("再生に失敗しました。", ephemeral=True)
            except Exception:
                pass
