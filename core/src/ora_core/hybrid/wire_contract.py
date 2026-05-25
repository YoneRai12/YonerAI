from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Mapping

from ora_core.execution.ledger import new_run_id, safe_summary

from .node_posture import NODE_POSTURE_SCHEMA_VERSION, evaluate_local_node_posture
from .extension_manifest import (
    EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION,
    build_extension_capability_manifest,
    evaluate_extension_capability_manifest,
)


HYBRID_WIRE_CONTRACT_VERSION = "yonerai-hybrid-wire-contract/v0.3"
HYBRID_WIRE_COMPATIBLE_VERSIONS = (
    "yonerai-hybrid-wire-contract/v0.1",
    "yonerai-hybrid-wire-contract/v0.2",
    HYBRID_WIRE_CONTRACT_VERSION,
)
HYBRID_WIRE_STUB_NODE_ID = "local-node-dev-fixture"
HYBRID_WIRE_STUB_SESSION_ID = "local-node-session-dev-fixture"
HYBRID_WIRE_STUB_LEASE_ID = "local-node-lease-dev-fixture"
HYBRID_WIRE_STUB_TOKEN_HASH = "sha256:local-node-session-token-dev-fixture-hash"
HYBRID_WIRE_STUB_MANIFEST_EXPIRES_AT = "2100-01-01T00:00:00Z"
HYBRID_WIRE_STUB_SESSION_EXPIRES_AT = "2100-01-01T01:00:00Z"

WireCapabilityName = Literal[
    "local_model",
    "workspace_file_access",
    "mock_search",
    "tool_boundary",
    "ledger",
    "dangerous_operation",
]
TrustSessionState = Literal[
    "missing_node",
    "unverified_node",
    "verified_test_node",
    "expired_session",
    "revoked_session",
    "capability_not_declared",
    "approval_required",
]
HYBRID_WIRE_REQUIRED_TRUST_STATES: tuple[TrustSessionState, ...] = (
    "missing_node",
    "unverified_node",
    "verified_test_node",
    "expired_session",
    "revoked_session",
    "capability_not_declared",
    "approval_required",
)

_ROUTE_CAPABILITY_ALIASES: dict[str, str] = {
    "local_model": "local_tools",
    "workspace_file_access": "private_files",
    "mock_search": "local_tools",
    "tool_boundary": "local_tools",
    "ledger": "local_tools",
    "dangerous_operation": "dangerous_operations",
}
_FORBIDDEN_WIRE_KEYS = {
    "raw_prompt",
    "prompt",
    "provider_key",
    "api_key",
    "secret",
    "access_token",
    "token",
    "password",
    "auth",
    "authorization",
}
_SECRET_LIKE_RE = re.compile(r"\b(?:api|private)[\s_-]*key\b|sk-[a-z0-9_-]+", re.IGNORECASE)
_LOCAL_PATH_MARKERS = ("c:\\users\\", "c:/users/", "/users/", "/home/", "/root/")


@dataclass(frozen=True)
class LocalNodeCapability:
    name: WireCapabilityName
    enabled: bool
    approval_required: bool
    route_capability: str
    description: str
    disabled_reason: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LocalNodeHello:
    node_id: str
    contract_version: str
    mode: str
    loopback_only: bool
    non_production: bool
    production_trust_material: bool
    status: str
    lease_required: bool
    audit_log_required: bool
    schema_name: str = "LocalNodeHello"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LocalNodeHeartbeat:
    node_id: str
    session_id: str
    issued_at: str
    healthy: bool
    loopback_only: bool
    production_runtime: bool
    status: str
    lease_id: str
    lease_expires_at: str
    audit_cursor: str
    message_body_persisted: bool
    schema_name: str = "LocalNodeHeartbeat"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LocalNodeCapabilityManifest:
    manifest_id: str
    node_id: str
    issued_at: str
    expires_at: str
    capabilities: tuple[LocalNodeCapability, ...]
    loopback_only: bool
    non_production: bool
    signed_origin_verified: bool
    production_trust_material: bool
    manifest_status: str
    lease_policy: str
    audit_event_schema: str
    message_body_persistence: str
    schema_name: str = "LocalNodeCapabilityManifest"

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = [capability.to_public_dict() for capability in self.capabilities]
        return payload


@dataclass(frozen=True)
class LocalNodeSessionRef:
    session_id: str
    node_id: str
    manifest_id: str
    issued_at: str
    expires_at: str
    state: str
    signed_origin_verified: bool
    non_production: bool
    bearer_token_included: bool
    production_trust_material: bool
    lease_id: str
    lease_expires_at: str
    token_hash: str
    token_hash_algorithm: str
    bearer_token_hash_only: bool
    message_body_persisted: bool
    schema_name: str = "LocalNodeSessionRef"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LocalNodeRunEnvelope:
    run_id: str
    session_ref: LocalNodeSessionRef
    capability: WireCapabilityName
    task_summary: str
    payload_summary: str
    raw_prompt_included: bool
    provider_key_included: bool
    local_path_included: bool
    created_at: str
    lease_id: str
    audit_event_id: str
    audit_summary: str
    message_body_persisted: bool
    schema_name: str = "LocalNodeRunEnvelope"

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["session_ref"] = self.session_ref.to_public_dict()
        return payload


@dataclass(frozen=True)
class LocalNodeRunResult:
    run_id: str
    status: str
    result_summary: str
    raw_result_included: bool
    local_path_included: bool
    artifacts: tuple[dict[str, object], ...]
    completed_at: str
    audit_event_id: str
    message_body_persisted: bool
    schema_name: str = "LocalNodeRunResult"

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["artifacts"] = list(self.artifacts)
        return payload


@dataclass(frozen=True)
class LocalNodeError:
    code: str
    message: str
    retryable: bool
    public_safe: bool
    raw_exception_included: bool
    status: str
    audit_event_id: str
    schema_name: str = "LocalNodeError"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OfficialOrchestrationStubRequest:
    request_id: str
    requested_capability: str
    task_summary: str
    session_ref: LocalNodeSessionRef | None
    route_strategy: str
    approval_required: bool
    audit_event_required: bool
    args_hash_required: bool
    private_file_content_included: bool
    raw_prompt_included: bool
    provider_key_included: bool
    dry_run: bool
    official_cloud_runtime_implemented: bool
    production_oracle_used: bool
    network_required: bool
    schema_name: str = "OfficialOrchestrationStubRequest"

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["session_ref"] = self.session_ref.to_public_dict() if self.session_ref else None
        return payload


@dataclass(frozen=True)
class OfficialOrchestrationStubResponse:
    response_id: str
    request_id: str
    status: str
    route_strategy: str
    accepted_for_private_implementation: bool
    public_repo_execution_available: bool
    disabled_reason: str
    controlled_error_schema: str
    approval_required: bool
    audit_event_required: bool
    args_hash_required: bool
    private_file_content_included: bool
    raw_prompt_included: bool
    provider_key_included: bool
    message_body_persisted: bool
    official_cloud_runtime_implemented: bool
    production_oracle_used: bool
    network_required: bool
    schema_name: str = "OfficialOrchestrationStubResponse"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class HybridWireTrustDecision:
    state: TrustSessionState
    requested_capability: str
    allowed_for_preview: bool
    execute_allowed: bool
    approval_required: bool
    production_trust_material: bool
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _capabilities() -> tuple[LocalNodeCapability, ...]:
    return (
        LocalNodeCapability(
            name="local_model",
            enabled=True,
            approval_required=True,
            route_capability="local_tools",
            description="Loopback-only local model execution contract; live use still requires explicit opt-in.",
        ),
        LocalNodeCapability(
            name="workspace_file_access",
            enabled=True,
            approval_required=True,
            route_capability="private_files",
            description="Explicit selected file inside workspace allowlist only; no folder crawl or arbitrary path.",
        ),
        LocalNodeCapability(
            name="mock_search",
            enabled=True,
            approval_required=False,
            route_capability="local_tools",
            description="Mock search fixture contract; no live web search by default.",
        ),
        LocalNodeCapability(
            name="tool_boundary",
            enabled=True,
            approval_required=True,
            route_capability="local_tools",
            description="Tool boundary planning contract; no arbitrary shell execution.",
        ),
        LocalNodeCapability(
            name="ledger",
            enabled=True,
            approval_required=False,
            route_capability="local_tools",
            description="Redacted local run ledger reference contract; not cloud memory.",
        ),
        LocalNodeCapability(
            name="dangerous_operation",
            enabled=False,
            approval_required=True,
            route_capability="dangerous_operations",
            description="Dangerous operation placeholder; disabled in public repo and requires owner approval.",
            disabled_reason="dangerous_operation_disabled_in_public_repo",
        ),
    )


def build_local_node_hello(*, node_id: str = HYBRID_WIRE_STUB_NODE_ID) -> LocalNodeHello:
    return LocalNodeHello(
        node_id=node_id,
        contract_version=HYBRID_WIRE_CONTRACT_VERSION,
        mode="official_hybrid_private",
        loopback_only=True,
        non_production=True,
        production_trust_material=False,
        status="fixture_ready",
        lease_required=True,
        audit_log_required=True,
    )


def build_local_node_capability_manifest(
    *,
    node_id: str = HYBRID_WIRE_STUB_NODE_ID,
    manifest_id: str = "local-node-dev-fixture-manifest",
    signed_origin_verified: bool = True,
    issued_at: str = "2026-05-22T00:00:00Z",
    expires_at: str = HYBRID_WIRE_STUB_MANIFEST_EXPIRES_AT,
) -> LocalNodeCapabilityManifest:
    return LocalNodeCapabilityManifest(
        manifest_id=manifest_id,
        node_id=node_id,
        issued_at=issued_at,
        expires_at=expires_at,
        capabilities=_capabilities(),
        loopback_only=True,
        non_production=True,
        signed_origin_verified=signed_origin_verified,
        production_trust_material=False,
        manifest_status="fixture_valid" if signed_origin_verified else "fixture_unverified",
        lease_policy="required_per_session",
        audit_event_schema="hybrid-wire-audit/v0.3",
        message_body_persistence="forbidden",
    )


def build_local_node_session_ref(
    *,
    node_id: str = HYBRID_WIRE_STUB_NODE_ID,
    manifest_id: str = "local-node-dev-fixture-manifest",
    session_id: str = HYBRID_WIRE_STUB_SESSION_ID,
    state: str = "active",
    issued_at: str = "2026-05-22T00:00:00Z",
    expires_at: str = HYBRID_WIRE_STUB_SESSION_EXPIRES_AT,
    signed_origin_verified: bool = True,
    lease_id: str = HYBRID_WIRE_STUB_LEASE_ID,
) -> LocalNodeSessionRef:
    return LocalNodeSessionRef(
        session_id=session_id,
        node_id=node_id,
        manifest_id=manifest_id,
        issued_at=issued_at,
        expires_at=expires_at,
        state=state,
        signed_origin_verified=signed_origin_verified,
        non_production=True,
        bearer_token_included=False,
        production_trust_material=False,
        lease_id=lease_id,
        lease_expires_at=expires_at,
        token_hash=HYBRID_WIRE_STUB_TOKEN_HASH,
        token_hash_algorithm="sha256",
        bearer_token_hash_only=True,
        message_body_persisted=False,
    )


def build_local_node_heartbeat(
    *,
    node_id: str = HYBRID_WIRE_STUB_NODE_ID,
    session_id: str = HYBRID_WIRE_STUB_SESSION_ID,
) -> LocalNodeHeartbeat:
    lease_expires_at = HYBRID_WIRE_STUB_SESSION_EXPIRES_AT
    return LocalNodeHeartbeat(
        node_id=node_id,
        session_id=session_id,
        issued_at=_now(),
        healthy=True,
        loopback_only=True,
        production_runtime=False,
        status="fixture_alive",
        lease_id=HYBRID_WIRE_STUB_LEASE_ID,
        lease_expires_at=lease_expires_at,
        audit_cursor="audit-cursor-dev-fixture",
        message_body_persisted=False,
    )


def build_run_envelope(
    *,
    capability: WireCapabilityName,
    prompt: str,
    session_ref: LocalNodeSessionRef | None = None,
    run_id: str | None = None,
) -> LocalNodeRunEnvelope:
    ref = session_ref or build_local_node_session_ref()
    summary = _wire_summary(prompt)
    envelope_run_id = run_id or new_run_id()
    return LocalNodeRunEnvelope(
        run_id=envelope_run_id,
        session_ref=ref,
        capability=capability,
        task_summary=summary,
        payload_summary=summary,
        raw_prompt_included=False,
        provider_key_included=False,
        local_path_included=False,
        created_at=_now(),
        lease_id=ref.lease_id,
        audit_event_id=f"audit-{envelope_run_id}",
        audit_summary="metadata_only_no_message_body",
        message_body_persisted=False,
    )


def build_run_result(*, run_id: str, result: str, status: str = "completed") -> LocalNodeRunResult:
    return LocalNodeRunResult(
        run_id=run_id,
        status=status,
        result_summary=_wire_summary(result),
        raw_result_included=False,
        local_path_included=False,
        artifacts=(),
        completed_at=_now(),
        audit_event_id=f"audit-{run_id}",
        message_body_persisted=False,
    )


def build_node_error(*, code: str, message: str, retryable: bool = False) -> LocalNodeError:
    return LocalNodeError(
        code=_wire_summary(code, max_chars=80) or "unknown_error",
        message=_wire_summary(message),
        retryable=retryable,
        public_safe=True,
        raw_exception_included=False,
        status="error",
        audit_event_id=f"audit-error-{_wire_summary(code, max_chars=40) or 'unknown'}",
    )


def build_official_orchestration_stub_request(
    *,
    requested_capability: str = "workspace_file_access",
    task: str = "Preview workspace file access through Local Node contract.",
    session_ref: LocalNodeSessionRef | None = None,
    request_id: str = "official-stub-request-dev-fixture",
) -> OfficialOrchestrationStubRequest:
    return OfficialOrchestrationStubRequest(
        request_id=request_id,
        requested_capability=requested_capability,
        task_summary=_wire_summary(task),
        session_ref=session_ref,
        route_strategy=_orchestration_route_strategy(requested_capability),
        approval_required=True,
        audit_event_required=True,
        args_hash_required=True,
        private_file_content_included=False,
        raw_prompt_included=False,
        provider_key_included=False,
        dry_run=True,
        official_cloud_runtime_implemented=False,
        production_oracle_used=False,
        network_required=False,
    )


def build_official_orchestration_stub_response(
    *,
    request: OfficialOrchestrationStubRequest | None = None,
    response_id: str = "official-stub-response-dev-fixture",
) -> OfficialOrchestrationStubResponse:
    request = request or build_official_orchestration_stub_request()
    return OfficialOrchestrationStubResponse(
        response_id=response_id,
        request_id=request.request_id,
        status="contract_stub_only",
        route_strategy=request.route_strategy,
        accepted_for_private_implementation=True,
        public_repo_execution_available=False,
        disabled_reason="production_oracle_not_implemented_in_public_repo",
        controlled_error_schema="LocalNodeError",
        approval_required=request.approval_required,
        audit_event_required=request.audit_event_required,
        args_hash_required=request.args_hash_required,
        private_file_content_included=False,
        raw_prompt_included=False,
        provider_key_included=False,
        message_body_persisted=False,
        official_cloud_runtime_implemented=False,
        production_oracle_used=False,
        network_required=False,
    )


def build_local_node_status_report(
    *,
    node_available: bool = True,
    verified: bool = True,
    session_state: str = "active",
) -> dict[str, object]:
    manifest = build_local_node_capability_manifest(signed_origin_verified=verified) if node_available else None
    session_ref = (
        build_local_node_session_ref(state=session_state, signed_origin_verified=verified)
        if node_available
        else None
    )
    posture = (
        evaluate_local_node_posture(
            node_id=HYBRID_WIRE_STUB_NODE_ID,
            manifest_verified=verified,
            session_state=session_state,
            declared_capabilities=tuple(
                capability.name for capability in manifest.capabilities if capability.enabled
            )
            if manifest
            else (),
            revoked=session_state == "revoked",
        )
        if node_available
        else None
    )
    return {
        "schema_version": HYBRID_WIRE_CONTRACT_VERSION,
        "compatible_versions": list(HYBRID_WIRE_COMPATIBLE_VERSIONS),
        "command": "yonerai node status",
        "ok": True,
        "local_node": {
            "available": node_available,
            "trust_state": "verified_test_node" if node_available and verified else "unverified_node" if node_available else "missing_node",
            "loopback_only": True,
            "non_production": True,
            "production_trust_material": False,
            "lease_id": HYBRID_WIRE_STUB_LEASE_ID if node_available else None,
            "session_token_hash_only": bool(session_ref and session_ref.bearer_token_hash_only),
            "message_body_persisted": False,
            "audit_event_schema": "hybrid-wire-audit/v0.3",
            "hello": build_local_node_hello().to_public_dict() if node_available else None,
            "heartbeat": build_local_node_heartbeat().to_public_dict() if node_available else None,
            "capability_manifest": manifest.to_public_dict() if manifest else None,
            "session_ref": session_ref.to_public_dict() if session_ref else None,
            "posture": posture.to_public_dict() if posture else None,
        },
        "official_cloud_runtime_implemented": False,
        "production_oracle_used": False,
        "network_required": False,
        "actions_not_performed": _wire_non_actions(),
    }


def build_pairing_dry_run_report() -> dict[str, object]:
    session_ref = build_local_node_session_ref()
    request = build_official_orchestration_stub_request(session_ref=session_ref)
    response = build_official_orchestration_stub_response(request=request)
    decision = evaluate_wire_request(
        manifest=build_local_node_capability_manifest(),
        session_ref=session_ref,
        requested_capability=request.requested_capability,
    )
    return {
        "schema_version": HYBRID_WIRE_CONTRACT_VERSION,
        "compatible_versions": list(HYBRID_WIRE_COMPATIBLE_VERSIONS),
        "command": "yonerai node pair --dry-run",
        "ok": True,
        "dry_run": True,
        "pairing_performed": False,
        "session_token_plaintext_included": False,
        "session_token_hash_only": True,
        "message_body_persisted": False,
        "official_orchestration_stub_request": request.to_public_dict(),
        "official_orchestration_stub_response": response.to_public_dict(),
        "trust_decision": decision.to_public_dict(),
        "actions_not_performed": _wire_non_actions(),
    }


def build_hybrid_wire_conformance_report() -> dict[str, object]:
    manifest = build_local_node_capability_manifest()
    active_session = build_local_node_session_ref()
    orchestration_request = build_official_orchestration_stub_request(
        requested_capability="cloud_orchestration",
        task="Hard public reasoning over public docs through cloud contract candidate.",
        session_ref=active_session,
    )
    orchestration_response = build_official_orchestration_stub_response(request=orchestration_request)
    route_orchestration_alignment = _route_orchestration_alignment_case()
    posture_cases = _node_posture_cases()
    extension_cases = _extension_boundary_cases()
    trust_cases = (
        (
            "missing_node",
            evaluate_wire_request(
                manifest=None,
                session_ref=active_session,
                requested_capability="workspace_file_access",
            ),
        ),
        (
            "unverified_node",
            evaluate_wire_request(
                manifest=build_local_node_capability_manifest(signed_origin_verified=False),
                session_ref=active_session,
                requested_capability="workspace_file_access",
            ),
        ),
        (
            "verified_test_node",
            evaluate_wire_request(
                manifest=manifest,
                session_ref=active_session,
                requested_capability="mock_search",
            ),
        ),
        (
            "expired_session",
            evaluate_wire_request(
                manifest=manifest,
                session_ref=build_local_node_session_ref(state="expired"),
                requested_capability="workspace_file_access",
            ),
        ),
        (
            "revoked_session",
            evaluate_wire_request(
                manifest=manifest,
                session_ref=build_local_node_session_ref(state="revoked"),
                requested_capability="workspace_file_access",
            ),
        ),
        (
            "capability_not_declared",
            evaluate_wire_request(
                manifest=manifest,
                session_ref=active_session,
                requested_capability="unknown_future_capability",
            ),
        ),
        (
            "approval_required",
            evaluate_wire_request(
                manifest=manifest,
                session_ref=active_session,
                requested_capability="dangerous_operation",
            ),
        ),
    )
    expected_states = HYBRID_WIRE_REQUIRED_TRUST_STATES
    observed_states = tuple(decision.state for _label, decision in trust_cases)
    route_alignment_ok = route_orchestration_alignment.get("status") == "ok"
    return {
        "schema_version": HYBRID_WIRE_CONTRACT_VERSION,
        "compatible_versions": list(HYBRID_WIRE_COMPATIBLE_VERSIONS),
        "ok": expected_states == observed_states and route_alignment_ok,
        "test_fixture_only": True,
        "local_node_fixture_available": True,
        "route_preview_fixture_supported": True,
        "node_posture_schema_version": NODE_POSTURE_SCHEMA_VERSION,
        "extension_capability_manifest_schema_version": EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION,
        "required_node_posture_states": ["VERIFIED", "LIMITED", "RECOVERY", "QUARANTINED", "REVOKED"],
        "required_node_posture_state_count": 5,
        "production_trust_material": False,
        "official_cloud_runtime_implemented": False,
        "production_oracle_used": False,
        "network_required": False,
        "lease_required": True,
        "session_token_hash_only": True,
        "message_body_persisted": False,
        "audit_event_schema": "hybrid-wire-audit/v0.3",
        "required_trust_states": list(HYBRID_WIRE_REQUIRED_TRUST_STATES),
        "required_trust_state_count": len(HYBRID_WIRE_REQUIRED_TRUST_STATES),
        "schemas": [
            "LocalNodeHello",
            "LocalNodeHeartbeat",
            "LocalNodeCapabilityManifest",
            "LocalNodeSessionRef",
            "LocalNodeRunEnvelope",
            "LocalNodeRunResult",
            "LocalNodeError",
            "OfficialOrchestrationStubRequest",
            "OfficialOrchestrationStubResponse",
        ],
        "official_orchestration_stub": {
            "request": orchestration_request.to_public_dict(),
            "response": orchestration_response.to_public_dict(),
        },
        "route_orchestration_alignment": route_orchestration_alignment,
        "capabilities": [capability.name for capability in manifest.capabilities],
        "trust_states": [
            {
                "name": label,
                "observed_state": decision.state,
                "execute_allowed": decision.execute_allowed,
                "allowed_for_preview": decision.allowed_for_preview,
                "approval_required": decision.approval_required,
                "reasons": list(decision.reasons),
            }
            for label, decision in trust_cases
        ],
        "node_posture_states": posture_cases,
        "extension_boundary": extension_cases,
        "cli_commands": [
            "yonerai node status --json",
            "yonerai node status --pretty",
            "yonerai node pair --dry-run --json",
            "yonerai node pair --dry-run --pretty",
            "yonerai route preview <task> --use-local-node-fixture",
        ],
        "actions_not_performed": _wire_non_actions(),
    }


def _node_posture_cases() -> list[dict[str, object]]:
    base_capabilities = ("local_model", "workspace_file_access", "mock_search", "tool_boundary", "ledger")
    return [
        evaluate_local_node_posture(
            node_id=HYBRID_WIRE_STUB_NODE_ID,
            manifest_verified=True,
            session_state="active",
            declared_capabilities=base_capabilities,
        ).to_public_dict(),
        evaluate_local_node_posture(
            node_id=HYBRID_WIRE_STUB_NODE_ID,
            manifest_verified=False,
            session_state="active",
            declared_capabilities=base_capabilities,
            declared_extensions=("experimental.extension",),
        ).to_public_dict(),
        evaluate_local_node_posture(
            node_id=HYBRID_WIRE_STUB_NODE_ID,
            manifest_verified=True,
            session_state="expired",
            declared_capabilities=base_capabilities,
            policy_drift=True,
            manifest_drift=True,
        ).to_public_dict(),
        evaluate_local_node_posture(
            node_id=HYBRID_WIRE_STUB_NODE_ID,
            manifest_verified=True,
            session_state="active",
            declared_capabilities=base_capabilities,
            suspicious_behavior=True,
        ).to_public_dict(),
        evaluate_local_node_posture(
            node_id=HYBRID_WIRE_STUB_NODE_ID,
            manifest_verified=True,
            session_state="revoked",
            declared_capabilities=base_capabilities,
        ).to_public_dict(),
    ]


def _extension_boundary_cases() -> list[dict[str, object]]:
    return [
        evaluate_extension_capability_manifest(
            build_extension_capability_manifest(
                extension_id="local-dev-search-extension",
                declared_capabilities=("mock_search",),
            )
        ).to_public_dict(),
        evaluate_extension_capability_manifest(
            build_extension_capability_manifest(
                extension_id="duplicate-capability-extension",
                declared_capabilities=("mock_search", "mock_search"),
            )
        ).to_public_dict(),
        evaluate_extension_capability_manifest(
            build_extension_capability_manifest(
                extension_id="overbroad-capability-extension",
                declared_capabilities=("local_tools", "pc_operations"),
            )
        ).to_public_dict(),
        evaluate_extension_capability_manifest(
            build_extension_capability_manifest(
                extension_id="policy-drift-extension",
                declared_capabilities=("mock_search",),
            ),
            policy_drift=True,
        ).to_public_dict(),
    ]


def _route_orchestration_alignment_case() -> dict[str, object]:
    from ora_core.route_preview import preview_route

    route_decision = preview_route(
        "hard public reasoning over public API docs",
        mode="official_hybrid_private",
    ).to_public_dict()
    route_strategy = route_decision.get("route_strategy")
    route = route_decision.get("route")
    requested_capability = route_decision.get("requested_capability")
    approval_required = bool(route_decision.get("approval_required"))
    request = build_official_orchestration_stub_request(
        requested_capability=str(requested_capability or ""),
        task="Hard public reasoning over public API docs.",
    )
    response = build_official_orchestration_stub_response(request=request)
    audit_requirements = route_decision.get("audit_requirements")
    if not isinstance(audit_requirements, dict):
        audit_requirements = {}
    checks = {
        "route_strategy_matches_request": route_strategy == request.route_strategy,
        "route_strategy_matches_response": route_strategy == response.route_strategy,
        "approval_preserved": approval_required == request.approval_required == response.approval_required,
        "audit_preserved": (
            bool(audit_requirements.get("audit_event_required"))
            == request.audit_event_required
            == response.audit_event_required
        ),
        "args_hash_preserved": (
            bool(audit_requirements.get("args_hash_required")) == request.args_hash_required == response.args_hash_required
        ),
        "private_file_content_excluded": (
            route_decision.get("private_file_content_sent_to_cloud") is False
            and request.private_file_content_included is False
            and response.private_file_content_included is False
        ),
        "raw_prompt_excluded": (
            route_decision.get("raw_prompt_body_sent_to_cloud") is False
            and request.raw_prompt_included is False
            and response.raw_prompt_included is False
        ),
        "provider_key_excluded": (
            route_decision.get("provider_key_sent_to_cloud") is False
            and request.provider_key_included is False
            and response.provider_key_included is False
        ),
        "public_repo_execution_disabled": response.public_repo_execution_available is False,
        "network_not_required": request.network_required is False and response.network_required is False,
    }
    return {
        "name": "hard_public_reasoning_cloud_contract_candidate",
        "status": "ok" if all(checks.values()) else "fail",
        "route": route,
        "route_strategy": route_strategy,
        "request_schema": request.schema_name,
        "response_schema": response.schema_name,
        "requested_capability": request.requested_capability,
        "privacy_class": route_decision.get("privacy_class"),
        "cloud_contract_candidate": bool(route_decision.get("cloud_contract_candidate")),
        "checks": checks,
    }


def _parse_wire_timestamp(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _wire_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def evaluate_wire_request(
    *,
    manifest: LocalNodeCapabilityManifest | None,
    session_ref: LocalNodeSessionRef | None,
    requested_capability: str,
    approval_granted: bool = False,
    now: datetime | None = None,
) -> HybridWireTrustDecision:
    capability = requested_capability.strip().lower().replace("-", "_").replace(".", "_")
    current = _wire_now(now)
    if manifest is None:
        return _wire_decision("missing_node", capability, ("local_node_missing",))
    if manifest.production_trust_material:
        return _wire_decision("unverified_node", capability, ("production_trust_material_not_allowed_public_repo",))
    if not manifest.signed_origin_verified:
        return _wire_decision("unverified_node", capability, ("local_node_not_verified",))
    manifest_expires_at = _parse_wire_timestamp(manifest.expires_at)
    if manifest_expires_at is None:
        return _wire_decision("unverified_node", capability, ("local_node_manifest_expiry_invalid",))
    if manifest_expires_at <= current:
        return _wire_decision("unverified_node", capability, ("local_node_manifest_expired",))
    if session_ref is None:
        return _wire_decision("expired_session", capability, ("local_node_session_missing",))
    if session_ref.production_trust_material:
        return _wire_decision("unverified_node", capability, ("production_trust_material_not_allowed_public_repo",))
    if not session_ref.signed_origin_verified:
        return _wire_decision("unverified_node", capability, ("local_node_session_not_verified",))
    if session_ref.node_id != manifest.node_id or session_ref.manifest_id != manifest.manifest_id:
        return _wire_decision("unverified_node", capability, ("local_node_session_manifest_mismatch",))
    if session_ref.state == "revoked":
        return _wire_decision("revoked_session", capability, ("local_node_session_revoked",))
    if session_ref.state != "active":
        return _wire_decision("expired_session", capability, ("local_node_session_not_active",))
    session_expires_at = _parse_wire_timestamp(session_ref.expires_at)
    if session_expires_at is None:
        return _wire_decision("expired_session", capability, ("local_node_session_expiry_invalid",))
    if session_expires_at <= current:
        return _wire_decision("expired_session", capability, ("local_node_session_expired",))
    lease_expires_at = _parse_wire_timestamp(session_ref.lease_expires_at)
    if lease_expires_at is None:
        return _wire_decision("expired_session", capability, ("local_node_session_lease_expiry_invalid",))
    if lease_expires_at <= current:
        return _wire_decision("expired_session", capability, ("local_node_session_lease_expired",))

    declared, duplicates = _declared_capabilities(manifest)
    if duplicates:
        return _wire_decision("unverified_node", capability, ("duplicate_capability_declared",))
    item = declared.get(capability)
    if item is None:
        return _wire_decision("capability_not_declared", capability, ("capability_not_declared",))
    if item.approval_required or not item.enabled:
        reasons = ["capability_requires_owner_approval"]
        if not item.enabled:
            reasons.append(item.disabled_reason or "capability_disabled")
        return _wire_decision(
            "approval_required",
            capability,
            tuple(reasons),
            allowed_for_preview=approval_granted and item.enabled,
            approval_required=True,
        )
    return _wire_decision(
        "verified_test_node",
        capability,
        ("verified_test_node_contract_preview",),
        allowed_for_preview=True,
    )


def route_preview_inputs_from_node_status(local_node: Mapping[str, object]) -> dict[str, object]:
    manifest = local_node.get("capability_manifest")
    capabilities: list[str] = []
    posture = local_node.get("posture")
    exposed_wire_capabilities: set[str] | None = None
    local_work_preview_allowed = True
    if isinstance(posture, Mapping):
        local_work_preview_allowed = bool(posture.get("local_work_preview_allowed"))
        exposed_capabilities = posture.get("exposed_capabilities")
        if isinstance(exposed_capabilities, list):
            exposed_wire_capabilities = {
                str(item).strip().lower().replace("-", "_").replace(".", "_")
                for item in exposed_capabilities
                if isinstance(item, str) and item.strip()
            }
    if isinstance(manifest, Mapping):
        for item in manifest.get("capabilities", []):
            if not isinstance(item, Mapping) or not item.get("enabled"):
                continue
            wire_name = str(item.get("name") or "").strip().lower().replace("-", "_").replace(".", "_")
            if exposed_wire_capabilities is not None:
                if not local_work_preview_allowed or wire_name not in exposed_wire_capabilities:
                    continue
                route_capability = str(item.get("route_capability") or "")
                if route_capability:
                    capabilities.append(route_capability)
                continue
            route_capability = str(item.get("route_capability") or "")
            if route_capability:
                capabilities.append(route_capability)
    trust_state = str(local_node.get("trust_state") or "missing_node")
    route_state = "present_verified" if trust_state == "verified_test_node" else "present_unverified"
    if trust_state == "missing_node" or not local_node.get("available"):
        route_state = "missing"
    session_ref = local_node.get("session_ref")
    session_state = "enrolled_verified" if isinstance(session_ref, Mapping) and session_ref.get("state") == "active" else "missing"
    return {
        "has_local_node": bool(local_node.get("available")),
        "local_node_verification_state": route_state,
        "local_node_capabilities": tuple(capabilities),
        "require_enrolled_verified_session": session_state == "enrolled_verified",
        "session_verification_state": session_state,
        "node_posture_state": str(posture.get("state")) if isinstance(posture, Mapping) else None,
        "local_work_preview_allowed": local_work_preview_allowed,
    }


def wire_capability_to_route_capability(capability: str) -> str:
    normalized = capability.strip().lower().replace("-", "_").replace(".", "_")
    return _ROUTE_CAPABILITY_ALIASES.get(normalized, normalized)


def _orchestration_route_strategy(requested_capability: str) -> str:
    normalized = requested_capability.strip().lower().replace("-", "_").replace(".", "_")
    if normalized in {"cloud_orchestration", "public_ui_sync_support", "self_evolution_proposals"}:
        return "cloud_contract_candidate"
    if normalized in {"workspace_file_access", "local_model", "tool_boundary", "ledger", "dangerous_operation"}:
        return "hybrid"
    return "deny"


def _wire_decision(
    state: TrustSessionState,
    requested_capability: str,
    reasons: tuple[str, ...],
    *,
    allowed_for_preview: bool = False,
    approval_required: bool = False,
) -> HybridWireTrustDecision:
    return HybridWireTrustDecision(
        state=state,
        requested_capability=requested_capability,
        allowed_for_preview=allowed_for_preview,
        execute_allowed=False,
        approval_required=approval_required,
        production_trust_material=False,
        reasons=reasons,
    )


def _wire_non_actions() -> list[str]:
    return [
        "no production Oracle",
        "no official cloud runtime",
        "no production signing key",
        "no production trust store",
        "no live Discord",
        "no deploy",
        "no arbitrary shell",
        "no arbitrary file access",
        "no provider key",
        "no network call",
    ]


def _wire_summary(value: object, *, max_chars: int = 240) -> str:
    summary = safe_summary(value, max_chars=max_chars)
    return _SECRET_LIKE_RE.sub("[credential_redacted]", summary)


def assert_public_safe_wire_payload(payload: Mapping[str, Any]) -> tuple[str, ...]:
    violations: list[str] = []
    _collect_wire_payload_violations(payload, violations=violations, visited=set())
    return tuple(violations)


def _declared_capabilities(
    manifest: LocalNodeCapabilityManifest,
) -> tuple[dict[str, LocalNodeCapability], tuple[str, ...]]:
    declared: dict[str, LocalNodeCapability] = {}
    duplicates: list[str] = []
    for item in manifest.capabilities:
        if item.name in declared:
            duplicates.append(item.name)
            continue
        declared[item.name] = item
    return declared, tuple(duplicates)


def _collect_wire_payload_violations(
    value: object,
    *,
    violations: list[str],
    visited: set[int],
) -> None:
    if isinstance(value, Mapping):
        value_id = id(value)
        if value_id in visited:
            return
        visited.add(value_id)
        for key, child in value.items():
            normalized_key = str(key).strip().lower().replace("-", "_").replace(" ", "_")
            if normalized_key in _FORBIDDEN_WIRE_KEYS:
                violations.append(f"forbidden_key:{normalized_key}")
            _collect_wire_payload_violations(child, violations=violations, visited=visited)
        return
    if isinstance(value, (list, tuple)):
        value_id = id(value)
        if value_id in visited:
            return
        visited.add(value_id)
        for item in value:
            _collect_wire_payload_violations(item, violations=violations, visited=visited)
        return
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in _LOCAL_PATH_MARKERS):
            violations.append("forbidden_value:local_path")
        if _SECRET_LIKE_RE.search(value):
            violations.append("forbidden_value:secret_like")
