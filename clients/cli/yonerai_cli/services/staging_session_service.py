from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import re
import sys
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from yonerai_cli.config import default_config_path
from yonerai_cli.services.auth_session_service import sanitize_staging_account


STAGING_SESSION_CLAIM_SCHEMA_VERSION = "yonerai-staging-session-claim/v0.1"
DEFAULT_SCOPES = ("account:read", "conversation:read", "sync:preview")
_TOKEN_KEY_RE = re.compile(
    r"(^|[_\-.:\s])(google_token|access_token|id_token|refresh_token|auth_code|authorization_code|client_secret|password|api_key)($|[_\-.:\s])",
    re.IGNORECASE,
)
_LOCAL_PATH_RE = re.compile(r"([A-Za-z]:\\|\\\\|/Users/|/home/|/root/)", re.IGNORECASE)
_SAFE_TEXT_RE = re.compile(r"^[A-Za-z0-9_.:@+\-*(),!\[\]&\s]{0,240}$")
_SAFE_SCOPE_RE = re.compile(r"^[a-z][a-z0-9:_-]{1,80}$")
_MEMORY_SESSIONS: dict[str, tuple[str, dict[str, object]]] = {}


class StagingSessionStorageError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message

    def to_safe_error(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "token_printed": False,
            "local_path_printed": False,
            "google_token_printed": False,
        }


def default_staging_session_claim_path(config_path: str | Path | None = None) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path()
    if config_path is None and not str(os.environ.get("YONERAI_CLI_CONFIG_PATH") or "").strip():
        return base.with_name("staging-session-claim.json")
    return base.with_name(f"{base.stem}.staging-session-claim.json")


def default_staging_session_secret_path(config_path: str | Path | None = None) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path()
    if config_path is None and not str(os.environ.get("YONERAI_CLI_CONFIG_PATH") or "").strip():
        return base.with_name("staging-session-token.dpapi")
    return base.with_name(f"{base.stem}.staging-session-token.dpapi")


def legacy_staging_session_claim_path(config_path: str | Path | None = None) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path()
    return base.with_name("staging-session-claim.json")


def legacy_staging_session_secret_path(config_path: str | Path | None = None) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path()
    return base.with_name("staging-session-token.dpapi")


def _candidate_staging_session_claim_paths(config_path: str | Path | None = None) -> tuple[Path, ...]:
    return _dedupe_paths(
        (
            default_staging_session_claim_path(config_path),
            legacy_staging_session_claim_path(config_path),
        )
    )


def _candidate_staging_session_secret_paths(config_path: str | Path | None = None) -> tuple[Path, ...]:
    return _dedupe_paths(
        (
            default_staging_session_secret_path(config_path),
            legacy_staging_session_secret_path(config_path),
        )
    )


def _dedupe_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return tuple(result)


def build_staging_session_claim(
    *,
    session_token: str,
    origin: str,
    account: Mapping[str, object] | None = None,
    expires_at: object = None,
    scopes: tuple[str, ...] | list[str] | None = None,
    storage_backend: str,
) -> dict[str, object]:
    token = _validate_session_token(session_token)
    safe_account = sanitize_staging_account(account or {})
    safe_scopes = _safe_scopes(scopes)
    issued_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    claim = {
        "schema_version": STAGING_SESSION_CLAIM_SCHEMA_VERSION,
        "auth_state": "linked",
        "origin": _safe_public_text(origin, fallback="configured"),
        "issued_at": issued_at,
        "expires_at": _safe_public_text(expires_at, fallback=None),
        "account_id": _safe_public_text(safe_account.get("account_ref"), fallback="linked-staging-account"),
        "redacted_email": _safe_public_text(safe_account.get("email_redacted"), fallback="not-linked"),
        "display_name": _safe_public_text(safe_account.get("display_name"), fallback="linked staging account"),
        "scopes": list(safe_scopes),
        "session_hash": _session_hash(token),
        "storage_backend": _safe_storage_backend(storage_backend),
        "token_printed": False,
        "google_token_stored": False,
        "google_access_token_stored": False,
        "google_id_token_stored": False,
        "google_refresh_token_stored": False,
        "auth_code_stored": False,
        "plaintext_session_token_stored": False,
    }
    return validate_staging_session_claim(claim)


def validate_staging_session_claim(claim: Mapping[str, object]) -> dict[str, object]:
    serialized = json.dumps(claim, ensure_ascii=False, sort_keys=True)
    if _contains_forbidden_secret_material(claim):
        raise ValueError("staging session claim contains forbidden token-like metadata")
    if _LOCAL_PATH_RE.search(serialized):
        raise ValueError("staging session claim contains a local path")
    scopes_raw = claim.get("scopes") if isinstance(claim.get("scopes"), list) else []
    scopes = _safe_scopes([str(scope) for scope in scopes_raw])
    session_hash = str(claim.get("session_hash") or "").strip()
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", session_hash):
        raise ValueError("staging session claim hash is invalid")
    auth_state = str(claim.get("auth_state") or "unauthenticated")
    if auth_state not in {"unauthenticated", "pending", "linked", "expired", "revoked"}:
        raise ValueError("staging session auth_state is invalid")
    return {
        "schema_version": STAGING_SESSION_CLAIM_SCHEMA_VERSION,
        "auth_state": _expired_state(auth_state, claim.get("expires_at")),
        "origin": _safe_public_text(claim.get("origin"), fallback="not_configured"),
        "issued_at": _safe_public_text(claim.get("issued_at"), fallback=None),
        "expires_at": _safe_public_text(claim.get("expires_at"), fallback=None),
        "account_id": _safe_public_text(claim.get("account_id"), fallback="linked-staging-account"),
        "redacted_email": _safe_public_text(claim.get("redacted_email"), fallback="not-linked"),
        "display_name": _safe_public_text(claim.get("display_name"), fallback="linked staging account"),
        "scopes": list(scopes),
        "session_hash": session_hash,
        "storage_backend": _safe_storage_backend(claim.get("storage_backend")),
        "token_printed": False,
        "google_token_stored": False,
        "google_access_token_stored": False,
        "google_id_token_stored": False,
        "google_refresh_token_stored": False,
        "auth_code_stored": False,
        "plaintext_session_token_stored": False,
    }


def save_staging_session(
    *,
    session_token: str,
    origin: str,
    account: Mapping[str, object] | None = None,
    expires_at: object = None,
    scopes: tuple[str, ...] | list[str] | None = None,
    config_path: str | Path | None = None,
) -> dict[str, object]:
    token = _validate_session_token(session_token)
    memory_key = _memory_key(config_path)
    if _dpapi_available():
        claim = build_staging_session_claim(
            session_token=token,
            origin=origin,
            account=account,
            expires_at=expires_at,
            scopes=scopes,
            storage_backend="windows_dpapi_file",
        )
        protected = _dpapi_protect(token.encode("utf-8"))
        secret_path = default_staging_session_secret_path(config_path)
        claim_path = default_staging_session_claim_path(config_path)
        try:
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            secret_path.write_text("dpapi:v1:" + base64.b64encode(protected).decode("ascii") + "\n", encoding="ascii")
            claim_path.write_text(json.dumps(claim, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            raise StagingSessionStorageError("staging_session_store_failed", "Staging session could not be stored securely.") from exc
        _MEMORY_SESSIONS.pop(memory_key, None)
        return claim

    claim = build_staging_session_claim(
        session_token=token,
        origin=origin,
        account=account,
        expires_at=expires_at,
        scopes=scopes,
        storage_backend="memory_session_only",
    )
    _MEMORY_SESSIONS[memory_key] = (token, claim)
    return claim


def load_staging_session_claim(config_path: str | Path | None = None) -> dict[str, object]:
    claim, _path = _load_staging_session_claim_with_path(config_path)
    return claim


def _load_staging_session_claim_with_path(config_path: str | Path | None = None) -> tuple[dict[str, object], Path | None]:
    memory = _MEMORY_SESSIONS.get(_memory_key(config_path))
    if memory is not None:
        return validate_staging_session_claim(memory[1]), None
    for claim_path in _candidate_staging_session_claim_paths(config_path):
        if not claim_path.exists():
            continue
        try:
            raw = json.loads(claim_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        try:
            return validate_staging_session_claim(raw), claim_path
        except ValueError:
            continue
    return empty_staging_session_claim(), None


def load_staging_session_token(config_path: str | Path | None = None) -> tuple[str | None, dict[str, object]]:
    memory_key = _memory_key(config_path)
    memory = _MEMORY_SESSIONS.get(memory_key)
    if memory is not None:
        token, claim = memory
        validated = validate_staging_session_claim(claim)
        if validated["auth_state"] == "linked" and _session_hash(token) == validated["session_hash"]:
            return token, validated
        return None, empty_staging_session_claim()

    claim, claim_path = _load_staging_session_claim_with_path(config_path)
    if claim.get("auth_state") != "linked" or claim.get("storage_backend") != "windows_dpapi_file":
        return None, claim
    secret_paths = list(_candidate_staging_session_secret_paths(config_path))
    if claim_path == legacy_staging_session_claim_path(config_path):
        legacy_secret = legacy_staging_session_secret_path(config_path)
        secret_paths = [legacy_secret, *[path for path in secret_paths if path != legacy_secret]]
    for secret_path in secret_paths:
        try:
            raw = secret_path.read_text(encoding="ascii").strip()
        except OSError:
            continue
        if not raw.startswith("dpapi:v1:"):
            continue
        try:
            protected = base64.b64decode(raw.removeprefix("dpapi:v1:").encode("ascii"), validate=True)
            token = _dpapi_unprotect(protected).decode("utf-8")
        except (ValueError, UnicodeDecodeError, StagingSessionStorageError):
            continue
        try:
            token = _validate_session_token(token)
        except StagingSessionStorageError:
            continue
        if _session_hash(token) != claim.get("session_hash"):
            continue
        return token, claim
    return None, claim


def clear_staging_session(config_path: str | Path | None = None) -> dict[str, object]:
    memory_removed = _MEMORY_SESSIONS.pop(_memory_key(config_path), None) is not None
    removed = memory_removed
    delete_failed = False
    for path in (
        *_candidate_staging_session_claim_paths(config_path),
        *_candidate_staging_session_secret_paths(config_path),
    ):
        try:
            if path.exists():
                path.unlink()
                removed = True
        except OSError:
            delete_failed = True
    report: dict[str, object] = {
        "schema_version": STAGING_SESSION_CLAIM_SCHEMA_VERSION,
        "ok": not delete_failed,
        "operation": "staging_logout",
        "session_removed": removed,
        "token_printed": False,
        "local_path_printed": False,
        "google_token_stored": False,
        "production_login_enabled": False,
    }
    if delete_failed:
        report["error"] = {
            "code": "staging_session_clear_failed",
            "message": "Staging session could not be fully cleared.",
            "local_path_printed": False,
            "token_printed": False,
        }
    return report


def build_staging_session_status(config_path: str | Path | None = None) -> dict[str, object]:
    token, claim = load_staging_session_token(config_path)
    return {
        "schema_version": STAGING_SESSION_CLAIM_SCHEMA_VERSION,
        "ok": True,
        "operation": "staging_session_status",
        "auth_state": claim.get("auth_state", "unauthenticated"),
        "session_available": token is not None,
        "origin": claim.get("origin", "not_configured"),
        "account_id": claim.get("account_id", "not-linked"),
        "redacted_email": claim.get("redacted_email", "not-linked"),
        "display_name": claim.get("display_name", "not-linked"),
        "expires_at": claim.get("expires_at"),
        "scopes": claim.get("scopes", []),
        "session_hash": claim.get("session_hash"),
        "storage_backend": claim.get("storage_backend", "none"),
        "token_printed": False,
        "google_token_stored": False,
        "google_access_token_stored": False,
        "google_id_token_stored": False,
        "google_refresh_token_stored": False,
        "auth_code_stored": False,
        "plaintext_session_token_stored": False,
    }


def empty_staging_session_claim() -> dict[str, object]:
    return {
        "schema_version": STAGING_SESSION_CLAIM_SCHEMA_VERSION,
        "auth_state": "unauthenticated",
        "origin": "not_configured",
        "issued_at": None,
        "expires_at": None,
        "account_id": "not-linked",
        "redacted_email": "not-linked",
        "display_name": "not-linked",
        "scopes": [],
        "session_hash": None,
        "storage_backend": "none",
        "token_printed": False,
        "google_token_stored": False,
        "google_access_token_stored": False,
        "google_id_token_stored": False,
        "google_refresh_token_stored": False,
        "auth_code_stored": False,
        "plaintext_session_token_stored": False,
    }


def _validate_session_token(value: str) -> str:
    token = str(value or "").strip()
    if len(token) < 12 or len(token) > 4096:
        raise StagingSessionStorageError("staging_session_claim_invalid", "Staging session claim is invalid.")
    if any(ord(char) < 32 or ord(char) == 127 for char in token):
        raise StagingSessionStorageError("staging_session_claim_invalid", "Staging session claim is invalid.")
    if _TOKEN_KEY_RE.search(token):
        raise StagingSessionStorageError("staging_session_claim_invalid", "Staging session claim is invalid.")
    return token


def _session_hash(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _safe_scopes(scopes: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    raw = tuple(scopes or DEFAULT_SCOPES)
    safe = tuple(scope for scope in raw if isinstance(scope, str) and _SAFE_SCOPE_RE.fullmatch(scope))
    return safe or DEFAULT_SCOPES


def _safe_storage_backend(value: object) -> str:
    text = str(value or "none").strip().lower()
    if text in {"windows_dpapi_file", "memory_session_only", "none"}:
        return text
    return "none"


def _safe_public_text(value: object, *, fallback: str | None) -> str | None:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if _TOKEN_KEY_RE.search(text) or _LOCAL_PATH_RE.search(text) or not _SAFE_TEXT_RE.fullmatch(text):
        return fallback
    return text


def _contains_forbidden_secret_material(value: object, *, key: str = "") -> bool:
    allowed_false_keys = {
        "token_printed",
        "google_token_stored",
        "google_access_token_stored",
        "google_id_token_stored",
        "google_refresh_token_stored",
        "auth_code_stored",
        "plaintext_session_token_stored",
    }
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            nested_key_text = str(nested_key)
            if _TOKEN_KEY_RE.search(nested_key_text) and nested_key_text not in allowed_false_keys:
                return True
            if _contains_forbidden_secret_material(nested_value, key=nested_key_text):
                return True
    elif isinstance(value, list | tuple):
        return any(_contains_forbidden_secret_material(item, key=key) for item in value)
    else:
        if key in allowed_false_keys:
            return value is True
        if _TOKEN_KEY_RE.search(key) and str(value):
            return True
    return False


def _expired_state(auth_state: str, expires_at: object) -> str:
    if auth_state != "linked" or expires_at is None:
        return auth_state
    try:
        expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError:
        return auth_state
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return "expired" if expires <= datetime.now(UTC) else auth_state


def _memory_key(config_path: str | Path | None) -> str:
    return str(default_staging_session_claim_path(config_path))


def _dpapi_available() -> bool:
    return sys.platform.startswith("win")


class _DATA_BLOB(ctypes.Structure):
    _fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte)))


def _dpapi_protect(data: bytes) -> bytes:
    if not _dpapi_available():
        raise StagingSessionStorageError("secure_storage_unavailable", "Secure staging session storage is unavailable.")
    return _crypt_protect(data, protect=True)


def _dpapi_unprotect(data: bytes) -> bytes:
    if not _dpapi_available():
        raise StagingSessionStorageError("secure_storage_unavailable", "Secure staging session storage is unavailable.")
    return _crypt_protect(data, protect=False)


def _crypt_protect(data: bytes, *, protect: bool) -> bytes:
    in_buffer = ctypes.create_string_buffer(data)
    in_blob = _DATA_BLOB(len(data), ctypes.cast(in_buffer, ctypes.POINTER(ctypes.c_byte)))
    out_blob = _DATA_BLOB()
    entropy_data = b"YonerAI staging session v1"
    entropy_buffer = ctypes.create_string_buffer(entropy_data)
    entropy_blob = _DATA_BLOB(len(entropy_data), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_byte)))
    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    flags = 0
    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            ctypes.byref(entropy_blob),
            None,
            None,
            flags,
            ctypes.byref(out_blob),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            ctypes.byref(entropy_blob),
            None,
            None,
            flags,
            ctypes.byref(out_blob),
        )
    if not ok:
        raise StagingSessionStorageError("staging_session_dpapi_failed", "Windows DPAPI failed for staging session storage.")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def storage_capability() -> dict[str, object]:
    return {
        "secure_persistent_storage_available": _dpapi_available(),
        "preferred_backend": "windows_dpapi_file" if _dpapi_available() else "memory_session_only",
        "fallback_backend": "memory_session_only",
        "plaintext_file_storage_allowed": False,
        "project_file_storage_allowed": False,
    }
