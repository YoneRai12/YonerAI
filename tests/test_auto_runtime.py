from __future__ import annotations

import json
from pathlib import Path


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
    assert report["reviewer_plan"]["subtask_count"] == 3
    assert report["oracle_stub"]["response"]["status"] == "completed"
    assert report["oracle_stub"]["request"]["raw_prompt_included"] is False
    assert report["boundaries"]["private_file_content_sent_to_cloud_contract"] is False


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
        ledger=FileRunLedger(ledger_path),
        local_file_context=True,
    )
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    persisted = ledger_path.read_text(encoding="utf-8")

    assert report["ok"] is True
    assert report["auto"]["privacy"] == "local_file"
    assert report["auto"]["route"] == "hybrid_node"
    assert report["local_node"]["used"] is True
    assert report["boundaries"]["private_file_content_sent_to_cloud_contract"] is False
    assert secretish not in serialized
    assert secretish not in persisted
    assert "hybrid_node_route" in persisted


def test_auto_runtime_dangerous_task_is_denied_without_shell_execution() -> None:
    build_report, InMemoryRunLedger, _FileRunLedger = _load_auto_runtime()

    report = build_report("delete file and run shell command", ledger=InMemoryRunLedger())

    assert report["ok"] is False
    assert report["auto"]["route"] == "deny"
    assert report["auto"]["approval_required"] is True
    assert report["run"]["status"] == "blocked"
    assert report["error"]["code"] == "approval_required"
    assert report["boundaries"]["shell_execution_performed"] is False
