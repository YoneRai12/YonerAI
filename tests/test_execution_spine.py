from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest


def _prepare_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    for path in (repo_root, core_src):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_run_ledger_redacts_task_and_records_events() -> None:
    _prepare_paths()
    from ora_core.execution import InMemoryRunLedger

    ledger = InMemoryRunLedger()
    run = ledger.create_run(
        task_text="summarize C:\\Users\\person\\secret.txt with sk-" + ("A" * 24),
        classification={"category": "summarize_public"},
        route_decision={"route": "managed_cloud_contract_only"},
        provider_decision={"provider_id": "mock"},
        approval_required=False,
    )
    ledger.append_event(run.run_id, "provider", "ok", "answered with sk-" + ("B" * 24))
    completed = ledger.complete_run(run.run_id, result_summary="done")
    encoded = json.dumps(completed.to_public_dict())

    assert run.run_id.startswith("run_")
    assert len(run.run_id) == 28
    assert "[local_path_redacted]" in encoded
    assert "sk-" not in encoded
    assert completed.status == "completed"
    assert completed.to_public_dict()["persistence"]["raw_prompt_persisted"] is False




def test_safe_summary_redacts_labeled_secret_values() -> None:
    _prepare_paths()
    from ora_core.execution.ledger import safe_summary

    summarized = safe_summary("api_key=ABCDEF authorization Bearer SECRET access_token:TOKEN123")

    assert "ABCDEF" not in summarized
    assert "SECRET" not in summarized
    assert "TOKEN123" not in summarized
    assert summarized.count("[secret_redacted]") >= 3


def test_legacy_ora_clean_content_characterization_strips_channel_tags() -> None:
    _prepare_paths()
    from src.cogs.ora_pure_helpers import clean_content

    assert clean_content("<|final|>visible reply<|end|>") == "visible reply"


def test_safe_summary_uses_legacy_ora_content_cleaner() -> None:
    _prepare_paths()
    from ora_core.execution import legacy_text_normalizer_status
    from ora_core.execution.ledger import safe_summary

    summary = safe_summary("<|final|>visible reply")
    status = legacy_text_normalizer_status()

    assert summary == "visible reply"
    assert status["execution_spine_connected"] is True
    assert status["source"] == "src/cogs/ora_pure_helpers.py"


def test_legacy_text_normalizer_preserves_embedded_generic_token_text() -> None:
    _prepare_paths()
    from ora_core.execution import normalize_legacy_generated_text

    text = "Document the literal token <|example|> without changing it."

    assert normalize_legacy_generated_text(text) == text


def test_legacy_text_normalizer_strips_route_eval_json_for_ledger() -> None:
    _prepare_paths()
    from ora_core.execution import legacy_text_normalizer_status, normalize_legacy_generated_text
    from ora_core.execution.ledger import safe_summary

    content = 'before {"visible": true} middle {"route_eval": {"route": "internal", "note": "brace } inside"}} after'

    assert normalize_legacy_generated_text(content) == 'before {"visible": true} middle  after'
    assert safe_summary(content) == 'before {"visible": true} middle  after'
    assert legacy_text_normalizer_status()["route_json_stripper_connected"] is True


def test_legacy_text_cleaner_import_is_cached(monkeypatch) -> None:
    _prepare_paths()
    import builtins

    from ora_core.execution import legacy_text

    legacy_text._LEGACY_CLEANER_CACHE = legacy_text._CACHE_MISSING
    original_import = builtins.__import__
    calls = 0

    def counting_import(name, *args, **kwargs):
        nonlocal calls
        if name == "src.cogs.ora_pure_helpers":
            calls += 1
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", counting_import)

    assert legacy_text._load_legacy_cleaner() is not None
    assert legacy_text._load_legacy_cleaner() is not None
    assert calls == 1


def test_execute_task_mock_provider_records_completed_run() -> None:
    _prepare_paths()
    from ora_core.execution import InMemoryRunLedger, execute_task

    ledger = InMemoryRunLedger()
    result = execute_task("summarize public docs", mode="self-host", provider="mock", ledger=ledger).to_public_dict()

    assert result["ok"] is True
    assert result["response"]["provider"] == "mock"
    assert result["run"]["status"] == "completed"
    assert result["run"]["events"][0]["name"] == "plan_created"
    assert result["boundary_checks"]["web_search"]["execution_performed"] is False
    assert result["plan"]["side_effects"]["shell"] is False


def test_execute_task_blocks_dangerous_operation() -> None:
    _prepare_paths()
    from ora_core.execution import execute_task

    result = execute_task("delete file and run shell command", mode="hybrid", provider="mock").to_public_dict()

    assert result["ok"] is False
    assert result["run"]["status"] == "blocked"
    assert result["run"]["approval_required"] is True
    assert result["error"]["code"] == "approval_required"
    assert result["response"] is None


def test_local_provider_registry_uses_loopback_adapter_and_rejects_remote() -> None:
    _prepare_paths()
    from ora_core.providers import ProviderRequest, build_default_provider_registry
    from ora_core.providers.local import LocalLLMProviderAdapter

    remote = build_default_provider_registry(
        {
            "ORA_LOCAL_LLM_ENABLED": "1",
            "ORA_LOCAL_LLM_BASE_URL": "https://example.com",
            "ORA_LOCAL_LLM_MODEL": "local-test",
        }
    )
    assert remote.status_for("local").reason == "local_provider_loopback_policy_rejected"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "loopback reply"}})

    adapter = LocalLLMProviderAdapter(
        {
            "ORA_LOCAL_LLM_ENABLED": "1",
            "ORA_LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
            "ORA_LOCAL_LLM_MODEL": "local-test",
        },
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = adapter.generate(ProviderRequest(prompt="hello"), allow_live_call=True)

    assert adapter.status().available is True
    assert response.provider == "local"
    assert response.output_text == "loopback reply"


def test_execute_task_local_provider_live_uses_loopback_adapter_and_ledger() -> None:
    _prepare_paths()
    from ora_core.execution import InMemoryRunLedger, execute_task
    from ora_core.providers.local import LocalLLMProviderAdapter
    from ora_core.providers.registry import ProviderRegistry

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "<|final|>local reply"}})

    adapter = LocalLLMProviderAdapter(
        {
            "ORA_LOCAL_LLM_ENABLED": "1",
            "ORA_LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
            "ORA_LOCAL_LLM_MODEL": "local-test",
        },
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    ledger = InMemoryRunLedger()
    result = execute_task(
        "summarize public docs",
        mode="self-host",
        provider="local",
        live=True,
        ledger=ledger,
        registry=ProviderRegistry((adapter,)),
    ).to_public_dict()

    assert result["ok"] is True
    assert result["response"]["provider"] == "local"
    assert result["response"]["output_text"] == "local reply"
    assert result["live_call_performed"] is True
    assert result["run"]["status"] == "completed"
    assert "<|final|>" not in result["run"]["result_summary"]


def test_execute_task_local_provider_requires_explicit_live() -> None:
    _prepare_paths()
    from ora_core.execution import execute_task
    from ora_core.providers.local import LocalLLMProviderAdapter
    from ora_core.providers.registry import ProviderRegistry

    adapter = LocalLLMProviderAdapter(
        {
            "ORA_LOCAL_LLM_ENABLED": "1",
            "ORA_LOCAL_LLM_BASE_URL": "http://127.0.0.1:11434",
            "ORA_LOCAL_LLM_MODEL": "local-test",
        },
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500))),
    )
    result = execute_task(
        "summarize public docs",
        mode="self-host",
        provider="local",
        live=False,
        registry=ProviderRegistry((adapter,)),
    ).to_public_dict()

    assert result["ok"] is False
    assert result["error"]["code"] == "local_live_call_disabled"
    assert result["live_call_performed"] is False


def test_openai_compatible_live_requires_live_flag_and_env(monkeypatch) -> None:
    _prepare_paths()
    from ora_core.providers import ProviderError, ProviderRequest
    from ora_core.providers.openai_compatible import OpenAICompatibleProviderAdapter

    pseudo_key = "redaction-fixture-key"
    adapter = OpenAICompatibleProviderAdapter(
        {
            "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://api.example.invalid/v1",
            "YONERAI_OPENAI_COMPATIBLE_API_KEY": pseudo_key,
            "YONERAI_OPENAI_COMPATIBLE_MODEL": "gpt-test",
        }
    )

    with pytest.raises(ProviderError) as exc_info:
        adapter.generate(ProviderRequest(prompt="hello"), allow_live_call=True)
    public = exc_info.value.to_public_dict()
    assert public["code"] == "live_provider_env_not_enabled"
    assert pseudo_key not in json.dumps(public)

    live = OpenAICompatibleProviderAdapter(
        {
            "YONERAI_OPENAI_COMPATIBLE_BASE_URL": "https://api.example.invalid/v1",
            "YONERAI_OPENAI_COMPATIBLE_API_KEY": pseudo_key,
            "YONERAI_OPENAI_COMPATIBLE_LIVE": "1",
        }
    )
    assert live.status().available is True


@pytest.mark.skipif(
    not (
        __import__("os").getenv("YONERAI_OPENAI_COMPATIBLE_LIVE_TEST") == "1"
        and __import__("os").getenv("YONERAI_OPENAI_COMPATIBLE_LIVE") == "1"
        and __import__("os").getenv("YONERAI_OPENAI_COMPATIBLE_API_KEY")
        and __import__("os").getenv("YONERAI_OPENAI_COMPATIBLE_BASE_URL")
    ),
    reason="live provider test is explicitly opt-in",
)
def test_openai_compatible_live_opt_in_smoke() -> None:
    _prepare_paths()
    from ora_core.providers import ProviderRequest, build_default_provider_registry

    response = build_default_provider_registry().resolve("openai-compatible").generate(
        ProviderRequest(prompt="Reply with the word ok."),
        allow_live_call=True,
    )

    assert response.provider == "openai-compatible"
    assert response.output_text


def test_search_and_tool_boundaries_are_disabled_by_default() -> None:
    _prepare_paths()
    from ora_core.execution import build_boundary_checks_for_task
    from ora_core.planning import classify_task

    checks = build_boundary_checks_for_task(classify_task("search the web for public docs"), requested_tool="run_shell")

    assert checks["web_search"]["status"] == "disabled"
    assert checks["web_search"]["execution_performed"] is False
    assert checks["tool_boundary"]["status"] == "denied"
    assert checks["tool_boundary"]["execution_performed"] is False
