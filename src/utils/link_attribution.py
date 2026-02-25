from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import aiosqlite

from src.config import resolve_bot_db_path

_BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _db_path() -> str:
    return resolve_bot_db_path(os.getenv("ORA_BOT_DB"))


def _now() -> int:
    return int(time.time())


def _mode() -> str:
    mode = (os.getenv("ORA_LINK_ATTRIBUTION_MODE") or "redirect").strip().lower()
    if mode not in {"redirect", "utm", "off"}:
        mode = "redirect"
    return mode


def _redirect_base() -> str:
    base = (os.getenv("ORA_LINK_REDIRECT_BASE_URL") or "https://yonerai.com/r").strip()
    if not base:
        base = "https://yonerai.com/r"
    return base.rstrip("/")


def _random_base62(length: int = 10) -> str:
    n = max(6, min(24, int(length)))
    return "".join(_BASE62[secrets.randbelow(len(_BASE62))] for _ in range(n))


def _is_http_url(url: str) -> bool:
    p = urlsplit(url or "")
    return p.scheme in {"http", "https"} and bool(p.netloc)


def _target_domain(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except Exception:
        return ""


def _is_already_redirect_url(url: str) -> bool:
    base = _redirect_base()
    try:
        u = urlsplit(url)
        b = urlsplit(base)
        if not u.scheme or not u.netloc:
            return False
        if u.scheme.lower() != b.scheme.lower() or u.netloc.lower() != b.netloc.lower():
            return False
        bpath = b.path.rstrip("/")
        return u.path.startswith(bpath + "/") if bpath else u.path.startswith("/")
    except Exception:
        return False


def _append_params_no_overwrite(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    existing = {k for k, _ in query_items}
    for k, v in params.items():
        if (k not in existing) and (v is not None):
            query_items.append((str(k), str(v)))
    new_query = urlencode(query_items, doseq=True)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


def _hash_optional(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    pepper = (
        (os.getenv("ORA_LINK_CLICK_HASH_PEPPER") or "").strip()
        or (os.getenv("WEB_SESSION_SECRET") or "").strip()
        or (os.getenv("ORA_WEB_API_TOKEN") or "").strip()
        or "yonerai-link-hash"
    )
    msg = f"{pepper}:{raw}".encode("utf-8", errors="ignore")
    return hashlib.sha256(msg).hexdigest()


async def _ensure_schema(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
CREATE TABLE IF NOT EXISTS link_refs (
  id TEXT PRIMARY KEY,
  message_id TEXT,
  run_id TEXT,
  request_id TEXT,
  trace_id TEXT,
  origin TEXT,
  created_at INTEGER NOT NULL,
  target_url TEXT NOT NULL,
  target_domain TEXT,
  clicks_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_link_refs_created ON link_refs(created_at);
CREATE INDEX IF NOT EXISTS idx_link_refs_run ON link_refs(run_id);
CREATE INDEX IF NOT EXISTS idx_link_refs_message ON link_refs(message_id);

CREATE TABLE IF NOT EXISTS link_clicks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  ip_hash TEXT,
  ua_hash TEXT,
  FOREIGN KEY(ref_id) REFERENCES link_refs(id)
);
CREATE INDEX IF NOT EXISTS idx_link_clicks_ref_ts ON link_clicks(ref_id, ts);

CREATE TABLE IF NOT EXISTS run_request_meta (
  run_id TEXT PRIMARY KEY,
  message_id TEXT,
  request_id TEXT,
  trace_id TEXT,
  origin TEXT,
  node_id TEXT,
  tampered INTEGER NOT NULL DEFAULT 0,
  source TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_request_meta_trace ON run_request_meta(trace_id);

CREATE TABLE IF NOT EXISTS run_effective_route (
  run_id TEXT PRIMARY KEY,
  effective_route_json TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_effective_route_updated ON run_effective_route(updated_at);
        """
    )


async def record_run_request_meta(
    *,
    run_id: str,
    message_id: str | None,
    request_id: str | None,
    trace_id: str | None,
    origin: str | None,
    node_id: str | None,
    tampered: bool,
    source: str | None,
) -> None:
    if not run_id:
        return
    try:
        async with aiosqlite.connect(_db_path()) as db:
            await _ensure_schema(db)
            await db.execute(
                (
                    "INSERT OR REPLACE INTO run_request_meta("
                    "run_id, message_id, request_id, trace_id, origin, node_id, tampered, source, created_at"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    str(run_id),
                    str(message_id) if message_id else None,
                    str(request_id) if request_id else None,
                    str(trace_id) if trace_id else None,
                    str(origin) if origin else None,
                    str(node_id) if node_id else None,
                    1 if tampered else 0,
                    str(source) if source else None,
                    _now(),
                ),
            )
            await db.commit()
    except Exception:
        return


async def record_run_effective_route(*, run_id: str, effective_route: dict[str, Any]) -> None:
    if not run_id or not isinstance(effective_route, dict):
        return
    try:
        payload = json.dumps(effective_route, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return
    now = _now()
    try:
        async with aiosqlite.connect(_db_path()) as db:
            await _ensure_schema(db)
            await db.execute(
                (
                    "INSERT INTO run_effective_route(run_id, effective_route_json, created_at, updated_at) "
                    "VALUES(?, ?, ?, ?) "
                    "ON CONFLICT(run_id) DO UPDATE SET "
                    "effective_route_json=excluded.effective_route_json, updated_at=excluded.updated_at"
                ),
                (str(run_id), payload, now, now),
            )
            await db.commit()
    except Exception:
        return


async def get_run_effective_route(run_id: str) -> dict[str, Any] | None:
    rid = (run_id or "").strip()
    if not rid:
        return None
    try:
        async with aiosqlite.connect(_db_path()) as db:
            await _ensure_schema(db)
            async with db.execute(
                "SELECT effective_route_json FROM run_effective_route WHERE run_id=? LIMIT 1",
                (rid,),
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        raw = row[0]
        if not isinstance(raw, str) or not raw.strip():
            return None
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return None
    except Exception:
        return None


async def _insert_link_ref(
    *,
    ref_id: str,
    target_url: str,
    message_id: str | None,
    run_id: str | None,
    request_id: str | None,
    trace_id: str | None,
    origin: str | None,
) -> bool:
    try:
        async with aiosqlite.connect(_db_path()) as db:
            await _ensure_schema(db)
            cur = await db.execute(
                (
                    "INSERT OR IGNORE INTO link_refs("
                    "id, message_id, run_id, request_id, trace_id, origin, created_at, target_url, target_domain"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    str(ref_id),
                    str(message_id) if message_id else None,
                    str(run_id) if run_id else None,
                    str(request_id) if request_id else None,
                    str(trace_id) if trace_id else None,
                    str(origin) if origin else "yonerai",
                    _now(),
                    str(target_url),
                    _target_domain(target_url),
                ),
            )
            await db.commit()
            return (cur.rowcount or 0) > 0
    except Exception:
        return False


async def _create_ref_id(
    *,
    target_url: str,
    message_id: str | None,
    run_id: str | None,
    request_id: str | None,
    trace_id: str | None,
    origin: str | None,
) -> str:
    for _ in range(10):
        ref_id = _random_base62(10)
        ok = await _insert_link_ref(
            ref_id=ref_id,
            target_url=target_url,
            message_id=message_id,
            run_id=run_id,
            request_id=request_id,
            trace_id=trace_id,
            origin=origin,
        )
        if ok:
            return ref_id
    # Last fallback.
    ref_id = _random_base62(14)
    await _insert_link_ref(
        ref_id=ref_id,
        target_url=target_url,
        message_id=message_id,
        run_id=run_id,
        request_id=request_id,
        trace_id=trace_id,
        origin=origin,
    )
    return ref_id


async def attribute_url(
    url: str,
    *,
    message_id: str | None = None,
    run_id: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
    origin: str | None = None,
    mode: str | None = None,
) -> tuple[str, str | None]:
    raw = (url or "").strip()
    if (not raw) or (not _is_http_url(raw)):
        return raw, None

    chosen = (mode or _mode()).strip().lower()
    if chosen not in {"redirect", "utm", "off"}:
        chosen = _mode()
    if chosen == "off":
        return raw, None

    if chosen == "redirect":
        if _is_already_redirect_url(raw):
            return raw, None
        ref_id = await _create_ref_id(
            target_url=raw,
            message_id=message_id,
            run_id=run_id,
            request_id=request_id,
            trace_id=trace_id,
            origin=origin,
        )
        return f"{_redirect_base()}/{ref_id}", ref_id

    # UTM mode
    parts = urlsplit(raw)
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    ref_id = str(existing.get("yonerai_ref") or "").strip()
    if not ref_id:
        ref_id = await _create_ref_id(
            target_url=raw,
            message_id=message_id,
            run_id=run_id,
            request_id=request_id,
            trace_id=trace_id,
            origin=origin,
        )

    params = {
        "utm_source": (os.getenv("ORA_LINK_UTM_SOURCE") or "yonerai").strip() or "yonerai",
        "utm_medium": (os.getenv("ORA_LINK_UTM_MEDIUM") or "ai_ref").strip() or "ai_ref",
        "utm_campaign": (os.getenv("ORA_LINK_UTM_CAMPAIGN") or "ora").strip() or "ora",
        "utm_content": str(message_id or "").strip(),
        "yonerai_ref": ref_id,
    }
    out = _append_params_no_overwrite(raw, params)
    return out, ref_id


async def resolve_link_ref(ref_id: str) -> dict[str, Any] | None:
    rid = (ref_id or "").strip()
    if not rid:
        return None
    try:
        async with aiosqlite.connect(_db_path()) as db:
            await _ensure_schema(db)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                (
                    "SELECT id, message_id, run_id, request_id, trace_id, origin, created_at, "
                    "target_url, target_domain, clicks_count FROM link_refs WHERE id=? LIMIT 1"
                ),
                (rid,),
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


async def record_link_click(*, ref_id: str, ip: str | None, user_agent: str | None) -> bool:
    rid = (ref_id or "").strip()
    if not rid:
        return False

    store_hashes = (os.getenv("ORA_LINK_STORE_HASHED_IP_UA") or "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    ip_hash = _hash_optional(ip) if store_hashes else None
    ua_hash = _hash_optional(user_agent) if store_hashes else None

    try:
        async with aiosqlite.connect(_db_path()) as db:
            await _ensure_schema(db)
            cur = await db.execute("SELECT 1 FROM link_refs WHERE id=? LIMIT 1", (rid,))
            exists = await cur.fetchone()
            if not exists:
                return False

            await db.execute("UPDATE link_refs SET clicks_count=clicks_count+1 WHERE id=?", (rid,))
            await db.execute(
                "INSERT INTO link_clicks(ref_id, ts, ip_hash, ua_hash) VALUES(?, ?, ?, ?)",
                (rid, _now(), ip_hash, ua_hash),
            )
            await db.commit()
            return True
    except Exception:
        return False


async def resolve_and_record_click(*, ref_id: str, ip: str | None, user_agent: str | None) -> str | None:
    row = await resolve_link_ref(ref_id)
    if not row:
        return None
    await record_link_click(ref_id=ref_id, ip=ip, user_agent=user_agent)
    target = str(row.get("target_url") or "").strip()
    if not _is_http_url(target):
        return None
    return target
