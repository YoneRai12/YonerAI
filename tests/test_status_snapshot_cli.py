from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
CORE_SRC = ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_status_snapshot_default_fixture_json_has_v1_shape(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["status", "--source", "fixture", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["schema_version"] == "yonerai-status-snapshot-client/v0.1"
    assert report["snapshot"]["schema_version"] == "yonerai.status.v1"
    assert report["snapshot"]["private_runtime_details_included"] is False
    assert report["production_cloud_claim"] is False


def test_status_snapshot_component_pretty_ja_shows_worker_offline(capsys) -> None:
    from yonerai_cli import cli

    assert (
        cli.main(
            [
                "status",
                "component",
                "official_execution_worker",
                "--source",
                "fixture",
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

    assert "official_execution_worker" in output
    assert "offline/unavailable/staging" in output
    assert "本番 Oracle/cloud/login" in output
    assert "Traceback" not in output


def test_status_snapshot_json_has_no_ansi(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["status", "--source", "fixture", "--json"]) == 0
    output = capsys.readouterr().out

    assert "\x1b[" not in output
    assert "C:\\Users" not in output


def test_status_snapshot_negative_timeout_is_controlled_json(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["status", "--source", "fixture", "--timeout-seconds", "-1", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)

    assert report["ok"] is False
    assert report["error"]["code"] == "status_snapshot_timeout_invalid"
    assert report["error"]["local_path_printed"] is False
    assert report["error"]["token_printed"] is False


def test_legacy_status_check_still_works(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["status", "check", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status_api"]["schema_version"] == "yonerai-status-api/v0.1"


def test_interactive_status_uses_status_snapshot(monkeypatch, capsys) -> None:
    from yonerai_cli import cli
    from yonerai_cli.services import interactive_service
    from yonerai_cli.services.status_snapshot_service import build_status_snapshot_report

    class _PlainStringIO:
        def __init__(self, value: str) -> None:
            import io

            self._stream = io.StringIO(value)

        def readline(self, *args, **kwargs):
            return self._stream.readline(*args, **kwargs)

        def isatty(self) -> bool:
            return False

    def fake_status(*, prepare_import_paths):
        return build_status_snapshot_report(source="fixture")

    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/状態\n/quit\n"))
    monkeypatch.setattr(interactive_service, "build_interactive_status_check", fake_status)

    assert cli.main(["chat", "--script", "--lang", "ja", "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "状態" in output
    assert "公式実行ワーカー" in output
    assert "offline/unavailable/staging" in output
