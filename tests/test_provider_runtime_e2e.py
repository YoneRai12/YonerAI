from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest


def _prepare_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for path in (repo_root, repo_root / "core" / "src", repo_root / "clients" / "cli"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


@dataclass
class _ServerHandle:
    base_url: str
    requests: list[dict[str, object]]


@contextmanager
def _loopback_json_server(
    handler: Callable[[str, dict[str, str], dict[str, object]], tuple[int, dict[str, object]]],
) -> Iterator[_ServerHandle]:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            headers = {str(key): str(value) for key, value in self.headers.items()}
            requests.append({"path": self.path, "headers": headers, "payload": payload})
            status, body = handler(self.path, headers, payload)
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _ServerHandle(base_url=f"http://127.0.0.1:{server.server_port}", requests=requests)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _load_cli_module() -> Any:
    _prepare_paths()
    from yonerai_cli import cli

    return cli


def test_openai_compatible_adapter_e2e_uses_loopback_mock_http_server() -> None:
    _prepare_paths()
    from ora_core.providers import ProviderRequest
    from ora_core.providers.openai_compatible import OpenAICompatibleProviderAdapter

    pseudo_key = "sk-" + ("A" * 24)

    def handler(path: str, headers: dict[str, str], payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        assert path == "/v1/chat/completions"
        assert headers["Authorization"] == f"Bearer {pseudo_key}"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        return 200, {"choices": [{"message": {"role": "assistant", "content": "openai loopback reply"}}]}

    with _loopback_json_server(handler) as server:
        adapter = OpenAICompatibleProviderAdapter(
            {
                "YONERAI_OPENAI_COMPATIBLE_BASE_URL": f"{server.base_url}/v1",
                "YONERAI_OPENAI_COMPATIBLE_API_KEY": pseudo_key,
                "YONERAI_OPENAI_COMPATIBLE_MODEL": "openai-e2e",
                "YONERAI_OPENAI_COMPATIBLE_LIVE": "1",
            }
        )

        response = adapter.generate(ProviderRequest(prompt="hello"), allow_live_call=True)

    assert response.provider == "openai-compatible"
    assert response.output_text == "openai loopback reply"
    assert len(server.requests) == 1
    assert pseudo_key not in json.dumps(response.to_public_dict())


def test_local_llm_provider_e2e_uses_loopback_mock_http_server() -> None:
    _prepare_paths()
    from ora_core.providers import ProviderRequest
    from ora_core.providers.local import LocalLLMProviderAdapter

    def handler(path: str, _headers: dict[str, str], payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        assert path == "/api/chat"
        assert payload["model"] == "local-e2e"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        return 200, {"message": {"role": "assistant", "content": "local loopback reply"}}

    with _loopback_json_server(handler) as server:
        adapter = LocalLLMProviderAdapter(
            {
                "ORA_LOCAL_LLM_ENABLED": "1",
                "ORA_LOCAL_LLM_BASE_URL": server.base_url,
                "ORA_LOCAL_LLM_MODEL": "local-e2e",
            }
        )

        response = adapter.generate(ProviderRequest(prompt="hello"), allow_live_call=True)

    assert response.provider == "local"
    assert response.model == "local-e2e"
    assert response.output_text == "local loopback reply"
    assert len(server.requests) == 1


def test_cli_ask_openai_compatible_live_e2e_records_redacted_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli_module()
    pseudo_key = "sk-" + ("B" * 24)
    ledger = tmp_path / "runs.jsonl"

    def handler(path: str, headers: dict[str, str], payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        assert path == "/v1/chat/completions"
        assert headers["Authorization"] == f"Bearer {pseudo_key}"
        assert payload["messages"][-1] == {"role": "user", "content": "hello"}
        return 200, {"choices": [{"message": {"role": "assistant", "content": "openai cli e2e reply"}}]}

    with _loopback_json_server(handler) as server:
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", f"{server.base_url}/v1")
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", pseudo_key)
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_MODEL", "openai-cli-e2e")
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_LIVE", "1")

        exit_code = cli.main(
            ["ask", "hello", "--provider", "openai-compatible", "--live", "--json", "--ledger", str(ledger)]
        )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    ledger_text = ledger.read_text(encoding="utf-8")
    assert exit_code == 0
    assert output["ok"] is True
    assert output["response"]["provider"] == "openai-compatible"
    assert output["response"]["output_text"] == "openai cli e2e reply"
    assert output["run"]["status"] == "completed"
    assert output["live_call_performed"] is True
    assert output["ledger"]["file_backed"] is True
    assert pseudo_key not in captured.out
    assert pseudo_key not in captured.err
    assert pseudo_key not in ledger_text
    assert "shared_traffic_policy" in ledger_text
    assert str(tmp_path) not in captured.out
    assert len(server.requests) == 1


def test_cli_ask_local_live_e2e_records_redacted_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli_module()
    ledger = tmp_path / "runs.jsonl"

    def handler(path: str, _headers: dict[str, str], payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        assert path == "/api/chat"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        return 200, {"message": {"role": "assistant", "content": "local cli e2e reply"}}

    with _loopback_json_server(handler) as server:
        monkeypatch.setenv("ORA_LOCAL_LLM_ENABLED", "1")
        monkeypatch.setenv("ORA_LOCAL_LLM_BASE_URL", server.base_url)
        monkeypatch.setenv("ORA_LOCAL_LLM_MODEL", "local-cli-e2e")

        exit_code = cli.main(["ask", "hello", "--provider", "local", "--live", "--json", "--ledger", str(ledger)])

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    ledger_text = ledger.read_text(encoding="utf-8")
    assert exit_code == 0
    assert output["ok"] is True
    assert output["response"]["provider"] == "local"
    assert output["response"]["model"] == "local-cli-e2e"
    assert output["response"]["output_text"] == "local cli e2e reply"
    assert output["run"]["status"] == "completed"
    assert output["live_call_performed"] is True
    assert "provider_response" in ledger_text
    assert str(tmp_path) not in captured.out
    assert len(server.requests) == 1


def test_cli_ask_openai_compatible_missing_env_and_live_opt_in_are_controlled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli_module()
    for key in (
        "YONERAI_OPENAI_COMPATIBLE_BASE_URL",
        "YONERAI_OPENAI_COMPATIBLE_API_KEY",
        "YONERAI_OPENAI_COMPATIBLE_LIVE",
    ):
        monkeypatch.delenv(key, raising=False)

    missing_env_ledger = tmp_path / "missing-env.jsonl"
    missing_env_rc = cli.main(
        ["ask", "hello", "--provider", "openai-compatible", "--live", "--json", "--ledger", str(missing_env_ledger)]
    )
    missing_env_output = json.loads(capsys.readouterr().out)

    assert missing_env_rc == 1
    assert missing_env_output["ok"] is False
    assert missing_env_output["error"]["code"] == "provider_unavailable"
    assert missing_env_output["live_call_performed"] is False
    assert "provider_unavailable" in missing_env_ledger.read_text(encoding="utf-8")

    def handler(_path: str, _headers: dict[str, str], _payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        raise AssertionError("missing --live must not call the provider server")

    with _loopback_json_server(handler) as server:
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", f"{server.base_url}/v1")
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", "redaction-fixture-key")
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_LIVE", "1")
        no_live_ledger = tmp_path / "no-live.jsonl"

        no_live_rc = cli.main(["ask", "hello", "--provider", "openai-compatible", "--json", "--ledger", str(no_live_ledger)])

    no_live_output = json.loads(capsys.readouterr().out)
    assert no_live_rc == 1
    assert no_live_output["ok"] is False
    assert no_live_output["error"]["code"] == "live_required"
    assert no_live_output["live_call_performed"] is False
    assert len(server.requests) == 0
    assert "redaction-fixture-key" not in json.dumps(no_live_output)
    assert "redaction-fixture-key" not in no_live_ledger.read_text(encoding="utf-8")


def test_cli_ask_local_non_loopback_and_missing_live_are_controlled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli_module()
    monkeypatch.setenv("ORA_LOCAL_LLM_ENABLED", "1")
    monkeypatch.setenv("ORA_LOCAL_LLM_BASE_URL", "https://example.com")
    non_loopback_ledger = tmp_path / "non-loopback.jsonl"

    non_loopback_rc = cli.main(["ask", "hello", "--provider", "local", "--live", "--json", "--ledger", str(non_loopback_ledger)])
    non_loopback_output = json.loads(capsys.readouterr().out)

    assert non_loopback_rc == 1
    assert non_loopback_output["ok"] is False
    assert non_loopback_output["error"]["code"] == "provider_unavailable"
    assert non_loopback_output["live_call_performed"] is False
    assert "example.com" not in json.dumps(non_loopback_output)
    assert "example.com" not in non_loopback_ledger.read_text(encoding="utf-8")

    def handler(_path: str, _headers: dict[str, str], _payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        raise AssertionError("missing --live must not call the local provider server")

    with _loopback_json_server(handler) as server:
        monkeypatch.setenv("ORA_LOCAL_LLM_BASE_URL", server.base_url)
        no_live_ledger = tmp_path / "local-no-live.jsonl"

        no_live_rc = cli.main(["ask", "hello", "--provider", "local", "--json", "--ledger", str(no_live_ledger)])

    no_live_output = json.loads(capsys.readouterr().out)
    assert no_live_rc == 1
    assert no_live_output["ok"] is False
    assert no_live_output["error"]["code"] == "local_live_call_disabled"
    assert no_live_output["live_call_performed"] is False
    assert len(server.requests) == 0


def test_provider_runtime_http_error_is_redacted_in_output_and_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli_module()
    pseudo_key = "sk-" + ("C" * 24)
    ledger = tmp_path / "error-runs.jsonl"

    def handler(_path: str, _headers: dict[str, str], _payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        return 503, {"error": "upstream failed"}

    with _loopback_json_server(handler) as server:
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", f"{server.base_url}/v1")
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", pseudo_key)
        monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_LIVE", "1")

        exit_code = cli.main(
            ["ask", "hello", "--provider", "openai-compatible", "--live", "--json", "--ledger", str(ledger)]
        )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    ledger_text = ledger.read_text(encoding="utf-8")
    assert exit_code == 1
    assert output["ok"] is False
    assert output["error"]["code"] == "provider_http_error"
    assert output["live_call_performed"] is True
    assert output["run"]["status"] == "failed"
    assert "provider_error" in ledger_text
    assert pseudo_key not in captured.out
    assert pseudo_key not in captured.err
    assert pseudo_key not in ledger_text
    assert str(tmp_path) not in captured.out
