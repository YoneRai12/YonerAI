from __future__ import annotations

import os
from typing import Mapping

from .anthropic import _messages_url
from .contracts import ProviderError
from .gemini import DEFAULT_GEMINI_MODEL, _generate_content_url
from .openai_compatible import _chat_completions_url
from .registry import ProviderRegistry, build_default_provider_registry


PROVIDER_SETUP_SCHEMA_VERSION = "yonerai-provider-setup/v1"


def build_provider_setup_report(
    env: Mapping[str, str | None] | None = None,
    *,
    registry: ProviderRegistry | None = None,
) -> dict[str, object]:
    source = dict(os.environ if env is None else env)
    active_registry = registry or build_default_provider_registry(source)
    providers = [_provider_setup_entry(status, source) for status in active_registry.list_statuses()]
    return {
        "schema_version": PROVIDER_SETUP_SCHEMA_VERSION,
        "network_probe_performed": False,
        "live_call_performed": False,
        "providers": providers,
    }


def _provider_setup_entry(status: dict[str, object], env: Mapping[str, str | None]) -> dict[str, object]:
    provider_id = str(status.get("provider_id") or "unknown")
    configured = bool(status.get("configured"))
    available = bool(status.get("available"))
    reason = str(status.get("reason") or "") or None
    env_status = dict(status.get("env_status") or {})
    entry: dict[str, object] = {
        "provider_id": provider_id,
        "configured": configured,
        "available": available,
        "reason": reason,
        "env_status": env_status,
        "capabilities": _capability_negotiation(provider_id, status),
        "setup_blockers": [],
        "live_ready": False,
        "network_probe_performed": False,
        "live_call_performed": False,
    }
    if provider_id == "mock":
        entry["setup_status"] = "ready"
        entry["live_ready"] = True
        return entry
    if provider_id == "local":
        blockers = _local_provider_blockers(status)
        entry["setup_status"] = _local_provider_setup_status(status)
        entry["live_ready"] = available
        entry["loopback_only"] = True
        entry["setup_blockers"] = blockers
        return entry
    if provider_id == "openai-compatible":
        blockers = _openai_compatible_blockers(env_status, env)
        entry["setup_status"] = _external_provider_setup_status("openai-compatible", blockers)
        entry["live_ready"] = not blockers
        entry["requires_live_flag"] = True
        entry["setup_blockers"] = blockers
        return entry
    if provider_id in {"anthropic", "gemini"}:
        blockers = _external_provider_blockers(provider_id, env_status, env, available, reason)
        entry["setup_status"] = _external_provider_setup_status(provider_id, blockers)
        entry["live_ready"] = not blockers
        entry["requires_live_flag"] = True
        entry["setup_blockers"] = blockers
        return entry

    blockers = []
    if not available:
        blockers.append(reason or f"{provider_id}_provider_not_configured")
    entry["setup_status"] = "ready" if available else "blocked"
    entry["live_ready"] = available and _enabled(env.get(f"YONERAI_{provider_id.upper()}_LIVE"))
    entry["setup_blockers"] = blockers
    return entry


def _capability_negotiation(provider_id: str, status: Mapping[str, object]) -> dict[str, object]:
    raw = status.get("capabilities")
    capabilities = raw if isinstance(raw, Mapping) else {}
    chat = bool(capabilities.get("chat"))
    structured_output = bool(capabilities.get("structured_output"))
    streaming = bool(capabilities.get("streaming"))
    vision = bool(capabilities.get("vision"))
    tool_use = bool(capabilities.get("tool_use"))
    available = bool(status.get("available"))
    safe_for_subagents = bool(available and chat)
    fallback_reason = None
    if not chat:
        fallback_reason = "chat_capability_missing"
    elif not available:
        fallback_reason = "provider_unavailable_or_not_configured"
    elif provider_id not in {"mock", "local", "openai-compatible", "anthropic", "gemini"}:
        fallback_reason = "provider_not_registered_for_subagents"
        safe_for_subagents = False

    return {
        "chat": chat,
        "streaming": streaming,
        "json": structured_output,
        "structured_output": structured_output,
        "tool_calling": tool_use,
        "tool_use": tool_use,
        "vision": vision,
        "search": False,
        "embeddings": False,
        "max_context": _capability_max_context(provider_id),
        "safe_for_subagents": safe_for_subagents,
        "subagent_mode": "plan_display_only",
        "subagent_fallback_reason": fallback_reason,
    }


def _capability_max_context(provider_id: str) -> int | None:
    if provider_id == "mock":
        return 8192
    return None


def _local_provider_blockers(status: dict[str, object]) -> list[str]:
    if status.get("available") is True:
        return []
    reason = str(status.get("reason") or "local_provider_unavailable")
    if reason == "local_provider_not_enabled":
        return ["set ORA_LOCAL_LLM_ENABLED=1", "configure a loopback ORA_LOCAL_LLM_BASE_URL if not using the default"]
    if reason == "local_provider_loopback_policy_rejected":
        return ["set ORA_LOCAL_LLM_BASE_URL to localhost or a loopback IP without credentials, query, or fragment"]
    return [reason]


def _local_provider_setup_status(status: dict[str, object]) -> str:
    if status.get("available") is True:
        return "live_ready"
    reason = str(status.get("reason") or "")
    if reason == "local_provider_not_enabled":
        return "disabled"
    if reason == "local_provider_loopback_policy_rejected":
        return "loopback_rejected"
    return "blocked"


def _openai_compatible_blockers(env_status: Mapping[str, object], env: Mapping[str, str | None]) -> list[str]:
    blockers = []
    if env_status.get("YONERAI_OPENAI_COMPATIBLE_BASE_URL") != "present_redacted":
        blockers.append("set YONERAI_OPENAI_COMPATIBLE_BASE_URL")
    else:
        blockers.extend(_provider_base_url_blockers("openai-compatible", env.get("YONERAI_OPENAI_COMPATIBLE_BASE_URL")))
    if env_status.get("YONERAI_OPENAI_COMPATIBLE_API_KEY") != "present_redacted":
        blockers.append("set YONERAI_OPENAI_COMPATIBLE_API_KEY")
    if not _enabled(env.get("YONERAI_OPENAI_COMPATIBLE_LIVE")):
        blockers.append("set YONERAI_OPENAI_COMPATIBLE_LIVE=1")
    return blockers


def _external_provider_blockers(
    provider_id: str,
    env_status: Mapping[str, object],
    env: Mapping[str, str | None],
    available: bool,
    reason: str | None,
) -> list[str]:
    prefix = _provider_env_prefix(provider_id)
    blockers = []
    if not available:
        api_key = f"YONERAI_{prefix}_API_KEY"
        if env_status.get(api_key) != "present_redacted":
            blockers.append(f"set {api_key}")
        else:
            blockers.append(reason or f"{provider_id}_provider_not_configured")
    blockers.extend(_provider_base_url_blockers(provider_id, env.get(f"YONERAI_{prefix}_BASE_URL")))
    live_key = f"YONERAI_{prefix}_LIVE"
    if not _enabled(env.get(live_key)):
        blockers.append(f"set {live_key}=1")
    return blockers


def _external_provider_setup_status(provider_id: str, blockers: list[str]) -> str:
    if not blockers:
        return "live_ready"
    live_key = f"set YONERAI_{_provider_env_prefix(provider_id)}_LIVE=1"
    if blockers == [live_key]:
        return "live_opt_in_required"
    if any("without credentials, query, or fragment" in blocker for blocker in blockers):
        return "invalid_configuration"
    if any("BASE_URL" in blocker or "API_KEY" in blocker for blocker in blockers):
        return "missing_configuration"
    return "blocked"


def _provider_base_url_blockers(provider_id: str, raw_base_url: str | None) -> list[str]:
    if not str(raw_base_url or "").strip():
        return []
    try:
        if provider_id == "openai-compatible":
            _chat_completions_url(str(raw_base_url))
        elif provider_id == "anthropic":
            _messages_url(str(raw_base_url))
        elif provider_id == "gemini":
            _generate_content_url(str(raw_base_url), DEFAULT_GEMINI_MODEL)
    except ProviderError:
        env_key = f"YONERAI_{_provider_env_prefix(provider_id)}_BASE_URL"
        return [f"set {env_key} to an http(s) URL without credentials, query, or fragment"]
    return []


def _provider_env_prefix(provider_id: str) -> str:
    return provider_id.upper().replace("-", "_")


def _enabled(raw: str | None) -> bool:
    return str(raw or "").strip().lower() in {"1", "true", "yes", "on"}
