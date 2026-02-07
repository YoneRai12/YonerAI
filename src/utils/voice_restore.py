from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Iterable

import discord

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw)
    except Exception:
        return default


def _restore_path(state_dir: str) -> Path:
    p = Path(state_dir) / "voice_restore.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def snapshot_voice_connections(bot: discord.Client, *, state_dir: str) -> dict[str, Any]:
    """
    Capture current voice connections so they can be restored after restart.
    """
    entries: list[dict[str, int]] = []
    for vc in list(getattr(bot, "voice_clients", []) or []):
        try:
            if not vc or not vc.is_connected():
                continue
            if not vc.guild or not vc.channel:
                continue
            entries.append({"guild_id": int(vc.guild.id), "channel_id": int(vc.channel.id)})
        except Exception:
            continue

    payload = {
        "ts": int(time.time()),
        "entries": entries,
        "version": 1,
    }
    return payload


def write_snapshot(payload: dict[str, Any], *, state_dir: str) -> None:
    path = _restore_path(state_dir)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_snapshot(*, state_dir: str) -> dict[str, Any] | None:
    path = _restore_path(state_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_snapshot(*, state_dir: str) -> None:
    path = _restore_path(state_dir)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def should_restore(payload: dict[str, Any] | None) -> tuple[bool, str]:
    if not _bool_env("ORA_VOICE_RESTORE_ON_STARTUP", default=False):
        return False, "disabled"
    if not payload:
        return False, "no_snapshot"
    ts = int(payload.get("ts") or 0)
    ttl = max(30, _int_env("ORA_VOICE_RESTORE_TTL_SEC", 300))
    age = int(time.time()) - ts
    if age < 0:
        age = 0
    if age > ttl:
        return False, f"expired(age={age}s ttl={ttl}s)"
    entries = payload.get("entries") or []
    if not isinstance(entries, list) or not entries:
        return False, "empty"
    return True, "ok"


async def restore_voice_connections(bot: discord.Client, *, state_dir: str) -> dict[str, Any]:
    """
    Best-effort reconnect to previously connected voice channels.
    """
    payload = read_snapshot(state_dir=state_dir)
    ok, reason = should_restore(payload)
    if not ok:
        return {"ok": False, "reason": reason}

    entries = payload.get("entries") or []
    restored: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for e in entries:
        try:
            guild_id = int(e.get("guild_id"))
            channel_id = int(e.get("channel_id"))
        except Exception:
            continue

        guild = bot.get_guild(guild_id)
        if not guild:
            failed.append({"guild_id": guild_id, "channel_id": channel_id, "error": "guild_not_found"})
            continue

        # Avoid duplicates (already connected).
        try:
            if guild.voice_client and guild.voice_client.is_connected():
                restored.append({"guild_id": guild_id, "channel_id": int(guild.voice_client.channel.id)})
                continue
        except Exception:
            pass

        ch = guild.get_channel(channel_id)
        if ch is None:
            try:
                ch = await guild.fetch_channel(channel_id)
            except Exception as ex:
                failed.append({"guild_id": guild_id, "channel_id": channel_id, "error": f"fetch_channel: {ex}"})
                continue

        if not isinstance(ch, (discord.VoiceChannel, discord.StageChannel)):
            failed.append({"guild_id": guild_id, "channel_id": channel_id, "error": "not_voice_channel"})
            continue

        try:
            await ch.connect(timeout=30.0, reconnect=True, self_deaf=False)
            restored.append({"guild_id": guild_id, "channel_id": channel_id})
        except Exception as ex:
            failed.append({"guild_id": guild_id, "channel_id": channel_id, "error": str(ex)})

    # Clear snapshot so we don't rejoin stale channels on later boots.
    clear_snapshot(state_dir=state_dir)

    return {"ok": True, "restored": restored, "failed": failed, "reason": reason}

