from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Mapping


CONFIG_SCHEMA_VERSION = "yonerai-cli-config/v0.7"
LANGUAGES = ("ja", "en")
PROVIDER_PREFERENCES = ("auto", "mock", "local", "openai-compatible", "anthropic", "gemini")
APPROVAL_MODES = ("prompt", "deny")
AGENT_MODES = ("plan_readonly", "build_safe", "review", "memory")
FILE_ACCESS_MODES = ("workspace_only", "disabled")
MEMORY_DEFAULT_SCOPES = ("local", "local_private", "procedural", "shared_preference", "project", "session")
MODEL_RE = re.compile(r"^[A-Za-z0-9_.:+/-]{1,80}$")

DEFAULT_CONFIG: dict[str, object] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "language": None,
    "provider_preference": "auto",
    "model_preference": "auto",
    "agent_mode": "plan_readonly",
    "approval_mode": "prompt",
    "file_access_mode": "workspace_only",
    "live_provider_enabled": False,
    "network_enabled": False,
    "tools_mode": "dry_run",
    "ledger_enabled": False,
    "memory_enabled": True,
    "memory_default_scope": "local_private",
    "memory_cloud_to_local_preview_enabled": True,
    "memory_local_to_cloud_approval_required": True,
    "memory_self_evolution_signal_enabled": False,
    "update_notice_enabled": False,
    "auth_onboarding_seen": False,
    "google_auth_enabled": False,
    "openai_data_sharing_enabled": False,
}


class ConfigError(ValueError):
    pass


def default_config_path(env: Mapping[str, str | None] | None = None) -> Path:
    source = os.environ if env is None else env
    override = str(source.get("YONERAI_CLI_CONFIG_PATH") or "").strip()
    if override:
        return Path(override).expanduser()
    appdata = str(source.get("APPDATA") or "").strip()
    if appdata:
        return Path(appdata) / "YonerAI" / "cli-config.json"
    xdg_config = str(source.get("XDG_CONFIG_HOME") or "").strip()
    if xdg_config:
        return Path(xdg_config) / "yonerai" / "cli-config.json"
    return Path.home() / ".config" / "yonerai" / "cli-config.json"


def load_cli_config(path: str | Path | None = None, *, env: Mapping[str, str | None] | None = None) -> dict[str, object]:
    config_path = Path(path).expanduser() if path is not None else default_config_path(env)
    if not config_path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("YonerAI CLI config could not be read as JSON.") from exc
    if not isinstance(raw, dict):
        raise ConfigError("YonerAI CLI config must be a JSON object.")
    merged = dict(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        if key in raw:
            merged[key] = raw[key]
    return validate_cli_config(merged)


def save_cli_config(config: Mapping[str, object], path: str | Path | None = None, *, env: Mapping[str, str | None] | None = None) -> dict[str, object]:
    config_path = Path(path).expanduser() if path is not None else default_config_path(env)
    validated = validate_cli_config(config)
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(validated, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise ConfigError("YonerAI CLI config could not be written.") from exc
    return validated


def set_cli_config_value(
    key: str,
    value: str,
    path: str | Path | None = None,
    *,
    env: Mapping[str, str | None] | None = None,
) -> dict[str, object]:
    config = load_cli_config(path, env=env)
    normalized_key = normalize_config_key(key)
    config[normalized_key] = parse_config_value(normalized_key, value)
    return save_cli_config(config, path, env=env)


def validate_cli_config(config: Mapping[str, object]) -> dict[str, object]:
    merged = dict(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        if key in config:
            merged[key] = config[key]
    merged["schema_version"] = CONFIG_SCHEMA_VERSION
    language = merged.get("language")
    if language is not None and language not in LANGUAGES:
        raise ConfigError("language must be ja or en.")
    if merged.get("provider_preference") not in PROVIDER_PREFERENCES:
        raise ConfigError("provider_preference is invalid.")
    model = merged.get("model_preference")
    if not isinstance(model, str) or not MODEL_RE.fullmatch(model) or "://" in model or "\\" in model:
        raise ConfigError("model_preference is invalid.")
    if merged.get("approval_mode") not in APPROVAL_MODES:
        raise ConfigError("approval_mode is invalid.")
    if merged.get("agent_mode") not in AGENT_MODES:
        raise ConfigError("agent_mode is invalid.")
    if merged.get("file_access_mode") not in FILE_ACCESS_MODES:
        raise ConfigError("file_access_mode is invalid.")
    for key in (
        "live_provider_enabled",
        "network_enabled",
        "ledger_enabled",
        "memory_enabled",
        "memory_cloud_to_local_preview_enabled",
        "memory_local_to_cloud_approval_required",
        "memory_self_evolution_signal_enabled",
        "update_notice_enabled",
        "auth_onboarding_seen",
        "google_auth_enabled",
        "openai_data_sharing_enabled",
    ):
        if type(merged.get(key)) is not bool:
            raise ConfigError(f"{key} must be a boolean.")
    if merged.get("memory_default_scope") not in MEMORY_DEFAULT_SCOPES:
        raise ConfigError("memory_default_scope is invalid.")
    if merged.get("memory_local_to_cloud_approval_required") is not True:
        raise ConfigError("memory_local_to_cloud_approval_required must stay true in the public runtime.")
    if merged.get("tools_mode") != "dry_run":
        raise ConfigError("tools_mode must be dry_run in the public alpha.")
    return merged


def normalize_config_key(key: str) -> str:
    normalized = key.strip().replace("-", "_")
    aliases = {
        "provider": "provider_preference",
        "model": "model_preference",
        "model_preference": "model_preference",
        "agent_mode": "agent_mode",
        "mode": "agent_mode",
        "language": "language",
        "lang": "language",
        "approval": "approval_mode",
        "file_access": "file_access_mode",
        "live_provider": "live_provider_enabled",
        "network": "network_enabled",
        "ledger": "ledger_enabled",
        "history": "ledger_enabled",
        "memory": "memory_enabled",
        "memory_enabled": "memory_enabled",
        "memory_default_scope": "memory_default_scope",
        "memory_scope": "memory_default_scope",
        "memory_cloud_to_local_preview": "memory_cloud_to_local_preview_enabled",
        "memory_cloud_preview": "memory_cloud_to_local_preview_enabled",
        "memory_local_to_cloud_approval_required": "memory_local_to_cloud_approval_required",
        "memory_self_evolution_signal": "memory_self_evolution_signal_enabled",
        "self_evolution_memory": "memory_self_evolution_signal_enabled",
        "update_notice": "update_notice_enabled",
        "updates": "update_notice_enabled",
        "google_auth": "google_auth_enabled",
        "auth_google": "google_auth_enabled",
        "openai_data_sharing": "openai_data_sharing_enabled",
        "data_sharing": "openai_data_sharing_enabled",
        "shared_traffic": "openai_data_sharing_enabled",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in DEFAULT_CONFIG or normalized == "schema_version":
        raise ConfigError("unsupported config key.")
    return normalized


def parse_config_value(key: str, value: str) -> object:
    raw = value.strip()
    if key == "language":
        if raw not in LANGUAGES:
            raise ConfigError("language must be ja or en.")
        return raw
    if key == "provider_preference":
        if raw not in PROVIDER_PREFERENCES:
            raise ConfigError("provider must be auto, mock, local, openai-compatible, anthropic, or gemini.")
        return raw
    if key == "model_preference":
        if not MODEL_RE.fullmatch(raw) or "://" in raw or "\\" in raw:
            raise ConfigError("model must be auto or a simple provider model id.")
        return raw
    if key == "agent_mode":
        aliases = {
            "計画": "plan_readonly",
            "読み取り": "plan_readonly",
            "読み取り専用": "plan_readonly",
            "plan": "plan_readonly",
            "plan-readonly": "plan_readonly",
            "readonly": "plan_readonly",
            "read-only": "plan_readonly",
            "read_only": "plan_readonly",
            "安全実行": "build_safe",
            "ビルド": "build_safe",
            "構築": "build_safe",
            "build": "build_safe",
            "execute-safe": "build_safe",
            "safe-build": "build_safe",
            "レビュー": "review",
            "査読": "review",
            "reviewer": "review",
            "記憶": "memory",
            "メモリ": "memory",
        }
        normalized = aliases.get(raw, aliases.get(raw.lower(), raw))
        if normalized not in AGENT_MODES:
            raise ConfigError("agent mode must be plan_readonly, build_safe, review, or memory.")
        return normalized
    if key == "approval_mode":
        if raw not in APPROVAL_MODES:
            raise ConfigError("approval mode must be prompt or deny.")
        return raw
    if key == "file_access_mode":
        if raw not in FILE_ACCESS_MODES:
            raise ConfigError("file access mode must be workspace_only or disabled.")
        return raw
    if key == "memory_default_scope":
        if raw not in MEMORY_DEFAULT_SCOPES:
            raise ConfigError(
                "memory default scope must be local, local_private, procedural, shared_preference, project, or session."
            )
        return raw
    if key == "memory_local_to_cloud_approval_required":
        if raw.lower() in {"true", "1", "yes", "on"}:
            return True
        raise ConfigError("local-to-cloud memory approval cannot be disabled in the public runtime.")
    if key in {
        "live_provider_enabled",
        "network_enabled",
        "ledger_enabled",
        "memory_enabled",
        "memory_cloud_to_local_preview_enabled",
        "memory_self_evolution_signal_enabled",
        "update_notice_enabled",
        "google_auth_enabled",
        "openai_data_sharing_enabled",
    }:
        if raw.lower() in {"true", "1", "yes", "on"}:
            return True
        if raw.lower() in {"false", "0", "no", "off"}:
            return False
        raise ConfigError(f"{key} must be true or false.")
    raise ConfigError("unsupported config key.")


def build_config_report(config: Mapping[str, object], *, exists: bool) -> dict[str, object]:
    validated = validate_cli_config(config)
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "ok": True,
        "config_exists": exists,
        "path_persisted_in_output": False,
        "secrets_supported": False,
        "config": {
            "language": validated["language"],
            "provider_preference": validated["provider_preference"],
            "model_preference": validated["model_preference"],
            "agent_mode": validated["agent_mode"],
            "approval_mode": validated["approval_mode"],
            "file_access_mode": validated["file_access_mode"],
            "live_provider_enabled": validated["live_provider_enabled"],
            "network_enabled": validated["network_enabled"],
            "tools_mode": validated["tools_mode"],
            "ledger_enabled": validated["ledger_enabled"],
            "memory_enabled": validated["memory_enabled"],
            "memory_default_scope": validated["memory_default_scope"],
            "memory_cloud_to_local_preview_enabled": validated["memory_cloud_to_local_preview_enabled"],
            "memory_local_to_cloud_approval_required": validated["memory_local_to_cloud_approval_required"],
            "memory_self_evolution_signal_enabled": validated["memory_self_evolution_signal_enabled"],
            "update_notice_enabled": validated["update_notice_enabled"],
            "google_auth_enabled": validated["google_auth_enabled"],
            "openai_data_sharing_enabled": validated["openai_data_sharing_enabled"],
        },
        "actions_not_performed": (
            "no provider key storage",
            "no provider key output",
            "no live provider call",
            "no shell execution",
            "no file access outside config file",
        ),
    }
