from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "core" / "src"
CLI_SRC = ROOT / "clients" / "cli"


def _prepare_paths() -> None:
    for path in (CORE_SRC, CLI_SRC):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_synthetic_discord_gateway_adapter_is_public_safe() -> None:
    _prepare_paths()
    from ora_core.discord_gateway import SyntheticDiscordGatewayAdapter

    report = SyntheticDiscordGatewayAdapter().handle_mention("summarize public launch notes").to_public_dict()

    assert report["ok"] is True
    assert report["synthetic"] is True
    assert report["live_discord"] is False
    assert report["token_required"] is False
    assert report["duplicate_responder_prevented"] is True
    assert report["final_once"] is True
    assert report["progress_events"] >= 1
    assert report["run_request"]["requested_surface"] == "discord_gateway_synthetic"
    assert report["run_request"]["raw_prompt_persisted"] is False
    assert "discord_token" not in json.dumps(report).lower()


def test_official_status_contract_is_fixture_only() -> None:
    _prepare_paths()
    from ora_core.status_contract import build_official_status_contract

    report = build_official_status_contract(source="fixture")
    components = {component["component"]: component for component in report["components"]}

    assert report["ok"] is True
    assert report["network_required"] is False
    assert report["production_service_called"] is False
    assert report["official_cloud_runtime_included"] is False
    assert components["official_managed_cloud"]["status"] == "external_contract_only"
    assert components["oracle_control_plane"]["status"] == "stub_local_dev_only"
    assert components["installer_distribution"]["status"] == "dry_run_manifest_verify_only"


def test_windows_install_plan_is_dry_run_only() -> None:
    _prepare_paths()
    from yonerai_cli.install_planner import build_windows_install_plan

    report = build_windows_install_plan(str(ROOT / "releases" / "manifest.example.json"))

    assert report["ok"] is True
    assert report["dry_run"] is True
    assert report["download_performed"] is False
    assert report["remote_code_executed"] is False
    assert report["install_performed"] is False
    assert report["path_mutation"] is False
    assert report["powershell_pipe_execution_allowed"] is False


def test_cli_discord_status_and_install_outputs_are_network_free(capsys, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("alpha2 boundary commands must not open network")

    monkeypatch.setattr(cli.urllib.request, "urlopen", fail_urlopen)

    assert cli.main(["discord", "synthetic", "hello", "--json"]) == 0
    discord_report = json.loads(capsys.readouterr().out)
    assert discord_report["live_discord"] is False

    assert cli.main(["status", "--source", "fixture", "--json"]) == 0
    status_report = json.loads(capsys.readouterr().out)
    assert status_report["official_status"]["production_service_called"] is False

    assert cli.main(["install", "plan-windows", "--json"]) == 0
    install_report = json.loads(capsys.readouterr().out)
    assert install_report["download_performed"] is False
    assert install_report["remote_code_executed"] is False


def test_powershell_install_planner_static_boundaries() -> None:
    script = (ROOT / "scripts" / "install" / "plan_windows_install.ps1").read_text(encoding="utf-8")
    lower = script.lower()

    assert "invoke-expression" not in lower
    assert " iex" not in lower
    assert "irm " not in lower
    assert "invoke-restmethod" not in lower
    assert "downloadstring" not in lower
    assert "setx" not in lower
    assert "remote_code_executed = $false" in script


def test_cli_boundary_commands_available_from_clients_cli_cwd() -> None:
    env = {**os.environ, "PYTHONPATH": str(CLI_SRC)}
    commands = [
        [sys.executable, "-m", "yonerai_cli", "discord", "synthetic", "hello", "--json"],
        [sys.executable, "-m", "yonerai_cli", "status", "--source", "fixture", "--json"],
        [sys.executable, "-m", "yonerai_cli", "install", "plan-windows", "--json"],
    ]

    for command in commands:
        result = subprocess.run(command, cwd=CLI_SRC, env=env, text=True, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert "C:\\Users" not in result.stdout
        assert "Traceback" not in result.stderr
