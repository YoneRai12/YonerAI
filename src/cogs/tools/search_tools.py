import logging
import discord
from typing import Optional

logger = logging.getLogger(__name__)

async def code_grep(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """
    Search for a pattern in the codebase using grep/ripgrep.
    Args:
        query (str): The search pattern.
        path (str): The directory or file to search in (default: ".").
        ignore_case (bool): Whether to ignore case (default: True).
    """
    if bot is None: return "❌ Bot instance missing."

    # [SECURITY GATE] Admin Only for Agentic Search
    if message.author.id != bot.config.admin_user_id:
        logger.warning(f"🚫 Unauthorized Code Explorer attempt by {message.author} (ID: {message.author.id})")
        return "⛔ Access Denied: このスキルは管理者専用です。"

    query = args.get("query")
    if not query: return "❌ Missing query."

    path = args.get("path", ".")
    ignore_case = args.get("ignore_case", True)

    cog = bot.get_cog("ORACog")
    if not cog or not hasattr(cog, "safe_shell"):
        return "❌ SafeShell not available on ORACog."

    flags = "-n -m 50"
    if ignore_case:
        flags += " -i"

    # Use rg (ripgrep) if available, fallback to grep
    cmd = f"rg {flags} {query} {path}"

    if status_manager: await status_manager.update_current(f"🔍 Grepping for '{query}'...")

    result = await cog.safe_shell.run(cmd)

    if result["exit_code"] != 0:
        if "rg: command not found" in result["stderr"]:
             # Fallback to grep
             cmd = f"grep {flags} {query} {path}"
             result = await cog.safe_shell.run(cmd)

    if result["exit_code"] != 0:
        return f"❌ Grep Failed: {result['stderr']}"

    out = result["stdout"]
    if not out:
        return f"No matches found for '{query}' in {path}."

    return f"### Grep Results for '{query}':\n```\n{out}\n```"

async def code_find(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """
    Find files in the codebase using glob-style patterns.
    Args:
        pattern (str): The filename pattern (regex).
        path (str): The directory to search in (default: ".").
    """
    if bot is None: return "❌ Bot instance missing."

    # [SECURITY GATE] Admin Only for Agentic Search
    if message.author.id != bot.config.admin_user_id:
        return "⛔ Access Denied: 管理者専用です。"

    pattern = args.get("pattern")
    if not pattern: return "❌ Missing pattern."

    path = args.get("path", ".")

    cog = bot.get_cog("ORACog")
    if not cog or not hasattr(cog, "safe_shell"):
        return "❌ SafeShell not available."

    cmd = f"find {pattern} {path} -m 100"

    if status_manager: await status_manager.update_current(f"📂 Finding files matching '{pattern}'...")

    result = await cog.safe_shell.run(cmd)

    if result["exit_code"] != 0:
        return f"❌ Find Failed: {result['stderr']}"

    out = result["stdout"]
    if not out:
        return f"No files matching '{pattern}' found in {path}."

    return f"### Found Files ({pattern}):\n```\n{out}\n```"

async def code_read(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """
    Read content of a file, optionally with line range.
    Args:
        path (str): File path.
        start (int): Start line (1-indexed).
        end (int): End line (inclusive).
    """
    if bot is None: return "❌ Bot instance missing."

    # [SECURITY GATE] Admin Only for Agentic Search
    if message.author.id != bot.config.admin_user_id:
        return "⛔ Access Denied: 管理者専用です。"

    path = args.get("path")
    if not path: return "❌ Missing path."

    start = args.get("start")
    end = args.get("end")

    cog = bot.get_cog("ORACog")
    if not cog or not hasattr(cog, "safe_shell"):
        return "❌ SafeShell not available."

    if start and end:
        cmd = f"lines -s {start} -e {end} {path}"
    elif start:
        cmd = f"lines -s {start} {path}"
    else:
        cmd = f"cat -n {path}"

    if status_manager: await status_manager.update_current(f"📖 Reading {path}...")

    result = await cog.safe_shell.run(cmd)

    if result["exit_code"] != 0:
        return f"❌ Read Failed: {result['stderr']}"

    return f"### File Content: {path}\n```\n{result['stdout']}\n```"

async def code_tree(args: dict, message: discord.Message, status_manager, bot=None) -> str:
    """
    View directory structure.
    Args:
        path (str): Root directory.
        depth (int): Max depth (default: 2).
    """
    if bot is None: return "❌ Bot instance missing."

    # [SECURITY GATE] Admin Only for Agentic Search
    if message.author.id != bot.config.admin_user_id:
        return "⛔ Access Denied: 管理者専用です。"

    path = args.get("path", ".")
    depth = args.get("depth", 2)

    cog = bot.get_cog("ORACog")
    if not cog or not hasattr(cog, "safe_shell"):
        return "❌ SafeShell not available."

    cmd = f"tree -L {depth} {path}"

    if status_manager: await status_manager.update_current(f"🌳 Mapping directory {path}...")

    result = await cog.safe_shell.run(cmd)

    if result["exit_code"] != 0:
        return f"❌ Tree Failed: {result['stderr']}"

    return f"### Directory Structure: {path}\n```\n{result['stdout']}\n```"
