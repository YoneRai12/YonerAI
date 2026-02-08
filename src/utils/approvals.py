from __future__ import annotations

import asyncio
import os
import secrets
import json
import time
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

def _timeout_for_level(risk_level: str) -> int:
    level = (risk_level or "").strip().upper()
    if level == "CRITICAL":
        raw = (os.getenv("ORA_APPROVAL_TTL_CRITICAL_SEC") or "30").strip()
        try:
            val = int(raw)
        except Exception:
            val = 30
        return max(10, min(300, val))
    if level == "HIGH":
        raw = (os.getenv("ORA_APPROVAL_TTL_HIGH_SEC") or str(_timeout_sec())).strip()
        try:
            val = int(raw)
        except Exception:
            val = _timeout_sec()
        return max(30, min(600, val))
    return _timeout_sec()

def timeout_for_level(risk_level: str) -> int:
    """Public wrapper for consistent TTL computation from risk level."""
    return _timeout_for_level(risk_level)


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
    timeout = _timeout_for_level(risk_level)
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


def normalize_args_json(args: Dict[str, Any]) -> str:
    payload = _redact_args(args if isinstance(args, dict) else {})
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)[:5000]
    except Exception:
        return str(payload)[:5000]

def args_hash(args: Dict[str, Any]) -> str:
    """
    Hash raw args for anti-swap verification without storing plaintext args.
    """
    import hashlib

    a = args if isinstance(args, dict) else {}
    try:
        raw = json.dumps(a, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:
        raw = str(a)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def approval_summary(tool_name: str, args: Dict[str, Any], risk_level: str, risk_score: int) -> str:
    # Compact one-liner for lists.
    a = args if isinstance(args, dict) else {}
    key_parts: list[str] = []
    for k in ("url", "path", "query", "command", "cmd", "prompt", "text", "action"):
        v = a.get(k)
        if isinstance(v, str) and v.strip():
            key_parts.append(f"{k}={v.strip()[:80]}")
    extras = ("; ".join(key_parts)[:160]) if key_parts else ""
    if extras:
        return f"{tool_name} ({risk_level} score={risk_score}) {extras}"
    return f"{tool_name} ({risk_level} score={risk_score})"


async def _dm_owner_approval(
    *,
    bot: Any,
    owner_id: int,
    tool_name: str,
    tool_call_id: str,
    correlation_id: str,
    risk_score: int,
    risk_level: str,
    reasons: list[str],
    args_json: str,
    expected_code: str,
    expires_at: int,
) -> None:
    reason_text = "\n".join(f"- {r}" for r in (reasons or [])[:12]) or "- (none)"

    embed = discord.Embed(
        title=f"Approval Required ({risk_level})",
        description="Tool execution is paused. Approve via owner-only command or Web API.",
        color=0xE53E3E if risk_level == "CRITICAL" else 0xDD6B20,
    )
    embed.add_field(name="Tool", value=f"`{tool_name}`", inline=False)
    embed.add_field(name="Approval ID", value=f"`{tool_call_id}`", inline=False)
    if correlation_id:
        embed.add_field(name="CID", value=f"`{correlation_id}`", inline=False)
    embed.add_field(name="Risk", value=f"score={risk_score} level={risk_level}", inline=False)
    embed.add_field(name="Reasons", value=reason_text[:1024], inline=False)
    embed.add_field(name="Args (normalized/redacted)", value=f"```json\n{args_json[:900]}\n```", inline=False)
    if expected_code:
        embed.add_field(name="CRITICAL Code", value=f"`{expected_code}`", inline=False)

    ttl_left = max(0, int(expires_at) - int(time.time()))
    embed.set_footer(text=f"Expires in ~{ttl_left}s. Approve: /approve <id> [code], Deny: /deny <id>")

    try:
        user = bot.get_user(owner_id) or await bot.fetch_user(owner_id)
        await user.send(embed=embed)
    except Exception:
        # If DM fails (blocked), do not brick execution; caller will timeout.
        pass


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
    Out-of-band approval:
    - Create/persist a pending approval row in DB.
    - Notify owner via DM (separate channel).
    - Poll DB for approve/deny/expire until timeout.
    Returns: {"status": "approved"|"denied"|"expired"|"timeout"|"rate_limited", "code": str|None, "expected_code": str|None}
    """
    if not tool_call_id:
        return {"status": "denied", "code": None, "expected_code": None}

    cfg = getattr(bot, "config", None)
    owner_id = getattr(cfg, "admin_user_id", None)
    if not owner_id:
        await message.reply("⛔ Approval required, but ADMIN_USER_ID is not configured.")
        return {"status": "denied", "code": None, "expected_code": None}

    expected = ""
    if requires_code:
        expected = secrets.token_hex(8)[: _critical_code_len()]

    store = getattr(bot, "store", None)
    # Basic anti-spam: rate-limit guest approval creation to avoid owner DM bombing.
    if store and (not is_owner(bot, int(message.author.id))):
        try:
            raw_lim = (os.getenv("ORA_APPROVAL_RATE_LIMIT_PER_MIN") or "0").strip()
            limit = int(raw_lim)
        except Exception:
            limit = 0
        if limit > 0:
            try:
                raw_win = (os.getenv("ORA_APPROVAL_RATE_LIMIT_WINDOW_SEC") or "60").strip()
                window_sec = max(10, min(600, int(raw_win)))
            except Exception:
                window_sec = 60
            since = int(time.time()) - int(window_sec)
            try:
                cnt = await store.count_approval_requests(actor_id=int(message.author.id), since_ts=since)
            except Exception:
                cnt = 0
            if cnt >= int(limit):
                try:
                    await message.reply("⛔ Too many approval requests. Please wait a bit and try again.")
                except Exception:
                    pass
                return {"status": "rate_limited", "code": None, "expected_code": None}

    req = None
    if store:
        try:
            # Update expected_code in the persisted request for out-of-band verification.
            row = await store.get_approval_request(tool_call_id=tool_call_id)
            if row:
                req = row
            now = int(time.time())
            expires_at = int((req or {}).get("expires_at") or (now + int(timeout_sec)))
            args_json = normalize_args_json(args if isinstance(args, dict) else {})
            summary = approval_summary(tool_name, args if isinstance(args, dict) else {}, risk_level, risk_score)
            await store.upsert_approval_request(
                tool_call_id=tool_call_id,
                created_at=int((req or {}).get("created_at") or now),
                expires_at=expires_at,
                actor_id=int(message.author.id),
                tool_name=tool_name,
                correlation_id=correlation_id or None,
                risk_score=int(risk_score),
                risk_level=str(risk_level),
                requires_code=bool(requires_code),
                expected_code=expected or None,
                args_hash=args_hash(args if isinstance(args, dict) else {}),
                requested_role="owner" if is_owner(bot, message.author.id) else "guest",
                args_json=args_json,
                summary=summary,
            )
            req = await store.get_approval_request(tool_call_id=tool_call_id)
        except Exception:
            req = None

    expires_at = int((req or {}).get("expires_at") or (int(time.time()) + int(timeout_sec)))
    args_json = (req or {}).get("args_json") or normalize_args_json(args if isinstance(args, dict) else {})

    # Notify owner via DM (separate channel).
    await _dm_owner_approval(
        bot=bot,
        owner_id=int(owner_id),
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        correlation_id=correlation_id,
        risk_score=int(risk_score),
        risk_level=str(risk_level),
        reasons=reasons or [],
        args_json=str(args_json),
        expected_code=expected,
        expires_at=expires_at,
    )

    # Inform the requester that approval is pending (no approve buttons in-band).
    try:
        await message.reply(f"⏸️ Approval requested from owner. approval_id=`{tool_call_id}` (expires soon).")
    except Exception:
        pass

    # Poll decision from DB until timeout/expiry.
    deadline = time.time() + max(5, int(timeout_sec))
    while time.time() < deadline:
        now = int(time.time())
        if now >= expires_at:
            if store:
                try:
                    await store.decide_approval_request(tool_call_id=tool_call_id, status="expired", decided_by="system")
                except Exception:
                    pass
            return {"status": "expired", "code": None, "expected_code": expected or None}

        if store:
            st = await store.get_approval_status(tool_call_id=tool_call_id)
            if st in {"approved", "denied"}:
                return {"status": st, "code": None, "expected_code": expected or None}
            if st in {"expired", "timeout"}:
                return {"status": st, "code": None, "expected_code": expected or None}

        await asyncio.sleep(2.0)

    return {"status": "timeout", "code": None, "expected_code": expected or None}
