from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace


def _load_auto_runtime():
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))
    from ora_core.execution import FileRunLedger, InMemoryRunLedger, build_auto_runtime_report

    return build_auto_runtime_report, InMemoryRunLedger, FileRunLedger


def test_auto_runtime_executes_instant_mock_path_without_live_calls() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    report = build_report("hello", ledger=InMemoryRunLedger())

    assert report["schema_version"] == "yonerai-auto-runtime/v0.1"
    assert report["ok"] is True
    assert report["auto"]["difficulty"] == "instant"
    assert report["auto"]["privacy"] == "public"
    assert report["auto"]["route"] == "instant_local"
    assert report["response"]["provider"] == "mock"
    assert report["run"]["run_id"].startswith("run_")
    assert report["live_call_performed"] is False
    assert report["boundaries"]["shell_execution_performed"] is False


def test_auto_runtime_agent_public_task_uses_oracle_stub_and_reviewer_plan() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    report = build_report("hard public reasoning over public API docs", ledger=InMemoryRunLedger())

    assert report["ok"] is True
    assert report["auto"]["difficulty"] == "agent"
    assert report["auto"]["route"] == "cloud_contract_candidate"
    assert report["reviewer_plan"]["enabled"] is True
    assert report["reviewer_plan"]["subtask_count"] == 5
    assert [step["id"] for step in report["task_progress"]["steps"]] == [
        "classify",
        "route",
        "provider_selection",
        "execution",
        "review",
        "result",
    ]
    assert report["task_progress"]["steps"][-1]["state"] == "done"
    assert report["oracle_stub"]["response"]["status"] == "completed"
    assert report["oracle_stub"]["request"]["raw_prompt_included"] is False
    assert report["boundaries"]["private_file_content_sent_to_cloud_contract"] is False


def test_auto_runtime_cloud_contract_route_uses_actual_task_metadata() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    task = "review public YonerAI API docs for a release checklist"
    report = build_report(task, ledger=InMemoryRunLedger())
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    assert report["auto"]["route"] == "cloud_contract_candidate"
    assert report["route"]["task_class"] == "public_reasoning"
    assert report["route"]["cloud_contract_candidate"] is True
    assert "hard public reasoning over public API docs" not in serialized


def test_auto_runtime_cloud_contract_preview_keeps_public_reasoning_for_run_words() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    task = "fix bug in parser and run tests with hard public reasoning over public API docs"
    report = build_report(task, ledger=InMemoryRunLedger())

    assert report["ok"] is True
    assert report["auto"]["route"] == "cloud_contract_candidate"
    assert report["route"]["task_class"] == "public_reasoning"
    assert report["route"]["dangerous_operation"] is False
    assert report["route"]["approval_state"] == "not_required"
    assert report["route"]["cloud_contract_candidate"] is True


def test_auto_runtime_research_task_uses_mock_search_without_network() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    report = build_report("search the web for YonerAI alpha docs", ledger=InMemoryRunLedger())

    assert report["ok"] is True
    assert report["search"]["needed"] is True
    assert report["search"]["mode"] == "mock"
    assert report["search"]["network_performed"] is False
    assert report["search"]["live_boundary"]["reason"] == "live_search_not_implemented"
    assert len(report["search"]["results"]) == 2


def test_auto_runtime_private_file_context_stays_local_and_records_redacted_ledger(tmp_path: Path) -> None:
    build_report, _InMemoryRunLedger, FileRunLedger = _load_auto_runtime()
    ledger_path = tmp_path / "runs.jsonl"
    secretish = "token=alpha-secret-fixture"

    report = build_report(
        "summarize this file",
        provider_prompt=f"Workspace file context follows. {secretish}",
        provider="anthropic",
        live=True,
        ledger=FileRunLedger(ledger_path),
        local_file_context=True,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    persisted = ledger_path.read_text(encoding="utf-8")

    assert report["ok"] is True
    assert report["auto"]["privacy"] == "local_file"
    assert report["auto"]["route"] == "hybrid_node"
    assert report["auto"]["provider_id"] == "mock"
    assert "external_provider_blocked_for_private_context" in report["auto"]["reasons"]
    assert report["provider"]["external_provider_allowed"] is False
    assert report["live_call_performed"] is False
    assert report["local_node"]["used"] is True
    assert report["boundaries"]["private_file_content_sent_to_cloud_contract"] is False
    assert secretish not in serialized
    assert secretish not in persisted
    assert "hybrid_node_route" in persisted


def test_auto_runtime_records_memory_ids_only_in_ledger(tmp_path: Path) -> None:
    build_report, _InMemoryRunLedger, FileRunLedger = _load_auto_runtime()
    from ora_core.memory import LocalMemoryStore

    memory_store = LocalMemoryStore(tmp_path / "memory.jsonl")
    memory = memory_store.add("prefer concise responses", scope="procedural")
    memory_store.add("token=hidden-fixture", scope="procedural")
    ledger_path = tmp_path / "runs.jsonl"

    report = build_report(
        "hello",
        ledger=FileRunLedger(ledger_path),
        memory_records=memory_store.list(),
    )
    persisted = ledger_path.read_text(encoding="utf-8")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["ok"] is True
    assert report["memory"]["enabled"] is True
    assert report["memory"]["used_ids"] == [memory.id]
    assert report["run"]["memory_used"] == [memory.id]
    assert memory.id in persisted
    assert "prefer concise responses" not in persisted
    assert "hidden-fixture" not in persisted
    assert "prefer concise responses" not in serialized
    assert report["memory"]["raw_memory_content_in_ledger"] is False
    assert report["memory"]["content_sent_to_cloud_contract"] is False


def test_auto_runtime_dangerous_task_is_denied_without_shell_execution() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    report = build_report("delete file and run shell command", ledger=InMemoryRunLedger())

    assert report["ok"] is False
    assert report["auto"]["route"] == "deny"
    assert report["auto"]["approval_required"] is True
    assert report["run"]["status"] == "blocked"
    assert report["error"]["code"] == "approval_required"
    assert report["task_progress"]["steps"][3]["state"] == "skipped"
    assert report["task_progress"]["steps"][-1]["state"] == "blocked"
    assert report["boundaries"]["shell_execution_performed"] is False


def test_auto_runtime_ignores_invalid_context_event_without_crashing() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    report = build_report("hello", ledger=InMemoryRunLedger(), context_events=[object()])

    assert report["ok"] is True
    event_names = [event["name"] for event in report["run"]["events"]]
    assert "context_event_ignored" in event_names
    assert "provider_response" in event_names


def test_auto_runtime_oracle_queue_failure_returns_controlled_error(monkeypatch) -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()
    from ora_core.hybrid import oracle_stub

    class BrokenOracleQueue:
        def enqueue(self, request):
            self.request = request
            return SimpleNamespace(queue_id="oracle_stub_queue_broken")

        def process_next(self):
            return None

    monkeypatch.setattr(oracle_stub, "LocalDevOracleStubQueue", BrokenOracleQueue)

    report = build_report("hard public reasoning over public API docs", ledger=InMemoryRunLedger())

    assert report["ok"] is False
    assert report["auto"]["route"] == "cloud_contract_candidate"
    assert report["oracle_stub"]["status"] == "failed"
    assert report["oracle_stub"]["response"]["disabled_reason"] == "oracle_stub_queue_processing_failed"
    assert report["error"]["code"] == "oracle_stub_denied"
    event_names = [event["name"] for event in report["run"]["events"]]
    assert "oracle_stub_result" in event_names


def test_auto_runtime_oracle_import_failure_returns_controlled_error(monkeypatch) -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()
    import builtins
    import sys

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("cryptography"):
            raise ModuleNotFoundError("No module named 'cryptography'")
        return real_import(name, globals, locals, fromlist, level)

    for module_name in list(sys.modules):
        if module_name == "ora_core.hybrid" or module_name.startswith("ora_core.hybrid."):
            sys.modules.pop(module_name, None)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    report = build_report("hard public reasoning over public API docs", ledger=InMemoryRunLedger())

    assert report["ok"] is False
    assert report["auto"]["route"] == "cloud_contract_candidate"
    assert report["oracle_stub"]["status"] == "failed"
    assert report["oracle_stub"]["operation"] == "import"
    assert report["oracle_stub"]["response"]["status"] == "failed"
    assert report["oracle_stub"]["response"]["disabled_reason"] == "oracle_stub_unavailable:ModuleNotFoundError"
    assert report["error"]["code"] == "oracle_stub_denied"
    event_names = [event["name"] for event in report["run"]["events"]]
    assert "oracle_stub_import" in event_names
