from __future__ import annotations

import logging
from typing import Any, Optional

import discord
from discord import ui

logger = logging.getLogger(__name__)


class PlaylistActionsView(ui.View):
    """
    Discord-native action UI for playlist-like URLs.

    Provides:
    - Queue All
    - Shuffle + Queue All
    - (Optional) Pick One (provider-specific)
    """

    def __init__(
        self,
        *,
        cog: Any,
        requester_id: int,
        url: str,
        can_pick_one: bool,
        timeout: float = 90.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog
        self.requester_id = int(requester_id)
        self.url = str(url or "").strip()
        self.can_pick_one = bool(can_pick_one)
        self.message: Optional[discord.Message] = None

        if not self.can_pick_one:
            # Disable the pick button at construction time if not supported.
            try:
                self.pick_one.disabled = True  # type: ignore[attr-defined]
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

    async def _disable(self) -> None:
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

    @ui.button(label="Queue All", style=discord.ButtonStyle.primary, custom_id="playlist_actions_queue_all", row=0)
    async def queue_all(self, interaction: discord.Interaction, button: ui.Button):  # type: ignore[override]
        await interaction.response.defer()
        await self._disable()
        try:
            ctx = await self.cog.bot.get_context(self.message) if self.message else None
            if ctx and hasattr(self.cog, "enqueue_playlist_url_from_ai"):
                await self.cog.enqueue_playlist_url_from_ai(ctx, self.url, force_queue_all=True)
        except Exception as e:
            logger.exception("queue_all failed: %s", e)

    @ui.button(
        label="Shuffle + Queue",
        style=discord.ButtonStyle.secondary,
        custom_id="playlist_actions_shuffle_queue",
        row=0,
    )
    async def shuffle_queue(self, interaction: discord.Interaction, button: ui.Button):  # type: ignore[override]
        await interaction.response.defer()
        await self._disable()
        try:
            ctx = await self.cog.bot.get_context(self.message) if self.message else None
            if ctx and hasattr(self.cog, "enqueue_playlist_url_from_ai"):
                await self.cog.enqueue_playlist_url_from_ai(ctx, self.url, force_queue_all=True, shuffle_override=True)
        except Exception as e:
            logger.exception("shuffle_queue failed: %s", e)

    @ui.button(label="Pick One", style=discord.ButtonStyle.secondary, custom_id="playlist_actions_pick_one", row=1)
    async def pick_one(self, interaction: discord.Interaction, button: ui.Button):  # type: ignore[override]
        await interaction.response.defer()
        if not self.can_pick_one:
            try:
                await interaction.followup.send("このURLは曲選択に未対応です。", ephemeral=True)
            except Exception:
                pass
            return

        try:
            ctx = await self.cog.bot.get_context(self.message) if self.message else None
            if ctx and hasattr(self.cog, "playlist_pick_one_ui_from_ai"):
                await self.cog.playlist_pick_one_ui_from_ai(ctx, self.url)
        except Exception as e:
            logger.exception("pick_one failed: %s", e)

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="playlist_actions_cancel", row=1)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):  # type: ignore[override]
        await interaction.response.defer(ephemeral=True)
        await self._disable()
        try:
            await interaction.followup.send("キャンセルしました。", ephemeral=True)
        except Exception:
            pass
