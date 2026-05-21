from __future__ import annotations

import json

from scripts.dev import public_mvp_smoke


def test_public_mvp_smoke_runs_without_credentials(monkeypatch) -> None:
    for key in (
        "DISCORD_TOKEN",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ORA_CORE_API_TOKEN",
        "ORA_LOCAL_LLM_BASE_URL",
        "ORA_LOCAL_LLM_ENABLED",
        "ORA_LOCAL_LLM_PUBLIC_TOKEN",
    ):
        monkeypatch.setenv(key, "must-be-cleared-by-smoke")

    result = public_mvp_smoke.run_smoke()

    assert result["ok"] is True
    assert result["contract"] == public_mvp_smoke.PUBLIC_MVP_SMOKE_CONTRACT
    assert result["credentials_required"] is False
    assert result["external_provider_required"] is False
    assert result["live_discord_required"] is False
    assert [check["endpoint"] for check in result["checks"]] == [
        "/health",
        "/v1/public/messages",
        "/api/v1/agent/run",
    ]
    assert "must-be-cleared-by-smoke" not in json.dumps(result)


def test_public_mvp_smoke_cli_json_output_is_deterministic(capsys) -> None:
    exit_code = public_mvp_smoke.main(["--json"])

    assert exit_code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    assert body["contract"] == public_mvp_smoke.PUBLIC_MVP_SMOKE_CONTRACT
    assert body["checks"] == [
        {"endpoint": "/health", "status": "ok"},
        {
            "endpoint": "/v1/public/messages",
            "mode": "mock",
            "provider": "offline-mock",
            "status": "ok",
        },
        {
            "endpoint": "/api/v1/agent/run",
            "mode": "mock",
            "provider": "offline-mock",
            "status": "ok",
        },
    ]
    assert "run_id" not in body
    assert "session_id" not in body


def test_public_mvp_smoke_cli_masks_unexpected_failures(monkeypatch, capsys) -> None:
    def fail_unexpectedly():
        raise RuntimeError("private runtime detail")

    monkeypatch.setattr(public_mvp_smoke, "run_smoke", fail_unexpectedly)

    exit_code = public_mvp_smoke.main(["--json"])

    assert exit_code == 1
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "ok": False,
        "contract": public_mvp_smoke.PUBLIC_MVP_SMOKE_CONTRACT,
        "error": "public MVP smoke failed",
    }
