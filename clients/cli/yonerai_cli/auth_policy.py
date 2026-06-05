from __future__ import annotations

import os
import secrets
import re
from typing import Mapping
from urllib.parse import quote, urlparse


GOOGLE_AUTH_SCHEMA_VERSION = "yonerai-google-auth-contract/v0.1"
PRIVACY_STATUS_SCHEMA_VERSION = "yonerai-privacy-status/v0.1"
GOOGLE_OAUTH_SCOPES = ("openid", "email", "profile")
DEFAULT_GOOGLE_LOOPBACK_REDIRECT = "http://127.0.0.1:8765/oauth/google/callback"
STAGING_AUTH_ORIGIN_ENV_KEYS = ("YONERAI_STAGING_AUTH_ORIGIN", "YONERAI_OFFICIAL_API_STAGING_ORIGIN")
STAGING_AUTH_ALLOW_LOCALHOST_DEV_ENV = "YONERAI_STAGING_AUTH_ALLOW_LOCALHOST_DEV"
ALLOWED_STAGING_AUTH_HOSTS = frozenset(
    {
        "api-staging.yonerai.com",
        "staging.yonerai.com",
    }
)
LOCALHOST_DEV_AUTH_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
STAGING_AUTH_START_PATH = "/v1/auth/google/start"
STAGING_API_CONTRACT_ENDPOINTS = (
    ("GET", "/v1/account/me"),
    ("GET", "/v1/status"),
    ("GET", "/v1/rate-limit"),
    ("POST", "/v1/sync/preview"),
)
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{6,256}$")


def build_google_auth_status(
    config: Mapping[str, object] | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
) -> dict[str, object]:
    source = os.environ if env is None else env
    client_id_configured = _client_id_configured(source)
    redirect_report = _loopback_redirect_report(
        str(source.get("YONERAI_GOOGLE_OAUTH_REDIRECT_URI") or DEFAULT_GOOGLE_LOOPBACK_REDIRECT)
    )
    auth_enabled = bool((config or {}).get("google_auth_enabled", False))
    configured = client_id_configured and bool(redirect_report["valid"])
    staging = _staging_auth_origin_report(source)
    staging_ready = bool(staging["configured"]) and bool(redirect_report["valid"])
    preferred_lang = _preferred_lang(config)
    error = None
    if not (configured or staging_ready):
        error = _google_auth_unconfigured_error(
            client_id_configured or bool(staging["configured"]),
            redirect_report,
        )
    return {
        "schema_version": GOOGLE_AUTH_SCHEMA_VERSION,
        "ok": True,
        "configured": configured,
        "staging_login_available": bool(staging["configured"]),
        "staging": staging,
        "google_auth_enabled": auth_enabled,
        "production_login_enabled": False,
        "live_oauth_enabled": False,
        "client_id_configured": client_id_configured,
        "client_secret_required": False,
        "client_secret_supported": False,
        "client_id_printed": False,
        "token_printed": False,
        "flow": _google_flow_contract(redirect_report),
        "storage": _google_token_storage_contract(),
        "next_safe_command": (
            f"yonerai auth google login --staging --pretty --lang {preferred_lang}"
            if staging_ready
            else "yonerai auth google login --dry-run --pretty"
        ),
        "actions_not_performed": _google_auth_non_actions(),
        "error": error,
    }


def build_google_login_dry_run(
    config: Mapping[str, object] | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
) -> dict[str, object]:
    source = os.environ if env is None else env
    status = build_google_auth_status(config, env=source)
    ok = bool(status["configured"])
    client_id_configured = _client_id_configured(source)
    redirect_report = _loopback_redirect_report(
        str(source.get("YONERAI_GOOGLE_OAUTH_REDIRECT_URI") or DEFAULT_GOOGLE_LOOPBACK_REDIRECT)
    )
    dry_run_error = None if ok else _google_auth_unconfigured_error(client_id_configured, redirect_report)
    return {
        "schema_version": GOOGLE_AUTH_SCHEMA_VERSION,
        "ok": ok,
        "operation": "google_login_dry_run",
        "dry_run": True,
        "configured": status["configured"],
        "production_login_enabled": False,
        "live_oauth_started": False,
        "browser_opened": False,
        "authorization_url_printed": False,
        "state_generated": ok,
        "state_printed": False,
        "pkce_code_challenge_generated": ok,
        "pkce_code_verifier_printed": False,
        "token_printed": False,
        "client_id_printed": False,
        "flow": status["flow"],
        "storage": status["storage"],
        "actions_that_would_run": [
            "create a high-entropy state parameter",
            "create a PKCE code verifier and S256 code challenge",
            "start a loopback-only callback listener",
            "open the system browser for Google OAuth consent",
            "exchange the authorization code only after state and PKCE verification",
        ],
        "actions_not_performed": status["actions_not_performed"],
        "error": dry_run_error,
    }


def build_google_login_staging(
    config: Mapping[str, object] | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
) -> dict[str, object]:
    source = os.environ if env is None else env
    status = build_google_auth_status(config, env=source)
    staging = status["staging"] if isinstance(status.get("staging"), dict) else {}
    redirect_valid = bool(status["flow"]["redirect_valid"])
    configured = bool(staging.get("configured")) and redirect_valid
    state = secrets.token_urlsafe(32) if configured else None
    device_session_id = secrets.token_urlsafe(24) if configured else None
    redirect_uri = str(status["flow"]["redirect_uri"])
    authorization_url = None
    if configured and state and device_session_id:
        origin = str(staging["origin"])
        authorization_url = (
            f"{origin}{STAGING_AUTH_START_PATH}"
            f"?state={quote(state, safe='')}"
            f"&device_session_id={quote(device_session_id, safe='')}"
            f"&redirect_uri={quote(redirect_uri, safe='')}"
        )
    staging_error = staging.get("error") if not staging.get("configured") else None
    return {
        "schema_version": GOOGLE_AUTH_SCHEMA_VERSION,
        "ok": configured,
        "operation": "google_login_staging",
        "dry_run": False,
        "staging_login": True,
        "staging": staging,
        "configured": configured,
        "production_login_enabled": False,
        "live_oauth_started": False,
        "browser_opened": False,
        "authorization_url_printed": configured,
        "authorization_url": authorization_url,
        "state_generated": configured,
        "state_printed_separately": False,
        "device_session_id_generated": configured,
        "device_session_id_printed_separately": False,
        "pkce_code_challenge_generated": False,
        "pkce_code_verifier_printed": False,
        "token_printed": False,
        "client_id_printed": False,
        "client_secret_required": False,
        "client_secret_supported": False,
        "official_backend_called": False,
        "token_exchange_performed": False,
        "refresh_token_stored": False,
        "flow": status["flow"],
        "storage": status["storage"],
        "staging_api": _staging_api_contract(staging),
        "actions_that_would_run": [
            "use the staging backend as the OAuth client",
            "open or print a staging authorization URL",
            "require one-time state and device session correlation",
            "complete token exchange only inside the staging backend",
            "return a public-safe account link state in a future callback",
        ],
        "actions_not_performed": [
            "no Google client secret in the public CLI",
            "no production Google login",
            "no token exchange in the public CLI",
            "no token printing",
            "no refresh token plaintext storage",
            "no provider key storage",
            "no local private content upload",
            "no account sync performed",
        ],
        "error": None if configured else staging_error or status.get("error") or _staging_auth_unconfigured_error(),
    }


def build_privacy_status(config: Mapping[str, object] | None = None) -> dict[str, object]:
    values = dict(config or {})
    requested_data_sharing = bool(values.get("openai_data_sharing_enabled", False))
    return {
        "schema_version": PRIVACY_STATUS_SCHEMA_VERSION,
        "ok": True,
        "data_sharing": {
            "openai_shared_traffic_requested": requested_data_sharing,
            "openai_shared_traffic_enabled": False,
            "default": "off",
            "requires_explicit_opt_in": True,
            "runtime_supported": False,
            "reason": "public repo does not enable shared OpenAI traffic",
        },
        "private_content_exclusion": {
            "active": True,
            "excluded": [
                "private prompts",
                "workspace-local file content",
                "local memory records",
                "local node payloads",
                "provider keys",
                "secrets",
            ],
        },
        "ledger": {
            "shared_traffic_flag_recorded": True,
            "default_shared_traffic": False,
            "raw_prompt_persisted": False,
        },
        "quota": {
            "daily_quota_placeholder": True,
            "rate_limit_placeholder": True,
            "free_usage_claimed": False,
            "owner_or_org_eligibility_assumed": False,
        },
        "google_auth": {
            "production_login_enabled": False,
            "live_oauth_enabled": False,
            "token_storage_enabled": False,
        },
        "actions_not_performed": [
            "no OpenAI shared traffic enabled",
            "no private content shared",
            "no provider key storage",
            "no Google OAuth token storage",
            "no production Google login",
            "no telemetry ingestion",
        ],
    }


def validate_staging_redirect_location(
    location: str,
    expected_origin: str,
    *,
    env: Mapping[str, str | None] | None = None,
) -> dict[str, object]:
    source = os.environ if env is None else env
    localhost_dev_allowed = _env_truthy(source.get(STAGING_AUTH_ALLOW_LOCALHOST_DEV_ENV))
    origin_report = _validate_staging_auth_origin(expected_origin, localhost_dev_allowed=localhost_dev_allowed)
    if not origin_report["valid"]:
        return {"valid": False, "reason": "expected_origin_invalid", "location_printed": False}
    try:
        parsed = urlparse(location)
        expected = urlparse(str(origin_report["origin"]))
        parsed_port = parsed.port
        expected_port = expected.port
    except ValueError:
        return {"valid": False, "reason": "redirect_location_invalid", "location_printed": False}
    expected_scheme = expected.scheme
    valid = (
        parsed.scheme == expected_scheme
        and (parsed.hostname or "").lower() == (expected.hostname or "").lower()
        and (parsed_port or _default_port(parsed.scheme)) == (expected_port or _default_port(expected_scheme))
        and not parsed.username
        and not parsed.password
    )
    return {
        "valid": valid,
        "reason": None if valid else "redirect_host_not_allowed",
        "location_printed": valid,
        "expected_host": expected.hostname,
        "actual_host": (parsed.hostname or "invalid") if valid else "redacted",
    }


def _client_id_configured(env: Mapping[str, str | None]) -> bool:
    value = str(env.get("YONERAI_GOOGLE_OAUTH_CLIENT_ID") or "").strip()
    return bool(value and _CLIENT_ID_RE.fullmatch(value))


def _staging_auth_origin_report(env: Mapping[str, str | None]) -> dict[str, object]:
    selected_key = None
    raw_origin = ""
    for key in STAGING_AUTH_ORIGIN_ENV_KEYS:
        candidate = str(env.get(key) or "").strip()
        if candidate:
            selected_key = key
            raw_origin = candidate
            break
    if not raw_origin:
        return {
            "configured": False,
            "origin": "not_configured",
            "source": "env",
            "env_key": STAGING_AUTH_ORIGIN_ENV_KEYS[0],
            "allowed_hosts": sorted(ALLOWED_STAGING_AUTH_HOSTS),
            "production": False,
            "error": _staging_auth_unconfigured_error(),
        }
    localhost_dev_allowed = _env_truthy(env.get(STAGING_AUTH_ALLOW_LOCALHOST_DEV_ENV))
    report = _validate_staging_auth_origin(raw_origin, localhost_dev_allowed=localhost_dev_allowed)
    configured = bool(report["valid"])
    return {
        "configured": configured,
        "origin": report["origin"] if configured else "invalid_or_disallowed",
        "source": "env",
        "env_key": selected_key,
        "allowed_hosts": sorted(ALLOWED_STAGING_AUTH_HOSTS),
        "localhost_dev_allowed": localhost_dev_allowed,
        "production": False,
        "error": None if configured else {"code": report["reason"], "message": "Staging auth origin is not allowed."},
    }


def _validate_staging_auth_origin(origin: str, *, localhost_dev_allowed: bool = False) -> dict[str, object]:
    try:
        parsed = urlparse(origin)
        parsed_port = parsed.port
    except ValueError:
        return {"valid": False, "origin": "invalid_or_disallowed", "reason": "staging_origin_invalid"}
    host = (parsed.hostname or "").lower()
    unsafe_components = bool(parsed.username or parsed.password or parsed.query or parsed.fragment)
    localhost_dev = (
        localhost_dev_allowed
        and parsed.scheme in {"http", "https"}
        and host in LOCALHOST_DEV_AUTH_HOSTS
        and not unsafe_components
        and (parsed.path in {"", "/"})
    )
    valid = localhost_dev or (
        parsed.scheme == "https"
        and host in ALLOWED_STAGING_AUTH_HOSTS
        and not unsafe_components
        and (parsed_port in {None, 443})
        and (parsed.path in {"", "/"})
    )
    if not valid:
        reason = "staging_origin_must_be_allowlisted_https_host"
        if unsafe_components:
            reason = "staging_origin_must_not_include_credentials_query_or_fragment"
        elif parsed.scheme != "https":
            reason = "staging_origin_must_be_https"
        elif host not in ALLOWED_STAGING_AUTH_HOSTS:
            reason = "staging_origin_host_not_allowlisted"
        elif parsed_port not in {None, 443}:
            reason = "staging_origin_port_not_allowed"
        elif parsed.path not in {"", "/"}:
            reason = "staging_origin_path_not_allowed"
        return {"valid": False, "origin": "invalid_or_disallowed", "reason": reason}
    if localhost_dev:
        port = f":{parsed_port}" if parsed_port else ""
        normalized = f"{parsed.scheme}://{_url_host(host)}{port}"
        return {"valid": True, "origin": normalized, "reason": None, "localhost_dev": True}
    normalized = f"https://{host}"
    return {"valid": True, "origin": normalized, "reason": None}


def _env_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _preferred_lang(config: Mapping[str, object] | None) -> str:
    lang = str((config or {}).get("language") or "ja").strip().lower()
    return lang if lang in {"ja", "en"} else "ja"


def _default_port(scheme: str) -> int | None:
    if scheme == "http":
        return 80
    if scheme == "https":
        return 443
    return None


def _url_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _staging_auth_unconfigured_error() -> dict[str, str]:
    return {
        "code": "staging_auth_origin_not_configured",
        "message": "Set YONERAI_STAGING_AUTH_ORIGIN to an allowlisted staging YonerAI origin before using --staging.",
    }


def _staging_api_contract(staging: Mapping[str, object]) -> dict[str, object]:
    origin = str(staging.get("origin") or "not_configured") if staging.get("configured") else "not_configured"
    return {
        "configured": bool(staging.get("configured")),
        "origin": origin,
        "fixture_only": True,
        "network_fetch_default": "off",
        "allowed_methods_and_paths": [
            {"method": method, "path": path, "url": f"{origin}{path}" if origin != "not_configured" else "not_configured"}
            for method, path in STAGING_API_CONTRACT_ENDPOINTS
        ],
        "redirect_policy": "reject_unexpected_host",
        "private_content_exclusion": {
            "local_to_cloud_disabled_by_default": True,
            "local_private_content_upload": False,
            "local_file_content_upload": False,
            "local_memory_upload": False,
        },
    }


def _loopback_redirect_report(redirect_uri: str) -> dict[str, object]:
    try:
        parsed = urlparse(redirect_uri)
        parsed.port
    except ValueError:
        return {"valid": False, "uri": DEFAULT_GOOGLE_LOOPBACK_REDIRECT, "reason": "redirect_uri_invalid"}
    host = (parsed.hostname or "").lower()
    valid_host = host in {"127.0.0.1", "localhost", "::1"}
    unsafe_components = bool(parsed.username or parsed.password or parsed.query or parsed.fragment)
    valid = parsed.scheme == "http" and valid_host and bool(parsed.path) and not unsafe_components
    reason = None
    if not valid:
        reason = (
            "redirect_uri_must_not_include_credentials_query_or_fragment"
            if unsafe_components
            else "redirect_uri_must_be_loopback_http"
        )
    return {
        "valid": valid,
        "uri": redirect_uri if valid else DEFAULT_GOOGLE_LOOPBACK_REDIRECT,
        "loopback_only": valid_host,
        "scheme": parsed.scheme,
        "reason": reason,
    }


def _google_flow_contract(redirect_report: Mapping[str, object]) -> dict[str, object]:
    return {
        "type": "installed_app_oauth_pkce",
        "provider": "google",
        "scopes": list(GOOGLE_OAUTH_SCOPES),
        "minimal_scopes": True,
        "pkce_required": True,
        "pkce_method": "S256",
        "state_required": True,
        "loopback_redirect_only": True,
        "redirect_uri": redirect_report["uri"],
        "redirect_valid": redirect_report["valid"],
        "embedded_webview_allowed": False,
        "network_required_for_real_login": True,
        "dry_run_network_performed": False,
    }


def _google_token_storage_contract() -> dict[str, object]:
    return {
        "refresh_token_storage": "disabled_by_default",
        "access_token_storage": "disabled_by_default",
        "keyring_only_future": True,
        "plain_text_token_storage_allowed": False,
        "provider_key_storage_allowed": False,
    }


def _google_auth_non_actions() -> list[str]:
    return [
        "no live OAuth request",
        "no browser launch",
        "no embedded webview",
        "no token exchange",
        "no token printing",
        "no refresh token storage",
        "no provider key storage",
        "no production Google login",
    ]


def _google_auth_unconfigured_error(client_id_configured: bool, redirect_report: Mapping[str, object]) -> dict[str, object]:
    if not client_id_configured:
        return {
            "code": "google_oauth_client_not_configured",
            "message": "YONERAI_GOOGLE_OAUTH_CLIENT_ID is not configured; dry-run shows the contract only.",
        }
    return {
        "code": str(redirect_report.get("reason") or "google_oauth_redirect_not_configured"),
        "message": "Google OAuth redirect must be a loopback http redirect URI.",
    }
