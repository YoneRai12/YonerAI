from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any

import aiosqlite

from src.config import TEMP_DIR, resolve_bot_db_path

FILES_ROOT = Path(TEMP_DIR) / "files_mvp"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files_records (
  id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  original_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  sha256 TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_records_owner ON files_records(owner_id);
CREATE INDEX IF NOT EXISTS idx_files_records_expires ON files_records(expires_at);

CREATE TABLE IF NOT EXISTS file_share_tokens (
  token_hash TEXT PRIMARY KEY,
  file_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  FOREIGN KEY(file_id) REFERENCES files_records(id)
);
CREATE INDEX IF NOT EXISTS idx_file_share_tokens_file ON file_share_tokens(file_id);
CREATE INDEX IF NOT EXISTS idx_file_share_tokens_expires ON file_share_tokens(expires_at);
"""


async def _connect() -> aiosqlite.Connection:
  db = await aiosqlite.connect(resolve_bot_db_path())
  db.row_factory = aiosqlite.Row
  await db.executescript(_SCHEMA)
  return db


def _token_hash(token: str) -> str:
  pepper = (os.getenv("ORA_FILES_TOKEN_PEPPER") or "").strip()
  return hashlib.sha256(f"{pepper}:{token}".encode("utf-8")).hexdigest()


def issue_share_token() -> tuple[str, str]:
  token = secrets.token_urlsafe(24)
  return token, _token_hash(token)


async def create_file_record(
  *,
  file_id: str,
  owner_id: str,
  source_kind: str,
  original_name: str,
  mime_type: str,
  size_bytes: int,
  sha256_hex: str,
  storage_path: str,
  created_at: int,
  expires_at: int,
) -> None:
  db = await _connect()
  try:
    await db.execute(
      (
        "INSERT INTO files_records(id, owner_id, source_kind, original_name, mime_type, size_bytes, sha256, "
        "storage_path, created_at, expires_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
      ),
      (
        file_id,
        owner_id,
        source_kind,
        original_name,
        mime_type,
        int(size_bytes),
        sha256_hex,
        storage_path,
        int(created_at),
        int(expires_at),
      ),
    )
    await db.commit()
  finally:
    await db.close()


async def get_file_record(file_id: str) -> dict[str, Any] | None:
  db = await _connect()
  try:
    async with db.execute("SELECT * FROM files_records WHERE id=?", (file_id,)) as cur:
      row = await cur.fetchone()
    return dict(row) if row else None
  finally:
    await db.close()


async def create_share_token_record(*, file_id: str, token_hash: str, created_at: int, expires_at: int) -> None:
  db = await _connect()
  try:
    await db.execute(
      "INSERT INTO file_share_tokens(token_hash, file_id, created_at, expires_at) VALUES(?, ?, ?, ?)",
      (token_hash, file_id, int(created_at), int(expires_at)),
    )
    await db.commit()
  finally:
    await db.close()


async def get_file_record_by_share_token(token: str) -> dict[str, Any] | None:
  token_hash = _token_hash(token)
  db = await _connect()
  try:
    async with db.execute(
      (
        "SELECT f.* FROM file_share_tokens s "
        "JOIN files_records f ON f.id=s.file_id "
        "WHERE s.token_hash=?"
      ),
      (token_hash,),
    ) as cur:
      row = await cur.fetchone()
    return dict(row) if row else None
  finally:
    await db.close()


async def cleanup_expired_files(*, now_ts: int | None = None) -> dict[str, int]:
  now_ts = int(now_ts or time.time())
  deleted_files = 0
  deleted_tokens = 0

  db = await _connect()
  try:
    async with db.execute("SELECT storage_path FROM files_records WHERE expires_at<=?", (now_ts,)) as cur:
      stale_rows = await cur.fetchall()
    for row in stale_rows:
      storage_path = Path(str(row["storage_path"]))
      try:
        if storage_path.exists():
          storage_path.unlink()
      except Exception:
        pass
      try:
        parent = storage_path.parent
        if parent.exists():
          shutil.rmtree(parent, ignore_errors=True)
      except Exception:
        pass

    cur1 = await db.execute("DELETE FROM file_share_tokens WHERE expires_at<=?", (now_ts,))
    deleted_tokens += int(cur1.rowcount or 0)
    cur2 = await db.execute("DELETE FROM files_records WHERE expires_at<=?", (now_ts,))
    deleted_files += int(cur2.rowcount or 0)
    await db.commit()
  finally:
    await db.close()

  return {"files_deleted": deleted_files, "tokens_deleted": deleted_tokens}
