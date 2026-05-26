from __future__ import annotations

import io
import json
import sys
import tomllib
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

    assert report["schema_version"] == "yonerai-cli-config/v0.4"
    assert report["secrets_supported"] is False
    assert report["path_persisted_in_output"] is False
    assert str(tmp_path) not in json.dumps(report)

    assert cli.main(["config", "set", "language", "ja", "--json"]) == 0
    updated = json.loads(capsys.readouterr().out)

    assert updated["config"]["language"] == "ja"
    assert "no provider key storage" in updated["actions_not_performed"]
    assert "api_key" not in config_path.read_text(encoding="utf-8").lower()

    assert cli.main(["config", "set", "ledger", "on", "--json"]) == 0
    ledger_enabled = json.loads(capsys.readouterr().out)
    assert ledger_enabled["config"]["ledger_enabled"] is True
    assert str(tmp_path) not in json.dumps(ledger_enabled)


def test_cli_config_write_failure_is_controlled(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"

    def fail_write_text(*_args, **_kwargs):
        raise OSError("fixture write failure")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    assert cli.main(["config", "set", "language", "ja", "--config-path", str(config_path)]) == 2

    captured = capsys.readouterr()
    assert "YonerAI CLI config could not be written" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err


def test_cli_package_version_normalizes_pep440_prerelease() -> None:
    import yonerai_cli

    assert yonerai_cli._to_public_semver("0.3.0a1") == "0.3.0-alpha.1"
    assert yonerai_cli._to_public_semver("0.3.0b2") == "0.3.0-beta.2"
    assert yonerai_cli._to_public_semver("0.3.0rc3") == "0.3.0-rc.3"
    assert yonerai_cli._to_public_semver("0.3.0-alpha.1") == "0.3.0-alpha.1"


def test_cli_package_entry_point_exposes_yonerai_command() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "clients" / "cli" / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["yonerai"] == "yonerai_cli.cli:main"


def test_readmes_document_install_and_start_yonerai() -> None:
    for relative_path in ("README.md", "README_JP.md", "clients/cli/README.md"):
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

        assert "Install and start YonerAI" in text
        assert "python -m pip install -e clients/cli" in text
        assert "yonerai" in text
        assert "yonerai chat" in text
        assert "yonerai ask --auto" in text


def test_cli_without_args_has_non_tty_interactive_fallback(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(tmp_path / "cli-config.json"))

    assert cli.main([]) == 0
    output = capsys.readouterr().out

    assert "YonerAI Interactive CLI" in output
    assert "対話画面は起動しません" in output
    assert str(tmp_path) not in output


def test_cli_without_args_tty_runs_first_launch_language_selection(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setattr(sys, "stdin", _TTYStringIO("1\n/終了\n"))

    assert cli.main([]) == 0
    output = capsys.readouterr().out

    assert "YonerAI language / 表示言語" in output
    assert "YonerAI ミッションコントロール CLI" in output
    assert "日本語モード" in output
    assert json.loads(config_path.read_text(encoding="utf-8"))["language"] == "ja"
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

    assert "YonerAI ミッションコントロール CLI" in output
    assert "YonerAI ミッションコントロール" in output
    assert "実行ID（run_id）" in output
    assert "プロバイダー（AI接続先）: モック（テスト用）" in output
    assert "進行状況" in output
    assert "エージェント計画" in output
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
    assert "/選択 5 オン" in output
    assert "履歴記録（ローカル履歴）" in output
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


def test_chat_numbered_settings_and_ledger_are_usable_in_japanese(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    default_ledger = tmp_path / "runs.jsonl"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/設定\n/選択 2 モック\n/選択 5 オン\nhello\n/履歴\n/終了\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "設定を変更しました: プロバイダー（AI接続先）=モック（テスト用）" in output
    assert "設定を変更しました: 履歴記録（ローカル履歴）=オン" in output
    assert "YonerAI ミッションコントロール" in output
    assert "実行履歴" in output
    assert default_ledger.exists()
    assert str(tmp_path) not in output


def test_chat_invalid_language_and_provider_keep_shell_alive(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/language xx\n/provider nope\nhello\n/quit\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert output.count("値が不正です") == 2
    assert "YonerAI ミッションコントロール" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output


def test_chat_setting_write_failure_is_not_reported_as_invalid_input(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli
    from yonerai_cli import interactive as interactive_module
    from yonerai_cli.config import ConfigError, DEFAULT_CONFIG, save_cli_config

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    config = dict(DEFAULT_CONFIG)
    config["language"] = "en"
    save_cli_config(config, config_path)

    def fail_set_config(*_args: Any, **_kwargs: Any) -> dict[str, object]:
        raise ConfigError("fixture write failure")

    monkeypatch.setattr(interactive_module, "set_cli_config_value", fail_set_config)
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/provider mock\nhello\n/quit\n"))

    assert cli.main(["chat", "--script", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "Could not save config: fixture write failure" in output
    assert "Invalid value" not in output
    assert "YonerAI response" in output
    assert "Traceback" not in output
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


def test_chat_agents_and_run_show_explain_mission_control_state(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    ledger_path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/履歴記録 オン\nhard public reasoning over public API docs\n/エージェント\n/履歴\n/終了\n"),
    )

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

    assert "エージェント計画" in output
    assert "計画係" in output
    assert "調査係" in output
    assert "レビュー係" in output
    assert "実サブエージェント起動: なし" in output
    assert "進行=" in output
    assert "経路=クラウド候補（ローカル開発スタブ）" in output
    assert ledger_path.exists()
    assert str(tmp_path) not in output


def test_safe_escapes_terminal_control_sequences() -> None:
    from yonerai_cli.interactive import _safe

    rendered = _safe("hello\x1b[31mred\x07")

    assert "\\x1b" in rendered
    assert "\\x07" in rendered
    assert "\x1b" not in rendered
    assert "\x07" not in rendered


def test_format_runs_escapes_control_sequences() -> None:
    from yonerai_cli.interactive import _format_runs

    report = {
        "runs": [
            {"run_id": "r-1", "status": "completed", "task_summary": "ok\x1b]52;c;dGVzdA==\x07"},
        ]
    }

    rendered = _format_runs(report, lang="en")

    assert "\\x1b" in rendered
    assert "\\x07" in rendered
    assert "\x1b" not in rendered
    assert "\x07" not in rendered
