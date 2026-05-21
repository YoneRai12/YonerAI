from __future__ import annotations

from dataclasses import asdict, dataclass
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
