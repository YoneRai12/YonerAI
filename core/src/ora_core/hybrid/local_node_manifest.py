from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from ..three_mode import ModeName
from .envelope import DEFAULT_CONTROL_PLANE_AUDIENCE, parse_envelope_datetime


LOCAL_NODE_MANIFEST_SCHEMA_VERSION = "yonerai-local-node-manifest-test/v1"
LOCAL_NODE_MANIFEST_SIGNATURE_SCHEMA_VERSION = "yonerai-local-node-manifest-signature-test/v1"
LOCAL_NODE_MANIFEST_ALGORITHM = "ed25519-test-only"

CapabilityName = Literal[
    "private_files",
    "pc_operations",
    "local_tools",
    "heavy_work",
    "dangerous_operations",
    "self_evolution_proposals",
]
ManifestVerificationStatus = Literal[
    "verified",
    "invalid_signature",
    "wrong_key_id",
    "expired",
    "not_yet_valid",
    "wrong_audience",
    "unsupported_algorithm",
    "unsupported_schema",
]

KNOWN_LOCAL_NODE_CAPABILITIES = frozenset(
    {
        "private_files",
        "pc_operations",
        "local_tools",
        "heavy_work",
        "dangerous_operations",
        "self_evolution_proposals",
    }
)
APPROVAL_GATED_CAPABILITIES = frozenset(
    {
        "private_files",
        "pc_operations",
        "local_tools",
        "heavy_work",
        "dangerous_operations",
        "self_evolution_proposals",
    }
)


@dataclass(frozen=True)
class LocalNodeIdentity:
    node_id: str
    issuer: str
    display_name: str
    non_production: bool = True

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LocalNodeCapabilityManifest:
    manifest_id: str
    identity: LocalNodeIdentity
    audience: str
    issued_at: str
    expires_at: str
    capabilities: tuple[str, ...]
    mode_compatibility: tuple[ModeName, ...]
    production_trust_material: bool = False
    schema_version: str = LOCAL_NODE_MANIFEST_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["mode_compatibility"] = list(self.mode_compatibility)
        return payload


@dataclass(frozen=True)
class LocalNodeManifestSignature:
    algorithm: str
    key_id: str
    signature_b64: str
    schema_version: str = LOCAL_NODE_MANIFEST_SIGNATURE_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SignedLocalNodeManifest:
    manifest: LocalNodeCapabilityManifest
    signature: LocalNodeManifestSignature

    def to_public_dict(self) -> dict[str, object]:
        return {
            "manifest": self.manifest.to_public_dict(),
            "signature": self.signature.to_public_dict(),
        }


@dataclass(frozen=True)
class LocalNodeManifestVerification:
    status: ManifestVerificationStatus
    verified: bool
    trusted: bool
    production_trust_material: bool
    declared_capabilities: tuple[str, ...]
    denied_capabilities: tuple[str, ...]
    approval_required_capabilities: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["declared_capabilities"] = list(self.declared_capabilities)
        payload["denied_capabilities"] = list(self.denied_capabilities)
        payload["approval_required_capabilities"] = list(self.approval_required_capabilities)
        payload["reasons"] = list(self.reasons)
        return payload


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _private_key_from_b64(private_key_b64: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64.encode("ascii")))


def _public_key_from_b64(public_key_b64: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64.encode("ascii")))


def local_node_public_key_id(public_key_b64: str) -> str:
    raw = base64.b64decode(public_key_b64.encode("ascii"))
    return hashlib.sha256(raw).hexdigest()


def generate_test_local_node_keypair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(private_raw).decode("ascii"), base64.b64encode(public_raw).decode("ascii")


def build_test_local_node_manifest(
    *,
    manifest_id: str = "test-local-node-manifest",
    node_id: str = "test-local-node",
    issuer: str = "local-dev-control-plane-simulator",
    audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE,
    issued_at: str = "2026-05-21T00:00:00Z",
    expires_at: str = "2026-05-22T00:00:00Z",
    capabilities: tuple[str, ...] = (
        "private_files",
        "pc_operations",
        "local_tools",
        "heavy_work",
        "dangerous_operations",
        "self_evolution_proposals",
    ),
    mode_compatibility: tuple[ModeName, ...] = ("official_hybrid_private", "full_private_self_host"),
) -> LocalNodeCapabilityManifest:
    return LocalNodeCapabilityManifest(
        manifest_id=manifest_id,
        identity=LocalNodeIdentity(
            node_id=node_id,
            issuer=issuer,
            display_name="Test Local Node",
            non_production=True,
        ),
        audience=audience,
        issued_at=issued_at,
        expires_at=expires_at,
        capabilities=capabilities,
        mode_compatibility=mode_compatibility,
        production_trust_material=False,
    )


def sign_local_node_manifest(
    manifest: LocalNodeCapabilityManifest,
    *,
    private_key_b64: str,
) -> SignedLocalNodeManifest:
    public_key_b64 = base64.b64encode(
        _private_key_from_b64(private_key_b64)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    signature_raw = _private_key_from_b64(private_key_b64).sign(_canonical_json(manifest.to_public_dict()))
    return SignedLocalNodeManifest(
        manifest=manifest,
        signature=LocalNodeManifestSignature(
            algorithm=LOCAL_NODE_MANIFEST_ALGORITHM,
            key_id=local_node_public_key_id(public_key_b64),
            signature_b64=base64.b64encode(signature_raw).decode("ascii"),
        ),
    )


def verify_local_node_manifest(
    signed_manifest: SignedLocalNodeManifest,
    *,
    public_key_b64: str,
    expected_audience: str = DEFAULT_CONTROL_PLANE_AUDIENCE,
    now: datetime | None = None,
) -> LocalNodeManifestVerification:
    manifest = signed_manifest.manifest
    signature = signed_manifest.signature
    reasons: list[str] = []
    status: ManifestVerificationStatus = "verified"

    if manifest.schema_version != LOCAL_NODE_MANIFEST_SCHEMA_VERSION:
        reasons.append("unsupported_manifest_schema")
        status = "unsupported_schema"
    if signature.schema_version != LOCAL_NODE_MANIFEST_SIGNATURE_SCHEMA_VERSION:
        reasons.append("unsupported_signature_schema")
        status = "unsupported_schema"
    if signature.algorithm != LOCAL_NODE_MANIFEST_ALGORITHM:
        reasons.append("unsupported_signature_algorithm")
        status = "unsupported_algorithm"
    if manifest.audience != expected_audience:
        reasons.append("wrong_audience")
        status = "wrong_audience"
    expected_key_id = local_node_public_key_id(public_key_b64)
    if signature.key_id != expected_key_id:
        reasons.append("wrong_key_id")
        status = "wrong_key_id"

    current = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    try:
        issued_at = parse_envelope_datetime(manifest.issued_at)
        expires_at = parse_envelope_datetime(manifest.expires_at)
    except ValueError:
        reasons.append("invalid_timestamp")
        status = "expired"
    else:
        if current < issued_at:
            reasons.append("not_yet_valid")
            status = "not_yet_valid"
        if current >= expires_at:
            reasons.append("expired_manifest")
            status = "expired"

    known_capabilities = tuple(capability for capability in manifest.capabilities if capability in KNOWN_LOCAL_NODE_CAPABILITIES)
    denied_capabilities = tuple(capability for capability in manifest.capabilities if capability not in KNOWN_LOCAL_NODE_CAPABILITIES)
    if denied_capabilities:
        reasons.append("unknown_capability_denied")

    if not reasons or reasons == ["unknown_capability_denied"]:
        try:
            signature_raw = base64.b64decode(signature.signature_b64.encode("ascii"))
            _public_key_from_b64(public_key_b64).verify(signature_raw, _canonical_json(manifest.to_public_dict()))
        except (InvalidSignature, ValueError) as exc:
            del exc
            reasons.append("invalid_signature")
            status = "invalid_signature"

    verified = status == "verified"
    if not verified:
        known_capabilities = ()

    return LocalNodeManifestVerification(
        status=status,
        verified=verified,
        trusted=False,
        production_trust_material=False,
        declared_capabilities=known_capabilities,
        denied_capabilities=denied_capabilities,
        approval_required_capabilities=tuple(
            capability for capability in known_capabilities if capability in APPROVAL_GATED_CAPABILITIES
        ),
        reasons=tuple(dict.fromkeys(reasons or ("manifest_verified_origin_integrity_only",))),
    )
