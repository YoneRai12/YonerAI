from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _prepare_core_path() -> None:
    core_src = Path(__file__).resolve().parents[1] / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_mock_provider_success_and_registry_list(monkeypatch) -> None:
    _prepare_core_path()
    monkeypatch.delenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", raising=False)
    monkeypatch.delenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", raising=False)

    from ora_core.providers import ProviderRequest, build_default_provider_registry

    registry = build_default_provider_registry()
    statuses = registry.list_statuses()
    mock = registry.resolve("mock")
    response = mock.generate(ProviderRequest(prompt="hello"))

    assert response.provider == "mock"
    assert response.deterministic is True
    assert "No live provider call" in response.output_text
    assert any(status["provider_id"] == "mock" and status["available"] is True for status in statuses)
    assert any(status["provider_id"] == "openai-compatible" and status["available"] is False for status in statuses)


def test_openai_compatible_contract_builds_payload_without_live_call(monkeypatch) -> None:
    _prepare_core_path()
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", "https://api.example.invalid/v1")
    pseudo_key = "redaction-fixture-key"
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", pseudo_key)
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_MODEL", "gpt-test")

    from ora_core.providers import ProviderError, ProviderRequest
    from ora_core.providers.openai_compatible import OpenAICompatibleProviderAdapter

    adapter = OpenAICompatibleProviderAdapter(dict(**{
        "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://api.example.invalid/v1",
        "YONERAI_OPENAI_COMPATIBLE_API_KEY": pseudo_key,
        "YONERAI_OPENAI_COMPATIBLE_MODEL": "gpt-test",
    }))
    status = adapter.status().to_public_dict()
    payload = adapter.build_chat_payload(ProviderRequest(prompt="return JSON", structured=True))

    assert status["available"] is True
    assert status["env_status"]["YONERAI_OPENAI_COMPATIBLE_API_KEY"] == "present_redacted"
    assert pseudo_key not in json.dumps(status)
    assert payload["model"] == "gpt-test"
    assert payload["response_format"] == {"type": "json_object"}
    with pytest.raises(ProviderError) as exc_info:
        adapter.generate(ProviderRequest(prompt="hello"))
    public = exc_info.value.to_public_dict()
    assert public["code"] == "live_provider_call_disabled"
    assert pseudo_key not in json.dumps(public)


def test_provider_setup_report_explains_local_and_openai_blockers_without_network() -> None:
    _prepare_core_path()
    from ora_core.providers import build_provider_setup_report

    report = build_provider_setup_report({})
    providers = {provider["provider_id"]: provider for provider in report["providers"]}

    assert report["schema_version"] == "yonerai-provider-setup/v1"
    assert report["network_probe_performed"] is False
    assert report["live_call_performed"] is False
    assert providers["mock"]["setup_status"] == "ready"
    assert providers["local"]["setup_status"] == "disabled"
    assert providers["local"]["loopback_only"] is True
    assert providers["openai-compatible"]["setup_status"] == "missing_configuration"
    assert "set ORA_LOCAL_LLM_ENABLED=1" in providers["local"]["setup_blockers"]
    assert "set YONERAI_OPENAI_COMPATIBLE_BASE_URL" in providers["openai-compatible"]["setup_blockers"]
    assert "set YONERAI_OPENAI_COMPATIBLE_API_KEY" in providers["openai-compatible"]["setup_blockers"]
    assert "set YONERAI_OPENAI_COMPATIBLE_LIVE=1" in providers["openai-compatible"]["setup_blockers"]


def test_provider_setup_report_marks_openai_compatible_live_ready_without_leaking_key() -> None:
    _prepare_core_path()
    from ora_core.providers import build_provider_setup_report

    pseudo_key = "redaction-fixture-key"
    report = build_provider_setup_report(
        {
            "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://api.example.invalid/v1",
            "YONERAI_OPENAI_COMPATIBLE_API_KEY": pseudo_key,
            "YONERAI_OPENAI_COMPATIBLE_LIVE": "1",
        }
    )
    provider = next(item for item in report["providers"] if item["provider_id"] == "openai-compatible")

    assert provider["setup_status"] == "live_ready"
    assert provider["live_ready"] is True
    assert provider["setup_blockers"] == []
    assert provider["env_status"]["YONERAI_OPENAI_COMPATIBLE_API_KEY"] == "present_redacted"
    assert pseudo_key not in json.dumps(report)


def test_provider_setup_report_distinguishes_openai_live_opt_in_blocker() -> None:
    _prepare_core_path()
    from ora_core.providers import build_provider_setup_report

    report = build_provider_setup_report(
        {
            "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://api.example.invalid/v1",
            "YONERAI_OPENAI_COMPATIBLE_API_KEY": "redaction-fixture-key",
        }
    )
    provider = next(item for item in report["providers"] if item["provider_id"] == "openai-compatible")

    assert provider["setup_status"] == "live_opt_in_required"
    assert provider["setup_blockers"] == ["set YONERAI_OPENAI_COMPATIBLE_LIVE=1"]
    assert "redaction-fixture-key" not in json.dumps(report)


def test_provider_setup_report_rejects_openai_compatible_invalid_base_url_before_live_ready() -> None:
    _prepare_core_path()
    from ora_core.providers import build_provider_setup_report

    report = build_provider_setup_report(
        {
            "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://user:secret@api.example.invalid/v1?token=secret#frag",
            "YONERAI_OPENAI_COMPATIBLE_API_KEY": "redaction-fixture-key",
            "YONERAI_OPENAI_COMPATIBLE_LIVE": "1",
        }
    )
    provider = next(item for item in report["providers"] if item["provider_id"] == "openai-compatible")

    assert provider["setup_status"] == "invalid_configuration"
    assert provider["live_ready"] is False
    assert provider["setup_blockers"] == [
        "set YONERAI_OPENAI_COMPATIBLE_BASE_URL to an http(s) URL without credentials, query, or fragment"
    ]
    assert "secret" not in json.dumps(report).lower()


@pytest.mark.parametrize(
    ("provider_id", "env_prefix"),
    [
        ("anthropic", "YONERAI_ANTHROPIC"),
        ("gemini", "YONERAI_GEMINI"),
    ],
)
def test_provider_setup_report_rejects_external_provider_invalid_base_url_before_live_ready(
    provider_id: str,
    env_prefix: str,
) -> None:
    _prepare_core_path()
    from ora_core.providers import build_provider_setup_report

    report = build_provider_setup_report(
        {
            f"{env_prefix}_BASE_URL": "https://user:secret@api.example.invalid/v1?token=secret#frag",
            f"{env_prefix}_API_KEY": "redaction-fixture-key",
            f"{env_prefix}_LIVE": "1",
        }
    )
    provider = next(item for item in report["providers"] if item["provider_id"] == provider_id)

    assert provider["setup_status"] == "invalid_configuration"
    assert provider["live_ready"] is False
    assert provider["setup_blockers"] == [f"set {env_prefix}_BASE_URL to an http(s) URL without credentials, query, or fragment"]
    assert "secret" not in json.dumps(report).lower()


def test_openai_compatible_live_request_shape_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderRequest
    from ora_core.providers.openai_compatible import OpenAICompatibleProviderAdapter

    seen: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> object:
        seen["timeout"] = timeout
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse({"choices": [{"message": {"content": "openai compatible reply"}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter = OpenAICompatibleProviderAdapter(
        {
            "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://api.example.invalid/v1",
            "YONERAI_OPENAI_COMPATIBLE_API_KEY": "redaction-fixture-key",
            "YONERAI_OPENAI_COMPATIBLE_MODEL": "gpt-test",
            "YONERAI_OPENAI_COMPATIBLE_LIVE": "1",
        }
    )

    response = adapter.generate(ProviderRequest(prompt="hello", system="be terse", structured=True), allow_live_call=True)

    assert seen["url"] == "https://api.example.invalid/v1/chat/completions"
    assert seen["payload"] == {
        "model": "gpt-test",
        "messages": [{"role": "system", "content": "be terse"}, {"role": "user", "content": "hello"}],
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    headers = {str(key).lower(): value for key, value in seen["headers"].items()}
    assert headers["authorization"] == "Bearer redaction-fixture-key"
    assert response.provider == "openai-compatible"
    assert response.output_text == "openai compatible reply"
    assert "redaction-fixture-key" not in json.dumps(response.to_public_dict())


def test_openai_compatible_rejects_base_url_credentials_query_and_fragment() -> None:
    _prepare_core_path()
    from ora_core.providers import ProviderError, ProviderRequest
    from ora_core.providers.openai_compatible import OpenAICompatibleProviderAdapter

    adapter = OpenAICompatibleProviderAdapter(
        {
            "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://user:secret@api.example.invalid/v1?token=secret#frag",
            "YONERAI_OPENAI_COMPATIBLE_API_KEY": "redaction-fixture-key",
            "YONERAI_OPENAI_COMPATIBLE_LIVE": "1",
        }
    )

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate(ProviderRequest(prompt="hello"), allow_live_call=True)

    public = exc_info.value.to_public_dict()
    assert public["code"] == "provider_config_invalid"
    assert "secret" not in json.dumps(public).lower()


def test_task_classifier_covers_public_private_coding_and_dangerous() -> None:
    _prepare_core_path()
    from ora_core.planning import classify_task

    assert classify_task("summarize public docs").category == "summarize_public"
    assert classify_task("fix this Python test").category == "coding"
    private_task = classify_task("read my local file C:\\Users\\person\\secret.txt")
    assert private_task.category == "local_private_file"
    assert private_task.risk == "private_data"
    dangerous = classify_task("delete file and run shell command")
    assert dangerous.category == "dangerous_operation"
    assert dangerous.risk == "dangerous"
    unsupported = classify_task("connect live Discord with a Discord token")
    assert unsupported.category == "unsupported"


def test_execution_plan_public_task_is_preview_only(monkeypatch) -> None:
    _prepare_core_path()
    monkeypatch.delenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", raising=False)
    monkeypatch.delenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", raising=False)
    from ora_core.planning import build_execution_plan

    plan = build_execution_plan("summarize public docs", mode="hybrid").to_public_dict()

    assert plan["schema_version"] == "yonerai-execution-plan/v1"
    assert plan["classification"]["category"] == "summarize_public"
    assert plan["provider"]["provider_id"] == "mock"
    assert plan["model"]["tier"] == "balanced"
    assert plan["side_effects"] == {
        "provider_call": False,
        "network_call": False,
        "shell": False,
        "file_access": False,
        "discord": False,
        "memory_persisted": False,
        "deploy": False,
    }
    assert plan["safety_checks"]["mcp_deny_policy"]["runtime_execution"] is False
    assert plan["safety_checks"]["managed_download_guard"]["download_performed"] is False


def test_execution_plan_private_and_dangerous_tasks_require_approval() -> None:
    _prepare_core_path()
    from ora_core.planning import build_execution_plan

    private_plan = build_execution_plan("read my local file C:\\Users\\person\\secret.txt", mode="hybrid").to_public_dict()
    dangerous_plan = build_execution_plan("delete file and run shell command", mode="hybrid").to_public_dict()

    assert private_plan["classification"]["category"] == "local_private_file"
    assert private_plan["task"] == "read my local file [local_path_redacted]"
    assert private_plan["provider"]["provider_id"] == "local"
    assert private_plan["provider"]["local_node_required"] is True
    assert "local_node_required" in private_plan["disabled_reasons"]
    assert dangerous_plan["approval"]["required"] is True
    assert "mcp_deny_policy" in dangerous_plan["disabled_reasons"]
    assert any(gate["reason"] == "mcp_tool_denied_by_default" for gate in dangerous_plan["approval"]["gates"])


def test_execution_plan_external_provider_unavailable_does_not_leak_key(monkeypatch) -> None:
    _prepare_core_path()
    monkeypatch.delenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL", raising=False)
    pseudo_key = "redaction-fixture-key"
    monkeypatch.setenv("YONERAI_OPENAI_COMPATIBLE_API_KEY", pseudo_key)
    from ora_core.planning import build_execution_plan

    plan = build_execution_plan("fix this Python bug", mode="hybrid", provider="openai-compatible").to_public_dict()

    encoded = json.dumps(plan)
    assert plan["provider"]["provider_id"] == "openai-compatible"
    assert plan["provider"]["provider_available"] is False
    assert "openai_compatible_provider_not_configured" in plan["disabled_reasons"]
    assert pseudo_key not in encoded


def test_execution_plan_managed_download_guard_connection() -> None:
    _prepare_core_path()
    from ora_core.planning import build_execution_plan

    plan = build_execution_plan("download https://example.com/not-managed.bin", mode="hybrid").to_public_dict()

    guard = plan["safety_checks"]["managed_download_guard"]
    assert guard["relevant_to_task"] is True
    assert guard["network_performed"] is False
    assert guard["managed_url_accepted"] is True
    assert guard["unsafe_url_rejected"] is True
    assert "managed_download_guard" in plan["disabled_reasons"]
    assert any(item["name"] == "managed_download_guard" for item in plan["large_codebase_connections"])
