from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from yonerai_cli.config import default_config_path


STAGING_AUTH_CLAIM_SCHEMA_VERSION = "yonerai-staging-auth-claim/v0.1"
_TOKEN_KEY_RE = re.compile(
    r"(^|[_\-.:\s])(access_token|id_token|refresh_token|token|secret|authorization|credential|password|auth_code|code)($|[_\-.:\s])",
    re.IGNORECASE,
)
_LOCAL_PATH_RE = re.compile(r"([A-Za-z]:\\|\\\\|/Users/|/home/|/root/)")
_SAFE_TEXT_RE = re.compile(r"^[A-Za-z0-9_.:@+\-*(),!\[\]&\s]{0,160}$")
_PUBLIC_ACCOUNT_REF_RE = re.compile(r"^staging-account-[a-f0-9]{16}$")


def default_staging_auth_claim_path(config_path: str | Path | None = None) -> Path:
    base = Path(config_path).expanduser() if config_path is not None else default_config_path()
    if config_path is None and not str(os.environ.get("YONERAI_CLI_CONFIG_PATH") or "").strip():
        return base.with_name("staging-auth-claim.json")
    return base.with_name(f"{base.stem}.staging-auth-claim.json")


def empty_staging_auth_claim() -> dict[str, object]:
    return {
        "schema_version": STAGING_AUTH_CLAIM_SCHEMA_VERSION,
        "auth_state": "unauthenticated",
        "origin": "not_configured",
        "linked_at": None,
        "expires_at": None,
        "account": {
            "account_ref": "not-linked",
            "display_name": "not-linked",
            "email_redacted": "not-linked",
            "raw_email_stored": False,
            "raw_subject_stored": False,
        },
        "storage": _storage_boundary(),
    }


def load_staging_auth_claim(path: str | Path | None = None) -> dict[str, object]:
    claim_path = default_staging_auth_claim_path(path) if path is None or _looks_like_config_path(path) else Path(path).expanduser()
    if not claim_path.exists():
        return empty_staging_auth_claim()
    try:
        raw = json.loads(claim_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_staging_auth_claim()
    if not isinstance(raw, dict):
        return empty_staging_auth_claim()
    try:
        return validate_staging_auth_claim(raw)
    except ValueError:
        return empty_staging_auth_claim()


def save_staging_auth_claim(
    claim: Mapping[str, object],
    *,
    config_path: str | Path | None = None,
    claim_path: str | Path | None = None,
) -> dict[str, object]:
    validated = validate_staging_auth_claim(claim)
    target = Path(claim_path).expanduser() if claim_path is not None else default_staging_auth_claim_path(config_path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(validated, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ValueError("staging auth claim could not be written") from exc
    return validated


def build_staging_auth_claim(
    *,
    origin: str,
    expires_at: object = None,
    account: Mapping[str, object] | None = None,
) -> dict[str, object]:
    safe_account = sanitize_staging_account(account or {})
    return validate_staging_auth_claim(
        {
            "schema_version": STAGING_AUTH_CLAIM_SCHEMA_VERSION,
            "auth_state": "linked",
            "origin": _safe_public_text(origin, fallback="configured"),
            "linked_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "expires_at": _safe_public_text(expires_at, fallback=None),
            "account": safe_account,
            "storage": _storage_boundary(),
        }
    )


def sanitize_staging_account(account: Mapping[str, object]) -> dict[str, object]:
    raw_email = _first_text(account, ("email_redacted", "display_email_redacted", "email"))
    raw_name = _first_text(account, ("display_name", "name", "login", "account_name"))
    raw_ref = _first_text(account, ("account_ref", "subject_ref", "account_id", "sub", "id", "user_id"))
    return {
        "account_ref": _safe_account_ref(raw_ref or raw_email or raw_name),
        "display_name": _safe_public_text(raw_name, fallback="linked staging account"),
        "email_redacted": _redact_email(raw_email),
        "raw_email_stored": False,
        "raw_subject_stored": False,
    }


def validate_staging_auth_claim(claim: Mapping[str, object]) -> dict[str, object]:
    serialized = json.dumps(claim, ensure_ascii=False, sort_keys=True)
    if _contains_forbidden_secret_material(claim):
        raise ValueError("staging auth claim contains token-like content")
    if _LOCAL_PATH_RE.search(serialized):
        raise ValueError("staging auth claim contains a local path")
    auth_state = str(claim.get("auth_state") or "unauthenticated")
    if auth_state not in {"unauthenticated", "pending", "linked", "expired", "revoked"}:
        raise ValueError("staging auth claim auth_state is invalid")
    account = claim.get("account") if isinstance(claim.get("account"), Mapping) else {}
    storage = claim.get("storage") if isinstance(claim.get("storage"), Mapping) else {}
    validated = {
        "schema_version": STAGING_AUTH_CLAIM_SCHEMA_VERSION,
        "auth_state": auth_state,
        "origin": _safe_public_text(claim.get("origin"), fallback="not_configured"),
        "linked_at": _safe_public_text(claim.get("linked_at"), fallback=None),
        "expires_at": _safe_public_text(claim.get("expires_at"), fallback=None),
        "account": {
            "account_ref": _safe_account_ref(account.get("account_ref")),
            "display_name": _safe_public_text(account.get("display_name"), fallback="linked staging account"),
            "email_redacted": _redact_email(account.get("email_redacted")),
            "raw_email_stored": False,
            "raw_subject_stored": False,
        },
        "storage": {
            "google_token_stored": False,
            "refresh_token_stored": False,
            "staging_session_token_stored": False,
            "provider_key_stored": False,
            "plaintext_secret_stored": False,
        },
    }
    for key, value in _storage_boundary().items():
        if storage.get(key) is True:
            raise ValueError("staging auth claim attempted to store a secret")
        validated["storage"][key] = bool(value)
    return validated


def _contains_forbidden_secret_material(value: object, *, key: str = "") -> bool:
    allowed_secret_boundary_keys = set(_storage_boundary())
    if isinstance(value, Mapping):
        for nested_key, nested_value in value.items():
            nested_key_text = str(nested_key)
            if _TOKEN_KEY_RE.search(nested_key_text) and nested_key_text not in allowed_secret_boundary_keys:
                return True
            if _contains_forbidden_secret_material(nested_value, key=nested_key_text):
                return True
    elif isinstance(value, list | tuple):
        return any(_contains_forbidden_secret_material(item, key=key) for item in value)
    else:
        text = str(value)
        if key in allowed_secret_boundary_keys:
            return value is True
        if _TOKEN_KEY_RE.search(key) and text:
            return True
    return False


def _storage_boundary() -> dict[str, bool]:
    return {
        "google_token_stored": False,
        "refresh_token_stored": False,
        "staging_session_token_stored": False,
        "provider_key_stored": False,
        "plaintext_secret_stored": False,
    }


def _first_text(account: Mapping[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = account.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return ""


def _redact_email(value: object) -> str:
    text = _safe_public_text(value, fallback="not-linked")
    if "@" not in text:
        return text
    local, domain = text.split("@", 1)
    if not local or not domain:
        return "redacted"
    return f"{local[:1]}***@{domain}"


def _safe_account_ref(value: object) -> str:
    text = _safe_public_text(value, fallback="linked-staging-account")
    if text in {"not-linked", "linked-staging-account"}:
        return text
    if isinstance(text, str) and _PUBLIC_ACCOUNT_REF_RE.fullmatch(text):
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"staging-account-{digest}"


def _safe_public_text(value: object, *, fallback: str | None) -> str | None:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    if _TOKEN_KEY_RE.search(text) or _LOCAL_PATH_RE.search(text) or not _SAFE_TEXT_RE.fullmatch(text):
        return fallback
    return text


def _looks_like_config_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() == ".json" and Path(path).name != "staging-auth-claim.json"
