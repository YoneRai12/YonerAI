from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

from ..three_mode import ModeName
from .local_node_enrollment import (
    LocalNodeEnrollmentSession,
    enrollment_session_state,
)


LOCAL_NODE_SESSION_REF_SCHEMA_VERSION = "yonerai-local-node-session-ref-contract/v1"

SessionRefStatus = Literal[
    "bound",
    "expired",
    "revoked",
    "unverified",
    "mode_mismatch",
    "capability_not_declared",
    "approval_required",
]


@dataclass(frozen=True)
class LocalNodeSessionRef:
    """Public-safe reference to an enrolled Local Node session.

    This is a contract object for previews and synthetic local-dev tests. It is
    not a bearer token and intentionally excludes pairing codes, session tokens,
    raw request args, hostnames, paths, and production trust material.
    """

    session_id: str
    node_id: str
    key_id: str
    manifest_id: str
    mode: ModeName
    capability: str
    session_expires_at: str
    signed_origin_verified: bool
    approval_required: bool
    production_trust_material: bool = False
    schema_version: str = LOCAL_NODE_SESSION_REF_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LocalNodeSessionRefValidation:
    status: SessionRefStatus
    bound: bool
    preview_usable: bool
    execute_allowed: bool
    approval_required: bool
    production_trust_material: bool
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def build_local_node_session_ref(
    session: LocalNodeEnrollmentSession,
    *,
    capability: str,
) -> LocalNodeSessionRef:
    return LocalNodeSessionRef(
        session_id=session.session_id,
        node_id=session.enrolled_node_id,
        key_id=session.key_id,
        manifest_id=session.manifest_id,
        mode=session.mode,
        capability=capability,
        session_expires_at=session.session_expires_at,
        signed_origin_verified=session.signed_origin_verified,
        approval_required=capability in session.approval_required_capabilities,
        production_trust_material=session.production_trust_material,
    )


def validate_local_node_session_ref(
    ref: LocalNodeSessionRef,
    *,
    session: LocalNodeEnrollmentSession,
    expected_mode: ModeName,
    now: datetime | None = None,
) -> LocalNodeSessionRefValidation:
    if ref.production_trust_material or session.production_trust_material:
        return _session_ref_decision(
            status="unverified",
            reasons=("production_trust_material_not_allowed_in_public_session_ref",),
            production_trust_material=ref.production_trust_material or session.production_trust_material,
        )

    if expected_mode == "official_managed_cloud":
        return _session_ref_decision(
            status="mode_mismatch",
            reasons=("managed_cloud_session_ref_runtime_not_in_public_repo",),
        )

    if ref.mode != expected_mode or session.mode != expected_mode:
        return _session_ref_decision(status="mode_mismatch", reasons=("session_ref_mode_mismatch",))

    if (
        ref.session_id != session.session_id
        or ref.node_id != session.enrolled_node_id
        or ref.key_id != session.key_id
        or ref.manifest_id != session.manifest_id
    ):
        return _session_ref_decision(status="unverified", reasons=("session_ref_binding_mismatch",))

    state = enrollment_session_state(session, now=now)
    if state == "revoked":
        return _session_ref_decision(status="revoked", reasons=("session_ref_revoked",))
    if state == "expired":
        return _session_ref_decision(status="expired", reasons=("session_ref_expired",))
    if state != "enrolled_verified" or not ref.signed_origin_verified:
        return _session_ref_decision(status="unverified", reasons=("session_ref_requires_verified_enrollment",))

    if ref.capability not in session.capabilities:
        return _session_ref_decision(
            status="capability_not_declared",
            reasons=("session_ref_capability_not_declared",),
        )

    if ref.approval_required or ref.capability in session.approval_required_capabilities:
        return _session_ref_decision(
            status="approval_required",
            reasons=("session_ref_capability_requires_approval",),
            bound=True,
            preview_usable=True,
            approval_required=True,
        )

    return _session_ref_decision(
        status="bound",
        reasons=("session_ref_bound_for_preview",),
        bound=True,
        preview_usable=True,
    )


def _session_ref_decision(
    *,
    status: SessionRefStatus,
    reasons: tuple[str, ...],
    bound: bool = False,
    preview_usable: bool = False,
    approval_required: bool = False,
    production_trust_material: bool = False,
) -> LocalNodeSessionRefValidation:
    return LocalNodeSessionRefValidation(
        status=status,
        bound=bound,
        preview_usable=preview_usable,
        execute_allowed=False,
        approval_required=approval_required,
        production_trust_material=production_trust_material,
        reasons=reasons,
    )
