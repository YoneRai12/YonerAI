from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION = "yonerai-extension-capability-manifest/v0.1"

SAFE_EXTENSION_CAPABILITIES = frozenset({"mock_search", "ledger"})
OVERBROAD_EXTENSION_CAPABILITIES = frozenset(
    {
        "private_files",
        "workspace_file_access",
        "pc_operations",
        "local_tools",
        "dangerous_operation",
        "dangerous_operations",
        "production_deploy",
        "live_discord_gateway",
        "official_private_control_plane",
    }
)

ExtensionManifestStatus = Literal["accepted_for_review", "denied", "policy_drift"]


@dataclass(frozen=True)
class ExtensionCapabilityManifest:
    extension_id: str
    version: str
    declared_capabilities: tuple[str, ...]
    schema_version: str = EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["declared_capabilities"] = list(self.declared_capabilities)
        return payload


@dataclass(frozen=True)
class ExtensionCapabilityDecision:
    schema_version: str
    extension_id: str
    status: ExtensionManifestStatus
    accepted_capabilities: tuple[str, ...]
    denied_capabilities: tuple[str, ...]
    duplicate_capabilities: tuple[str, ...]
    overbroad_capabilities: tuple[str, ...]
    unknown_capabilities: tuple[str, ...]
    can_execute: bool
    audit_required: bool
    policy_drift: bool
    production_trust_material: bool
    network_required: bool
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["accepted_capabilities"] = list(self.accepted_capabilities)
        payload["denied_capabilities"] = list(self.denied_capabilities)
        payload["duplicate_capabilities"] = list(self.duplicate_capabilities)
        payload["overbroad_capabilities"] = list(self.overbroad_capabilities)
        payload["unknown_capabilities"] = list(self.unknown_capabilities)
        payload["reasons"] = list(self.reasons)
        return payload


def build_extension_capability_manifest(
    *,
    extension_id: str = "local-dev-extension",
    version: str = "0.1.0-test",
    declared_capabilities: tuple[str, ...] = ("mock_search",),
) -> ExtensionCapabilityManifest:
    return ExtensionCapabilityManifest(
        extension_id=_safe_extension_id(extension_id),
        version=str(version or "unknown")[:64],
        declared_capabilities=declared_capabilities,
    )


def evaluate_extension_capability_manifest(
    manifest: ExtensionCapabilityManifest,
    *,
    policy_drift: bool = False,
) -> ExtensionCapabilityDecision:
    normalized_all = [_normalize_capability(capability) for capability in manifest.declared_capabilities]
    normalized_all = [capability for capability in normalized_all if capability]
    declared_unique = tuple(dict.fromkeys(normalized_all))
    duplicates = tuple(
        capability for capability in declared_unique if normalized_all.count(capability) > 1
    )
    overbroad = tuple(
        capability for capability in declared_unique if capability in OVERBROAD_EXTENSION_CAPABILITIES or "*" in capability
    )
    unknown = tuple(
        capability
        for capability in declared_unique
        if capability not in SAFE_EXTENSION_CAPABILITIES and capability not in overbroad
    )
    denied = tuple(dict.fromkeys((*duplicates, *overbroad, *unknown)))
    reasons: list[str] = []

    if policy_drift:
        reasons.append("extension_policy_drift_detected")
        status: ExtensionManifestStatus = "policy_drift"
    elif denied:
        status = "denied"
    else:
        status = "accepted_for_review"

    if duplicates:
        reasons.append("duplicate_extension_capability_denied")
    if overbroad:
        reasons.append("overbroad_extension_capability_denied")
    if unknown:
        reasons.append("unknown_extension_capability_denied")
    if status == "accepted_for_review":
        reasons.append("extension_capabilities_declared_no_execution")

    accepted = tuple(capability for capability in declared_unique if capability in SAFE_EXTENSION_CAPABILITIES)
    if status != "accepted_for_review":
        accepted = ()

    return ExtensionCapabilityDecision(
        schema_version=EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION,
        extension_id=manifest.extension_id,
        status=status,
        accepted_capabilities=accepted,
        denied_capabilities=denied,
        duplicate_capabilities=duplicates,
        overbroad_capabilities=overbroad,
        unknown_capabilities=unknown,
        can_execute=False,
        audit_required=True,
        policy_drift=policy_drift,
        production_trust_material=False,
        network_required=False,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _normalize_capability(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(".", "_")


def _safe_extension_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown-extension"
    if "\\" in text or "/" in text or ":" in text:
        return "extension-id-redacted"
    return text[:80]
