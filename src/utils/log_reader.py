import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LocalLogReader:
    """
    Reads chat history from local rotation logs (L:/ORA_Logs/guilds/{guild_id}.log)
    to bypass Discord API Rate Limits.
    """

    LOG_DIR = r"L:\ORA_Logs\guilds"

    # Regex to parse standard log format:
    # 2025-12-28 14:44:40,395 INFO guild_123 Message from User (123): Hello
    # We need to adapt to what GuildLogger actually writes.
    # It writes: logger.info(f"{message.author.name} ({message.author.id}): {message.content}")
    # So the line is: TIMESTAMP INFO guild_ID User (ID): Content
    # Let's target the message part.

    def __init__(self):
        self.log_pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*? INFO guild_\d+ (.*?)\s\((\d+)\):\s(.*)$"
        )
        # 2024-01-01T12:00:00.000 INFO guild_123 User (123): Content

    def get_recent_messages(
        self, guild_id: int, limit: int = 50, user_id: Optional[int] = None, is_public: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """
        Parses local logs to find recent messages. Supports privacy scoping.
        """
        # 1. Determine log files to read
        log_files = []
        if is_public is True:
            log_files.append(os.path.join(self.LOG_DIR, f"{guild_id}_public.log"))
        elif is_public is False:
            log_files.append(os.path.join(self.LOG_DIR, f"{guild_id}_private.log"))
        else:
            # Both (legacy or combined)
            log_files.append(os.path.join(self.LOG_DIR, f"{guild_id}_public.log"))
            log_files.append(os.path.join(self.LOG_DIR, f"{guild_id}_private.log"))
            log_files.append(os.path.join(self.LOG_DIR, f"{guild_id}_archive.log"))  # Legacy fallback

        log_files.append(os.path.join(self.LOG_DIR, f"{guild_id}.log"))  # Active log

        all_lines = []
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        # Read everything. For large logs, we might want to tail it instead.
                        lines = f.readlines()
                        all_lines.extend(lines)
                except:
                    pass

        messages = []
        try:
            # Process in reverse to get most recent
            for line in reversed(all_lines):
                if len(messages) >= limit:
                    break

                # Format: TIMESTAMP INFO guild_ID Message: User (ID): Content | Attachments: N
                parts = line.split(" ", 3)
                if len(parts) < 4:
                    continue

                msg_content = parts[3].strip()

                # Regex for archived format: Message: User#1234 (12345): Content | Attachments: 0
                match = re.search(r"Message: (.*?) \((\d+)\): (.*?) \| Attachments: \d+$", msg_content, re.DOTALL)
                if not match:
                    # Fallback for standard logger or missing attachments part
                    # Expected: Message: User (12345): Content
                    match = re.search(r"Message: (.*?) \((\d+)\): (.*)$", msg_content, re.DOTALL)

                if match:
                    author_name = match.group(1)
                    author_id = int(match.group(2))
                    content = match.group(3)

                    if user_id and author_id != user_id:
                        continue

                    msg_obj = {
                        "author_name": author_name,
                        "author_id": author_id,
                        "content": content,
                        "timestamp": parts[0],
                    }
                    messages.append(msg_obj)

            logger.debug(f"LocalLogReader: Found {len(messages)} messages for {user_id} in {guild_id}.")
            return messages

        except Exception as e:
            logger.error(f"Failed to read local log for {guild_id}: {e}")
            return []
