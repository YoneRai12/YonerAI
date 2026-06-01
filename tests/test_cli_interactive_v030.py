from __future__ import annotations

import io
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib

import pytest
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
        "YONERAI_MEMORY_STORE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)


def _redact_test_path(text: str | None, tmp_path: Path) -> str:
    redacted = (text or "").replace(str(tmp_path), "<tmp>")
    return redacted.replace(str(CLIENTS_CLI), "<repo>/clients/cli").replace(str(REPO_ROOT), "<repo>")


def _venv_purelib(python_bin: Path) -> Path:
    result = subprocess.run(
        [str(python_bin), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return Path(result.stdout.strip())


def _ensure_no_network_build_backend(python_bin: Path, tmp_path: Path) -> bool:
    check = subprocess.run(
        [str(python_bin), "-c", "import setuptools.build_meta"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if check.returncode == 0:
        return True

    spec = importlib.util.find_spec("setuptools")
    if spec is None or spec.origin is None:
        return False

    host_site = Path(spec.origin).resolve().parent.parent
    target_site = _venv_purelib(python_bin)
    for package_name in ("setuptools", "pkg_resources", "_distutils_hack"):
        source = host_site / package_name
        if source.exists():
            shutil.copytree(source, target_site / package_name, dirs_exist_ok=True)
    for dist_info in host_site.glob("setuptools-*.dist-info"):
        shutil.copytree(dist_info, target_site / dist_info.name, dirs_exist_ok=True)
    precedence = host_site / "distutils-precedence.pth"
    if precedence.exists():
        shutil.copy2(precedence, target_site / precedence.name)

    verify = subprocess.run(
        [str(python_bin), "-c", "import setuptools.build_meta"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert verify.returncode == 0, (
        "setuptools build backend seed failed:\n"
        f"STDOUT:\n{_redact_test_path(verify.stdout, tmp_path)}\n"
        f"STDERR:\n{_redact_test_path(verify.stderr, tmp_path)}"
    )
    return True


def test_cli_config_show_and_set_do_not_print_paths_or_store_secrets(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["config", "show", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "yonerai-cli-config/v0.6"
    assert report["secrets_supported"] is False
    assert report["path_persisted_in_output"] is False
    assert report["config"]["memory_enabled"] is True
    assert report["config"]["memory_default_scope"] == "local_private"
    assert report["config"]["memory_local_to_cloud_approval_required"] is True
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

    assert cli.main(["config", "set", "openai_data_sharing", "off", "--json"]) == 0
    privacy_flag = json.loads(capsys.readouterr().out)
    assert privacy_flag["config"]["openai_data_sharing_enabled"] is False

    assert cli.main(["config", "set", "memory_scope", "procedural", "--json"]) == 0
    memory_scope = json.loads(capsys.readouterr().out)
    assert memory_scope["config"]["memory_default_scope"] == "procedural"

    assert cli.main(["config", "set", "memory_local_to_cloud_approval_required", "off", "--json"]) == 2
    rejected = capsys.readouterr()
    assert "cannot be disabled" in rejected.err
    assert "Traceback" not in rejected.err


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
    assert yonerai_cli.__version__ == (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_cli_package_entry_point_exposes_yonerai_command() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "clients" / "cli" / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["yonerai"] == "yonerai_cli.cli:main"
    package_version = pyproject["project"]["version"]
    public_package_version = package_version.replace("a", "-alpha.").replace("b", "-beta.")
    assert public_package_version == (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_install_like_entry_point_starts_yonerai(tmp_path: Path) -> None:
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    python_bin = venv_dir / scripts_dir / ("python.exe" if os.name == "nt" else "python")
    yonerai_bin = venv_dir / scripts_dir / ("yonerai.exe" if os.name == "nt" else "yonerai")
    if not _ensure_no_network_build_backend(python_bin, tmp_path):
        pytest.skip("setuptools build backend is unavailable in both test host and fresh venv")

    env = {
        **os.environ,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "YONERAI_CLI_CONFIG_PATH": str(tmp_path / "cli-config.json"),
    }
    install_result = subprocess.run(
        [
            str(python_bin),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-build-isolation",
            "--no-deps",
            "-e",
            str(CLIENTS_CLI),
        ],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert install_result.returncode == 0, (
        f"install-like setup failed with exit code {install_result.returncode}.\n"
        f"STDOUT:\n{_redact_test_path(install_result.stdout, tmp_path)}\n"
        f"STDERR:\n{_redact_test_path(install_result.stderr, tmp_path)}"
    )

    try:
        result = subprocess.run(
            [str(yonerai_bin)],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            input="",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
    except OSError as exc:
        if getattr(exc, "winerror", None) != 4551:
            raise
        result = subprocess.run(
            [str(python_bin), "-m", "yonerai_cli"],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            input="",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=15,
        )

    assert result.returncode == 0, (
        f"yonerai entry point failed with exit code {result.returncode}.\n"
        f"STDOUT:\n{_redact_test_path(result.stdout, tmp_path)}\n"
        f"STDERR:\n{_redact_test_path(result.stderr, tmp_path)}"
    )
    assert "YonerAI Interactive CLI" in result.stdout
    assert "yonerai chat" in result.stdout
    assert "Traceback" not in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_readmes_document_install_and_start_yonerai() -> None:
    from yonerai_cli.install_planner import LATEST_STABLE_VERSION, TRUSTED_INSTALL_SCRIPT_SHA256

    for relative_path in ("README.md", "clients/cli/README.md"):
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

        assert "Install and start YonerAI" in text
        assert "GitHub Release" in text
        assert "Quick install" in text
        assert "Verified install" in text
        assert f"YonerAI-{LATEST_STABLE_VERSION}" in text
        assert "install.ps1.sha256" in text
        assert TRUSTED_INSTALL_SCRIPT_SHA256 in text
        assert "python --version" in text
        assert "python -m venv .venv" in text
        assert "python -m pip install -e clients/cli" in text
        assert "yonerai" in text
        assert "yonerai chat" in text
        assert "yonerai ask --auto" in text

    readme_jp = (REPO_ROOT / "README_JP.md").read_text(encoding="utf-8")
    assert "GitHub Release" in readme_jp
    assert "Quick install" in readme_jp
    assert "Verified install" in readme_jp
    assert "install.ps1.sha256" in readme_jp


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
    assert "提供元（AI接続元）: モック（テスト用）" in output
    assert "進行状況" in output
    assert "エージェント計画" in output
    assert "終了しました" in output
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
        _PlainStringIO(
            "/settings\n/providers\n/safety\n/tasks\n/local-llm\n/auth\n/sync\n/privacy\n/runs\n/live on\n/network on\n/update-notice on\n/provider mock\n/quit\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "設定" in output
    assert "カテゴリ" in output
    assert "/設定 記憶" in output
    assert "/選択 5 オン|オフ" in output
    assert "提供元（AI接続元）" in output
    assert "次に試す" in output
    assert "キーの値は表示・保存しません" in output
    assert "安全設定" in output
    assert "タスク" in output
    assert "ローカルLLMセットアップ" in output
    assert "検出状態" in output
    assert "確認した候補" in output
    assert "\n  検出状態" in output
    assert "\n    - Ollama" in output
    assert "認証" in output
    assert "同期" in output
    assert "プライバシー" in output
    assert "Google OAuth" in output
    assert "local -> cloud" in output
    assert "OpenAI共有トラフィック" in output
    assert "実行履歴" in output
    assert "設定を変更しました: ライブ接続（外部/ローカル実行）=オン" in output
    assert "設定を変更しました: ネットワーク（外部通信）=オン" in output
    assert "設定を変更しました: 更新通知（ローカルmanifest確認）=オン" in output
    assert "提供元（AI接続元）=モック（テスト用）" in output
    assert "Network" not in output
    assert "Changed setting" not in output
    assert str(tmp_path) not in output


def test_chat_memory_screen_is_available_in_japanese(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(tmp_path / "memory.jsonl"))
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/記憶\n/メモリ\n/memory\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert output.count("記憶") >= 3
    assert "local -> cloud自動同期: オフ" in output
    assert "cloud同期: オフ" in output
    assert "raw prompt保存: オフ" in output
    assert "yonerai memory add" in output
    assert str(tmp_path) not in output


def test_chat_memory_actions_are_available_from_interactive_cli(tmp_path: Path, monkeypatch, capsys) -> None:
    from ora_core.memory import LocalMemoryStore
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    memory_path = tmp_path / "memory.jsonl"
    existing = LocalMemoryStore(memory_path).add("prefer short local replies", scope="procedural")
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(memory_path))
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO(
            f"/memory list\n/memory add remember safe local preference\n/memory sync preview local-to-cloud\n"
            f"/memory forget {existing.id}\n/memory list\n/quit\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert existing.id in output
    assert "memory_id" in output
    assert "remember safe local preference" in output
    assert "local-to-cloud" in output
    assert "sync_performed" in output
    assert "cloud" in output
    assert str(tmp_path) not in output


def test_chat_memory_settings_can_be_changed_individually(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO(
            "/settings memory off\n/settings memory scope procedural\n/settings memory cloud-preview off\n"
            "/settings memory self-evolution on\n/settings memory local-to-cloud off\n/quit\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out
    stored = json.loads(config_path.read_text(encoding="utf-8"))

    assert stored["memory_enabled"] is False
    assert stored["memory_default_scope"] == "procedural"
    assert stored["memory_cloud_to_local_preview_enabled"] is False
    assert stored["memory_self_evolution_signal_enabled"] is True
    assert stored["memory_local_to_cloud_approval_required"] is True
    assert "local -> cloud" in output
    assert "public runtime" in output
    assert str(tmp_path) not in output


def test_chat_memory_cloud_preview_setting_blocks_cloud_to_local_preview(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(tmp_path / "memory.jsonl"))
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO(
            "/settings memory cloud-preview off\n"
            "/memory sync preview cloud-to-local\n"
            "/memory sync preview local-to-cloud\n"
            "/quit\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "cloud -> local memory preview: オフ" in output
    assert "同期previewは実行しません" in output
    assert output.count("sync_performed") == 1
    assert str(tmp_path) not in output


def test_chat_memory_settings_do_not_display_memory_contents(tmp_path: Path, monkeypatch, capsys) -> None:
    from ora_core.memory import LocalMemoryStore
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    memory_path = tmp_path / "memory.jsonl"
    LocalMemoryStore(memory_path).add("private preference should stay out of settings", scope="procedural")
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(memory_path))
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/settings memory\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "active_records: 1" in output
    assert "private preference should stay out of settings" not in output
    assert "mem_" not in output
    assert str(tmp_path) not in output


def test_chat_ask_auto_displays_memory_used_ids_without_raw_memory(tmp_path: Path, monkeypatch, capsys) -> None:
    from ora_core.memory import LocalMemoryStore
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    memory_path = tmp_path / "memory.jsonl"
    memory = LocalMemoryStore(memory_path).add("prefer concise private answer", scope="procedural")
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(memory_path))
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("hello\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "memory_used=" in output
    assert memory.id in output
    assert "prefer concise private answer" not in output
    assert str(tmp_path) not in output


def test_chat_japanese_commands_and_values_are_accepted(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/ヘルプ\n/設定\n/安全\n/認証\n/同期\n/プライバシー\n/提供元選択 モック\n/言語 日本語\n/終了\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "/設定" in output
    assert "/settings" not in output
    assert "ネットワーク（外部通信）" in output
    assert "ファイルアクセス（ファイル読み取り）" in output
    assert "ツール（操作機能）" in output
    assert "本番Googleログインはまだ有効にしていません" in output
    assert "local->cloud自動同期なし" in output
    assert "private/local内容の除外" in output
    assert "提供元（AI接続元）=モック（テスト用）" in output
    assert "言語=日本語" in output
    assert str(tmp_path) not in output


def test_chat_accepts_readable_japanese_commands_and_values(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO(
            "/状態\n/ホーム\n/設定\n/提供元選択 モック\n/言語 日本語\n/履歴記録 オン\n/更新通知 オン\n/終了\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out
    stored = json.loads(config_path.read_text(encoding="utf-8"))

    assert stored["provider_preference"] == "mock"
    assert stored["language"] == "ja"
    assert stored["ledger_enabled"] is True
    assert stored["update_notice_enabled"] is True
    assert output.count("YonerAI ミッションコントロール CLI") >= 2
    assert "Unknown command" not in output
    assert str(tmp_path) not in output


def test_chat_numbered_settings_and_ledger_are_usable_in_japanese(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    default_ledger = tmp_path / "runs.jsonl"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/設定\n/選択 2 モック\n/選択 5 オン\n/選択 6 オフ\n/選択 7 オフ\n/選択 9 オン\nhello\n/タスク\n/履歴\n/終了\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "設定を変更しました: 提供元（AI接続元）=モック（テスト用）" in output
    assert "設定を変更しました: 履歴記録（ローカル履歴）=オン" in output
    assert "設定を変更しました: ライブ接続（外部/ローカル実行）=オフ" in output
    assert "設定を変更しました: ネットワーク（外部通信）=オフ" in output
    assert "設定を変更しました: 更新通知（ローカルmanifest確認）=オン" in output
    assert "YonerAI ミッションコントロール" in output
    assert "タスク" in output
    assert "実行履歴" in output
    assert default_ledger.exists()
    assert str(tmp_path) not in output


def test_chat_settings_category_screens_are_individual_and_japanese(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(tmp_path / "memory.jsonl"))
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO(
            "/設定\n/設定 言語\n/設定 安全\n/設定 記憶\n/設定 更新\n/設定 認証\n/設定 プライバシー\n/終了\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "まとめて全設定を流しません" in output
    assert "設定: 言語" in output
    assert "安全設定" in output
    assert "記憶" in output
    assert "local -> cloud" in output
    assert "承認必須" in output
    assert "自動同期しません" in output
    assert "設定: 更新" in output
    assert "通常更新: 通知だけ" in output
    assert "クリティカル更新" in output
    assert "本番Googleログインはまだ有効にしていません" in output
    assert "OpenAI共有トラフィック" in output
    assert "Settings" not in output
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

    assert output.count("値が正しくありません") == 2
    assert "YonerAI ミッションコントロール" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output


def test_chat_setting_write_failure_is_not_reported_as_invalid_input(tmp_path: Path, monkeypatch) -> None:
    from yonerai_cli import interactive as interactive_module
    from yonerai_cli.config import ConfigError, DEFAULT_CONFIG, save_cli_config
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    config = dict(DEFAULT_CONFIG)
    config["language"] = "en"
    save_cli_config(config, config_path)
    providers_used: list[str] = []

    def fail_set_config(*_args: Any, **_kwargs: Any) -> dict[str, object]:
        raise ConfigError("fixture write failure")

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, lang: str) -> dict[str, Any]:
        providers_used.append(provider)
        return {
            "ok": True,
            "run": {"id": "run_test"},
            "response": {"output_text": f"handled {task}"},
            "auto": {"provider": provider, "route": "local_llm"},
            "live_call_performed": live,
            "ledger": {"path": ledger_path, "enabled": bool(ledger_path)},
        }

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    monkeypatch.setattr(interactive_module, "set_cli_config_value", fail_set_config)
    stdout = _PlainStringIO()

    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), provider="local", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO("/provider mock\nhello\n/quit\n"),
        stdout=stdout,
    )
    output = stdout.getvalue()

    assert rc == 0
    assert "Could not save config: fixture write failure" in output
    assert "Changed setting: provider=mock" not in output
    assert "Invalid value" not in output
    assert "YonerAI response" in output
    assert providers_used == ["local"]
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


def test_tui_empty_prompt_does_not_exit_session(tmp_path: Path, monkeypatch) -> None:
    import yonerai_cli.interactive as interactive_module
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    prompts = iter(["", "/quit"])

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        raise AssertionError("empty prompt must not run ask")

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    monkeypatch.setattr(interactive_module, "_can_use_prompt_toolkit", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(interactive_module, "prompt_line", lambda **_kwargs: next(prompts))

    stdout = _TTYStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(tmp_path / "cli-config.json"), lang="en"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_TTYStringIO(""),
        stdout=stdout,
    )

    assert rc == 0
    assert "Goodbye" in stdout.getvalue()


def test_startup_update_notice_is_non_blocking_and_repeated_after_task(tmp_path: Path) -> None:
    from yonerai_cli.config import DEFAULT_CONFIG, save_cli_config
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    config_path = tmp_path / "cli-config.json"
    config = dict(DEFAULT_CONFIG)
    config["language"] = "en"
    config["update_notice_enabled"] = True
    save_cli_config(config, config_path)
    asked: list[str] = []
    update_checks = 0

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, lang: str) -> dict[str, Any]:
        asked.append(task)
        return {
            "ok": True,
            "run": {"id": "run_update_notice"},
            "response": {"output_text": "ok"},
            "auto": {"provider": provider, "route": "instant_local"},
            "live_call_performed": live,
            "ledger": {"path": ledger_path, "enabled": bool(ledger_path)},
        }

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    def update_check(*_args: Any) -> dict[str, Any]:
        nonlocal update_checks
        update_checks += 1
        return {
            "update_available": True,
            "current_version": "0.6.4",
            "latest_stable": "0.6.5",
            "critical_update": True,
            "update_policy": {"active_session_behavior": "warn_only_do_not_interrupt"},
            "next_safe_command": "yonerai update check --pretty",
        }

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), lang="en", script=True, color="never"),
        InteractiveCallbacks(
            providers=providers,
            ask_auto=ask_auto,
            runs_list=runs_list,
            runs_show=runs_show,
            update_check=update_check,
        ),
        stdin=_PlainStringIO("hello\n/quit\n"),
        stdout=stdout,
    )
    output = stdout.getvalue()

    assert rc == 0
    assert asked == ["hello"]
    assert update_checks == 1
    assert "Startup update notice" in output
    assert "Post-task update notice" in output
    assert "critical_update: True" in output
    assert "no auto-apply" in output
    assert "local mock chat remains available" in output
    assert str(tmp_path) not in output


def test_network_off_forces_live_off_in_chat_session(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    calls: list[bool] = []

    def fake_interactive_ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, lang: str) -> dict[str, Any]:
        calls.append(live)
        return {
            "ok": True,
            "run": {"id": "run_test"},
            "response": {"output_text": "ok"},
            "auto": {"provider": provider, "mode": "safe"},
            "live_call_performed": live,
        }

    monkeypatch.setattr(cli, "_interactive_ask_auto", fake_interactive_ask_auto)
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/live on\n/network off\nhello\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "Changed setting: live_provider=True" in output
    assert "Changed setting: network=False" in output
    assert calls == [False]


def test_network_on_restores_existing_live_request_in_chat_session(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    calls: list[bool] = []

    def fake_interactive_ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, lang: str) -> dict[str, Any]:
        calls.append(live)
        return {
            "ok": True,
            "run": {"id": "run_test"},
            "response": {"output_text": "ok"},
            "auto": {"provider": provider, "mode": "safe"},
            "live_call_performed": live,
        }

    monkeypatch.setattr(cli, "_interactive_ask_auto", fake_interactive_ask_auto)
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/live on\n/network off\n/network on\nhello\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "Changed setting: network=False" in output
    assert "Changed setting: network=True" in output
    assert calls == [True]


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
    assert "実サブエージェント起動" in output
    assert "実サブエージェント起動: なし" in output
    assert "進行=" in output
    assert "経路=クラウド候補（ローカル開発スタブ）" in output
    assert ledger_path.exists()
    assert str(tmp_path) not in output


def test_safe_escapes_terminal_control_sequences() -> None:
    from yonerai_cli.interactive import _safe

    rendered = _safe("hello" + chr(27) + "[31mred" + chr(7))

    assert "\\x" + "1b" in rendered
    assert "\\x07" in rendered
    assert chr(27) not in rendered
    assert chr(7) not in rendered


def test_format_runs_counts_only_task_progress_events() -> None:
    from yonerai_cli.interactive import _format_runs

    report = {
        "runs": [
            {
                "run_id": "r-progress",
                "status": "completed",
                "task_summary": "ok",
                "events": [
                    {"name": "auto_runtime_decision", "status": "ok"},
                    {"name": "task_progress_classify", "status": "ok"},
                    {"name": "provider_response", "status": "ok"},
                    {"name": "task_progress_result", "status": "ok"},
                ],
            },
        ]
    }

    rendered = _format_runs(report, lang="en")

    assert "progress_events=2" in rendered
    assert "progress_events=4" not in rendered


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


def test_slash_command_summary_is_japanese_first() -> None:
    from yonerai_cli.tui import slash_command_summary, slash_command_words, tui_capability_report

    words = slash_command_words("ja")
    summary = slash_command_summary("ja")
    report = tui_capability_report()

    assert words[:12] == [
        "/状態",
        "/設定",
        "/モデル",
        "/提供元",
        "/安全",
        "/履歴",
        "/表示",
        "/タスク",
        "/エージェント",
        "/認証",
        "/同期",
        "/プライバシー",
    ]
    assert "/設定" in summary
    assert "/状態" in summary
    assert "/ホーム" in summary
    assert "/モデル" in summary
    assert "/認証" in summary
    assert "/同期" in summary
    assert "/プライバシー" in summary
    assert "/記憶" in summary
    assert "/記憶" in words
    assert "/メモリ" in words
    assert "/memory" not in words
    assert "/更新" in summary
    assert "/設定" in words
    assert "/状態" in words
    assert "/ホーム" in words
    assert words.count("/状態") == 1
    assert words.count("/ホーム") == 1
    assert "/提供元" in words
    assert "/更新" in words
    assert "/提供元選択" in words
    assert "/ファイルアクセス" in words
    assert "/ネットワーク" in words
    assert "/設定" in summary
    assert "/提供元" in summary
    assert "/設定 / /設定" not in summary
    assert "/提供元 / /提供元" not in summary
    assert "/settings" not in words
    assert "/settings" not in summary
    assert "/provider" not in words
    assert report["plain_fallback"] is True
    assert report["json_ansi_output"] is False
    assert report["japanese_alias_completion"] is True
    assert report["japanese_value_completion"] is True
    assert report["status_screen"] is True


def test_slash_value_completion_is_context_aware_and_japanese_first() -> None:
    from yonerai_cli.tui import slash_command_value_group, slash_value_meta, slash_value_words

    provider_words = slash_value_words("/提供元選択 ", "ja")
    provider_meta = slash_value_meta("/提供元選択 ", "ja")

    assert slash_command_value_group("/提供元選択 ") == "provider"
    assert provider_words[:4] == ["自動", "モック", "ローカル", "OpenAI互換"]
    assert provider_words[-2:] == ["アンソロピック", "ジェミニ"]
    assert "auto" not in provider_words
    assert "mock" not in provider_words
    assert "Anthropic" not in provider_words
    assert "Gemini" not in provider_words
    assert provider_meta["モック"] == "既定のテスト用提供元"

    assert slash_value_words("/選択 1 ", "ja") == ["日本語", "英語"]
    assert slash_value_words("/選択 2 ", "ja")[:3] == ["自動", "モック", "ローカル"]
    assert slash_value_words("/選択 5 ", "ja") == ["オン", "オフ"]
    assert slash_value_words("/モデル ", "ja")[:2] == ["自動", "llama3.1"]
    assert slash_value_words("/選択 8 ", "ja")[:2] == ["自動", "llama3.1"]
    assert slash_value_words("/ライブ ", "ja") == ["オン", "オフ"]
    assert slash_value_words("/更新通知 ", "ja") == ["オン", "オフ"]
    assert slash_command_value_group("/設定 ") == "settings_category"
    assert slash_value_words("/設定 ", "ja")[:4] == ["言語", "提供元", "モデル", "安全"]
    assert "memory" not in slash_value_words("/設定 ", "ja")
    assert "Anthropic" in slash_value_words("/provider ", "en")
    assert "Gemini" in slash_value_words("/provider ", "en")
    assert slash_value_words("/file-access ", "en")[:4] == [
        "workspace_only",
        "ワークスペース内のみ",
        "disabled",
        "無効",
    ]


def test_prompt_completer_switches_to_value_candidates_when_available() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from yonerai_cli.tui import _build_prompt_completer

    completer = _build_prompt_completer("ja")
    provider_candidates = [
        completion.text for completion in completer.get_completions(Document("/提供元選択 "), CompleteEvent())
    ]
    toggle_candidates = [
        completion.text for completion in completer.get_completions(Document("/選択 5 "), CompleteEvent())
    ]

    assert provider_candidates[:3] == ["自動", "モック", "ローカル"]
    assert "mock" not in provider_candidates
    assert "Anthropic" not in provider_candidates
    assert "アンソロピック" in provider_candidates
    assert toggle_candidates == ["オン", "オフ"]


def test_chat_models_and_update_commands_are_usable(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/\n/モデル\n/モデル 自動\n/モデル llama3.1\n/更新 releases/manifest.example.json\n/終了\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0

    output = capsys.readouterr().out
    stored = json.loads(config_path.read_text(encoding="utf-8"))
    assert "候補" in output
    assert "/設定" in output
    assert "/settings" not in output
    assert "モデル（AIモデル）" in output
    assert "ローカルLLM（PC内モデル）" in output
    assert "設定を変更しました: モデル（AIモデル）=llama3.1" in output
    assert "更新確認" in output
    assert "最新stable" in output
    assert "Quick install" in output
    assert "Verified install" in output
    assert "強制更新: なし" in output
    assert "自動適用: なし" in output
    assert "セキュリティ更新: なし" in output
    assert "クリティカル更新: なし" in output
    assert "基本ローカルmockチャット: 利用可" in output
    assert "実行しなかったこと" in output
    assert "no download" in output
    assert "no forced update" in output
    assert stored["model_preference"] == "llama3.1"
    assert str(tmp_path) not in output
    assert chr(27) + "[" not in output


def test_chat_update_command_handles_missing_manifest_without_crashing(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    missing_manifest = tmp_path / "missing-manifest.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO(f"/更新 {missing_manifest}\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "更新確認に失敗しました" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output


def test_chat_update_command_accepts_spaced_manifest_path(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    manifest_dir = tmp_path / "My Releases"
    manifest_dir.mkdir()
    source = REPO_ROOT / "releases" / "manifest.example.json"
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/更新 My Releases/manifest.json\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "更新確認" in output
    assert "最新stable" in output
    assert "no download" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output


def test_config_set_model_is_supported_and_rejects_url_values(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["config", "set", "model", "llama3.1", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["config"]["model_preference"] == "llama3.1"
    assert str(tmp_path) not in json.dumps(output)

    assert cli.main(["config", "set", "model", "http://127.0.0.1:11434", "--json"]) == 2
    captured = capsys.readouterr()
    assert "model must be auto or a simple provider model id" in captured.err
    assert "Traceback" not in captured.err
