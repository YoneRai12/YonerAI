from __future__ import annotations

import asyncio
import os
import secrets
from dataclasses import dataclass
from typing import Any, Dict, Optional

import discord

from src.utils.access_control import is_owner


@dataclass(frozen=True)
class ApprovalPolicy:
    requires_approval: bool
    requires_code: bool
    timeout_sec: int


def _timeout_sec() -> int:
    raw = (os.getenv("ORA_APPROVAL_TIMEOUT_SEC") or "120").strip()
    try:
        val = int(raw)
    except Exception:
        val = 120
    return max(30, min(600, val))


def _critical_code_len() -> int:
    raw = (os.getenv("ORA_APPROVAL_CRITICAL_CODE_LEN") or "6").strip()
    try:
        val = int(raw)
    except Exception:
        val = 6
    return max(4, min(10, val))


def policy_for(*, bot: Any, actor_id: int, risk_level: str, risk_score: int) -> ApprovalPolicy:
    """
    Owner policy (per your decision):
    - LOW/MEDIUM: auto
    - HIGH: 1-click approval
    - CRITICAL: 2-step approval (button + code)
    """
    timeout = _timeout_sec()
    is_own = is_owner(bot, actor_id)

    # Non-owner users are already tool-allowlisted; still gate MEDIUM+ by default.
    if not is_own:
        if risk_score >= 30:
            return ApprovalPolicy(requires_approval=True, requires_code=(risk_score >= 90), timeout_sec=timeout)
        return ApprovalPolicy(requires_approval=False, requires_code=False, timeout_sec=timeout)

    if risk_score >= 90:
        return ApprovalPolicy(requires_approval=True, requires_code=True, timeout_sec=timeout)
    if risk_score >= 60:
        return ApprovalPolicy(requires_approval=True, requires_code=False, timeout_sec=timeout)
    return ApprovalPolicy(requires_approval=False, requires_code=False, timeout_sec=timeout)


def _redact_args(args: Dict[str, Any]) -> Dict[str, Any]:
    # Reuse the trace redaction rules
    from src.utils.agent_trace import _sanitize as sanitize  # type: ignore
    return sanitize(args, max_str=200)  # type: ignore


class _ApprovalCodeModal(discord.ui.Modal):
    def __init__(self, *, expected_code: str, fut: asyncio.Future, title: str = "CRITICAL Approval Code"):
        super().__init__(title=title)
        self.expected_code = expected_code
        self.fut = fut
        self.code = discord.ui.TextInput(
            label="Enter approval code",
            placeholder="e.g. 123456",
            required=True,
            max_length=16,
        )
        self.add_item(self.code)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if self.fut.done():
            await interaction.response.send_message("Already decided.", ephemeral=True)
            return
        entered = str(self.code.value or "").strip()
        if entered != self.expected_code:
            await interaction.response.send_message("❌ Code mismatch.", ephemeral=True)
            return
        self.fut.set_result(("approved", entered))
        await interaction.response.send_message("✅ Approved.", ephemeral=True)


class ApprovalView(discord.ui.View):
    def __init__(
        self,
        *,
        actor_id: int,
        risk_level: str,
        requires_code: bool,
        expected_code: str,
        fut: asyncio.Future,
        timeout: int,
    ):
        super().__init__(timeout=timeout)
        self.actor_id = actor_id
        self.risk_level = risk_level
        self.requires_code = requires_code
        self.expected_code = expected_code
        self.fut = fut

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.actor_id:
            return True
        await interaction.response.send_message("⛔ Only the request owner can approve.", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if not self.fut.done():
            self.fut.set_result(("timeout", None))

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.fut.done():
            await interaction.response.send_message("Already decided.", ephemeral=True)
            return
        if self.requires_code:
            await interaction.response.send_modal(_ApprovalCodeModal(expected_code=self.expected_code, fut=self.fut))
            return
        self.fut.set_result(("approved", None))
        await interaction.response.send_message("✅ Approved.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.fut.done():
            await interaction.response.send_message("Already decided.", ephemeral=True)
            return
        self.fut.set_result(("denied", None))
        await interaction.response.send_message("❌ Denied.", ephemeral=True)


async def request_approval(
    *,
    bot: Any,
    message: discord.Message,
    tool_name: str,
    args: Dict[str, Any],
    risk_score: int,
    risk_level: str,
    reasons: list[str],
    correlation_id: str = "",
    tool_call_id: str = "",
    requires_code: bool,
    timeout_sec: int,
) -> dict:
    """
    Send approval UI to Discord and await decision.
    Returns: {"status": "approved"|"denied"|"timeout", "code": str|None, "expected_code": str|None}
    """
    expected = ""
    if requires_code:
        expected = secrets.token_hex(8)[: _critical_code_len()]

    fut: asyncio.Future = asyncio.get_event_loop().create_future()
    view = ApprovalView(
        actor_id=message.author.id,
        risk_level=risk_level,
        requires_code=requires_code,
        expected_code=expected,
        fut=fut,
        timeout=timeout_sec,
    )

    redacted = _redact_args(args if isinstance(args, dict) else {})
    reason_text = "\n".join(f"- {r}" for r in (reasons or [])[:12]) or "- (none)"

    embed = discord.Embed(
        title=f"Approval Required ({risk_level})",
        description="Tool execution is paused until you approve.",
        color=0xE53E3E if risk_level == "CRITICAL" else 0xDD6B20,
    )
    embed.add_field(name="Tool", value=f"`{tool_name}`", inline=False)
    if tool_call_id:
        embed.add_field(name="ToolCallID", value=f"`{tool_call_id}`", inline=False)
    if correlation_id:
        embed.add_field(name="CID", value=f"`{correlation_id}`", inline=False)
    embed.add_field(name="Risk", value=f"score={risk_score} level={risk_level}", inline=False)
    embed.add_field(name="Reasons", value=reason_text[:1024], inline=False)
    embed.add_field(name="Args (redacted)", value=f"```json\n{str(redacted)[:900]}\n```", inline=False)
    if requires_code:
        embed.add_field(name="CRITICAL Code", value=f"`{expected}` (enter in modal)", inline=False)
    embed.set_footer(text=f"Timeout: {timeout_sec}s (auto-deny)")

    msg = await message.reply(embed=embed, view=view)
    status, code = await fut

    # Disable buttons after decision
    try:
        for child in view.children:
            if hasattr(child, "disabled"):
                child.disabled = True
        await msg.edit(view=view)
    except Exception:
        pass

    return {"status": status, "code": code, "expected_code": expected or None}

