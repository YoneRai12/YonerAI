from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


PUBLIC_MVP_SMOKE_CONTRACT = "public-mvp-smoke-0.1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prepare_import_path() -> None:
    root = _repo_root()
    core_src = root / "core" / "src"
    for path in (root, core_src):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _prepare_public_env() -> None:
    os.environ["ORA_ALLOW_MISSING_SECRETS"] = "1"
    os.environ["ORA_BOT_DB"] = "sqlite+aiosqlite:///:memory:"
    os.environ["ORA_DOTENV_PATH"] = str(_repo_root() / ".codex-public-smoke-missing.env")
    for key in (
        "DISCORD_TOKEN",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ORA_CORE_API_TOKEN",
        "ORA_LOCAL_LLM_BASE_URL",
        "ORA_LOCAL_LLM_ENABLED",
        "ORA_LOCAL_LLM_PUBLIC_TOKEN",
    ):
        os.environ.pop(key, None)


def _clear_public_runtime_modules() -> None:
    for name in list(sys.modules):
        if name == "ora_core" or name.startswith("ora_core.") or name in {"src.config"} or name.startswith("src.web."):
            sys.modules.pop(name, None)


def _fresh_core_app() -> Any:
    _prepare_import_path()
    _prepare_public_env()
    _clear_public_runtime_modules()

    with redirect_stdout(io.StringIO()):
        main_mod = importlib.import_module("ora_core.main")

    from ora_core.api.routes.agent_runs import reset_surface_agent_run_store
    from ora_core.sessions import reset_public_conversation_session_store

    reset_surface_agent_run_store()
    reset_public_conversation_session_store()
    return main_mod.app


def _assert_json_response(response: Any, *, endpoint: str) -> dict[str, Any]:
    try:
        body = response.json()
    except Exception as exc:  # pragma: no cover - defensive command-line guard
        raise AssertionError(f"{endpoint} did not return JSON") from exc
    if not isinstance(body, dict):
        raise AssertionError(f"{endpoint} returned non-object JSON")
    return body


def run_smoke() -> dict[str, Any]:
    app = _fresh_core_app()
    checks: list[dict[str, str]] = []

    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        health = client.get("/health")
        health_body = _assert_json_response(health, endpoint="/health")
        assert health.status_code == 200, "/health did not return 200"
        assert health_body.get("ok") is True, "/health ok flag was not true"
        checks.append({"endpoint": "/health", "status": "ok"})

        message = client.post(
            "/v1/public/messages",
            json={"message": "hello public MVP", "mode": "mock", "conversation_id": "public-mvp-smoke"},
        )
        message_body = _assert_json_response(message, endpoint="/v1/public/messages")
        assert message.status_code == 200, "/v1/public/messages did not return 200"
        assert message_body.get("ok") is True, "public message ok flag was not true"
        assert message_body.get("mode") == "mock", "public message mode was not mock"
        assert message_body.get("provider") == "offline-mock", "public message provider was not offline-mock"
        assert message_body.get("memory_persisted") is False, "public message persisted memory"
        assert message_body.get("requires_approval") is False, "public message unexpectedly required approval"
        checks.append(
            {
                "endpoint": "/v1/public/messages",
                "status": "ok",
                "mode": "mock",
                "provider": "offline-mock",
            }
        )

        run = client.post(
            "/api/v1/agent/run",
            json={"prompt": "hello public MVP", "mode": "mock", "conversation_id": "public-mvp-smoke"},
        )
        run_body = _assert_json_response(run, endpoint="/api/v1/agent/run")
        assert run.status_code == 200, "/api/v1/agent/run did not return 200"
        assert run_body.get("ok") is True, "agent run ok flag was not true"
        assert run_body.get("status") == "completed", "agent run did not complete in mock mode"
        assert run_body.get("provider") == "offline-mock", "agent run provider was not offline-mock"
        assert run_body.get("memory_persisted") is False, "agent run persisted memory"
        assert str(run_body.get("events_url", "")).startswith("/api/v1/agent/runs/")
        assert str(run_body.get("results_url", "")).startswith("/api/v1/agent/runs/")
        checks.append(
            {
                "endpoint": "/api/v1/agent/run",
                "status": "ok",
                "mode": "mock",
                "provider": "offline-mock",
            }
        )

    return {
        "ok": True,
        "contract": PUBLIC_MVP_SMOKE_CONTRACT,
        "credentials_required": False,
        "external_provider_required": False,
        "live_discord_required": False,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the credential-free YonerAI public MVP smoke.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    try:
        result = run_smoke()
    except Exception as exc:
        public_error = str(exc) if isinstance(exc, AssertionError) else "public MVP smoke failed"
        failure = {"ok": False, "contract": PUBLIC_MVP_SMOKE_CONTRACT, "error": public_error}
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True) if args.json else f"FAIL: {public_error}")
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("YonerAI public MVP smoke: ok")
        for check in result["checks"]:
            print(f"- {check['endpoint']}: {check['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
