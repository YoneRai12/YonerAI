from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from yonerai_cli import __version__
from yonerai_cli.config import ConfigError, build_config_report, default_config_path, load_cli_config, set_cli_config_value
from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.release_manifest import (
    ManifestError,
    format_manifest_verify_pretty,
    load_manifest_file,
    load_test_trust_fixture,
    parse_artifact_args,
    verify_manifest,
)


DEFAULT_API_ORIGIN = "http://127.0.0.1:8001"
TOKEN_ENV = "ORA_CORE_API_TOKEN"
PRIVATE_MARKERS = (
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'=])/(root|etc|home|users|var|tmp)/", re.IGNORECASE),
    re.compile(
        r"(api[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret|google[_-]?client[_-]?secret|authorization)",
        re.IGNORECASE,
    ),
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
LANG_CHOICES = ("en", "ja")
COLOR_CHOICES = ("auto", "never", "always")
PLAN_PROVIDER_CHOICES = ("auto", "mock", "openai-compatible", "local", "anthropic", "gemini")
PROVIDERS_SCHEMA_VERSION = "yonerai-providers/v0.2"
PLAN_MODE_CHOICES = (
    "managed-contract",
    "hybrid",
    "self-host",
    "official_managed_cloud",
    "official_hybrid_private",
    "full_private_self_host",
)


class CliError(Exception):
    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _is_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def normalize_loopback_origin(origin: str) -> str:
    try:
        parsed = urllib.parse.urlparse(origin)
    except ValueError as exc:
        raise CliError("api origin is invalid.") from exc
    if parsed.scheme not in {"http", "https"}:
        raise CliError("api origin must use http or https.")
    if parsed.username or parsed.password:
        raise CliError("api origin must not include credentials.")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise CliError("api origin must be an origin only, without path, query, or fragment.")
    if not _is_loopback_host(parsed.hostname):
        raise CliError("api origin must be loopback: localhost, 127.0.0.1, or ::1.")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")


def request_json(method: str, origin: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{normalize_loopback_origin(origin)}{path}"
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    token = os.getenv(TOKEN_ENV)
    if token:
        headers["X-ORA-Core-Token"] = token
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return _load_response_json(response.read())
    except urllib.error.HTTPError as exc:
        raise CliError(_safe_http_error(exc), exit_code=1) from exc
    except urllib.error.URLError:
        raise CliError("request failed: could not reach loopback Core API.", exit_code=1)
    except TimeoutError as exc:
        raise CliError("request timed out.", exit_code=1) from exc


def _load_response_json(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CliError("failed to parse JSON response.", exit_code=1) from exc
    if not isinstance(data, dict):
        raise CliError("response JSON must be an object.", exit_code=1)
    return data


def _safe_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        data = json.loads(exc.read().decode("utf-8"))
    except Exception:
        return f"request failed with status {exc.code}."
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        return _format_error_body(exc.code, detail, fallback_code=data.get("error") if isinstance(data, dict) else None)
    if isinstance(detail, str):
        return f"request failed with status {exc.code}: {_safe_error_text(detail, fallback='request failed')}"
    if isinstance(data, dict):
        return _format_error_body(exc.code, data)
    return f"request failed with status {exc.code}."


def _safe_error_text(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.split())
    if not cleaned:
        return fallback
    if any(pattern.search(cleaned) for pattern in PRIVATE_MARKERS):
        return fallback
    return cleaned[:220]


def _format_error_body(status_code: int, body: dict[str, Any], *, fallback_code: object | None = None) -> str:
    code = _safe_error_text(body.get("error") or fallback_code or "error", fallback="error")
    message = _safe_error_text(body.get("message"), fallback="request failed")
    parts = [f"request failed with status {status_code}: {code}: {message}"]
    context = []
    for key in ("mode", "provider", "model", "status"):
        safe_value = _safe_error_text(body.get(key), fallback="")
        if safe_value:
            context.append(f"{key}={safe_value}")
    if context:
        parts.append(f"({', '.join(context)})")
    return " ".join(parts)


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _build_doctor_report(*, command: str = "yonerai doctor") -> dict[str, Any]:
    manifest_path = _repo_root() / "releases" / "manifest.example.json"
    manifest_report: dict[str, Any]
    try:
        manifest_report = verify_manifest(load_manifest_file(str(manifest_path)))
    except ManifestError as exc:
        manifest_report = {"ok": False, "errors": [str(exc)]}
    _prepare_trusted_cli_import_paths()
    try:
        from ora_core.providers import build_provider_setup_report

        provider_setup = build_provider_setup_report()
    except ImportError:
        provider_setup = {
            "schema_version": "yonerai-provider-setup/v1",
            "network_probe_performed": False,
            "live_call_performed": False,
            "providers": [],
            "error": "provider_setup_unavailable",
        }
    try:
        from ora_core.hybrid.wire_contract import build_hybrid_wire_conformance_report

        hybrid_wire_contract = build_hybrid_wire_conformance_report()
    except ImportError:
        hybrid_wire_contract = {
            "schema_version": "yonerai-hybrid-wire-contract/v0.3",
            "ok": False,
            "error": "hybrid_wire_contract_unavailable",
            "network_required": False,
            "official_cloud_runtime_implemented": False,
            "production_oracle_used": False,
            "production_trust_material": False,
        }
    try:
        from ora_core.hybrid.relay_status import build_relay_status_report

        relay_status = build_relay_status_report(os.environ)
    except ImportError:
        relay_status = {
            "schema_version": "yonerai-relay-status/v0.1",
            "ok": False,
            "error": "relay_status_unavailable",
            "relay": {"process_started": False, "public_exposure_allowed": False},
        }
    try:
        from ora_core.hybrid.node_relay_contract import build_hybrid_node_relay_contract_stub

        hybrid_node_relay_contract = build_hybrid_node_relay_contract_stub(os.environ)
    except ImportError:
        hybrid_node_relay_contract = {
            "schema_version": "yonerai-hybrid-node-relay-contract/v0.1",
            "ok": False,
            "error": "hybrid_node_relay_contract_unavailable",
            "official_cloud_runtime_implemented": False,
            "production_oracle_used": False,
            "network_required": False,
        }
    try:
        from ora_core.hybrid import build_oracle_stub_status_report

        oracle_stub = build_oracle_stub_status_report()
    except ImportError:
        oracle_stub = {
            "schema_version": "yonerai-oracle-stub/v0.1",
            "ok": False,
            "error": "oracle_stub_unavailable",
            "network_required": False,
            "production_oracle_used": False,
            "official_cloud_runtime_implemented": False,
        }
    try:
        from ora_core.hybrid import build_hybrid_execution_slice_status_report

        hybrid_execution_slice = build_hybrid_execution_slice_status_report()
    except ImportError:
        hybrid_execution_slice = {
            "schema_version": "yonerai-hybrid-execution-slice/v0.1",
            "ok": False,
            "error": "hybrid_execution_slice_unavailable",
            "network_required": False,
            "production_oracle_used": False,
            "official_cloud_runtime_implemented": False,
        }
    try:
        from ora_core.execution.auto_runtime import build_auto_runtime_status_report

        auto_runtime = build_auto_runtime_status_report()
    except ImportError:
        auto_runtime = {
            "schema_version": "yonerai-auto-runtime/v0.1",
            "ok": False,
            "error": "auto_runtime_unavailable",
            "network_required": False,
            "production_oracle_used": False,
            "official_cloud_runtime_implemented": False,
        }
    python_supported = sys.version_info >= (3, 11)
    manifest_contract_valid = bool(manifest_report.get("contract_valid", manifest_report.get("ok")))
    system_checks = {
        "redaction_self_check": _run_redaction_self_check(),
        "mcp_deny_policy": _run_mcp_deny_policy_self_check(),
    }
    checks_ok = all(bool(check.get("ok")) for check in system_checks.values())
    hybrid_wire_ok = bool(hybrid_wire_contract.get("ok"))
    relay_ok = bool(relay_status.get("ok"))
    hybrid_node_relay_ok = bool(hybrid_node_relay_contract.get("ok"))
    oracle_stub_ok = bool(oracle_stub.get("ok"))
    hybrid_execution_slice_ok = bool(hybrid_execution_slice.get("ok"))
    auto_runtime_ok = bool(auto_runtime.get("ok"))
    return {
        "ok": (
            manifest_contract_valid
            and python_supported
            and checks_ok
            and hybrid_wire_ok
            and relay_ok
            and hybrid_node_relay_ok
            and oracle_stub_ok
            and hybrid_execution_slice_ok
            and auto_runtime_ok
        ),
        "command": command,
        "schema_version": "yonerai-doctor/v1",
        "python": {
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "supported": python_supported,
        },
        "cli": {
            "import_ok": True,
            "package_version": __version__,
            "repo_version": _read_repo_version(),
            "demo_command_available": True,
            "quickstart_alias_available": True,
        },
        "manifest": {
            "example_present": manifest_path.exists(),
            "contract_valid": manifest_contract_valid,
            "install_ready": bool(manifest_report.get("install_ready", False)),
            "signature_state": manifest_report.get("signature_state"),
            "non_production_reason": manifest_report.get("non_production_reason"),
        },
        "credentials": {
            TOKEN_ENV: "present_redacted" if os.getenv(TOKEN_ENV) else "absent",
            "required_for_demo": False,
        },
        "boundaries": {
            "network_required": False,
            "install_mutation": False,
            "path_mutation": False,
            "official_cloud_runtime_included": False,
            "live_discord_required": False,
            "persistent_memory_required": False,
            "oracle_required": False,
            "deploy_required": False,
        },
        "providers": provider_setup,
        "hybrid_wire_contract": hybrid_wire_contract,
        "relay_status": relay_status,
        "hybrid_node_relay_contract": hybrid_node_relay_contract,
        "oracle_stub": oracle_stub,
        "hybrid_execution_slice": hybrid_execution_slice,
        "auto_runtime": auto_runtime,
        "provider_runtime_e2e_fixtures": _provider_runtime_e2e_fixture_report(),
        "system_checks": system_checks,
        "errors": manifest_report.get("errors", []),
    }


def _provider_runtime_e2e_fixture_report() -> dict[str, object]:
    return {
        "status": "covered_by_local_tests",
        "openai_compatible": "local_mock_http_server_tested",
        "local_llm": "loopback_mock_http_server_tested",
        "run_ledger": "redacted_success_and_error_paths_tested",
        "network_probe_performed": False,
        "live_call_performed": False,
        "external_network_call_performed": False,
    }


def _build_start_report(*, guided: bool = False) -> dict[str, Any]:
    _prepare_trusted_cli_import_paths()
    from yonerai_cli.first_run import build_first_run_report

    doctor_report = _build_doctor_report(command="yonerai start")
    return build_first_run_report(
        provider_setup=doctor_report.get("providers"),
        repo_version=doctor_report.get("cli", {}).get("repo_version"),
        env=os.environ,
        guided=guided,
    )


def _build_providers_report() -> dict[str, Any]:
    _prepare_trusted_cli_import_paths()
    try:
        from ora_core.providers import build_provider_setup_report
        from yonerai_cli.first_run import detect_local_llm
    except Exception as exc:
        raise CliError("provider runtime setup is unavailable.", exit_code=1) from exc

    provider_setup = build_provider_setup_report(os.environ)
    local_llm = detect_local_llm(os.environ)
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


def _print_providers_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> None:
    print(_format_providers_pretty(report, lang=lang, color=color))


def _format_providers_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    if lang == "ja":
        title = "YonerAI プロバイダー"
        sections = _provider_sections_ja(report)
    else:
        title = "YonerAI providers"
        sections = _provider_sections_en(report)
    return render_report(title, sections, color=color)


def _provider_sections_en(report: dict[str, Any]) -> tuple[CliSection, ...]:
    providers = _provider_entries(report)
    return (
        CliSection(
            "Recommended first command",
            (
                CliRow("command", report.get("recommended_first_command"), "ok"),
                CliRow("live_call_performed", report.get("live_call_performed"), "fail" if report.get("live_call_performed") else "ok"),
                CliRow("network_probe_performed", report.get("network_probe_performed"), "fail" if report.get("network_probe_performed") else "ok"),
                CliRow("loopback_probe_performed", report.get("loopback_probe_performed"), "warn" if report.get("loopback_probe_performed") else "ok"),
            ),
        ),
        *(_provider_entry_section_en(provider) for provider in providers),
        CliSection(
            "Non-actions",
            tuple(CliRow(f"no_{index}", item, "ok") for index, item in enumerate(report.get("actions_not_performed") or [], start=1)),
        ),
    )


def _provider_sections_ja(report: dict[str, Any]) -> tuple[CliSection, ...]:
    providers = _provider_entries(report)
    return (
        CliSection(
            "最初に試すコマンド",
            (
                CliRow("command", report.get("recommended_first_command"), "ok"),
                CliRow("live呼び出し", _yes_no_ja(report.get("live_call_performed")), "fail" if report.get("live_call_performed") else "ok"),
                CliRow("外部ネットワークprobe", _yes_no_ja(report.get("network_probe_performed")), "fail" if report.get("network_probe_performed") else "ok"),
                CliRow("loopback確認", _yes_no_ja(report.get("loopback_probe_performed")), "warn" if report.get("loopback_probe_performed") else "ok"),
            ),
        ),
        *(_provider_entry_section_ja(provider) for provider in providers),
        CliSection(
            "このコマンドがしないこと",
            tuple(CliRow(f"未実行{index}", _provider_non_action_ja(str(item)), "ok") for index, item in enumerate(report.get("actions_not_performed") or [], start=1)),
        ),
    )


def _provider_entry_section_en(provider: dict[str, object]) -> CliSection:
    provider_id = str(provider.get("provider_id") or "unknown")
    return CliSection(
        provider_id,
        (
            CliRow("state", provider.get("plain_state"), _provider_plain_state_level(provider.get("plain_state"))),
            CliRow("configured", provider.get("configured"), "ok" if provider.get("configured") else "warn"),
            CliRow("available", provider.get("available"), "ok" if provider.get("available") else "warn"),
            CliRow("requires_live", provider.get("requires_live_flag", False), "warn" if provider.get("requires_live_flag") else "ok"),
            CliRow("private_context_safe", provider.get("safe_for_private_context"), "ok" if provider.get("safe_for_private_context") else "warn"),
            CliRow("command", provider.get("command"), "ok"),
            CliRow("does", provider.get("does"), "ok"),
            CliRow("does_not", provider.get("does_not"), "ok"),
            CliRow("setup", provider.get("setup_hint"), "ok" if provider.get("available") else "warn"),
        ),
    )


def _provider_entry_section_ja(provider: dict[str, object]) -> CliSection:
    provider_id = str(provider.get("provider_id") or "unknown")
    return CliSection(
        _provider_label_ja(provider_id),
        (
            CliRow("状態", _provider_plain_state_text_ja(provider.get("plain_state")), _provider_plain_state_level(provider.get("plain_state"))),
            CliRow("設定済み", _yes_no_ja(provider.get("configured")), "ok" if provider.get("configured") else "warn"),
            CliRow("利用可能", _yes_no_ja(provider.get("available")), "ok" if provider.get("available") else "warn"),
            CliRow("--live必須", _yes_no_ja(provider.get("requires_live_flag", False)), "warn" if provider.get("requires_live_flag") else "ok"),
            CliRow("private/local file", "送らない" if provider.get("safe_for_private_context") else "送らないため自動経路ではブロック", "ok" if provider.get("safe_for_private_context") else "warn"),
            CliRow("コマンド", provider.get("command"), "ok"),
            CliRow("何をするか", _provider_does_ja(provider_id), "ok"),
            CliRow("何をしないか", _provider_does_not_ja(provider_id), "ok"),
            CliRow("次の設定", _provider_setup_hint_ja(provider_id, provider), "ok" if provider.get("available") else "warn"),
        ),
    )


def _provider_entries(report: dict[str, Any]) -> tuple[dict[str, object], ...]:
    providers = report.get("providers")
    if not isinstance(providers, list):
        return ()
    return tuple(provider for provider in providers if isinstance(provider, dict))


def _provider_plain_state_level(state: object) -> str:
    if state in {"ready_now", "ready_for_explicit_local_live", "configured_for_explicit_live"}:
        return "ok"
    if state in {"blocked_by_loopback_policy", "invalid_configuration"}:
        return "fail"
    return "warn"


def _provider_label_ja(provider_id: str) -> str:
    mapping = {
        "mock": "mock provider",
        "local": "local LLM",
        "openai-compatible": "OpenAI-compatible",
        "anthropic": "Anthropic",
        "gemini": "Gemini",
    }
    return mapping.get(provider_id, provider_id)


def _provider_plain_state_text_ja(state: object) -> str:
    mapping = {
        "ready_now": "今すぐ利用可能",
        "ready_for_explicit_local_live": "明示的なlocal --liveで利用可能",
        "loopback_server_detected_enable_env": "loopbackサーバー検出済み、env有効化が必要",
        "blocked_by_loopback_policy": "loopbackポリシーで拒否",
        "not_enabled_or_not_detected": "未有効または未検出",
        "configured_for_explicit_live": "明示的な--liveで利用可能",
        "needs_live_opt_in": "provider別live opt-inが必要",
        "invalid_configuration": "設定が不正",
        "not_configured": "未設定",
    }
    return mapping.get(str(state), "不明")


def _provider_does_ja(provider_id: str) -> str:
    mapping = {
        "mock": "API keyなしで安全なrun_id付き応答を返します。",
        "local": "明示的に有効化したloopback-only local LLMを--live時だけ使います。",
        "openai-compatible": "--liveとenv opt-inがある場合だけOpenAI互換endpointを呼びます。",
        "anthropic": "--liveとenv opt-inがある場合だけAnthropicを呼びます。",
        "gemini": "--liveとenv opt-inがある場合だけGeminiを呼びます。",
    }
    return mapping.get(provider_id, "provider設定状態を表示します。")


def _provider_does_not_ja(provider_id: str) -> str:
    if provider_id == "mock":
        return "live provider、local LLM、Discord、Oracle、official cloudには接続しません。"
    if provider_id == "local":
        return "非loopback URL、埋め込みcredential、既定live実行は許可しません。"
    if provider_id in {"openai-compatible", "anthropic", "gemini"}:
        return "既定では実行せず、private/local-file自動経路には送らず、keyも表示しません。"
    return "providersコマンド自体はprovider呼び出しを実行しません。"


def _provider_setup_hint_ja(provider_id: str, provider: dict[str, object]) -> str:
    hint = str(provider.get("setup_hint") or "")
    if provider_id == "mock":
        return "設定不要です。"
    if provider_id == "local" and provider.get("plain_state") == "loopback_server_detected_enable_env":
        return "ORA_LOCAL_LLM_ENABLED=1 を設定して --provider local --live を使います。"
    if provider_id == "local" and provider.get("plain_state") == "blocked_by_loopback_policy":
        return "localhost / 127.0.0.1 / ::1 のみ許可します。credential、query、fragmentは不可です。"
    return hint


def _provider_non_action_ja(value: str) -> str:
    mapping = {
        "no external provider call": "外部provider呼び出しなし",
        "no local LLM text generation": "local LLM生成なし",
        "no provider key output": "provider key出力なし",
        "no live Discord": "live Discord接続なし",
        "no production Oracle": "production Oracleなし",
        "no official cloud runtime": "official cloud runtimeなし",
        "no shell execution": "shell実行なし",
        "no file read": "ファイル読み取りなし",
        "no install": "installなし",
        "no PATH mutation": "PATH変更なし",
        "no arbitrary shell execution": "任意shell実行なし",
        "no arbitrary file access": "任意ファイルアクセスなし",
        "no deploy": "deployなし",
        "no public tunnel": "public tunnelなし",
        "no live external provider call by default": "既定のlive外部provider呼び出しなし",
        "no private file content sent to cloud contract": "private file内容をcloud contractへ送信なし",
    }
    return mapping.get(value, value)


def _yes_no_ja(value: object) -> str:
    return "はい" if bool(value) else "いいえ"


def _print_start_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    from yonerai_cli.first_run import format_first_run_pretty

    print(format_first_run_pretty(report, lang=lang, color=color))


def _build_status_report(*, source: str = "local") -> dict[str, Any]:
    report = _build_doctor_report(command="yonerai status")
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.status_contract import build_official_status_contract
    except Exception as exc:
        raise CliError("official status contract fixture is unavailable.", exit_code=1) from exc
    report["status_source"] = source
    report["official_status"] = build_official_status_contract(source=source)
    return report


def _build_oracle_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.execution import build_run_ledger_from_env
        from ora_core.hybrid import (
            DEFAULT_ORACLE_STUB_TASK,
            build_oracle_stub_queue_report,
            build_oracle_stub_status_report,
        )
    except Exception as exc:
        raise CliError("Oracle stub fixture is unavailable.", exit_code=1) from exc
    if args.oracle_command == "status":
        return build_oracle_stub_status_report()
    if args.oracle_command == "queue":
        task = " ".join(args.task).strip() or DEFAULT_ORACLE_STUB_TASK
        ledger = build_run_ledger_from_env(args.ledger_path) if args.ledger_path or os.getenv("YONERAI_RUN_LEDGER_PATH") else None
        return build_oracle_stub_queue_report(task, ledger=ledger)
    raise CliError("unknown oracle command", exit_code=2)


def _build_hybrid_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.execution import build_run_ledger_from_env
        from ora_core.hybrid import DEFAULT_HYBRID_EXECUTION_TASK, build_hybrid_execution_slice_report
    except Exception as exc:
        raise CliError("Hybrid execution slice is unavailable.", exit_code=1) from exc
    if args.hybrid_command != "run":
        raise CliError("unknown hybrid command", exit_code=2)
    task = " ".join(args.task).strip() or DEFAULT_HYBRID_EXECUTION_TASK
    ledger = build_run_ledger_from_env(args.ledger_path)
    return build_hybrid_execution_slice_report(
        task,
        provider=args.provider,
        live=args.live,
        ledger=ledger,
        env=os.environ,
    )


def _run_redaction_self_check() -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from src.utils.redaction import redact_text
    except Exception:
        return {
            "ok": False,
            "status": "fail",
            "network_required": False,
            "private_runtime_required": False,
            "reason": "redaction utility unavailable",
        }

    openai_sample = "sk-" + ("A" * 24)
    webhook_sample = "https://discord.com/api/" + "webhooks/123456789012345678/" + ("B" * 40)
    query_sample = "https://example.invalid/callback?code=" + ("C" * 24)
    redacted = redact_text(f"{openai_sample} {webhook_sample} {query_sample}")
    ok = (
        "sk-" not in redacted
        and "discord.com/api/webhooks" not in redacted
        and "code=" not in redacted
        and "[REDACTED]" in redacted
    )
    return {
        "ok": ok,
        "status": "ok" if ok else "fail",
        "network_required": False,
        "private_runtime_required": False,
        "reason": None if ok else "redaction self-check did not mask all samples",
    }


def _read_repo_version() -> str | None:
    try:
        version = (_repo_root() / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return version or None


def _run_mcp_deny_policy_self_check() -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from src.cogs.mcp_policy import is_mcp_tool_denied
    except Exception:
        return {
            "ok": False,
            "status": "fail",
            "network_required": False,
            "live_runtime_required": False,
            "reason": "MCP deny policy utility unavailable",
        }

    patterns = ["delete", "deploy", "shell", "run"]
    dangerous_names_denied = all(
        is_mcp_tool_denied(name, patterns)
        for name in ("delete_file", "deploy_release", "run_shell")
    )
    safe_name_allowed = not is_mcp_tool_denied("generate_artwork", patterns)
    ok = dangerous_names_denied and safe_name_allowed
    return {
        "ok": ok,
        "status": "ok" if ok else "fail",
        "network_required": False,
        "live_runtime_required": False,
        "dangerous_names_denied": dangerous_names_denied,
        "safe_name_allowed": safe_name_allowed,
        "reason": None if ok else "MCP deny policy fixture failed",
    }


def _print_doctor_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    print(_format_doctor_pretty(report, lang=lang, color=color))


def _format_doctor_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    if lang == "ja":
        title = "YonerAI 診断"
        sections = _doctor_sections_ja(report)
    else:
        title = "YonerAI doctor"
        sections = _doctor_sections_en(report)
    if report["errors"]:
        error_title = "エラー" if lang == "ja" else "Errors"
        sections = (*sections, CliSection(error_title, tuple(CliRow("error", error, "fail") for error in report["errors"])))
    return render_report(title, sections, color=color)


def _print_status_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    print(_format_status_pretty(report, lang=lang, color=color))


def _format_status_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    manifest = report["manifest"]
    boundaries = report["boundaries"]
    if lang == "ja":
        sections = (
            CliSection(
                "公開デモ",
                (
                    CliRow("デモ", "利用可能", "ok"),
                    CliRow("Quickstart", "利用可能", "ok"),
                    CliRow("認証情報", "不要", "ok"),
                ),
            ),
            CliSection(
                "配布準備",
                (
                    CliRow("マニフェスト", "有効" if manifest["contract_valid"] else "無効", "ok" if manifest["contract_valid"] else "fail"),
                    CliRow("インストール準備", "完了" if manifest["install_ready"] else "未完了", "ok" if manifest["install_ready"] else "warn"),
                    CliRow("ネットワークインストーラー", "未実装", "ok"),
                ),
            ),
            CliSection(
                "境界",
                (
                    CliRow("Official Managed Cloud", "外部/契約のみ", "ok"),
                    CliRow("Live Discord", "不要", "ok"),
                    CliRow("永続メモリ", "不要", "ok" if not boundaries["persistent_memory_required"] else "fail"),
                ),
            ),
        )
        return render_report("YonerAI 状態", sections, color=color)

    sections = (
        CliSection(
            "Public demo",
            (
                CliRow("demo", "available", "ok"),
                CliRow("quickstart", "available", "ok"),
                CliRow("credentials", "not required", "ok"),
            ),
        ),
        CliSection(
            "Distribution readiness",
            (
                CliRow("manifest", "valid" if manifest["contract_valid"] else "invalid", "ok" if manifest["contract_valid"] else "fail"),
                CliRow("install_ready", manifest["install_ready"], "ok" if manifest["install_ready"] else "warn"),
                CliRow("network_installer", "not implemented", "ok"),
            ),
        ),
        CliSection(
            "Boundaries",
            (
                CliRow("official_cloud", "external/contract-only", "ok"),
                CliRow("live_discord", "not required", "ok"),
                CliRow("persistent_memory", "not required", "ok" if not boundaries["persistent_memory_required"] else "fail"),
            ),
        ),
    )
    official_status = report.get("official_status")
    if isinstance(official_status, dict):
        components = official_status.get("components") if isinstance(official_status.get("components"), list) else []
        component_rows = tuple(
            CliRow(
                str(component.get("component")),
                str(component.get("status")),
                "ok" if component.get("network_required") is False else "warn",
                note=component.get("degraded_reason"),
            )
            for component in components
            if isinstance(component, dict)
        )
        sections = (
            *sections,
            CliSection(
                "Official status contract",
                component_rows
                or (
                    CliRow("components", "none", "warn"),
                ),
            ),
        )
    return render_report("YonerAI status", sections, color=color)


def _doctor_sections_en(report: dict[str, Any]) -> tuple[CliSection, ...]:
    python_report = report["python"]
    cli_report = report["cli"]
    manifest_report = report["manifest"]
    boundaries = report["boundaries"]
    redaction_check = report["system_checks"]["redaction_self_check"]
    mcp_check = report["system_checks"]["mcp_deny_policy"]
    provider_rows = _provider_setup_rows(report, lang="en")
    provider_e2e_rows = _provider_runtime_e2e_rows(report, lang="en")
    hybrid_wire_rows = _hybrid_wire_contract_rows(report, lang="en")
    node_relay_rows = _hybrid_node_relay_contract_rows(report, lang="en")
    relay_rows = _relay_status_rows(report, lang="en")
    oracle_rows = _oracle_stub_rows(report)
    auto_runtime_rows = _auto_runtime_rows(report)
    return (
        CliSection(
            "Setup",
            (
                CliRow("overall", "ready for public demo" if report["ok"] else "needs attention", "ok" if report["ok"] else "fail"),
                CliRow("python", python_report["version"], "ok" if python_report["supported"] else "fail"),
                CliRow("cli_import", cli_report["import_ok"], "ok" if cli_report["import_ok"] else "fail"),
                CliRow("package_version", cli_report["package_version"], "ok"),
                CliRow("repo_version", cli_report["repo_version"] or "unknown", "ok" if cli_report["repo_version"] else "warn"),
                CliRow("demo", "available" if cli_report["demo_command_available"] else "missing", "ok" if cli_report["demo_command_available"] else "fail"),
                CliRow(
                    "quickstart",
                    "available" if cli_report["quickstart_alias_available"] else "missing",
                    "ok" if cli_report["quickstart_alias_available"] else "fail",
                ),
            ),
        ),
        CliSection(
            "Manifest",
            (
                CliRow("manifest_example_valid", manifest_report["contract_valid"], "ok" if manifest_report["contract_valid"] else "fail"),
                CliRow("manifest_install_ready", manifest_report["install_ready"], "ok" if manifest_report["install_ready"] else "warn"),
                CliRow("signature_state", manifest_report["signature_state"], "ok" if manifest_report["signature_state"] == "signed" else "warn"),
                CliRow("non_production_reason", manifest_report["non_production_reason"] or "none", "warn" if manifest_report["non_production_reason"] else "ok"),
            ),
        ),
        CliSection(
            "Diagnostics",
            (
                CliRow("redaction_self_check", redaction_check["status"], "ok" if redaction_check["ok"] else "fail"),
                CliRow("mcp_deny_policy", mcp_check["status"], "ok" if mcp_check["ok"] else "fail"),
            ),
        ),
        CliSection("Hybrid Wire Contract", hybrid_wire_rows),
        CliSection("Hybrid Node/Relay", node_relay_rows),
        CliSection("Relay local-dev", relay_rows),
        CliSection("Oracle stub", oracle_rows),
        CliSection("Auto runtime", auto_runtime_rows),
        CliSection("Provider runtime", provider_rows),
        CliSection("Provider runtime E2E fixtures", provider_e2e_rows),
        CliSection(
            "Boundaries",
            (
                CliRow("network_required", boundaries["network_required"], "fail" if boundaries["network_required"] else "ok"),
                CliRow("credentials_required_for_demo", report["credentials"]["required_for_demo"], "fail" if report["credentials"]["required_for_demo"] else "ok"),
                CliRow("official_cloud_runtime", "external/contract-only", "ok"),
                CliRow("live_discord", "not required", "ok" if not boundaries["live_discord_required"] else "fail"),
                CliRow("network_installer", "not implemented", "ok"),
                CliRow("production_features", "not included", "ok"),
                CliRow("install_mutation", boundaries["install_mutation"], "fail" if boundaries["install_mutation"] else "ok"),
                CliRow("path_mutation", boundaries["path_mutation"], "fail" if boundaries["path_mutation"] else "ok"),
            ),
        ),
    )


def _doctor_sections_ja(report: dict[str, Any]) -> tuple[CliSection, ...]:
    python_report = report["python"]
    cli_report = report["cli"]
    manifest_report = report["manifest"]
    boundaries = report["boundaries"]
    redaction_check = report["system_checks"]["redaction_self_check"]
    mcp_check = report["system_checks"]["mcp_deny_policy"]
    provider_rows = _provider_setup_rows(report, lang="ja")
    provider_e2e_rows = _provider_runtime_e2e_rows(report, lang="ja")
    hybrid_wire_rows = _hybrid_wire_contract_rows(report, lang="ja")
    node_relay_rows = _hybrid_node_relay_contract_rows(report, lang="ja")
    relay_rows = _relay_status_rows(report, lang="ja")
    oracle_rows = _oracle_stub_rows(report)
    auto_runtime_rows = _auto_runtime_rows(report)
    return (
        CliSection(
            "セットアップ",
            (
                CliRow("全体", "公開デモ実行可能" if report["ok"] else "確認が必要", "ok" if report["ok"] else "fail"),
                CliRow("Python", python_report["version"], "ok" if python_report["supported"] else "fail"),
                CliRow("CLI import", "成功" if cli_report["import_ok"] else "失敗", "ok" if cli_report["import_ok"] else "fail"),
                CliRow("CLI package", cli_report["package_version"], "ok"),
                CliRow("Repo version", cli_report["repo_version"] or "unknown", "ok" if cli_report["repo_version"] else "warn"),
                CliRow("デモ", "利用可能" if cli_report["demo_command_available"] else "未検出", "ok" if cli_report["demo_command_available"] else "fail"),
                CliRow(
                    "Quickstart",
                    "利用可能" if cli_report["quickstart_alias_available"] else "未検出",
                    "ok" if cli_report["quickstart_alias_available"] else "fail",
                ),
            ),
        ),
        CliSection(
            "マニフェスト",
            (
                CliRow("マニフェスト", "有効" if manifest_report["contract_valid"] else "無効", "ok" if manifest_report["contract_valid"] else "fail"),
                CliRow("インストール準備", "完了" if manifest_report["install_ready"] else "未完了", "ok" if manifest_report["install_ready"] else "warn"),
                CliRow("署名状態", manifest_report["signature_state"], "ok" if manifest_report["signature_state"] == "signed" else "warn"),
                CliRow("非本番理由", manifest_report["non_production_reason"] or "なし", "warn" if manifest_report["non_production_reason"] else "ok"),
            ),
        ),
        CliSection(
            "診断",
            (
                CliRow("Redaction self-check", "成功" if redaction_check["ok"] else "失敗", "ok" if redaction_check["ok"] else "fail"),
                CliRow("MCP deny policy", "成功" if mcp_check["ok"] else "失敗", "ok" if mcp_check["ok"] else "fail"),
            ),
        ),
        CliSection("Hybrid Wire Contract", hybrid_wire_rows),
        CliSection("Hybrid Node/Relay", node_relay_rows),
        CliSection("Relay local-dev", relay_rows),
        CliSection("Oracle stub", oracle_rows),
        CliSection("Auto runtime", auto_runtime_rows),
        CliSection("プロバイダー実行環境", provider_rows),
        CliSection("プロバイダー実行環境 E2E フィクスチャ", provider_e2e_rows),
        CliSection(
            "境界",
            (
                CliRow("ネットワーク", "不要" if not boundaries["network_required"] else "必要", "ok" if not boundaries["network_required"] else "fail"),
                CliRow("認証情報", "不要" if not report["credentials"]["required_for_demo"] else "必要", "ok" if not report["credentials"]["required_for_demo"] else "fail"),
                CliRow("Official Managed Cloud", "外部/契約のみ", "ok"),
                CliRow("Live Discord", "不要" if not boundaries["live_discord_required"] else "必要", "ok" if not boundaries["live_discord_required"] else "fail"),
                CliRow("ネットワークインストーラー", "未実装", "ok"),
                CliRow("本番機能", "含まれません", "ok"),
                CliRow("インストール変更", "なし" if not boundaries["install_mutation"] else "あり", "ok" if not boundaries["install_mutation"] else "fail"),
                CliRow("PATH変更", "なし" if not boundaries["path_mutation"] else "あり", "ok" if not boundaries["path_mutation"] else "fail"),
            ),
        ),
    )


def _oracle_stub_rows(report: dict[str, Any]) -> tuple[CliRow, ...]:
    oracle = report.get("oracle_stub")
    if not isinstance(oracle, dict):
        return (CliRow("status", "unavailable", "warn"),)
    return (
        CliRow("status", oracle.get("status", "unknown"), "ok" if oracle.get("ok") else "fail"),
        CliRow("schema", oracle.get("schema_version", "unknown"), "ok"),
        CliRow("queue_available", oracle.get("queue_available", False), "ok" if oracle.get("queue_available") else "warn"),
        CliRow(
            "deterministic_fixture",
            oracle.get("deterministic_fixture_result", False),
            "ok" if oracle.get("deterministic_fixture_result") else "warn",
        ),
        CliRow(
            "network_required",
            oracle.get("network_required", False),
            "fail" if oracle.get("network_required") else "ok",
        ),
        CliRow(
            "production_oracle_used",
            oracle.get("production_oracle_used", False),
            "fail" if oracle.get("production_oracle_used") else "ok",
        ),
        CliRow(
            "official_cloud_runtime",
            oracle.get("official_cloud_runtime_implemented", False),
            "fail" if oracle.get("official_cloud_runtime_implemented") else "ok",
        ),
    )


def _auto_runtime_rows(report: dict[str, Any]) -> tuple[CliRow, ...]:
    auto_runtime = report.get("auto_runtime")
    if not isinstance(auto_runtime, dict):
        return (CliRow("status", "unavailable", "warn"),)
    routes = auto_runtime.get("routes")
    route_count = len(routes) if isinstance(routes, list) else 0
    return (
        CliRow("status", auto_runtime.get("status", "unknown"), "ok" if auto_runtime.get("ok") else "fail"),
        CliRow("schema", auto_runtime.get("schema_version", "unknown"), "ok"),
        CliRow("command", auto_runtime.get("command", "yonerai ask --auto --json"), "ok"),
        CliRow("routes", route_count, "ok" if route_count >= 5 else "warn"),
        CliRow("mock_provider_default", auto_runtime.get("mock_provider_default"), "ok"),
        CliRow("local_llm_loopback_only", auto_runtime.get("local_llm_loopback_only"), "ok"),
        CliRow(
            "live_external_provider_default",
            auto_runtime.get("live_external_provider_default"),
            "fail" if auto_runtime.get("live_external_provider_default") else "ok",
        ),
        CliRow(
            "reviewer_plan",
            auto_runtime.get("reviewer_plan_supported"),
            "ok" if auto_runtime.get("reviewer_plan_supported") else "warn",
        ),
    )


def _hybrid_wire_contract_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    hybrid = report.get("hybrid_wire_contract")
    if not isinstance(hybrid, dict):
        unavailable = "利用不可" if lang == "ja" else "unavailable"
        return (CliRow("status", unavailable, "warn"),)
    trust_states = hybrid.get("trust_states")
    trust_state_count = len(trust_states) if isinstance(trust_states, list) else 0
    required_count = _hybrid_required_trust_state_count(hybrid)
    posture_states = hybrid.get("node_posture_states")
    posture_state_count = len(posture_states) if isinstance(posture_states, list) else 0
    required_posture_count = _hybrid_required_node_posture_state_count(hybrid)
    capabilities = hybrid.get("capabilities")
    capability_count = len(capabilities) if isinstance(capabilities, list) else 0
    extension_boundary = hybrid.get("extension_boundary")
    extension_boundary_count = len(extension_boundary) if isinstance(extension_boundary, list) else 0
    orchestration_stub = hybrid.get("official_orchestration_stub")
    orchestration_response = {}
    if isinstance(orchestration_stub, dict):
        response_value = orchestration_stub.get("response")
        if isinstance(response_value, dict):
            orchestration_response = response_value
    route_alignment = hybrid.get("route_orchestration_alignment")
    if not isinstance(route_alignment, dict):
        route_alignment = {}
    status_ok = "正常" if lang == "ja" else "ok"
    status_fail = "失敗" if lang == "ja" else "fail"
    route_alignment_status = route_alignment.get("status")
    route_alignment_value = status_ok if route_alignment_status == "ok" else status_fail
    route_alignment_level = "ok" if route_alignment_status == "ok" else "fail"
    not_implemented = "未実装" if lang == "ja" else "not implemented"
    implemented = "実装済み" if lang == "ja" else "implemented"
    return (
        CliRow("status", status_ok if hybrid.get("ok") else status_fail, "ok" if hybrid.get("ok") else "fail"),
        CliRow("schema", hybrid.get("schema_version", "unknown"), "ok"),
        CliRow("test_fixture_only", hybrid.get("test_fixture_only"), "ok" if hybrid.get("test_fixture_only") else "warn"),
        CliRow("capabilities", capability_count, "ok" if capability_count else "warn"),
        CliRow("trust_states", trust_state_count, "ok" if trust_state_count >= required_count else "warn"),
        CliRow("extension_boundary", extension_boundary_count, "ok" if extension_boundary_count else "warn"),
        CliRow(
            "node_posture_states",
            posture_state_count,
            "ok" if posture_state_count >= required_posture_count else "warn",
        ),
        CliRow(
            "route_preview_fixture",
            hybrid.get("route_preview_fixture_supported"),
            "ok" if hybrid.get("route_preview_fixture_supported") else "warn",
        ),
        CliRow(
            "orchestration_response",
            orchestration_response.get("schema_name", "missing"),
            "ok" if orchestration_response.get("schema_name") == "OfficialOrchestrationStubResponse" else "warn",
        ),
        CliRow(
            "cloud_contract_candidate",
            orchestration_response.get("route_strategy", "missing"),
            "ok" if orchestration_response.get("route_strategy") == "cloud_contract_candidate" else "warn",
        ),
        CliRow(
            "route_orchestration_alignment",
            route_alignment_value,
            route_alignment_level,
        ),
        CliRow("network_required", hybrid.get("network_required"), "fail" if hybrid.get("network_required") else "ok"),
        CliRow(
            "official_cloud_runtime",
            not_implemented if not hybrid.get("official_cloud_runtime_implemented") else implemented,
            "ok" if not hybrid.get("official_cloud_runtime_implemented") else "fail",
        ),
    )


def _hybrid_required_trust_state_count(hybrid: dict[str, Any]) -> int:
    required_count = hybrid.get("required_trust_state_count")
    if isinstance(required_count, int) and required_count > 0:
        return required_count
    required_states = hybrid.get("required_trust_states")
    if isinstance(required_states, list) and required_states:
        return len(required_states)
    trust_states = hybrid.get("trust_states")
    return len(trust_states) if isinstance(trust_states, list) else 1


def _hybrid_required_node_posture_state_count(hybrid: dict[str, Any]) -> int:
    required_count = hybrid.get("required_node_posture_state_count")
    if isinstance(required_count, int) and required_count > 0:
        return required_count
    required_states = hybrid.get("required_node_posture_states")
    if isinstance(required_states, list) and required_states:
        return len(required_states)
    posture_states = hybrid.get("node_posture_states")
    return len(posture_states) if isinstance(posture_states, list) else 1


def _hybrid_node_relay_contract_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    contract = report.get("hybrid_node_relay_contract")
    if not isinstance(contract, dict):
        unavailable = "利用不可" if lang == "ja" else "unavailable"
        return (CliRow("status", unavailable, "warn"),)
    is_ok = bool(contract.get("ok"))
    status_ok = "正常" if lang == "ja" else "ok"
    needs_attention = "確認が必要" if lang == "ja" else "needs attention"
    not_implemented = "未実装" if lang == "ja" else "not implemented"
    implemented = "実装済み" if lang == "ja" else "implemented"
    schema_version = contract.get("schema_version", "unknown")
    schema_status = "fail" if schema_version == "unknown" else "ok"
    scope = contract.get("public_repo_scope", "unknown")
    scope_status = "fail" if scope == "unknown" else "ok"
    return (
        CliRow("status", status_ok if is_ok else needs_attention, "ok" if is_ok else "fail"),
        CliRow("schema", schema_version, schema_status),
        CliRow("scope", scope, scope_status),
        CliRow(
            "official_cloud_runtime",
            not_implemented if not contract.get("official_cloud_runtime_implemented") else implemented,
            "ok" if not contract.get("official_cloud_runtime_implemented") else "fail",
        ),
        CliRow("production_oracle", contract.get("production_oracle_used"), "fail" if contract.get("production_oracle_used") else "ok"),
        CliRow("network_required", contract.get("network_required"), "fail" if contract.get("network_required") else "ok"),
    )


def _relay_status_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    relay_status = report.get("relay_status")
    if not isinstance(relay_status, dict):
        unavailable = "利用不可" if lang == "ja" else "unavailable"
        return (CliRow("status", unavailable, "warn"),)
    relay = relay_status.get("relay")
    relay = relay if isinstance(relay, dict) else {}
    is_ok = bool(relay_status.get("ok"))
    status_ok = "正常" if lang == "ja" else "ok"
    needs_attention = "確認が必要" if lang == "ja" else "needs attention"
    schema_version = relay_status.get("schema_version", "unknown")
    mode = relay_status.get("mode", "unknown")
    return (
        CliRow("status", status_ok if is_ok else needs_attention, "ok" if is_ok else "fail"),
        CliRow("schema", schema_version, "fail" if schema_version == "unknown" else "ok"),
        CliRow("mode", mode, "fail" if mode == "unknown" else "ok"),
        CliRow("loopback_only", relay.get("loopback_only"), "ok" if relay.get("loopback_only") else "fail"),
        CliRow("process_started", relay.get("process_started"), "fail" if relay.get("process_started") else "ok"),
        CliRow("public_exposure_allowed", relay.get("public_exposure_allowed"), "fail" if relay.get("public_exposure_allowed") else "ok"),
        CliRow("message_body_persisted", relay.get("message_body_persisted"), "fail" if relay.get("message_body_persisted") else "ok"),
    )


def _provider_setup_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    provider_setup = report.get("providers") if isinstance(report.get("providers"), dict) else {}
    providers = provider_setup.get("providers") if isinstance(provider_setup, dict) else []
    rows: list[CliRow] = []
    for provider in providers if isinstance(providers, list) else []:
        if not isinstance(provider, dict):
            continue
        provider_id = str(provider.get("provider_id") or "unknown")
        blockers = provider.get("setup_blockers")
        blocker_text = ", ".join(str(blocker) for blocker in blockers) if isinstance(blockers, list) else ""
        value = str(provider.get("setup_status") or "unknown")
        if blocker_text:
            value = f"{value}; {blocker_text}"
        rows.append(CliRow(provider_id, value, _provider_setup_level(str(provider.get("setup_status") or "unknown"))))
    fallback_name = "プロバイダー" if lang == "ja" else "providers"
    fallback_value = "利用不可" if lang == "ja" else "unavailable"
    return tuple(rows) or (CliRow(fallback_name, fallback_value, "warn"),)


def _provider_runtime_e2e_rows(report: dict[str, Any], *, lang: str = "en") -> tuple[CliRow, ...]:
    fixtures = report.get("provider_runtime_e2e_fixtures")
    if not isinstance(fixtures, dict):
        fixtures = {}
    status_value = fixtures.get("status", "unknown")
    openai_value = fixtures.get("openai_compatible", "unknown")
    local_llm_value = fixtures.get("local_llm", "unknown")
    ledger_value = fixtures.get("run_ledger", "unknown")
    external_network_value = fixtures.get("external_network_call_performed", "unknown")
    return (
        CliRow("status" if lang == "en" else "状態", status_value, _fixture_value_status(status_value, expected="covered_by_local_tests")),
        CliRow("openai_compatible", openai_value, _fixture_value_status(openai_value)),
        CliRow("local_llm", local_llm_value, _fixture_value_status(local_llm_value)),
        CliRow("run_ledger", ledger_value, _fixture_value_status(ledger_value)),
        CliRow(
            "external_network_call_performed" if lang == "en" else "外部ネットワーク通信",
            external_network_value,
            "ok" if external_network_value is False else "fail",
        ),
    )


def _fixture_value_status(value: object, *, expected: object | None = None) -> str:
    if expected is not None:
        if value == expected:
            return "ok"
        return "fail" if value == "unknown" else "warn"
    return "fail" if value == "unknown" else "ok"


def _provider_setup_level(setup_status: str) -> str:
    if setup_status in {"ready", "live_ready"}:
        return "ok"
    if setup_status in {"disabled", "live_opt_in_required", "missing_configuration"}:
        return "warn"
    return "fail"


def _bool_text(value: object) -> str:
    return "true" if value is True else "false" if value is False else str(value)


def _nested_dict(value: object, key: str) -> object:
    if not isinstance(value, dict):
        return None
    return value.get(key)


def _run_public_mvp_smoke(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_trusted_cli_import_paths()
        public_mvp_smoke = _load_public_mvp_smoke_module()
    except Exception as exc:
        raise CliError("public MVP smoke is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else []
        return public_mvp_smoke.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:
        raise CliError("public MVP smoke failed.", exit_code=1) from exc


def _run_public_demo(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_trusted_cli_import_paths()
        public_demo = _load_public_demo_module()
    except Exception as exc:
        raise CliError("YonerAI public demo is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else ["--pretty"]
        return public_demo.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        raise CliError("YonerAI public demo failed.", exit_code=1) from exc


def _prepare_repo_import_path() -> None:
    _pin_import_path_front(_repo_root())


def _prepare_trusted_cli_import_paths() -> None:
    _prepare_repo_import_path()
    _prepare_core_import_path()


def _load_repo_script_module(module_name: str, script_relative_path: str) -> Any:
    script_path = _repo_root() / script_relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise CliError("public script module is unavailable.", exit_code=1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_public_mvp_smoke_module() -> Any:
    return _load_repo_script_module("yonerai_trusted_public_mvp_smoke", "scripts/dev/public_mvp_smoke.py")


def _load_public_demo_module() -> Any:
    return _load_repo_script_module("yonerai_trusted_public_demo", "scripts/dev/public_demo.py")


def _prepare_core_import_path() -> None:
    core_src = _repo_root() / "core" / "src"
    _pin_import_path_front(core_src)


def _pin_import_path_front(path: Path) -> None:
    text = str(path)
    sys.path[:] = [entry for entry in sys.path if entry != text]
    sys.path.insert(0, text)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _preview_route(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.route_preview import preview_route
    except Exception as exc:
        raise CliError("route preview is unavailable.", exit_code=1) from exc

    prompt = _prompt_from_args(args.task)
    local_node_state = args.local_node_state
    fixture_inputs: dict[str, object] | None = None
    if getattr(args, "use_local_node_fixture", False):
        try:
            from ora_core.hybrid.wire_contract import (
                build_local_node_status_report,
                route_preview_inputs_from_node_status,
            )
        except Exception as exc:
            raise CliError("Hybrid Wire Local Node fixture is unavailable.", exit_code=1) from exc
        status_report = build_local_node_status_report()
        local_node = status_report.get("local_node")
        if isinstance(local_node, dict):
            fixture_inputs = route_preview_inputs_from_node_status(local_node)
    has_local_node = args.has_local_node or local_node_state in {
        "present_unverified",
        "present_verified",
        "expired",
        "invalid_signature",
        "wrong_audience",
    }
    if local_node_state == "missing":
        has_local_node = False
    local_node_capabilities = tuple(args.local_node_capability or ()) or None
    require_session = args.require_enrolled_verified_session or args.session_state is not None
    session_state = args.session_state
    if fixture_inputs is not None:
        has_local_node = bool(fixture_inputs["has_local_node"])
        local_node_state = str(fixture_inputs["local_node_verification_state"])
        local_node_capabilities = tuple(fixture_inputs["local_node_capabilities"])  # type: ignore[arg-type]
        require_session = bool(fixture_inputs["require_enrolled_verified_session"])
        session_state = str(fixture_inputs["session_verification_state"])
    decision = preview_route(
        prompt,
        mode=args.mode,
        requested_capability=args.capability,
        has_local_node=has_local_node,
        local_node_verification_state=local_node_state,
        local_node_capabilities=local_node_capabilities,
        require_enrolled_verified_session=require_session,
        session_verification_state=session_state,
        risk_hint=args.risk_hint,
    )
    report = decision.to_public_dict()
    if fixture_inputs is not None:
        report["hybrid_wire_node_fixture_used"] = True
        report["node_posture_state"] = fixture_inputs.get("node_posture_state")
        report["local_work_preview_allowed"] = fixture_inputs.get("local_work_preview_allowed")
    return report


def _print_route_preview_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_route_preview_pretty(report, color=color))


def _format_route_preview_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    audit = report.get("audit_requirements")
    if not isinstance(audit, dict):
        audit = {}
    sections = (
        CliSection(
            "Route preview",
            (
                CliRow("route", report.get("route"), "fail" if report.get("route_strategy") == "deny" else "ok"),
                CliRow("route_strategy", report.get("route_strategy"), "ok"),
                CliRow("task_class", report.get("task_class"), "ok"),
                CliRow("privacy_class", report.get("privacy_class"), "warn" if report.get("privacy_class") != "public" else "ok"),
                CliRow("requested_capability", report.get("requested_capability"), "ok"),
            ),
        ),
        CliSection(
            "Local and cloud gates",
            (
                CliRow("node_posture_state", report.get("node_posture_state") or "none", "ok"),
                CliRow("capability_gate", report.get("capability_gate"), "ok" if report.get("capability_gate") == "satisfied" else "warn"),
                CliRow("approval_state", report.get("approval_state"), "warn" if report.get("approval_state") == "required" else "ok"),
                CliRow("cloud_escape_reason", report.get("cloud_escape_reason") or "none", "warn" if report.get("cloud_escape_reason") else "ok"),
                CliRow("oracle_stub_status", report.get("oracle_stub_status"), "ok" if report.get("oracle_stub_eligible") else "warn"),
            ),
        ),
        CliSection(
            "Audit requirements",
            (
                CliRow("audit_event_required", audit.get("audit_event_required"), "ok"),
                CliRow("args_hash_required", audit.get("args_hash_required"), "ok" if audit.get("args_hash_required") else "warn"),
                CliRow("preserve_approval", audit.get("cloud_escape_preserves_approval"), "ok"),
                CliRow("preserve_args_hash", audit.get("cloud_escape_preserves_args_hash"), "ok"),
            ),
        ),
    )
    return render_report("YonerAI route preview", sections, color=color)


def _print_oracle_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_oracle_pretty(report, color=color))


def _format_oracle_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    request = report.get("request") if isinstance(report.get("request"), dict) else {}
    response = report.get("response") if isinstance(report.get("response"), dict) else {}
    rows = (
        CliRow("operation", report.get("operation", "status"), "ok"),
        CliRow("status", report.get("status"), "ok" if report.get("ok") else "fail"),
        CliRow("local_dev_stub", report.get("local_dev_stub", True), "ok"),
        CliRow("route_strategy", request.get("route_strategy", "n/a"), "ok" if report.get("ok") else "warn"),
        CliRow("privacy_class", request.get("privacy_class", "n/a"), "ok" if request.get("privacy_class") == "public" else "warn"),
        CliRow("run_id", request.get("run_id", "n/a"), "ok"),
    )
    boundaries = (
        CliRow("network_required", report.get("network_required", False), "fail" if report.get("network_required") else "ok"),
        CliRow(
            "provider_call_performed",
            report.get("provider_call_performed", False),
            "fail" if report.get("provider_call_performed") else "ok",
        ),
        CliRow(
            "production_oracle_used",
            report.get("production_oracle_used", False),
            "fail" if report.get("production_oracle_used") else "ok",
        ),
        CliRow(
            "raw_prompt_included",
            response.get("raw_prompt_included", False),
            "fail" if response.get("raw_prompt_included") else "ok",
        ),
        CliRow(
            "private_file_content_included",
            response.get("private_file_content_included", False),
            "fail" if response.get("private_file_content_included") else "ok",
        ),
    )
    non_actions = tuple(CliRow("not_performed", item, "ok") for item in report.get("actions_not_performed", []))
    return render_report(
        "YonerAI Oracle stub",
        (
            CliSection("Local-dev fixture", rows),
            CliSection("Boundaries", boundaries),
            CliSection("Actions not performed", non_actions or (CliRow("actions", "none", "warn"),)),
        ),
        color=color,
    )


def _print_hybrid_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_hybrid_pretty(report, color=color))


def _format_hybrid_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    provider = report.get("provider_execution") if isinstance(report.get("provider_execution"), dict) else {}
    provider_run = provider.get("run") if isinstance(provider.get("run"), dict) else {}
    provider_response = provider.get("response") if isinstance(provider.get("response"), dict) else {}
    selected_route = report.get("selected_route") if isinstance(report.get("selected_route"), dict) else {}
    local_node = report.get("local_node_runtime") if isinstance(report.get("local_node_runtime"), dict) else {}
    proxy = local_node.get("http_proxy_fixture") if isinstance(local_node.get("http_proxy_fixture"), dict) else {}
    oracle = report.get("oracle_stub_execution") if isinstance(report.get("oracle_stub_execution"), dict) else {}
    oracle_request = oracle.get("request") if isinstance(oracle.get("request"), dict) else {}
    boundaries = report.get("boundaries") if isinstance(report.get("boundaries"), dict) else {}
    route_rows = tuple(
        CliRow(
            str(item.get("name")),
            str(item.get("route_strategy")),
            "ok",
            note=f"privacy={item.get('privacy_class')} approval={item.get('approval_state')}",
        )
        for item in report.get("route_matrix", [])
        if isinstance(item, dict)
    )
    sections = (
        CliSection(
            "Hybrid run",
            (
                CliRow("status", "ok" if report.get("ok") else "failed", "ok" if report.get("ok") else "fail"),
                CliRow("selected_route", selected_route.get("route_strategy"), "ok"),
                CliRow("provider_run_id", provider_run.get("run_id"), "ok" if provider_run.get("run_id") else "warn"),
                CliRow("provider", provider_response.get("provider") or "none", "ok" if provider_response else "warn"),
            ),
        ),
        CliSection(
            "Local-dev node and relay",
            (
                CliRow("local_node_runtime", local_node.get("ok"), "ok" if local_node.get("ok") else "fail"),
                CliRow(
                    "relay_loopback_only",
                    _nested_dict(local_node.get("relay"), "loopback_only"),
                    "ok" if _nested_dict(local_node.get("relay"), "loopback_only") is True else "fail",
                ),
                CliRow("proxy_status", proxy.get("status"), "ok" if proxy.get("status") == "completed" else "warn"),
                CliRow("message_body_persisted", boundaries.get("message_body_persisted"), "fail" if boundaries.get("message_body_persisted") else "ok"),
            ),
        ),
        CliSection(
            "Oracle stub",
            (
                CliRow("status", oracle.get("status"), "ok" if oracle.get("ok") else "warn"),
                CliRow("run_id", oracle_request.get("run_id"), "ok" if oracle_request.get("run_id") else "warn"),
                CliRow("route_strategy", oracle_request.get("route_strategy"), "ok"),
                CliRow("raw_prompt_sent", boundaries.get("raw_prompt_sent_to_oracle_stub"), "fail" if boundaries.get("raw_prompt_sent_to_oracle_stub") else "ok"),
                CliRow(
                    "private_file_sent",
                    boundaries.get("private_file_content_sent_to_oracle_stub"),
                    "fail" if boundaries.get("private_file_content_sent_to_oracle_stub") else "ok",
                ),
            ),
        ),
        CliSection("Route matrix", route_rows),
        CliSection(
            "Non-actions",
            tuple(CliRow("boundary", item, "ok") for item in report.get("actions_not_performed", [])),
        ),
    )
    return render_report("YonerAI Hybrid local-dev run", sections, color=color)


def _build_node_status_report() -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.hybrid.wire_contract import build_local_node_status_report
    except Exception as exc:
        raise CliError("Hybrid Wire Local Node status is unavailable.", exit_code=1) from exc
    return build_local_node_status_report()


def _build_node_pair_report(args: argparse.Namespace) -> dict[str, Any]:
    if not args.dry_run:
        raise CliError("yonerai node pair is dry-run only in this public repo.", exit_code=2)
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.hybrid.wire_contract import build_pairing_dry_run_report
    except Exception as exc:
        raise CliError("Hybrid Wire Local Node pairing dry-run is unavailable.", exit_code=1) from exc
    return build_pairing_dry_run_report()


def _build_relay_status_report() -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.hybrid.relay_status import build_relay_status_report
    except Exception as exc:
        raise CliError("Hybrid Relay local-dev status is unavailable.", exit_code=1) from exc
    return build_relay_status_report(os.environ)


def _print_node_status_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_node_status_pretty(report, color=color))


def _format_node_status_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    local_node_value = report.get("local_node") or {}
    local_node = local_node_value if isinstance(local_node_value, dict) else {}
    manifest_value = local_node.get("capability_manifest") or {}
    manifest = manifest_value if isinstance(manifest_value, dict) else {}
    capabilities_value = manifest.get("capabilities") or []
    capabilities = capabilities_value if isinstance(capabilities_value, list) else []
    capability_rows = tuple(
        CliRow(
            str(capability.get("name")),
            "enabled" if capability.get("enabled") else "disabled",
            "ok" if capability.get("enabled") else "warn",
            note="approval required" if capability.get("approval_required") else None,
        )
        for capability in capabilities
        if isinstance(capability, dict)
    )
    sections = (
        CliSection(
            "Hybrid Wire Contract",
            (
                CliRow("schema", report.get("schema_version"), "ok"),
                CliRow("trust_state", local_node.get("trust_state"), "ok"),
                CliRow("posture_state", _node_posture_state(local_node), "ok"),
                CliRow("loopback_only", local_node.get("loopback_only"), "ok"),
                CliRow("non_production", local_node.get("non_production"), "ok"),
            ),
        ),
        CliSection(
            "Local Node fixture",
            (
                CliRow("available", local_node.get("available"), "ok" if local_node.get("available") else "warn"),
                CliRow("production_trust_material", local_node.get("production_trust_material"), "fail" if local_node.get("production_trust_material") else "ok"),
                CliRow("network_required", report.get("network_required"), "fail" if report.get("network_required") else "ok"),
                CliRow(
                    "official_cloud_runtime",
                    "not implemented" if not report.get("official_cloud_runtime_implemented") else "implemented",
                    "ok" if not report.get("official_cloud_runtime_implemented") else "fail",
                ),
            ),
        ),
        CliSection("Capabilities", capability_rows),
        CliSection(
            "Non-actions",
            tuple(CliRow("boundary", action, "ok") for action in report.get("actions_not_performed", ())),
        ),
    )
    return render_report("YonerAI Local Node status", sections, color=color)


def _print_node_pair_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_node_pair_pretty(report, color=color))


def _format_node_pair_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    request = report.get("official_orchestration_stub_request")
    if not isinstance(request, dict):
        request = {}
    response = report.get("official_orchestration_stub_response")
    if not isinstance(response, dict):
        response = {}
    decision = report.get("trust_decision")
    if not isinstance(decision, dict):
        decision = {}
    sections = (
        CliSection(
            "Pairing dry-run",
            (
                CliRow("schema", report.get("schema_version"), "ok"),
                CliRow("dry_run", report.get("dry_run"), "ok" if report.get("dry_run") else "fail"),
                CliRow("pairing_performed", report.get("pairing_performed"), "fail" if report.get("pairing_performed") else "ok"),
                CliRow("request_schema", request.get("schema_name"), "ok"),
                CliRow("response_schema", response.get("schema_name"), "ok" if response else "warn"),
            ),
        ),
        CliSection(
            "Trust decision",
            (
                CliRow("state", decision.get("state"), _trust_decision_status(decision)),
                CliRow("requested_capability", decision.get("requested_capability"), "ok"),
                CliRow("execute_allowed", decision.get("execute_allowed"), "fail" if decision.get("execute_allowed") else "ok"),
                CliRow("approval_required", decision.get("approval_required"), "warn" if decision.get("approval_required") else "ok"),
            ),
        ),
        CliSection(
            "Non-actions",
            tuple(CliRow("boundary", action, "ok") for action in report.get("actions_not_performed", ())),
        ),
    )
    return render_report("YonerAI Local Node pairing preview", sections, color=color)


def _node_posture_state(local_node: dict[str, Any]) -> object:
    posture = local_node.get("posture")
    if not isinstance(posture, dict):
        return "unknown"
    return posture.get("state", "unknown")


def _print_relay_status_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_relay_status_pretty(report, color=color))


def _format_relay_status_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    relay_value = report.get("relay") or {}
    relay = relay_value if isinstance(relay_value, dict) else {}
    connector_value = report.get("node_connector") or {}
    connector = connector_value if isinstance(connector_value, dict) else {}
    limits_value = report.get("limits") or {}
    limits = limits_value if isinstance(limits_value, dict) else {}
    sections = (
        CliSection(
            "Local-dev relay",
            (
                CliRow("schema", report.get("schema_version"), "ok"),
                CliRow("mode", report.get("mode"), "ok"),
                CliRow("host", relay.get("host"), "ok" if relay.get("loopback_only") else "fail"),
                CliRow("port", relay.get("port"), "ok"),
                CliRow("loopback_only", relay.get("loopback_only"), "ok" if relay.get("loopback_only") else "fail"),
                CliRow(
                    "public_exposure_requested",
                    relay.get("public_exposure_requested"),
                    "fail" if relay.get("public_exposure_requested") else "ok",
                ),
                CliRow("public_exposure_allowed", relay.get("public_exposure_allowed"), "fail" if relay.get("public_exposure_allowed") else "ok"),
            ),
        ),
        CliSection(
            "Runtime boundary",
            (
                CliRow("process_started", relay.get("process_started"), "fail" if relay.get("process_started") else "ok"),
                CliRow("health_probe_performed", relay.get("health_probe_performed"), "fail" if relay.get("health_probe_performed") else "ok"),
                CliRow("quick_tunnel_enabled", relay.get("quick_tunnel_enabled"), "fail" if relay.get("quick_tunnel_enabled") else "ok"),
                CliRow("message_body_persisted", relay.get("message_body_persisted"), "fail" if relay.get("message_body_persisted") else "ok"),
                CliRow("pairing_code_storage", relay.get("pairing_code_storage"), "ok"),
                CliRow("session_token_storage", relay.get("session_token_storage"), "ok"),
            ),
        ),
        CliSection(
            "Node connector",
            (
                CliRow(
                    "relay_url_category",
                    connector.get("relay_url_category"),
                    "ok"
                    if connector.get("relay_url_category") in {"loopback", "auto_unresolved_no_probe", "auto_resolved_loopback"}
                    else "fail",
                ),
                CliRow(
                    "node_api_base_url_category",
                    connector.get("node_api_base_url_category"),
                    "ok" if connector.get("node_api_base_url_category") == "loopback" else "fail",
                ),
                CliRow("connector_started", connector.get("connector_started"), "fail" if connector.get("connector_started") else "ok"),
                CliRow("pairing_code_printed", connector.get("pairing_code_printed"), "fail" if connector.get("pairing_code_printed") else "ok"),
            ),
        ),
        CliSection(
            "Limits",
            tuple(CliRow(key, value, "ok") for key, value in limits.items()),
        ),
        CliSection(
            "Non-actions",
            tuple(CliRow("boundary", action, "ok") for action in report.get("actions_not_performed", ())),
        ),
    )
    return render_report("YonerAI Relay local-dev status", sections, color=color)


def _trust_decision_status(decision: dict[str, Any]) -> str:
    state = decision.get("state")
    if decision.get("execute_allowed"):
        return "fail"
    if state == "verified_test_node":
        return "ok"
    if state in {
        "approval_required",
        "capability_not_declared",
        "expired_session",
        "missing_node",
        "revoked_session",
        "unverified_node",
    }:
        return "warn"
    return "fail"


def _build_execution_plan_report(args: argparse.Namespace, *, command: str, dry_run: bool) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.planning import build_execution_plan
    except Exception as exc:
        raise CliError("execution plan preview is unavailable.", exit_code=1) from exc

    prompt = _prompt_from_args(args.task)
    try:
        plan = build_execution_plan(
            prompt,
            command=command,
            mode=args.mode,
            provider=args.provider,
            dry_run=dry_run,
        )
    except ValueError as exc:
        raise CliError(str(exc), exit_code=2) from exc
    return plan.to_public_dict()


def _print_execution_plan_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_execution_plan_pretty(report, color=color))


def _format_execution_plan_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    classification = report["classification"]
    provider = report["provider"]
    route = report["route"]
    model = report["model"]
    approval = report["approval"]
    side_effects = report["side_effects"]
    safety = report["safety_checks"]
    disabled_reasons = report.get("disabled_reasons") or []
    sections = (
        CliSection(
            "Task",
            (
                CliRow("command", report["command"], "ok"),
                CliRow("category", classification["category"], "ok"),
                CliRow("risk", classification["risk"], "warn" if classification["risk"] != "safe_public" else "ok"),
                CliRow("complexity", classification["complexity"], "ok"),
                CliRow("execution_surface", report["estimated_execution_surface"], "warn" if approval["required"] else "ok"),
            ),
        ),
        CliSection(
            "Route and provider",
            (
                CliRow("route", route["route"], "warn" if route.get("unavailable_reason") else "ok"),
                CliRow("mode", route["mode"], "ok"),
                CliRow("provider", provider["provider_id"], "ok" if provider["provider_available"] else "warn"),
                CliRow("provider_available", provider["provider_available"], "ok" if provider["provider_available"] else "warn"),
                CliRow("model_tier", model["tier"], "ok"),
                CliRow("model", model["model_id"], "ok"),
            ),
        ),
        CliSection(
            "Approval and disabled reasons",
            (
                CliRow("approval_required", approval["required"], "warn" if approval["required"] else "ok"),
                CliRow("disabled_reasons", ", ".join(disabled_reasons) if disabled_reasons else "none", "warn" if disabled_reasons else "ok"),
            ),
        ),
        CliSection(
            "Safety checks",
            (
                CliRow("mcp_deny_policy", safety["mcp_deny_policy"]["status"], "ok" if safety["mcp_deny_policy"]["ok"] else "fail"),
                CliRow(
                    "managed_download_guard",
                    safety["managed_download_guard"]["status"],
                    "ok" if safety["managed_download_guard"]["ok"] else "fail",
                ),
                CliRow("provider_call", side_effects["provider_call"], "fail" if side_effects["provider_call"] else "ok"),
                CliRow("network_call", side_effects["network_call"], "fail" if side_effects["network_call"] else "ok"),
                CliRow("shell", side_effects["shell"], "fail" if side_effects["shell"] else "ok"),
                CliRow("file_access", side_effects["file_access"], "fail" if side_effects["file_access"] else "ok"),
                CliRow("deploy", side_effects["deploy"], "fail" if side_effects["deploy"] else "ok"),
            ),
        ),
    )
    return render_report("YonerAI execution plan", sections, color=color)


def _execute_ask_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.execution.workspace_files import (
            WorkspaceFileError,
            build_workspace_file_access_event,
            build_workspace_file_prompt,
            read_workspace_text_file,
        )
        from ora_core.execution.ledger import build_run_ledger_from_env
        from ora_core.execution.spine import execute_task
    except Exception as exc:
        raise CliError("execution spine is unavailable.", exit_code=1) from exc

    prompt = _prompt_from_args(args.task)
    ledger_status = _ledger_status(args.ledger_path)
    provider_prompt = prompt
    file_context = None
    context_events = []
    if args.file:
        if not args.workspace:
            raise CliError("--workspace is required when --file is used.", exit_code=2)
        try:
            file_context = read_workspace_text_file(
                args.file,
                workspace=args.workspace,
                max_bytes=args.file_max_bytes,
            )
        except WorkspaceFileError as exc:
            return {
                "schema_version": "yonerai-execution-result/v1",
                "ok": False,
                "run": None,
                "plan": None,
                "response": None,
                "boundary_checks": {},
                "live_call_performed": False,
                "ledger": ledger_status,
                "file_context": None,
                "error": exc.to_public_dict(),
            }
        provider_prompt = build_workspace_file_prompt(prompt, file_context)
        context_events.append(build_workspace_file_access_event(file_context))
    try:
        result = execute_task(
            prompt,
            provider_prompt=provider_prompt,
            mode=args.mode,
            provider=args.provider,
            live=args.live,
            ledger=build_run_ledger_from_env(args.ledger_path),
            context_events=context_events,
        )
    except ValueError as exc:
        raise CliError(str(exc), exit_code=2) from exc
    report = result.to_public_dict()
    report["ledger"] = ledger_status
    if file_context is not None:
        report["file_context"] = file_context.to_public_dict()
    return report


def _execute_auto_ask_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.execution.auto_runtime import build_auto_runtime_report
        from ora_core.execution.workspace_files import (
            WorkspaceFileError,
            build_workspace_file_access_event,
            build_workspace_file_prompt,
            read_workspace_text_file,
        )
        from ora_core.execution.ledger import build_run_ledger_from_env
    except Exception as exc:
        raise CliError("auto runtime is unavailable.", exit_code=1) from exc

    prompt = _prompt_from_args(args.task)
    ledger_status = _ledger_status(args.ledger_path)
    provider_prompt = prompt
    file_context = None
    context_events = []
    if args.file:
        if not args.workspace:
            raise CliError("--workspace is required when --file is used.", exit_code=2)
        try:
            file_context = read_workspace_text_file(
                args.file,
                workspace=args.workspace,
                max_bytes=args.file_max_bytes,
            )
        except WorkspaceFileError as exc:
            return {
                "schema_version": "yonerai-auto-runtime/v0.1",
                "ok": False,
                "command": "yonerai ask --auto",
                "run": None,
                "auto": None,
                "response": None,
                "ledger": ledger_status,
                "file_context": None,
                "live_call_performed": False,
                "error": exc.to_public_dict(),
            }
        provider_prompt = build_workspace_file_prompt(prompt, file_context)
        context_events.append(build_workspace_file_access_event(file_context))
    try:
        report = build_auto_runtime_report(
            prompt,
            provider_prompt=provider_prompt,
            provider=args.provider,
            live=args.live,
            ledger=build_run_ledger_from_env(args.ledger_path),
            context_events=context_events,
            local_file_context=file_context is not None,
        )
    except ValueError as exc:
        raise CliError(str(exc), exit_code=2) from exc
    report["ledger"] = ledger_status
    if file_context is not None:
        report["file_context"] = file_context.to_public_dict()
    return report


def _print_execution_result_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_execution_result_pretty(report, color=color))


def _print_auto_runtime_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    print(_format_auto_runtime_pretty(report, lang=lang, color=color))


def _format_auto_runtime_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    if report.get("run") is None or report.get("auto") is None:
        error = report.get("error") or {}
        return render_report(
            "YonerAI ask --auto",
            (CliSection("Error", (CliRow(str(error.get("code") or "error"), error.get("message") or "request failed", "fail"),)),),
            color=color,
        )
    run = report["run"] if isinstance(report.get("run"), dict) else {}
    auto = report["auto"] if isinstance(report.get("auto"), dict) else {}
    provider = report["provider"] if isinstance(report.get("provider"), dict) else {}
    response = report["response"] if isinstance(report.get("response"), dict) else {}
    search = report["search"] if isinstance(report.get("search"), dict) else {}
    reviewer = report["reviewer_plan"] if isinstance(report.get("reviewer_plan"), dict) else {}
    task_progress = report["task_progress"] if isinstance(report.get("task_progress"), dict) else {}
    boundaries = report["boundaries"] if isinstance(report.get("boundaries"), dict) else {}
    error = report["error"] if isinstance(report.get("error"), dict) else {}
    ledger = report["ledger"] if isinstance(report.get("ledger"), dict) else {}
    actions_not_performed = tuple(str(item) for item in report.get("actions_not_performed") or ())
    if lang == "ja":
        sections = _auto_runtime_sections_ja(
            report=report,
            run=run,
            auto=auto,
            provider=provider,
            response=response,
            search=search,
            reviewer=reviewer,
            task_progress=task_progress,
            boundaries=boundaries,
            error=error,
            ledger=ledger,
            actions_not_performed=actions_not_performed,
        )
        return render_report("YonerAI ask --auto", sections, color=color)
    sections = (
        CliSection(
            "Auto runtime",
            (
                CliRow("run_id", run.get("run_id"), "ok" if run.get("run_id") else "warn"),
                CliRow("status", run.get("status"), "ok" if run.get("status") == "completed" else "warn"),
                CliRow("difficulty", auto.get("difficulty"), "ok"),
                CliRow("privacy", auto.get("privacy"), "ok" if auto.get("privacy") == "public" else "warn"),
                CliRow("route", auto.get("route"), "fail" if auto.get("route") == "deny" else "ok"),
                CliRow("route_label", _auto_route_label_en(auto.get("route")), "fail" if auto.get("route") == "deny" else "ok"),
                CliRow("approval_required", auto.get("approval_required"), "warn" if auto.get("approval_required") else "ok"),
            ),
        ),
        CliSection(
            "Execution",
            (
                CliRow("provider", provider.get("provider_id"), "ok" if provider.get("provider_available") else "warn"),
                CliRow("model", response.get("model") or provider.get("model_id"), "ok"),
                CliRow("live_call_performed", report.get("live_call_performed"), "warn" if report.get("live_call_performed") else "ok"),
                CliRow("output", response.get("output_text") or error.get("message") or "none", "ok" if report.get("ok") else "warn"),
            ),
        ),
        CliSection(
            "Ledger",
            (
                CliRow("enabled", ledger.get("enabled", False), "ok" if ledger.get("enabled") else "warn"),
                CliRow("file_backed", ledger.get("file_backed", False), _optional_bool_status(ledger.get("file_backed", False))),
                CliRow("local_only", ledger.get("local_only", True), "ok"),
                CliRow("raw_prompt_persisted", ledger.get("raw_prompt_persisted", False), "fail" if ledger.get("raw_prompt_persisted") else "ok"),
                CliRow("next", _runs_next_command(run, ledger), "ok" if ledger.get("file_backed") else "warn"),
            ),
        ),
        CliSection(
            "Task progress",
            tuple(
                CliRow(
                    str(step.get("id") or "step"),
                    f"{step.get('state')}: {step.get('summary')}",
                    _progress_status_for_cli(step.get("state")),
                )
                for step in _progress_steps(task_progress)
            )
            or (CliRow("progress", "not recorded", "warn"),),
        ),
        CliSection(
            "Search and reviewer",
            (
                CliRow("search_mode", search.get("mode"), "ok" if search.get("mode") in {"mock", "not_requested"} else "warn"),
                CliRow("search_results", len(search.get("results") or []), "ok"),
                CliRow("reviewer_plan", reviewer.get("enabled"), "ok" if reviewer.get("enabled") else "skipped"),
                CliRow("subtasks", reviewer.get("subtask_count"), "ok" if reviewer.get("enabled") else "skipped"),
            ),
        ),
        CliSection(
            "Boundaries",
            (
                CliRow("private_file_to_cloud", boundaries.get("private_file_content_sent_to_cloud_contract"), "fail" if boundaries.get("private_file_content_sent_to_cloud_contract") else "ok"),
                CliRow("live_search_performed", boundaries.get("live_search_performed"), "fail" if boundaries.get("live_search_performed") else "ok"),
                CliRow("shell_execution", boundaries.get("shell_execution_performed"), "fail" if boundaries.get("shell_execution_performed") else "ok"),
                CliRow("production_oracle", boundaries.get("production_oracle_used"), "fail" if boundaries.get("production_oracle_used") else "ok"),
                CliRow("official_cloud_runtime", boundaries.get("official_cloud_runtime_implemented"), "fail" if boundaries.get("official_cloud_runtime_implemented") else "ok"),
            ),
        ),
        CliSection(
            "Non-actions",
            tuple(CliRow(f"no_{index}", item, "ok") for index, item in enumerate(actions_not_performed[:6], start=1)),
        ),
    )
    return render_report("YonerAI ask --auto", sections, color=color)


def _auto_runtime_sections_ja(
    *,
    report: dict[str, Any],
    run: dict[str, Any],
    auto: dict[str, Any],
    provider: dict[str, Any],
    response: dict[str, Any],
    search: dict[str, Any],
    reviewer: dict[str, Any],
    task_progress: dict[str, Any],
    boundaries: dict[str, Any],
    error: dict[str, Any],
    ledger: dict[str, Any],
    actions_not_performed: tuple[str, ...],
) -> tuple[CliSection, ...]:
    return (
        CliSection(
            "判断",
            (
                CliRow("run_id", run.get("run_id"), "ok" if run.get("run_id") else "warn"),
                CliRow("状態", _run_status_ja(run.get("status")), "ok" if run.get("status") == "completed" else "warn"),
                CliRow("難しさ", _auto_difficulty_ja(auto.get("difficulty")), "ok"),
                CliRow("privacy", _auto_privacy_ja(auto.get("privacy")), "ok" if auto.get("privacy") == "public" else "warn"),
                CliRow("経路", _auto_route_label_ja(auto.get("route")), "fail" if auto.get("route") == "deny" else "ok"),
                CliRow("承認", "必要" if auto.get("approval_required") else "不要", "warn" if auto.get("approval_required") else "ok"),
            ),
        ),
        CliSection(
            "実行",
            (
                CliRow("provider", provider.get("provider_id"), "ok" if provider.get("provider_available") else "warn"),
                CliRow("model", response.get("model") or provider.get("model_id"), "ok"),
                CliRow("live呼び出し", _yes_no_ja(report.get("live_call_performed")), "warn" if report.get("live_call_performed") else "ok"),
                CliRow("出力", response.get("output_text") or error.get("message") or "なし", "ok" if report.get("ok") else "warn"),
            ),
        ),
        CliSection(
            "履歴",
            (
                CliRow("有効", _yes_no_ja(ledger.get("enabled", False)), "ok" if ledger.get("enabled") else "warn"),
                CliRow("file-backed", _yes_no_ja(ledger.get("file_backed", False)), _optional_bool_status(ledger.get("file_backed", False))),
                CliRow("local-only", _yes_no_ja(ledger.get("local_only", True)), "ok"),
                CliRow("raw prompt保存", _yes_no_ja(ledger.get("raw_prompt_persisted", False)), "fail" if ledger.get("raw_prompt_persisted") else "ok"),
                CliRow("次に見る", _runs_next_command(run, ledger), "ok" if ledger.get("file_backed") else "warn"),
            ),
        ),
        CliSection(
            "進行状況",
            tuple(
                CliRow(
                    _progress_step_label_ja(step.get("id")),
                    f"{_progress_state_label_ja(step.get('state'))}: {_progress_summary_ja(step.get('id'), step.get('summary'))}",
                    _progress_status_for_cli(step.get("state")),
                )
                for step in _progress_steps(task_progress)
            )
            or (CliRow("進行", "記録なし", "warn"),),
        ),
        CliSection(
            "検索とレビュー",
            (
                CliRow("検索", _search_mode_ja(search.get("mode")), "ok" if search.get("mode") in {"mock", "not_requested"} else "warn"),
                CliRow("検索結果数", len(search.get("results") or []), "ok"),
                CliRow("レビュー計画", _yes_no_ja(reviewer.get("enabled")), "ok" if reviewer.get("enabled") else "skipped"),
                CliRow("担当数", reviewer.get("subtask_count"), "ok" if reviewer.get("enabled") else "skipped"),
                CliRow("実エージェント起動", "なし（計画表示のみ）", "ok"),
            ),
        ),
        CliSection(
            "境界",
            (
                CliRow("private fileをcloudへ送信", _yes_no_ja(boundaries.get("private_file_content_sent_to_cloud_contract")), "fail" if boundaries.get("private_file_content_sent_to_cloud_contract") else "ok"),
                CliRow("live search", _yes_no_ja(boundaries.get("live_search_performed")), "fail" if boundaries.get("live_search_performed") else "ok"),
                CliRow("shell実行", _yes_no_ja(boundaries.get("shell_execution_performed")), "fail" if boundaries.get("shell_execution_performed") else "ok"),
                CliRow("production Oracle", _yes_no_ja(boundaries.get("production_oracle_used")), "fail" if boundaries.get("production_oracle_used") else "ok"),
                CliRow("official cloud runtime", _yes_no_ja(boundaries.get("official_cloud_runtime_implemented")), "fail" if boundaries.get("official_cloud_runtime_implemented") else "ok"),
            ),
        ),
        CliSection(
            "この実行がしないこと",
            tuple(CliRow(f"未実行{index}", _provider_non_action_ja(item), "ok") for index, item in enumerate(actions_not_performed[:6], start=1)),
        ),
    )


def _auto_route_label_en(route: object) -> str:
    mapping = {
        "instant_local": "run immediately through local mock/provider-safe path",
        "local_llm": "run through explicit loopback-only local LLM",
        "hybrid_node": "keep private/local-file context on the local Hybrid node path",
        "cloud_contract_candidate": "public hard task queued to local-dev Oracle stub envelope",
        "deny": "blocked because approval or unsafe capability would be required",
    }
    return mapping.get(str(route), "unknown route")


def _progress_steps(task_progress: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    steps = task_progress.get("steps") if isinstance(task_progress.get("steps"), list) else []
    return tuple(step for step in steps if isinstance(step, dict))


def _progress_status_for_cli(state: object) -> str:
    if state == "done":
        return "ok"
    if state == "skipped":
        return "skipped"
    if state == "blocked":
        return "warn"
    if state == "error":
        return "fail"
    if state == "running":
        return "warn"
    return "warn"


def _progress_step_label_ja(value: object) -> str:
    mapping = {
        "classify": "分類",
        "route": "経路選択",
        "provider_selection": "提供元選択",
        "execution": "実行",
        "review": "レビュー",
        "result": "結果",
    }
    return mapping.get(str(value), str(value or "不明"))


def _progress_state_label_ja(value: object) -> str:
    mapping = {
        "pending": "待機",
        "running": "実行中",
        "done": "完了",
        "skipped": "スキップ",
        "blocked": "ブロック",
        "error": "エラー",
    }
    return mapping.get(str(value), str(value or "不明"))


def _progress_summary_ja(step: object, summary: object) -> str:
    text = str(summary or "")
    step_id = str(step)
    if step_id == "classify" and "difficulty=" in text:
        return text.replace("difficulty=instant", "難易度=即時").replace("difficulty=task", "難易度=タスク").replace(
            "difficulty=agent", "難易度=複雑"
        ).replace("privacy=public", "公開").replace("privacy=local_file", "ローカルファイル").replace("privacy=private", "非公開")
    if step_id == "route" and "route=" in text:
        return text.replace("route=instant_local", "経路=ローカル即時").replace("route=local_llm", "経路=ローカルLLM").replace(
            "route=cloud_contract_candidate", "経路=クラウド候補"
        ).replace("route=deny", "経路=拒否").replace("approval_required=false", "承認不要").replace(
            "approval_required=true", "承認必要"
        )
    if step_id == "provider_selection" and "provider=" in text:
        return text.replace("provider=mock", "提供元=モック").replace("provider=oracle-stub", "提供元=オラクルスタブ").replace(
            "provider=local", "提供元=ローカル"
        )
    if step_id == "execution":
        if text.startswith("executed route="):
            return "選択した安全な経路で実行しました"
        if text.startswith("execution skipped"):
            return "安全上、実行をスキップしました"
        if text.startswith("execution stopped"):
            return "実行を停止しました"
    if step_id == "review":
        if text.startswith("reviewer plan not required"):
            return "この経路ではレビュー計画は不要です"
        if text.startswith("subagents_planned="):
            return text.replace("subagents_planned=", "担当計画=").replace(" reviewer_required=true", " / レビューあり")
    if step_id == "result":
        if text.startswith("result returned"):
            return "秘匿済みの安全な結果を返しました"
        if text.startswith("blocked safely"):
            return "安全にブロックしました"
        if text.startswith("result unavailable"):
            return "結果は利用できません"
    return text


def _auto_route_label_ja(route: object) -> str:
    mapping = {
        "instant_local": "ローカルで即時実行",
        "local_llm": "loopback-only local LLMで実行",
        "hybrid_node": "private/local-fileをローカルHybrid側に留める",
        "cloud_contract_candidate": "公開タスクだけlocal-dev Oracle stubへ",
        "deny": "危険または未承認のため拒否",
    }
    return mapping.get(str(route), "不明")


def _auto_difficulty_ja(value: object) -> str:
    mapping = {"instant": "すぐ返せる", "task": "通常タスク", "agent": "複数手順"}
    return mapping.get(str(value), str(value or "不明"))


def _auto_privacy_ja(value: object) -> str:
    mapping = {"public": "公開情報", "private": "private扱い", "local_file": "選択ファイル内", "dangerous": "危険操作"}
    return mapping.get(str(value), str(value or "不明"))


def _run_status_ja(value: object) -> str:
    mapping = {"completed": "完了", "failed": "失敗", "blocked": "ブロック", "running": "実行中", "created": "作成済み"}
    return mapping.get(str(value), str(value or "不明"))


def _search_mode_ja(value: object) -> str:
    mapping = {"mock": "mock検索", "not_requested": "検索なし", "live": "live検索"}
    return mapping.get(str(value), str(value or "不明"))


def _runs_next_command(run: dict[str, Any], ledger: dict[str, Any]) -> str:
    run_id = str(run.get("run_id") or "<run_id>")
    if ledger.get("file_backed"):
        return f"yonerai runs show {run_id} --ledger <local.jsonl> --json"
    return '履歴を残すには: yonerai ask "hello" --auto --ledger .yonerai-runs.jsonl --json'


def _format_execution_result_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    if report.get("run") is None or report.get("plan") is None:
        error = report.get("error") or {}
        return render_report(
            "YonerAI ask",
            (CliSection("Error", (CliRow(str(error.get("code") or "error"), error.get("message") or "request failed", "fail"),)),),
            color=color,
        )
    run = report["run"]
    plan = report["plan"]
    response = report.get("response") or {}
    error = report.get("error") or {}
    boundary = report.get("boundary_checks") or {}
    ledger = report.get("ledger") or {}
    file_backed = ledger.get("file_backed", "unknown")
    provider = plan["provider"]
    sections = (
        CliSection(
            "Run",
            (
                CliRow("run_id", run["run_id"], "ok"),
                CliRow("status", run["status"], "ok" if run["status"] == "completed" else "warn"),
                CliRow("category", plan["classification"]["category"], "ok"),
                CliRow("approval_required", run["approval_required"], "warn" if run["approval_required"] else "ok"),
                CliRow("file_backed", file_backed, _optional_bool_status(file_backed)),
            ),
        ),
        CliSection(
            "Provider",
            (
                CliRow("provider", provider["provider_id"], "ok" if provider["provider_available"] else "warn"),
                CliRow("model", response.get("model") or plan["model"]["model_id"], "ok"),
                CliRow("live_call_performed", report["live_call_performed"], "warn" if report["live_call_performed"] else "ok"),
            ),
        ),
        CliSection(
            "Answer",
            (
                CliRow("ok", report["ok"], "ok" if report["ok"] else "warn"),
                CliRow("output", response.get("output_text") or error.get("message") or "none", "ok" if report["ok"] else "warn"),
            ),
        ),
        CliSection(
            "Boundaries",
            (
                CliRow("web_search", boundary.get("web_search", {}).get("status", "unknown"), "ok"),
                CliRow("tool_boundary", boundary.get("tool_boundary", {}).get("status", "unknown"), "ok"),
                CliRow(
                    "ora_tool_schema_boundary",
                    boundary.get("ora_tool_schema_boundary", {}).get("status", "unknown"),
                    "ok" if boundary.get("ora_tool_schema_boundary", {}).get("status") == "ok" else "warn",
                ),
                CliRow(
                    "ora_guardrail_response_interpreter",
                    boundary.get("ora_guardrail_response_interpreter", {}).get("status", "unknown"),
                    "ok" if boundary.get("ora_guardrail_response_interpreter", {}).get("status") == "ok" else "warn",
                ),
                CliRow("shell", plan["side_effects"]["shell"], "fail" if plan["side_effects"]["shell"] else "ok"),
                CliRow("file_access", plan["side_effects"]["file_access"], "fail" if plan["side_effects"]["file_access"] else "ok"),
                CliRow("memory_persisted", run["persistence"]["memory_persisted"], "fail" if run["persistence"]["memory_persisted"] else "ok"),
            ),
        ),
    )
    return render_report("YonerAI ask", sections, color=color)


def _build_runs_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.execution.ledger import build_run_ledger_from_env
    except Exception as exc:
        raise CliError("run ledger is unavailable.", exit_code=1) from exc

    ledger = build_run_ledger_from_env(args.ledger_path)
    ledger_status = _ledger_status(args.ledger_path)
    if args.runs_command == "list":
        runs = [run.to_public_dict() for run in ledger.list_runs(limit=args.limit)]
        return {
            "schema_version": "yonerai-runs-list/v1",
            "ok": True,
            "ledger": ledger_status,
            "runs": runs,
            "count": len(runs),
            "raw_prompt_persisted": False,
            "raw_completion_persisted": False,
        }
    run = ledger.get_run(args.run_id)
    if run is None:
        return {
            "schema_version": "yonerai-runs-show/v1",
            "ok": False,
            "ledger": ledger_status,
            "error": {"code": "unknown_run", "message": "run_id was not found in the selected local ledger"},
            "run": None,
        }
    return {
        "schema_version": "yonerai-runs-show/v1",
        "ok": True,
        "ledger": ledger_status,
        "run": run.to_public_dict(),
        "raw_prompt_persisted": False,
        "raw_completion_persisted": False,
    }


def _ledger_status(ledger_path: str | None) -> dict[str, object]:
    configured = bool((ledger_path or os.getenv("YONERAI_RUN_LEDGER_PATH") or "").strip())
    return {
        "enabled": configured,
        "file_backed": configured,
        "local_only": True,
        "path_persisted_in_output": False,
        "raw_prompt_persisted": False,
        "raw_completion_persisted": False,
    }


def _start_cli_boundary_run(
    ledger: Any,
    *,
    task_text: str,
    category: str,
    route: str,
    provider_id: str,
    provider_available: bool,
    disabled_reason: str | None = None,
):
    return ledger.create_run(
        task_text=task_text,
        classification={"category": category, "risk": "safe_public", "source": "yonerai_cli"},
        route_decision={"route": route, "mode": "public_cli", "network_required": False},
        provider_decision={
            "provider_id": provider_id,
            "provider_available": provider_available,
            "live_call_performed": False,
        },
        approval_required=False,
        disabled_reason=disabled_reason,
    )


def _optional_bool_status(value: object) -> str:
    if value is True:
        return "ok"
    if value is False:
        return "warn"
    return "fail"


def _build_search_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.search import MockSearchAdapter, SearchRequest, build_live_search_disabled_boundary
        from ora_core.execution.ledger import build_run_ledger_from_env
    except Exception as exc:
        raise CliError("search adapter is unavailable.", exit_code=1) from exc
    ledger = build_run_ledger_from_env(args.ledger_path)
    ledger_status = _ledger_status(args.ledger_path)
    if args.search_mode != "mock":
        query = _safe_prompt_from_args(args.query)
        live_boundary = build_live_search_disabled_boundary(query)
        run = _start_cli_boundary_run(
            ledger,
            task_text=f"search live {query}",
            category="web_search_boundary",
            route="live_search_disabled_boundary",
            provider_id="live-search",
            provider_available=False,
            disabled_reason=live_boundary["reason"],
        )
        ledger.append_event(run.run_id, "live_search_boundary", "blocked", live_boundary["reason"])
        run = ledger.fail_run(run.run_id, error_summary=live_boundary["message"], blocked=True)
        return {
            "schema_version": "yonerai-search/v1",
            "ok": False,
            "adapter": args.search_mode,
            "query": query,
            "run": run.to_public_dict(),
            "ledger": ledger_status,
            "execution_performed": False,
            "network_performed": False,
            "live_boundary": live_boundary,
            "error": {"code": "search_live_disabled", "message": "live search is not implemented in this public alpha slice"},
            "results": [],
        }
    query = _prompt_from_args(args.query)
    run = _start_cli_boundary_run(
        ledger,
        task_text=f"search mock {query}",
        category="mock_web_search",
        route="mock_search_adapter",
        provider_id="mock-search",
        provider_available=True,
    )
    results = [result.to_public_dict() for result in MockSearchAdapter().search(SearchRequest(query=query))]
    ledger.append_event(run.run_id, "mock_search_results", "ok", f"result_count={len(results)}")
    run = ledger.complete_run(run.run_id, result_summary=f"mock search returned {len(results)} results")
    return {
        "schema_version": "yonerai-search/v1",
        "ok": True,
        "adapter": "mock",
        "run": run.to_public_dict(),
        "ledger": ledger_status,
        "execution_performed": False,
        "network_performed": False,
        "query": query,
        "results": results,
    }


def _print_search_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    if not report["ok"]:
        boundary = report.get("live_boundary") or {}
        run = report.get("run") or {}
        reason = str(boundary.get("reason") or "unknown")
        reason_status = "fail" if reason == "unknown" else "warn"
        message = str(boundary.get("message") or report.get("error", {}).get("message") or "no message")
        actions = ", ".join(boundary.get("actions_not_performed") or ())
        print(
            render_report(
                "YonerAI search",
                (
                    CliSection(
                        "Live search boundary",
                        (
                            CliRow("run_id", run.get("run_id", "unknown"), "warn"),
                            CliRow("run_status", run.get("status", "blocked"), "warn"),
                            CliRow("status", boundary.get("status", "disabled"), "warn"),
                            CliRow("reason", reason, reason_status),
                            CliRow("message", message, reason_status),
                            CliRow("network_performed", report.get("network_performed", False), "ok"),
                            CliRow("actions_not_performed", actions or "no network request", "ok"),
                        ),
                    ),
                ),
                color=color,
            )
        )
        return
    run = report.get("run") or {}
    rows = tuple(CliRow(result["title"], result["snippet"], "ok") for result in report["results"])
    print(
        render_report(
            "YonerAI search",
            (
                CliSection(
                    "Run",
                    (
                        CliRow("run_id", run.get("run_id", "unknown"), "ok"),
                        CliRow("run_status", run.get("status", "completed"), "ok"),
                    ),
                ),
                CliSection("Mock results", rows),
            ),
            color=color,
        )
    )


def _safe_prompt_from_args(parts: list[str] | tuple[str, ...]) -> str:
    return " ".join(" ".join(str(part or "").split()) for part in parts).strip()


def _build_discord_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.discord_gateway import SyntheticDiscordGatewayAdapter
        from ora_core.execution.ledger import build_run_ledger_from_env
    except Exception as exc:
        raise CliError("Discord gateway adapter is unavailable.", exit_code=1) from exc
    prompt = _prompt_from_args(args.message)
    ledger = build_run_ledger_from_env(args.ledger_path)
    ledger_status = _ledger_status(args.ledger_path)
    run = _start_cli_boundary_run(
        ledger,
        task_text=f"discord synthetic {prompt}",
        category="synthetic_discord_gateway",
        route="synthetic_discord_gateway",
        provider_id="synthetic-discord-gateway",
        provider_available=True,
    )
    result = SyntheticDiscordGatewayAdapter().handle_mention(prompt)
    report = result.to_public_dict()
    ledger.append_event(run.run_id, "synthetic_discord_gateway", "ok", f"progress_events={report['progress_events']}")
    run = ledger.complete_run(run.run_id, result_summary="synthetic Discord gateway completed")
    report["run"] = run.to_public_dict()
    report["ledger"] = ledger_status
    return report


def _print_discord_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    rows = (
        CliRow("run_id", report.get("run", {}).get("run_id", "unknown"), "ok"),
        CliRow("run_status", report.get("run", {}).get("status", "completed"), "ok"),
        CliRow("adapter", report["adapter"], "ok" if report["ok"] else "fail"),
        CliRow("synthetic", report["synthetic"], "ok" if report["synthetic"] else "fail"),
        CliRow("live_discord", report["live_discord"], "fail" if report["live_discord"] else "ok"),
        CliRow("token_required", report["token_required"], "fail" if report["token_required"] else "ok"),
        CliRow("final_once", report["final_once"], "ok" if report["final_once"] else "fail"),
        CliRow("progress_events", report["progress_events"], "ok"),
    )
    print(render_report("YonerAI Discord gateway", (CliSection("Synthetic adapter", rows),), color=color))


def _build_install_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from yonerai_cli.install_planner import (
            build_install_plan,
            build_install_plan_from_default,
            build_windows_install_plan,
            build_windows_install_plan_from_default,
        )
    except Exception as exc:
        raise CliError("Install planner is unavailable.", exit_code=1) from exc
    try:
        if args.install_command == "plan":
            if args.manifest:
                return build_install_plan(args.manifest)
            return build_install_plan_from_default(_repo_root())
        if args.manifest:
            return build_windows_install_plan(args.manifest)
        return build_windows_install_plan_from_default(_repo_root())
    except ManifestError as exc:
        raise CliError(str(exc), exit_code=2) from exc


def _build_update_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        from yonerai_cli.install_planner import build_update_plan, build_update_plan_from_default
    except Exception as exc:
        raise CliError("Update planner is unavailable.", exit_code=1) from exc
    current_version = _read_repo_version() or __version__
    try:
        if args.manifest:
            return build_update_plan(args.manifest, current_version=current_version)
        return build_update_plan_from_default(_repo_root(), current_version=current_version)
    except ManifestError as exc:
        raise CliError(str(exc), exit_code=2) from exc


def _print_install_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    manifest = report["manifest"]
    non_actions = report["non_actions"]
    errors = tuple(CliRow("error", error, "fail") for error in manifest["errors"])
    sections = (
        CliSection(
            "Dry-run plan",
            (
                CliRow("dry_run", report["dry_run"], "ok" if report["dry_run"] else "fail"),
                CliRow("target_category", report["target_category"], "ok"),
                CliRow("manifest_contract_valid", manifest["contract_valid"], "ok" if manifest["contract_valid"] else "fail"),
                CliRow("install_ready", manifest["install_ready"], "ok" if manifest["install_ready"] else "warn"),
                CliRow("artifact_count", manifest["artifact_count"], "ok" if manifest["artifact_count"] else "fail"),
            ),
        ),
        CliSection(
            "Signature",
            (
                CliRow("signature_state", manifest["signature_state"], "ok" if manifest["signature_state"] == "signed" else "warn"),
                CliRow("signature_verified", manifest["signature_verified"], "ok" if manifest["signature_verified"] else "warn"),
                CliRow(
                    "placeholder_non_production",
                    manifest["placeholder_non_production"],
                    "warn" if manifest["placeholder_non_production"] else "ok",
                ),
                CliRow(
                    "verification_required_before_real_install",
                    manifest["verification_required_before_real_install"],
                    "warn" if manifest["verification_required_before_real_install"] else "ok",
                ),
            ),
        ),
        CliSection(
            "Non-actions",
            tuple(CliRow(name, value, "ok" if value else "fail") for name, value in non_actions.items()),
        ),
        CliSection(
            "Execution boundary",
            (
                CliRow("download_performed", report["download_performed"], "fail" if report["download_performed"] else "ok"),
                CliRow("install_performed", report["install_performed"], "fail" if report["install_performed"] else "ok"),
                CliRow("path_mutation", report["path_mutation"], "fail" if report["path_mutation"] else "ok"),
                CliRow("remote_code_executed", report["remote_code_executed"], "fail" if report["remote_code_executed"] else "ok"),
            ),
        ),
    )
    if errors:
        sections = (*sections, CliSection("Errors", errors))
    print(render_report("YonerAI install plan", sections, color=color))


def _update_version_comparison_level(report: dict[str, Any]) -> str:
    comparison = report["version_comparison"]
    if comparison == "target_older":
        return "warn"
    if comparison == "unknown":
        return "fail"
    return "ok" if report["ok"] else "warn"


def _print_update_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    manifest = report["manifest"]
    signature = report["signature_status"]
    non_actions = report["non_actions"]
    selected = report["selected_artifact"] or {}
    errors = tuple(CliRow("error", error, "fail") for error in manifest["errors"])
    warnings = tuple(CliRow("warning", warning, "warn") for warning in report["warnings"])
    sections = (
        CliSection(
            "Dry-run update plan",
            (
                CliRow("dry_run", report["dry_run"], "ok" if report["dry_run"] else "fail"),
                CliRow("current_version", report["current_version"], "ok"),
                CliRow("target_version", report["target_version"], "ok" if report["target_version"] else "fail"),
                CliRow("update_available", report["update_available"], "warn" if report["update_available"] else "ok"),
                CliRow("version_comparison", report["version_comparison"], _update_version_comparison_level(report)),
                CliRow("rollback_plan_available", report["rollback_plan_available"], "ok" if report["rollback_plan_available"] else "warn"),
            ),
        ),
        CliSection(
            "Manifest",
            (
                CliRow("contract_valid", manifest["contract_valid"], "ok" if manifest["contract_valid"] else "fail"),
                CliRow("install_ready", manifest["install_ready"], "ok" if manifest["install_ready"] else "warn"),
                CliRow("artifact_count", manifest["artifact_count"], "ok" if manifest["artifact_count"] else "fail"),
                CliRow("selected_artifact", selected.get("artifact_id", "none"), "ok" if selected else "fail"),
                CliRow("sha256_present", report["sha256_present"], "ok" if report["sha256_present"] else "fail"),
            ),
        ),
        CliSection(
            "Signature",
            (
                CliRow("signature_state", signature["state"], "ok" if signature["state"] == "signed" else "warn"),
                CliRow("signature_verified", signature["verified"], "ok" if signature["verified"] else "warn"),
                CliRow(
                    "placeholder_non_production",
                    signature["placeholder_non_production"],
                    "warn" if signature["placeholder_non_production"] else "ok",
                ),
                CliRow(
                    "verification_required_before_real_update",
                    signature["verification_required_before_real_update"],
                    "warn" if signature["verification_required_before_real_update"] else "ok",
                ),
            ),
        ),
        CliSection(
            "Non-actions",
            tuple(CliRow(name, value, "ok" if value else "fail") for name, value in non_actions.items()),
        ),
        CliSection(
            "Execution boundary",
            (
                CliRow("download_performed", report["download_performed"], "fail" if report["download_performed"] else "ok"),
                CliRow("install_performed", report["install_performed"], "fail" if report["install_performed"] else "ok"),
                CliRow("path_mutation", report["path_mutation"], "fail" if report["path_mutation"] else "ok"),
                CliRow("remote_code_executed", report["remote_code_executed"], "fail" if report["remote_code_executed"] else "ok"),
            ),
        ),
    )
    if warnings:
        sections = (*sections, CliSection("Warnings", warnings))
    if errors:
        sections = (*sections, CliSection("Errors", errors))
    print(render_report("YonerAI update plan", sections, color=color))


def _build_ops_plan_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.ops import plan_operation
    except Exception as exc:
        raise CliError("SafeShell planner is unavailable.", exit_code=1) from exc
    plan = plan_operation(args.operation)
    return {
        "schema_version": "yonerai-ops-plan/v1",
        "ok": plan.status == "planned",
        "plan": plan.to_public_dict(),
        "shell_executed": False,
        "mutation_performed": False,
    }


def _print_ops_plan_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    plan = report["plan"]
    rows = (
        CliRow("operation", plan["operation_id"], "ok" if report["ok"] else "fail"),
        CliRow("status", plan["status"], "ok" if report["ok"] else "fail"),
        CliRow("command_preview", " ".join(plan["command_preview"]) if plan["command_preview"] else "none", "ok" if report["ok"] else "warn"),
        CliRow("approval_required", plan["approval_required"], "warn" if plan["approval_required"] else "ok"),
        CliRow("shell_executed", report["shell_executed"], "fail" if report["shell_executed"] else "ok"),
    )
    print(render_report("YonerAI ops plan", (CliSection("SafeShell", rows),), color=color))


def _build_memory_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.memory import LocalMemoryStore
    except Exception as exc:
        raise CliError("local memory store is unavailable.", exit_code=1) from exc
    if not args.store:
        raise CliError("--store is required for explicit local memory v0.1.", exit_code=2)
    store = LocalMemoryStore(args.store)
    if args.memory_command == "add":
        if not args.confirm_local:
            raise CliError("memory add requires --confirm-local.", exit_code=2)
        record = store.add(_prompt_from_args(args.text), tags=tuple(args.tag or ()))
        return {
            "schema_version": "yonerai-local-memory-cli/v0.1",
            "ok": True,
            "operation": "add",
            "record": record.to_public_dict(),
            "cloud_synced": False,
            "raw_prompt_persisted": False,
        }
    if args.memory_command == "list":
        records = [record.to_public_dict() for record in store.list()]
        return {
            "schema_version": "yonerai-local-memory-cli/v0.1",
            "ok": True,
            "operation": "list",
            "records": records,
            "count": len(records),
            "cloud_synced": False,
        }
    if args.memory_command == "delete":
        deleted = store.delete(args.memory_id)
        return {
            "schema_version": "yonerai-local-memory-cli/v0.1",
            "ok": deleted,
            "operation": "delete",
            "memory_id": args.memory_id,
            "deleted": deleted,
            "cloud_synced": False,
        }
    if args.memory_command == "export":
        return store.export() | {"operation": "export"}
    raise CliError("unknown memory command", exit_code=2)


def _print_memory_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    if report.get("operation") == "list":
        rows = tuple(CliRow(record["memory_id"], record["text"], "ok") for record in report["records"]) or (
            CliRow("records", "none", "warn"),
        )
        print(render_report("YonerAI local memory", (CliSection("Records", rows),), color=color))
        return
    rows = (
        CliRow("operation", report.get("operation", "unknown"), "ok" if report.get("ok") else "fail"),
        CliRow("ok", report.get("ok"), "ok" if report.get("ok") else "fail"),
        CliRow("cloud_synced", report.get("cloud_synced", False), "fail" if report.get("cloud_synced") else "ok"),
    )
    print(render_report("YonerAI local memory", (CliSection("Local-only", rows),), color=color))


def _print_runs_list_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    ledger = report.get("ledger") or {}
    file_backed = ledger.get("file_backed", "unknown")
    if lang == "ja":
        title = "YonerAI 実行履歴"
        ledger_title = "履歴"
        recent_title = "最近の実行"
        empty_text = "選択したlocal ledgerには履歴がありません"
        path_label = "出力にpathを保存"
        guidance = '履歴を残すには: yonerai ask "hello" --auto --ledger .yonerai-runs.jsonl --json'
    else:
        title = "YonerAI runs"
        ledger_title = "Ledger"
        recent_title = "Recent"
        empty_text = "none in selected local ledger"
        path_label = "path_persisted_in_output"
        guidance = 'To keep history: yonerai ask "hello" --auto --ledger .yonerai-runs.jsonl --json'
    rows = tuple(
        CliRow(
            str(run["run_id"]),
            f"{run['status']} {run['provider_decision'].get('provider_id', 'unknown')} {run['task_summary']}",
            "ok" if run["status"] == "completed" else "warn",
        )
        for run in report["runs"]
    ) or (CliRow("runs", empty_text, "warn"),)
    if not ledger.get("file_backed"):
        rows = rows + (CliRow("next", guidance, "warn"),)
    print(
        render_report(
            title,
            (
                CliSection(
                    ledger_title,
                    (
                        CliRow("file_backed", file_backed, _optional_bool_status(file_backed)),
                        CliRow("local_only", ledger.get("local_only", True), "ok"),
                        CliRow(
                            path_label,
                            ledger.get("path_persisted_in_output", False),
                            "fail" if ledger.get("path_persisted_in_output") else "ok",
                        ),
                    ),
                ),
                CliSection(recent_title, rows),
            ),
            color=color,
        )
    )


def _print_run_show_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> None:
    title = "YonerAI 実行" if lang == "ja" else "YonerAI run"
    if not report["ok"]:
        error_title = "エラー" if lang == "ja" else "Error"
        print(render_report(title, (CliSection(error_title, (CliRow("error", report["error"]["message"], "fail"),)),), color=color))
        return
    run = report["run"]
    ledger = report.get("ledger") or {}
    file_backed = ledger.get("file_backed", "unknown")
    events = tuple(CliRow(event["name"], f"{event['status']} {event['summary']}", "ok" if event["status"] == "ok" else "warn") for event in run["events"])
    progress_events = tuple(event for event in run["events"] if str(event.get("name") or "").startswith("task_progress_"))
    if lang == "ja":
        progress_rows = tuple(
            CliRow(
                _progress_step_label_ja(str(event.get("name") or "").removeprefix("task_progress_")),
                f"{_progress_state_label_ja(event.get('status'))}: "
                f"{_progress_summary_ja(str(event.get('name') or '').removeprefix('task_progress_'), event.get('summary'))}",
                _progress_status_for_cli(event.get("status")),
            )
            for event in progress_events
        )
        agent_rows = _run_agent_rows_ja(run)
    else:
        progress_rows = tuple(
            CliRow(
                str(event.get("name") or "").removeprefix("task_progress_"),
                f"{event.get('status')}: {event.get('summary')}",
                _progress_status_for_cli(event.get("status")),
            )
            for event in progress_events
        )
        agent_rows = _run_agent_rows_en(run)
    sections = (
        CliSection(
            "履歴" if lang == "ja" else "Ledger",
            (
                CliRow("file_backed", file_backed, _optional_bool_status(file_backed)),
                CliRow("local_only", ledger.get("local_only", True), "ok"),
                CliRow("raw_prompt_persisted", ledger.get("raw_prompt_persisted", False), "fail" if ledger.get("raw_prompt_persisted") else "ok"),
            ),
        ),
        CliSection(
            "実行" if lang == "ja" else "Run",
            (
                CliRow("run_id", run["run_id"], "ok"),
                CliRow("status", _run_status_ja(run["status"]) if lang == "ja" else run["status"], "ok" if run["status"] == "completed" else "warn"),
                CliRow("task_summary", run["task_summary"], "ok"),
                CliRow("provider", run["provider_decision"].get("provider_id", "unknown"), "ok"),
            ),
        ),
        CliSection("進行状況" if lang == "ja" else "Task progress", progress_rows or (CliRow("progress", "not recorded", "warn"),)),
        CliSection("エージェント計画" if lang == "ja" else "Agent plan", agent_rows),
        CliSection("イベント" if lang == "ja" else "Events", events or (CliRow("events", "none", "warn"),)),
    )
    print(render_report(title, sections, color=color))


def _run_agent_rows_ja(run: dict[str, Any]) -> tuple[CliRow, ...]:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    reviewer_event = next((event for event in events if isinstance(event, dict) and event.get("name") == "auto_reviewer_plan"), None)
    return (
        CliRow("レビュー計画", reviewer_event.get("summary") if isinstance(reviewer_event, dict) else "記録なし", "ok" if reviewer_event else "skipped"),
        CliRow("実エージェント起動", "なし（計画表示のみ）", "ok"),
    )


def _run_agent_rows_en(run: dict[str, Any]) -> tuple[CliRow, ...]:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    reviewer_event = next((event for event in events if isinstance(event, dict) and event.get("name") == "auto_reviewer_plan"), None)
    return (
        CliRow("reviewer_plan", reviewer_event.get("summary") if isinstance(reviewer_event, dict) else "not recorded", "ok" if reviewer_event else "skipped"),
        CliRow("subagents_started", False, "ok"),
    )


def _build_config_report_for_cli(args: argparse.Namespace) -> dict[str, Any]:
    try:
        config = load_cli_config(args.config_path)
        config_path = Path(args.config_path).expanduser() if args.config_path else default_config_path()
        return build_config_report(config, exists=config_path.exists())
    except ConfigError as exc:
        raise CliError(str(exc), exit_code=2) from exc


def _set_config_report_for_cli(args: argparse.Namespace) -> dict[str, Any]:
    try:
        config = set_cli_config_value(args.config_key, args.config_value, args.config_path)
        return build_config_report(config, exists=True) | {
            "operation": "set",
            "changed_key": args.config_key,
        }
    except ConfigError as exc:
        raise CliError(str(exc), exit_code=2) from exc


def _print_config_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> None:
    config = report.get("config") if isinstance(report.get("config"), dict) else {}
    if lang == "ja":
        title = "YonerAI 設定"
        settings_title = "設定"
        boundary_title = "境界"
        rows = (
            CliRow("language", config.get("language") or "ja", "ok"),
            CliRow("provider", config.get("provider_preference"), "ok"),
            CliRow("approval", config.get("approval_mode"), "ok"),
            CliRow("file_access", config.get("file_access_mode"), "ok"),
            CliRow("live_provider", config.get("live_provider_enabled"), "warn" if config.get("live_provider_enabled") else "ok"),
            CliRow("network", config.get("network_enabled"), "warn" if config.get("network_enabled") else "ok"),
            CliRow("tools", config.get("tools_mode"), "ok"),
            CliRow("ledger", config.get("ledger_enabled"), "ok" if config.get("ledger_enabled") else "warn"),
        )
        boundary_rows = (
            CliRow("secrets_supported", report.get("secrets_supported"), "fail" if report.get("secrets_supported") else "ok"),
            CliRow("path_persisted_in_output", report.get("path_persisted_in_output"), "fail" if report.get("path_persisted_in_output") else "ok"),
        )
    else:
        title = "YonerAI config"
        settings_title = "Settings"
        boundary_title = "Boundary"
        rows = (
            CliRow("language", config.get("language") or "ja", "ok"),
            CliRow("provider", config.get("provider_preference"), "ok"),
            CliRow("approval", config.get("approval_mode"), "ok"),
            CliRow("file_access", config.get("file_access_mode"), "ok"),
            CliRow("live_provider", config.get("live_provider_enabled"), "warn" if config.get("live_provider_enabled") else "ok"),
            CliRow("network", config.get("network_enabled"), "warn" if config.get("network_enabled") else "ok"),
            CliRow("tools", config.get("tools_mode"), "ok"),
            CliRow("ledger", config.get("ledger_enabled"), "ok" if config.get("ledger_enabled") else "warn"),
        )
        boundary_rows = (
            CliRow("secrets_supported", report.get("secrets_supported"), "fail" if report.get("secrets_supported") else "ok"),
            CliRow("path_persisted_in_output", report.get("path_persisted_in_output"), "fail" if report.get("path_persisted_in_output") else "ok"),
        )
    print(render_report(title, (CliSection(settings_title, rows), CliSection(boundary_title, boundary_rows)), color=color))


def _interactive_callbacks():
    from yonerai_cli.interactive import InteractiveCallbacks

    return InteractiveCallbacks(
        providers=_build_providers_report,
        ask_auto=_interactive_ask_auto,
        runs_list=_interactive_runs_list,
        runs_show=_interactive_runs_show,
    )


def _interactive_ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, _lang: str) -> dict[str, Any]:
    args = argparse.Namespace(
        task=[task],
        provider=provider,
        live=live,
        ledger_path=ledger_path,
        file=None,
        workspace=None,
        file_max_bytes=65536,
    )
    return _execute_auto_ask_report(args)


def _interactive_runs_list(ledger_path: str | None, limit: int, _lang: str) -> dict[str, Any]:
    args = argparse.Namespace(runs_command="list", ledger_path=ledger_path, limit=limit)
    return _build_runs_report(args)


def _interactive_runs_show(run_id: str, ledger_path: str | None, _lang: str) -> dict[str, Any]:
    args = argparse.Namespace(runs_command="show", ledger_path=ledger_path, run_id=run_id, limit=1)
    return _build_runs_report(args)


def _run_interactive_chat(args: argparse.Namespace) -> int:
    from yonerai_cli.interactive import InteractiveOptions, run_interactive_cli

    options = InteractiveOptions(
        config_path=args.config_path,
        lang=args.lang,
        provider=args.provider,
        live=args.live,
        ledger_path=args.ledger_path,
        script=args.script,
        color=args.color,
    )
    try:
        return run_interactive_cli(options, _interactive_callbacks())
    except ConfigError as exc:
        raise CliError(str(exc), exit_code=2) from exc


def _prompt_from_args(parts: list[str]) -> str:
    prompt = " ".join(parts).strip()
    if not prompt:
        raise CliError("prompt must not be empty.")
    return prompt


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--api-origin",
        default=DEFAULT_API_ORIGIN,
        help=f"Loopback Core API origin. Default: {DEFAULT_API_ORIGIN}",
    )

    parser = argparse.ArgumentParser(
        prog="yonerai",
        description=(
            "YonerAI CLI Local Runtime. "
            "Includes an interactive terminal shell, safe provider readiness, auto routing, and diagnostics. "
            "It is not a deploy tool or Official Managed Cloud runtime."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=False)

    chat = subcommands.add_parser("chat", aliases=["interactive"], help="Start the Japanese-first interactive YonerAI terminal.")
    chat.add_argument("--config-path", help="Optional local CLI config path. Defaults to the user config directory.")
    chat.add_argument("--lang", choices=LANG_CHOICES, help="Interactive language. Defaults to saved config or first-launch selection.")
    chat.add_argument("--provider", choices=PLAN_PROVIDER_CHOICES, help="Provider preference for chat messages. Defaults to saved config.")
    chat.add_argument("--live", action="store_true", help="Explicitly allow configured live provider/local LLM execution.")
    chat.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path.")
    chat.add_argument("--script", action="store_true", help="Read chat lines from stdin even when stdin is not a TTY.")
    chat.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Output color mode. Default: auto.")

    config = subcommands.add_parser("config", help="Show or update local YonerAI CLI preferences. No secrets are stored.")
    config_subcommands = config.add_subparsers(dest="config_command", required=True)
    config_show = config_subcommands.add_parser("show", help="Show local CLI preferences without printing the config path.")
    config_show.add_argument("--config-path", help="Optional local CLI config path.")
    config_show_output = config_show.add_mutually_exclusive_group()
    config_show_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    config_show_output.add_argument("--pretty", action="store_true", help="Print a readable settings summary.")
    config_show.add_argument("--lang", choices=LANG_CHOICES, default="ja", help="Pretty output language. Default: ja.")
    config_show.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    config_set = config_subcommands.add_parser("set", help="Set one local CLI preference. Provider keys are not accepted.")
    config_set.add_argument("config_key", choices=("language", "lang", "provider", "provider_preference", "approval", "approval_mode", "file_access", "file_access_mode", "live_provider", "network", "ledger", "history"))
    config_set.add_argument("config_value")
    config_set.add_argument("--config-path", help="Optional local CLI config path.")
    config_set_output = config_set.add_mutually_exclusive_group()
    config_set_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    config_set_output.add_argument("--pretty", action="store_true", help="Print a readable settings summary.")
    config_set.add_argument("--lang", choices=LANG_CHOICES, default="ja", help="Pretty output language. Default: ja.")
    config_set.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    subcommands.add_parser("health", parents=[shared], help="Check the local Core API health endpoint.")

    smoke = subcommands.add_parser("smoke", help="Run the credential-free in-process public MVP smoke.")
    smoke_output = smoke.add_mutually_exclusive_group()
    smoke_output.add_argument("--json", action="store_true", help="Print compact machine-readable JSON.")
    smoke_output.add_argument("--pretty", action="store_true", help="Print a detailed human-readable summary.")

    demo = subcommands.add_parser(
        "demo",
        aliases=["quickstart"],
        help="Run a credential-free public YonerAI demo after clone.",
    )
    demo_output = demo.add_mutually_exclusive_group()
    demo_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    demo_output.add_argument("--pretty", action="store_true", help="Print a readable sectioned demo summary.")

    start = subcommands.add_parser("start", help="Guide the first local YonerAI run for non-engineers.")
    start.add_argument("--guided", action="store_true", help="Show copyable next actions for the first five minutes.")
    start_output = start.add_mutually_exclusive_group()
    start_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    start_output.add_argument("--pretty", action="store_true", help="Print a readable first-run guide.")
    start.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    start.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    doctor = subcommands.add_parser("doctor", help="Run offline, non-mutating setup diagnostics.")
    doctor_output = doctor.add_mutually_exclusive_group()
    doctor_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    doctor_output.add_argument("--pretty", action="store_true", help="Print a readable diagnostic summary.")
    doctor.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    doctor.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    providers = subcommands.add_parser("providers", help="Show provider readiness and safe setup guidance.")
    providers_output = providers.add_mutually_exclusive_group()
    providers_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    providers_output.add_argument("--pretty", action="store_true", help="Print readable provider setup guidance.")
    providers.add_argument("--lang", choices=LANG_CHOICES, default="ja", help="Pretty output language. Default: ja.")
    providers.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    status = subcommands.add_parser("status", help="Print offline public demo and installer readiness status.")
    status_output = status.add_mutually_exclusive_group()
    status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    status_output.add_argument("--pretty", action="store_true", help="Print a readable status summary.")
    status.add_argument("--source", choices=("local", "fixture"), default="local", help="Status source. Default: local.")
    status.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    status.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    manifest = subcommands.add_parser("manifest", help="Validate local YonerAI release manifests without installing.")
    manifest_subcommands = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_verify = manifest_subcommands.add_parser("verify", help="Validate a local release manifest file.")
    manifest_verify.add_argument("manifest_path", help="Local manifest JSON path. Remote URLs are rejected.")
    manifest_verify.add_argument(
        "--artifact",
        action="append",
        help="Optional ARTIFACT_ID=LOCAL_FILE mapping for local SHA256/size verification. Repeatable.",
    )
    manifest_verify.add_argument(
        "--test-trust-fixture",
        help="Local non-production test trust fixture for signed manifest verification. Remote URLs are rejected.",
    )
    manifest_verify.add_argument("--require-signed", action="store_true", help="Reject manifests without verified signatures.")
    manifest_output = manifest_verify.add_mutually_exclusive_group()
    manifest_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    manifest_output.add_argument("--pretty", action="store_true", help="Print a readable verification summary.")
    manifest_verify.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    manifest_verify.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    route = subcommands.add_parser("route", help="Preview safe YonerAI task routing without executing it.")
    route_subcommands = route.add_subparsers(dest="route_command", required=True)
    route_preview = route_subcommands.add_parser("preview", help="Preview cloud/local/hybrid/disabled routing.")
    route_preview.add_argument("task", nargs="+")
    route_preview_output = route_preview.add_mutually_exclusive_group()
    route_preview_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    route_preview_output.add_argument("--pretty", action="store_true", help="Print a readable route preview.")
    route_preview.add_argument(
        "--mode",
        choices=["official_managed_cloud", "official_hybrid_private", "full_private_self_host"],
        default="official_managed_cloud",
    )
    route_preview.add_argument("--capability", help="Optional explicit capability name.")
    route_preview.add_argument("--risk-hint", help="Optional public-safe operation class hint.")
    route_preview.add_argument("--has-local-node", action="store_true", help="Preview as if a user Local Node is available.")
    route_preview.add_argument(
        "--use-local-node-fixture",
        action="store_true",
        help="Use the public-safe Hybrid Wire v0.3 Local Node dev fixture for route preview.",
    )
    route_preview.add_argument(
        "--local-node-state",
        choices=[
            "missing",
            "present_unverified",
            "present_verified",
            "expired",
            "invalid_signature",
            "wrong_audience",
        ],
        help="Optional test-only Local Node verification state for route preview.",
    )
    route_preview.add_argument(
        "--local-node-capability",
        action="append",
        help="Optional declared capability for a verified test Local Node manifest. Repeatable.",
    )
    route_preview.add_argument(
        "--require-enrolled-verified-session",
        action="store_true",
        help="Require a public-safe enrolled verified Local Node session state for local work previews.",
    )
    route_preview.add_argument(
        "--session-state",
        choices=[
            "missing",
            "unenrolled",
            "pairing_pending",
            "enrolled_unverified",
            "enrolled_verified",
            "expired",
            "revoked",
            "wrong_audience",
        ],
        help="Optional public-safe Local Node enrollment/session state for route preview.",
    )
    route_preview.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    node = subcommands.add_parser("node", help="Inspect public-safe Hybrid Wire Local Node fixtures.")
    node_subcommands = node.add_subparsers(dest="node_command", required=True)
    node_status = node_subcommands.add_parser("status", help="Show public-safe Local Node fixture status.")
    node_status_output = node_status.add_mutually_exclusive_group()
    node_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    node_status_output.add_argument("--pretty", action="store_true", help="Print a readable Local Node status.")
    node_status.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    node_pair = node_subcommands.add_parser("pair", help="Preview Local Node pairing without performing it.")
    node_pair.add_argument("--dry-run", action="store_true", help="Required; do not pair or contact any service.")
    node_pair_output = node_pair.add_mutually_exclusive_group()
    node_pair_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    node_pair_output.add_argument("--pretty", action="store_true", help="Print a readable Local Node pairing preview.")
    node_pair.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    relay = subcommands.add_parser("relay", help="Inspect public-safe Hybrid Relay local-dev fixtures.")
    relay_subcommands = relay.add_subparsers(dest="relay_command", required=True)
    relay_status = relay_subcommands.add_parser("status", help="Show local-dev Relay fixture status without starting it.")
    relay_status_output = relay_status.add_mutually_exclusive_group()
    relay_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    relay_status_output.add_argument("--pretty", action="store_true", help="Print a readable Relay local-dev status.")
    relay_status.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    oracle = subcommands.add_parser("oracle", help="Run public-safe local-dev Oracle stub fixtures.")
    oracle_subcommands = oracle.add_subparsers(dest="oracle_command", required=True)
    oracle_status = oracle_subcommands.add_parser("status", help="Show Oracle stub availability without contacting cloud.")
    oracle_status_output = oracle_status.add_mutually_exclusive_group()
    oracle_status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    oracle_status_output.add_argument("--pretty", action="store_true", help="Print a readable Oracle stub status.")
    oracle_status.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    oracle_queue = oracle_subcommands.add_parser("queue", help="Queue one safe cloud-candidate task into the local-dev Oracle stub.")
    oracle_queue.add_argument("task", nargs="*", help="Public task text. Defaults to a public reasoning fixture.")
    oracle_queue.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    oracle_queue_output = oracle_queue.add_mutually_exclusive_group()
    oracle_queue_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    oracle_queue_output.add_argument("--pretty", action="store_true", help="Print a readable Oracle stub queue result.")
    oracle_queue.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    hybrid = subcommands.add_parser("hybrid", help="Run public-safe local-dev Hybrid execution slices.")
    hybrid_subcommands = hybrid.add_subparsers(dest="hybrid_command", required=True)
    hybrid_run = hybrid_subcommands.add_parser(
        "run",
        help="Run route, Local Node relay fixture, provider execution, and Oracle stub envelope locally.",
    )
    hybrid_run.add_argument("task", nargs="*", help="Public task text. Defaults to a safe Hybrid slice fixture.")
    hybrid_run.add_argument("--provider", choices=("mock", "local"), default="mock", help="Provider to execute locally. Default: mock.")
    hybrid_run.add_argument("--live", action="store_true", help="Allow explicit loopback-only local provider execution.")
    hybrid_run.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    hybrid_run_output = hybrid_run.add_mutually_exclusive_group()
    hybrid_run_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    hybrid_run_output.add_argument("--pretty", action="store_true", help="Print a readable Hybrid execution report.")
    hybrid_run.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    plan = subcommands.add_parser("plan", help="Preview classification, route, provider, and approval without executing.")
    plan.add_argument("task", nargs="+")
    plan_output = plan.add_mutually_exclusive_group()
    plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    plan_output.add_argument("--pretty", action="store_true", help="Print a readable execution plan summary.")
    plan.add_argument("--provider", choices=PLAN_PROVIDER_CHOICES, default="auto", help="Provider preference. Default: auto.")
    plan.add_argument("--mode", choices=PLAN_MODE_CHOICES, default="managed-contract", help="Planning mode. Default: managed-contract.")
    plan.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    ask = subcommands.add_parser("ask", help="Execute a safe YonerAI ask path or preview it with --dry-run.")
    ask.add_argument("task", nargs="+")
    ask.add_argument("--auto", action="store_true", help="Use the auto runtime router: classify, route, execute safe paths, and record run_id.")
    ask.add_argument("--dry-run", action="store_true", help="Preview only; no provider call is made.")
    ask.add_argument("--live", action="store_true", help="Allow explicitly gated local or external live provider execution.")
    ask.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    ask.add_argument("--file", help="Optional workspace-local UTF-8 text file to summarize or use as ask context.")
    ask.add_argument("--workspace", help="Required workspace root when --file is used.")
    ask.add_argument("--file-max-bytes", type=int, default=65536, help="Maximum file bytes to read. Default: 65536.")
    ask_output = ask.add_mutually_exclusive_group()
    ask_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    ask_output.add_argument("--pretty", action="store_true", help="Print a readable execution summary.")
    ask.add_argument("--provider", choices=PLAN_PROVIDER_CHOICES, default="auto", help="Provider preference. Default: auto.")
    ask.add_argument("--mode", choices=PLAN_MODE_CHOICES, default="self-host", help="Execution planning mode. Default: self-host.")
    ask.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    ask.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    search = subcommands.add_parser("search", help="Run deterministic mock search or report live search as disabled.")
    search.add_argument("search_mode", choices=("mock", "live"), help="Search mode. Default-safe mode is mock.")
    search.add_argument("query", nargs="+")
    search.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    search_output = search.add_mutually_exclusive_group()
    search_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    search_output.add_argument("--pretty", action="store_true", help="Print a readable search fixture summary.")
    search.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    discord = subcommands.add_parser("discord", help="Inspect public-safe Discord gateway adapter boundaries.")
    discord_subcommands = discord.add_subparsers(dest="discord_command", required=True)
    discord_synthetic = discord_subcommands.add_parser("synthetic", help="Run a synthetic Discord mention fixture.")
    discord_synthetic.add_argument("message", nargs="+")
    discord_synthetic.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    discord_synthetic_output = discord_synthetic.add_mutually_exclusive_group()
    discord_synthetic_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    discord_synthetic_output.add_argument("--pretty", action="store_true", help="Print a readable Discord adapter summary.")
    discord_synthetic.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    install = subcommands.add_parser("install", help="Plan installer actions without downloading or installing.")
    install_subcommands = install.add_subparsers(dest="install_command", required=True)
    install_plan = install_subcommands.add_parser("plan", help="Build a local manifest install dry-run plan.")
    install_plan.add_argument("--manifest", help="Local release manifest JSON path. Defaults to releases/manifest.example.json.")
    install_plan_output = install_plan.add_mutually_exclusive_group()
    install_plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    install_plan_output.add_argument("--pretty", action="store_true", help="Print a readable installer plan.")
    install_plan.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    install_plan_windows = install_subcommands.add_parser("plan-windows", help="Build a Windows installer dry-run plan.")
    install_plan_windows.add_argument("--manifest", help="Local release manifest JSON path. Defaults to releases/manifest.example.json.")
    install_plan_windows_output = install_plan_windows.add_mutually_exclusive_group()
    install_plan_windows_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    install_plan_windows_output.add_argument("--pretty", action="store_true", help="Print a readable installer plan.")
    install_plan_windows.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    update = subcommands.add_parser("update", help="Plan update actions without downloading or installing.")
    update_subcommands = update.add_subparsers(dest="update_command", required=True)
    update_plan = update_subcommands.add_parser("plan", help="Build a local manifest update dry-run plan.")
    update_plan.add_argument("--manifest", help="Local release manifest JSON path. Defaults to releases/manifest.example.json.")
    update_plan_output = update_plan.add_mutually_exclusive_group()
    update_plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    update_plan_output.add_argument("--pretty", action="store_true", help="Print a readable update plan.")
    update_plan.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    ops = subcommands.add_parser("ops", help="Plan safe diagnostic operations without arbitrary shell execution.")
    ops_subcommands = ops.add_subparsers(dest="ops_command", required=True)
    ops_plan = ops_subcommands.add_parser("plan", help="Preview a SafeShell diagnostic operation.")
    ops_plan.add_argument("operation", choices=("python-version", "git-status", "node-version"))
    ops_plan_output = ops_plan.add_mutually_exclusive_group()
    ops_plan_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    ops_plan_output.add_argument("--pretty", action="store_true", help="Print a readable operation plan.")
    ops_plan.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    memory = subcommands.add_parser("memory", help="Manage explicit opt-in local memory v0.1 records.")
    memory_subcommands = memory.add_subparsers(dest="memory_command", required=True)
    memory_add = memory_subcommands.add_parser("add", help="Add a redacted local-only memory record.")
    memory_add.add_argument("text", nargs="+")
    memory_add.add_argument("--store", required=True, help="Local JSONL memory store path.")
    memory_add.add_argument("--confirm-local", action="store_true", help="Confirm this is explicit local-only memory.")
    memory_add.add_argument("--tag", action="append", help="Optional simple tag. Repeatable.")
    memory_add_output = memory_add.add_mutually_exclusive_group()
    memory_add_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_add_output.add_argument("--pretty", action="store_true", help="Print a readable memory summary.")
    memory_add.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    memory_list = memory_subcommands.add_parser("list", help="List redacted local-only memory records.")
    memory_list.add_argument("--store", required=True, help="Local JSONL memory store path.")
    memory_list_output = memory_list.add_mutually_exclusive_group()
    memory_list_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_list_output.add_argument("--pretty", action="store_true", help="Print a readable memory list.")
    memory_list.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    memory_delete = memory_subcommands.add_parser("delete", help="Delete one local-only memory record.")
    memory_delete.add_argument("memory_id")
    memory_delete.add_argument("--store", required=True, help="Local JSONL memory store path.")
    memory_delete_output = memory_delete.add_mutually_exclusive_group()
    memory_delete_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_delete_output.add_argument("--pretty", action="store_true", help="Print a readable memory summary.")
    memory_delete.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    memory_export = memory_subcommands.add_parser("export", help="Export redacted local-only memory records.")
    memory_export.add_argument("--store", required=True, help="Local JSONL memory store path.")
    memory_export_output = memory_export.add_mutually_exclusive_group()
    memory_export_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    memory_export_output.add_argument("--pretty", action="store_true", help="Print a readable memory summary.")
    memory_export.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    runs = subcommands.add_parser("runs", help="Inspect opt-in redacted local run ledger history.")
    runs_subcommands = runs.add_subparsers(dest="runs_command", required=True)
    runs_list = runs_subcommands.add_parser("list", help="List recent runs from an opt-in ledger.")
    runs_list.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Defaults to YONERAI_RUN_LEDGER_PATH.")
    runs_list.add_argument("--limit", type=int, default=20, help="Maximum runs to show. Default: 20.")
    runs_list_output = runs_list.add_mutually_exclusive_group()
    runs_list_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    runs_list_output.add_argument("--pretty", action="store_true", help="Print a readable run list.")
    runs_list.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    runs_list.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    runs_show = runs_subcommands.add_parser("show", help="Show one run from an opt-in ledger.")
    runs_show.add_argument("run_id")
    runs_show.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path. Defaults to YONERAI_RUN_LEDGER_PATH.")
    runs_show_output = runs_show.add_mutually_exclusive_group()
    runs_show_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    runs_show_output.add_argument("--pretty", action="store_true", help="Print a readable run summary.")
    runs_show.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    runs_show.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    message = subcommands.add_parser("message", parents=[shared], help="Send a local public message smoke request.")
    message.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    message.add_argument("prompt", nargs="+")

    run = subcommands.add_parser("run", parents=[shared], help="Create a local Surface API run smoke request.")
    run.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    run.add_argument("prompt", nargs="+")

    return parser


def run(argv: list[str] | None = None) -> int:
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    if not actual_argv:
        return _run_interactive_chat(
            argparse.Namespace(
                config_path=None,
                lang=None,
                provider=None,
                live=False,
                ledger_path=None,
                script=False,
                color="auto",
            )
        )
    parser = build_parser()
    args = parser.parse_args(actual_argv)

    if args.command in {"chat", "interactive"}:
        return _run_interactive_chat(args)
    if args.command == "config":
        report = _set_config_report_for_cli(args) if args.config_command == "set" else _build_config_report_for_cli(args)
        if args.json:
            _print_json(report)
        else:
            _print_config_pretty(report, lang=args.lang, color=args.color)
        return 0
    if args.command == "health":
        _print_json(request_json("GET", args.api_origin, "/health"))
        return 0
    if args.command == "smoke":
        return _run_public_mvp_smoke(json_output=args.json, pretty=args.pretty)
    if args.command in {"demo", "quickstart"}:
        return _run_public_demo(json_output=args.json, pretty=args.pretty)
    if args.command == "start":
        report = _build_start_report(guided=args.guided)
        if args.json:
            _print_json(report)
        else:
            _print_start_pretty(report, lang=args.lang, color=args.color)
        return 0
    if args.command == "doctor":
        report = _build_doctor_report()
        if args.json:
            _print_json(report)
        else:
            _print_doctor_pretty(report, lang=args.lang, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "providers":
        report = _build_providers_report()
        if args.json:
            _print_json(report)
        else:
            _print_providers_pretty(report, lang=args.lang, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "status":
        report = _build_status_report(source=args.source)
        if args.json:
            _print_json(report)
        else:
            _print_status_pretty(report, lang=args.lang, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "manifest" and args.manifest_command == "verify":
        try:
            artifacts = parse_artifact_args(args.artifact)
            test_trust_fixture = load_test_trust_fixture(args.test_trust_fixture) if args.test_trust_fixture else None
            report = verify_manifest(
                load_manifest_file(args.manifest_path),
                artifact_paths=artifacts,
                require_signed=args.require_signed,
                test_trust_fixture=test_trust_fixture,
            )
        except ManifestError as exc:
            raise CliError(str(exc), exit_code=2) from exc
        if args.json:
            _print_json(report)
        else:
            print(format_manifest_verify_pretty(report, lang=args.lang, color=args.color))
        return 0 if report["ok"] else 1
    if args.command == "route" and args.route_command == "preview":
        report = _preview_route(args)
        if args.pretty:
            _print_route_preview_pretty(report, color=args.color)
        else:
            _print_json(report)
        return 0
    if args.command == "node" and args.node_command == "status":
        report = _build_node_status_report()
        if args.pretty:
            _print_node_status_pretty(report, color=args.color)
        else:
            _print_json(report)
        return 0
    if args.command == "node" and args.node_command == "pair":
        report = _build_node_pair_report(args)
        if args.pretty:
            _print_node_pair_pretty(report, color=args.color)
        else:
            _print_json(report)
        return 0
    if args.command == "relay" and args.relay_command == "status":
        report = _build_relay_status_report()
        if args.pretty:
            _print_relay_status_pretty(report, color=args.color)
        else:
            _print_json(report)
        return 0 if report["ok"] else 1
    if args.command == "oracle":
        report = _build_oracle_report(args)
        if args.pretty:
            _print_oracle_pretty(report, color=args.color)
        else:
            _print_json(report)
        return 0 if report["ok"] else 1
    if args.command == "hybrid":
        report = _build_hybrid_report(args)
        if args.pretty:
            _print_hybrid_pretty(report, color=args.color)
        else:
            _print_json(report)
        return 0 if report["ok"] else 1
    if args.command == "plan":
        report = _build_execution_plan_report(args, command="yonerai plan", dry_run=True)
        if args.json:
            _print_json(report)
        else:
            _print_execution_plan_pretty(report, color=args.color)
        return 0
    if args.command == "ask":
        if args.dry_run:
            report = _build_execution_plan_report(args, command="yonerai ask --dry-run", dry_run=True)
        elif args.auto:
            report = _execute_auto_ask_report(args)
        else:
            report = _execute_ask_report(args)
        if args.json:
            _print_json(report)
        else:
            if args.dry_run:
                _print_execution_plan_pretty(report, color=args.color)
            elif args.auto:
                _print_auto_runtime_pretty(report, lang=args.lang, color=args.color)
            else:
                _print_execution_result_pretty(report, color=args.color)
        return 0 if args.dry_run or report["ok"] else 1
    if args.command == "runs":
        report = _build_runs_report(args)
        if args.json:
            _print_json(report)
        elif args.runs_command == "show":
            _print_run_show_pretty(report, lang=args.lang, color=args.color)
        else:
            _print_runs_list_pretty(report, lang=args.lang, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "search":
        report = _build_search_report(args)
        if args.json:
            _print_json(report)
        else:
            _print_search_pretty(report, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "discord" and args.discord_command == "synthetic":
        report = _build_discord_report(args)
        if args.json:
            _print_json(report)
        else:
            _print_discord_pretty(report, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "install" and args.install_command in {"plan", "plan-windows"}:
        report = _build_install_report(args)
        if args.json:
            _print_json(report)
        else:
            _print_install_pretty(report, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "update" and args.update_command == "plan":
        report = _build_update_report(args)
        if args.json:
            _print_json(report)
        else:
            _print_update_pretty(report, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "ops" and args.ops_command == "plan":
        report = _build_ops_plan_report(args)
        if args.json:
            _print_json(report)
        else:
            _print_ops_plan_pretty(report, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "memory":
        report = _build_memory_report(args)
        if args.json:
            _print_json(report)
        else:
            _print_memory_pretty(report, color=args.color)
        return 0 if report["ok"] else 1
    if args.command == "message":
        prompt = _prompt_from_args(args.prompt)
        _print_json(request_json("POST", args.api_origin, "/v1/public/messages", {"message": prompt, "mode": args.mode}))
        return 0
    if args.command == "run":
        prompt = _prompt_from_args(args.prompt)
        _print_json(request_json("POST", args.api_origin, "/api/v1/agent/run", {"prompt": prompt, "mode": args.mode}))
        return 0
    parser.error("unknown command")
    return 2


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    try:
        return run(argv)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            continue
