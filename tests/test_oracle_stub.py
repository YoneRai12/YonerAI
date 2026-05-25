from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_oracle_stub_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core.execution import FileRunLedger, InMemoryRunLedger
    from ora_core.hybrid import build_oracle_stub_queue_report, build_oracle_stub_status_report

    return build_oracle_stub_status_report, build_oracle_stub_queue_report, InMemoryRunLedger, FileRunLedger


def test_oracle_stub_status_is_public_safe_and_offline() -> None:
    build_status, _build_queue, _memory_ledger, _file_ledger = _load_oracle_stub_module()

    report = build_status()

    assert report["ok"] is True
    assert report["operation"] == "status"
    assert report["queue_available"] is True
    assert report["network_required"] is False
    assert report["provider_call_performed"] is False
    assert report["production_oracle_used"] is False
    assert report["official_cloud_runtime_implemented"] is False
    assert report["private_file_content_sent_to_cloud_stub"] is False


def test_oracle_stub_queue_processes_public_cloud_candidate_with_redacted_ledger() -> None:
    _build_status, build_queue, InMemoryRunLedger, _file_ledger = _load_oracle_stub_module()
    ledger = InMemoryRunLedger()

    report = build_queue("hard public reasoning over public API docs", ledger=ledger)

    assert report["ok"] is True
    assert report["operation"] == "queue"
    assert report["status"] == "completed"
    assert report["route"]["route_strategy"] == "cloud_contract_candidate"
    assert report["route"]["oracle_stub_eligible"] is True
    assert report["request"]["schema_name"] == "OracleStubRequest"
    assert report["request"]["privacy_class"] == "public"
    assert report["request"]["raw_private_content_included"] is False
    assert report["request"]["raw_prompt_included"] is False
    assert report["request"]["provider_key_included"] is False
    assert report["response"]["schema_name"] == "OracleStubResponse"
    assert report["response"]["status"] == "completed"
    assert report["response"]["network_call_performed"] is False
    assert report["response"]["production_oracle_used"] is False
    assert report["response"]["official_cloud_runtime_implemented"] is False
    assert report["response"]["raw_prompt_included"] is False
    assert report["response"]["private_file_content_included"] is False
    assert report["provider_call_performed"] is False
    assert report["run"]["status"] == "completed"
    event_names = [event["name"] for event in report["run"]["events"]]
    assert event_names == ["oracle_stub_enqueued", "oracle_stub_result"]
    assert "hard public reasoning over public API docs" not in json.dumps(report, ensure_ascii=False)


def test_oracle_stub_refuses_private_and_dangerous_tasks() -> None:
    _build_status, build_queue, _memory_ledger, _file_ledger = _load_oracle_stub_module()

    private_report = build_queue("hard public reasoning over my private files")
    dangerous_report = build_queue("hard public reasoning to format disk")

    assert private_report["ok"] is False
    assert private_report["response"]["status"] == "denied"
    assert private_report["request"]["privacy_class"] == "private"
    assert private_report["request"]["disabled_reason"] == "privacy_class_not_public"
    assert private_report["route"]["oracle_stub_eligible"] is False
    assert private_report["response"]["private_file_content_included"] is False
    assert dangerous_report["ok"] is False
    assert dangerous_report["response"]["status"] == "denied"
    assert dangerous_report["route"]["task_class"] == "dangerous"
    assert dangerous_report["request"]["disabled_reason"] == "dangerous_operation_requires_private_approval"
    assert dangerous_report["response"]["production_oracle_used"] is False


def test_oracle_stub_file_ledger_persists_redacted_events_without_raw_prompt(tmp_path: Path) -> None:
    _build_status, build_queue, _memory_ledger, FileRunLedger = _load_oracle_stub_module()
    ledger_path = tmp_path / "runs.jsonl"

    report = build_queue("hard public reasoning over public API docs", ledger=FileRunLedger(ledger_path))

    persisted = ledger_path.read_text(encoding="utf-8")
    assert report["run"]["run_id"] in persisted
    assert "oracle_stub_enqueued" in persisted
    assert "oracle_stub_result" in persisted
    assert "hard public reasoning over public API docs" not in persisted
    assert "production_oracle_used" not in persisted
