from __future__ import annotations

import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
CORE_SRC = ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def test_status_check_json_includes_status_api_bridge(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["status", "check", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    serialized = json.dumps(report, sort_keys=True)

    assert report["status_api"]["schema_version"] == "yonerai-status-api/v0.1"
    assert report["status_api"]["status"] == "not_production"
    assert report["status_api"]["component_count"] == 12
    assert report["status_api"]["production_backend_included"] is False
    assert "C:\\Users" not in serialized
    assert "/Users/" not in serialized
    assert "sk-" not in serialized


def test_status_check_pretty_ja_mentions_bridge(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["status", "check", "--pretty", "--lang", "ja"]) == 0
    output = capsys.readouterr().out

    assert "Status API bridge" in output
    assert "latest_stable" in output
    assert "production_backend_included" in output
    assert "Traceback" not in output


def test_api_status_can_read_local_status_feed_fixture(capsys) -> None:
    from yonerai_cli import cli

    fixture = ROOT / "docs" / "contracts" / "fixtures" / "status-api-0.1" / "status-feed.fixture.json"
    assert cli.main(["api", "status", "--status-source", str(fixture), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status_bridge"]["source"]["kind"] == "local_file"
    assert report["status_bridge"]["component_count"] == 12
    assert report["official_backend_called"] is False
    assert report["production_backend_included"] is False


def test_api_status_rejects_url_source_without_explicit_network(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["api", "status", "--status-source", "https://status.yonerai.com/status.json", "--json"]) == 2
    captured = capsys.readouterr()

    assert "requires --allow-network-status-fetch" in captured.err
    assert "Traceback" not in captured.err


def test_api_status_rejects_missing_local_status_source_without_traceback(capsys, tmp_path) -> None:
    from yonerai_cli import cli

    missing = tmp_path / "missing-status-feed.json"
    assert cli.main(["api", "status", "--status-source", str(missing), "--json"]) == 2
    captured = capsys.readouterr()

    assert "failed to read status source file" in captured.err
    assert str(missing) not in captured.err
    assert "Traceback" not in captured.err


def test_api_status_rejects_invalid_local_status_source_without_traceback(capsys, tmp_path) -> None:
    from yonerai_cli import cli

    invalid = tmp_path / "bad-status-feed.json"
    invalid.write_text("{not json", encoding="utf-8")
    assert cli.main(["api", "status", "--status-source", str(invalid), "--json"]) == 2
    captured = capsys.readouterr()

    assert "status source file is not valid JSON" in captured.err
    assert str(invalid) not in captured.err
    assert "Traceback" not in captured.err


def test_api_status_rejects_private_endpoint_without_printing_it(capsys, tmp_path) -> None:
    from ora_core.official.status_api import build_status_feed_fixture
    from yonerai_cli import cli

    private_endpoint = "http://10.0.0.5/runbook"
    feed = build_status_feed_fixture()
    feed["incidents"] = [
        {
            "id": "bad-incident",
            "summary": {"en": f"private runbook {private_endpoint}"},
            "component_id": "official_api",
            "state": "degraded",
        }
    ]
    fixture = tmp_path / "status-feed.json"
    fixture.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")

    assert cli.main(["api", "status", "--status-source", str(fixture), "--json"]) == 2
    captured = capsys.readouterr()

    assert "non-public marker" in captured.err
    assert private_endpoint not in captured.err
    assert "private_runtime_details_included" not in captured.err
    assert "Traceback" not in captured.err


def test_doctor_json_includes_status_api(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["doctor", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["status_api"]["ok"] is True
    assert report["status_api"]["component_count"] == 12


class _PlainStringIO:
    def __init__(self, value: str) -> None:
        self._stream = io.StringIO(value)

    def readline(self, *args, **kwargs):
        return self._stream.readline(*args, **kwargs)

    def isatty(self) -> bool:
        return False


def test_interactive_status_screen_shows_status_bridge(monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/状態\n/quit\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "状態" in output
    assert "component数" in output
    assert "status.yonerai.com" in output
    assert "本番AWS/Oracle" in output
    assert "Traceback" not in output
