from __future__ import annotations

import json
import sys
from pathlib import Path


repo_root = Path(__file__).resolve().parents[1]
core_src = repo_root / "core" / "src"
if str(core_src) not in sys.path:
    sys.path.insert(0, str(core_src))

from ora_core.hybrid.node_posture import (  # noqa: E402
    NODE_POSTURE_SCHEMA_VERSION,
    evaluate_local_node_posture,
)
from ora_core.hybrid.wire_contract import (  # noqa: E402
    assert_public_safe_wire_payload,
    build_local_node_status_report,
    route_preview_inputs_from_node_status,
)


def test_verified_posture_exposes_declared_known_capabilities() -> None:
    posture = evaluate_local_node_posture(
        node_id="local-node-1",
        manifest_verified=True,
        session_state="active",
        declared_capabilities=("local_model", "workspace_file_access", "mock_search", "ledger"),
    )

    payload = posture.to_public_dict()
    assert payload["schema_version"] == NODE_POSTURE_SCHEMA_VERSION
    assert payload["state"] == "VERIFIED"
    assert payload["exposed_capabilities"] == [
        "local_model",
        "workspace_file_access",
        "mock_search",
        "ledger",
    ]
    assert payload["denied_capabilities"] == []
    assert payload["local_work_preview_allowed"] is True
    assert payload["owner_approval_required"] is False
    assert assert_public_safe_wire_payload(payload) == ()


def test_limited_posture_reduces_unknown_extensions_to_safe_capabilities() -> None:
    posture = evaluate_local_node_posture(
        node_id="local-node-1",
        manifest_verified=True,
        session_state="active",
        declared_capabilities=("workspace_file_access", "mock_search", "ledger", "future_private_capability"),
        declared_extensions=("experimental.plugin",),
    )
    payload = posture.to_public_dict()

    assert payload["state"] == "LIMITED"
    assert payload["exposed_capabilities"] == ["mock_search", "ledger"]
    assert "workspace_file_access" in payload["denied_capabilities"]
    assert "future_private_capability" in payload["denied_capabilities"]
    assert "declared_extensions_require_review" in payload["reasons"]
    assert payload["local_work_preview_allowed"] is False
    assert payload["owner_approval_required"] is True


def test_recovery_posture_exposes_only_ledger_for_drift_or_expired_session() -> None:
    posture = evaluate_local_node_posture(
        node_id="local-node-1",
        manifest_verified=True,
        session_state="expired",
        declared_capabilities=("workspace_file_access", "mock_search", "ledger"),
        policy_drift=True,
        manifest_drift=True,
    )
    payload = posture.to_public_dict()

    assert payload["state"] == "RECOVERY"
    assert payload["exposed_capabilities"] == ["ledger"]
    assert payload["local_work_preview_allowed"] is False
    assert "policy_drift_detected" in payload["reasons"]
    assert "manifest_drift_detected" in payload["reasons"]
    assert "session_expired" in payload["reasons"]


def test_quarantined_and_revoked_postures_expose_no_capabilities() -> None:
    quarantined = evaluate_local_node_posture(
        node_id="local-node-1",
        manifest_verified=True,
        session_state="active",
        declared_capabilities=("mock_search", "ledger"),
        suspicious_behavior=True,
    ).to_public_dict()
    revoked = evaluate_local_node_posture(
        node_id="local-node-1",
        manifest_verified=True,
        session_state="revoked",
        declared_capabilities=("mock_search", "ledger"),
    ).to_public_dict()

    assert quarantined["state"] == "QUARANTINED"
    assert quarantined["exposed_capabilities"] == []
    assert quarantined["local_work_preview_allowed"] is False
    assert "suspicious_behavior_detected" in quarantined["reasons"]
    assert revoked["state"] == "REVOKED"
    assert revoked["exposed_capabilities"] == []
    assert revoked["local_work_preview_allowed"] is False
    assert "node_or_session_revoked" in revoked["reasons"]


def test_node_status_includes_public_safe_posture_and_route_inputs_use_reduced_capabilities() -> None:
    report = build_local_node_status_report()
    local_node = report["local_node"]
    posture = local_node["posture"]
    route_inputs = route_preview_inputs_from_node_status(local_node)
    serialized = json.dumps(report, sort_keys=True)

    assert posture["schema_version"] == NODE_POSTURE_SCHEMA_VERSION
    assert posture["state"] == "VERIFIED"
    assert "workspace_file_access" in posture["exposed_capabilities"]
    assert "private_files" in route_inputs["local_node_capabilities"]
    assert assert_public_safe_wire_payload(report) == ()
    assert "C:\\Users\\" not in serialized


def test_unverified_node_status_is_limited_and_removes_private_route_capability() -> None:
    report = build_local_node_status_report(verified=False)
    local_node = report["local_node"]
    posture = local_node["posture"]
    route_inputs = route_preview_inputs_from_node_status(local_node)

    assert posture["state"] == "LIMITED"
    assert posture["exposed_capabilities"] == ["mock_search", "ledger"]
    assert posture["local_work_preview_allowed"] is False
    assert "private_files" not in route_inputs["local_node_capabilities"]
    assert "local_tools" not in route_inputs["local_node_capabilities"]


def test_posture_handles_missing_optional_values_without_traceback() -> None:
    posture = evaluate_local_node_posture(
        node_id=None,
        manifest_verified=False,
        session_state=None,
        declared_capabilities=(None, "mock_search"),
        declared_extensions=(None,),
    ).to_public_dict()

    assert posture["node_id"] == "unknown-node"
    assert posture["session_state"] == "missing"
    assert posture["state"] == "LIMITED"
    assert posture["exposed_capabilities"] == ["mock_search"]
