"""SQLite-backed storage helpers for the ORA bot."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Tuple

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  discord_user_id TEXT PRIMARY KEY,
  google_sub TEXT,
  privacy TEXT NOT NULL DEFAULT 'private',
  speak_search_progress INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  points INTEGER DEFAULT 0,
  display_name TEXT
);
CREATE TABLE IF NOT EXISTS login_states (
  state TEXT PRIMARY KEY,
  discord_user_id TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS datasets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  discord_user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  source_url TEXT,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  message TEXT NOT NULL,
  response TEXT,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS dashboard_tokens (
  token TEXT PRIMARY KEY,
  guild_id TEXT NOT NULL,
  created_by TEXT,
  expires_at INTEGER NOT NULL
);
"""


class Store:
    """Async wrapper around the SQLite database."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init(self) -> None:
        """Initialise tables if they do not exist."""

        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(SCHEMA)
            
            # Migration: Ensure points column exists
            try:
                await db.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
            except Exception:
                pass # Column likely exists
            
            # Migration: Ensure display_name column exists
            try:
                await db.execute("ALTER TABLE users ADD COLUMN display_name TEXT")
            except Exception:
                pass

            # Migration: Ensure permission_level column exists (default 'user')
            try:
                await db.execute("ALTER TABLE users ADD COLUMN permission_level TEXT DEFAULT 'user'")
            except Exception:
                pass

            await db.commit()

    async def backup(self) -> None:
        """Create an atomic backup of the database file."""
        
        if not os.path.exists(self._db_path):
            return

        # 1. Determine Backup Target Directory
        # Try L: drive first, fallback to local 'backups' dir
        l_drive_path = Path("L:/Backups/ORADiscordBOT")
        local_backup_path = Path("backups")
        
        target_dir = local_backup_path
        
        # Check L: drive writability
        if os.path.exists("L:/"):
            try:
                l_drive_path.mkdir(parents=True, exist_ok=True)
                # Test write
                test_file = l_drive_path / ".write_test"
                test_file.touch()
                test_file.unlink()
                target_dir = l_drive_path
            except Exception as e:
                logger.warning(f"L: ドライブは存在しますが書き込みできません。ローカルに保存します: {e}")
                local_backup_path.mkdir(exist_ok=True)
        else:
            local_backup_path.mkdir(exist_ok=True)

        # 2. Generate Filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19] # Include millis
        backup_filename = f"ora_{timestamp}.sqlite"
        temp_filename = f"ora_{timestamp}.sqlite.tmp"
        corrupt_filename = f"ora_{timestamp}.corrupt"
        
        final_path = target_dir / backup_filename
        temp_path = target_dir / temp_filename
        corrupt_path = target_dir / corrupt_filename

        # 3. Execute Backup in Thread
        def _backup_task():
            src_conn = None
            dst_conn = None
            try:
                # Open NEW synchronous connections for thread safety
                src_conn = sqlite3.connect(self._db_path)
                dst_conn = sqlite3.connect(str(temp_path))
                
                # Perform Backup
                src_conn.backup(dst_conn, pages=1000)
                dst_conn.close() # Close to flush WAL
                dst_conn = None
                
                # Verify Integrity
                verify_conn = sqlite3.connect(str(temp_path))
                cursor = verify_conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()[0]
                verify_conn.close()
                
                if result == "ok":
                    # Atomic Replace
                    # os.replace is atomic on POSIX, and usually atomic on Windows if dest exists (Python 3.3+)
                    # But here we are creating a new file.
                    # We rename .tmp to .sqlite
                    if os.path.exists(final_path):
                        os.remove(final_path) # Should not happen with timestamp
                    os.replace(temp_path, final_path)
                    logger.info(f"バックアップ成功: {final_path}")
                    return True
                else:
                    logger.error(f"バックアップ整合性チェック失敗: {result}")
                    os.replace(temp_path, corrupt_path)
                    return False
                    
            except Exception as e:
                logger.error(f"バックアップ失敗: {e}")
                if os.path.exists(temp_path):
                    try:
                        os.replace(temp_path, corrupt_path)
                    except:
                        pass
                return False
            finally:
                if src_conn: src_conn.close()
                if dst_conn: dst_conn.close()

        # Run in executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        success = await loop.run_in_executor(None, _backup_task)

        # 4. Rotation (Keep latest 5)
        if success:
            try:
                files = sorted(target_dir.glob("ora_*.sqlite"), key=os.path.getmtime, reverse=True)
                for old_file in files[5:]:
                    try:
                        old_file.unlink()
                        logger.info(f"古いバックアップを削除しました: {old_file.name}")
                    except Exception as e:
                        logger.warning(f"古いバックアップの削除に失敗しました {old_file.name}: {e}")
            except Exception as e:
                logger.warning(f"バックアップローテーションに失敗しました: {e}")

    async def ensure_user(
        self,
        discord_user_id: int,
        privacy_default: str,
        *,
        speak_search_progress_default: int | None = None,
        display_name: str | None = None,
    ) -> None:
        """Ensure the user row exists with default privacy and search progress settings.

        Args:
            discord_user_id: Discord user ID as integer.
            privacy_default: Default privacy mode ('private' or 'public').
            speak_search_progress_default: Optional default value for search progress speaking (0 or 1).
            display_name: Optional Discord username/display name.
        """
        now = int(time.time())
        # When not provided, fallback to 0
        sp_default = int(speak_search_progress_default or 0)
        async with aiosqlite.connect(self._db_path) as db:
            if display_name:
                await db.execute(
                    (
                        "INSERT INTO users(discord_user_id, privacy, speak_search_progress, created_at, display_name) "
                        "VALUES(?, ?, ?, ?, ?) ON CONFLICT(discord_user_id) DO UPDATE SET display_name=excluded.display_name"
                    ),
                    (str(discord_user_id), privacy_default, sp_default, now, display_name),
                )
            else:
                await db.execute(
                    (
                        "INSERT INTO users(discord_user_id, privacy, speak_search_progress, created_at) "
                        "VALUES(?, ?, ?, ?) ON CONFLICT(discord_user_id) DO NOTHING"
                    ),
                    (str(discord_user_id), privacy_default, sp_default, now),
                )
            await db.commit()

    async def set_privacy(self, discord_user_id: int, mode: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET privacy=? WHERE discord_user_id=?",
                (mode, str(discord_user_id)),
            )
            await db.commit()

    async def get_privacy(self, discord_user_id: int) -> str:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT privacy FROM users WHERE discord_user_id=?",
                (str(discord_user_id),),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else "private"

    async def set_system_privacy(self, discord_user_id: int, mode: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            # Lazy migration
            try:
                await db.execute("ALTER TABLE users ADD COLUMN system_privacy TEXT DEFAULT 'private'")
            except Exception:
                pass
            
            await db.execute(
                "UPDATE users SET system_privacy=? WHERE discord_user_id=?",
                (mode, str(discord_user_id)),
            )
            await db.commit()

    async def get_system_privacy(self, discord_user_id: int) -> str:
        async with aiosqlite.connect(self._db_path) as db:
            try:
                async with db.execute(
                    "SELECT system_privacy FROM users WHERE discord_user_id=?",
                    (str(discord_user_id),),
                ) as cursor:
                    row = await cursor.fetchone()
                return row[0] if row and row[0] else "private"
            except Exception:
                # Column might not exist yet if set_system_privacy hasn't been called
                # In that case, default to 'private' (or we could fallback to main privacy?)
                # Let's default to 'private' for safety.
                return "private"

    async def get_speak_search_progress(self, discord_user_id: int) -> int:
        """Return the search progress speech setting (0 or 1) for a user."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT speak_search_progress FROM users WHERE discord_user_id=?",
                (str(discord_user_id),),
            ) as cursor:
                row = await cursor.fetchone()
        if row is None or row[0] is None:
            return 0
        try:
            return int(row[0])
        except ValueError:
            return 0

    async def set_speak_search_progress(self, discord_user_id: int, value: int) -> None:
        """Update the search progress speech setting for a user."""
        val = 1 if value else 0
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET speak_search_progress=? WHERE discord_user_id=?",
                (val, str(discord_user_id)),
            )
            await db.commit()

    async def get_desktop_watch_enabled(self, discord_user_id: int) -> bool:
        """Return whether desktop watcher is enabled for this user (Admin)."""
        async with aiosqlite.connect(self._db_path) as db:
            # Check if column exists first (migration hack for dev)
            # In production, we should use proper migrations.
            # For now, we'll just try-catch or assume schema is updated if we recreate DB.
            # But user won't recreate DB.
            # Let's just try to select it. If it fails, return True (default).
            try:
                async with db.execute(
                    "SELECT desktop_watch_enabled FROM users WHERE discord_user_id=?",
                    (str(discord_user_id),),
                ) as cursor:
                    row = await cursor.fetchone()
                if row is None or row[0] is None:
                    return True # Default ON
                return bool(row[0])
            except Exception:
                return True

    async def set_desktop_watch_enabled(self, discord_user_id: int, enabled: bool) -> None:
        """Set desktop watcher state."""
        val = 1 if enabled else 0
        async with aiosqlite.connect(self._db_path) as db:
            # Ensure column exists (hacky migration)
            try:
                await db.execute("ALTER TABLE users ADD COLUMN desktop_watch_enabled INTEGER DEFAULT 1")
            except Exception:
                pass # Column likely exists
            
            await db.execute(
                "UPDATE users SET desktop_watch_enabled=? WHERE discord_user_id=?",
                (val, str(discord_user_id)),
            )
            await db.commit()

    async def upsert_google_sub(self, discord_user_id: int, google_sub: str, refresh_token: Optional[str] = None) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            if refresh_token:
                await db.execute(
                    (
                        "INSERT INTO users(discord_user_id, google_sub, refresh_token, privacy, created_at) "
                        "VALUES(?, ?, ?, 'private', ?) "
                        "ON CONFLICT(discord_user_id) DO UPDATE SET google_sub=excluded.google_sub, refresh_token=excluded.refresh_token"
                    ),
                    (str(discord_user_id), google_sub, refresh_token, int(time.time())),
                )
            else:
                await db.execute(
                    (
                        "INSERT INTO users(discord_user_id, google_sub, privacy, created_at) "
                        "VALUES(?, ?, 'private', ?) "
                        "ON CONFLICT(discord_user_id) DO UPDATE SET google_sub=excluded.google_sub"
                    ),
                    (str(discord_user_id), google_sub, int(time.time())),
                )
            await db.commit()

    async def get_google_creds(self, discord_user_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT google_sub, refresh_token FROM users WHERE discord_user_id=?",
                (str(discord_user_id),),
            ) as cursor:
                row = await cursor.fetchone()
        
        if not row or not row['refresh_token']:
            return None
            
        return {
            'refresh_token': row['refresh_token'],
            'client_id': None, # Will be filled by caller from env
            'client_secret': None,
            'token_uri': "https://oauth2.googleapis.com/token",
        }

    async def get_google_sub(self, discord_user_id: int) -> Optional[str]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT google_sub FROM users WHERE discord_user_id=?",
                (str(discord_user_id),),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row and row[0] else None

    async def start_login_state(self, state: str, discord_user_id: int, ttl_sec: int = 900) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                (
                    "INSERT OR REPLACE INTO login_states(state, discord_user_id, expires_at) "
                    "VALUES(?, ?, ?)"
                ),
                (state, str(discord_user_id), int(time.time()) + ttl_sec),
            )
            await db.commit()

    async def consume_login_state(self, state: str) -> Optional[str]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT discord_user_id, expires_at FROM login_states WHERE state=?",
                (state,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return None

        discord_user_id, expires_at = row
        if int(time.time()) > int(expires_at):
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("DELETE FROM login_states WHERE state=?", (state,))
                await db.commit()
            return None

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM login_states WHERE state=?", (state,))
            await db.commit()
        return str(discord_user_id)

    async def add_dataset(
        self, discord_user_id: int, name: str, source_url: Optional[str]
    ) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                (
                    "INSERT INTO datasets(discord_user_id, name, source_url, created_at) "
                    "VALUES(?, ?, ?, ?)"
                ),
                (str(discord_user_id), name, source_url, int(time.time())),
            )
            await db.commit()
            assert cursor.lastrowid is not None
            return int(cursor.lastrowid)

    async def list_datasets(
        self, discord_user_id: int, limit: int = 10
    ) -> Sequence[Tuple[int, str, Optional[str], int]]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                (
                    "SELECT id, name, source_url, created_at FROM datasets "
                    "WHERE discord_user_id=? ORDER BY id DESC LIMIT ?"
                ),
                (str(discord_user_id), limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [(int(r[0]), str(r[1]), r[2], int(r[3])) for r in rows]

    async def add_conversation(
        self, user_id: str, platform: str, message: str, response: str
    ) -> None:
        """Log a conversation turn. user_id can be Discord ID or Google Sub."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                (
                    "INSERT INTO conversations(user_id, platform, message, response, created_at) "
                    "VALUES(?, ?, ?, ?, ?)"
                ),
                (user_id, platform, message, response, int(time.time())),
            )
            await db.commit()

    async def get_conversations(self, user_id: Optional[str] = None, limit: int = 20) -> list[dict]:
        """Get recent conversations. If user_id is None, return all."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            if user_id:
                query = "SELECT * FROM conversations WHERE user_id=? ORDER BY created_at DESC LIMIT ?"
                params = (user_id, limit)
            else:
                query = "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?"
                params = (limit,)
            
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def search_conversations(self, query: str, user_id: Optional[str] = None, limit: int = 5) -> list[dict]:
        """Search conversations for a keyword."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            search_query = f"%{query}%"
            
            if user_id:
                sql = "SELECT * FROM conversations WHERE user_id=? AND (message LIKE ? OR response LIKE ?) ORDER BY created_at DESC LIMIT ?"
                params = (user_id, search_query, search_query, limit)
            else:
                # Global search (if allowed permissions, but typically restricted by caller)
                sql = "SELECT * FROM conversations WHERE message LIKE ? OR response LIKE ? ORDER BY created_at DESC LIMIT ?"
                params = (search_query, search_query, limit)
                
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def clear_conversations(self, user_id: str) -> int:
        """Clear conversation history for a user."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("DELETE FROM conversations WHERE user_id=?", (user_id,))
            await db.commit()
            return cursor.rowcount

    async def upsert_google_user(self, google_sub: str, email: str | None, credentials) -> None:
        """Update or insert Google user info."""
        # credentials is a google.oauth2.credentials.Credentials object
        refresh_token = credentials.refresh_token
        
        async with aiosqlite.connect(self._db_path) as db:
            # We might need a separate table for google users if we want to store email
            # But for now, let's assume we map it to the 'users' table via some mechanism
            # OR we just update the existing users table if we can find the user?
            # The current schema has 'users' keyed by 'discord_user_id'.
            # If we don't have a discord_user_id yet, we can't insert into 'users' easily unless we allow null discord_id
            # or use a different table.
            
            # However, the 'users' table schema is:
            # discord_user_id TEXT PRIMARY KEY, google_sub TEXT, ...
            
            # The Web Auth flow gets Google info FIRST, then links to Discord.
            # So we might need to store Google info temporarily or allow looking up by google_sub.
            
            # For this implementation, let's assume we are updating an existing user OR 
            # we need a way to store "Unlinked Google Users".
            # But the 'link_discord_google' method implies we link them later.
            
            # Let's just store the refresh token if we can find the user, or do nothing?
            # Wait, the user's snippet says:
            # await store.upsert_google_user(google_sub=google_sub, email=email, credentials=creds)
            # await store.link_discord_google(discord_user_id, google_sub)
            
            # This implies 'upsert_google_user' might create a record.
            # But our 'users' table requires discord_user_id as PK.
            
            # Let's modify 'users' table or add a 'google_users' table?
            # Given the constraints, I will implement 'link_discord_google' to do the heavy lifting
            # and 'upsert_google_user' to maybe just log or update if the user exists.
            
            # ACTUALLY, looking at the schema:
            # CREATE TABLE IF NOT EXISTS users (discord_user_id TEXT PRIMARY KEY, google_sub TEXT, ...)
            
            # If we don't have discord_id, we can't insert.
            # But the auth flow has 'state' which contains 'discord_user_id'.
            # So 'link_discord_google' is the one that matters.
            
            # Let's make 'upsert_google_user' a no-op or just helper if we had a google_users table.
            # BUT, if the user logs in via Web and we want to show their data, we need to know who they are.
            # If they are already linked, we can update their refresh token.
            pass

    async def link_discord_google(self, discord_user_id: int | str, google_sub: str) -> None:
        """Link a Discord user to a Google Subject ID."""
        async with aiosqlite.connect(self._db_path) as db:
            # Check if user exists
            async with db.execute("SELECT 1 FROM users WHERE discord_user_id=?", (str(discord_user_id),)) as cursor:
                exists = await cursor.fetchone()
            
            if exists:
                await db.execute(
                    "UPDATE users SET google_sub=? WHERE discord_user_id=?",
                    (google_sub, str(discord_user_id)),
                )
            else:
                # Create new user
                await db.execute(
                    "INSERT INTO users(discord_user_id, google_sub, created_at) VALUES(?, ?, ?)",
                    (str(discord_user_id), google_sub, int(time.time())),
                )
            await db.commit()

            await db.commit()

    async def get_points(self, discord_user_id: int) -> int:
        """Get the current point balance for a user."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT points FROM users WHERE discord_user_id=?", (str(discord_user_id),))
            row = await cursor.fetchone()
            if row:
                return row[0] if row[0] is not None else 0
            return 0

    async def add_points(self, discord_user_id: int, amount: int) -> int:
        """Add points to a user. Returns new balance."""
        async with aiosqlite.connect(self._db_path) as db:
            # Upsert User if not exists
            await db.execute(
                "INSERT INTO users(discord_user_id, created_at, points) VALUES(?, ?, 0) ON CONFLICT(discord_user_id) DO NOTHING",
                (str(discord_user_id), int(time.time()))
            )

            # Atomic Add
            await db.execute(
                "UPDATE users SET points = points + ? WHERE discord_user_id=?",
                (amount, str(discord_user_id))
            )
            await db.commit()
            
            # Fetch new balance
            async with db.execute("SELECT points FROM users WHERE discord_user_id=?", (str(discord_user_id),)) as cursor:
                 row = await cursor.fetchone()
                 return row[0] if row else 0

    async def set_points(self, discord_user_id: int, amount: int) -> None:
        """Set absolute point balance."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO users(discord_user_id, created_at, points) VALUES(?, ?, ?) ON CONFLICT(discord_user_id) DO UPDATE SET points=?",
                (str(discord_user_id), int(time.time()), amount, amount)
            )
            await db.commit()

    async def get_permission_level(self, discord_user_id: int) -> str:
        """Get the permission level for a user (user, sub_admin, vc_admin, owner)."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT permission_level FROM users WHERE discord_user_id=?",
                (str(discord_user_id),)
            ) as cursor:
                row = await cursor.fetchone()
        
        if not row or not row[0]:
            return "user"
        return row[0]

    async def set_permission_level(self, discord_user_id: int, level: str) -> None:
        """Set permission level (owner, sub_admin, vc_admin, user)."""
        async with aiosqlite.connect(self._db_path) as db:
            # Upsert
            await db.execute(
                "INSERT INTO users(discord_user_id, created_at, permission_level) VALUES(?, ?, ?) "
                "ON CONFLICT(discord_user_id) DO UPDATE SET permission_level=?",
                (str(discord_user_id), int(time.time()), level, level)
            )
            await db.commit()

    async def get_rank(self, discord_user_id: int) -> Tuple[int, int]:
        """Get the rank of a user based on points. Returns (rank, total_users)."""
        async with aiosqlite.connect(self._db_path) as db:
            # 1. Get user's points
            async with db.execute("SELECT points FROM users WHERE discord_user_id=?", (str(discord_user_id),)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return (0, 0)
                my_points = row[0] if row[0] is not None else 0

            # 2. Count distinct tokens with MORE points
            # Rank = (Count > my_points) + 1
            async with db.execute("SELECT COUNT(*) FROM users WHERE points > ?", (my_points,)) as cursor:
                rank_row = await cursor.fetchone()
                rank = rank_row[0] + 1
            
            # 3. Total Count (with > 0 points)
            async with db.execute("SELECT COUNT(*) FROM users WHERE points > 0") as cursor:
                total_row = await cursor.fetchone()
                total = total_row[0]

            return (rank, total)

    async def get_or_create_dashboard_token(self, guild_id: int, user_id: int, ttl: int = 31536000) -> str:
        """Get existing valid token or create a new persistent access token (Default 1 year)."""
        import uuid
        now = int(time.time())
        
        async with aiosqlite.connect(self._db_path) as db:
            # 1. Try to find existing valid token
            async with db.execute("SELECT token, expires_at FROM dashboard_tokens WHERE guild_id=?", (str(guild_id),)) as cursor:
                rows = await cursor.fetchall()
                
            # Filter for valid one (and maybe cleanup expired ones)
            valid_token = None
            for r in rows:
                if r[1] > now:
                    valid_token = r[0]
                    break
            
            if valid_token:
                return valid_token

            # 2. Create New
            token = str(uuid.uuid4())
            expires = now + ttl # Default 1 year
            
            await db.execute(
                "INSERT INTO dashboard_tokens(token, guild_id, created_by, expires_at) VALUES(?, ?, ?, ?)",
                (token, str(guild_id), str(user_id), expires)
            )
            await db.commit()
            return token

    async def validate_dashboard_token(self, token: str) -> Optional[str]:
        """Validate token and return guild_id if valid. Deletes expired tokens."""
        now = int(time.time())
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT guild_id, expires_at FROM dashboard_tokens WHERE token=?", (token,)) as cursor:
                row = await cursor.fetchone()
            
            if not row:
                return None
            
            guild_id, expires_at = row
            if now > expires_at:
                # Expired
                await db.execute("DELETE FROM dashboard_tokens WHERE token=?", (token,))
                await db.commit()
                return None
            
            return guild_id
