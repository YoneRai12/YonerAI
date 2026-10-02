from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"


def _prepare_paths() -> None:
    text = str(CLI_SRC)
    if text not in sys.path:
        sys.path.insert(0, text)


def _example_manifest() -> dict[str, Any]:
    return json.loads((ROOT / "releases" / "manifest.example.json").read_text(encoding="utf-8"))


def test_build_install_plan_valid_manifest_is_dry_run_only() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_install_plan

    report = build_install_plan(str(ROOT / "releases" / "manifest.example.json"))

    assert report["schema_version"] == "yonerai-install-plan/v0.1"
    assert report["ok"] is True
    assert report["dry_run"] is True
    assert report["target_category"] == "windows-user"
    assert report["manifest"]["contract_valid"] is True
    assert report["manifest"]["install_ready"] is False
    assert report["manifest"]["signature_verified"] is False
    assert report["manifest"]["placeholder_non_production"] is True
    assert report["manifest"]["verification_required_before_real_install"] is True
    assert report["artifacts"][0]["sha256_present"] is True
    assert report["artifacts"][0]["sha256_format_valid"] is True
    assert report["artifacts"][0]["filename_matches"] is True
    assert report["non_actions"]["no_download"] is True
    assert report["non_actions"]["no_execution"] is True
    assert report["non_actions"]["no_path_mutation"] is True
    assert report["non_actions"]["no_package_install"] is True
    assert report["non_actions"]["no_registry_modification"] is True
    assert report["non_actions"]["no_service_install"] is True
    assert report["non_actions"]["no_remote_script_execution"] is True
    assert report["download_performed"] is False
    assert report["remote_code_executed"] is False
    assert report["install_performed"] is False
    assert report["path_mutation"] is False
    assert report["network_required"] is False


def test_cli_install_plan_json_is_stable_and_network_free(monkeypatch, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    def fail_urlopen(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("install plan must not open network")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    assert cli.main(["install", "plan", "--manifest", "releases/manifest.example.json", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "yonerai-install-plan/v0.1"
    assert output["manifest"]["placeholder_non_production"] is True
    assert output["manifest"]["signature_verified"] is False
    assert output["non_actions"]["no_remote_script_execution"] is True
    assert output["download_performed"] is False
    assert output["install_performed"] is False
    assert ("C:" + "\\Users") not in json.dumps(output)
    assert str(ROOT) not in json.dumps(output)


def test_cli_install_plan_pretty_is_readable(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    assert cli.main(["install", "plan", "--manifest", "releases/manifest.example.json", "--pretty", "--color", "never"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI install plan" in output
    assert "Dry-run plan" in output
    assert "verification_required_before_real_install" in output
    assert "no_download" in output
    assert "remote_code_executed: false" in output
    assert "\033[" not in output


def test_cli_install_plan_rejects_invalid_json_without_traceback(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    bad_manifest = tmp_path / "bad-manifest.json"
    bad_manifest.write_text("{", encoding="utf-8")

    exit_code = cli.main(["install", "plan", "--manifest", str(bad_manifest), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "manifest file is not valid JSON" in captured.err
    assert "Traceback" not in captured.err
    assert str(bad_manifest) not in captured.err


def test_cli_install_plan_missing_sha256_fails_controlled(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    del manifest["artifacts"][0]["sha256"]
    manifest_path = tmp_path / "missing-sha.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code = cli.main(["install", "plan", "--manifest", str(manifest_path), "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 1
    assert output["ok"] is False
    assert any("sha256" in error for error in output["manifest"]["errors"])
    assert "Traceback" not in captured.err
    assert str(manifest_path) not in captured.out


def test_cli_install_plan_invalid_artifact_name_fails_controlled(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    manifest = _example_manifest()
    manifest["artifacts"][0]["url"] = (
        "https://github.com/YoneRai12/YonerAI/releases/download/"
        "v0.1.0-alpha.1/YonerAI-latest.zip"
    )
    manifest_path = tmp_path / "bad-artifact-name.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code = cli.main(["install", "plan", "--manifest", str(manifest_path), "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exit_code == 1
    assert output["ok"] is False
    assert output["artifacts"][0]["filename_matches"] is False
    assert any("filename" in error or "artifact name" in error for error in output["manifest"]["errors"])
    assert "Traceback" not in captured.err


def test_install_plan_module_invocation_from_clients_cli_cwd() -> None:
    import subprocess

    env = {**os.environ, "PYTHONPATH": str(CLI_SRC)}
    result = subprocess.run(
        [sys.executable, "-m", "yonerai_cli", "install", "plan", "--json"],
        cwd=CLI_SRC,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["schema_version"] == "yonerai-install-plan/v0.1"
    assert output["download_performed"] is False
    assert output["remote_code_executed"] is False
    assert ("C:" + "\\Users") not in result.stdout
    assert "Traceback" not in result.stderr
