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
  id TEXT PRIMARY KEY,
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

-- Owner-only scheduled tasks (safe-by-default: LLM-only unless explicitly extended later)
CREATE TABLE IF NOT EXISTS scheduled_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id TEXT NOT NULL,
  guild_id TEXT,
  channel_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  interval_sec INTEGER NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  model_pref TEXT,
  next_run_at INTEGER NOT NULL,
  last_run_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_task_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  status TEXT NOT NULL,
  core_run_id TEXT,
  output TEXT,
  error TEXT,
  FOREIGN KEY(task_id) REFERENCES scheduled_tasks(id)
);

-- Tool audit log (approvals + execution trail)
CREATE TABLE IF NOT EXISTS tool_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  actor_id TEXT,
  guild_id TEXT,
  channel_id TEXT,
  tool_name TEXT NOT NULL,
  tool_call_id TEXT UNIQUE,
  correlation_id TEXT,
  risk_score INTEGER,
  risk_level TEXT,
  approval_required INTEGER NOT NULL DEFAULT 0,
  approval_status TEXT,
  args_json TEXT,
  result_preview TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_audit_ts ON tool_audit(ts);
CREATE INDEX IF NOT EXISTS idx_tool_audit_actor ON tool_audit(actor_id);

-- Approval requests (idempotent per tool_call_id)
CREATE TABLE IF NOT EXISTS approval_requests (
  tool_call_id TEXT PRIMARY KEY,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  actor_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  correlation_id TEXT,
  risk_score INTEGER,
  risk_level TEXT,
  requires_code INTEGER NOT NULL DEFAULT 0,
  expected_code TEXT,
  args_hash TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  decided_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_approval_requests_created ON approval_requests(created_at);

-- Chat-level events (for tracking empty-final fallbacks, etc.)
CREATE TABLE IF NOT EXISTS chat_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  actor_id TEXT,
  guild_id TEXT,
  channel_id TEXT,
  correlation_id TEXT,
  run_id TEXT,
  event_type TEXT NOT NULL,
  detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_chat_events_corr ON chat_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_chat_events_ts ON chat_events(ts);
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

            # Migration: approvals UX (M1.5). Add missing columns for richer approval UX without breaking old DBs.
            try:
                async with db.execute("PRAGMA table_info(approval_requests)") as cur:
                    cols = {str(r[1]) for r in await cur.fetchall()}
                # Keep columns optional to remain backward compatible with existing deployments.
                missing: list[tuple[str, str]] = []
                for name, decl in [
                    ("requested_role", "TEXT"),
                    ("args_json", "TEXT"),
                    ("args_hash", "TEXT"),
                    ("summary", "TEXT"),
                    ("decided_by", "TEXT"),
                ]:
                    if name not in cols:
                        missing.append((name, decl))
                for name, decl in missing:
                    await db.execute(f"ALTER TABLE approval_requests ADD COLUMN {name} {decl}")
            except Exception:
                pass

            # Migration: Ensure points column exists
            try:
                await db.execute("ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0")
            except Exception:
                pass  # Column likely exists

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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]  # Include millis
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
                dst_conn.close()  # Close to flush WAL
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
                        os.remove(final_path)  # Should not happen with timestamp
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
                    except Exception:
                        pass
                return False
            finally:
                if src_conn:
                    src_conn.close()
                if dst_conn:
                    dst_conn.close()

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
                        "INSERT INTO users(id, privacy, speak_search_progress, created_at, display_name) "
                        "VALUES(?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET display_name=excluded.display_name"
                    ),
                    (str(discord_user_id), privacy_default, sp_default, now, display_name),
                )
            else:
                await db.execute(
                    (
                        "INSERT INTO users(id, privacy, speak_search_progress, created_at) "
                        "VALUES(?, ?, ?, ?) ON CONFLICT(id) DO NOTHING"
                    ),
                    (str(discord_user_id), privacy_default, sp_default, now),
                )
            await db.commit()

    async def set_privacy(self, discord_user_id: int, mode: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET privacy=? WHERE id=?",
                (mode, str(discord_user_id)),
            )
            await db.commit()

    async def get_privacy(self, discord_user_id: int) -> str:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT privacy FROM users WHERE id=?",
                (str(discord_user_id),),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else "private"

    # -----------------------------
    # Scheduler (Owner-Only)
    # -----------------------------

    async def create_scheduled_task(
        self,
        *,
        owner_id: int,
        guild_id: int | None,
        channel_id: int,
        prompt: str,
        interval_sec: int,
        model_pref: str | None = None,
        enabled: bool = True,
    ) -> int:
        now = int(time.time())
        interval_sec = max(30, int(interval_sec))
        next_run_at = now + interval_sec
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                (
                    "INSERT INTO scheduled_tasks(owner_id, guild_id, channel_id, prompt, interval_sec, enabled, model_pref, "
                    "next_run_at, last_run_at, created_at, updated_at) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)"
                ),
                (
                    str(owner_id),
                    str(guild_id) if guild_id is not None else None,
                    str(channel_id),
                    prompt,
                    interval_sec,
                    1 if enabled else 0,
                    model_pref,
                    next_run_at,
                    now,
                    now,
                ),
            )
            await db.commit()
            # scheduled_tasks.id is AUTOINCREMENT.
            task_id = int(cur.lastrowid or 0)

        # Best-effort housekeeping: keep audit tables bounded so logs don't grow unbounded.
        try:
            await self.prune_audit_tables()
        except Exception:
            pass
        return task_id

    async def prune_audit_tables(self) -> None:
        """Prune audit tables based on env-driven retention limits (best-effort)."""
        retention_days_raw = os.getenv("ORA_AUDIT_RETENTION_DAYS", "14").strip()
        max_rows_raw = os.getenv("ORA_AUDIT_MAX_ROWS", "50000").strip()
        max_chat_rows_raw = os.getenv("ORA_CHAT_EVENTS_MAX_ROWS", "50000").strip()

        try:
            retention_days = max(1, int(retention_days_raw))
        except Exception:
            retention_days = 14
        try:
            max_rows = max(1000, int(max_rows_raw))
        except Exception:
            max_rows = 50000
        try:
            max_chat_rows = max(1000, int(max_chat_rows_raw))
        except Exception:
            max_chat_rows = 50000

        now = int(time.time())
        cutoff = now - (retention_days * 86400)

        async with aiosqlite.connect(self._db_path) as db:
            # Time-based pruning
            await db.execute("DELETE FROM tool_audit WHERE ts < ?", (int(cutoff),))
            await db.execute("DELETE FROM approval_requests WHERE created_at < ?", (int(cutoff),))
            await db.execute("DELETE FROM chat_events WHERE ts < ?", (int(cutoff),))

            # Size-based pruning (keep newest rows)
            async def _prune_by_count(table: str, ts_col: str, keep: int) -> None:
                async with db.execute(f"SELECT COUNT(1) FROM {table}") as cur:
                    row = await cur.fetchone()
                total = int(row[0] or 0) if row else 0
                excess = total - int(keep)
                if excess <= 0:
                    return
                await db.execute(
                    f"DELETE FROM {table} WHERE id IN (SELECT id FROM {table} ORDER BY {ts_col} ASC LIMIT ?)",
                    (int(excess),),
                )

            await _prune_by_count("tool_audit", "ts", max_rows)
            await _prune_by_count("chat_events", "ts", max_chat_rows)

            await db.commit()

    async def log_tool_audit(
        self,
        *,
        ts: int,
        actor_id: Optional[int],
        guild_id: Optional[int],
        channel_id: Optional[int],
        tool_name: str,
        tool_call_id: str | None,
        correlation_id: str | None,
        risk_score: int,
        risk_level: str,
        approval_required: bool,
        approval_status: str | None,
        args_json: str,
        result_preview: str,
    ) -> None:
        from src.utils.redaction import redact_json_string, redact_text

        max_args_chars_raw = os.getenv("ORA_AUDIT_MAX_ARGS_CHARS", "5000").strip()
        max_result_chars_raw = os.getenv("ORA_AUDIT_MAX_RESULT_CHARS", "2000").strip()
        try:
            max_args_chars = max(500, int(max_args_chars_raw))
        except Exception:
            max_args_chars = 5000
        try:
            max_result_chars = max(200, int(max_result_chars_raw))
        except Exception:
            max_result_chars = 2000

        safe_args = redact_json_string(str(args_json or ""), max_chars=max_args_chars)
        safe_preview = redact_text(str(result_preview or ""))[:max_result_chars]

        async with aiosqlite.connect(self._db_path) as db:
            try:
                await db.execute(
                    (
                        "INSERT OR REPLACE INTO tool_audit("
                        "ts, actor_id, guild_id, channel_id, tool_name, tool_call_id, correlation_id, "
                        "risk_score, risk_level, approval_required, approval_status, args_json, result_preview"
                        ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    ),
                    (
                        int(ts),
                        str(actor_id) if actor_id is not None else None,
                        str(guild_id) if guild_id is not None else None,
                        str(channel_id) if channel_id is not None else None,
                        str(tool_name or ""),
                        str(tool_call_id) if tool_call_id else None,
                        str(correlation_id) if correlation_id else None,
                        int(risk_score),
                        str(risk_level or ""),
                        1 if approval_required else 0,
                        str(approval_status) if approval_status else None,
                        safe_args,
                        safe_preview,
                    ),
                )
                await db.commit()
            except Exception:
                # Best-effort; never fail tool execution due to logging.
                return

    async def update_tool_audit_result(self, *, tool_call_id: str, result_preview: str) -> None:
        """Update the result preview for an existing tool_call_id (best-effort)."""
        from src.utils.redaction import redact_text

        if not tool_call_id:
            return
        safe_preview = redact_text(str(result_preview or ""))[:2000]
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "UPDATE tool_audit SET result_preview=? WHERE tool_call_id=?",
                    (safe_preview, str(tool_call_id)),
                )
                await db.commit()
        except Exception:
            return

    async def get_tool_audit_rows(
        self,
        *,
        limit: int = 200,
        actor_id: Optional[int] = None,
        tool_name: Optional[str] = None,
        since_ts: Optional[int] = None,
    ) -> list[dict]:
        limit = max(1, min(1000, int(limit)))
        where = []
        params: list[object] = []
        if actor_id is not None:
            where.append("actor_id=?")
            params.append(str(actor_id))
        if tool_name:
            where.append("tool_name=?")
            params.append(str(tool_name))
        if since_ts is not None:
            where.append("ts>=?")
            params.append(int(since_ts))
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT ts, actor_id, guild_id, channel_id, tool_name, tool_call_id, correlation_id, "
            "risk_score, risk_level, approval_required, approval_status, args_json, result_preview "
            f"FROM tool_audit{clause} ORDER BY ts DESC LIMIT ?"
        )
        params.append(limit)
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(sql, tuple(params)) as cur:
                rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "ts": int(r[0]),
                    "actor_id": r[1],
                    "guild_id": r[2],
                    "channel_id": r[3],
                    "tool_name": r[4],
                    "tool_call_id": r[5],
                    "correlation_id": r[6],
                    "risk_score": r[7],
                    "risk_level": r[8],
                    "approval_required": bool(r[9]) if r[9] is not None else False,
                    "approval_status": r[10],
                    "args_json": r[11],
                    "result_preview": r[12],
                }
            )
        return out

    async def get_approval_requests_rows(
        self,
        *,
        limit: int = 200,
        since_ts: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        limit = max(1, min(1000, int(limit)))
        where = []
        params: list[object] = []
        if since_ts is not None:
            where.append("created_at>=?")
            params.append(int(since_ts))
        if status:
            where.append("status=?")
            params.append(str(status))
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT tool_call_id, created_at, expires_at, actor_id, tool_name, correlation_id, risk_score, risk_level, "
            "requires_code, expected_code, status, decided_at, requested_role, args_json, args_hash, summary, decided_by "
            f"FROM approval_requests{clause} ORDER BY created_at DESC LIMIT ?"
        )
        params.append(limit)
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(sql, tuple(params)) as cur:
                rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "tool_call_id": r[0],
                    "created_at": int(r[1]),
                    "expires_at": int(r[2]),
                    "actor_id": r[3],
                    "tool_name": r[4],
                    "correlation_id": r[5],
                    "risk_score": r[6],
                    "risk_level": r[7],
                    "requires_code": bool(r[8]) if r[8] is not None else False,
                    "expected_code": r[9],
                    "status": r[10],
                    "decided_at": int(r[11]) if r[11] is not None else None,
                    "requested_role": r[12],
                    "args_json": r[13],
                    "args_hash": r[14],
                    "summary": r[15],
                    "decided_by": r[16],
                }
            )
        return out

    async def count_approval_requests(
        self,
        *,
        actor_id: int,
        since_ts: Optional[int] = None,
    ) -> int:
        """
        Count approval requests for basic rate limiting.
        Note: actor_id is stored as text for historical reasons; compare as string.
        """
        where = ["actor_id=?"]
        params: list[object] = [str(int(actor_id))]
        if since_ts is not None:
            where.append("created_at>=?")
            params.append(int(since_ts))
        clause = " AND ".join(where)
        sql = f"SELECT COUNT(1) FROM approval_requests WHERE {clause}"
        async with aiosqlite.connect(self._db_path) as db:
            try:
                async with db.execute(sql, tuple(params)) as cur:
                    row = await cur.fetchone()
                return int(row[0] or 0) if row else 0
            except Exception:
                return 0

    async def count_tool_audit_rows(
        self,
        *,
        actor_id: int,
        since_ts: Optional[int] = None,
    ) -> int:
        """
        Count tool_audit rows for rate limiting.
        """
        where = ["actor_id=?"]
        params: list[object] = [str(int(actor_id))]
        if since_ts is not None:
            where.append("ts>=?")
            params.append(int(since_ts))
        clause = " AND ".join(where)
        sql = f"SELECT COUNT(1) FROM tool_audit WHERE {clause}"
        async with aiosqlite.connect(self._db_path) as db:
            try:
                async with db.execute(sql, tuple(params)) as cur:
                    row = await cur.fetchone()
                return int(row[0] or 0) if row else 0
            except Exception:
                return 0

    async def get_chat_events_rows(
        self,
        *,
        limit: int = 200,
        event_type: Optional[str] = None,
        since_ts: Optional[int] = None,
    ) -> list[dict]:
        limit = max(1, min(1000, int(limit)))
        where = []
        params: list[object] = []
        if event_type:
            where.append("event_type=?")
            params.append(str(event_type))
        if since_ts is not None:
            where.append("ts>=?")
            params.append(int(since_ts))
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT ts, actor_id, guild_id, channel_id, correlation_id, run_id, event_type, detail "
            f"FROM chat_events{clause} ORDER BY ts DESC LIMIT ?"
        )
        params.append(limit)
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(sql, tuple(params)) as cur:
                rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "ts": int(r[0]),
                    "actor_id": r[1],
                    "guild_id": r[2],
                    "channel_id": r[3],
                    "correlation_id": r[4],
                    "run_id": r[5],
                    "event_type": r[6],
                    "detail": r[7],
                }
            )
        return out

    async def upsert_approval_request(
        self,
        *,
        tool_call_id: str,
        created_at: int,
        expires_at: int,
        actor_id: int,
        tool_name: str,
        correlation_id: str | None,
        risk_score: int,
        risk_level: str,
        requires_code: bool,
        expected_code: str | None,
        args_hash: str | None = None,
        requested_role: str | None = None,
        args_json: str | None = None,
        summary: str | None = None,
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            try:
                await db.execute(
                    (
                        "INSERT OR REPLACE INTO approval_requests("
                        "tool_call_id, created_at, expires_at, actor_id, tool_name, correlation_id, "
                        "risk_score, risk_level, requires_code, expected_code, args_hash, requested_role, args_json, summary, status, decided_at, decided_by"
                        ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                        "COALESCE((SELECT status FROM approval_requests WHERE tool_call_id=?), 'pending'), "
                        "COALESCE((SELECT decided_at FROM approval_requests WHERE tool_call_id=?), NULL), "
                        "COALESCE((SELECT decided_by FROM approval_requests WHERE tool_call_id=?), NULL))"
                    ),
                    (
                        str(tool_call_id),
                        int(created_at),
                        int(expires_at),
                        str(actor_id),
                        str(tool_name or ""),
                        str(correlation_id) if correlation_id else None,
                        int(risk_score),
                        str(risk_level or ""),
                        1 if requires_code else 0,
                        str(expected_code) if expected_code else None,
                        str(args_hash) if args_hash else None,
                        str(requested_role) if requested_role else None,
                        str(args_json) if args_json else None,
                        str(summary) if summary else None,
                        str(tool_call_id),
                        str(tool_call_id),
                        str(tool_call_id),
                    ),
                )
                await db.commit()
            except Exception:
                return

    async def set_approval_status(self, *, tool_call_id: str, status: str) -> None:
        now = int(time.time())
        async with aiosqlite.connect(self._db_path) as db:
            try:
                await db.execute(
                    "UPDATE approval_requests SET status=?, decided_at=? WHERE tool_call_id=?",
                    (str(status), int(now), str(tool_call_id)),
                )
                await db.commit()
            except Exception:
                return

    async def get_approval_request(self, *, tool_call_id: str) -> Optional[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            try:
                async with db.execute(
                    (
                        "SELECT tool_call_id, created_at, expires_at, actor_id, tool_name, correlation_id, "
                        "risk_score, risk_level, requires_code, expected_code, status, decided_at, "
                        "requested_role, args_json, args_hash, summary, decided_by "
                        "FROM approval_requests WHERE tool_call_id=?"
                    ),
                    (str(tool_call_id),),
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    return None
                return {
                    "tool_call_id": row[0],
                    "created_at": int(row[1]),
                    "expires_at": int(row[2]),
                    "actor_id": row[3],
                    "tool_name": row[4],
                    "correlation_id": row[5],
                    "risk_score": row[6],
                    "risk_level": row[7],
                    "requires_code": bool(row[8]) if row[8] is not None else False,
                    "expected_code": row[9],
                    "status": row[10],
                    "decided_at": int(row[11]) if row[11] is not None else None,
                    "requested_role": row[12],
                    "args_json": row[13],
                    "args_hash": row[14],
                    "summary": row[15],
                    "decided_by": row[16],
                }
            except Exception:
                return None

    async def decide_approval_request(
        self,
        *,
        tool_call_id: str,
        status: str,
        decided_by: str,
    ) -> bool:
        now = int(time.time())
        async with aiosqlite.connect(self._db_path) as db:
            try:
                cur = await db.execute(
                    (
                        "UPDATE approval_requests "
                        "SET status=?, decided_at=?, decided_by=? "
                        "WHERE tool_call_id=? AND status='pending'"
                    ),
                    (str(status), int(now), str(decided_by), str(tool_call_id)),
                )
                await db.commit()
                return (cur.rowcount or 0) > 0
            except Exception:
                return False

    async def get_approval_status(self, *, tool_call_id: str) -> Optional[str]:
        async with aiosqlite.connect(self._db_path) as db:
            try:
                async with db.execute(
                    "SELECT status FROM approval_requests WHERE tool_call_id=?",
                    (str(tool_call_id),),
                ) as cur:
                    row = await cur.fetchone()
                if not row:
                    return None
                return str(row[0]) if row[0] is not None else None
            except Exception:
                return None

    async def list_scheduled_tasks(self, *, owner_id: int) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                (
                    "SELECT id, guild_id, channel_id, prompt, interval_sec, enabled, model_pref, next_run_at, last_run_at, created_at "
                    "FROM scheduled_tasks WHERE owner_id=? ORDER BY id DESC"
                ),
                (str(owner_id),),
            ) as cur:
                rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "id": int(r[0]),
                    "guild_id": r[1],
                    "channel_id": r[2],
                    "prompt": r[3],
                    "interval_sec": int(r[4]),
                    "enabled": bool(r[5]),
                    "model_pref": r[6],
                    "next_run_at": int(r[7]),
                    "last_run_at": int(r[8]) if r[8] is not None else None,
                    "created_at": int(r[9]),
                }
            )
        return out

    async def delete_scheduled_task(self, *, owner_id: int, task_id: int) -> bool:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("DELETE FROM scheduled_task_runs WHERE task_id=?", (int(task_id),))
            cur = await db.execute(
                "DELETE FROM scheduled_tasks WHERE owner_id=? AND id=?",
                (str(owner_id), int(task_id)),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def log_chat_event(
        self,
        *,
        ts: int,
        actor_id: Optional[int],
        guild_id: Optional[int],
        channel_id: Optional[int],
        correlation_id: Optional[str],
        run_id: Optional[str],
        event_type: str,
        detail: Optional[str] = None,
    ) -> None:
        """Best-effort chat-level event logging (must never break primary flow)."""
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    (
                        "INSERT INTO chat_events(ts, actor_id, guild_id, channel_id, correlation_id, run_id, event_type, detail) "
                        "VALUES(?, ?, ?, ?, ?, ?, ?, ?)"
                    ),
                    (
                        int(ts),
                        str(actor_id) if actor_id is not None else None,
                        str(guild_id) if guild_id is not None else None,
                        str(channel_id) if channel_id is not None else None,
                        correlation_id,
                        run_id,
                        event_type,
                        detail,
                    ),
                )
                await db.commit()
        except Exception:
            # Never block chat on logging failures.
            return

    async def set_scheduled_task_enabled(self, *, owner_id: int, task_id: int, enabled: bool) -> bool:
        now = int(time.time())
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "UPDATE scheduled_tasks SET enabled=?, updated_at=? WHERE owner_id=? AND id=?",
                (1 if enabled else 0, now, str(owner_id), int(task_id)),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0

    async def get_due_scheduled_tasks(self, *, now_ts: int, limit: int = 5) -> list[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                (
                    "SELECT id, owner_id, guild_id, channel_id, prompt, interval_sec, model_pref, next_run_at "
                    "FROM scheduled_tasks WHERE enabled=1 AND next_run_at<=? ORDER BY next_run_at ASC LIMIT ?"
                ),
                (int(now_ts), int(limit)),
            ) as cur:
                rows = await cur.fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "id": int(r[0]),
                    "owner_id": int(r[1]),
                    "guild_id": r[2],
                    "channel_id": int(r[3]),
                    "prompt": r[4],
                    "interval_sec": int(r[5]),
                    "model_pref": r[6],
                    "next_run_at": int(r[7]),
                }
            )
        return out

    async def claim_scheduled_task(self, *, task_id: int, now_ts: int) -> bool:
        """
        Atomically move next_run_at forward so multiple workers don't run the same task concurrently.
        """
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT interval_sec FROM scheduled_tasks WHERE id=? AND enabled=1", (int(task_id),)) as cur:
                row = await cur.fetchone()
            if not row:
                return False
            interval_sec = max(30, int(row[0] or 30))
            next_run = int(now_ts) + interval_sec
            cur2 = await db.execute(
                "UPDATE scheduled_tasks SET next_run_at=?, last_run_at=?, updated_at=? WHERE id=? AND enabled=1 AND next_run_at<=?",
                (next_run, int(now_ts), int(now_ts), int(task_id), int(now_ts)),
            )
            await db.commit()
            return (cur2.rowcount or 0) > 0

    async def insert_task_run(self, *, task_id: int, started_at: int, status: str = "running") -> int:
        async with aiosqlite.connect(self._db_path) as db:
            cur = await db.execute(
                "INSERT INTO scheduled_task_runs(task_id, started_at, status) VALUES(?, ?, ?)",
                (int(task_id), int(started_at), status),
            )
            await db.commit()
            return int(cur.lastrowid)

    async def finish_task_run(
        self,
        *,
        run_row_id: int,
        finished_at: int,
        status: str,
        core_run_id: str | None = None,
        output: str | None = None,
        error: str | None = None,
    ) -> None:
        # Keep output small to avoid DB bloat.
        out = (output or "").strip()
        if len(out) > 4000:
            out = out[:3997] + "..."
        err = (error or "").strip()
        if len(err) > 2000:
            err = err[:1997] + "..."
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                (
                    "UPDATE scheduled_task_runs SET finished_at=?, status=?, core_run_id=?, output=?, error=? "
                    "WHERE id=?"
                ),
                (int(finished_at), status, core_run_id, out or None, err or None, int(run_row_id)),
            )
            await db.commit()

    async def set_system_privacy(self, discord_user_id: int, mode: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            # Lazy migration
            try:
                await db.execute("ALTER TABLE users ADD COLUMN system_privacy TEXT DEFAULT 'private'")
            except Exception:
                pass

            await db.execute(
                "UPDATE users SET system_privacy=? WHERE id=?",
                (mode, str(discord_user_id)),
            )
            await db.commit()

    async def get_system_privacy(self, discord_user_id: int) -> str:
        async with aiosqlite.connect(self._db_path) as db:
            try:
                async with db.execute(
                    "SELECT system_privacy FROM users WHERE id=?",
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
                "SELECT speak_search_progress FROM users WHERE id=?",
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
                "UPDATE users SET speak_search_progress=? WHERE id=?",
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
                    "SELECT desktop_watch_enabled FROM users WHERE id=?",
                    (str(discord_user_id),),
                ) as cursor:
                    row = await cursor.fetchone()
                if row is None or row[0] is None:
                    return True  # Default ON
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
                pass  # Column likely exists

            await db.execute(
                "UPDATE users SET desktop_watch_enabled=? WHERE id=?",
                (val, str(discord_user_id)),
            )
            await db.commit()

    async def upsert_google_sub(
        self, discord_user_id: int, google_sub: str, refresh_token: Optional[str] = None
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            if refresh_token:
                await db.execute(
                    (
                        "INSERT INTO users(id, google_sub, refresh_token, privacy, created_at) "
                        "VALUES(?, ?, ?, 'private', ?) "
                        "ON CONFLICT(id) DO UPDATE SET google_sub=excluded.google_sub, refresh_token=excluded.refresh_token"
                    ),
                    (str(discord_user_id), google_sub, refresh_token, int(time.time())),
                )
            else:
                await db.execute(
                    (
                        "INSERT INTO users(id, google_sub, privacy, created_at) "
                        "VALUES(?, ?, 'private', ?) "
                        "ON CONFLICT(id) DO UPDATE SET google_sub=excluded.google_sub"
                    ),
                    (str(discord_user_id), google_sub, int(time.time())),
                )
            await db.commit()

    async def get_google_creds(self, discord_user_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT google_sub, refresh_token FROM users WHERE id=?",
                (str(discord_user_id),),
            ) as cursor:
                row = await cursor.fetchone()

        if not row or not row["refresh_token"]:
            return None

        return {
            "refresh_token": row["refresh_token"],
            "client_id": None,  # Will be filled by caller from env
            "client_secret": None,
            "token_uri": "https://oauth2.googleapis.com/token",
        }

    async def get_google_sub(self, discord_user_id: int) -> Optional[str]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT google_sub FROM users WHERE id=?",
                (str(discord_user_id),),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row and row[0] else None

    async def start_login_state(self, state: str, discord_user_id: int, ttl_sec: int = 900) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                ("INSERT OR REPLACE INTO login_states(state, discord_user_id, expires_at) VALUES(?, ?, ?)"),
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

    async def add_dataset(self, discord_user_id: int, name: str, source_url: Optional[str]) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                ("INSERT INTO datasets(discord_user_id, name, source_url, created_at) VALUES(?, ?, ?, ?)"),
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

    async def add_conversation(self, user_id: str, platform: str, message: str, response: str) -> None:
        """Log a conversation turn. user_id can be Discord ID or Google Sub."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                ("INSERT INTO conversations(user_id, platform, message, response, created_at) VALUES(?, ?, ?, ?, ?)"),
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

        async with aiosqlite.connect(self._db_path):
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
            async with db.execute("SELECT 1 FROM users WHERE id=?", (str(discord_user_id),)) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await db.execute(
                    "UPDATE users SET google_sub=? WHERE id=?",
                    (google_sub, str(discord_user_id)),
                )
            else:
                # Create new user
                await db.execute(
                    "INSERT INTO users(id, google_sub, created_at) VALUES(?, ?, ?)",
                    (str(discord_user_id), google_sub, int(time.time())),
                )
            await db.commit()

            await db.commit()

    async def get_points(self, discord_user_id: int) -> int:
        """Get the current point balance for a user."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("SELECT points FROM users WHERE id=?", (str(discord_user_id),))
            row = await cursor.fetchone()
            if row:
                return row[0] if row[0] is not None else 0
            return 0

    async def add_points(self, discord_user_id: int, amount: int) -> int:
        """Add points to a user. Returns new balance."""
        async with aiosqlite.connect(self._db_path) as db:
            # Upsert User if not exists
            await db.execute(
                "INSERT INTO users(id, created_at, points) VALUES(?, ?, 0) ON CONFLICT(id) DO NOTHING",
                (str(discord_user_id), int(time.time())),
            )

            # Atomic Add
            await db.execute(
                "UPDATE users SET points = points + ? WHERE id=?", (amount, str(discord_user_id))
            )
            await db.commit()

            # Fetch new balance
            async with db.execute(
                "SELECT points FROM users WHERE id=?", (str(discord_user_id),)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def set_points(self, discord_user_id: int, amount: int) -> None:
        """Set absolute point balance."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO users(id, created_at, points) VALUES(?, ?, ?) ON CONFLICT(id) DO UPDATE SET points=?",
                (str(discord_user_id), int(time.time()), amount, amount),
            )
            await db.commit()

    async def get_permission_level(self, discord_user_id: int) -> str:
        """Get the permission level for a user (user, sub_admin, vc_admin, owner)."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT permission_level FROM users WHERE id=?", (str(discord_user_id),)
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
                "INSERT INTO users(id, created_at, permission_level) VALUES(?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET permission_level=?",
                (str(discord_user_id), int(time.time()), level, level),
            )
            await db.commit()

    async def get_rank(self, discord_user_id: int) -> Tuple[int, int]:
        """Get the rank of a user based on points. Returns (rank, total_users)."""
        async with aiosqlite.connect(self._db_path) as db:
            # 1. Get user's points
            async with db.execute(
                "SELECT points FROM users WHERE id=?", (str(discord_user_id),)
            ) as cursor:
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
            async with db.execute(
                "SELECT token, expires_at FROM dashboard_tokens WHERE guild_id=?", (str(guild_id),)
            ) as cursor:
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
            expires = now + ttl  # Default 1 year

            await db.execute(
                "INSERT INTO dashboard_tokens(token, guild_id, created_by, expires_at) VALUES(?, ?, ?, ?)",
                (token, str(guild_id), str(user_id), expires),
            )
            await db.commit()
            return token

    async def validate_dashboard_token(self, token: str) -> Optional[str]:
        """Validate token and return guild_id if valid. Deletes expired tokens."""
        now = int(time.time())
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT guild_id, expires_at FROM dashboard_tokens WHERE token=?", (token,)
            ) as cursor:
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
