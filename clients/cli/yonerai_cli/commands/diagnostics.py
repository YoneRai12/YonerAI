from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from yonerai_cli import __version__
from yonerai_cli.commands.providers import ProvidersCommandError, build_providers_report
from yonerai_cli.release_manifest import ManifestError, load_manifest_file, verify_manifest


TOKEN_ENV = "ORA_CORE_API_TOKEN"


class DiagnosticsCommandError(Exception):
    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _build_doctor_report(*, command: str = "yonerai doctor") -> dict[str, Any]:
    manifest_path = _repo_root() / "releases" / "manifest.example.json"
    manifest_report: dict[str, Any]
    try:
        manifest_report = verify_manifest(load_manifest_file(str(manifest_path)))
    except ManifestError as exc:
        manifest_report = {"ok": False, "errors": [str(exc)]}
    try:
        from yonerai_cli.install_planner import build_install_update_status

        install_update = build_install_update_status()
    except Exception:
        install_update = {
            "latest_stable": "unknown",
            "quick_install_command": "unavailable",
            "github_install_fallback_command": "unavailable",
            "verified_install_page": "https://yonerai.com/install",
            "forced_update_enabled": False,
            "auto_update_apply_enabled": False,
        }
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
    try:
        from yonerai_cli.install_planner import build_install_status

        install_source = build_install_status(_repo_root(), channel="stable")
    except Exception:
        install_source = {
            "schema_version": "yonerai-install-status/v0.1",
            "ok": False,
            "source_policy": {
                "install_script_source": "github_release_asset_only",
                "yonerai_com_serves_install_script": False,
                "yonerai_com_serves_manifest_or_zip": False,
                "local_file_source_allowed": False,
            },
        }
    try:
        from ora_core.official import build_status_check_report

        status_api = build_status_check_report(profile="operational")
    except Exception:
        status_api = {
            "schema_version": "yonerai-status-api/v0.1",
            "ok": False,
            "status": "contract_only",
            "component_count": 0,
            "production_backend_included": False,
            "private_runtime_details_included": False,
            "error": "status_api_unavailable",
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
    status_api_ok = bool(status_api.get("ok"))
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
            and status_api_ok
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
        "install_update": install_update,
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
        "install_source": install_source,
        "status_api": status_api,
        "provider_runtime_e2e_fixtures": _provider_runtime_e2e_fixture_report(),
        "system_checks": system_checks,
        "errors": manifest_report.get("errors", []),
    }


def _build_status_report(
    *,
    source: str = "local",
    status_source: str | None = None,
    allow_network_status_fetch: bool = False,
    profile: str = "operational",
) -> dict[str, Any]:
    report = _build_doctor_report(command="yonerai status")
    try:
        _prepare_trusted_cli_import_paths()
        from ora_core.status_contract import build_official_status_contract
        from ora_core.official import build_status_check_report
    except Exception as exc:
        raise DiagnosticsCommandError("official status contract fixture is unavailable.", exit_code=1) from exc
    report["status_source"] = source
    report["official_status"] = build_official_status_contract(source=source)
    try:
        report["status_api"] = build_status_check_report(
            source=status_source,
            allow_network=allow_network_status_fetch,
            profile=profile,
        )
    except ValueError as exc:
        raise DiagnosticsCommandError(str(exc), exit_code=2) from exc
    return report


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
    try:
        return build_providers_report(prepare_import_paths=_prepare_trusted_cli_import_paths, env=os.environ)
    except ProvidersCommandError as exc:
        raise DiagnosticsCommandError(str(exc), exit_code=1) from exc


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


from yonerai_cli.screens.diagnostics import (
    _format_doctor_pretty,
    _format_status_pretty,
    _print_doctor_pretty,
    _print_start_pretty,
    _print_status_pretty,
)


def _run_public_mvp_smoke(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_trusted_cli_import_paths()
        public_mvp_smoke = _load_public_mvp_smoke_module()
    except Exception as exc:
        raise DiagnosticsCommandError("public MVP smoke is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else []
        return public_mvp_smoke.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:
        raise DiagnosticsCommandError("public MVP smoke failed.", exit_code=1) from exc


def _run_public_demo(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_trusted_cli_import_paths()
        public_demo = _load_public_demo_module()
    except Exception as exc:
        raise DiagnosticsCommandError("YonerAI public demo is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else ["--pretty"]
        return public_demo.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        raise DiagnosticsCommandError("YonerAI public demo failed.", exit_code=1) from exc


def _prepare_repo_import_path() -> None:
    _pin_import_path_front(_repo_root())


def _prepare_trusted_cli_import_paths() -> None:
    _prepare_repo_import_path()
    _prepare_core_import_path()


def _load_repo_script_module(module_name: str, script_relative_path: str) -> Any:
    script_path = _repo_root() / script_relative_path
    if not script_path.is_file():
        raise DiagnosticsCommandError("public script module is unavailable.", exit_code=1)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise DiagnosticsCommandError("public script module is unavailable.", exit_code=1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_public_mvp_smoke_module() -> Any:
    try:
        return _load_repo_script_module("yonerai_trusted_public_mvp_smoke", "scripts/dev/public_mvp_smoke.py")
    except DiagnosticsCommandError:
        from yonerai_cli.services.public_runtime_service import packaged_public_mvp_smoke

        return packaged_public_mvp_smoke


def _load_public_demo_module() -> Any:
    try:
        return _load_repo_script_module("yonerai_trusted_public_demo", "scripts/dev/public_demo.py")
    except DiagnosticsCommandError:
        from yonerai_cli.services.public_runtime_service import packaged_public_demo

        return packaged_public_demo


def _prepare_core_import_path() -> None:
    core_src = _repo_root() / "core" / "src"
    _pin_import_path_front(core_src)


def _pin_import_path_front(path: Path) -> None:
    text = str(path)
    sys.path[:] = [entry for entry in sys.path if entry != text]
    sys.path.insert(0, text)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]
