import asyncio
import logging
import os
import time
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.utils.agent_trace import trace_event
from src.utils.core_client import core_client

logger = logging.getLogger(__name__)


class SchedulerCog(commands.Cog):
    """
    Owner-only scheduled tasks runner.

    Security posture:
    - Disabled by default (ORA_SCHEDULER_ENABLED=0).
    - Runs tasks as LLM-only: available_tools=[] so Core cannot request tool dispatch.
      (We can extend later with explicit allowlists + approval gates.)
    - Stores audit trail in SQLite (scheduled_task_runs).
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._sem = asyncio.Semaphore(int(os.getenv("ORA_SCHEDULER_MAX_CONCURRENCY", "1") or "1"))

        self._enabled = (os.getenv("ORA_SCHEDULER_ENABLED", "0").strip() in {"1", "true", "yes", "on"})
        tick = int(os.getenv("ORA_SCHEDULER_TICK_SEC", "15") or "15")
        self._tick_sec = max(5, min(120, tick))

        # tasks.loop interval can't be set dynamically after decoration, so we start our own loop.
        self._task: Optional[asyncio.Task] = None

    async def cog_load(self) -> None:
        if not self._enabled:
            logger.info("Scheduler disabled (ORA_SCHEDULER_ENABLED=0).")
            return
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started (tick=%ss, concurrency=%s).", self._tick_sec, self._sem._value)

    async def cog_unload(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _run_loop(self) -> None:
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error("Scheduler tick failed: %s", e, exc_info=True)
            await asyncio.sleep(self._tick_sec)

    async def _tick(self) -> None:
        store = getattr(self.bot, "store", None)
        if store is None:
            return
        now_ts = int(time.time())
        due = await store.get_due_scheduled_tasks(now_ts=now_ts, limit=5)
        if not due:
            return

        for task in due:
            # claim first; if claim fails, someone else took it or it moved.
            claimed = await store.claim_scheduled_task(task_id=task["id"], now_ts=now_ts)
            if not claimed:
                continue
            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: dict) -> None:
        async with self._sem:
            store = getattr(self.bot, "store", None)
            if store is None:
                return

            task_id = int(task["id"])
            owner_id = int(task["owner_id"])
            channel_id = int(task["channel_id"])
            guild_id = task.get("guild_id")
            prompt = str(task.get("prompt") or "").strip()
            model_pref = task.get("model_pref")

            started_at = int(time.time())
            run_row_id = await store.insert_task_run(task_id=task_id, started_at=started_at, status="running")

            correlation_id = f"sched:{task_id}:{started_at}"
            trace_event("scheduler.task_start", correlation_id=correlation_id, task_id=str(task_id), channel_id=str(channel_id))

            try:
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    channel = await self.bot.fetch_channel(channel_id)
                if not channel or not hasattr(channel, "send"):
                    raise RuntimeError("target channel not found or not sendable")

                # Bind memory to the channel (so summaries can be contextual, but still "LLM-only").
                kind = "channel"
                ext_id = f"{guild_id}:{channel_id}" if guild_id else f"dm:{owner_id}"
                context_binding = {"provider": "discord", "kind": kind, "external_id": ext_id}

                client_context = {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "guild_id": str(guild_id) if guild_id else None,
                    "channel_id": str(channel_id),
                    "is_admin": True,
                    "scheduled_task_id": str(task_id),
                }

                # LLM-only contract for safety/reproducibility.
                safe_prompt = (
                    "[SCHEDULED TASK]\n"
                    "Rules:\n"
                    "- This is an automated run. Do not request tool calls.\n"
                    "- Output concise Japanese.\n\n"
                    f"{prompt}"
                )

                resp = await core_client.send_message(
                    content=safe_prompt,
                    provider_id=str(owner_id),
                    display_name="ORA Scheduler",
                    conversation_id=None,
                    idempotency_key=f"scheduler:{task_id}:{started_at}",
                    context_binding=context_binding,
                    attachments=[],
                    stream=False,
                    client_context=client_context,
                    available_tools=[],  # critical: no tool dispatch
                    source="scheduler",
                    llm_preference=model_pref,
                    correlation_id=correlation_id,
                )
                if "error" in resp:
                    raise RuntimeError(str(resp.get("error")))
                run_id = resp.get("run_id")
                if not run_id:
                    raise RuntimeError("missing run_id from core")

                final = await core_client.get_final_response(run_id, timeout=300)
                if not final:
                    raise RuntimeError("empty final response")

                # Post result to channel (no attachments).
                await channel.send(f"⏰ **Scheduled Task #{task_id}**\n{final.strip()}")

                finished_at = int(time.time())
                await store.finish_task_run(
                    run_row_id=run_row_id,
                    finished_at=finished_at,
                    status="ok",
                    core_run_id=str(run_id),
                    output=final,
                )
                trace_event("scheduler.task_done", correlation_id=correlation_id, task_id=str(task_id), status="ok")

            except Exception as e:
                finished_at = int(time.time())
                await store.finish_task_run(
                    run_row_id=run_row_id,
                    finished_at=finished_at,
                    status="failed",
                    error=str(e),
                )
                trace_event("scheduler.task_done", correlation_id=correlation_id, task_id=str(task_id), status="failed", error=str(e))
                logger.error("Scheduled task %s failed: %s", task_id, e, exc_info=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SchedulerCog(bot))

