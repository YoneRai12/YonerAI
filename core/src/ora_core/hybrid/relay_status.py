from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


RELAY_STATUS_SCHEMA_VERSION = "yonerai-relay-status/v0.1"
DEFAULT_RELAY_HOST = "127.0.0.1"
DEFAULT_RELAY_PORT = 9010
DEFAULT_RELAY_URL = f"ws://{DEFAULT_RELAY_HOST}:{DEFAULT_RELAY_PORT}"
DEFAULT_NODE_API_BASE_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class RelayLocalDevLimits:
    max_msg_bytes: int = 1_048_576
    max_http_body_bytes: int = 262_144
    max_pending: int = 64
    client_timeout_sec: int = 35
    pair_ttl_sec: int = 120
    session_ttl_sec: int = 3_600

    def to_public_dict(self) -> dict[str, int]:
        return {
            "max_msg_bytes": self.max_msg_bytes,
            "max_http_body_bytes": self.max_http_body_bytes,
            "max_pending": self.max_pending,
            "client_timeout_sec": self.client_timeout_sec,
            "pair_ttl_sec": self.pair_ttl_sec,
            "session_ttl_sec": self.session_ttl_sec,
        }


def build_relay_status_report(env: Mapping[str, str] | None = None) -> dict[str, object]:
    values = env or {}
    host = _env_str(values, "ORA_RELAY_HOST", DEFAULT_RELAY_HOST)
    port = _env_int(values, "ORA_RELAY_PORT", DEFAULT_RELAY_PORT)
    expose_mode = _env_str(values, "ORA_RELAY_EXPOSE_MODE", "none").lower()
    relay_url = _coerce_ws_base_url(_env_str(values, "ORA_RELAY_URL", DEFAULT_RELAY_URL))
    node_api_base_url = _env_str(values, "ORA_NODE_API_BASE_URL", DEFAULT_NODE_API_BASE_URL)

    host_loopback = _is_loopback_host(host)
    relay_url_auto = relay_url.lower() == "auto"
    relay_url_loopback = relay_url_auto or _is_loopback_url(relay_url)
    node_api_loopback = _is_loopback_url(node_api_base_url)
    public_exposure_requested = expose_mode not in {"", "none", "off", "false", "0"}
    ok = host_loopback and relay_url_loopback and node_api_loopback and not public_exposure_requested

    return {
        "schema_version": RELAY_STATUS_SCHEMA_VERSION,
        "command": "yonerai relay status",
        "ok": ok,
        "mode": "local_dev_fixture",
        "relay": {
            "host": host if host_loopback else "non_loopback_redacted",
            "port": port,
            "default_url": DEFAULT_RELAY_URL,
            "configured_url_category": _relay_url_category(relay_url_loopback=relay_url_loopback, relay_url_auto=relay_url_auto),
            "loopback_default": True,
            "loopback_only": host_loopback and relay_url_loopback,
            "health_probe_performed": False,
            "process_started": False,
            "quick_tunnel_enabled": False,
            "public_exposure_requested": public_exposure_requested,
            "public_exposure_allowed": False,
            "message_body_persisted": False,
            "state_persistence": "memory_only",
            "pairing_code_storage": "hash_only",
            "pairing_code_plaintext_included": False,
            "session_token_storage": "hash_only",
            "session_token_plaintext_included": False,
        },
        "node_connector": {
            "default_relay_url": DEFAULT_RELAY_URL,
            "relay_url_category": _relay_url_category(relay_url_loopback=relay_url_loopback, relay_url_auto=relay_url_auto),
            "default_node_api_base_url": DEFAULT_NODE_API_BASE_URL,
            "node_api_base_url_category": "loopback" if node_api_loopback else "non_loopback_blocked",
            "node_api_loopback_only": node_api_loopback,
            "connector_started": False,
            "pairing_code_printed": False,
        },
        "limits": RelayLocalDevLimits(
            max_msg_bytes=_env_int(values, "ORA_RELAY_MAX_MSG_BYTES", RelayLocalDevLimits.max_msg_bytes),
            max_http_body_bytes=_env_int(
                values,
                "ORA_RELAY_MAX_HTTP_BODY_BYTES",
                RelayLocalDevLimits.max_http_body_bytes,
            ),
            max_pending=_env_int(values, "ORA_RELAY_MAX_PENDING", RelayLocalDevLimits.max_pending),
            client_timeout_sec=_env_int(
                values,
                "ORA_RELAY_CLIENT_TIMEOUT_SEC",
                RelayLocalDevLimits.client_timeout_sec,
            ),
            pair_ttl_sec=_env_int(values, "ORA_RELAY_PAIR_TTL_SEC", RelayLocalDevLimits.pair_ttl_sec),
            session_ttl_sec=_env_int(values, "ORA_RELAY_SESSION_TTL_SEC", RelayLocalDevLimits.session_ttl_sec),
        ).to_public_dict(),
        "endpoints": ["/health", "/api/pair", "/ws/node", "/ws/client"],
        "actions_not_performed": [
            "no relay process start",
            "no node connector start",
            "no cloudflared start",
            "no public tunnel",
            "no network probe",
            "no token output",
            "no pairing code output",
            "no message body persistence",
            "no remote execution",
        ],
    }


def _env_str(env: Mapping[str, str], name: str, default: str) -> str:
    value = str(env.get(name) or "").strip()
    return value or default


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    value = str(env.get(name) or "").strip()
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _coerce_ws_base_url(url: str) -> str:
    value = (url or "").strip().rstrip("/")
    if value.startswith("https://"):
        return "wss://" + value[len("https://") :]
    if value.startswith("http://"):
        return "ws://" + value[len("http://") :]
    return value


def _is_loopback_url(url: str) -> bool:
    value = (url or "").strip()
    if not value:
        return False
    if "://" not in value and not value.startswith("//"):
        value = f"//{value}"
    parsed = urlparse(value)
    return _is_loopback_host(parsed.hostname or "")


def _is_loopback_host(host: str) -> bool:
    value = (host or "").strip().strip("[]").lower()
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _relay_url_category(*, relay_url_loopback: bool, relay_url_auto: bool) -> str:
    if relay_url_auto:
        return "auto_unresolved_no_probe"
    return "loopback" if relay_url_loopback else "non_loopback_blocked"
