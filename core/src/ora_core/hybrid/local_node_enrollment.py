from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Literal

from ..three_mode import ModeName
from .envelope import DEFAULT_CONTROL_PLANE_AUDIENCE, parse_envelope_datetime
from .local_node_manifest import (
    APPROVAL_GATED_CAPABILITIES,
    LocalNodeManifestVerification,
    SignedLocalNodeManifest,
    verify_local_node_manifest,
)


LOCAL_NODE_ENROLLMENT_SCHEMA_VERSION = "yonerai-local-node-enrollment-test/v1"

EnrollmentState = Literal[
    "not_enrolled",
    "pairing_pending",
    "enrolled_unverified",
    "enrolled_verified",
    "expired",
    "revoked",
]
PairingConsumeStatus = Literal[
    "enrolled_verified",
    "enrolled_unverified",
    "invalid_pairing_code",
    "pairing_code_reused",
    "expired_pairing_code",
    "node_mismatch",
    "key_mismatch",
    "mode_incompatible",
]
SessionCapabilityStatus = Literal[
    "allowed",
    "approval_required",
    "not_verified",
    "expired",
    "revoked",
    "capability_not_declared",
]


@dataclass(frozen=True)
class LocalNodeEnrollmentRequest:
    node_id: str
    key_id: str
    mode: ModeName
    requested_capabilities: tuple[str, ...]
    audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE
    non_production: bool = True
    production_trust_material: bool = False
    schema_version: str = LOCAL_NODE_ENROLLMENT_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["requested_capabilities"] = list(self.requested_capabilities)
        return payload


@dataclass(frozen=True)
class PairingChallenge:
    challenge_id: str
    node_id: str
    key_id: str
    mode: ModeName
    audience: str
    issued_at: str
    expires_at: str
    pairing_code_hash: str
    enrollment_state: EnrollmentState = "pairing_pending"
    consumed_at: str | None = None
    non_production: bool = True
    production_trust_material: bool = False
    schema_version: str = LOCAL_NODE_ENROLLMENT_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("pairing_code_hash", None)
        return payload


@dataclass(frozen=True)
class LocalNodeEnrollmentSession:
    session_id: str
    enrolled_node_id: str
    key_id: str
    manifest_id: str
    mode: ModeName
    session_issued_at: str
    session_expires_at: str
    session_token_hash: str | None
    capabilities: tuple[str, ...]
    approval_required_capabilities: tuple[str, ...]
    enrollment_state: EnrollmentState
    signed_origin_verified: bool
    trusted: bool = False
    non_production: bool = True
    production_trust_material: bool = False
    revoked: bool = False
    schema_version: str = LOCAL_NODE_ENROLLMENT_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["approval_required_capabilities"] = list(self.approval_required_capabilities)
        return payload


@dataclass(frozen=True)
class PairingConsumptionResult:
    status: PairingConsumeStatus
    accepted: bool
    challenge: PairingChallenge
    session: LocalNodeEnrollmentSession | None
    manifest_verification: LocalNodeManifestVerification | None
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "accepted": self.accepted,
            "challenge": self.challenge.to_public_dict(),
            "session": self.session.to_public_dict() if self.session else None,
            "manifest_verification": (
                self.manifest_verification.to_public_dict() if self.manifest_verification else None
            ),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class LocalNodeSessionCapabilityDecision:
    status: SessionCapabilityStatus
    allowed: bool
    approval_required: bool
    session_state: EnrollmentState
    capability: str
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


def pairing_code_hash(*, challenge_id: str, node_id: str, pairing_code: str) -> str:
    payload = f"{challenge_id}:{node_id}:{pairing_code}".encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def create_pairing_challenge(
    request: LocalNodeEnrollmentRequest,
    *,
    pairing_code: str,
    challenge_id: str = "test-local-node-pairing",
    issued_at: str = "2026-05-21T00:00:00Z",
    expires_at: str = "2026-05-21T00:10:00Z",
) -> PairingChallenge:
    return PairingChallenge(
        challenge_id=challenge_id,
        node_id=request.node_id,
        key_id=request.key_id,
        mode=request.mode,
        audience=request.audience,
        issued_at=issued_at,
        expires_at=expires_at,
        pairing_code_hash=pairing_code_hash(
            challenge_id=challenge_id,
            node_id=request.node_id,
            pairing_code=pairing_code,
        ),
        enrollment_state="pairing_pending",
    )


def consume_pairing_code(
    challenge: PairingChallenge,
    *,
    pairing_code: str,
    signed_manifest: SignedLocalNodeManifest,
    public_key_b64: str,
    now: datetime | None = None,
    session_id: str = "test-local-node-session",
    session_token: str | None = None,
    session_expires_at: str = "2026-05-21T01:00:00Z",
) -> PairingConsumptionResult:
    current = _current_time(now)
    consumed_at = _format_datetime(current)

    if challenge.consumed_at is not None or challenge.enrollment_state != "pairing_pending":
        return _pairing_reject(
            challenge,
            status="pairing_code_reused",
            reasons=("pairing_code_already_consumed",),
            current=consumed_at,
        )

    if current >= parse_envelope_datetime(challenge.expires_at):
        return _pairing_reject(
            replace(challenge, enrollment_state="expired"),
            status="expired_pairing_code",
            reasons=("pairing_code_expired",),
            current=consumed_at,
        )

    if challenge.pairing_code_hash != pairing_code_hash(
        challenge_id=challenge.challenge_id,
        node_id=challenge.node_id,
        pairing_code=pairing_code,
    ):
        return _pairing_reject(
            challenge,
            status="invalid_pairing_code",
            reasons=("pairing_code_hash_mismatch",),
            current=consumed_at,
        )

    manifest = signed_manifest.manifest
    if manifest.identity.node_id != challenge.node_id:
        return _pairing_reject(
            replace(challenge, consumed_at=consumed_at),
            status="node_mismatch",
            reasons=("manifest_node_id_mismatch",),
            current=consumed_at,
        )
    if signed_manifest.signature.key_id != challenge.key_id:
        return _pairing_reject(
            replace(challenge, consumed_at=consumed_at),
            status="key_mismatch",
            reasons=("manifest_key_id_mismatch",),
            current=consumed_at,
        )
    if challenge.mode not in manifest.mode_compatibility:
        return _pairing_reject(
            replace(challenge, consumed_at=consumed_at),
            status="mode_incompatible",
            reasons=("manifest_mode_incompatible",),
            current=consumed_at,
        )

    verification = verify_local_node_manifest(
        signed_manifest,
        public_key_b64=public_key_b64,
        expected_audience=challenge.audience,
        now=current,
    )
    enrollment_state: EnrollmentState = "enrolled_verified" if verification.verified else "enrolled_unverified"
    updated_challenge = replace(challenge, consumed_at=consumed_at, enrollment_state=enrollment_state)
    session = LocalNodeEnrollmentSession(
        session_id=session_id,
        enrolled_node_id=challenge.node_id,
        key_id=challenge.key_id,
        manifest_id=manifest.manifest_id,
        mode=challenge.mode,
        session_issued_at=consumed_at,
        session_expires_at=session_expires_at,
        session_token_hash=_session_token_hash(session_id=session_id, session_token=session_token),
        capabilities=verification.declared_capabilities if verification.verified else (),
        approval_required_capabilities=(
            verification.approval_required_capabilities if verification.verified else ()
        ),
        enrollment_state=enrollment_state,
        signed_origin_verified=verification.verified,
        trusted=False,
        production_trust_material=False,
    )
    return PairingConsumptionResult(
        status=enrollment_state,
        accepted=True,
        challenge=updated_challenge,
        session=session,
        manifest_verification=verification,
        reasons=verification.reasons,
    )


def revoke_enrollment_session(session: LocalNodeEnrollmentSession) -> LocalNodeEnrollmentSession:
    return replace(session, revoked=True, enrollment_state="revoked")


def enrollment_session_state(
    session: LocalNodeEnrollmentSession,
    *,
    now: datetime | None = None,
) -> EnrollmentState:
    if session.revoked or session.enrollment_state == "revoked":
        return "revoked"
    current = _current_time(now)
    if current >= parse_envelope_datetime(session.session_expires_at):
        return "expired"
    return session.enrollment_state


def evaluate_enrollment_session_capability(
    session: LocalNodeEnrollmentSession,
    capability: str,
    *,
    now: datetime | None = None,
) -> LocalNodeSessionCapabilityDecision:
    state = enrollment_session_state(session, now=now)
    if state == "revoked":
        return LocalNodeSessionCapabilityDecision(
            status="revoked",
            allowed=False,
            approval_required=True,
            session_state=state,
            capability=capability,
            reasons=("session_revoked",),
        )
    if state == "expired":
        return LocalNodeSessionCapabilityDecision(
            status="expired",
            allowed=False,
            approval_required=True,
            session_state=state,
            capability=capability,
            reasons=("session_expired",),
        )
    if state != "enrolled_verified":
        return LocalNodeSessionCapabilityDecision(
            status="not_verified",
            allowed=False,
            approval_required=True,
            session_state=state,
            capability=capability,
            reasons=("session_not_verified",),
        )
    if capability not in session.capabilities:
        return LocalNodeSessionCapabilityDecision(
            status="capability_not_declared",
            allowed=False,
            approval_required=True,
            session_state=state,
            capability=capability,
            reasons=("session_capability_not_declared",),
        )

    approval_required = capability in session.approval_required_capabilities or capability in APPROVAL_GATED_CAPABILITIES
    return LocalNodeSessionCapabilityDecision(
        status="approval_required" if approval_required else "allowed",
        allowed=True,
        approval_required=approval_required,
        session_state=state,
        capability=capability,
        reasons=("session_bound_capability_declared",),
    )


def _pairing_reject(
    challenge: PairingChallenge,
    *,
    status: PairingConsumeStatus,
    reasons: tuple[str, ...],
    current: str,
) -> PairingConsumptionResult:
    del current
    return PairingConsumptionResult(
        status=status,
        accepted=False,
        challenge=challenge,
        session=None,
        manifest_verification=None,
        reasons=reasons,
    )


def _current_time(now: datetime | None) -> datetime:
    return now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _session_token_hash(*, session_id: str, session_token: str | None) -> str | None:
    if session_token is None:
        return None
    payload = f"{session_id}:{session_token}".encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
