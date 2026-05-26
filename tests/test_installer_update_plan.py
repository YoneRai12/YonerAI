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
    from yonerai_cli.install_planner import build_update_plan

    manifest = _example_manifest()
    _set_manifest_version(manifest, _current_version())
    manifest_path = _write_manifest(tmp_path, manifest)

    report = build_update_plan(str(manifest_path), current_version=_current_version())

    assert report["schema_version"] == "yonerai-update-plan/v0.1"
    assert report["ok"] is True
    assert report["dry_run"] is True
    assert report["current_version"] == _current_version()
    assert report["target_version"] == _current_version()
    assert report["update_available"] is False
    assert report["version_comparison"] == "same"
    assert report["selected_artifact"]["filename_matches"] is True
    assert report["sha256_present"] is True
    assert report["rollback_plan_available"] is False
    assert "no download" in report["actions_not_performed"]
    assert "no install" in report["actions_not_performed"]


def test_cli_update_plan_reports_update_available(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    _set_manifest_version(manifest, FUTURE_TEST_VERSION)
    manifest_path = _write_manifest(tmp_path, manifest)

    assert cli.main(["update", "plan", "--manifest", str(manifest_path), "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-update-plan/v0.1"
    assert output["current_version"] == _current_version()
    assert output["target_version"] == FUTURE_TEST_VERSION
    assert output["update_available"] is True
    assert output["version_comparison"] == "target_newer"
    assert output["download_performed"] is False
    assert output["install_performed"] is False
    assert output["path_mutation"] is False
    assert output["remote_code_executed"] is False


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
        "update_available",
        "selected_artifact",
        "sha256_present",
        "signature_status",
        "rollback_plan_available",
        "actions_that_would_run",
        "actions_not_performed",
    }
    assert expected_fields <= set(output)
    assert output["actions_not_performed"][:5] == [
        "no download",
        "no install",
        "no PATH mutation",
        "no remote execution",
        "no package install",
    ]
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
    assert output["manifest"] == "manifest.json"
    assert output["next_safe_command"] == "yonerai update plan --manifest manifest.json --pretty"
    assert str(tmp_path) not in raw
    assert str(ROOT) not in raw
    assert ("C:" + "\\Users") not in raw


def test_update_check_quotes_spaced_manifest_path_in_next_safe_command(tmp_path, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_update_check

    manifest_dir = tmp_path / "My Releases"
    manifest_dir.mkdir()
    manifest = _example_manifest()
    _set_manifest_version(manifest, _current_version())
    manifest_path = _write_manifest(manifest_dir, manifest)
    monkeypatch.chdir(tmp_path)

    report = build_update_check(str(manifest_path), current_version=_current_version())

    assert report["manifest"] == "My Releases/manifest.json"
    assert report["next_safe_command"] == "yonerai update plan --manifest 'My Releases/manifest.json' --pretty"
    assert str(tmp_path) not in json.dumps(report)


def test_update_check_shell_quotes_metacharacters_in_manifest_path(tmp_path, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_update_check

    manifest_dir = tmp_path / "poc;$(echo hacked)>out"
    manifest_dir.mkdir()
    manifest = _example_manifest()
    _set_manifest_version(manifest, _current_version())
    manifest_path = _write_manifest(manifest_dir, manifest)
    monkeypatch.chdir(tmp_path)

    report = build_update_check(str(manifest_path), current_version=_current_version())

    assert report["manifest"] == "poc;$(echo hacked)>out/manifest.json"
    assert report["next_safe_command"] == "yonerai update plan --manifest 'poc;$(echo hacked)>out/manifest.json' --pretty"
    assert str(tmp_path) not in json.dumps(report)


def test_cli_update_check_pretty_is_readable_and_color_safe(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "check", "--manifest", "releases/manifest.example.json", "--pretty", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI update check" in output
    assert "Update check" in output
    assert "latest_manifest_version" in output
    assert "download_performed" in output
    assert "network_required" in output
    assert "false" in output
    assert "\033[" not in output


def test_cli_update_plan_pretty_is_readable(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["update", "plan", "--manifest", "releases/manifest.example.json", "--pretty", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI update plan" in output
    assert "Dry-run update plan" in output
    assert "current_version" in output
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
