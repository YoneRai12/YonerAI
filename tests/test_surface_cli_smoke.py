from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from io import BytesIO


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
