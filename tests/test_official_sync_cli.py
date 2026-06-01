from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
CORE_SRC = ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_sync_status_json_is_public_contract_only(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["sync", "status", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == "yonerai-account-sync/v0.1"
    assert report["auth_state"] == "dry_run"
    assert report["directions"]["local_to_cloud"]["enabled_by_default"] is False
    assert report["directions"]["local_to_cloud"]["requires_explicit_approval"] is True
    assert report["shared_traffic_enabled"] is False
    assert report["official_cloud_runtime_enabled"] is False
    assert report["production_oracle_enabled"] is False
    assert "C:\\Users" not in serialized
    assert "/Users/" not in serialized
    assert "sk-" not in serialized


def test_sync_preview_allows_linked_selected_cloud_to_local(capsys) -> None:
    from yonerai_cli import cli

    assert (
        cli.main(
            [
                "sync",
                "preview",
                "--direction",
                "cloud-to-local",
                "--fixture-auth-state",
                "linked",
                "--selected",
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)

    assert report["direction"] == "cloud_to_local"
    assert report["decision"]["state"] == "allowed"
    assert report["preview_only"] is True
    assert report["official_backend_called"] is False
    assert report["sync_performed"] is False


def test_sync_preview_local_to_cloud_requires_approval_and_excludes_private_content(capsys) -> None:
    from yonerai_cli import cli

    assert (
        cli.main(
            [
                "sync",
                "preview",
                "--direction",
                "local-to-cloud",
                "--fixture-auth-state",
                "linked",
                "--selected",
                "--include-private-file",
                "--include-local-memory",
                "--include-local-node-payload",
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    exclusion = report["private_content_exclusion"]

    assert report["decision"]["state"] == "approval_required"
    assert exclusion["private_file_content_excluded"] is True
    assert exclusion["local_memory_excluded"] is True
    assert exclusion["local_node_payload_excluded"] is True
    assert "no private file content upload" in report["actions_not_performed"]


def test_sync_approve_requires_dry_run_without_traceback(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["sync", "approve", "--json"]) == 2
    captured = capsys.readouterr()

    assert "requires --dry-run" in captured.err
    assert "Traceback" not in captured.err


def test_sync_approve_dry_run_does_not_record_or_call_backend(capsys) -> None:
    from yonerai_cli import cli

    assert (
        cli.main(
            [
                "sync",
                "approve",
                "--dry-run",
                "--direction",
                "local-to-cloud",
                "--fixture-auth-state",
                "linked",
                "--selected",
                "--explicit-approval",
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)

    assert report["operation"] == "sync_approve_dry_run"
    assert report["decision"]["state"] == "allowed"
    assert report["dry_run"] is True
    assert report["approval_recorded"] is False
    assert report["sync_performed"] is False
    assert report["official_backend_called"] is False


def test_sync_api_contract_and_rate_limit_are_exposed_as_fixtures(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["sync", "api-contract", "--json"]) == 0
    api_report = json.loads(capsys.readouterr().out)
    assert api_report["production_backend_included"] is False
    assert any(endpoint["path"] == "/v1/sync/preview" for endpoint in api_report["endpoints"])
    assert any(endpoint["path"] == "/v1/rate-limit" for endpoint in api_report["endpoints"])

    assert cli.main(["sync", "rate-limit", "--json"]) == 0
    rate_report = json.loads(capsys.readouterr().out)
    assert rate_report["shared_traffic"]["openai_shared_traffic_enabled"] is False
    assert rate_report["fallback"]["cloud_quota_exceeded"] == "local_mock_or_loopback_provider"


def test_sync_status_standalone_cli_reports_controlled_unavailable_error(tmp_path) -> None:
    package_root = tmp_path / "standalone_cli"
    shutil.copytree(CLIENTS_CLI / "yonerai_cli", package_root / "yonerai_cli")

    script = (
        "from yonerai_cli import cli\n"
        "rc = cli.main(['sync', 'status', '--json'])\n"
        "print(f'rc={rc}')\n"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", script],
        cwd=tmp_path,
        env={"PYTHONPATH": str(package_root)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "rc=1" in completed.stdout
    assert "official sync contract fixtures are unavailable" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert "ModuleNotFoundError" not in completed.stderr
