from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"
FUTURE_TEST_VERSION = "999.0.0-alpha.1"


def _prepare_paths() -> None:
    text = str(CLI_SRC)
    if text not in sys.path:
        sys.path.insert(0, text)


def _example_manifest() -> dict[str, Any]:
    return json.loads((ROOT / "releases" / "manifest.example.json").read_text(encoding="utf-8"))


def _current_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _set_manifest_version(manifest: dict[str, Any], version: str) -> None:
    manifest["version"] = version
    manifest["release"]["tag"] = f"v{version}"
    manifest["release"]["github_release_url"] = f"https://github.com/YoneRai12/YonerAI/releases/tag/v{version}"
    artifact = manifest["artifacts"][0]
    artifact["id"] = f"yonerai-{version}-source-archive"
    artifact["url"] = f"https://github.com/YoneRai12/YonerAI/releases/download/v{version}/YonerAI-{version}.zip"


def _write_manifest(tmp_path: Path, manifest: dict[str, Any]) -> Path:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def test_build_update_plan_reports_no_update_needed_for_matching_version(tmp_path) -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import LATEST_STABLE_VERSION, build_update_plan

    manifest = _example_manifest()
    _set_manifest_version(manifest, _current_version())
    manifest_path = _write_manifest(tmp_path, manifest)

    report = build_update_plan(str(manifest_path), current_version=_current_version())

    assert report["schema_version"] == "yonerai-update-plan/v0.1"
    assert report["ok"] is True
    assert report["dry_run"] is True
    assert report["current_version"] == _current_version()
    assert report["target_version"] == _current_version()
    assert report["latest_stable"] == LATEST_STABLE_VERSION
    assert report["channel"] == manifest["channel"]
    assert report["update_available"] is False
    assert report["version_comparison"] == "same"
    assert report["selected_artifact"]["filename_matches"] is True
    assert report["sha256_present"] is True
    assert report["rollback_plan_available"] is False
    assert "no download" in report["actions_not_performed"]
    assert "no install" in report["actions_not_performed"]
    assert "no forced update" in report["actions_not_performed"]
    assert "no auto-apply update" in report["actions_not_performed"]
    assert report["forced_update_enabled"] is False
    assert report["auto_update_apply_enabled"] is False
    assert report["security_update"] is False
    assert report["critical_update"] is False
    assert report["update_policy"]["active_session_behavior"] == "warn_only_do_not_interrupt"
    assert report["update_policy"]["basic_local_mock_chat_allowed"] is True


def test_cli_update_plan_reports_update_available(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli
    from yonerai_cli.install_planner import LATEST_STABLE_VERSION, TRUSTED_INSTALL_SCRIPT_SHA256

    manifest = _example_manifest()
    _set_manifest_version(manifest, FUTURE_TEST_VERSION)
    manifest_path = _write_manifest(tmp_path, manifest)

    assert cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-update-plan/v0.1"
    assert output["current_version"] == _current_version()
    assert output["target_version"] == FUTURE_TEST_VERSION
    assert output["latest_stable"] == LATEST_STABLE_VERSION
    assert output["channel"] == manifest["channel"]
    assert output["update_available"] is True
    assert output["version_comparison"] == "target_newer"
    assert output["download_performed"] is False
    assert output["install_performed"] is False
    assert output["path_mutation"] is False
    assert output["remote_code_executed"] is False
    assert output["quick_install_command"] == "irm https://install.yonerai.com | iex"
    assert f"releases/download/v{LATEST_STABLE_VERSION}" in output["github_install_fallback_command"]
    assert TRUSTED_INSTALL_SCRIPT_SHA256 in output["github_install_fallback_command"]
    assert "(Get-Process -Id $PID).Path" in output["github_install_fallback_command"]
    assert output["verified_install_page"] == "https://yonerai.com/install"
    assert output["forced_update_enabled"] is False
    assert output["auto_update_apply_enabled"] is False
    assert output["security_update"] is False
    assert output["critical_update"] is False
    assert output["update_policy"]["auto_apply_enabled"] is False
    assert output["update_policy"]["forced_silent_update_enabled"] is False


def test_cli_update_plan_rejects_invalid_artifact_name(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    _set_manifest_version(manifest, FUTURE_TEST_VERSION)
    manifest["artifacts"][0]["url"] = (
        "https://github.com/YoneRai12/YonerAI/releases/download/"
        f"v{FUTURE_TEST_VERSION}/YonerAI-latest.zip"
    )
    manifest_path = _write_manifest(tmp_path, manifest)

    exit_code = cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["selected_artifact"]["filename_matches"] is False
    assert any("filename" in error for error in output["manifest"]["errors"])
    assert "Traceback" not in captured.err


def test_cli_update_plan_rejects_missing_sha256(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    _set_manifest_version(manifest, FUTURE_TEST_VERSION)
    del manifest["artifacts"][0]["sha256"]
    manifest_path = _write_manifest(tmp_path, manifest)

    exit_code = cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["sha256_present"] is False
    assert any("sha256" in error for error in output["manifest"]["errors"])
    assert "Traceback" not in captured.err


def test_cli_update_plan_reports_non_production_signature_warning(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "plan", "--manifest", "releases/manifest.example.json", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["signature_status"]["state"] == "placeholder_non_production"
    assert output["signature_status"]["verified"] is False
    assert output["signature_status"]["placeholder_non_production"] is True
    assert output["signature_status"]["verification_required_before_real_update"] is True
    assert any("non-production placeholder signature" in warning for warning in output["warnings"])


def test_install_update_status_keeps_latest_base_separate_from_trusted_digest() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import (
        LATEST_STABLE_VERSION,
        TRUSTED_INSTALL_SCRIPT_SHA256,
        build_install_update_status,
    )

    report = build_install_update_status()

    assert report["github_latest_install_base_url"] == (
        "https://github.com/YoneRai12/YonerAI/releases/latest/download"
    )
    assert report["github_trusted_install_base_url"] == (
        f"https://github.com/YoneRai12/YonerAI/releases/download/v{LATEST_STABLE_VERSION}"
    )
    assert report["trusted_install_release_tag"] == f"v{LATEST_STABLE_VERSION}"
    assert report["trusted_install_script_sha256"] == TRUSTED_INSTALL_SCRIPT_SHA256


def test_cli_install_status_does_not_require_ok_field(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["install", "status", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["latest_stable"]
    assert output["quick_install_command"] == "irm https://install.yonerai.com | iex"
    assert output["channel"] == "stable"
    assert "Traceback" not in json.dumps(output)


def test_cli_update_plan_rejects_empty_prerelease_identifier(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    _set_manifest_version(manifest, "0.1.0-alpha..3")
    manifest_path = _write_manifest(tmp_path, manifest)

    exit_code = cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["version_comparison"] == "unknown"
    assert any("version is invalid" in error for error in output["manifest"]["errors"])
    assert any("version comparison could not be completed" in warning for warning in output["warnings"])


def test_cli_update_plan_rejects_core_leading_zero_version(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    _set_manifest_version(manifest, "01.2.3")
    manifest_path = _write_manifest(tmp_path, manifest)

    exit_code = cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["version_comparison"] == "unknown"
    assert any("version is invalid" in error for error in output["manifest"]["errors"])
    assert any("release tag is invalid" in error for error in output["manifest"]["errors"])


def test_cli_update_plan_rejects_prerelease_numeric_leading_zero(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    _set_manifest_version(manifest, "1.0.0-alpha.01")
    manifest_path = _write_manifest(tmp_path, manifest)

    exit_code = cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["version_comparison"] == "unknown"
    assert any("version is invalid" in error for error in output["manifest"]["errors"])
    assert any("release tag is invalid" in error for error in output["manifest"]["errors"])


def test_cli_update_plan_json_is_stable_and_network_free(monkeypatch, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("update plan must not open network")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    assert cli.main(["update", "plan", "--manifest", "releases/manifest.example.json", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    expected_fields = {
        "current_version",
        "target_version",
        "latest_stable",
        "channel",
        "update_available",
        "selected_artifact",
        "sha256_present",
        "signature_status",
        "rollback_plan_available",
        "actions_that_would_run",
        "actions_not_performed",
        "quick_install_command",
        "github_install_fallback_command",
        "verified_install_command",
        "forced_update_enabled",
        "auto_update_apply_enabled",
        "security_update",
        "critical_update",
        "update_policy",
    }
    assert expected_fields <= set(output)
    assert output["actions_not_performed"][:5] == [
        "no download",
        "no install",
        "no PATH mutation",
        "no remote execution",
        "no package install",
    ]
    assert "no forced update" in output["actions_not_performed"]
    assert "no auto-apply update" in output["actions_not_performed"]
    assert output["non_actions"]["no_download"] is True
    assert output["non_actions"]["no_install"] is True
    assert output["non_actions"]["no_path_mutation"] is True
    assert output["non_actions"]["no_remote_execution"] is True
    assert output["network_required"] is False
    assert output["admin_required"] is False
    assert ("C:" + "\\Users") not in json.dumps(output)
    assert str(ROOT) not in json.dumps(output)


def test_cli_update_check_json_is_stable_network_free_and_path_safe(tmp_path, monkeypatch, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli
    from yonerai_cli.install_planner import LATEST_STABLE_VERSION, TRUSTED_INSTALL_SCRIPT_SHA256

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("update check must not open network")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)
    manifest = _example_manifest()
    _set_manifest_version(manifest, FUTURE_TEST_VERSION)
    manifest_path = _write_manifest(tmp_path, manifest)

    assert cli.main(["update", "check", "--manifest", str(manifest_path), "--json"]) == 0

    raw = capsys.readouterr().out
    output = json.loads(raw)
    assert output["schema_version"] == "yonerai-update-check/v0.1"
    assert output["current_version"] == _current_version()
    assert output["latest_manifest_version"] == FUTURE_TEST_VERSION
    assert output["latest_stable"] == LATEST_STABLE_VERSION
    assert output["channel"] == manifest["channel"]
    assert output["update_available"] is True
    assert output["artifact_status"]["sha256_present"] is True
    assert output["signature_status"]["placeholder_non_production"] is True
    assert output["rollback_plan_available"] is False
    assert output["download_performed"] is False
    assert output["install_performed"] is False
    assert output["path_mutation"] is False
    assert output["remote_code_executed"] is False
    assert output["network_required"] is False
    assert "no download" in output["actions_not_performed"]
    assert "no install" in output["actions_not_performed"]
    assert "no forced update" in output["actions_not_performed"]
    assert "no auto-apply update" in output["actions_not_performed"]
    assert output["quick_install_command"] == "irm https://install.yonerai.com | iex"
    assert f"releases/download/v{LATEST_STABLE_VERSION}" in output["github_install_fallback_command"]
    assert TRUSTED_INSTALL_SCRIPT_SHA256 in output["github_install_fallback_command"]
    assert "(Get-Process -Id $PID).Path" in output["github_install_fallback_command"]
    assert "install.ps1.sha256" in output["verified_install_command"]
    assert "sidecar does not match trusted digest" in output["verified_install_command"]
    assert output["verified_install_page"] == "https://yonerai.com/install"
    assert output["forced_update_enabled"] is False
    assert output["auto_update_apply_enabled"] is False
    assert output["security_update"] is False
    assert output["critical_update"] is False
    assert output["update_policy"]["active_session_behavior"] == "warn_only_do_not_interrupt"
    assert output["update_policy"]["basic_local_mock_chat_allowed"] is True
    assert output["manifest"] == "manifest.json"
    assert output["next_safe_command"] == "yonerai update plan --manifest manifest.json --pretty"
    assert output["next_safe_command_shell"] in {"powershell", "cmd", "posix"}
    assert output["next_safe_commands"]["powershell"] == "yonerai update plan --manifest manifest.json --pretty"
    assert output["next_safe_commands"]["cmd"] == "yonerai update plan --manifest manifest.json --pretty"
    assert output["next_safe_commands"]["posix"] == "yonerai update plan --manifest manifest.json --pretty"
    assert str(tmp_path) not in raw
    assert str(ROOT) not in raw
    assert ("C:" + "\\Users") not in raw


def test_update_check_quotes_spaced_manifest_path_in_next_safe_command(tmp_path, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import _quote_cli_path, build_update_check

    manifest_dir = tmp_path / "My Releases"
    manifest_dir.mkdir()
    manifest = _example_manifest()
    _set_manifest_version(manifest, _current_version())
    manifest_path = _write_manifest(manifest_dir, manifest)
    monkeypatch.chdir(tmp_path)

    report = build_update_check(str(manifest_path), current_version=_current_version())

    assert report["manifest"] == "My Releases/manifest.json"
    expected_manifest = _quote_cli_path("My Releases/manifest.json")
    assert report["next_safe_command"] == f"yonerai update plan --manifest {expected_manifest} --pretty"
    assert str(tmp_path) not in json.dumps(report)


def test_update_check_shell_quotes_metacharacters_in_manifest_path(tmp_path, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_update_check

    manifest_dir = tmp_path / "poc;&$(echo hacked)"
    manifest_dir.mkdir()
    manifest = _example_manifest()
    _set_manifest_version(manifest, _current_version())
    manifest_path = _write_manifest(manifest_dir, manifest)
    monkeypatch.chdir(tmp_path)

    report = build_update_check(str(manifest_path), current_version=_current_version())

    assert report["manifest"] == "poc;&$(echo hacked)/manifest.json"
    assert report["next_safe_command"] == report["next_safe_commands"][report["next_safe_command_shell"]]
    assert report["next_safe_commands"]["powershell"] == "yonerai update plan --manifest 'poc;&$(echo hacked)/manifest.json' --pretty"
    assert report["next_safe_commands"]["cmd"] == 'yonerai update plan --manifest "poc;&$(echo hacked)/manifest.json" --pretty'
    assert report["next_safe_commands"]["posix"] == "yonerai update plan --manifest 'poc;&$(echo hacked)/manifest.json' --pretty"
    assert str(tmp_path) not in json.dumps(report)


def test_update_check_uses_windows_safe_manifest_path_quoting() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import _quote_cli_path

    assert _quote_cli_path("manifest.json", platform="nt") == "manifest.json"
    assert _quote_cli_path("My Releases/manifest.json", platform="nt", shell="powershell") == "'My Releases/manifest.json'"
    assert (
        _quote_cli_path("poc;$(echo hacked)/manifest.json", platform="nt", shell="powershell")
        == "'poc;$(echo hacked)/manifest.json'"
    )
    assert _quote_cli_path("release's/manifest.json", platform="nt", shell="powershell") == "'release''s/manifest.json'"
    assert _quote_cli_path("My Releases/manifest.json", platform="nt", shell="cmd") == '"My Releases/manifest.json"'
    assert _quote_cli_path("poc;&$(echo hacked)/manifest.json", platform="nt", shell="cmd") == '"poc;&$(echo hacked)/manifest.json"'
    assert _quote_cli_path("release%USERPROFILE%!/manifest.json", platform="nt", shell="cmd") == '"release^%USERPROFILE^%^!/manifest.json"'


def test_update_check_reports_shell_specific_next_safe_commands(tmp_path, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_update_check

    manifest_dir = tmp_path / "poc;&$(echo hacked)"
    manifest_dir.mkdir()
    manifest = _example_manifest()
    _set_manifest_version(manifest, _current_version())
    manifest_path = _write_manifest(manifest_dir, manifest)
    monkeypatch.chdir(tmp_path)

    report = build_update_check(str(manifest_path), current_version=_current_version())

    assert report["next_safe_commands"]["powershell"] == "yonerai update plan --manifest 'poc;&$(echo hacked)/manifest.json' --pretty"
    assert report["next_safe_commands"]["cmd"] == 'yonerai update plan --manifest "poc;&$(echo hacked)/manifest.json" --pretty'
    assert report["next_safe_commands"]["posix"] == "yonerai update plan --manifest 'poc;&$(echo hacked)/manifest.json' --pretty"


def test_update_check_detects_windows_shell_preference() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import _detect_cli_shell

    assert _detect_cli_shell(platform="nt", env={"YONERAI_CLI_SHELL": "cmd"}) == "cmd"
    assert _detect_cli_shell(platform="nt", env={"YONERAI_CLI_SHELL": "pwsh"}) == "powershell"
    assert _detect_cli_shell(platform="nt", env={"COMSPEC": "C:\\Windows\\System32\\cmd.exe", "PROMPT": "$P$G"}) == "cmd"
    assert _detect_cli_shell(platform="nt", env={"COMSPEC": "C:\\Windows\\System32\\cmd.exe"}) == "powershell"
    assert (
        _detect_cli_shell(
            platform="nt",
            env={"COMSPEC": "C:\\Windows\\System32\\cmd.exe", "SHELL": "C:\\Program Files\\PowerShell\\7\\pwsh.exe"},
        )
        == "powershell"
    )
    assert _detect_cli_shell(platform="posix", env={"SHELL": "/bin/bash"}) == "posix"


def test_cli_update_check_pretty_is_readable_and_color_safe(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "check", "--manifest", "releases/manifest.example.json", "--pretty", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "更新確認" in output
    assert "現在のバージョン" in output
    assert "最新安定版" in output
    assert "チャンネル" in output
    assert "強制更新" in output
    assert "自動適用" in output
    assert "セキュリティ更新" in output
    assert "クリティカル更新" in output
    assert "基本ローカルmockチャット" in output
    assert "no forced update" in output
    assert "\033[" not in output


def test_cli_update_check_pretty_accepts_japanese_language(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert (
        cli.main(
            [
                "update",
                "check",
                "--manifest",
                "releases/manifest.example.json",
                "--pretty",
                "--lang",
                "ja",
                "--color",
                "never",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "更新確認" in output
    assert "現在のバージョン" in output
    assert "チャンネル" in output
    assert "強制更新" in output
    assert "自動適用" in output
    assert "次:" in output
    assert "\033[" not in output


def test_cli_update_check_pretty_accepts_english_language(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert (
        cli.main(
            [
                "update",
                "check",
                "--manifest",
                "releases/manifest.example.json",
                "--pretty",
                "--lang",
                "en",
                "--color",
                "never",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out
    assert "YonerAI update check" in output
    assert "Update check" in output
    assert "current_version" in output
    assert "forced_update_enabled" in output
    assert "\033[" not in output


def test_cli_update_choice_pretty_is_japanese_first(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "--pretty", "--lang", "ja", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI 更新" in output
    assert "安定版" in output
    assert "ベータ版" in output
    assert "ここではダウンロード、インストール、PATH変更、自動適用は行いません" in output


def test_cli_update_choice_pretty_can_show_english(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "--pretty", "--lang", "en", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI update" in output
    assert "Which channel do you want to check?" in output
    assert "This command does not download, install, mutate PATH, or auto-apply updates." in output


def test_cli_update_json_ignores_language_flag_and_keeps_stable_schema(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "check", "--manifest", "releases/manifest.example.json", "--json", "--lang", "ja"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-update-check/v0.1"
    assert output["download_performed"] is False
    assert output["install_performed"] is False
    assert "lang" not in output


def test_cli_update_short_choice_screen_is_safe(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-update-choice/v0.1"
    assert output["command"] == "yonerai update"
    assert output["default_channel"] == "stable"
    assert [choice["id"] for choice in output["choices"]] == ["stable", "alpha"]
    assert output["choices"][0]["command"] == "yonerai update stable"
    assert output["choices"][1]["command"] == "yonerai update beta"
    assert output["download_performed"] is False
    assert output["install_performed"] is False
    assert output["path_mutation"] is False
    assert output["remote_code_executed"] is False
    assert output["auto_update_apply_enabled"] is False
    assert output["forced_update_enabled"] is False


def test_cli_update_short_stable_and_alpha_select_expected_channels(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "--json", "stable"]) == 0
    stable_parent_json = json.loads(capsys.readouterr().out)
    assert stable_parent_json["schema_version"] == "yonerai-update-check/v0.1"
    assert stable_parent_json["channel"] == "stable"

    assert cli.main(["update", "stable", "--json"]) == 0
    stable = json.loads(capsys.readouterr().out)
    assert stable["schema_version"] == "yonerai-update-check/v0.1"
    assert stable["channel"] == "stable"
    assert stable["latest_manifest_version"] == "0.8.1"
    assert stable["download_performed"] is False
    assert stable["install_performed"] is False

    assert cli.main(["update", "alpha", "--json"]) == 0
    alpha = json.loads(capsys.readouterr().out)
    assert alpha["schema_version"] == "yonerai-update-check/v0.1"
    assert alpha["channel"] == "alpha"
    assert alpha["latest_manifest_version"] == "0.21.0-alpha.2"
    assert alpha["download_performed"] is False
    assert alpha["install_performed"] is False

    assert cli.main(["update", "beta", "--json"]) == 0
    beta = json.loads(capsys.readouterr().out)
    assert beta["schema_version"] == "yonerai-update-check/v0.1"
    assert beta["channel"] == "alpha"
    assert beta["latest_manifest_version"] == "0.21.0-alpha.2"
    assert beta["download_performed"] is False
    assert beta["install_performed"] is False


def test_cli_update_short_japanese_beta_alias_selects_prerelease_channel(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "ベータ版", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["channel"] == "alpha"
    assert output["latest_manifest_version"] == "0.21.0-alpha.2"

    assert cli.main(["update", "アルファ版", "--json"]) == 0
    compat = json.loads(capsys.readouterr().out)
    assert compat["channel"] == "alpha"


def test_cli_update_apply_short_japanese_alpha_alias_selects_prerelease_channel(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "apply", "アルファ", "--json"]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["channel"] == "alpha"
    assert output["confirmation_required"] is True


def test_cli_update_apply_requires_explicit_confirmation(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "apply", "beta", "--json"]) == 1

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-update-apply/v0.1"
    assert output["channel"] == "alpha"
    assert output["confirmation_required"] is True
    assert output["download_performed"] is False
    assert output["install_performed"] is False
    assert output["path_mutation"] is False
    assert output["remote_code_executed"] is False
    assert output["next_safe_command"] == "yonerai update apply beta --yes"
    assert output["next_interactive_command"] == "/更新 適用 ベータ版 確認"


def test_update_apply_test_mode_does_not_install() -> None:
    _prepare_paths()
    from yonerai_cli.services.update_service import build_update_apply_report

    report = build_update_apply_report(
        channel="alpha",
        confirmed=True,
        repo_root=ROOT,
        current_version="0.20.0-alpha.1",
        env={"YONERAI_UPDATE_APPLY_TEST_MODE": "1"},
    )

    assert report["ok"] is True
    assert report["apply_state"] == "test_mode_not_installed"
    assert report["download_performed"] is False
    assert report["install_performed"] is False
    assert report["path_mutation"] is False
    assert report["remote_code_executed"] is False
    assert report["network_required"] is True


def test_update_apply_test_mode_does_not_require_powershell(monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli.services import update_service

    monkeypatch.setattr(update_service.shutil, "which", lambda _: None)

    report = update_service.build_update_apply_report(
        channel="alpha",
        confirmed=True,
        repo_root=ROOT,
        current_version="0.20.0-alpha.1",
        env={"YONERAI_UPDATE_APPLY_TEST_MODE": "1"},
    )

    assert report["ok"] is True
    assert report["apply_state"] == "test_mode_not_installed"


def test_cli_update_plan_pretty_is_readable(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "plan", "--manifest", "releases/manifest.example.json", "--pretty", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI update plan" in output
    assert "Dry-run update plan" in output
    assert "current_version" in output
    assert "latest_stable" in output
    assert "channel" in output
    assert "quick_install_command" in output
    assert "forced_update_enabled" in output
    assert "auto_update_apply_enabled" in output
    assert "security_update" in output
    assert "critical_update" in output
    assert "basic_local_mock_chat_allowed" in output
    assert "[WARN] version_comparison" in output
    assert "rollback_plan_available" in output
    assert "remote_code_executed: false" in output
    assert "\033[" not in output


def test_update_plan_module_invocation_from_clients_cli_cwd() -> None:
    import subprocess

    env = {**os.environ, "PYTHONPATH": str(CLI_SRC)}
    result = subprocess.run(
        [sys.executable, "-m", "yonerai_cli", "update", "plan", "--json"],
        cwd=CLI_SRC,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["schema_version"] == "yonerai-update-plan/v0.1"
    assert output["download_performed"] is False
    assert output["remote_code_executed"] is False
    assert ("C:" + "\\Users") not in result.stdout
    assert "Traceback" not in result.stderr


def test_update_check_module_invocation_preserves_relative_manifest_command_from_clients_cli_cwd() -> None:
    import subprocess

    env = {**os.environ, "PYTHONPATH": str(CLI_SRC)}
    result = subprocess.run(
        [sys.executable, "-m", "yonerai_cli", "update", "check", "--json"],
        cwd=CLI_SRC,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["schema_version"] == "yonerai-update-check/v0.1"
    assert output["manifest"].startswith("../../releases/manifest.v")
    assert output["next_safe_command"].startswith("yonerai update plan --manifest ../../releases/manifest.v")
    assert output["rollback_plan_available"] is False
    assert ("C:" + "\\Users") not in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_update_plan_handles_oversized_numeric_version_component(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    huge_major = "9" * 5000
    _set_manifest_version(manifest, f"{huge_major}.0.0")
    manifest_path = _write_manifest(tmp_path, manifest)

    exit_code = cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["version_comparison"] == "unknown"
    assert any("version comparison could not be completed" in warning for warning in output["warnings"])
    assert "Traceback" not in captured.err
