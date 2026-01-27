
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import aiofiles

logger = logging.getLogger(__name__)

class MarkdownMemory:
    """
    Manages persistent memory storage in Markdown format, 
    inspired by Obsidian/Clawdbot architecture.
    """
    def __init__(self, root_dir: str = "data/memories"):
        self.root_dir = root_dir
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir, exist_ok=True)

    def _get_filename(self, session_id: str) -> str:
        """Generates a filename based on date and session ID."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        # Sanitize session_id just in case
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ('-', '_'))
        return os.path.join(self.root_dir, f"{date_str}-{safe_id}.md")

    async def save_conversation(self, session_id: str, messages: List[Dict[str, Any]], metadata: Dict[str, Any] = None):
        """
        Saves a conversation to a Markdown file.
        If file exists, appends new messages (logic could vary).
        For now, we overwrite or create fresh daily logs.
        """
        filename = self._get_filename(session_id)
        
        # Format content
        content = []
        
        # Frontmatter
        content.append("---")
        content.append(f"date: {datetime.now().isoformat()}")
        content.append(f"session_id: {session_id}")
        if metadata:
            for k, v in metadata.items():
                content.append(f"{k}: {v}")
        content.append("---")
        content.append("")
        content.append(f"# Session Log: {session_id}")
        content.append("")
        
        for msg in messages:
            role = msg.get("role", "unknown")
            text = msg.get("content", "")
            timestamp = msg.get("timestamp", datetime.now().strftime("%H:%M:%S"))
            
            icon = "👤" if role == "user" else "🤖"
            content.append(f"### {icon} {role.capitalize()} ({timestamp})")
            content.append(text)
            content.append("")
            
        async with aiofiles.open(filename, "w", encoding="utf-8") as f:
            await f.write("\n".join(content))
            
        logger.info(f"Saved persistent memory to {filename}")

    async def append_message(self, session_id: str, role: str, content: str):
        """Appends a single message to the active session file."""
        filename = self._get_filename(session_id)
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = "👤" if role == "user" else "🤖"
        
        block = f"\n### {icon} {role.capitalize()} ({timestamp})\n{content}\n"
        
        async with aiofiles.open(filename, "a", encoding="utf-8") as f:
            await f.write(block)
