import time
from typing import Optional

import discord


def _fmt_ts(ts: Optional[int]) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))
    except Exception:
        return str(ts)


async def schedule_task(args: dict, message: discord.Message, status_manager, bot=None):
    """
    Owner-only: create a periodic scheduled task (LLM-only).
    """
    if not bot:
        return "❌ Internal error: bot missing."

    prompt = (args.get("prompt") or "").strip()
    if not prompt:
        return "❌ Missing `prompt`."

    interval_sec = int(args.get("interval_sec") or 0)
    if interval_sec < 30:
        return "❌ interval_sec must be >= 30."

    channel_id = int(args.get("channel_id") or message.channel.id)
    model_pref = (args.get("model") or "").strip() or None
    enabled = bool(args.get("enabled", True))

    store = getattr(bot, "store", None)
    if store is None:
        return "❌ Store not initialized."

    task_id = await store.create_scheduled_task(
        owner_id=message.author.id,
        guild_id=message.guild.id if message.guild else None,
        channel_id=channel_id,
        prompt=prompt,
        interval_sec=interval_sec,
        model_pref=model_pref,
        enabled=enabled,
    )
    return f"✅ Scheduled task created: #{task_id} (interval={interval_sec}s, enabled={enabled}, channel_id={channel_id})"


async def list_scheduled_tasks(args: dict, message: discord.Message, status_manager, bot=None):
    if not bot:
        return "❌ Internal error: bot missing."
    store = getattr(bot, "store", None)
    if store is None:
        return "❌ Store not initialized."

    items = await store.list_scheduled_tasks(owner_id=message.author.id)
    if not items:
        return "No scheduled tasks."

    lines = ["📅 **Scheduled Tasks**"]
    for t in items[:20]:
        p = (t.get("prompt") or "").replace("\n", " ").strip()
        if len(p) > 80:
            p = p[:77] + "..."
        lines.append(
            f"- #{t['id']} enabled={t['enabled']} interval={t['interval_sec']}s next={_fmt_ts(t['next_run_at'])} ch={t['channel_id']} :: {p}"
        )
    return "\n".join(lines)


async def delete_scheduled_task(args: dict, message: discord.Message, status_manager, bot=None):
    if not bot:
        return "❌ Internal error: bot missing."
    task_id = int(args.get("task_id") or 0)
    if task_id <= 0:
        return "❌ Missing `task_id`."
    store = getattr(bot, "store", None)
    if store is None:
        return "❌ Store not initialized."
    ok = await store.delete_scheduled_task(owner_id=message.author.id, task_id=task_id)
    return "✅ Deleted." if ok else "❌ Not found."


async def toggle_scheduled_task(args: dict, message: discord.Message, status_manager, bot=None):
    if not bot:
        return "❌ Internal error: bot missing."
    task_id = int(args.get("task_id") or 0)
    enabled = bool(args.get("enabled", True))
    if task_id <= 0:
        return "❌ Missing `task_id`."
    store = getattr(bot, "store", None)
    if store is None:
        return "❌ Store not initialized."
    ok = await store.set_scheduled_task_enabled(owner_id=message.author.id, task_id=task_id, enabled=enabled)
    return f"✅ Updated: enabled={enabled}" if ok else "❌ Not found."

