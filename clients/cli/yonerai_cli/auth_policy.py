from __future__ import annotations

import os
import re
import webbrowser
from collections.abc import Callable
from typing import Mapping
from urllib.parse import urlparse

from yonerai_cli.staging_auth_bridge import (
    CLI_BRIDGE_POLL_PATH_TEMPLATE,
    CLI_BRIDGE_START_PATH,
    GOOGLE_BROWSER_START_PATH,
    GOOGLE_CALLBACK_PATH,
    HeaderJsonTransport,
    JsonTransport,
    StagingAuthBridgeError,
    poll_cli_bridge,
    start_cli_bridge_for_polling,
    wait_for_cli_bridge_link,
)
from yonerai_cli.services.auth_session_service import build_staging_auth_claim, load_staging_auth_claim
from yonerai_cli.services.staging_session_service import (
    build_staging_session_status,
    storage_capability,
)


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
STAGING_AUTH_START_PATH = GOOGLE_BROWSER_START_PATH
STAGING_API_CONTRACT_ENDPOINTS = (
    ("GET", "/v1/account/me"),
    ("GET", "/v1/status"),
    ("GET", "/v1/rate-limit"),
    ("POST", "/v1/sync/preview"),
    ("GET", GOOGLE_BROWSER_START_PATH),
    ("GET", GOOGLE_CALLBACK_PATH),
    ("POST", CLI_BRIDGE_START_PATH),
    ("GET", CLI_BRIDGE_POLL_PATH_TEMPLATE),
)
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{6,256}$")


def build_google_auth_status(
    config: Mapping[str, object] | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
) -> dict[str, object]:
    source = os.environ if env is None else env
    client_id_configured = _client_id_configured(source)
    redirect_report = _loopback_redirect_report(
        str(source.get("YONERAI_GOOGLE_OAUTH_REDIRECT_URI") or DEFAULT_GOOGLE_LOOPBACK_REDIRECT)
    )
    auth_enabled = bool((config or {}).get("google_auth_enabled", False))
    configured = client_id_configured and bool(redirect_report["valid"])
    staging = _staging_auth_origin_report(source)
    staging_claim = load_staging_auth_claim(claim_path)
    staging_session_claim = build_staging_session_status(claim_path)
    staging_ready = bool(staging["configured"]) and bool(redirect_report["valid"])
    preferred_lang = _preferred_lang(config)
    session_state = str(staging_session_claim.get("auth_state") or "unauthenticated")
    claim_state = str(staging_claim.get("auth_state") or "unauthenticated")
    effective_state = session_state if session_state in {"linked", "pending", "expired", "revoked"} else claim_state
    effective_account = (
        {
            "account_id": staging_session_claim.get("account_id"),
            "account_ref": staging_session_claim.get("account_id"),
            "display_name": staging_session_claim.get("display_name"),
            "email_redacted": staging_session_claim.get("redacted_email"),
            "raw_email_stored": False,
            "raw_subject_stored": False,
        }
        if effective_state in {"linked", "pending", "expired", "revoked"} and session_state in {"linked", "pending", "expired", "revoked"}
        else staging_claim.get("account")
    )
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
        "staging_session": staging_claim,
        "staging_session_claim": staging_session_claim,
        "staging_auth_state": effective_state,
        "staging_account": effective_account,
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
        "session_storage": storage_capability(),
        "next_safe_command": "yonerai login",
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
    bridge: bool = False,
    poll_request_id: str | None = None,
    timeout_seconds: float = 10.0,
    wait_linked: bool = False,
    open_browser: bool = False,
    max_wait_seconds: float = 120.0,
    poll_interval_seconds: float = 2.0,
    transport: JsonTransport | None = None,
    account_transport: HeaderJsonTransport | None = None,
    session_claim_handler: Callable[[str, Mapping[str, object], Mapping[str, object]], Mapping[str, object]] | None = None,
) -> dict[str, object]:
    source = os.environ if env is None else env
    status = build_google_auth_status(config, env=source)
    staging = status["staging"] if isinstance(status.get("staging"), dict) else {}
    redirect_valid = bool(status["flow"]["redirect_valid"])
    configured = bool(staging.get("configured")) and redirect_valid
    authorization_url = None
    bridge_report: dict[str, object] = {
        "supported": True,
        "network_called": False,
        "start_path": CLI_BRIDGE_START_PATH,
        "poll_path_template": CLI_BRIDGE_POLL_PATH_TEMPLATE,
        "browser_start_path": GOOGLE_BROWSER_START_PATH,
        "callback_path": GOOGLE_CALLBACK_PATH,
        "request_id": None,
        "poll_status": "not_started",
        "staging_session_received": False,
        "staging_session_token_printed": False,
        "waited_until_linked": False,
        "poll_attempts": 0,
        "account_me": None,
    }
    bridge_error: dict[str, object] | None = None
    browser_opened = False
    if configured:
        origin = str(staging["origin"])
        authorization_url = f"{origin}{STAGING_AUTH_START_PATH}"
        active_poll_url: str | None = None
        if bridge or poll_request_id:
            bridge_report["network_called"] = True
            try:
                if bridge:
                    started, active_poll_url = start_cli_bridge_for_polling(
                        origin,
                        timeout_seconds=timeout_seconds,
                        transport=transport,
                    )
                    bridge_report["start"] = started
                    bridge_report["request_id"] = started.get("request_id")
                    authorization_url = str(started.get("browser_start_url") or authorization_url)
                    if open_browser and authorization_url:
                        try:
                            browser_opened = bool(webbrowser.open(authorization_url))
                        except Exception:
                            browser_opened = False
                active_request_id = str(poll_request_id or bridge_report.get("request_id") or "")
                if active_request_id and wait_linked:
                    polled = wait_for_cli_bridge_link(
                        origin,
                        active_request_id,
                        timeout_seconds=timeout_seconds,
                        max_wait_seconds=max_wait_seconds,
                        poll_interval_seconds=poll_interval_seconds,
                        transport=transport,
                        account_transport=account_transport,
                        session_claim_handler=session_claim_handler,
                        poll_url=active_poll_url,
                    )
                    bridge_report["poll"] = polled
                    bridge_report["poll_status"] = polled.get("status")
                    bridge_report["request_id"] = polled.get("request_id")
                    bridge_report["staging_session_received"] = bool(polled.get("staging_session_received"))
                    bridge_report["linked_without_cli_session"] = bool(polled.get("linked_without_cli_session"))
                    bridge_report["linked_without_session_claim"] = bool(polled.get("linked_without_session_claim"))
                    bridge_report["waited_until_linked"] = bool(polled.get("waited_until_linked"))
                    bridge_report["poll_attempts"] = polled.get("poll_attempts", 0)
                    bridge_report["account_me"] = polled.get("account_me")
                elif poll_request_id:
                    polled = poll_cli_bridge(
                        origin,
                        poll_request_id,
                        poll_url=active_poll_url,
                        timeout_seconds=timeout_seconds,
                        transport=transport,
                    )
                    bridge_report["poll"] = polled
                    bridge_report["poll_status"] = polled.get("status")
                    bridge_report["request_id"] = polled.get("request_id")
                    bridge_report["staging_session_received"] = bool(polled.get("staging_session_received"))
                    bridge_report["linked_without_cli_session"] = bool(polled.get("linked_without_cli_session"))
                    bridge_report["linked_without_session_claim"] = bool(polled.get("linked_without_session_claim"))
            except StagingAuthBridgeError as exc:
                bridge_error = exc.to_safe_error()
                authorization_url = None
        if poll_request_id and not bridge:
            authorization_url = None
    staging_error = staging.get("error") if not staging.get("configured") else None
    account_me = bridge_report.get("account_me") if isinstance(bridge_report.get("account_me"), Mapping) else {}
    account_validation_failed = bool(
        wait_linked
        and bridge_report.get("staging_session_received") is True
        and account_me
        and account_me.get("ok") is not True
    )
    missing_cli_session = bool(bridge_report.get("linked_without_cli_session") is True)
    wait_link_failed = bool(
        bridge_report["network_called"]
        and (
            (wait_linked and (not bridge_report["waited_until_linked"] or account_validation_failed))
            or missing_cli_session
        )
    )
    if account_validation_failed:
        wait_error_code = "staging_account_validation_failed"
        wait_error_message = "Staging account validation failed after the bridge linked."
    elif missing_cli_session:
        wait_error_code = "staging_cli_session_unavailable"
        wait_error_message = (
            "Staging browser login linked, but the backend did not issue a CLI bearer session. "
            "Run `yonerai login` after the staging auth bridge contract is updated."
        )
    else:
        wait_error_code = "staging_link_not_completed"
        wait_error_message = "Staging CLI bridge did not complete before the wait timeout."
    wait_link_error = (
        {
            "code": wait_error_code,
            "message": wait_error_message,
            "status_code": None,
            "private_endpoint_printed": False,
            "token_printed": False,
        }
        if wait_link_failed
        else None
    )
    ok = configured and bridge_error is None and not wait_link_failed
    authorization_url_printed = configured and bridge_error is None and authorization_url is not None
    linked_claim = (
        None
        if (account_validation_failed or missing_cli_session)
        else _linked_claim_from_validated_bridge(staging, bridge_report)
    )
    return {
        "schema_version": GOOGLE_AUTH_SCHEMA_VERSION,
        "ok": ok,
        "operation": "google_login_staging",
        "dry_run": False,
        "staging_login": True,
        "staging_login_available": bool(staging.get("configured")),
        "staging": staging,
        "configured": configured,
        "production_login_enabled": False,
        "live_oauth_started": False,
        "browser_opened": browser_opened,
        "browser_open_requested": bool(open_browser),
        "authorization_url_printed": authorization_url_printed,
        "authorization_url": authorization_url,
        "state_generated": False,
        "state_printed_separately": False,
        "device_session_id_generated": False,
        "device_session_id_printed_separately": False,
        "pkce_code_challenge_generated": False,
        "pkce_code_verifier_printed": False,
        "token_printed": False,
        "client_id_printed": False,
        "client_secret_required": False,
        "client_secret_supported": False,
        "official_backend_called": bool(bridge_report["network_called"]),
        "cli_bridge": bridge_report,
        "staging_linked": bool(linked_claim),
        "staging_linked_claim": linked_claim,
        "staging_claim_saved": False,
        "staging_session_token_stored": False,
        "next_safe_command": "yonerai login",
        "staging_session_claim_stored": bool(
            isinstance(bridge_report.get("poll"), Mapping)
            and isinstance(bridge_report["poll"].get("session_storage"), Mapping)
            and bridge_report["poll"]["session_storage"].get("stored") is True
        ),
        "staging_session_storage": (
            bridge_report["poll"].get("session_storage")
            if isinstance(bridge_report.get("poll"), Mapping)
            and isinstance(bridge_report["poll"].get("session_storage"), Mapping)
            else {}
        ),
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
        "error": bridge_error
        if bridge_error
        else wait_link_error
        if wait_link_error
        else None
        if configured
        else staging_error or status.get("error") or _staging_auth_unconfigured_error(),
    }


def _linked_claim_from_validated_bridge(
    staging: Mapping[str, object],
    bridge_report: Mapping[str, object],
) -> dict[str, object] | None:
    if bridge_report.get("staging_session_received") is not True:
        return None
    account_me = bridge_report.get("account_me") if isinstance(bridge_report.get("account_me"), Mapping) else {}
    if account_me.get("ok") is not True:
        return None
    poll = bridge_report.get("poll") if isinstance(bridge_report.get("poll"), Mapping) else {}
    account_me_account = account_me.get("account") if isinstance(account_me.get("account"), Mapping) else {}
    return build_staging_auth_claim(
        origin=str(staging.get("origin") or "configured"),
        expires_at=poll.get("expires_at"),
        account=account_me_account if isinstance(account_me_account, Mapping) else {},
    )


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
        "network_fetch_when": "yonerai login or explicit --bridge/--poll-request-id",
        "next_e2e_command": "yonerai login",
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
