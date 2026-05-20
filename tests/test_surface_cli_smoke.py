from __future__ import annotations

import json
import sys
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
