from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = REPO_ROOT / "clients" / "cli"
CORE_SRC = REPO_ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


class _UnavailableProbeOpener:
    def open(self, *_args: Any, **_kwargs: Any) -> None:
        raise OSError("loopback fixture unavailable")


def _load_cli_module():
    from yonerai_cli import cli
    from yonerai_cli import first_run

    return cli, first_run


def _clear_provider_env(monkeypatch) -> None:
    for key in (
        "ORA_LOCAL_LLM_ENABLED",
        "ORA_LOCAL_LLM_BASE_URL",
        "YONERAI_RUN_LEDGER_PATH",
        "YONERAI_OPENAI_COMPATIBLE_BASE_URL",
        "YONERAI_OPENAI_COMPATIBLE_API_KEY",
        "YONERAI_OPENAI_COMPATIBLE_LIVE",
        "YONERAI_ANTHROPIC_API_KEY",
        "YONERAI_ANTHROPIC_BASE_URL",
        "YONERAI_ANTHROPIC_LIVE",
        "YONERAI_GEMINI_API_KEY",
        "YONERAI_GEMINI_BASE_URL",
        "YONERAI_GEMINI_LIVE",
    ):
        monkeypatch.delenv(key, raising=False)


def test_cli_providers_reports_safe_runtime_setup(monkeypatch, capsys) -> None:
    cli, first_run = _load_cli_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setattr(first_run, "_LOCAL_PROBE_OPENER", _UnavailableProbeOpener())

    assert cli.main(["providers", "--json"]) == 0

    report = json.loads(capsys.readouterr().out)
    provider_ids = {provider["provider_id"] for provider in report["providers"]}
    assert report["schema_version"] == "yonerai-providers/v0.2"
    assert {"mock", "local", "openai-compatible", "anthropic", "gemini"} <= provider_ids
    assert report["live_call_performed"] is False
    assert report["network_probe_performed"] is False
    assert "no provider key output" in report["actions_not_performed"]
    assert report["recommended_first_command"] == 'yonerai ask "hello" --auto --json'
    mock_provider = next(provider for provider in report["providers"] if provider["provider_id"] == "mock")
    assert mock_provider["capabilities"]["chat"] is True
    assert mock_provider["capabilities"]["safe_for_subagents"] is True


def test_cli_providers_pretty_is_japanese_first(monkeypatch, capsys) -> None:
    cli, first_run = _load_cli_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setattr(first_run, "_LOCAL_PROBE_OPENER", _UnavailableProbeOpener())

    assert cli.main(["providers", "--pretty", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI プロバイダー" in output
    assert "最初に試すコマンド" in output
    assert "local LLM" in output
    assert "担当計画" in output
    assert "--live" in output
    assert "\x1b[" not in output


def test_cli_ask_auto_pretty_shows_japanese_route_and_ledger(tmp_path: Path, monkeypatch, capsys) -> None:
    cli, first_run = _load_cli_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setattr(first_run, "_LOCAL_PROBE_OPENER", _UnavailableProbeOpener())
    ledger = tmp_path / "runs.jsonl"

    assert cli.main(["ask", "hello", "--auto", "--ledger", str(ledger), "--pretty", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "判断" in output
    assert "ローカルで即時実行" in output
    assert "履歴" in output
    assert "yonerai runs show" in output
    assert str(tmp_path) not in output
    assert "\x1b[" not in output


def test_cli_runs_pretty_japanese_explains_ledger_opt_in(monkeypatch, capsys) -> None:
    cli, first_run = _load_cli_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setattr(first_run, "_LOCAL_PROBE_OPENER", _UnavailableProbeOpener())

    assert cli.main(["runs", "list", "--pretty", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI 実行履歴" in output
    assert "履歴を残すには" in output
    assert "\x1b[" not in output


def test_cli_oracle_queue_respects_ledger_env(monkeypatch, tmp_path: Path, capsys) -> None:
    cli, first_run = _load_cli_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setattr(first_run, "_LOCAL_PROBE_OPENER", _UnavailableProbeOpener())
    ledger = tmp_path / "runs.jsonl"
    monkeypatch.setenv("YONERAI_RUN_LEDGER_PATH", str(ledger))

    assert cli.main(["oracle", "queue", "--json"]) == 0
    queued = json.loads(capsys.readouterr().out)

    assert queued["run"]["run_id"].startswith("run_")
    assert ledger.exists()
    assert "oracle_stub_enqueued" in ledger.read_text(encoding="utf-8")

    assert cli.main(["runs", "show", queued["run"]["run_id"], "--json"]) == 0
    run_show = json.loads(capsys.readouterr().out)
    assert run_show["run"]["run_id"] == queued["run"]["run_id"]


def test_cli_hybrid_pretty_marks_non_loopback_relay_as_fail(monkeypatch) -> None:
    cli, first_run = _load_cli_module()
    _clear_provider_env(monkeypatch)
    monkeypatch.setattr(first_run, "_LOCAL_PROBE_OPENER", _UnavailableProbeOpener())

    output = cli._format_hybrid_pretty(
        {
            "ok": True,
            "provider_execution": {"run": {"run_id": "run_fixture"}, "response": {"provider": "mock"}},
            "selected_route": {"route_strategy": "hybrid"},
            "local_node_runtime": {
                "ok": True,
                "relay": {"loopback_only": False},
                "http_proxy_fixture": {"status": "completed"},
            },
            "oracle_stub_execution": {"ok": True, "status": "completed", "request": {"run_id": "run_fixture", "route_strategy": "cloud_contract_candidate"}},
            "boundaries": {
                "message_body_persisted": False,
                "raw_prompt_sent_to_oracle_stub": False,
                "private_file_content_sent_to_oracle_stub": False,
            },
            "route_matrix": [],
            "actions_not_performed": [],
        },
        color="never",
    )

    assert "[FAIL] relay_loopback_only" in output
    assert "relay_loopback_only   : false" in output
