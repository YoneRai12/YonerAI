from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


POLICY_SCHEMA_VERSION = "yonerai-policy-runtime/v0.1"
POLICY_SCHEMA_REPORT_VERSION = "yonerai-policy-schema/v0.1"


@dataclass(frozen=True)
class ProviderPolicy:
    default_provider: str
    preference: str
    allowed_preferences: tuple[str, ...]
    live_external_provider_enabled: bool
    live_call_default: bool
    key_storage_supported: bool
    key_output_allowed: bool
    local_llm_loopback_only: bool
    configurable: bool


@dataclass(frozen=True)
class ModelPolicy:
    preference: str
    source: str
    ui_hardcoded: bool
    configurable: bool
    unsafe_url_model_ids_allowed: bool


@dataclass(frozen=True)
class PricingPolicy:
    paid_provider_calls_default: bool
    shared_traffic_enabled: bool
    free_usage_claimed: bool
    quota_policy_source: str
    configurable: bool


@dataclass(frozen=True)
class PermissionPolicy:
    approval_mode: str
    file_access_mode: str
    tools_mode: str
    arbitrary_shell_execution: bool
    arbitrary_file_access: bool
    dangerous_actions_default: str
    configurable: bool


@dataclass(frozen=True)
class RuntimePolicy:
    public_runtime: str
    official_cloud_runtime_in_public_repo: bool
    production_oracle_in_public_repo: bool
    live_discord_enabled: bool
    deploy_enabled: bool
    configurable: bool


@dataclass(frozen=True)
class UpdatePolicy:
    notice_enabled: bool
    check_mode: str
    plan_mode: str
    auto_apply_enabled: bool
    forced_silent_update_enabled: bool
    path_mutation_default: bool
    configurable: bool


@dataclass(frozen=True)
class MemorySyncPolicy:
    memory_enabled: bool
    default_scope: str
    cloud_to_local_preview_enabled: bool
    local_to_cloud_approval_required: bool
    local_private_auto_upload: bool
    secret_like_sync_allowed: bool
    configurable: bool


@dataclass(frozen=True)
class CloudEscapePolicy:
    candidate_scope: str
    private_content_allowed: bool
    local_file_content_allowed: bool
    local_node_payload_allowed: bool
    audit_required: bool
    configurable: bool


DEFAULT_ALLOWED_PROVIDERS = ("auto", "mock", "local", "openai-compatible", "anthropic", "gemini")
POLICY_DEFAULTS: dict[str, dict[str, object]] = {
    "provider": {
        "default_provider": "mock",
        "preference": "auto",
        "allowed_preferences": DEFAULT_ALLOWED_PROVIDERS,
        "live_external_provider_enabled": False,
        "live_call_default": False,
        "key_storage_supported": False,
        "key_output_allowed": False,
        "local_llm_loopback_only": True,
        "configurable": True,
    },
    "model": {
        "preference": "auto",
        "source": "local_config",
        "ui_hardcoded": False,
        "configurable": True,
        "unsafe_url_model_ids_allowed": False,
    },
    "pricing": {
        "paid_provider_calls_default": False,
        "shared_traffic_enabled": False,
        "free_usage_claimed": False,
        "quota_policy_source": "contract_only",
        "configurable": False,
    },
    "permission": {
        "approval_mode": "prompt",
        "file_access_mode": "workspace_only",
        "tools_mode": "dry_run",
        "arbitrary_shell_execution": False,
        "arbitrary_file_access": False,
        "dangerous_actions_default": "approval_required_or_deny",
        "configurable": True,
    },
    "runtime": {
        "public_runtime": "cli_local_runtime",
        "official_cloud_runtime_in_public_repo": False,
        "production_oracle_in_public_repo": False,
        "live_discord_enabled": False,
        "deploy_enabled": False,
        "configurable": False,
    },
    "update": {
        "notice_enabled": False,
        "check_mode": "local_manifest_or_explicit_source",
        "plan_mode": "dry_run_only",
        "auto_apply_enabled": False,
        "forced_silent_update_enabled": False,
        "path_mutation_default": False,
        "configurable": True,
    },
    "memory_sync": {
        "memory_enabled": True,
        "default_scope": "local_private",
        "cloud_to_local_preview_enabled": True,
        "local_to_cloud_approval_required": True,
        "local_private_auto_upload": False,
        "secret_like_sync_allowed": False,
        "configurable": True,
    },
    "cloud_escape": {
        "candidate_scope": "public_only_contract_candidate",
        "private_content_allowed": False,
        "local_file_content_allowed": False,
        "local_node_payload_allowed": False,
        "audit_required": True,
        "configurable": False,
    },
}
POLICY_CONFIG_BINDINGS: dict[str, dict[str, tuple[str, object]]] = {
    "provider": {
        "preference": ("provider_preference", "auto"),
        "live_external_provider_enabled": ("live_provider_enabled", False),
    },
    "model": {
        "preference": ("model_preference", "auto"),
    },
    "pricing": {
        "shared_traffic_enabled": ("openai_data_sharing_enabled", False),
    },
    "permission": {
        "approval_mode": ("approval_mode", "prompt"),
        "file_access_mode": ("file_access_mode", "workspace_only"),
        "tools_mode": ("tools_mode", "dry_run"),
    },
    "update": {
        "notice_enabled": ("update_notice_enabled", False),
    },
    "memory_sync": {
        "memory_enabled": ("memory_enabled", True),
        "default_scope": ("memory_default_scope", "local_private"),
        "cloud_to_local_preview_enabled": ("memory_cloud_to_local_preview_enabled", True),
    },
}
POLICY_CLASSES = {
    "provider": ProviderPolicy,
    "model": ModelPolicy,
    "pricing": PricingPolicy,
    "permission": PermissionPolicy,
    "runtime": RuntimePolicy,
    "update": UpdatePolicy,
    "memory_sync": MemorySyncPolicy,
    "cloud_escape": CloudEscapePolicy,
}
POLICY_SCHEMA_FIELDS: dict[str, dict[str, object]] = {
    "provider": {
        "configurable": True,
        "config_keys": ("provider_preference", "live_provider_enabled"),
        "fixed_disabled": ("key_storage_supported", "key_output_allowed", "live_call_default"),
        "future": ("provider_capability_registry",),
    },
    "model": {
        "configurable": True,
        "config_keys": ("model_preference",),
        "fixed_disabled": ("unsafe_url_model_ids_allowed",),
        "future": ("model_catalog",),
    },
    "pricing": {
        "configurable": False,
        "config_keys": ("openai_data_sharing_enabled",),
        "fixed_disabled": ("paid_provider_calls_default", "free_usage_claimed"),
        "future": ("quota_policy_contract",),
    },
    "permission": {
        "configurable": True,
        "config_keys": ("approval_mode", "file_access_mode", "tools_mode"),
        "fixed_disabled": ("arbitrary_shell_execution", "arbitrary_file_access"),
        "future": ("sandbox_profile",),
    },
    "runtime": {
        "configurable": False,
        "config_keys": (),
        "fixed_disabled": (
            "production_oracle_in_public_repo",
            "official_cloud_runtime_in_public_repo",
            "live_discord_enabled",
        ),
        "future": ("private_official_runtime_contract",),
    },
    "update": {
        "configurable": True,
        "config_keys": ("update_notice_enabled",),
        "fixed_disabled": ("auto_apply_enabled", "forced_silent_update_enabled", "path_mutation_default"),
        "future": ("signed_update_policy",),
    },
    "memory_sync": {
        "configurable": True,
        "config_keys": ("memory_enabled", "memory_default_scope", "memory_cloud_to_local_preview_enabled"),
        "fixed_disabled": ("local_private_auto_upload", "secret_like_sync_allowed"),
        "future": ("official_cloud_memory_contract",),
    },
    "cloud_escape": {
        "configurable": False,
        "config_keys": (),
        "fixed_disabled": ("private_content_allowed", "local_file_content_allowed", "local_node_payload_allowed"),
        "future": ("official_private_cloud_approval_flow",),
    },
}


def build_policy_status_report(config: Mapping[str, object] | None = None) -> dict[str, Any]:
    """Build a public-safe, JSON-stable policy status report.

    The report intentionally contains only configuration-derived booleans and
    public product boundaries. It must not include secrets, local paths, host
    inventory, or private runtime details.
    """

    values = dict(config or {})
    provider = _build_policy("provider", values)
    model = _build_policy("model", values)
    pricing = _build_policy("pricing", values)
    permission = _build_policy("permission", values)
    runtime = _build_policy("runtime", values)
    update = _build_policy("update", values)
    memory = _build_policy("memory_sync", values)
    cloud_escape = _build_policy("cloud_escape", values)
    policies = {
        "provider": _policy_dict(provider),
        "model": _policy_dict(model),
        "pricing": _policy_dict(pricing),
        "permission": _policy_dict(permission),
        "runtime": _policy_dict(runtime),
        "update": _policy_dict(update),
        "memory_sync": _policy_dict(memory),
        "cloud_escape": _policy_dict(cloud_escape),
    }
    return {
        "schema_version": POLICY_SCHEMA_VERSION,
        "ok": True,
        "policies": policies,
        "summary": {
            "configurable": [name for name, policy in policies.items() if policy.get("configurable") is True],
            "fixed_disabled": [
                "provider_key_storage",
                "provider_key_output",
                "production_oracle",
                "official_cloud_runtime",
                "live_discord",
                "arbitrary_shell_execution",
                "arbitrary_file_access",
                "auto_update_apply",
                "local_private_memory_upload",
                "openai_shared_traffic_by_default",
            ],
            "source": "local_config_and_public_contracts",
        },
        "actions_not_performed": [
            "no provider calls",
            "no local LLM prompt",
            "no network fetch",
            "no file read",
            "no shell execution",
            "no install",
            "no PATH mutation",
        ],
        "policy_schema": build_policy_schema_report(),
    }


def build_policy_schema_report() -> dict[str, Any]:
    """Return the public policy schema contract used by CLI/TUI surfaces."""

    return {
        "schema_version": POLICY_SCHEMA_REPORT_VERSION,
        "policy_types": {
            name: {key: list(value) if isinstance(value, tuple) else value for key, value in definition.items()}
            for name, definition in POLICY_SCHEMA_FIELDS.items()
        },
        "redaction_boundary": {
            "contains_secrets": False,
            "contains_local_paths": False,
            "contains_provider_keys": False,
            "contains_private_runtime_inventory": False,
        },
    }


def validate_policy_runtime_contract(report: Mapping[str, object]) -> list[str]:
    """Validate the report shape against the public policy schema contract."""

    errors: list[str] = []
    policies = report.get("policies")
    if not isinstance(policies, Mapping):
        return ["missing policies"]
    schema = build_policy_schema_report()["policy_types"]
    for policy_name, schema_definition in schema.items():
        policy = policies.get(policy_name)
        if not isinstance(policy, Mapping):
            errors.append(f"missing policy: {policy_name}")
            continue
        fixed_disabled = schema_definition.get("fixed_disabled")
        if isinstance(fixed_disabled, list):
            for key in fixed_disabled:
                value = policy.get(str(key))
                if value is not False:
                    errors.append(f"{policy_name}.{key} must be false")
    return errors


def _build_policy(policy_name: str, values: Mapping[str, object]) -> object:
    data = dict(POLICY_DEFAULTS[policy_name])
    for field_name, (config_key, default) in POLICY_CONFIG_BINDINGS.get(policy_name, {}).items():
        current = data.get(field_name, default)
        if isinstance(current, bool):
            data[field_name] = _bool(values.get(config_key), bool(default))
        else:
            data[field_name] = _string(values.get(config_key), str(default))
    return POLICY_CLASSES[policy_name](**data)


def _policy_dict(policy: object) -> dict[str, Any]:
    data = asdict(policy)
    for key, value in tuple(data.items()):
        if isinstance(value, tuple):
            data[key] = list(value)
    return data


def _string(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _bool(value: object, default: bool) -> bool:
    if type(value) is bool:
        return value
    return default
