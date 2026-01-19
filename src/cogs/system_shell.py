from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.shell import ReadOnlyShellExecutor, ShellPolicy

logger = logging.getLogger(__name__)


class SystemShell(commands.Cog):
    """Safe, read-only system shell for debugging and inspection."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Determine root directory (assuming bot.py is in src or root)
        # We want the project root.
        # current file is src/cogs/system_shell.py. parent=cogs, parent=src, parent=root
        root_dir = Path(__file__).resolve().parent.parent.parent
        self.policy = ShellPolicy(root_dir=root_dir)
        self.executor = ReadOnlyShellExecutor(self.policy)

    @app_commands.command(name="shell", description="Execute safe read-only commands (ls, cat, grep, etc.)")
    @app_commands.describe(command="The command string to execute (e.g. 'ls -la src')")
    @app_commands.checks.has_permissions(administrator=True)
    async def shell_cmd(self, interaction: discord.Interaction, command: str):
        """Execute a safe shell command."""
        await interaction.response.defer()

        # Validate
        error = self.executor.validate(command)
        if error:
            await interaction.followup.send(f"🚫 **Access Denied**: {error}", ephemeral=True)
            return

        # Execute
        try:
            result = self.executor.run(command)
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            exit_code = result.get("outcome", {}).get("exit_code", 0)

            if stderr:
                output = f"⚠️ **Stderr**:\n```bash\n{stderr}\n```\n"
                if stdout:
                    output += f"**Stdout**:\n```bash\n{stdout}\n```"
            else:
                if not stdout:
                    stdout = "(No output)"
                output = f"**Exit Code**: {exit_code}\n```bash\n{stdout}\n```"

            if len(output) > 2000:
                # Truncate for Discord
                output = output[:1990] + "\n... (truncated)"

            await interaction.followup.send(output)

        except Exception as e:
            logger.exception("Shell execution failed")
            await interaction.followup.send(f"💥 **Internal Error**: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SystemShell(bot))
