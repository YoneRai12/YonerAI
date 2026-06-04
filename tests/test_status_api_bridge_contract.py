from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))


FORBIDDEN_PUBLIC_MARKERS = (
    "AKIA",
    "-----BEGIN",
    "PRIVATE KEY",
    "aws_secret",
    "secret_access_key",
    "arn:aws:",
    "C:\\Users",
    "/Users/",
    "/home/",
    "sk-",
    "discord.com/api/webhooks",
    "10.0.0.5",
    "192.168.",
    "127.0.0.1",
    "169.254.169.254",
    "fc00::",
    "fe80::",
)


def _serialized(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def test_status_api_contract_lists_required_endpoints_and_components() -> None:
    from ora_core.official.status_api import build_status_api_contract_fixture

    contract = build_status_api_contract_fixture()

    assert contract["schema_version"] == "yonerai-status-api-contract/v0.1"
    assert contract["production_backend_included"] is False
    assert {endpoint["path"] for endpoint in contract["endpoints"]} == {
        "/v1/status",
        "/v1/status/components",
        "/v1/status/incidents",
        "/v1/releases",
        "/v1/install",
        "/v1/rate-limit",
    }
    assert set(contract["component_ids"]) == {
        "cli_release",
        "install",
        "update",
        "official_api",
        "oracle",
        "google_auth",
        "shared_traffic",
        "memory_sync",
        "self_evolution",
        "discord",
        "provider_runtime",
        "hybrid_node",
    }


def test_status_feed_fixture_uses_default_status_day_overrides_and_incidents() -> None:
    from ora_core.official.status_api import build_status_feed_fixture

    feed = build_status_feed_fixture(profile="degraded_api")

    assert feed["schema_version"] == "yonerai.status.feed.v1"
    assert feed["incidents"]
    assert all("default_status" in category for category in feed["categories"])
    components = [component for category in feed["categories"] for component in category["components"]]
    assert all("default_status" in component for component in components)
    assert any(component["day_overrides"] for component in components)
    assert any(component["id"] == "official_api" for component in components)


@pytest.mark.parametrize(
    "profile, expected_status",
    [
        ("operational", "not_production"),
        ("degraded_api", "degraded"),
        ("maintenance", "maintenance"),
        ("oracle_not_production", "not_production"),
        ("auth_dry_run_only", "contract_only"),
        ("install_operational", "not_production"),
        ("alpha_available_stable_current", "not_production"),
    ],
)
def test_status_check_profiles_are_public_safe(profile: str, expected_status: str) -> None:
    from ora_core.official.status_api import build_status_check_report

    report = build_status_check_report(profile=profile)
    serialized = _serialized(report)

    assert report["status"] == expected_status
    assert report["production_backend_included"] is False
    assert report["private_runtime_details_included"] is False
    assert report["component_count"] == 12
    assert not any(marker in serialized for marker in FORBIDDEN_PUBLIC_MARKERS)


def test_status_source_local_file_is_allowed_and_network_is_fail_closed(tmp_path: Path) -> None:
    from ora_core.official.status_api import build_status_check_report, build_status_feed_fixture

    fixture_path = tmp_path / "status-feed.json"
    fixture_path.write_text(json.dumps(build_status_feed_fixture(), ensure_ascii=False), encoding="utf-8")

    local_report = build_status_check_report(source=str(fixture_path))
    assert local_report["source"]["kind"] == "local_file"
    assert local_report["ok"] is True
    assert local_report["status"] == "not_production"
    assert any(component["status"] == "not_production" for component in local_report["components"])

    with pytest.raises(ValueError, match="allowlisted"):
        build_status_check_report(source="https://evil.example/status.json", allow_network=True)

    with pytest.raises(ValueError, match="HTTPS"):
        build_status_check_report(source="http://status.yonerai.com/status.json", allow_network=True)

    with pytest.raises(ValueError, match="requires --allow-network-status-fetch"):
        build_status_check_report(source="https://status.yonerai.com/status.json", allow_network=False)


def test_status_network_fetch_rejects_redirects_before_following_private_target() -> None:
    from ora_core.official.status_api import _STATUS_URL_OPENER

    hits: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            hits.append(self.path)
            if self.path == "/redirect":
                self.send_response(302)
                location = f"http://127.0.0.1:{self.server.server_port}/private-status-feed.json"
                self.send_header("Location", location)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(Exception) as exc_info:
            redirect_url = f"http://127.0.0.1:{server.server_port}/redirect"
            _STATUS_URL_OPENER.open(redirect_url, timeout=5)
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    assert getattr(exc_info.value, "code", None) == 302
    assert hits == ["/redirect"]


def test_status_source_incidents_reject_non_public_markers(tmp_path: Path) -> None:
    from ora_core.official.status_api import build_status_check_report, build_status_feed_fixture

    feed = build_status_feed_fixture()
    feed["incidents"] = [
        {
            "id": "bad-incident",
            "summary": {"en": "debug path C:\\Users\\Example\\secret.txt"},
            "component_id": "official_api",
            "state": "degraded",
        }
    ]
    fixture_path = tmp_path / "status-feed.json"
    fixture_path.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="non-public marker"):
        build_status_check_report(source=str(fixture_path))


def test_status_source_components_reject_non_public_markers(tmp_path: Path) -> None:
    from ora_core.official.status_api import build_status_check_report, build_status_feed_fixture

    feed = build_status_feed_fixture()
    feed["categories"][0]["components"][0]["fact"] = {"en": "token sk-example should not publish"}
    fixture_path = tmp_path / "status-feed.json"
    fixture_path.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="non-public marker"):
        build_status_check_report(source=str(fixture_path))


@pytest.mark.parametrize(
    "bad_value",
    [
        "runbook http://10.0.0.5/runbook",
        "dashboard http://192.168.1.5/status",
        "loopback http://127.0.0.1/status",
        "metadata http://169.254.169.254/latest/meta-data",
        "ipv6 loopback http://[::1]/status",
        "ipv6 unique local http://[fc00::1]/status",
        "ipv6 link local http://[fe80::1]/status",
        "raw ipv6 loopback ::1",
        "raw ipv6 unique local fc00::1",
        "raw ipv6 link local fe80::1",
        "malformed ipv6 url http://[::1/status",
        "aws arn arn:aws:lambda:ap-northeast-1:123456789012:function:private",
        "instance i-0123456789abcdef0",
        "local path /root/private/status.json",
        "token api_key=example-secret",
        "internal host https://runbook.internal/status",
        "kubernetes service https://api.default.svc/status",
    ],
)
def test_status_source_rejects_private_endpoint_markers(tmp_path: Path, bad_value: str) -> None:
    from ora_core.official.status_api import build_status_check_report, build_status_feed_fixture

    feed = build_status_feed_fixture()
    feed["incidents"] = [
        {
            "id": "bad-incident",
            "summary": {"en": bad_value},
            "component_id": "official_api",
            "state": "degraded",
        }
    ]
    fixture_path = tmp_path / "status-feed.json"
    fixture_path.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="non-public marker") as exc_info:
        build_status_check_report(source=str(fixture_path))

    assert bad_value not in str(exc_info.value)


def test_status_source_accepts_public_docs_url(tmp_path: Path) -> None:
    from ora_core.official.status_api import build_status_check_report, build_status_feed_fixture

    feed = build_status_feed_fixture()
    feed["incidents"] = [
        {
            "id": "public-docs",
            "summary": {"en": "See https://yonerai.com/install for public install status."},
            "component_id": "install",
            "state": "operational",
        }
    ]
    fixture_path = tmp_path / "status-feed.json"
    fixture_path.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")

    report = build_status_check_report(source=str(fixture_path))
    serialized = _serialized(report)

    assert "https://yonerai.com/install" in serialized
    assert report["private_runtime_details_included"] is False


def test_status_source_component_source_private_url_is_not_printed(tmp_path: Path) -> None:
    from ora_core.official.status_api import build_status_check_report, build_status_feed_fixture

    feed = build_status_feed_fixture()
    feed["categories"][0]["components"][0]["source"] = "http://10.0.0.5/private-monitor"
    fixture_path = tmp_path / "status-feed.json"
    fixture_path.write_text(json.dumps(feed, ensure_ascii=False), encoding="utf-8")

    report = build_status_check_report(source=str(fixture_path))
    serialized = _serialized(report)

    assert "10.0.0.5" not in serialized
    assert report["components"][0]["source"]["provider"] == "yonerai"


def test_generated_status_fixtures_and_schemas_are_valid_json() -> None:
    fixture_dir = ROOT / "docs" / "contracts" / "fixtures" / "status-api-0.1"
    schema_dir = ROOT / "docs" / "contracts" / "schemas" / "status-api-0.1"
    assert fixture_dir.exists()
    assert schema_dir.exists()

    for path in [*fixture_dir.glob("*.json"), *schema_dir.glob("*.json")]:
        data = json.loads(path.read_text(encoding="utf-8"))
        serialized = _serialized(data)
        assert data
        assert not any(marker in serialized for marker in FORBIDDEN_PUBLIC_MARKERS)


def test_status_rate_limit_headers_are_contract_visible() -> None:
    from ora_core.official.status_api import build_status_rate_limit_report

    report = build_status_rate_limit_report()

    assert report["policy_state"] == "contract_only"
    assert "Retry-After" in report["headers"]
    assert "X-YonerAI-RateLimit-Bucket" in report["headers"]
    assert report["quota_exceeded_response"]["status"] == 429
