from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION = "yonerai-extension-capability-manifest/v0.2"

SAFE_EXTENSION_CAPABILITIES = frozenset({"mock_search", "ledger"})
SAFE_EXTENSION_RISK_TAGS = frozenset(
    {
        "fixture_only",
        "hash_only",
        "local_only",
        "mock",
        "no_network",
        "read_only",
        "redacted",
    }
)
DENIED_EXTENSION_RISK_TAGS = frozenset(
    {
        "arbitrary_file_access",
        "arbitrary_shell",
        "live_discord",
        "network",
        "pc_operation",
        "private_file_read",
        "production_deploy",
        "production_trust",
        "remote_execution",
        "secret_access",
        "write_file",
    }
)
ALLOWED_OWNER_SCOPES = frozenset({"local_owner", "workspace_owner"})
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
ALLOWED_FIELD_TYPES = frozenset({"string", "integer", "number", "boolean", "json", "hash_ref"})
ALLOWED_FIELD_SENSITIVITIES = frozenset({"public", "redacted_local", "private_local"})

ExtensionManifestStatus = Literal["accepted_for_review", "denied", "policy_drift"]


@dataclass(frozen=True)
class ExtensionIOField:
    name: str
    type: str
    required: bool
    sensitivity: str
    description: str = ""

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExtensionCapabilityManifest:
    extension_id: str
    version: str
    declared_capabilities: tuple[str, ...]
    typed_inputs: tuple[ExtensionIOField, ...]
    typed_outputs: tuple[ExtensionIOField, ...]
    risk_tags: tuple[str, ...]
    owner_scope: str
    audit_event_required: bool
    args_hash_required: bool
    schema_version: str = EXTENSION_CAPABILITY_MANIFEST_SCHEMA_VERSION

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["declared_capabilities"] = list(payload["declared_capabilities"])
        payload["typed_inputs"] = list(payload["typed_inputs"])
        payload["typed_outputs"] = list(payload["typed_outputs"])
        payload["risk_tags"] = list(payload["risk_tags"])
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
    typed_inputs: tuple[ExtensionIOField, ...]
    typed_outputs: tuple[ExtensionIOField, ...]
    invalid_io_fields: tuple[str, ...]
    risk_tags: tuple[str, ...]
    denied_risk_tags: tuple[str, ...]
    unknown_risk_tags: tuple[str, ...]
    owner_scope: str
    owner_scope_allowed: bool
    args_hash_required: bool
    can_execute: bool
    audit_required: bool
    audit_event_required: bool
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
        payload["typed_inputs"] = [field.to_public_dict() for field in self.typed_inputs]
        payload["typed_outputs"] = [field.to_public_dict() for field in self.typed_outputs]
        payload["invalid_io_fields"] = list(self.invalid_io_fields)
        payload["risk_tags"] = list(self.risk_tags)
        payload["denied_risk_tags"] = list(self.denied_risk_tags)
        payload["unknown_risk_tags"] = list(self.unknown_risk_tags)
        payload["reasons"] = list(self.reasons)
        return payload


def build_extension_capability_manifest(
    *,
    extension_id: str = "local-dev-extension",
    version: str = "0.1.0-test",
    declared_capabilities: tuple[str, ...] = ("mock_search",),
    typed_inputs: tuple[ExtensionIOField, ...] | None = None,
    typed_outputs: tuple[ExtensionIOField, ...] | None = None,
    risk_tags: tuple[str, ...] = ("fixture_only", "mock", "read_only", "no_network"),
    owner_scope: str = "local_owner",
    audit_event_required: object = True,
    args_hash_required: object = True,
) -> ExtensionCapabilityManifest:
    normalized_capabilities = tuple(_normalize_capability(capability) for capability in declared_capabilities)
    return ExtensionCapabilityManifest(
        extension_id=_safe_extension_id(extension_id),
        version=str(version or "unknown")[:64],
        declared_capabilities=declared_capabilities,
        typed_inputs=typed_inputs if typed_inputs is not None else _default_typed_inputs(normalized_capabilities),
        typed_outputs=typed_outputs if typed_outputs is not None else _default_typed_outputs(normalized_capabilities),
        risk_tags=tuple(dict.fromkeys(_normalize_capability(tag) for tag in risk_tags if str(tag or "").strip())),
        owner_scope=_normalize_capability(owner_scope) or "unknown_owner_scope",
        audit_event_required=audit_event_required is True,
        args_hash_required=args_hash_required is True,
    )


def evaluate_extension_capability_manifest(
    manifest: ExtensionCapabilityManifest,
    *,
    policy_drift: bool = False,
) -> ExtensionCapabilityDecision:
    normalized_all = [_normalize_capability(capability) for capability in manifest.declared_capabilities]
    normalized_all = [capability for capability in normalized_all if capability]
    declared_unique = tuple(dict.fromkeys(normalized_all))
    risk_tags = tuple(dict.fromkeys(_normalize_capability(tag) for tag in manifest.risk_tags if tag))
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
    denied_risk_tags = tuple(tag for tag in risk_tags if tag in DENIED_EXTENSION_RISK_TAGS)
    unknown_risk_tags = tuple(
        tag for tag in risk_tags if tag not in SAFE_EXTENSION_RISK_TAGS and tag not in DENIED_EXTENSION_RISK_TAGS
    )
    invalid_io_fields = _invalid_io_fields((*manifest.typed_inputs, *manifest.typed_outputs))
    owner_scope_allowed = manifest.owner_scope in ALLOWED_OWNER_SCOPES
    denied = tuple(dict.fromkeys((*duplicates, *overbroad, *unknown)))
    reasons: list[str] = []

    if policy_drift:
        reasons.append("extension_policy_drift_detected")
        status: ExtensionManifestStatus = "policy_drift"
    elif (
        denied
        or denied_risk_tags
        or unknown_risk_tags
        or invalid_io_fields
        or not owner_scope_allowed
        or not manifest.audit_event_required
        or not manifest.args_hash_required
    ):
        status = "denied"
    else:
        status = "accepted_for_review"

    if duplicates:
        reasons.append("duplicate_extension_capability_denied")
    if overbroad:
        reasons.append("overbroad_extension_capability_denied")
    if unknown:
        reasons.append("unknown_extension_capability_denied")
    if denied_risk_tags:
        reasons.append("denied_extension_risk_tag")
    if unknown_risk_tags:
        reasons.append("unknown_extension_risk_tag_denied")
    if invalid_io_fields:
        reasons.append("invalid_extension_io_contract_denied")
    if not owner_scope_allowed:
        reasons.append("owner_scope_not_allowed")
    if not manifest.audit_event_required:
        reasons.append("audit_event_required")
    if not manifest.args_hash_required:
        reasons.append("args_hash_required")
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
        typed_inputs=manifest.typed_inputs,
        typed_outputs=manifest.typed_outputs,
        invalid_io_fields=invalid_io_fields,
        risk_tags=risk_tags,
        denied_risk_tags=denied_risk_tags,
        unknown_risk_tags=unknown_risk_tags,
        owner_scope=manifest.owner_scope,
        owner_scope_allowed=owner_scope_allowed,
        args_hash_required=manifest.args_hash_required,
        can_execute=False,
        audit_required=True,
        audit_event_required=manifest.audit_event_required,
        policy_drift=policy_drift,
        production_trust_material=False,
        network_required=False,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _normalize_capability(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(".", "_")


def _default_typed_inputs(capabilities: tuple[str, ...]) -> tuple[ExtensionIOField, ...]:
    fields: list[ExtensionIOField] = []
    if "mock_search" in capabilities:
        fields.append(
            ExtensionIOField(
                name="query",
                type="string",
                required=True,
                sensitivity="public",
                description="Public mock-search query fixture.",
            )
        )
    if "ledger" in capabilities:
        fields.append(
            ExtensionIOField(
                name="run_id",
                type="string",
                required=False,
                sensitivity="redacted_local",
                description="Optional redacted local run identifier.",
            )
        )
    return tuple(fields)


def _default_typed_outputs(capabilities: tuple[str, ...]) -> tuple[ExtensionIOField, ...]:
    fields: list[ExtensionIOField] = []
    if "mock_search" in capabilities:
        fields.append(
            ExtensionIOField(
                name="result_refs",
                type="json",
                required=True,
                sensitivity="public",
                description="Public fixture result references only.",
            )
        )
    if "ledger" in capabilities:
        fields.append(
            ExtensionIOField(
                name="ledger_ref",
                type="hash_ref",
                required=False,
                sensitivity="redacted_local",
                description="Hash/reference to a redacted local run entry.",
            )
        )
    return tuple(fields)


def _invalid_io_fields(fields: tuple[ExtensionIOField, ...]) -> tuple[str, ...]:
    invalid: list[str] = []
    for field in fields:
        name = _normalize_capability(field.name)
        field_type = _normalize_capability(field.type)
        sensitivity = _normalize_capability(field.sensitivity)
        if not name:
            invalid.append("missing_name")
        if field_type not in ALLOWED_FIELD_TYPES:
            invalid.append(f"{name or 'unknown'}:invalid_type")
        if sensitivity not in ALLOWED_FIELD_SENSITIVITIES:
            invalid.append(f"{name or 'unknown'}:invalid_sensitivity")
    return tuple(dict.fromkeys(invalid))


def _safe_extension_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown-extension"
    if "\\" in text or "/" in text or ":" in text:
        return "extension-id-redacted"
    return text[:80]
