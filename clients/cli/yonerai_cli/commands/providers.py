from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping
from typing import Any

from yonerai_cli.screens.providers import format_providers_pretty


PROVIDERS_SCHEMA_VERSION = "yonerai-providers/v0.2"


class ProvidersCommandError(Exception):
    pass


def add_providers_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    providers = subcommands.add_parser("providers", help="Show provider readiness and safe setup guidance.")
    providers_output = providers.add_mutually_exclusive_group()
    providers_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    providers_output.add_argument("--pretty", action="store_true", help="Print readable provider setup guidance.")
    providers.add_argument("--lang", choices=lang_choices, default="ja", help="Pretty output language. Default: ja.")
    providers.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def build_providers_report(
    *,
    prepare_import_paths: Callable[[], None],
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    prepare_import_paths()
    try:
        from ora_core.providers import build_provider_setup_report
        from yonerai_cli.first_run import detect_local_llm
    except Exception as exc:
        raise ProvidersCommandError("provider runtime setup is unavailable.") from exc

    environ = os.environ if env is None else env
    provider_setup = build_provider_setup_report(environ)
    local_llm = detect_local_llm(environ)
    raw_providers = provider_setup.get("providers") if isinstance(provider_setup, dict) else []
    providers = [
        _provider_runtime_entry(provider, local_llm)
        for provider in raw_providers
        if isinstance(provider, dict)
    ]
    return {
        "schema_version": PROVIDERS_SCHEMA_VERSION,
        "ok": True,
        "command": "yonerai providers",
        "network_probe_performed": False,
        "loopback_probe_performed": bool(local_llm.get("probe_performed")),
        "live_call_performed": False,
        "local_llm": local_llm,
        "providers": providers,
        "recommended_first_command": _recommended_provider_first_command(providers),
        "actions_not_performed": [
            "no external provider call",
            "no local LLM text generation",
            "no provider key output",
            "no live Discord",
            "no production Oracle",
            "no official cloud runtime",
            "no shell execution",
            "no file read",
            "no install",
            "no PATH mutation",
        ],
    }


def handle_providers_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
    report_builder: Callable[[], dict[str, Any]],
) -> int:
    report = report_builder()
    if args.json:
        print_json(report)
    else:
        print(format_providers_pretty(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1


def _provider_runtime_entry(provider: dict[str, Any], local_llm: dict[str, object]) -> dict[str, object]:
    provider_id = str(provider.get("provider_id") or "unknown")
    setup_status = str(provider.get("setup_status") or "unknown")
    entry = dict(provider)
    entry["plain_state"] = _provider_plain_state(provider_id, provider, local_llm)
    entry["default_allowed"] = provider_id == "mock"
    entry["safe_for_private_context"] = provider_id in {"mock", "local"}
    entry["external_provider"] = provider_id in {"openai-compatible", "anthropic", "gemini"}
    entry["loopback_only"] = bool(provider.get("loopback_only")) or provider_id == "local"
    entry["command"] = _provider_command(provider_id, setup_status)
    entry["does"] = _provider_does(provider_id)
    entry["does_not"] = _provider_does_not(provider_id)
    entry["setup_hint"] = _provider_setup_hint(provider_id, provider, local_llm)
    if provider_id == "local":
        entry["local_llm_status"] = local_llm.get("status")
        entry["local_llm_endpoint_label"] = local_llm.get("endpoint_label")
        entry["local_llm_generation_performed"] = False
    return entry


def _provider_plain_state(
    provider_id: str,
    provider: dict[str, Any],
    local_llm: dict[str, object],
) -> str:
    setup_status = str(provider.get("setup_status") or "unknown")
    if provider_id == "mock":
        return "ready_now"
    if provider_id == "local":
        if provider.get("available") is True:
            return "ready_for_explicit_local_live"
        if local_llm.get("status") == "detected":
            return "loopback_server_detected_enable_env"
        if local_llm.get("status") == "blocked" or setup_status == "loopback_rejected":
            return "blocked_by_loopback_policy"
        return "not_enabled_or_not_detected"
    if setup_status == "live_ready":
        return "configured_for_explicit_live"
    if setup_status == "live_opt_in_required":
        return "needs_live_opt_in"
    if setup_status == "invalid_configuration":
        return "invalid_configuration"
    return "not_configured"


def _provider_command(provider_id: str, setup_status: str) -> str:
    if provider_id == "mock":
        return 'yonerai ask "hello" --auto --json'
    if provider_id == "local":
        return 'yonerai ask "hello" --auto --provider local --live --json'
    if provider_id in {"openai-compatible", "anthropic", "gemini"}:
        return f'yonerai ask "hello" --provider {provider_id} --live --json'
    return "yonerai providers --json"


def _provider_does(provider_id: str) -> str:
    mapping = {
        "mock": "Runs immediately without credentials and returns a public-safe run_id.",
        "local": "Uses an explicitly enabled loopback-only local LLM when --live is passed.",
        "openai-compatible": "Calls an OpenAI-compatible endpoint only after --live and env opt-in are present.",
        "anthropic": "Calls Anthropic only after --live and env opt-in are present.",
        "gemini": "Calls Gemini only after --live and env opt-in are present.",
    }
    return mapping.get(provider_id, "Reports provider setup state.")


def _provider_does_not(provider_id: str) -> str:
    if provider_id == "mock":
        return "Does not call live providers, local LLMs, Discord, Oracle, or official cloud."
    if provider_id == "local":
        return "Does not allow non-loopback URLs, embedded credentials, or default live execution."
    if provider_id in {"openai-compatible", "anthropic", "gemini"}:
        return "Does not run by default, does not receive private/local-file auto routes, and does not print keys."
    return "Does not execute provider calls from the providers command."


def _provider_setup_hint(provider_id: str, provider: dict[str, Any], local_llm: dict[str, object]) -> str:
    blockers = [str(item) for item in provider.get("setup_blockers") or [] if str(item).strip()]
    if provider_id == "mock":
        return "No setup required."
    if provider_id == "local":
        if provider.get("available") is True:
            return "Use --live for the local provider; endpoint remains loopback-only."
        if local_llm.get("status") == "detected":
            return "Set ORA_LOCAL_LLM_ENABLED=1, then use --provider local --live."
        if local_llm.get("status") == "blocked":
            return "Use localhost, 127.0.0.1, or ::1 without credentials, query, or fragment."
    if blockers:
        return "; ".join(blockers)
    return "Ready for explicit --live."


def _recommended_provider_first_command(providers: list[dict[str, object]]) -> str:
    local_provider = next((item for item in providers if item.get("provider_id") == "local"), {})
    if local_provider.get("plain_state") == "ready_for_explicit_local_live":
        return 'yonerai ask "hello" --auto --provider local --live --json'
    return 'yonerai ask "hello" --auto --json'
