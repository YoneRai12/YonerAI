from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread



ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def _context() -> dict[str, object]:
    return {
        "origin": "https://api-staging.yonerai.com",
        "origin_configured": True,
        "auth_state": "linked",
        "account_linked": True,
        "session_available": True,
        "session_token": "opaque-yonerai-session",
        "session_claim": {"expires_at": "2026-06-30T00:00:00Z"},
    }


def _install_context(monkeypatch) -> None:
    from yonerai_cli.services import provider_gateway_service

    monkeypatch.setattr(provider_gateway_service, "build_control_spine_context", lambda **_kwargs: dict(_context()))


def test_provider_gateway_404_is_controlled(monkeypatch) -> None:
    from yonerai_cli.services.provider_gateway_service import build_provider_gateway_report

    _install_context(monkeypatch)

    def transport(_method, _url, _headers, _body, _timeout):
        return 404, {"detail": {"reason": "not_found"}}, {"X-YonerAI-RateLimit-Remaining": "39"}

    report = build_provider_gateway_report("status", config={}, env={}, claim_path=None, transport=transport)
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["ok"] is False
    assert report["error"]["code"] == "provider_gateway_not_available"
    assert report["provider_gateway_available"] is False
    assert "opaque-yonerai-session" not in serialized


def test_provider_gateway_status_contract_derives_quota_and_models(monkeypatch) -> None:
    from yonerai_cli.services.provider_gateway_service import build_provider_gateway_report

    _install_context(monkeypatch)
    calls: list[str] = []

    def transport(_method, url, _headers, _body, _timeout):
        calls.append(url)
        return (
            200,
            {
                "contract_version": "yonerai.provider-gateway.v0.1",
                "provider_id": "openai_shared",
                "enabled": True,
                "kill_switch": False,
                "stage": "staging",
                "model_configured": False,
                "model_policy": {
                    "selected_model_hint": "gpt-4.1-nano",
                    "tools_enabled": False,
                    "file_inputs_enabled": False,
                    "web_search_enabled": False,
                    "code_interpreter_enabled": False,
                },
                "cost_policy": {
                    "daily_token_cap": 2000,
                    "max_input_tokens": 512,
                    "max_output_tokens": 96,
                    "hard_application_budget": True,
                },
                "traffic_default": "off",
                "secret_values_exposed": False,
                "production_deployment_allowed": False,
            },
            {"X-YonerAI-RateLimit-Remaining": "38"},
        )

    status = build_provider_gateway_report("status", config={}, env={}, claim_path=None, transport=transport)
    quota = build_provider_gateway_report("quota", config={}, env={}, claim_path=None, transport=transport)
    models = build_provider_gateway_report("models", config={}, env={}, claim_path=None, transport=transport)
    serialized = json.dumps({"status": status, "quota": quota, "models": models}, ensure_ascii=False)

    assert status["ok"] is True
    assert status["provider_gateway_available"] is True
    assert quota["quota"]["daily_token_cap"] == 2000
    assert models["models"][0]["model_id"] == "gpt-4.1-nano"
    assert all(url.endswith("/v1/provider-gateway/status") for url in calls)
    assert "opaque-yonerai-session" not in serialized
    assert "access_token" not in serialized


def test_provider_gateway_rejects_private_payload(monkeypatch) -> None:
    from yonerai_cli.services.provider_gateway_service import build_provider_gateway_report

    _install_context(monkeypatch)

    def transport(_method, _url, _headers, _body, _timeout):
        return 200, {"provider_status": {"runbook": "http://10.0.0.5/runbook", "api_key": "secret"}}, {}

    report = build_provider_gateway_report("status", config={}, env={}, claim_path=None, transport=transport)
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["ok"] is False
    assert report["error"]["code"] == "provider_gateway_private_payload_rejected"
    assert "10.0.0.5" not in serialized
    assert "secret" not in serialized


def test_provider_gateway_default_transport_rejects_redirect_before_forwarding_auth(monkeypatch) -> None:
    from yonerai_cli.services.provider_gateway_service import build_provider_gateway_report

    captured: list[str | None] = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server callback name
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target_server.server_port}/capture")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server callback name
            captured.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true}')

        def log_message(self, format: str, *args: object) -> None:
            return

    target_server = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)
    redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    target_thread = Thread(target=target_server.serve_forever, daemon=True)
    redirect_thread = Thread(target=redirect_server.serve_forever, daemon=True)
    target_thread.start()
    redirect_thread.start()
    try:
        context = dict(_context())
        context["origin"] = f"http://127.0.0.1:{redirect_server.server_port}"
        monkeypatch.setattr(
            "yonerai_cli.services.provider_gateway_service.build_control_spine_context",
            lambda **_kwargs: dict(context),
        )

        report = build_provider_gateway_report("status", config={}, env={}, claim_path=None, timeout_seconds=2.0)
    finally:
        redirect_server.shutdown()
        target_server.shutdown()
        redirect_thread.join(timeout=5)
        target_thread.join(timeout=5)
        redirect_server.server_close()
        target_server.server_close()

    serialized = json.dumps(report, ensure_ascii=False)
    assert report["ok"] is False
    assert report["error"]["code"] == "provider_gateway_redirect_forbidden"
    assert report["error"]["status_code"] == 302
    assert captured == []
    assert "opaque-yonerai-session" not in serialized


def test_provider_gateway_cli_disable(capsys) -> None:
    from yonerai_cli import cli

    rc = cli.main(["provider", "disable", "--json"])
    output = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert output["provider_gateway_disabled_locally"] is True
    assert output["openai_shared_traffic_default"] is False
