import os
import json
import logging
import asyncio
import aiofiles
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Default Memory Dir
if os.name == "nt" and os.path.exists(r"L:\ORA_Memory"):
    DEFAULT_MEMORY_DIR = r"L:\ORA_Memory"
else:
    DEFAULT_MEMORY_DIR = os.path.expanduser("~/ORA_Memory")

MEMORY_DIR = os.getenv("ORA_MEMORY_DIR", DEFAULT_MEMORY_DIR)

USER_MEMORY_DIR = os.path.join(MEMORY_DIR, "users")
CHANNEL_MEMORY_DIR = os.path.join(MEMORY_DIR, "channels")

# Ensure dirs exist
for d in [MEMORY_DIR, USER_MEMORY_DIR, CHANNEL_MEMORY_DIR]:
    os.makedirs(d, exist_ok=True)

class SimpleFileLock:
    """Cross-process file lock (Migrated from Discord Bot)."""
    def __init__(self, path: str, timeout: float = 2.0):
        self.lock_path = path + ".lock"
        self.timeout = timeout
        self._fd = None

    async def __aenter__(self):
        import time
        start_time = time.time()
        while True:
            try:
                self._fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(self._fd, f"{os.getpid()}:{time.time()}".encode())
                break
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    # Stale lock check
                    try:
                        stat = os.stat(self.lock_path)
                        if time.time() - stat.st_mtime > 5.0:
                            os.remove(self.lock_path)
                            continue
                    except Exception:
                        pass
                    logger.warning(f"Failed to acquire lock: {self.lock_path}")
                    break
                await asyncio.sleep(0.05)
            except Exception:
                break
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._fd:
            os.close(self._fd)
            if os.path.exists(self.lock_path):
                try:
                    os.remove(self.lock_path)
                except: pass

class MemoryStore:
    """
    Handles atomic reading/writing of JSON memory files.
    Serves as the Data Access Layer for the Brain.
    """
    def __init__(self):
        self._io_lock = asyncio.Lock()

    def _get_user_path(self, user_id: str) -> str:
        # Note: Core uses internal UUIDs usually, but for migration compatibility
        # we might need to handle Discord IDs.
        # For now, we assume user_id is the filename ID.
        return os.path.join(USER_MEMORY_DIR, f"{user_id}.json")

    async def read_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        path = self._get_user_path(user_id)
        if not os.path.exists(path):
            return None
        
        async with SimpleFileLock(path):
            async with self._io_lock:
                try:
                    async with aiofiles.open(path, "r", encoding="utf-8") as f:
                        content = await f.read()
                        if content.strip():
                            return json.loads(content)
                except Exception as e:
                    logger.error(f"Read failed for {user_id}: {e}")
        return None

    async def save_user_profile(self, user_id: str, data: Dict[str, Any]):
        path = self._get_user_path(user_id)
        async with SimpleFileLock(path):
            temp_path = path + ".tmp"
            try:
                async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                    await f.flush()
                
                if os.path.exists(path):
                    os.replace(temp_path, path)
                else:
                    os.rename(temp_path, path)
            except Exception as e:
                logger.error(f"Save failed for {user_id}: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    async def get_or_create_profile(self, user_id: str, default_name: str = "User") -> Dict[str, Any]:
        profile = await self.read_user_profile(user_id)
        if profile:
            return profile
        
        # New Profile Template (L1-L4 structure)
        import time
        new_profile = {
            "id": user_id,
            "name": default_name,
            "created_at": time.time(),
            "last_updated": datetime.now().isoformat(),
            "layer1_session_meta": {},
            "layer2_user_memory": {"facts": [], "traits": [], "impression": "Newcomer"},
            "layer3_recent_summaries": [],
            "layer4_raw_logs": [], # Usually not stored in main profile, but kept here for schema Ref
            "traits": [], # Legacy compat
            "status": "New"
        }
        await self.save_user_profile(user_id, new_profile)
        return new_profile

# Singleton instance
memory_store = MemoryStore()
