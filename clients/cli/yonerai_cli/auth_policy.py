from __future__ import annotations

import os
import re
from typing import Mapping
from urllib.parse import urlparse


GOOGLE_AUTH_SCHEMA_VERSION = "yonerai-google-auth-contract/v0.1"
PRIVACY_STATUS_SCHEMA_VERSION = "yonerai-privacy-status/v0.1"
GOOGLE_OAUTH_SCOPES = ("openid", "email", "profile")
DEFAULT_GOOGLE_LOOPBACK_REDIRECT = "http://127.0.0.1:8765/oauth/google/callback"
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
    return {
        "schema_version": GOOGLE_AUTH_SCHEMA_VERSION,
        "ok": True,
        "configured": configured,
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
        "next_safe_command": "yonerai auth google login --dry-run --pretty",
        "actions_not_performed": _google_auth_non_actions(),
        "error": None if configured else _google_auth_unconfigured_error(client_id_configured, redirect_report),
    }


def build_google_login_dry_run(
    config: Mapping[str, object] | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
) -> dict[str, object]:
    source = os.environ if env is None else env
    status = build_google_auth_status(config, env=source)
    ok = bool(status["configured"])
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
        "error": status["error"],
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


def _client_id_configured(env: Mapping[str, str | None]) -> bool:
    value = str(env.get("YONERAI_GOOGLE_OAUTH_CLIENT_ID") or "").strip()
    return bool(value and _CLIENT_ID_RE.fullmatch(value))


def _loopback_redirect_report(redirect_uri: str) -> dict[str, object]:
    try:
        parsed = urlparse(redirect_uri)
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
