from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_hybrid_slice_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core.execution import FileRunLedger, InMemoryRunLedger
    from ora_core.hybrid import (
        HYBRID_EXECUTION_SLICE_SCHEMA_VERSION,
        build_hybrid_execution_slice_report,
        build_hybrid_execution_slice_status_report,
    )

    return (
        HYBRID_EXECUTION_SLICE_SCHEMA_VERSION,
        build_hybrid_execution_slice_report,
        build_hybrid_execution_slice_status_report,
        InMemoryRunLedger,
        FileRunLedger,
    )


def test_hybrid_execution_slice_status_is_public_safe() -> None:
    schema, _build_report, build_status, _memory_ledger, _file_ledger = _load_hybrid_slice_module()

    report = build_status()

    assert report["schema_version"] == schema
    assert report["ok"] is True
    assert report["command"] == "yonerai hybrid run --json"
    assert report["local_dev_only"] is True
    assert report["in_process_relay_transport"] is True
    assert report["loopback_only"] is True
    assert report["network_required"] is False
    assert report["production_oracle_used"] is False
    assert report["official_cloud_runtime_implemented"] is False
    assert report["production_trust_material"] is False


def test_hybrid_execution_slice_runs_route_relay_provider_oracle_and_ledger() -> None:
    schema, build_report, _build_status, InMemoryRunLedger, _file_ledger = _load_hybrid_slice_module()
    ledger = InMemoryRunLedger()

    report = build_report(ledger=ledger)
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)

    assert report["schema_version"] == schema
    assert report["ok"] is True
    assert report["selected_route"]["route_strategy"] in {"cloud_contract_only", "cloud_contract_candidate"}
    assert report["local_node_runtime"]["ok"] is True
    assert report["local_node_runtime"]["http_proxy_fixture"]["status"] == "completed"
    assert report["provider_execution"]["ok"] is True
    assert report["provider_execution"]["response"]["provider"] == "mock"
    assert report["provider_execution"]["run"]["status"] == "completed"
    assert report["provider_execution"]["run"]["persistence"]["raw_prompt_persisted"] is False
    assert report["oracle_stub_execution"]["ok"] is True
    assert report["oracle_stub_execution"]["request"]["run_id"] == report["run_ids"]["oracle_run_id"]
    assert report["oracle_stub_execution"]["response"]["status"] == "completed"
    assert report["oracle_stub_execution"]["response"]["raw_prompt_included"] is False
    assert report["oracle_stub_execution"]["response"]["private_file_content_included"] is False
    assert report["boundaries"]["in_process_relay_transport"] is True
    assert report["boundaries"]["message_body_persisted"] is False
    assert report["boundaries"]["raw_prompt_sent_to_oracle_stub"] is False
    assert report["boundaries"]["private_file_content_sent_to_oracle_stub"] is False
    assert report["boundaries"]["production_oracle_used"] is False
    assert report["run_ids"]["provider_run_id"]
    assert report["run_ids"]["oracle_run_id"]
    assert "C:\\Users" not in serialized
    assert "sk-" not in serialized


def test_hybrid_execution_slice_route_matrix_covers_local_hybrid_cloud_and_deny() -> None:
    _schema, build_report, _build_status, InMemoryRunLedger, _file_ledger = _load_hybrid_slice_module()

    report = build_report(ledger=InMemoryRunLedger())
    matrix = {item["name"]: item for item in report["route_matrix"]}

    assert matrix["local_first_public_docs"]["route_strategy"] == "local_preferred"
    assert matrix["hybrid_private_file_local_node"]["route_strategy"] == "hybrid"
    assert matrix["hybrid_private_file_local_node"]["privacy_class"] == "private"
    assert matrix["hybrid_private_file_local_node"]["private_file_content_sent_to_cloud"] is False
    assert matrix["cloud_contract_public_reasoning"]["route_strategy"] == "cloud_contract_candidate"
    assert matrix["cloud_contract_public_reasoning"]["oracle_stub_eligible"] is True
    assert matrix["deny_dangerous_operation"]["route_strategy"] == "deny"
    assert matrix["deny_dangerous_operation"]["approval_state"] == "required"


def test_hybrid_execution_slice_file_ledger_persists_redacted_events(tmp_path: Path) -> None:
    _schema, build_report, _build_status, _memory_ledger, FileRunLedger = _load_hybrid_slice_module()
    ledger_path = tmp_path / "runs.jsonl"

    report = build_report(ledger=FileRunLedger(ledger_path))

    persisted = ledger_path.read_text(encoding="utf-8")
    assert report["run_ids"]["provider_run_id"] in persisted
    assert report["run_ids"]["oracle_run_id"] in persisted
    assert "hybrid_local_node_proxy" in persisted
    assert "oracle_stub_enqueued" in persisted
    assert "oracle_stub_result" in persisted
    assert "relay-node-e2e-token" not in persisted
    assert "hard public reasoning over public API docs" not in persisted
    assert "production_oracle_used" not in persisted
