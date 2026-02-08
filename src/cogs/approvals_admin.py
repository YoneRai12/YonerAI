from __future__ import annotations

import logging
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.access_control import is_owner

logger = logging.getLogger(__name__)


class ApprovalsAdmin(commands.Cog):
    """
    Owner-only approval commands.
    This is intentionally out-of-band from guest channels.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def _assert_owner(self, interaction: discord.Interaction) -> Optional[str]:
        if not interaction.user:
            return "No user."
        if not is_owner(self.bot, interaction.user.id):
            return "Owner only."
        if not getattr(self.bot, "store", None):
            return "Store is not available."
        return None

    @app_commands.command(name="approvals", description="List pending approval requests (owner only).")
    async def approvals(self, interaction: discord.Interaction, limit: int = 20) -> None:
        err = self._assert_owner(interaction)
        if err:
            await interaction.response.send_message(f"⛔ {err}", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        limit = max(1, min(50, int(limit)))
        rows = await self.bot.store.get_approval_requests_rows(limit=limit, status="pending")
        if not rows:
            await interaction.followup.send("No pending approvals.", ephemeral=True)
            return

        lines = []
        now = int(time.time())
        for r in rows:
            aid = r.get("tool_call_id")
            tool = r.get("tool_name")
            lvl = r.get("risk_level")
            score = r.get("risk_score")
            exp = int(r.get("expires_at") or 0)
            ttl = max(0, exp - now) if exp else 0
            summary = (r.get("summary") or "").strip()
            if summary:
                lines.append(f"- `{aid}` {tool} {lvl}({score}) ttl~{ttl}s: {summary[:120]}")
            else:
                lines.append(f"- `{aid}` {tool} {lvl}({score}) ttl~{ttl}s")
        await interaction.followup.send("\n".join(lines)[:1800], ephemeral=True)

    @app_commands.command(name="approve", description="Approve a pending request (owner only).")
    async def approve(self, interaction: discord.Interaction, approval_id: str, code: str | None = None) -> None:
        err = self._assert_owner(interaction)
        if err:
            await interaction.response.send_message(f"⛔ {err}", ephemeral=True)
            return

        approval_id = (approval_id or "").strip()
        await interaction.response.defer(ephemeral=True)
        req = await self.bot.store.get_approval_request(tool_call_id=approval_id)
        if not req:
            await interaction.followup.send("Not found.", ephemeral=True)
            return
        if req.get("status") != "pending":
            await interaction.followup.send(f"Already decided: {req.get('status')}", ephemeral=True)
            return

        # Code check for CRITICAL flows.
        if req.get("requires_code"):
            expected = (req.get("expected_code") or "").strip()
            presented = (code or "").strip()
            if not expected:
                await interaction.followup.send("❌ Missing expected code (request setup bug).", ephemeral=True)
                return
            if presented != expected:
                await interaction.followup.send("❌ Code mismatch.", ephemeral=True)
                return

        ok = await self.bot.store.decide_approval_request(
            tool_call_id=approval_id,
            status="approved",
            decided_by=f"discord:{interaction.user.id}",
        )
        await interaction.followup.send("✅ Approved." if ok else "No-op (not pending).", ephemeral=True)

    @app_commands.command(name="deny", description="Deny a pending request (owner only).")
    async def deny(self, interaction: discord.Interaction, approval_id: str) -> None:
        err = self._assert_owner(interaction)
        if err:
            await interaction.response.send_message(f"⛔ {err}", ephemeral=True)
            return

        approval_id = (approval_id or "").strip()
        await interaction.response.defer(ephemeral=True)
        req = await self.bot.store.get_approval_request(tool_call_id=approval_id)
        if not req:
            await interaction.followup.send("Not found.", ephemeral=True)
            return
        if req.get("status") != "pending":
            await interaction.followup.send(f"Already decided: {req.get('status')}", ephemeral=True)
            return

        ok = await self.bot.store.decide_approval_request(
            tool_call_id=approval_id,
            status="denied",
            decided_by=f"discord:{interaction.user.id}",
        )
        await interaction.followup.send("⛔ Denied." if ok else "No-op (not pending).", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ApprovalsAdmin(bot))

