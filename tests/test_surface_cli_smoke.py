from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any


def _load_cli_module():
    cli_src = Path(__file__).resolve().parents[1] / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli import cli

    return cli


def test_cli_health_command_uses_loopback_core_api(monkeypatch, capsys):
    cli = _load_cli_module()
    calls = []

    def fake_request_json(method, origin, path, body=None):
        calls.append((method, origin, path, body))
        return {"ok": True, "service": "ora-core"}

    monkeypatch.setattr(cli, "request_json", fake_request_json)

    assert cli.main(["health"]) == 0

    assert calls == [("GET", "http://127.0.0.1:8001", "/health", None)]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_cli_smoke_command_runs_public_mvp_smoke(monkeypatch):
    cli = _load_cli_module()
    calls = []

    def fake_public_smoke(json_output=False, pretty=False):
        calls.append((json_output, pretty))
        return 0

    monkeypatch.setattr(cli, "_run_public_mvp_smoke", fake_public_smoke)

    assert cli.main(["smoke", "--json"]) == 0

    assert calls == [(True, False)]


def test_cli_smoke_import_failure_is_public_safe(monkeypatch, capsys):
    cli = _load_cli_module()
    private_path = "C:" + "\\Users\\dev\\secret.txt"

    def fail_import(*, json_output=False, pretty=False):
        del json_output, pretty
        raise cli.CliError("public MVP smoke is unavailable.", exit_code=1) from RuntimeError(private_path)

    monkeypatch.setattr(cli, "_run_public_mvp_smoke", fail_import)

    assert cli.main(["smoke", "--pretty"]) == 1

    captured = capsys.readouterr()
    assert "public MVP smoke is unavailable" in captured.err
    assert private_path not in captured.err
    assert "Traceback" not in captured.err


def test_cli_demo_command_runs_public_demo_pretty_by_default(monkeypatch):
    cli = _load_cli_module()
    calls = []

    def fake_public_demo(json_output=False, pretty=False):
        calls.append((json_output, pretty))
        return 0

    monkeypatch.setattr(cli, "_run_public_demo", fake_public_demo)

    assert cli.main(["demo"]) == 0

    assert calls == [(False, False)]


def test_cli_quickstart_alias_runs_public_demo_pretty_by_default(monkeypatch):
    cli = _load_cli_module()
    calls = []

    def fake_public_demo(json_output=False, pretty=False):
        calls.append((json_output, pretty))
        return 0

    monkeypatch.setattr(cli, "_run_public_demo", fake_public_demo)

    assert cli.main(["quickstart"]) == 0

    assert calls == [(False, False)]


def test_cli_demo_json_flag_dispatches_to_public_demo_json(monkeypatch):
    cli = _load_cli_module()
    calls = []

    def fake_public_demo(json_output=False, pretty=False):
        calls.append((json_output, pretty))
        return 0

    monkeypatch.setattr(cli, "_run_public_demo", fake_public_demo)

    assert cli.main(["demo", "--json"]) == 0

    assert calls == [(True, False)]


def test_cli_demo_available_from_clients_cli_cwd() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_cwd = repo_root / "clients" / "cli"
    result = subprocess.run(
        [sys.executable, "-m", "yonerai_cli", "demo", "--json"],
        cwd=cli_cwd,
        env={**os.environ, "PYTHONPATH": str(cli_cwd)},
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["ok"] is True
    assert output["contract"] == "yonerai-public-demo/v1"
    assert output["schema_version"] == "1.0"
    assert output["cli_entrypoint"] == "yonerai demo"
    assert output["quickstart_alias"] == "yonerai quickstart"
    assert [section["name"] for section in output["sections"]] == [
        "public_core",
        "mode_boundary",
        "route_preview",
        "provider_planner",
        "execution_spine",
        "hybrid_trust",
        "managed_download",
        "self_evolution",
        "limitations",
    ]
    assert output["official_cloud_runtime_included"] is False
    assert output["oracle_required"] is False
    assert output["live_discord_required"] is False
    assert output["persistent_memory_required"] is False
    assert "Traceback" not in result.stderr
    assert "session_id" not in result.stdout.lower()
    assert "C:\\Users" not in result.stdout


def test_cli_doctor_reports_offline_status_without_network(monkeypatch, capsys):
    cli = _load_cli_module()
    for key in (
        "ORA_LOCAL_LLM_ENABLED",
        "ORA_LOCAL_LLM_BASE_URL",
        "YONERAI_OPENAI_COMPATIBLE_BASE_URL",
        "YONERAI_OPENAI_COMPATIBLE_API_KEY",
        "YONERAI_OPENAI_COMPATIBLE_LIVE",
    ):
        monkeypatch.delenv(key, raising=False)

    def fail_request_json(*_args: Any, **_kwargs: Any):
        raise AssertionError("doctor must not call loopback API")

    def fail_urlopen(*_args: Any, **_kwargs: Any):
        raise AssertionError("doctor must not open network")

    monkeypatch.setattr(cli, "request_json", fail_request_json)
    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    assert cli.main(["doctor", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-doctor/v1"
    assert output["ok"] is True
    assert output["boundaries"]["network_required"] is False
    assert output["boundaries"]["install_mutation"] is False
    assert output["boundaries"]["official_cloud_runtime_included"] is False
    assert output["manifest"]["contract_valid"] is True
    assert output["manifest"]["install_ready"] is False
    assert output["cli"]["repo_version"] == "0.1.0-alpha.2"
    assert output["system_checks"]["redaction_self_check"]["ok"] is True
    assert output["system_checks"]["mcp_deny_policy"]["ok"] is True
    assert output["system_checks"]["mcp_deny_policy"]["network_required"] is False
    assert output["providers"]["network_probe_performed"] is False
    e2e = output["provider_runtime_e2e_fixtures"]
    assert e2e["status"] == "covered_by_local_tests"
    assert e2e["openai_compatible"] == "local_mock_http_server_tested"
    assert e2e["local_llm"] == "loopback_mock_http_server_tested"
    assert e2e["run_ledger"] == "redacted_success_and_error_paths_tested"
    assert e2e["external_network_call_performed"] is False
    providers = {provider["provider_id"]: provider for provider in output["providers"]["providers"]}
    assert providers["mock"]["setup_status"] == "ready"
    assert providers["local"]["loopback_only"] is True
    assert "set ORA_LOCAL_LLM_ENABLED=1" in providers["local"]["setup_blockers"]
    assert "set YONERAI_OPENAI_COMPATIBLE_BASE_URL" in providers["openai-compatible"]["setup_blockers"]


def test_cli_doctor_redacts_token_presence(monkeypatch, capsys):
    cli = _load_cli_module()
    monkeypatch.setenv(cli.TOKEN_ENV, "super-secret-token")

    assert cli.main(["doctor", "--json"]) == 0

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["credentials"][cli.TOKEN_ENV] == "present_redacted"
    assert "super-secret-token" not in captured.out
    assert "Traceback" not in captured.err


def test_cli_doctor_redacts_openai_compatible_provider_setup(monkeypatch, capsys):
    cli = _load_cli_module()
    pseudo_key = "redaction-fixture-key"
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", "https://api.example.invalid/v1")
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", pseudo_key)
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_LIVE", "1")

    assert cli.main(["doctor", "--json"]) == 0

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    provider = next(item for item in output["providers"]["providers"] if item["provider_id"] == "openai-compatible")
    assert provider["setup_status"] == "live_ready"
    assert provider["live_ready"] is True
    assert provider["env_status"]["YONERAI_OPENAI_COMPATIBLE_API_KEY"] == "present_redacted"
    assert pseudo_key not in captured.out
    assert "api.example.invalid" not in captured.out


def test_cli_doctor_does_not_execute_demo_or_mutate_path(monkeypatch, capsys):
    cli = _load_cli_module()
    original_path = os.environ.get("PATH", "")

    def fail_demo(*_args: Any, **_kwargs: Any):
        raise AssertionError("doctor must not execute demo")

    monkeypatch.setattr(cli, "_run_public_demo", fail_demo)

    assert cli.main(["doctor", "--pretty"]) == 0

    assert os.environ.get("PATH", "") == original_path
    output = capsys.readouterr().out
    assert "YonerAI doctor" in output
    assert "manifest_example_valid: true" in output
    assert "Provider runtime" in output
    assert "Provider runtime E2E fixtures" in output
    assert "local_mock_http_server_tested" in output
    assert "loopback_mock_http_server_tested" in output
    assert "\033[" not in output


def test_cli_doctor_pretty_supports_japanese_without_json_key_translation(monkeypatch, capsys):
    cli = _load_cli_module()
    for key in (
        "ORA_LOCAL_LLM_ENABLED",
        "ORA_LOCAL_LLM_BASE_URL",
        "YONERAI_OPENAI_COMPATIBLE_BASE_URL",
        "YONERAI_OPENAI_COMPATIBLE_API_KEY",
        "YONERAI_OPENAI_COMPATIBLE_LIVE",
    ):
        monkeypatch.delenv(key, raising=False)

    assert cli.main(["doctor", "--pretty", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI 診断" in output
    assert "デモ" in output
    assert "利用可能" in output
    assert "Official Managed Cloud" in output
    assert "外部/契約のみ" in output
    assert "ネットワークインストーラー" in output
    assert "未実装" in output
    assert "本番機能" in output
    assert "含まれません" in output
    assert "プロバイダー実行環境" in output
    assert "プロバイダー実行環境 E2E フィクスチャ" in output
    assert "状態" in output
    assert "local_mock_http_server_tested" in output
    assert "openai-compatible" in output
    assert "set YONERAI_OPENAI_COMPATIBLE_BASE_URL" in output
    assert "manifest_example_valid" not in output
    assert "\033[" not in output


def test_provider_setup_rows_localizes_japanese_fallback():
    cli = _load_cli_module()

    rows = cli._provider_setup_rows({"providers": {}}, lang="ja")

    assert rows[0].label == "プロバイダー"
    assert rows[0].value == "利用不可"
    assert rows[0].status == "warn"


def test_cli_doctor_json_remains_english_keyed_with_lang_ja(capsys):
    cli = _load_cli_module()

    assert cli.main(["doctor", "--json", "--lang", "ja"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["command"] == "yonerai doctor"
    assert output["manifest"]["contract_valid"] is True
    assert "system_checks" in output
    assert "マニフェスト" not in json.dumps(output, ensure_ascii=False)


def test_cli_status_reports_public_demo_and_installer_readiness(capsys):
    cli = _load_cli_module()

    assert cli.main(["status", "--pretty", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI 状態" in output
    assert "公開デモ" in output
    assert "配布準備" in output
    assert "インストール準備" in output
    assert "未完了" in output
    assert "Live Discord" in output
    assert "不要" in output
    assert "\033[" not in output


def test_cli_status_json_is_doctor_schema_without_network(monkeypatch, capsys):
    cli = _load_cli_module()

    def fail_urlopen(*_args: Any, **_kwargs: Any):
        raise AssertionError("status must not open network")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    assert cli.main(["status", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["command"] == "yonerai status"
    assert output["schema_version"] == "yonerai-doctor/v1"
    assert output["boundaries"]["network_required"] is False


def test_cli_manifest_verify_accepts_example_as_contract_not_install_ready(capsys):
    cli = _load_cli_module()

    assert cli.main(["manifest", "verify", "releases/manifest.example.json", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["contract_valid"] is True
    assert output["install_ready"] is False
    assert output["signature_state"] == "placeholder_non_production"
    assert output["signature_verified"] is False
    assert output["non_production_reason"] == "signature_not_production_verified"


def test_cli_manifest_verify_pretty_reports_human_readable_boundary(capsys):
    cli = _load_cli_module()

    assert cli.main(["manifest", "verify", "releases/manifest.example.json", "--pretty", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI manifest verification" in output
    assert "contract_valid" in output
    assert "install_ready" in output
    assert "artifact_count" in output
    assert "signature_state" in output
    assert "download_performed: false" in output
    assert "install_performed" in output
    assert "\033[" not in output


def test_cli_manifest_verify_pretty_supports_japanese(capsys):
    cli = _load_cli_module()

    assert cli.main(["manifest", "verify", "releases/manifest.example.json", "--pretty", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI マニフェスト検証" in output
    assert "契約" in output
    assert "インストール準備" in output
    assert "未完了" in output
    assert "署名状態" in output
    assert "ダウンロード" in output
    assert "実行しません" in output


def test_cli_manifest_verify_rejects_remote_manifest_without_fetch(monkeypatch, capsys):
    cli = _load_cli_module()

    def fail_urlopen(*_args: Any, **_kwargs: Any):
        raise AssertionError("manifest verify must not fetch remote manifests")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    exit_code = cli.main(["manifest", "verify", "https://example.invalid/manifest.json", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "remote URLs are not fetched" in captured.err


def test_cli_manifest_verify_rejects_empty_artifact_path(capsys):
    cli = _load_cli_module()

    exit_code = cli.main(
        [
            "manifest",
            "verify",
            "releases/manifest.example.json",
            "--artifact",
            "yonerai-0.1.0-alpha.1-source-archive=   ",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "artifact path must not be empty" in captured.err


def test_cli_manifest_verify_rejects_missing_sha256(tmp_path, capsys):
    cli = _load_cli_module()
    manifest = json.loads((Path(__file__).resolve().parents[1] / "releases" / "manifest.example.json").read_text())
    manifest["artifacts"][0].pop("sha256")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code = cli.main(["manifest", "verify", str(manifest_path), "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["contract_valid"] is False
    assert any("sha256" in error for error in output["errors"])


def test_cli_manifest_verify_rejects_unknown_fields(tmp_path, capsys):
    cli = _load_cli_module()
    manifest = json.loads((Path(__file__).resolve().parents[1] / "releases" / "manifest.example.json").read_text())
    manifest["private_runtime_inventory"] = "not allowed"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code = cli.main(["manifest", "verify", str(manifest_path), "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert any("unknown fields" in error for error in output["errors"])
    assert "private_runtime_inventory" in json.dumps(output)


def test_cli_manifest_verify_rejects_require_signed_placeholder(capsys):
    cli = _load_cli_module()

    exit_code = cli.main(["manifest", "verify", "releases/manifest.example.json", "--require-signed", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["contract_valid"] is False
    assert "manifest is not fully signed." in output["errors"]


def test_cli_manifest_verify_hashes_supplied_artifact_without_printing_path(tmp_path, capsys):
    cli = _load_cli_module()
    artifact = tmp_path / "artifact.zip"
    artifact.write_bytes(b"local artifact")
    digest = __import__("hashlib").sha256(b"local artifact").hexdigest()
    manifest = json.loads((Path(__file__).resolve().parents[1] / "releases" / "manifest.example.json").read_text())
    manifest["artifacts"][0]["sha256"] = digest
    manifest["artifacts"][0]["size_bytes"] = len(b"local artifact")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    artifact_arg = f"{manifest['artifacts'][0]['id']}={artifact}"

    assert cli.main(["manifest", "verify", str(manifest_path), "--artifact", artifact_arg, "--json"]) == 0

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["artifact_checks"][0]["status"] == "verified"
    assert str(tmp_path) not in captured.out
    assert str(tmp_path) not in captured.err


def test_cli_manifest_verify_fails_digest_mismatch_closed(tmp_path, capsys):
    cli = _load_cli_module()
    artifact = tmp_path / "artifact.zip"
    artifact.write_bytes(b"wrong artifact")
    manifest_path = Path(__file__).resolve().parents[1] / "releases" / "manifest.example.json"
    artifact_id = json.loads(manifest_path.read_text(encoding="utf-8"))["artifacts"][0]["id"]

    exit_code = cli.main(["manifest", "verify", str(manifest_path), "--artifact", f"{artifact_id}={artifact}", "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["artifact_checks"][0]["status"] == "failed"
    assert output["artifact_checks"][0]["reason"] == "sha256_mismatch"


def test_cli_smoke_treats_system_exit_none_as_success(monkeypatch):
    cli = _load_cli_module()

    def exit_none(json_output=False, pretty=False):
        del json_output, pretty
        raise SystemExit

    class FakeSmoke:
        main = staticmethod(exit_none)

    monkeypatch.setattr(cli, "_load_public_mvp_smoke_module", lambda: FakeSmoke)

    assert cli._run_public_mvp_smoke() == 0


def test_cli_demo_treats_system_exit_none_as_success(monkeypatch):
    cli = _load_cli_module()

    def exit_none(argv=None):
        del argv
        raise SystemExit

    class FakeDemo:
        main = staticmethod(exit_none)

    monkeypatch.setattr(cli, "_load_public_demo_module", lambda: FakeDemo)

    assert cli._run_public_demo() == 0


def test_cli_message_command_uses_public_message_contract(monkeypatch, capsys):
    cli = _load_cli_module()
    calls = []

    def fake_request_json(method, origin, path, body=None):
        calls.append((method, origin, path, body))
        return {"ok": True, "reply": "mock reply", "memory_persisted": False}

    monkeypatch.setattr(cli, "request_json", fake_request_json)

    assert cli.main(["message", "--mode", "mock", "hello"]) == 0

    assert calls == [
        (
            "POST",
            "http://127.0.0.1:8001",
            "/v1/public/messages",
            {"message": "hello", "mode": "mock"},
        )
    ]
    output = json.loads(capsys.readouterr().out)
    assert output["reply"] == "mock reply"
    assert output["memory_persisted"] is False


def test_cli_run_command_uses_surface_api_run_contract(monkeypatch, capsys):
    cli = _load_cli_module()
    calls = []

    def fake_request_json(method, origin, path, body=None):
        calls.append((method, origin, path, body))
        return {"ok": True, "run_id": "surface-run-test", "memory_persisted": False}

    monkeypatch.setattr(cli, "request_json", fake_request_json)

    assert cli.main(["run", "--mode", "mock", "hello"]) == 0

    assert calls == [
        (
            "POST",
            "http://127.0.0.1:8001",
            "/api/v1/agent/run",
            {"prompt": "hello", "mode": "mock"},
        )
    ]
    output = json.loads(capsys.readouterr().out)
    assert output["run_id"] == "surface-run-test"
    assert output["memory_persisted"] is False


def test_cli_route_preview_public_docs_is_preview_only(capsys):
    cli = _load_cli_module()

    assert cli.main(["route", "preview", "--mode", "official_managed_cloud", "summarize", "public", "docs"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["route"] == "managed_cloud_contract_only"
    assert output["mode"] == "official_managed_cloud"
    assert output["cloud_allowed"] is False
    assert output["runtime_available_in_public_repo"] is False
    assert output["public_repo_support_status"] == "contract_only"
    assert output["external_official_service_required"] is True
    assert output["public_repo_execution_available"] is False
    assert output["private_data_allowed"] is False
    assert output["disabled"] is False
    assert output["unavailable_reason"] == "official_managed_cloud_runtime_not_included_in_public_repo"
    assert "preview_only_no_execution" in output["non_claims"]


def test_cli_route_preview_private_file_in_hybrid_requires_local_node(capsys):
    cli = _load_cli_module()

    assert cli.main(["route", "preview", "--mode", "official_hybrid_private", "read", "my", "local", "file"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["route"] == "local_node_required"
    assert output["requested_capability"] == "private_files"
    assert output["approval_required"] is True
    assert output["local_node_required"] is True
    assert output["unavailable_reason"] == "local_node_missing"
    assert "Traceback" not in json.dumps(output)


def test_cli_route_preview_reports_unverified_local_node(capsys):
    cli = _load_cli_module()

    assert (
        cli.main(
            [
                "route",
                "preview",
                "--mode",
                "official_hybrid_private",
                "--local-node-state",
                "present_unverified",
                "read",
                "my",
                "local",
                "file",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["route"] == "local_node_required"
    assert output["local_node_verification_state"] == "present_unverified"
    assert output["unavailable_reason"] == "unverified_node_denied"
    assert output["signed_origin_verified"] is False


def test_cli_route_preview_reports_verified_declared_capability(capsys):
    cli = _load_cli_module()

    assert (
        cli.main(
            [
                "route",
                "preview",
                "--mode",
                "official_hybrid_private",
                "--local-node-state",
                "present_verified",
                "--local-node-capability",
                "private_files",
                "read",
                "my",
                "local",
                "file",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["route"] == "hybrid_coordination_preview"
    assert output["local_node_verification_state"] == "present_verified"
    assert output["signed_origin_verified"] is True
    assert output["local_node_capability_declared"] is True
    assert output["public_repo_execution_available"] is False


def test_cli_route_preview_reports_missing_enrolled_session(capsys):
    cli = _load_cli_module()

    assert (
        cli.main(
            [
                "route",
                "preview",
                "--mode",
                "official_hybrid_private",
                "--local-node-state",
                "present_verified",
                "--local-node-capability",
                "private_files",
                "--require-enrolled-verified-session",
                "read",
                "my",
                "local",
                "file",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["route"] == "enrolled_verified_node_required"
    assert output["unavailable_reason"] == "local_node_session_required"
    assert output["session_required"] is True
    assert output["session_verified"] is False
    assert "session_id" not in json.dumps(output).lower()


def test_cli_route_preview_reports_enrolled_verified_session(capsys):
    cli = _load_cli_module()

    assert (
        cli.main(
            [
                "route",
                "preview",
                "--mode",
                "official_hybrid_private",
                "--local-node-state",
                "present_verified",
                "--local-node-capability",
                "private_files",
                "--session-state",
                "enrolled_verified",
                "read",
                "my",
                "local",
                "file",
            ]
        )
        == 0
    )

    output = json.loads(capsys.readouterr().out)
    assert output["route"] == "hybrid_coordination_preview"
    assert output["session_required"] is True
    assert output["session_verified"] is True
    assert output["session_gate_satisfied"] is True


def test_cli_plan_json_is_preview_only_without_network(monkeypatch, capsys):
    cli = _load_cli_module()

    def fail_request_json(*_args: Any, **_kwargs: Any):
        raise AssertionError("plan must not call loopback API")

    def fail_urlopen(*_args: Any, **_kwargs: Any):
        raise AssertionError("plan must not open network")

    monkeypatch.setattr(cli, "request_json", fail_request_json)
    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    assert cli.main(["plan", "summarize", "public", "docs", "--json", "--mode", "hybrid"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-execution-plan/v1"
    assert output["classification"]["category"] == "summarize_public"
    assert output["provider"]["provider_id"] == "mock"
    assert output["side_effects"]["provider_call"] is False
    assert output["side_effects"]["network_call"] is False
    assert output["side_effects"]["shell"] is False
    assert output["side_effects"]["file_access"] is False


def test_cli_plan_available_from_clients_cli_cwd() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_cwd = repo_root / "clients" / "cli"
    result = subprocess.run(
        [sys.executable, "-m", "yonerai_cli", "plan", "summarize public docs", "--json", "--mode", "hybrid"],
        cwd=cli_cwd,
        env={**os.environ, "PYTHONPATH": str(cli_cwd)},
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["schema_version"] == "yonerai-execution-plan/v1"
    assert output["safety_checks"]["mcp_deny_policy"]["status"] == "ok"
    assert output["safety_checks"]["managed_download_guard"]["status"] == "ok"
    assert "C:\\Users" not in result.stdout


def test_cli_plan_pretty_reports_classification_route_provider(capsys):
    cli = _load_cli_module()

    assert cli.main(["plan", "summarize", "public", "docs", "--pretty", "--mode", "hybrid", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI execution plan" in output
    assert "category" in output
    assert "summarize_public" in output
    assert "provider_available" in output
    assert "mcp_deny_policy" in output
    assert "\033[" not in output


def test_cli_ask_executes_mock_provider_by_default(capsys):
    cli = _load_cli_module()

    exit_code = cli.main(["ask", "hello", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    output = json.loads(captured.out)
    assert output["schema_version"] == "yonerai-execution-result/v1"
    assert output["ok"] is True
    assert output["run"]["run_id"].startswith("run_")
    assert output["response"]["provider"] == "mock"
    assert output["live_call_performed"] is False
    assert output["boundary_checks"]["ora_guardrail_response_interpreter"]["status"] == "ok"
    assert output["boundary_checks"]["ora_guardrail_response_interpreter"]["provider_call_performed"] is False


def test_cli_ask_pretty_reports_ledger_file_backed_label(tmp_path, capsys):
    cli = _load_cli_module()
    ledger = tmp_path / "runs.jsonl"

    assert cli.main(["ask", "hello", "--pretty", "--color", "never", "--ledger", str(ledger)]) == 0

    output = capsys.readouterr().out
    assert "file_backed" in output
    assert "ora_guardrail_response_interpreter" in output
    assert "ledger_file_backed" not in output
    assert "true" in output.lower()
    assert "\033[" not in output


def test_cli_ask_executes_local_provider_with_live_opt_in(monkeypatch, capsys):
    cli = _load_cli_module()
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    for path in (repo_root, core_src):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    from ora_core.providers import local_llm

    monkeypatch.setenv("ORA_LOCAL_LLM_ENABLED", "1")
    monkeypatch.setenv("ORA_LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("ORA_LOCAL_LLM_MODEL", "local-test")

    def fake_generate_local_llm_reply(**kwargs: Any) -> local_llm.LocalLLMReply:
        assert kwargs["config"].base_url == "http://127.0.0.1:11434"
        return local_llm.LocalLLMReply(reply="<|final|>local cli reply", provider="local-ollama", model="local-test")

    monkeypatch.setattr(local_llm, "generate_local_llm_reply", fake_generate_local_llm_reply)

    exit_code = cli.main(["ask", "summarize", "public", "docs", "--provider", "local", "--live", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    output = json.loads(captured.out)
    assert output["ok"] is True
    assert output["response"]["provider"] == "local"
    assert output["response"]["output_text"] == "local cli reply"
    assert output["live_call_performed"] is True
    assert output["ledger"]["local_only"] is True
    assert output["ledger"]["path_persisted_in_output"] is False


def test_cli_ask_dry_run_reuses_execution_plan_without_provider_call(monkeypatch, capsys):
    cli = _load_cli_module()

    def fail_request_json(*_args: Any, **_kwargs: Any):
        raise AssertionError("ask --dry-run must not call loopback API")

    monkeypatch.setattr(cli, "request_json", fail_request_json)

    assert cli.main(["ask", "fix", "this", "Python", "bug", "--dry-run", "--json", "--provider", "openai-compatible", "--mode", "hybrid"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["command"] == "yonerai ask --dry-run"
    assert output["dry_run"] is True
    assert output["execution_performed"] is False
    assert output["provider"]["provider_id"] == "openai-compatible"
    assert output["side_effects"]["provider_call"] is False


def test_cli_ask_blocks_dangerous_actual_execution(capsys):
    cli = _load_cli_module()

    exit_code = cli.main(["ask", "delete", "file", "and", "run", "shell", "command", "--json", "--mode", "hybrid"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["run"]["status"] == "blocked"
    assert output["error"]["code"] == "approval_required"
    assert output["plan"]["side_effects"]["shell"] is False


def test_cli_runs_list_and_show_use_opt_in_redacted_ledger(tmp_path, capsys):
    cli = _load_cli_module()
    ledger = tmp_path / "runs.jsonl"

    assert cli.main(["ask", "summarize", "public", "docs", "--json", "--ledger", str(ledger)]) == 0
    ask_output = json.loads(capsys.readouterr().out)
    run_id = ask_output["run"]["run_id"]
    assert ask_output["ledger"]["file_backed"] is True
    assert str(ledger) not in json.dumps(ask_output)

    assert cli.main(["runs", "list", "--json", "--ledger", str(ledger)]) == 0
    list_output = json.loads(capsys.readouterr().out)
    assert list_output["count"] == 1
    assert list_output["runs"][0]["run_id"] == run_id
    assert list_output["ledger"]["path_persisted_in_output"] is False
    assert list_output["raw_prompt_persisted"] is False

    assert cli.main(["runs", "show", run_id, "--json", "--ledger", str(ledger)]) == 0
    show_output = json.loads(capsys.readouterr().out)
    assert show_output["run"]["run_id"] == run_id
    assert show_output["run"]["status"] == "completed"
    assert show_output["ledger"]["local_only"] is True


def test_cli_plan_dangerous_task_requires_approval(capsys):
    cli = _load_cli_module()

    assert cli.main(["plan", "delete", "file", "and", "run", "shell", "command", "--json", "--mode", "hybrid"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["classification"]["category"] == "dangerous_operation"
    assert output["approval"]["required"] is True
    assert any(gate["reason"] == "mcp_tool_denied_by_default" for gate in output["approval"]["gates"])
    assert "mcp_deny_policy" in output["disabled_reasons"]


def test_cli_plan_provider_unavailable_message_does_not_leak_key(monkeypatch, capsys):
    cli = _load_cli_module()
    pseudo_key = "redaction-fixture-key"
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", pseudo_key)
    monkeypatch.delenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", raising=False)

    assert cli.main(["plan", "fix", "this", "Python", "bug", "--json", "--provider", "openai-compatible", "--mode", "hybrid"]) == 0

    output = capsys.readouterr().out
    parsed = json.loads(output)
    assert parsed["provider"]["provider_available"] is False
    assert pseudo_key not in output
    assert "present_redacted" in output


def test_cli_rejects_remote_api_origin(capsys):
    cli = _load_cli_module()

    exit_code = cli.main(["health", "--api-origin", "https://api.example.invalid"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "api origin must be loopback" in captured.err


def test_cli_origin_rejects_credentials_path_query_and_fragment():
    cli = _load_cli_module()

    rejected = [
        "http://user:secret@127.0.0.1:8001",
        "http://127.0.0.1:8001/api",
        "http://127.0.0.1:8001?token=secret",
        "http://127.0.0.1:8001#secret",
    ]

    for origin in rejected:
        try:
            cli.normalize_loopback_origin(origin)
        except cli.CliError:
            continue
        raise AssertionError(f"origin should be rejected: {origin}")


def test_cli_rejects_malformed_api_origin(capsys):
    cli = _load_cli_module()

    exit_code = cli.main(["health", "--api-origin", "http://[::1"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "api origin is invalid" in captured.err


def test_cli_help_text_is_public_safe(capsys):
    cli = _load_cli_module()

    try:
        cli.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    help_text = capsys.readouterr().out
    assert "local public MVP smoke CLI" in help_text
    assert "not a deploy tool" in help_text
    assert "production-ready" not in help_text


def test_cli_reports_non_json_success_response(monkeypatch, capsys):
    cli = _load_cli_module()

    class NonJsonResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"not json"

    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda request, timeout: NonJsonResponse())

    exit_code = cli.main(["health"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "failed to parse JSON response" in captured.err


def test_cli_http_error_uses_string_detail():
    cli = _load_cli_module()
    error = urllib.error.HTTPError(
        "http://127.0.0.1:8001/health",
        400,
        "Bad Request",
        {},
        BytesIO(b'{"detail":"bad request"}'),
    )

    assert cli._safe_http_error(error) == "request failed with status 400: bad request"


def test_cli_http_error_includes_safe_local_provider_context_without_secret_values():
    cli = _load_cli_module()
    error = urllib.error.HTTPError(
        "http://127.0.0.1:8001/v1/public/messages",
        503,
        "Service Unavailable",
        {},
        BytesIO(
            b'{"error":"local_llm_unavailable","message":"Local LLM runtime is unavailable.",'
            b'"mode":"local","provider":"local-ollama","model":"local-test","status":"unavailable"}'
        ),
    )

    message = cli._safe_http_error(error)

    assert message == (
        "request failed with status 503: local_llm_unavailable: Local LLM runtime is unavailable. "
        "(mode=local, provider=local-ollama, model=local-test, status=unavailable)"
    )
    assert "Authorization" not in message
    assert "token" not in message.lower()


def test_cli_http_error_redacts_secret_like_and_local_path_messages():
    cli = _load_cli_module()
    private_path = "C:" + "\\Users\\dev\\secret.txt"
    secret_like_model = "sk" + "-secret-model-value"
    error = urllib.error.HTTPError(
        "http://127.0.0.1:8001/v1/public/messages",
        503,
        "Service Unavailable",
        {},
        BytesIO(
            json.dumps(
                {
                    "error": "local_llm_unavailable",
                    "message": f"failed at {private_path}",
                    "mode": "local",
                    "provider": "local-ollama",
                    "model": secret_like_model,
                    "status": "unavailable",
                }
            ).encode("utf-8")
        ),
    )

    message = cli._safe_http_error(error)

    assert message == (
        "request failed with status 503: local_llm_unavailable: request failed "
        "(mode=local, provider=local-ollama, status=unavailable)"
    )
    assert private_path not in message
    assert secret_like_model not in message


def test_cli_url_error_does_not_print_local_paths_or_hosts(monkeypatch, capsys):
    cli = _load_cli_module()
    private_path = "C:" + "\\Users\\dev\\secret.txt"
    host = "DESKTOP" + "-LOCAL"

    def fail_urlopen(_request, timeout):
        raise urllib.error.URLError(f"failed at {private_path} on host {host}")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    exit_code = cli.main(["health"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "could not reach loopback Core API" in captured.err
    assert private_path not in captured.err
    assert host not in captured.err
