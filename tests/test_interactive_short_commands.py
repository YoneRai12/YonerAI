from __future__ import annotations

import io
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = REPO_ROOT / "clients" / "cli"
CORE_SRC = REPO_ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


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
        "YONERAI_MEMORY_STORE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)


def test_coerce_interactive_short_command_maps_safe_shell_words_to_slash() -> None:
    from yonerai_cli.interactive import _coerce_interactive_short_command

    assert _coerce_interactive_short_command("login") == "/login"
    assert _coerce_interactive_short_command("ログイン") == "/ログイン"
    assert _coerce_interactive_short_command("whoami") == "/whoami"
    assert _coerce_interactive_short_command("アカウント") == "/アカウント"
    assert _coerce_interactive_short_command("sessions") == "/sessions"
    assert _coerce_interactive_short_command("セッション") == "/セッション"
    assert _coerce_interactive_short_command("projects") == "/projects"
    assert _coerce_interactive_short_command("プロジェクト") == "/プロジェクト"
    assert _coerce_interactive_short_command("settings safety") == "/settings safety"
    assert _coerce_interactive_short_command("設定 安全") == "/設定 安全"
    assert _coerce_interactive_short_command("update beta") == "/update beta"
    assert _coerce_interactive_short_command("更新 ベータ版") == "/更新 ベータ版"
    assert _coerce_interactive_short_command("ping") == "/ping"
    assert _coerce_interactive_short_command("疎通") == "/疎通"
    assert _coerce_interactive_short_command("rate-limit") == "/rate-limit"
    assert _coerce_interactive_short_command("レート") == "/レート"
    assert _coerce_interactive_short_command("revoke session_123") == "/revoke session_123"
    assert _coerce_interactive_short_command("loguin") == "/login"
    assert _coerce_interactive_short_command("login したい") is None


def test_resolve_submitted_slash_command_keeps_short_queries_but_fixes_safe_unique_matches() -> None:
    from yonerai_cli.tui.keymap import resolve_submitted_slash_command

    assert resolve_submitted_slash_command("/loguin") == "/login"
    assert resolve_submitted_slash_command("/session") == "/sessions"
    assert resolve_submitted_slash_command("/l") is None
    assert resolve_submitted_slash_command("/lo") is None


def test_chat_script_accepts_bare_login_inside_interactive_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("login\nquit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "ログイン" in output
    assert "ログイン (/ログイン / login)" in output
    assert "yonerai login" not in output
    assert str(tmp_path) not in output


def test_chat_script_recovers_from_corrupt_local_config(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    config_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "設定を読み込めなかったため、既定値で起動しました。" in output
    assert "YonerAI CLI config could not be read as JSON" not in output
    assert str(tmp_path) not in output


def test_chat_script_accepts_fuzzy_english_slash_login_inside_interactive_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/loguin\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "ログイン" in output
    assert "ログイン (/ログイン / login)" in output
    assert "不明なコマンド" not in output
    assert str(tmp_path) not in output


def test_chat_script_shows_matches_for_short_english_slash_fragment(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/lo\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "/login" in output
    assert "/local-llm" in output
    assert "不明なコマンド" not in output
    assert str(tmp_path) not in output


def test_chat_script_accepts_bare_update_channel_inside_interactive_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("update beta\nquit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "更新確認" in output
    assert "チャンネル: ベータ版" in output
    assert "yonerai update beta" not in output
    assert str(tmp_path) not in output


def test_chat_script_accepts_japanese_local_llm_slash_command(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/ローカルLLM\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "ローカルLLM" in output
    assert "Ollama" in output
    assert "LM Studio" in output
    assert "次: Ollama か LM Studio を起動して /ローカルLLM" in output
    assert "個別案内: /ローカルLLM ollama / lmstudio" in output
    assert "不明なコマンド" not in output
    assert str(tmp_path) not in output


def test_chat_script_accepts_japanese_update_slash_command(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/更新\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "更新" in output
    assert "安定版" in output
    assert "ベータ版" in output
    assert "/更新 安定版 (/update stable)" in output
    assert "不明なコマンド" not in output
    assert str(tmp_path) not in output


def test_chat_script_accepts_bare_japanese_settings_inside_interactive_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("設定 安全\n終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "シェル実行（PC操作）: 任意コマンドは無効" in output
    assert "クラウド候補: 非公開ファイルやローカルファイルは送りません" in output
    assert str(tmp_path) not in output


def test_help_mentions_in_app_slash_short_commands() -> None:
    from yonerai_cli.screens.help import _help

    rendered = _help("ja")

    assert "`/ログイン`" in rendered
    assert "`/アカウント`" in rendered
    assert "`/セッション`" in rendered
    assert "`/プロジェクト`" in rendered
    assert "`/疎通`" in rendered
    assert "`/レート`" in rendered
    assert "`/更新`" in rendered
    assert "`/login`" in rendered
    assert "`/update`" in rendered


def test_startup_prelude_mentions_in_app_bare_short_commands(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli.interactive import _startup_prelude

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    config = {"_runtime_config_path": str(tmp_path / "cli-config.json")}

    rendered = _startup_prelude(config=config, lang="ja", update_notice=None)

    assert "login" in rendered
    assert "/ログイン" in rendered
    assert "whoami" not in rendered
    assert "sessions" not in rendered
    assert str(tmp_path) not in rendered
