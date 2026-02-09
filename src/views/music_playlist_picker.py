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


class PlaylistPickView(ui.View):
    """
    Discord-native picker for YouTube playlist entries.

    Constraints:
    - Discord Select menus allow up to 25 options. We paginate for larger playlists.
    """

    def __init__(
        self,
        *,
        cog: Any,
        requester_id: int,
        playlist_title: str,
        playlist_url: str,
        entries: List[Dict[str, Any]],
        page_size: int = 20,
        timeout: float = 120.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self.cog = cog
        self.requester_id = int(requester_id)
        self.playlist_title = playlist_title
        self.playlist_url = playlist_url
        self.entries = list(entries or [])
        self.page_size = max(5, min(25, int(page_size or 20)))
        self.page = 0
        self.message: Optional[discord.Message] = None

        self.select = ui.Select(
            placeholder="プレイリストから曲を選んでください (スクロールできます)",
            min_values=1,
            max_values=1,
            options=self._build_options(),
            custom_id="music_playlist_pick_select",
        )
        self.select.callback = self._on_select  # type: ignore[assignment]
        self.add_item(self.select)

    def _build_options(self) -> list[discord.SelectOption]:
        if not self.entries:
            return [discord.SelectOption(label="(no entries)", value="-1")]

        start = self.page * self.page_size
        end = min(len(self.entries), start + self.page_size)

        options: list[discord.SelectOption] = []
        for idx in range(start, end):
            e = self.entries[idx]
            title = str(e.get("title") or "(no title)")
            if len(title) > 95:
                title = title[:92] + "..."
            dur = _fmt_duration(e.get("duration"))
            desc = f"{idx + 1}/{len(self.entries)}" + (f" • {dur}" if dur else "")
            options.append(discord.SelectOption(label=title, description=desc[:100], value=str(idx)))
        return options

    async def _rerender(self, *, interaction: discord.Interaction, note: Optional[str] = None) -> None:
        try:
            self.select.options = self._build_options()
        except Exception:
            # Some discord.py versions don't like reassigning; fallback to rebuild the view.
            pass

        embed = discord.Embed(
            title="Choose a track from playlist",
            description=f"Playlist: **{self.playlist_title}**\nPage: {self.page + 1}/{max(1, (len(self.entries) + self.page_size - 1) // self.page_size)}",
            color=discord.Color.from_rgb(29, 185, 84),
        )
        if note:
            embed.add_field(name="Info", value=note[:1024], inline=False)

        try:
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception:
            pass

        try:
            await interaction.response.defer()
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

    @ui.button(label="Prev", style=discord.ButtonStyle.secondary, custom_id="music_playlist_prev", row=1)
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):  # type: ignore[override]
        if self.page > 0:
            self.page -= 1
        await self._rerender(interaction=interaction)

    @ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="music_playlist_next", row=1)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):  # type: ignore[override]
        max_page = max(0, (len(self.entries) - 1) // self.page_size)
        if self.page < max_page:
            self.page += 1
        await self._rerender(interaction=interaction)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="music_playlist_cancel", row=1)
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

    async def _on_select(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            idx = int(self.select.values[0])
        except Exception:
            idx = -1
        if idx < 0 or idx >= len(self.entries):
            try:
                await interaction.followup.send("選択が無効です。", ephemeral=True)
            except Exception:
                pass
            return

        picked = self.entries[idx]
        url = str(picked.get("webpage_url") or "").strip()
        title = str(picked.get("title") or "").strip()
        if not url:
            try:
                await interaction.followup.send("URLが取れませんでした。", ephemeral=True)
            except Exception:
                pass
            return

        # Disable UI now (avoid spam / double clicks)
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
            ctx = await self.cog.bot.get_context(self.message) if self.message else None
            if ctx:
                await self.cog.play_from_ai(ctx, url)
            else:
                await interaction.followup.send(f"🎵 再生: {title}\n{url}")
        except Exception as e:
            logger.exception("Playlist pick play failed: %s", e)
            try:
                await interaction.followup.send("再生に失敗しました。", ephemeral=True)
            except Exception:
                pass

