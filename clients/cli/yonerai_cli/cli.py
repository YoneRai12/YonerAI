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
    python_supported = sys.version_info >= (3, 11)
    manifest_contract_valid = bool(manifest_report.get("contract_valid", manifest_report.get("ok")))
    system_checks = {
        "redaction_self_check": _run_redaction_self_check(),
        "mcp_deny_policy": _run_mcp_deny_policy_self_check(),
    }
    checks_ok = all(bool(check.get("ok")) for check in system_checks.values())
    return {
        "ok": manifest_contract_valid and python_supported and checks_ok,
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
        "system_checks": system_checks,
        "errors": manifest_report.get("errors", []),
    }


def _build_status_report(*, source: str = "local") -> dict[str, Any]:
    report = _build_doctor_report(command="yonerai status")
    try:
        _prepare_core_import_path()
        from ora_core.status_contract import build_official_status_contract
    except Exception as exc:
        raise CliError("official status contract fixture is unavailable.", exit_code=1) from exc
    report["status_source"] = source
    report["official_status"] = build_official_status_contract(source=source)
    return report


def _run_redaction_self_check() -> dict[str, Any]:
    try:
        _prepare_repo_import_path()
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
        _prepare_repo_import_path()
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


def _bool_text(value: object) -> str:
    return "true" if value is True else "false" if value is False else str(value)


def _run_public_mvp_smoke(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_repo_import_path()
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
        _prepare_repo_import_path()
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
    text = str(_repo_root())
    if text not in sys.path:
        sys.path.insert(0, text)


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
    text = str(core_src)
    if text not in sys.path:
        sys.path.insert(0, text)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _preview_route(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_core_import_path()
        from ora_core.route_preview import preview_route
    except Exception as exc:
        raise CliError("route preview is unavailable.", exit_code=1) from exc

    prompt = _prompt_from_args(args.task)
    provider_prompt = prompt
    provider_prompt = prompt
    local_node_state = args.local_node_state
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
    decision = preview_route(
        prompt,
        mode=args.mode,
        requested_capability=args.capability,
        has_local_node=has_local_node,
        local_node_verification_state=local_node_state,
        local_node_capabilities=local_node_capabilities,
        require_enrolled_verified_session=require_session,
        session_verification_state=args.session_state,
        risk_hint=args.risk_hint,
    )
    return decision.to_public_dict()


def _build_execution_plan_report(args: argparse.Namespace, *, command: str, dry_run: bool) -> dict[str, Any]:
    try:
        _prepare_repo_import_path()
        _prepare_core_import_path()
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
        _prepare_repo_import_path()
        _prepare_core_import_path()
        from ora_core.execution.workspace_files import WorkspaceFileError, build_workspace_file_prompt, read_workspace_text_file
        from ora_core.execution.ledger import build_run_ledger_from_env
        from ora_core.execution.spine import execute_task
    except Exception as exc:
        raise CliError("execution spine is unavailable.", exit_code=1) from exc

    prompt = _prompt_from_args(args.task)
    file_context = None
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
                "file_context": None,
                "error": exc.to_public_dict(),
            }
        provider_prompt = build_workspace_file_prompt(prompt, file_context)
    try:
        result = execute_task(
            prompt,
            provider_prompt=provider_prompt,
            mode=args.mode,
            provider=args.provider,
            live=args.live,
            ledger=build_run_ledger_from_env(args.ledger_path),
        )
    except ValueError as exc:
        raise CliError(str(exc), exit_code=2) from exc
    report = result.to_public_dict()
    if file_context is not None:
        report["file_context"] = file_context.to_public_dict()
    return report


def _print_execution_result_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    print(_format_execution_result_pretty(report, color=color))


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
    provider = plan["provider"]
    sections = (
        CliSection(
            "Run",
            (
                CliRow("run_id", run["run_id"], "ok"),
                CliRow("status", run["status"], "ok" if run["status"] == "completed" else "warn"),
                CliRow("category", plan["classification"]["category"], "ok"),
                CliRow("approval_required", run["approval_required"], "warn" if run["approval_required"] else "ok"),
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
                CliRow("shell", plan["side_effects"]["shell"], "fail" if plan["side_effects"]["shell"] else "ok"),
                CliRow("file_access", plan["side_effects"]["file_access"], "fail" if plan["side_effects"]["file_access"] else "ok"),
                CliRow("memory_persisted", run["persistence"]["memory_persisted"], "fail" if run["persistence"]["memory_persisted"] else "ok"),
            ),
        ),
    )
    return render_report("YonerAI ask", sections, color=color)


def _build_runs_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_repo_import_path()
        _prepare_core_import_path()
        from ora_core.execution.ledger import build_run_ledger_from_env
    except Exception as exc:
        raise CliError("run ledger is unavailable.", exit_code=1) from exc

    ledger = build_run_ledger_from_env(args.ledger_path)
    if args.runs_command == "list":
        runs = [run.to_public_dict() for run in ledger.list_runs(limit=args.limit)]
        return {
            "schema_version": "yonerai-runs-list/v1",
            "ok": True,
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
            "error": {"code": "unknown_run", "message": "run_id was not found in the selected local ledger"},
            "run": None,
        }
    return {
        "schema_version": "yonerai-runs-show/v1",
        "ok": True,
        "run": run.to_public_dict(),
        "raw_prompt_persisted": False,
        "raw_completion_persisted": False,
    }


def _build_search_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_core_import_path()
        from ora_core.search import MockSearchAdapter, SearchRequest
    except Exception as exc:
        raise CliError("search adapter is unavailable.", exit_code=1) from exc
    if args.search_mode != "mock":
        return {
            "schema_version": "yonerai-search/v1",
            "ok": False,
            "adapter": args.search_mode,
            "execution_performed": False,
            "network_performed": False,
            "error": {"code": "search_live_disabled", "message": "live search is not implemented in this public alpha slice"},
            "results": [],
        }
    query = _prompt_from_args(args.query)
    results = [result.to_public_dict() for result in MockSearchAdapter().search(SearchRequest(query=query))]
    return {
        "schema_version": "yonerai-search/v1",
        "ok": True,
        "adapter": "mock",
        "execution_performed": False,
        "network_performed": False,
        "query": query,
        "results": results,
    }


def _print_search_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    if not report["ok"]:
        print(render_report("YonerAI search", (CliSection("Error", (CliRow("error", report["error"]["message"], "fail"),)),), color=color))
        return
    rows = tuple(CliRow(result["title"], result["snippet"], "ok") for result in report["results"])
    print(render_report("YonerAI search", (CliSection("Mock results", rows),), color=color))


def _build_discord_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_core_import_path()
        from ora_core.discord_gateway import SyntheticDiscordGatewayAdapter
    except Exception as exc:
        raise CliError("Discord gateway adapter is unavailable.", exit_code=1) from exc
    prompt = _prompt_from_args(args.message)
    result = SyntheticDiscordGatewayAdapter().handle_mention(prompt)
    return result.to_public_dict()


def _print_discord_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    rows = (
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
        _prepare_core_import_path()
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
        _prepare_core_import_path()
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


def _print_runs_list_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    rows = tuple(
        CliRow(
            str(run["run_id"]),
            f"{run['status']} {run['provider_decision'].get('provider_id', 'unknown')} {run['task_summary']}",
            "ok" if run["status"] == "completed" else "warn",
        )
        for run in report["runs"]
    ) or (CliRow("runs", "none in selected local ledger", "warn"),)
    print(render_report("YonerAI runs", (CliSection("Recent", rows),), color=color))


def _print_run_show_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> None:
    if not report["ok"]:
        print(render_report("YonerAI run", (CliSection("Error", (CliRow("error", report["error"]["message"], "fail"),)),), color=color))
        return
    run = report["run"]
    events = tuple(CliRow(event["name"], f"{event['status']} {event['summary']}", "ok" if event["status"] == "ok" else "warn") for event in run["events"])
    sections = (
        CliSection(
            "Run",
            (
                CliRow("run_id", run["run_id"], "ok"),
                CliRow("status", run["status"], "ok" if run["status"] == "completed" else "warn"),
                CliRow("task_summary", run["task_summary"], "ok"),
                CliRow("provider", run["provider_decision"].get("provider_id", "unknown"), "ok"),
            ),
        ),
        CliSection("Events", events or (CliRow("events", "none", "warn"),)),
    )
    print(render_report("YonerAI run", sections, color=color))


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
            "YonerAI local public MVP smoke CLI. "
            "Not the final product CLI, not native Japanese CLI, and not a deploy tool."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

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

    doctor = subcommands.add_parser("doctor", help="Run offline, non-mutating setup diagnostics.")
    doctor_output = doctor.add_mutually_exclusive_group()
    doctor_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    doctor_output.add_argument("--pretty", action="store_true", help="Print a readable diagnostic summary.")
    doctor.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    doctor.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

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
    route_preview.add_argument(
        "--mode",
        choices=["official_managed_cloud", "official_hybrid_private", "full_private_self_host"],
        default="official_managed_cloud",
    )
    route_preview.add_argument("--capability", help="Optional explicit capability name.")
    route_preview.add_argument("--risk-hint", help="Optional public-safe operation class hint.")
    route_preview.add_argument("--has-local-node", action="store_true", help="Preview as if a user Local Node is available.")
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
    ask.add_argument("--dry-run", action="store_true", help="Preview only; no provider call is made.")
    ask.add_argument("--live", action="store_true", help="Allow explicitly gated local or external live provider execution.")
    ask.add_argument("--ledger-path", help="Optional redacted JSONL run ledger path. Disabled by default.")
    ask.add_argument("--file", help="Optional workspace-local UTF-8 text file to summarize or use as ask context.")
    ask.add_argument("--workspace", help="Required workspace root when --file is used.")
    ask.add_argument("--file-max-bytes", type=int, default=65536, help="Maximum file bytes to read. Default: 65536.")
    ask_output = ask.add_mutually_exclusive_group()
    ask_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    ask_output.add_argument("--pretty", action="store_true", help="Print a readable execution summary.")
    ask.add_argument("--provider", choices=PLAN_PROVIDER_CHOICES, default="auto", help="Provider preference. Default: auto.")
    ask.add_argument("--mode", choices=PLAN_MODE_CHOICES, default="self-host", help="Execution planning mode. Default: self-host.")
    ask.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    search = subcommands.add_parser("search", help="Run deterministic mock search or report live search as disabled.")
    search.add_argument("search_mode", choices=("mock", "live"), help="Search mode. Default-safe mode is mock.")
    search.add_argument("query", nargs="+")
    search_output = search.add_mutually_exclusive_group()
    search_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    search_output.add_argument("--pretty", action="store_true", help="Print a readable search fixture summary.")
    search.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    discord = subcommands.add_parser("discord", help="Inspect public-safe Discord gateway adapter boundaries.")
    discord_subcommands = discord.add_subparsers(dest="discord_command", required=True)
    discord_synthetic = discord_subcommands.add_parser("synthetic", help="Run a synthetic Discord mention fixture.")
    discord_synthetic.add_argument("message", nargs="+")
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
    runs_list.add_argument("--ledger-path", help="Optional redacted JSONL run ledger path. Defaults to YONERAI_RUN_LEDGER_PATH.")
    runs_list.add_argument("--limit", type=int, default=20, help="Maximum runs to show. Default: 20.")
    runs_list_output = runs_list.add_mutually_exclusive_group()
    runs_list_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    runs_list_output.add_argument("--pretty", action="store_true", help="Print a readable run list.")
    runs_list.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")
    runs_show = runs_subcommands.add_parser("show", help="Show one run from an opt-in ledger.")
    runs_show.add_argument("run_id")
    runs_show.add_argument("--ledger-path", help="Optional redacted JSONL run ledger path. Defaults to YONERAI_RUN_LEDGER_PATH.")
    runs_show_output = runs_show.add_mutually_exclusive_group()
    runs_show_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    runs_show_output.add_argument("--pretty", action="store_true", help="Print a readable run summary.")
    runs_show.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    message = subcommands.add_parser("message", parents=[shared], help="Send a local public message smoke request.")
    message.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    message.add_argument("prompt", nargs="+")

    run = subcommands.add_parser("run", parents=[shared], help="Create a local Surface API run smoke request.")
    run.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    run.add_argument("prompt", nargs="+")

    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        _print_json(request_json("GET", args.api_origin, "/health"))
        return 0
    if args.command == "smoke":
        return _run_public_mvp_smoke(json_output=args.json, pretty=args.pretty)
    if args.command in {"demo", "quickstart"}:
        return _run_public_demo(json_output=args.json, pretty=args.pretty)
    if args.command == "doctor":
        report = _build_doctor_report()
        if args.json:
            _print_json(report)
        else:
            _print_doctor_pretty(report, lang=args.lang, color=args.color)
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
        _print_json(_preview_route(args))
        return 0
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
        else:
            report = _execute_ask_report(args)
        if args.json:
            _print_json(report)
        else:
            if args.dry_run:
                _print_execution_plan_pretty(report, color=args.color)
            else:
                _print_execution_result_pretty(report, color=args.color)
        return 0 if args.dry_run or report["ok"] else 1
    if args.command == "runs":
        report = _build_runs_report(args)
        if args.json:
            _print_json(report)
        elif args.runs_command == "show":
            _print_run_show_pretty(report, color=args.color)
        else:
            _print_runs_list_pretty(report, color=args.color)
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
