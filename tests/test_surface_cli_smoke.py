from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
from io import BytesIO
from pathlib import Path


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


def test_cli_smoke_treats_system_exit_none_as_success(monkeypatch):
    cli = _load_cli_module()

    def exit_none(json_output=False, pretty=False):
        del json_output, pretty
        raise SystemExit

    class FakeSmoke:
        main = staticmethod(exit_none)

    monkeypatch.setitem(sys.modules, "scripts.dev.public_mvp_smoke", FakeSmoke)

    assert cli._run_public_mvp_smoke() == 0


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
                    "model": "sk-secret-model-value",
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
    assert "sk-secret" not in message


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
