from __future__ import annotations

import io
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


class _TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


class _PlainStringIO(io.StringIO):
    def isatty(self) -> bool:
        return False


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


def test_cli_config_show_and_set_do_not_print_paths_or_store_secrets(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["config", "show", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "yonerai-cli-config/v0.3"
    assert report["secrets_supported"] is False
    assert report["path_persisted_in_output"] is False
    assert str(tmp_path) not in json.dumps(report)

    assert cli.main(["config", "set", "language", "ja", "--json"]) == 0
    updated = json.loads(capsys.readouterr().out)

    assert updated["config"]["language"] == "ja"
    assert "no provider key storage" in updated["actions_not_performed"]
    assert "api_key" not in config_path.read_text(encoding="utf-8").lower()


def test_cli_without_args_has_non_tty_interactive_fallback(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))

    assert cli.main([]) == 0
    output = capsys.readouterr().out

    assert "YonerAI Interactive CLI" in output
    assert "対話画面は起動しません" in output
    assert str(tmp_path) not in output


def test_chat_script_runs_ask_auto_and_persists_language_without_path_leak(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    ledger_path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("hello\n/quit\n"))

    assert (
        cli.main(
            [
                "chat",
                "--script",
                "--lang",
                "ja",
                "--config-path",
                str(config_path),
                "--ledger",
                str(ledger_path),
                "--color",
                "never",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out

    assert "YonerAI Interactive CLI v0.3 alpha" in output
    assert "YonerAI 応答" in output
    assert "実行ID（run_id）" in output
    assert "プロバイダー（AI接続先）: モック（テスト用）" in output
    assert "終了します" in output
    assert config_path.exists()
    assert ledger_path.exists()
    assert str(tmp_path) not in output


def test_chat_accepts_english_commands_while_showing_japanese_ui(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/settings\n/providers\n/safety\n/runs\n/provider mock\n/quit\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "設定" in output
    assert "プロバイダー" in output
    assert "安全設定" in output
    assert "実行履歴" in output
    assert "プロバイダー（AI接続先）=モック（テスト用）" in output
    assert "Network" not in output
    assert "Changed setting" not in output
    assert str(tmp_path) not in output


def test_chat_japanese_commands_and_values_are_accepted(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/ヘルプ\n/設定\n/安全\n/提供元選択 モック\n/言語 日本語\n/終了\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "/設定" in output
    assert "/settings" not in output
    assert "ネットワーク（外部通信）" in output
    assert "ファイルアクセス（ファイル読み取り）" in output
    assert "ツール（操作機能）" in output
    assert "プロバイダー（AI接続先）=モック（テスト用）" in output
    assert "言語=日本語" in output
    assert str(tmp_path) not in output


def test_first_launch_language_selection_persists_choice(tmp_path: Path) -> None:
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        raise AssertionError("no ask should run")

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    config_path = tmp_path / "cli-config.json"
    stdin = _TTYStringIO("2\n/quit\n")
    stdout = _TTYStringIO()

    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path)),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=stdin,
        stdout=stdout,
    )

    assert rc == 0
    output = stdout.getvalue()
    assert "YonerAI language / 表示言語" in output
    assert "English mode" in output
    assert json.loads(config_path.read_text(encoding="utf-8"))["language"] == "en"
