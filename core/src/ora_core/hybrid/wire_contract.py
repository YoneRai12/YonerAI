from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Mapping

from ora_core.execution.ledger import new_run_id, safe_summary


HYBRID_WIRE_CONTRACT_VERSION = "yonerai-hybrid-wire-contract/v0.1"
HYBRID_WIRE_STUB_NODE_ID = "local-node-dev-fixture"
HYBRID_WIRE_STUB_SESSION_ID = "local-node-session-dev-fixture"

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
    schema_name: str = "LocalNodeError"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OfficialOrchestrationStubRequest:
    request_id: str
    requested_capability: WireCapabilityName
    task_summary: str
    session_ref: LocalNodeSessionRef | None
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
    )


def build_local_node_capability_manifest(
    *,
    node_id: str = HYBRID_WIRE_STUB_NODE_ID,
    manifest_id: str = "local-node-dev-fixture-manifest",
    signed_origin_verified: bool = True,
    issued_at: str = "2026-05-22T00:00:00Z",
    expires_at: str = "2026-05-29T00:00:00Z",
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
    )


def build_local_node_session_ref(
    *,
    node_id: str = HYBRID_WIRE_STUB_NODE_ID,
    manifest_id: str = "local-node-dev-fixture-manifest",
    session_id: str = HYBRID_WIRE_STUB_SESSION_ID,
    state: str = "active",
    issued_at: str = "2026-05-22T00:00:00Z",
    expires_at: str = "2026-05-29T01:00:00Z",
    signed_origin_verified: bool = True,
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
    )


def build_local_node_heartbeat(
    *,
    node_id: str = HYBRID_WIRE_STUB_NODE_ID,
    session_id: str = HYBRID_WIRE_STUB_SESSION_ID,
) -> LocalNodeHeartbeat:
    return LocalNodeHeartbeat(
        node_id=node_id,
        session_id=session_id,
        issued_at=_now(),
        healthy=True,
        loopback_only=True,
        production_runtime=False,
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
    return LocalNodeRunEnvelope(
        run_id=run_id or new_run_id(),
        session_ref=ref,
        capability=capability,
        task_summary=summary,
        payload_summary=summary,
        raw_prompt_included=False,
        provider_key_included=False,
        local_path_included=False,
    )


def build_run_result(*, run_id: str, result: str, status: str = "completed") -> LocalNodeRunResult:
    return LocalNodeRunResult(
        run_id=run_id,
        status=status,
        result_summary=_wire_summary(result),
        raw_result_included=False,
        local_path_included=False,
        artifacts=(),
    )


def build_node_error(*, code: str, message: str, retryable: bool = False) -> LocalNodeError:
    return LocalNodeError(
        code=_wire_summary(code, max_chars=80) or "unknown_error",
        message=_wire_summary(message),
        retryable=retryable,
        public_safe=True,
        raw_exception_included=False,
    )


def build_official_orchestration_stub_request(
    *,
    requested_capability: WireCapabilityName = "workspace_file_access",
    task: str = "Preview workspace file access through Local Node contract.",
    session_ref: LocalNodeSessionRef | None = None,
    request_id: str = "official-stub-request-dev-fixture",
) -> OfficialOrchestrationStubRequest:
    return OfficialOrchestrationStubRequest(
        request_id=request_id,
        requested_capability=requested_capability,
        task_summary=_wire_summary(task),
        session_ref=session_ref,
        dry_run=True,
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
    return {
        "schema_version": HYBRID_WIRE_CONTRACT_VERSION,
        "command": "yonerai node status",
        "ok": True,
        "local_node": {
            "available": node_available,
            "trust_state": "verified_test_node" if node_available and verified else "unverified_node" if node_available else "missing_node",
            "loopback_only": True,
            "non_production": True,
            "production_trust_material": False,
            "hello": build_local_node_hello().to_public_dict() if node_available else None,
            "heartbeat": build_local_node_heartbeat().to_public_dict() if node_available else None,
            "capability_manifest": manifest.to_public_dict() if manifest else None,
            "session_ref": session_ref.to_public_dict() if session_ref else None,
        },
        "official_cloud_runtime_implemented": False,
        "production_oracle_used": False,
        "network_required": False,
        "actions_not_performed": _wire_non_actions(),
    }


def build_pairing_dry_run_report() -> dict[str, object]:
    session_ref = build_local_node_session_ref()
    request = build_official_orchestration_stub_request(session_ref=session_ref)
    decision = evaluate_wire_request(
        manifest=build_local_node_capability_manifest(),
        session_ref=session_ref,
        requested_capability=request.requested_capability,
    )
    return {
        "schema_version": HYBRID_WIRE_CONTRACT_VERSION,
        "command": "yonerai node pair --dry-run",
        "ok": True,
        "dry_run": True,
        "pairing_performed": False,
        "official_orchestration_stub_request": request.to_public_dict(),
        "trust_decision": decision.to_public_dict(),
        "actions_not_performed": _wire_non_actions(),
    }


def build_hybrid_wire_conformance_report() -> dict[str, object]:
    manifest = build_local_node_capability_manifest()
    active_session = build_local_node_session_ref()
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
    return {
        "schema_version": HYBRID_WIRE_CONTRACT_VERSION,
        "ok": expected_states == observed_states,
        "test_fixture_only": True,
        "local_node_fixture_available": True,
        "route_preview_fixture_supported": True,
        "production_trust_material": False,
        "official_cloud_runtime_implemented": False,
        "production_oracle_used": False,
        "network_required": False,
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
        ],
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
        "cli_commands": [
            "yonerai node status --json",
            "yonerai node status --pretty",
            "yonerai node pair --dry-run --json",
            "yonerai node pair --dry-run --pretty",
            "yonerai route preview <task> --use-local-node-fixture",
        ],
        "actions_not_performed": _wire_non_actions(),
    }


def evaluate_wire_request(
    *,
    manifest: LocalNodeCapabilityManifest | None,
    session_ref: LocalNodeSessionRef | None,
    requested_capability: str,
    approval_granted: bool = False,
) -> HybridWireTrustDecision:
    capability = requested_capability.strip().lower().replace("-", "_").replace(".", "_")
    if manifest is None:
        return _wire_decision("missing_node", capability, ("local_node_missing",))
    if manifest.production_trust_material:
        return _wire_decision("unverified_node", capability, ("production_trust_material_not_allowed_public_repo",))
    if not manifest.signed_origin_verified:
        return _wire_decision("unverified_node", capability, ("local_node_not_verified",))
    if session_ref is None:
        return _wire_decision("expired_session", capability, ("local_node_session_missing",))
    if session_ref.production_trust_material:
        return _wire_decision("unverified_node", capability, ("production_trust_material_not_allowed_public_repo",))
    if session_ref.state == "revoked":
        return _wire_decision("revoked_session", capability, ("local_node_session_revoked",))
    if session_ref.state != "active":
        return _wire_decision("expired_session", capability, ("local_node_session_not_active",))

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
    if isinstance(manifest, Mapping):
        for item in manifest.get("capabilities", []):
            if isinstance(item, Mapping) and item.get("enabled"):
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
    }


def wire_capability_to_route_capability(capability: str) -> str:
    normalized = capability.strip().lower().replace("-", "_").replace(".", "_")
    return _ROUTE_CAPABILITY_ALIASES.get(normalized, normalized)


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
