from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Literal

from ..route_preview import RoutePreviewDecision, preview_route
from ..three_mode import ModeName
from .connector_fixture import (
    FIXTURE_ISSUER_NODE_ID,
    build_fixture_signature_verifier,
    build_fixture_trust_registry,
)
from .envelope import DEFAULT_CONTROL_PLANE_AUDIENCE
from .local_node_manifest import (
    LocalNodeManifestVerification,
    SignedLocalNodeManifest,
    build_test_local_node_manifest,
    generate_test_local_node_keypair,
    sign_local_node_manifest,
    verify_local_node_manifest,
)
from .local_node_action_envelope import (
    LocalNodeActionEnvelope,
    LocalNodeActionVerification,
    action_args_hash,
    build_unsigned_local_node_action_envelope,
    sign_local_node_action_envelope,
    verify_local_node_action_envelope,
)
from .local_node_enrollment import (
    LocalNodeEnrollmentSession,
    LocalNodeSessionCapabilityDecision,
    consume_pairing_code,
    create_pairing_challenge,
    evaluate_enrollment_session_capability,
    LocalNodeEnrollmentRequest,
)
from .policy import InMemoryNonceStore


LOCAL_DEV_CONTROL_PLANE_PROFILE = "local_dev_control_plane"
LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION = "local-dev-control-plane-simulator-0.1"
LOCAL_DEV_CONTROL_PLANE_FIXED_NOW = datetime(2026, 5, 21, 12, tzinfo=timezone.utc)

LocalNodeVerificationState = Literal[
    "missing",
    "present_unverified",
    "present_verified",
    "expired",
    "invalid_signature",
    "wrong_audience",
]
EnrollmentBindingState = Literal[
    "missing_enrollment",
    "pairing_pending",
    "enrolled_verified",
    "enrolled_unverified",
    "expired",
    "revoked",
]


@dataclass(frozen=True)
class LocalDevNodeStatus:
    node_id: str
    available: bool
    non_production: bool
    capabilities: tuple[str, ...]
    requires_approval: tuple[str, ...]
    disabled: tuple[str, ...]
    trust_material: str
    verification_state: LocalNodeVerificationState
    signed_origin_verified: bool
    trusted: bool
    declared_capabilities: tuple[str, ...]
    denied_capabilities: tuple[str, ...]
    verification_reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["requires_approval"] = list(self.requires_approval)
        payload["disabled"] = list(self.disabled)
        payload["declared_capabilities"] = list(self.declared_capabilities)
        payload["denied_capabilities"] = list(self.denied_capabilities)
        payload["verification_reasons"] = list(self.verification_reasons)
        return payload


@dataclass(frozen=True)
class LocalDevControlPlaneStatus:
    schema_version: str
    profile: str
    official_cloud_stub_available: bool
    official_private_control_plane_ready: bool
    local_node: LocalDevNodeStatus
    production_trust_material: bool
    network_required: bool

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile": self.profile,
            "official_cloud_stub_available": self.official_cloud_stub_available,
            "official_private_control_plane_ready": self.official_private_control_plane_ready,
            "local_node": self.local_node.to_public_dict(),
            "production_trust_material": self.production_trust_material,
            "network_required": self.network_required,
        }


@dataclass(frozen=True)
class LocalDevSessionBindingDecision:
    schema_version: str
    profile: str
    non_production: bool
    local_node_verification_state: LocalNodeVerificationState
    enrollment_state: EnrollmentBindingState
    session_bound: bool
    local_work_allowed_for_preview: bool
    approval_required: bool
    capability: str
    capability_decision: LocalNodeSessionCapabilityDecision | None
    action_envelope: LocalNodeActionVerification | None
    production_trust_material: bool
    network_required: bool
    raw_args_stored: bool
    plaintext_pairing_code_stored: bool
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile": self.profile,
            "non_production": self.non_production,
            "local_node_verification_state": self.local_node_verification_state,
            "enrollment_state": self.enrollment_state,
            "session_bound": self.session_bound,
            "local_work_allowed_for_preview": self.local_work_allowed_for_preview,
            "approval_required": self.approval_required,
            "capability": self.capability,
            "capability_decision": (
                self.capability_decision.to_public_dict() if self.capability_decision else None
            ),
            "action_envelope": self.action_envelope.to_public_dict() if self.action_envelope else None,
            "production_trust_material": self.production_trust_material,
            "network_required": self.network_required,
            "raw_args_stored": self.raw_args_stored,
            "plaintext_pairing_code_stored": self.plaintext_pairing_code_stored,
            "reasons": list(self.reasons),
        }


def _local_dev_disabled_capabilities() -> tuple[str, ...]:
    return (
        "production_deploy",
        "persistent_memory",
        "live_discord_gateway",
        "official_private_control_plane",
    )


def _verification_state(result: LocalNodeManifestVerification) -> LocalNodeVerificationState:
    if result.verified:
        return "present_verified"
    if result.status == "expired":
        return "expired"
    if result.status == "wrong_audience":
        return "wrong_audience"
    return "invalid_signature"


def _build_default_signed_manifest() -> tuple[SignedLocalNodeManifest, str]:
    private_key_b64, public_key_b64 = generate_test_local_node_keypair()
    manifest = build_test_local_node_manifest(
        node_id=FIXTURE_ISSUER_NODE_ID,
        issuer=LOCAL_DEV_CONTROL_PLANE_PROFILE,
    )
    return sign_local_node_manifest(manifest, private_key_b64=private_key_b64), public_key_b64


def build_local_dev_control_plane_status(
    *,
    local_node_available: bool = True,
    signed_manifest: SignedLocalNodeManifest | None = None,
    public_key_b64: str | None = None,
    expected_audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE,
    now: datetime | None = LOCAL_DEV_CONTROL_PLANE_FIXED_NOW,
    verify_test_manifest: bool = True,
) -> LocalDevControlPlaneStatus:
    disabled = _local_dev_disabled_capabilities()

    if not local_node_available:
        local_node = LocalDevNodeStatus(
            node_id=FIXTURE_ISSUER_NODE_ID,
            available=False,
            non_production=True,
            capabilities=(),
            requires_approval=(),
            disabled=disabled,
            trust_material="missing_local_node",
            verification_state="missing",
            signed_origin_verified=False,
            trusted=False,
            declared_capabilities=(),
            denied_capabilities=(),
            verification_reasons=("local_node_missing",),
        )
        return LocalDevControlPlaneStatus(
            schema_version=LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION,
            profile=LOCAL_DEV_CONTROL_PLANE_PROFILE,
            official_cloud_stub_available=True,
            official_private_control_plane_ready=False,
            local_node=local_node,
            production_trust_material=False,
            network_required=False,
        )

    if signed_manifest is None or public_key_b64 is None:
        if verify_test_manifest:
            signed_manifest, public_key_b64 = _build_default_signed_manifest()
        else:
            local_node = LocalDevNodeStatus(
                node_id=FIXTURE_ISSUER_NODE_ID,
                available=True,
                non_production=True,
                capabilities=(),
                requires_approval=(),
                disabled=disabled,
                trust_material="unverified_local_node",
                verification_state="present_unverified",
                signed_origin_verified=False,
                trusted=False,
                declared_capabilities=(),
                denied_capabilities=(),
                verification_reasons=("signed_manifest_not_verified",),
            )
            return LocalDevControlPlaneStatus(
                schema_version=LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION,
                profile=LOCAL_DEV_CONTROL_PLANE_PROFILE,
                official_cloud_stub_available=True,
                official_private_control_plane_ready=False,
                local_node=local_node,
                production_trust_material=False,
                network_required=False,
            )

    verification = verify_local_node_manifest(
        signed_manifest,
        public_key_b64=public_key_b64,
        expected_audience=expected_audience,
        now=now,
    )
    capabilities = verification.declared_capabilities if verification.verified else ()
    approval_required = verification.approval_required_capabilities if verification.verified else ()
    local_node = LocalDevNodeStatus(
        node_id=signed_manifest.manifest.identity.node_id,
        available=True,
        non_production=True,
        capabilities=capabilities,
        requires_approval=approval_required,
        disabled=disabled,
        trust_material="test_signed_manifest_only",
        verification_state=_verification_state(verification),
        signed_origin_verified=verification.verified,
        trusted=verification.trusted,
        declared_capabilities=verification.declared_capabilities,
        denied_capabilities=verification.denied_capabilities,
        verification_reasons=verification.reasons,
    )
    return LocalDevControlPlaneStatus(
        schema_version=LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION,
        profile=LOCAL_DEV_CONTROL_PLANE_PROFILE,
        official_cloud_stub_available=True,
        official_private_control_plane_ready=False,
        local_node=local_node,
        production_trust_material=False,
        network_required=False,
    )


def build_local_dev_fixture_trust_context() -> dict[str, object]:
    registry = build_fixture_trust_registry()
    verifier = build_fixture_signature_verifier()
    return {
        "profile": LOCAL_DEV_CONTROL_PLANE_PROFILE,
        "issuer_node_id": FIXTURE_ISSUER_NODE_ID,
        "production_trust_material": False,
        "signature_algorithm": "test-static-signature",
        "registry_entry_exists": registry.get(FIXTURE_ISSUER_NODE_ID) is not None,
        "verifier_class": type(verifier).__name__,
    }


def preview_route_with_local_dev_control_plane(
    task_text: str,
    *,
    mode: ModeName = "official_hybrid_private",
    requested_capability: str | None = None,
    local_node_available: bool = True,
    risk_hint: str | None = None,
    verify_test_manifest: bool = True,
) -> RoutePreviewDecision:
    status = build_local_dev_control_plane_status(
        local_node_available=local_node_available,
        verify_test_manifest=verify_test_manifest,
    )
    return preview_route(
        task_text,
        mode=mode,
        requested_capability=requested_capability,
        has_local_node=status.local_node.available,
        local_node_verification_state=status.local_node.verification_state,
        local_node_capabilities=status.local_node.capabilities,
        risk_hint=risk_hint,
    )


def build_local_dev_enrolled_session_fixture(
    *,
    capability: str = "local_tools",
    verify_test_manifest: bool = True,
    pairing_code: str = "123456",
    now: datetime | None = LOCAL_DEV_CONTROL_PLANE_FIXED_NOW,
) -> tuple[LocalNodeEnrollmentSession | None, SignedLocalNodeManifest, str, str]:
    private_key_b64, public_key_b64 = generate_test_local_node_keypair()
    manifest = build_test_local_node_manifest(
        node_id=FIXTURE_ISSUER_NODE_ID,
        issuer=LOCAL_DEV_CONTROL_PLANE_PROFILE,
        capabilities=(capability, "dangerous_operations"),
    )
    signed = sign_local_node_manifest(manifest, private_key_b64=private_key_b64)
    if not verify_test_manifest:
        signed = replace(
            signed,
            manifest=replace(
                signed.manifest,
                capabilities=signed.manifest.capabilities + ("unknown.future.capability",),
            ),
        )
    request = LocalNodeEnrollmentRequest(
        node_id=manifest.identity.node_id,
        key_id=signed.signature.key_id,
        mode="official_hybrid_private",
        requested_capabilities=manifest.capabilities,
    )
    challenge = create_pairing_challenge(request, pairing_code=pairing_code)
    pairing = consume_pairing_code(
        challenge,
        pairing_code=pairing_code,
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=now,
    )
    return pairing.session, signed, private_key_b64, public_key_b64


def evaluate_local_dev_session_binding(
    *,
    capability: str = "local_tools",
    local_node_available: bool = True,
    enrollment_state: EnrollmentBindingState = "enrolled_verified",
    signed_action_envelope: LocalNodeActionEnvelope | None = None,
    expected_args_hash: str | None = None,
    nonce_store: InMemoryNonceStore | None = None,
    now: datetime | None = LOCAL_DEV_CONTROL_PLANE_FIXED_NOW,
) -> LocalDevSessionBindingDecision:
    if not local_node_available:
        return _session_binding_decision(
            local_node_verification_state="missing",
            enrollment_state="missing_enrollment",
            capability=capability,
            reasons=("local_node_missing",),
        )
    if enrollment_state == "missing_enrollment":
        return _session_binding_decision(
            local_node_verification_state="present_verified",
            enrollment_state=enrollment_state,
            capability=capability,
            reasons=("local_node_enrollment_required",),
        )
    if enrollment_state == "pairing_pending":
        return _session_binding_decision(
            local_node_verification_state="present_verified",
            enrollment_state=enrollment_state,
            capability=capability,
            reasons=("pairing_pending",),
        )

    verify_manifest = enrollment_state != "enrolled_unverified"
    session, _signed, private_key_b64, public_key_b64 = build_local_dev_enrolled_session_fixture(
        capability=capability,
        verify_test_manifest=verify_manifest,
        now=now,
    )
    if session is None:
        return _session_binding_decision(
            local_node_verification_state="present_unverified",
            enrollment_state="enrolled_unverified",
            capability=capability,
            reasons=("enrollment_without_verified_manifest",),
        )
    if enrollment_state == "revoked":
        from .local_node_enrollment import revoke_enrollment_session

        session = revoke_enrollment_session(session)
    if enrollment_state == "expired":
        session = replace(session, session_expires_at="2026-05-21T00:01:00Z")

    capability_decision = evaluate_enrollment_session_capability(session, capability, now=now)
    if signed_action_envelope is None:
        if not capability_decision.allowed:
            return _session_binding_decision(
                local_node_verification_state="present_verified",
                enrollment_state=enrollment_state,
                capability=capability,
                capability_decision=capability_decision,
                reasons=capability_decision.reasons,
            )
        args_hash = expected_args_hash or action_args_hash({"action": "synthetic_preview"})
        unsigned = build_unsigned_local_node_action_envelope(
            action_id="local-dev-action",
            node_id=session.enrolled_node_id,
            session_id=session.session_id,
            mode=session.mode,
            capability=capability,
            args_hash=args_hash,
        )
        signed_action_envelope = sign_local_node_action_envelope(unsigned, private_key_b64=private_key_b64)
        expected_args_hash = args_hash

    action_decision = verify_local_node_action_envelope(
        signed_action_envelope,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=expected_args_hash or signed_action_envelope.args_hash,
        nonce_store=nonce_store or InMemoryNonceStore(),
        mode=session.mode,
        now=now,
    )
    local_work_allowed = action_decision.accepted_for_preview and action_decision.session_bound
    return _session_binding_decision(
        local_node_verification_state="present_verified" if session.signed_origin_verified else "present_unverified",
        enrollment_state=enrollment_state,
        session_bound=action_decision.session_bound,
        local_work_allowed_for_preview=local_work_allowed,
        approval_required=action_decision.approval_required,
        capability=capability,
        capability_decision=capability_decision,
        action_envelope=action_decision,
        reasons=action_decision.reasons,
    )


def _session_binding_decision(
    *,
    local_node_verification_state: LocalNodeVerificationState,
    enrollment_state: EnrollmentBindingState,
    capability: str,
    reasons: tuple[str, ...],
    session_bound: bool = False,
    local_work_allowed_for_preview: bool = False,
    approval_required: bool = True,
    capability_decision: LocalNodeSessionCapabilityDecision | None = None,
    action_envelope: LocalNodeActionVerification | None = None,
) -> LocalDevSessionBindingDecision:
    return LocalDevSessionBindingDecision(
        schema_version=LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION,
        profile=LOCAL_DEV_CONTROL_PLANE_PROFILE,
        non_production=True,
        local_node_verification_state=local_node_verification_state,
        enrollment_state=enrollment_state,
        session_bound=session_bound,
        local_work_allowed_for_preview=local_work_allowed_for_preview,
        approval_required=approval_required,
        capability=capability,
        capability_decision=capability_decision,
        action_envelope=action_envelope,
        production_trust_material=False,
        network_required=False,
        raw_args_stored=False,
        plaintext_pairing_code_stored=False,
        reasons=reasons,
    )
