from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.transport import (  # noqa: E402
    LOCAL_DEV_RELAY_TRANSPORT_SCHEMA_VERSION,
    InMemoryRelayTransport,
)
from ora_core.hybrid.wire_contract import assert_public_safe_wire_payload  # noqa: E402


NOW = datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)


def _ready_transport() -> InMemoryRelayTransport:
    transport = InMemoryRelayTransport()
    transport.register_node(
        node_id="node-1",
        key_id="key-1",
        capabilities=("mock_search", "ledger"),
        handler=lambda body: b"response:" + body[:8],
        heartbeat_at=NOW,
    )
    transport.start_session(
        session_id="session-1",
        node_id="node-1",
        key_id="key-1",
        session_token="secret-session-token",
        capabilities=("mock_search",),
        expires_at=NOW + timedelta(minutes=10),
    )
    return transport


def test_in_memory_relay_transport_defaults_to_loopback_and_non_mutating() -> None:
    transport = InMemoryRelayTransport()
    report = transport.status_report()

    assert report["schema_version"] == LOCAL_DEV_RELAY_TRANSPORT_SCHEMA_VERSION
    assert report["ok"] is True
    assert report["bind_host"] == "127.0.0.1"
    assert report["loopback_only"] is True
    assert report["network_required"] is False
    assert report["process_started"] is False
    assert report["public_exposure_allowed"] is False
    assert report["message_body_persisted"] is False
    assert report["session_token_storage"] == "hash_only"


def test_transport_proxy_roundtrip_keeps_hashes_only() -> None:
    transport = _ready_transport()
    result = transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-1",
        capability="mock_search",
        body=b"request body must not persist",
        now=NOW,
    )
    payload = result.to_public_dict()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["ok"] is True
    assert payload["status"] == "completed"
    assert payload["request_body_hash"].startswith("sha256:")
    assert payload["response_body_hash"].startswith("sha256:")
    assert payload["request_body_persisted"] is False
    assert payload["response_body_persisted"] is False
    assert payload["raw_body_included"] is False
    assert payload["session_token_hash_only"] is True
    assert assert_public_safe_wire_payload(payload) == ()
    assert "secret-session-token" not in serialized
    assert "request body must not persist" not in serialized


def test_transport_denies_non_loopback_bind_without_leaking_configuration() -> None:
    transport = InMemoryRelayTransport(bind_host="0.0.0.0")
    result = transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-1",
        capability="mock_search",
        body=b"body",
        now=NOW,
    )
    report = transport.status_report()
    serialized = json.dumps({"report": report, "result": result.to_public_dict()}, sort_keys=True)

    assert report["ok"] is False
    assert report["bind_host"] == "non_loopback_redacted"
    assert result.status == "non_loopback_bind_denied"
    assert result.controlled_error is True
    assert "0.0.0.0" not in serialized


def test_transport_returns_controlled_errors_for_session_and_capability_failures() -> None:
    transport = _ready_transport()
    missing_session = transport.proxy_request(
        session_token="wrong-token",
        session_id="session-1",
        request_id="request-1",
        capability="mock_search",
        body=b"body",
        now=NOW,
    )
    wrong_capability = transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-2",
        capability="workspace_file_access",
        body=b"body",
        now=NOW,
    )
    whitespace_capability = transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-whitespace",
        capability="   ",
        body=b"body",
        now=NOW,
    )
    expired = transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-3",
        capability="mock_search",
        body=b"body",
        now=NOW + timedelta(hours=1),
    )

    assert missing_session.status == "invalid_session"
    assert missing_session.controlled_error is True
    assert wrong_capability.status == "capability_not_declared"
    assert wrong_capability.controlled_error is True
    assert whitespace_capability.capability == "unknown"
    assert whitespace_capability.status == "capability_not_declared"
    assert whitespace_capability.controlled_error is True
    assert expired.status == "expired_session"
    assert expired.controlled_error is True


def test_transport_rejects_revoked_session_wrong_node_key_stale_heartbeat_and_large_body() -> None:
    revoked_transport = _ready_transport()
    revoked_transport.revoke_session(session_token="secret-session-token", session_id="session-1")
    revoked = revoked_transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-revoked",
        capability="mock_search",
        body=b"body",
        now=NOW,
    )

    wrong_key_transport = InMemoryRelayTransport()
    wrong_key_transport.register_node(
        node_id="node-1",
        key_id="key-2",
        capabilities=("mock_search",),
        handler=lambda _body: b"ok",
        heartbeat_at=NOW,
    )
    wrong_key_transport.start_session(
        session_id="session-1",
        node_id="node-1",
        key_id="key-1",
        session_token="secret-session-token",
        capabilities=("mock_search",),
        expires_at=NOW + timedelta(minutes=10),
    )
    wrong_key = wrong_key_transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-wrong-key",
        capability="mock_search",
        body=b"body",
        now=NOW,
    )

    stale_transport = _ready_transport()
    stale = stale_transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-stale",
        capability="mock_search",
        body=b"body",
        now=NOW + timedelta(minutes=3),
    )

    large_transport = InMemoryRelayTransport(max_body_bytes=4)
    large = large_transport.proxy_request(
        session_token="secret-session-token",
        session_id="session-1",
        request_id="request-large",
        capability="mock_search",
        body=b"12345",
        now=NOW,
    )

    assert revoked.status == "revoked_session"
    assert wrong_key.status == "node_key_mismatch"
    assert stale.status == "stale_heartbeat"
    assert large.status == "body_too_large"
    assert all(item.controlled_error for item in (revoked, wrong_key, stale, large))
