import collections
import json
import logging
import os
import time

from discord.ext import commands, tasks


# Memory Handler for Log Snippets
class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=20):
        super().__init__()
        self.capacity = capacity
        self.buffer = collections.deque(maxlen=capacity)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.buffer.append(msg)
        except Exception:
            self.handleError(record)


# Attach handler globally (singleton pattern)
memory_handler = MemoryLogHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
memory_handler.setFormatter(formatter)
logging.getLogger().addHandler(memory_handler)


class HeartbeatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.heartbeat_file = os.path.join("data", "heartbeat.json")
        self.version = "v4.5 (Beta)"  # Should technically load from config or bot var
        self.watcher_expected = False
        self.watcher_ready = False

        # Ensure data dir exists
        os.makedirs("data", exist_ok=True)

        self.heartbeat_task.start()

    def cog_unload(self):
        self.heartbeat_task.cancel()

    @tasks.loop(seconds=5.0)
    async def heartbeat_task(self):
        try:
            # Gather Data
            current_status = "healthy" if self.bot.is_ready() else "booting"

            # Read existing to preserve flags if needed (though we own the write)
            # Actually, Watcher writes 'watcher_ready', Healer writes 'watcher_expected'.
            # We must READ before WRITE to strictly preserve external updates.
            # BUT, JSON read/write race condition is possible.
            # Given the roles:
            # Healer (Main Process) sets 'watcher_expected'.
            # Watcher (External) sets 'watcher_ready'.
            # Heartbeat (Main Process) updates 'timestamp' and 'logs'.

            # Since Healer and Heartbeat are same process, no race there.
            # Watcher is external.
            # To avoid overwriting Watcher's write, we should read first.

            existing_data = {}
            if os.path.exists(self.heartbeat_file):
                try:
                    with open(self.heartbeat_file, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                except:
                    pass

            # Update local state from file (if Watcher wrote to it)
            if "watcher_ready" in existing_data:
                self.watcher_ready = existing_data["watcher_ready"]

            # Merge Data
            data = {
                "timestamp": time.time(),
                "status": current_status,
                "version": self.version,
                "watcher_expected": self.watcher_expected,  # We own this
                "watcher_ready": self.watcher_ready,  # We reflect this
                "active_voice_channels": [
                    vc.channel.id for vc in self.bot.voice_clients if vc.is_connected()
                ],  # For Shadow Bot
                "last_log_snippet": list(memory_handler.buffer),
            }

            # Write safely
            # On Windows, atomic write is hard, but simple write is usually fine for this scale.
            # We use a temp file and rename to minimize read/write collision window.
            temp_file = self.heartbeat_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            os.replace(temp_file, self.heartbeat_file)

        except Exception as e:
            logging.getLogger("Heartbeat").error(f"Heartbeat failed: {e}")

    @heartbeat_task.before_loop
    async def before_heartbeat(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(HeartbeatCog(bot))
