from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping

from ..three_mode import ModeName
from .local_node_enrollment import (
    LocalNodeEnrollmentRequest,
    consume_pairing_code,
    create_pairing_challenge,
)
from .local_node_manifest import (
    build_test_local_node_manifest,
    generate_test_local_node_keypair,
    sign_local_node_manifest,
)
from .relay_status import build_relay_status_report
from .wire_contract import (
    LocalNodeCapabilityManifest as WireLocalNodeCapabilityManifest,
    LocalNodeSessionRef as WireLocalNodeSessionRef,
    build_local_node_capability_manifest,
    build_local_node_heartbeat,
    build_local_node_hello,
    build_local_node_session_ref,
    evaluate_wire_request,
)


HYBRID_RELAY_NODE_E2E_SCHEMA_VERSION = "yonerai-hybrid-relay-node-e2e/v0.1"


@dataclass(frozen=True)
class RelayHttpProxyFixture:
    request_id: str
    method: str
    path_category: str
    request_body_hash: str
    response_body_hash: str
    request_body_bytes: int
    response_body_bytes: int
    request_body_persisted: bool
    response_body_persisted: bool
    raw_body_included: bool
    message_type: str = "http_proxy"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


def build_local_dev_relay_node_e2e_report(
    env: Mapping[str, str] | None = None,
    *,
    requested_capability: str = "mock_search",
    session_state: str = "active",
    verified: bool = True,
    mode: ModeName = "official_hybrid_private",
    now: datetime | None = None,
) -> dict[str, object]:
    """Build a deterministic, public-safe Relay/Local Node E2E fixture.

    The report connects the public Hybrid Wire contract to the local-dev Relay
    status and pairing/session helpers. It performs no network calls and keeps
    request/response bodies represented only by hashes.
    """

    relay_status = build_relay_status_report(env)
    manifest = build_local_node_capability_manifest(signed_origin_verified=verified)
    session_ref = build_local_node_session_ref(state=session_state, signed_origin_verified=verified)
    trust_decision = evaluate_wire_request(
        manifest=manifest,
        session_ref=session_ref,
        requested_capability=requested_capability,
    )
    pairing = _build_pairing_probe(mode=mode, now=now)
    proxy_fixture = _build_proxy_fixture() if trust_decision.allowed_for_preview else None
    rejection_cases = _build_rejection_cases(manifest=manifest, session_ref=session_ref)

    ok = (
        bool(relay_status.get("ok"))
        and pairing["first_consume"]["accepted"] is True
        and pairing["reuse_consume"]["accepted"] is False
        and trust_decision.allowed_for_preview is True
        and rejection_cases["expired_session"]["state"] == "expired_session"
        and rejection_cases["revoked_session"]["state"] == "revoked_session"
        and rejection_cases["unverified_node"]["state"] == "unverified_node"
        and proxy_fixture is not None
        and proxy_fixture.raw_body_included is False
        and proxy_fixture.request_body_persisted is False
        and proxy_fixture.response_body_persisted is False
    )

    return {
        "schema_version": HYBRID_RELAY_NODE_E2E_SCHEMA_VERSION,
        "ok": ok,
        "mode": "local_dev_fixture",
        "network_required": False,
        "production_oracle_used": False,
        "official_cloud_runtime_implemented": False,
        "production_trust_material": False,
        "relay": {
            "schema_version": relay_status.get("schema_version"),
            "ok": relay_status.get("ok"),
            "loopback_only": _nested(relay_status, "relay", "loopback_only"),
            "process_started": _nested(relay_status, "relay", "process_started"),
            "public_exposure_allowed": _nested(relay_status, "relay", "public_exposure_allowed"),
            "message_body_persisted": _nested(relay_status, "relay", "message_body_persisted"),
            "pairing_code_storage": _nested(relay_status, "relay", "pairing_code_storage"),
            "session_token_storage": _nested(relay_status, "relay", "session_token_storage"),
        },
        "node_flow": {
            "hello": build_local_node_hello().to_public_dict(),
            "heartbeat": build_local_node_heartbeat().to_public_dict(),
            "capability_manifest": manifest.to_public_dict(),
            "session_ref": session_ref.to_public_dict(),
            "trust_decision": trust_decision.to_public_dict(),
        },
        "pairing": pairing,
        "http_proxy_fixture": proxy_fixture.to_public_dict() if proxy_fixture else None,
        "rejection_cases": rejection_cases,
        "actions_not_performed": [
            "no relay process start",
            "no node connector start",
            "no cloud runtime",
            "no production Oracle",
            "no network call",
            "no token output",
            "no pairing code output",
            "no message body persistence",
            "no remote execution",
        ],
    }


def _build_pairing_probe(*, mode: ModeName, now: datetime | None) -> dict[str, object]:
    current = now or datetime(2026, 5, 22, 0, 5, tzinfo=timezone.utc)
    issued_at = _format_datetime(current - timedelta(minutes=5))
    challenge_expires_at = _format_datetime(current + timedelta(minutes=5))
    session_expires_at = _format_datetime(current + timedelta(minutes=55))
    private_key_b64, public_key_b64 = generate_test_local_node_keypair()
    manifest = build_test_local_node_manifest(
        node_id="relay-node-e2e-fixture",
        issuer="local-dev-relay-node-e2e",
        issued_at=issued_at,
        expires_at=session_expires_at,
        capabilities=("local_tools",),
    )
    signed_manifest = sign_local_node_manifest(manifest, private_key_b64=private_key_b64)
    request = LocalNodeEnrollmentRequest(
        node_id=manifest.identity.node_id,
        key_id=signed_manifest.signature.key_id,
        mode=mode,
        requested_capabilities=manifest.capabilities,
    )
    challenge = create_pairing_challenge(
        request,
        pairing_code="123456",
        challenge_id="relay-node-e2e-pairing",
        issued_at=issued_at,
        expires_at=challenge_expires_at,
    )
    first = consume_pairing_code(
        challenge,
        pairing_code="123456",
        signed_manifest=signed_manifest,
        public_key_b64=public_key_b64,
        now=current,
        session_id="relay-node-e2e-session",
        session_token="relay-node-e2e-token",
        session_expires_at=session_expires_at,
    )
    reuse = consume_pairing_code(
        first.challenge,
        pairing_code="123456",
        signed_manifest=signed_manifest,
        public_key_b64=public_key_b64,
        now=current,
        session_id="relay-node-e2e-session-reuse",
        session_token="relay-node-e2e-token-reuse",
        session_expires_at=session_expires_at,
    )
    return {
        "pairing_code_hash_only": True,
        "pairing_code_plaintext_included": False,
        "session_token_hash_only": True,
        "session_token_plaintext_included": False,
        "first_consume": first.to_public_dict(),
        "reuse_consume": reuse.to_public_dict(),
    }


def _build_rejection_cases(
    *,
    manifest: WireLocalNodeCapabilityManifest,
    session_ref: WireLocalNodeSessionRef,
) -> dict[str, dict[str, object]]:
    return {
        "expired_session": evaluate_wire_request(
            manifest=manifest,
            session_ref=build_local_node_session_ref(state="expired"),
            requested_capability="mock_search",
        ).to_public_dict(),
        "revoked_session": evaluate_wire_request(
            manifest=manifest,
            session_ref=build_local_node_session_ref(state="revoked"),
            requested_capability="mock_search",
        ).to_public_dict(),
        "unverified_node": evaluate_wire_request(
            manifest=build_local_node_capability_manifest(signed_origin_verified=False),
            session_ref=session_ref,
            requested_capability="mock_search",
        ).to_public_dict(),
    }


def _build_proxy_fixture() -> RelayHttpProxyFixture:
    request_body = b'{"query":"local dev relay fixture"}'
    response_body = b'{"ok":true,"summary":"fixture response"}'
    return RelayHttpProxyFixture(
        request_id="relay-node-e2e-http-proxy",
        method="POST",
        path_category="loopback_node_api_fixture",
        request_body_hash=_sha256_prefixed(request_body),
        response_body_hash=_sha256_prefixed(response_body),
        request_body_bytes=len(request_body),
        response_body_bytes=len(response_body),
        request_body_persisted=False,
        response_body_persisted=False,
        raw_body_included=False,
    )


def _sha256_prefixed(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _nested(payload: Mapping[str, object], parent: str, key: str) -> object:
    value = payload.get(parent)
    if not isinstance(value, Mapping):
        return None
    return value.get(key)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
