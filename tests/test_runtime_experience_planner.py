from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _prepare_core_path() -> None:
    core_src = Path(__file__).resolve().parents[1] / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))


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
