"""
AI Repair Module
----------------
Interacts with Local LLM (RTX5090) or Cloud APIs to fix code based on error logs.
"""

import asyncio
import logging
import shutil
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

# Configuration
LOCAL_LLM_URL = "http://127.0.0.1:1234/v1/chat/completions"
# Fallback model name for local inference
LOCAL_MODEL = "local-model"


async def get_fix_from_ai(error_log: str, source_code: str, file_path: str) -> str | None:
    """
    Ask AI to fix the code given the error log.
    Returns the fixed code (full file content) or None if failed.
    """

    prompt = f"""
You are an expert Python debugger. 
The following code crashed with an error. Fix the bug.
Return ONLY the full corrected code. Do NOT wrap in markdown blocks like ```python.

FILE: {file_path}
ERROR:
{error_log}

SOURCE CODE:
{source_code}
    """

    messages = [
        {"role": "system", "content": "You are a coding assistant. Return only the fixed code."},
        {"role": "user", "content": prompt},
    ]

    # Try Local LLM (RTX5090)
    try:
        logger.info(f"Asking Local LLM ({LOCAL_LLM_URL}) for a fix...")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                LOCAL_LLM_URL,
                json={"model": LOCAL_MODEL, "messages": messages, "temperature": 0.2, "stream": False},
                timeout=60,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    # Clean markdown if present
                    if content.startswith("```python"):
                        content = content.replace("```python", "").replace("```", "")
                    elif content.startswith("```"):
                        content = content.replace("```", "")
                    return content.strip()
                else:
                    logger.warning(f"Local LLM failed with {resp.status}")
    except Exception as e:
        logger.error(f"Failed to query Local LLM: {e}")

    return None


def apply_fix_sync(sandbox_dir: Path, error_log: str) -> bool:
    """
    Synchronous wrapper to be called from launcher.
    1. Parses error log to find crashing file.
    2. Reads file.
    3. Calls AI.
    4. Writes back to sandbox.
    """
    # Simple log parsing logic to find the last python file in traceback
    # This is naive; a real implementation would parse the stack trace better.

    import re

    # Look for: File "path/to/file.py", line X, in module
    matches = list(re.finditer(r'File "([^"]+\.py)", line (\d+)', error_log))
    if not matches:
        logger.error("Could not identify failing file from logs.")
        return False

    last_match = matches[-1]
    file_path_str = last_match.group(1)

    # Resolve path relative to sandbox
    # The logs might show absolute paths or relative.
    # We need to map it to the SANDBOX_DIR.

    # If absolute path contains the project dir, replace it.
    # Current assumption: launcher running in root.

    # We need to find the relative path from the project root.
    full_path = Path(file_path_str)

    try:
        # Check if it's inside our sandbox
        rel_path = full_path.relative_to(sandbox_dir)
        target_file = sandbox_dir / rel_path
    except ValueError:
        try:
            # Maybe it was logged with the original path?
            # Start searching for the file in sandbox by name
            rel_path = Path(file_path_str).name  # super naive
            # Try to find it recursively? specific to src?
            # Let's assume standard structure: c:\Users\...\src\cogs\ora.py
            if "src" in str(full_path):
                parts = full_path.parts
                idx = parts.index("src")
                rel_path = Path(*parts[idx:])
                target_file = sandbox_dir / rel_path
            else:
                target_file = sandbox_dir / full_path.name
        except Exception:
            logger.error(f"Could not map {file_path_str} to sandbox.")
            return False

    if not target_file.exists():
        logger.error(f"Target file {target_file} does not exist in sandbox.")
        return False

    logger.info(f"Identified failing file: {target_file}")

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            source_code = f.read()

        # Call AI (using asyncio.run since we are in sync context)
        fixed_code = asyncio.run(get_fix_from_ai(error_log[-2000:], source_code, str(rel_path)))

        if fixed_code:
            # Safety: snapshot codebase before writing, so accidental deletions/garbage patches are recoverable.
            try:
                from src.utils.backup_manager import BackupManager

                bm = BackupManager(str(sandbox_dir))
                bm.create_snapshot(f"Before_AIRepair_{Path(str(rel_path)).stem}")
            except Exception as e:
                logger.warning(f"Snapshot before AI repair skipped: {e}")

            # Backup the broken file in sandbox just in case (e.g. .bak)
            shutil.copy(target_file, str(target_file) + ".bak")

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(fixed_code)
            logger.info("✅ Applied AI fix to sandbox file.")
            return True
        else:
            logger.warning("AI could not generate a fix.")
            return False

    except Exception as e:
        logger.error(f"Repair process failed: {e}")
        return False
