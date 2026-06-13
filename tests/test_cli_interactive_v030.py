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

    assert report["schema_version"] == "yonerai-cli-config/v0.7"
    assert report["secrets_supported"] is False
    assert report["path_persisted_in_output"] is False
    assert report["config"]["agent_mode"] == "plan_readonly"
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
    assert "会話: そのまま入力" in output
    assert "コマンド: / で候補を開く" in output
    assert "近道:" in output
    assert "/ /" not in output
    assert json.loads(config_path.read_text(encoding="utf-8"))["language"] == "ja"
    assert str(tmp_path) not in output


def test_first_launch_auth_onboarding_can_show_staging_contract(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    # First-launch order: language -> theme -> auth onboarding -> prompt.
    monkeypatch.setattr(sys, "stdin", _TTYStringIO("2\n2\n2\n/quit\n"))

    assert cli.main([]) == 0
    output = capsys.readouterr().out
    stored = json.loads(config_path.read_text(encoding="utf-8"))

    assert "YonerAI account / auth" in output
    assert "Use local only" in output
    assert "Check Google login" in output
    assert "Uses staging if configured, otherwise dry-run." in output
    assert "staging_origin: https://api-staging.yonerai.com" in output
    assert "google_login: available (staging)" in output
    assert "no Google token storage / no refresh token storage / no private auto-upload" in output
    assert "/login" in output
    assert stored["language"] == "en"
    assert stored["auth_onboarding_seen"] is True
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

    assert "会話: そのまま入力" in output
    assert "経路: ローカルで即時実行" in output
    assert "提供元: モック（テスト用）" in output
    assert "run_id:" in output
    assert "YonerAI mock provider response" in output
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
            "/settings\n/providers\n/safety\n/tasks\n/local-llm\n/auth\n/api\n/sync\n/privacy\n/runs\n/live on\n/network on\n/update-notice on\n/provider mock\n/quit\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "設定" in output
    assert "開く:" in output
    assert "/選択 <番号>" in output
    assert "現在: 日本語" in output
    assert "提供元（AI接続元）" in output
    assert "必要なものだけ明示して有効化します。" in output
    assert "キーの値は表示・保存しません" in output
    assert "安全設定" in output
    assert "タスク" in output
    assert "ローカルLLM:" in output
    assert ("検出: Ollama" in output) or ("アプリあり / 未起動" in output) or ("未検出" in output)
    assert ("次: /ローカルLLM 使う" in output) or ("次: /ローカルLLM" in output)
    assert "認証" in output
    assert "同期" in output
    assert "プライバシー" in output
    assert "Google α-staging" in output
    assert "認証 / API" in output
    assert "接続先: https://api-staging.yonerai.com" in output
    assert "境界: token保存なし / refresh保存なし / private自動アップロードなし" in output
    assert "実行履歴" in output
    assert "設定を変更しました: ライブ接続（外部/ローカル実行）=オン" in output
    assert "設定を変更しました: ネットワーク（外部通信）=オン" in output
    assert "設定を変更しました: 更新通知（安定版/ベータ版確認）=オン" in output
    assert "提供元（AI接続元）=モック（テスト用）" in output
    assert "Network" not in output
    assert "Changed setting" not in output
    assert str(tmp_path) not in output


def test_chat_auth_screen_shows_staging_and_sync_boundaries(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/auth\n/sync\n/privacy\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "Auth" in output
    assert "state: not linked (staging only) / Google alpha-staging" in output
    assert "account: not linked" in output
    assert "staging_origin: https://api-staging.yonerai.com" in output
    assert "guide: use `/login` (Japanese: `/ログイン`) to start browser sign-in" in output
    assert "Sync" in output
    assert "local_to_cloud_requires_approval: True" in output
    assert "private_content_exclusion_active: True" in output
    assert "openai_shared_traffic_enabled: False" in output
    assert str(tmp_path) not in output


def test_chat_auth_screen_shows_linked_staging_claim_without_raw_email(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.auth_session_service import build_staging_auth_claim, save_staging_auth_claim

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    save_staging_auth_claim(
        build_staging_auth_claim(
            origin="https://api-staging.yonerai.com",
            account={"email": "owner@example.com", "display_name": "Owner"},
        ),
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/auth\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "state: previously linked / Google alpha-staging" in output
    assert "account: o***@example.com" in output
    assert "owner@example.com" not in output
    assert str(tmp_path) not in output


def test_chat_auth_screen_uses_display_name_when_email_is_not_linked(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services.auth_session_service import build_staging_auth_claim, save_staging_auth_claim

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    save_staging_auth_claim(
        build_staging_auth_claim(
            origin="https://api-staging.yonerai.com",
            account={"display_name": "linked staging account"},
        ),
        config_path=config_path,
    )
    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/auth\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "state: previously linked / Google alpha-staging" in output
    assert "account: saved staging account" in output
    assert "account: not linked" not in output
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


def test_chat_settings_do_not_persist_runtime_config_path(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/settings memory off\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    _ = capsys.readouterr()
    stored = json.loads(config_path.read_text(encoding="utf-8"))

    assert "_runtime_config_path" not in stored
    assert str(tmp_path) not in json.dumps(stored, sort_keys=True)


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


def test_chat_memory_off_blocks_memory_add(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    memory_path = tmp_path / "memory.jsonl"
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(memory_path))
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO("/settings memory off\n/memory add should not persist\n/memory list\n/quit\n"),
    )

    assert cli.main(["chat", "--script", "--lang", "en", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "Memory is off" in output
    assert "should not persist" not in output
    assert "count: 0" in output
    assert not memory_path.exists() or memory_path.read_text(encoding="utf-8") == ""
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
    assert "/settings" in output
    assert "ネットワーク（外部通信）" in output
    assert "ファイルアクセス（ファイル読み取り）" in output
    assert "ツール（操作機能）" in output
    assert "本番: 使えません" in output
    assert "local→cloud自動同期なし" in output
    assert "private/local 除外" in output
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
    assert "会話: そのまま入力" in output
    assert "Unknown command" not in output
    assert str(tmp_path) not in output


def test_chat_script_reports_mojibake_hint_for_question_mark_slash_command(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/??\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "文字化けした可能性があります" in output
    assert "/quit" in output
    assert "/update beta" in output
    assert "$OutputEncoding" in output
    assert "不明なコマンドです" not in output
    assert "Traceback" not in output


def test_chat_numbered_settings_and_ledger_are_usable_in_japanese(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    default_ledger = tmp_path / "runs.jsonl"
    monkeypatch.setattr(
        sys,
        "stdin",
        _PlainStringIO(
            "/設定\n/選択 2 モック\n/選択 5 オン\n/選択 6 オフ\n/選択 7 オフ\n/選択 9 オン\nhello\n/タスク\n/履歴\n/終了\n"
        ),
    )

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "設定を変更しました: 提供元（AI接続元）=モック（テスト用）" in output
    assert "設定を変更しました: 履歴記録（ローカル履歴）=オン" in output
    assert "設定を変更しました: ライブ接続（外部/ローカル実行）=オフ" in output
    assert "設定を変更しました: ネットワーク（外部通信）=オフ" in output
    assert "設定を変更しました: 更新通知（安定版/ベータ版確認）=オン" in output
    assert "経路: ローカルで即時実行" in output
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

    assert "次: /設定 <項目名>  または  /選択 <番号>" in output
    assert "設定: 言語" in output
    assert "安全設定" in output
    assert "記憶" in output
    assert "local→cloud: 承認必須 / 自動同期なし" in output
    assert "承認必須" in output
    assert "cloud→local preview" in output
    assert "設定: 更新" in output
    assert "通常: 通知だけ" in output
    assert "クリティカル: 次回起動時に先に表示" in output
    assert "Google α-staging" in output
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
    assert "経路: ローカルで即時実行" in output
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
    assert "handled hello" in output
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
    stdin = _TTYStringIO("2\n1\n/quit\n")
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
    assert "YonerAI account / auth" in output
    assert "Local CLI works without login" in output
    assert "chat: type normally" in output
    assert "commands: use / for suggestions" in output
    stored = json.loads(config_path.read_text(encoding="utf-8"))
    assert stored["language"] == "en"
    assert stored["auth_onboarding_seen"] is True


def test_first_launch_google_auth_onboarding_is_dry_run_only(tmp_path: Path) -> None:
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
    # First-launch order: language -> theme -> auth onboarding -> prompt.
    stdin = _TTYStringIO("1\n2\n2\n/終了\n")
    stdout = _TTYStringIO()

    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=stdin,
        stdout=stdout,
    )

    assert rc == 0
    output = stdout.getvalue()
    assert "YonerAI account / 認証" in output
    assert "Googleログイン dry-run" in output
    assert "本番ログイン: 使えません" in output
    assert "Google token保存なし / refresh token保存なし / private自動アップロードなし" in output
    assert "/ログイン" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output
    stored = json.loads(config_path.read_text(encoding="utf-8"))
    assert stored["language"] == "ja"
    assert stored["auth_onboarding_seen"] is True
    assert stored["google_auth_enabled"] is False


def test_existing_language_config_skips_first_launch_prompt(tmp_path: Path) -> None:
    from yonerai_cli.config import DEFAULT_CONFIG, save_cli_config
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
    config = dict(DEFAULT_CONFIG)
    config["language"] = "ja"
    save_cli_config(config, config_path)

    stdout = _TTYStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path)),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_TTYStringIO("/終了\n"),
        stdout=stdout,
    )
    output = stdout.getvalue()

    assert rc == 0
    assert "YonerAI language / 表示言語" not in output
    assert "YonerAI account / 認証" not in output
    assert "会話: そのまま入力" in output
    assert json.loads(config_path.read_text(encoding="utf-8"))["language"] == "ja"
    assert str(tmp_path) not in output


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


def test_agent_console_palette_modes_permissions_and_mentions(tmp_path: Path) -> None:
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    asked: list[str] = []

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(task: str, *_args: Any) -> dict[str, Any]:
        asked.append(task)
        return {"ok": True}

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(tmp_path / "cli-config.json"), lang="ja", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO(
            "/\n"
            "/コマンド\n"
            "/入力\n"
            "/コンテキスト\n"
            "/進行\n"
            "/モード レビュー\n"
            "/計画\n"
            "/レビュー\n"
            "/権限\n"
            "/権限 自動安全\n"
            "/mode plan\n"
            "/mode read-only\n"
            "/select 10 build\n"
            "/permissions ask-before-risky\n"
            "@planner 公開リリースの計画\n"
            "@reviewer 安全境界を確認\n"
            "@implementer 実装候補を整理\n"
            "@tester テスト観点を整理\n"
            "/終了\n"
        ),
        stdout=stdout,
    )
    output = stdout.getvalue()

    assert rc == 0
    assert "コマンドパレット" in output
    assert "/ で候補を開きます。" in output
    assert "まずはよく使う短いコマンドだけを前に出します。" in output
    assert "/l や /p のように打つと、その場で絞り込みます" in output
    assert "Enter で実行、Esc で閉じます。" in output
    assert "コンテキスト" in output
    assert "@file は未実装" in output
    assert "@implementer" in output
    assert "@tester" in output
    assert "秘匿済み要約" in output
    assert "cloud候補へ渡しません" in output
    assert "進行表示" in output
    assert "経路選択" in output
    assert "提供元選択" in output
    assert "/モード" in output
    assert "/計画" in output
    assert "/レビュー" in output
    assert "/権限" in output
    assert "作業モード" in output
    assert "計画（読み取り専用）" in output
    assert "レビュー" in output
    assert "権限と承認" in output
    assert "自動安全" in output
    assert "危険時確認" in output
    assert "サブエージェント計画" in output
    assert "@planner" in output
    assert "@reviewer" in output
    assert "実装担当" in output
    assert "テスト担当" in output
    assert "実サブエージェント起動: なし" in output
    assert asked == []
    assert "値が正しくありません" not in output
    assert str(tmp_path) not in output


def test_permissions_dry_run_only_resets_read_only_approval(tmp_path: Path) -> None:
    from yonerai_cli.config import load_cli_config
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(_task: str, *_args: Any) -> dict[str, Any]:
        return {"ok": True}

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    config_path = tmp_path / "cli-config.json"
    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), lang="en", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO("/permissions read-only\n/permissions dry-run-only\n/permissions\n/quit\n"),
        stdout=stdout,
    )

    assert rc == 0
    stored = load_cli_config(config_path)
    assert stored["agent_mode"] == "plan_readonly"
    assert stored["approval_mode"] == "prompt"
    output = stdout.getvalue()
    assert "permissions=dry_run_only" in output
    assert "approval: prompt" in output


def test_compact_chat_turn_keeps_route_preview_and_answer_compact() -> None:
    from yonerai_cli.interactive import _format_chat_turn, _format_chat_view

    report = {
        "auto": {"route": "instant_local"},
        "provider": {"provider_id": "mock"},
        "run": {"run_id": "run_test_123"},
        "response": {"output_text": "YonerAI mock provider response."},
    }

    block = _format_chat_turn("こんにちは", report, lang="ja", compact=True)
    assert "あなた:" not in block
    assert "YonerAI:" not in block
    assert "経路:" in block
    assert "提供元:" in block
    assert "run_id: run_test_123" in block
    assert "YonerAI mock provider response." in block

    view = _format_chat_view([block], lang="ja")
    assert "会話" not in view
    assert "そのまま入力して会話します" not in view
    assert "YonerAI mock provider response." in view


def test_permission_profiles_disable_live_and_network_execution(tmp_path: Path) -> None:
    from yonerai_cli.config import load_cli_config
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    live_calls: list[bool] = []

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(_task: str, _provider: str, live: bool, *_args: Any) -> dict[str, Any]:
        live_calls.append(live)
        return {"ok": True, "response": {"output_text": "ok"}, "auto": {"route": "instant_local"}}

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    config_path = tmp_path / "cli-config.json"
    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), lang="en", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO(
            "/live on\n"
            "/network on\n"
            "/permissions read-only\n"
            "public task after read-only\n"
            "/permissions dry-run-only\n"
            "public task after dry-run-only\n"
            "/quit\n"
        ),
        stdout=stdout,
    )

    assert rc == 0
    stored = load_cli_config(config_path)
    assert stored["live_provider_enabled"] is False
    assert stored["network_enabled"] is False
    assert stored["agent_mode"] == "plan_readonly"
    assert stored["approval_mode"] == "prompt"
    assert live_calls == [False, False]


def test_safety_and_permissions_render_effective_live_state(tmp_path: Path) -> None:
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        raise AssertionError("safety display test must not execute ask")

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(tmp_path / "cli-config.json"), lang="en", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO("/live on\n/network on\n/safety\n/permissions\n/quit\n"),
        stdout=stdout,
    )

    assert rc == 0
    output = stdout.getvalue()
    assert "network: explicitly enabled" in output
    assert "live provider: off" in output
    assert "live: off" in output


def test_permission_profile_display_considers_cli_live_option(tmp_path: Path) -> None:
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        raise AssertionError("permission display test must not execute ask")

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(
            config_path=str(tmp_path / "cli-config.json"), lang="en", script=True, color="never", live=True
        ),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO("/network on\n/permissions auto-safe\n/quit\n"),
        stdout=stdout,
    )

    assert rc == 0
    output = stdout.getvalue()
    assert "permissions=auto_safe" in output
    assert "agent_mode: build_safe" in output
    assert "live: on" in output


def test_permission_profile_display_preserves_session_live_off(tmp_path: Path) -> None:
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        raise AssertionError("permission display test must not execute ask")

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(
            config_path=str(tmp_path / "cli-config.json"), lang="en", script=True, color="never", live=True
        ),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO("/live off\n/network on\n/permissions auto-safe\n/permissions\n/quit\n"),
        stdout=stdout,
    )

    assert rc == 0
    output = stdout.getvalue()
    assert "permissions=auto_safe" in output
    assert "agent_mode: build_safe" in output
    assert "live: on" not in output
    assert output.count("live: off") >= 2


def test_settings_safety_renders_effective_live_state(tmp_path: Path) -> None:
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        raise AssertionError("settings safety display test must not execute ask")

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(tmp_path / "cli-config.json"), lang="en", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO(
            "/permissions auto-safe\n/live on\n/network on\n/approval deny\n/settings safety\n/quit\n"
        ),
        stdout=stdout,
    )

    assert rc == 0
    output = stdout.getvalue()
    assert "network: explicitly enabled" in output
    assert "live provider: off" in output
    assert "live provider: explicitly enabled" not in output


def test_plan_review_commands_preview_task_without_execution(tmp_path: Path) -> None:
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    asked: list[str] = []

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(task: str, *_args: Any) -> dict[str, Any]:
        asked.append(task)
        return {"ok": True}

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(tmp_path / "cli-config.json"), lang="en", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO(
            "/plan draft release gate\n"
            "/review inspect safety boundary\n"
            "@researcher gather public docs\n"
            "@implementer draft safe patch\n"
            "@tester verify public smoke\n"
            "/quit\n"
        ),
        stdout=stdout,
    )
    output = stdout.getvalue()

    assert rc == 0
    assert asked == []
    assert "mention: @planner / planner" in output
    assert "request_summary: draft release gate" in output
    assert "mention: @reviewer / reviewer" in output
    assert "request_summary: inspect safety boundary" in output
    assert "mention: @researcher / researcher" in output
    assert "request_summary: gather public docs" in output
    assert "mention: @implementer / implementer" in output
    assert "request_summary: draft safe patch" in output
    assert "mention: @tester / tester" in output
    assert "request_summary: verify public smoke" in output
    assert str(tmp_path) not in output


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


def test_update_notice_off_takes_effect_without_restart(tmp_path: Path) -> None:
    from yonerai_cli.config import DEFAULT_CONFIG, save_cli_config
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    config_path = tmp_path / "cli-config.json"
    config = dict(DEFAULT_CONFIG)
    config["language"] = "en"
    config["update_notice_enabled"] = True
    save_cli_config(config, config_path)
    update_checks = 0

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, lang: str) -> dict[str, Any]:
        return {
            "ok": True,
            "run": {"id": "run_update_notice_off"},
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
        stdin=_PlainStringIO("/update-notice off\nhello\n/quit\n"),
        stdout=stdout,
    )
    output = stdout.getvalue()

    assert rc == 0
    assert update_checks == 1
    assert "Startup update notice" in output
    assert "Changed setting: update_notice=False" in output
    assert "Post-task update notice" not in output
    assert str(tmp_path) not in output


def test_network_off_forces_live_off_in_chat_session(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    calls: list[bool] = []

    def fake_interactive_ask_auto(
        task: str, provider: str, live: bool, ledger_path: str | None, lang: str
    ) -> dict[str, Any]:
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

    def fake_interactive_ask_auto(
        task: str, provider: str, live: bool, ledger_path: str | None, lang: str
    ) -> dict[str, Any]:
        calls.append(live)
        return {
            "ok": True,
            "run": {"id": "run_test"},
            "response": {"output_text": "ok"},
            "auto": {"provider": provider, "mode": "safe"},
            "live_call_performed": live,
        }

    monkeypatch.setattr(cli, "_interactive_ask_auto", fake_interactive_ask_auto)
    monkeypatch.setattr(
        sys, "stdin", _PlainStringIO("/permissions auto-safe\n/live on\n/network off\n/network on\nhello\n/quit\n")
    )

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

    assert words[:10] == [
        "/状態",
        "/ホーム",
        "/設定",
        "/コマンド",
        "/パレット",
        "/入力",
        "/入力欄",
        "/ログイン",
        "/認証",
        "/アカウント",
    ]
    assert "/セッション" in words[:14]
    assert "/ログアウト" in words[:14]
    assert "/取り消し" in words[:16]
    assert "/プロジェクト" in words[:16]
    assert "/同期" in words
    assert "/プライバシー" in words
    assert "/設定" in summary
    assert "/状態" in summary
    assert "/モデル" in summary
    assert "/認証" in summary
    assert "/レート" in summary
    assert "/レート" in words
    assert "/同期" in summary
    assert "/プライバシー" in summary
    assert "/コマンド" in summary
    assert "/入力" in summary
    assert "/コンテキスト" in summary
    assert "/参照" in words
    assert "/モード" in summary
    assert "/計画" in summary
    assert "/レビュー" in summary
    assert "/権限" in summary
    assert "/ポリシー" in summary
    assert "/ポリシー" in words
    assert "/記憶" in summary
    assert "/記憶" in words
    assert "/メモリ" in words
    assert "/memory" in words
    assert "/更新" in summary
    assert "/進行" in summary
    assert "/設定" in words
    assert "/状態" in words
    assert "/ホーム" in words
    assert "/パレット" in words
    assert "/入力欄" in words
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
    assert "/settings" in words
    assert "/settings" in summary
    assert "/palette" in words
    assert "/composer" in words
    assert "/provider" in words
    assert "/login" in words
    assert "/logout" in words
    assert "/revoke" in words
    assert report["plain_fallback"] is True
    assert report["json_ansi_output"] is False
    assert report["command_palette_categories"] is True
    assert report["japanese_alias_completion"] is True
    assert report["japanese_value_completion"] is True
    assert report["status_screen"] is True
    assert report["context_screen"] is True


def test_command_palette_pads_japanese_commands_by_display_width() -> None:
    from yonerai_cli.tui.palette import _pad_display_width

    assert _pad_display_width("/設定", 14) == "/設定" + (" " * 9)
    assert _pad_display_width("/live-provider", 14) == "/live-provider "


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
    assert slash_command_value_group("/モード ") == "agent_mode"
    assert slash_value_words("/モード ", "ja") == ["計画", "安全実行", "レビュー", "記憶"]
    assert slash_value_words("/選択 10 ", "ja") == ["計画", "安全実行", "レビュー", "記憶"]
    assert slash_command_value_group("/権限 ") == "permission_profile"
    assert slash_value_words("/権限 ", "ja") == ["読み取り専用", "自動安全", "危険時確認", "ドライランのみ"]
    assert "plan" in slash_value_words("/mode ", "en")
    assert "build" in slash_value_words("/mode ", "en")
    assert "auto-safe" in slash_value_words("/permissions ", "en")
    assert "ask-before-risky" in slash_value_words("/permissions ", "en")
    assert slash_value_words("/ライブ ", "ja") == ["オン", "オフ"]
    assert slash_value_words("/更新通知 ", "ja") == ["オン", "オフ"]
    assert slash_command_value_group("/設定 ") == "settings_category"
    assert slash_value_words("/設定 ", "ja")[:6] == ["言語", "表示方式", "提供元", "モデル", "モード", "安全"]
    assert "memory" not in slash_value_words("/設定 ", "ja")
    assert "Anthropic" in slash_value_words("/provider ", "en")
    assert "Gemini" in slash_value_words("/provider ", "en")
    assert slash_value_words("/file-access ", "en")[:4] == [
        "workspace_only",
        "ワークスペース内のみ",
        "disabled",
        "無効",
    ]


def test_codelevel_tui_audit_records_source_files_without_vendoring() -> None:
    audit = REPO_ROOT / "docs" / "competitive" / "CODEX_OPENCODE_CODELEVEL_TUI_AUDIT.md"
    text = audit.read_text(encoding="utf-8")

    assert "1d9c9c9f33735223cc564ec942001c9141a11eb1" in text
    assert "0a364330627e95aa723ff70959467ca62b13bf5b" in text
    assert "codex-rs/tui/src/app.rs" in text
    assert "codex-rs/tui/src/bottom_pane/chat_composer.rs" in text
    assert "codex-rs/tui/src/bottom_pane/scroll_state.rs" in text
    assert "packages/opencode/src/cli/cmd/tui/thread.ts" in text
    assert "packages/opencode/src/permission/index.ts" in text
    assert "packages/opencode/src/acp/permission.ts" in text
    assert "does not vendor" in text or "does not vendor, copy, or relicense external code" in text
    assert "No arbitrary `@file` loading" in text


def test_startup_home_header_uses_compact_logo_on_narrow_terminals() -> None:
    from yonerai_cli.startup_home import render_startup_home_header

    rendered = render_startup_home_header(color="never", width=80)

    assert "YonerAI" in rendered
    assert "CLI | build / sync / evolve" in rendered
    assert "██████" not in rendered


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
    assert "/settings" in output
    assert "モデル（AIモデル）" in output
    assert "ローカルLLM" in output
    assert "Ollama 127.0.0.1:11434" in output
    assert "設定を変更しました: モデル（AIモデル）=llama3.1" in output
    assert "更新確認" in output
    assert "最新安定版" in output
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


def test_chat_update_command_without_manifest_shows_channel_choices(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/更新\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "安定版を適用" in output
    assert "ベータ版を適用" in output
    assert "自動適用なし / 強制サイレント更新なし" in output
    assert "/更新 安定版 (/update stable)" in output
    assert "/更新 ベータ版 (/update beta)" in output
    assert "repair 案内だけ出します" in output
    assert str(tmp_path) not in output


def test_chat_update_beta_and_apply_are_short_safe_defaults(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/更新 ベータ版\n/更新 適用 ベータ版\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "更新確認" in output
    assert "チャンネル: ベータ版" in output
    assert "更新適用" in output
    assert "確認が必要: はい" in output
    assert "更新 適用 ベータ版 確認 (/更新 適用 ベータ版 確認 / update apply beta confirm)" in output
    assert "自動適用なし" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output


def test_chat_update_apply_accepts_japanese_confirm_token(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_UPDATE_APPLY_TEST_MODE", "1")
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/更新 適用 ベータ版 確認\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "更新適用" in output
    assert "確認が必要: いいえ" in output
    assert "状態: test_mode_not_installed" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output


def test_script_encoding_hint_does_not_treat_help_slash_as_mojibake() -> None:
    from yonerai_cli.interactive import _script_encoding_hint

    assert _script_encoding_hint("/?", "ja") is None


def test_chat_rate_limit_short_command_is_safe_without_staging_origin(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    _clear_provider_env(monkeypatch)
    monkeypatch.delenv("YONERAI_STAGING_AUTH_ORIGIN", raising=False)
    monkeypatch.delenv("YONERAI_OFFICIAL_API_STAGING_ORIGIN", raising=False)
    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/rate-limit\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "レート制限" in output
    assert "scope: anonymous" in output
    assert "次: /疎通 (/ping) ・ /更新 (/update)" in output
    assert "境界: shared trafficオフ / private upload無効 / 本番ログイン無効" in output
    assert "Traceback" not in output
    assert str(tmp_path) not in output


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
    assert "最新安定版" in output
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


def test_config_set_agent_mode_supports_japanese_aliases(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["config", "set", "mode", "レビュー", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["config"]["agent_mode"] == "review"
    assert str(tmp_path) not in json.dumps(output)

    assert cli.main(["config", "set", "mode", "read_only", "--json"]) == 0
    read_only = json.loads(capsys.readouterr().out)
    assert read_only["config"]["agent_mode"] == "plan_readonly"

    assert cli.main(["config", "set", "mode", "http://127.0.0.1:11434", "--json"]) == 2
    captured = capsys.readouterr()
    assert "agent mode must be plan_readonly" in captured.err
    assert "Traceback" not in captured.err


def test_slash_login_uses_interactive_tty_even_without_prompt_toolkit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import yonerai_cli.interactive as interactive_module
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    calls: list[tuple[str, bool]] = []

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        return {"ok": True}

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    def auth_login(lang: str, interactive_tty: bool) -> dict[str, Any]:
        calls.append((lang, interactive_tty))
        return {
            "ok": True,
            "configured": True,
            "staging": {"configured": True, "origin": "https://api-staging.yonerai.com"},
            "authorization_url": "https://api-staging.yonerai.com/auth/google/start",
            "browser_opened": interactive_tty,
            "next_safe_command": "yonerai login",
            "cli_bridge": {},
        }

    config_path = tmp_path / "cli-config.json"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(interactive_module, "_can_use_prompt_toolkit", lambda *_args, **_kwargs: False)

    stdout = _TTYStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), lang="ja", color="never"),
        InteractiveCallbacks(
            providers=providers,
            ask_auto=ask_auto,
            runs_list=runs_list,
            runs_show=runs_show,
            auth_login=auth_login,
        ),
        stdin=_TTYStringIO("/login\n/quit\n"),
        stdout=stdout,
    )

    assert rc == 0
    assert calls == [("ja", True)]
    rendered = stdout.getvalue()
    assert "ログイン" in rendered
    assert str(tmp_path) not in rendered
