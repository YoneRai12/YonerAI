from __future__ import annotations

import sys
from pathlib import Path


def _load_local_dev_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core.hybrid import local_dev_control_plane

    return local_dev_control_plane


def test_local_dev_control_plane_reports_non_production_status() -> None:
    simulator = _load_local_dev_module()

    status = simulator.build_local_dev_control_plane_status()

    assert status.schema_version == simulator.LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION
    assert status.profile == "local_dev_control_plane"
    assert status.official_cloud_stub_available is True
    assert status.official_private_control_plane_ready is False
    assert status.production_trust_material is False
    assert status.network_required is False
    assert status.local_node.non_production is True
    assert status.local_node.trust_material == "test_static_fixture_only"


def test_local_dev_node_capabilities_are_declared_and_approval_gated() -> None:
    simulator = _load_local_dev_module()

    status = simulator.build_local_dev_control_plane_status()

    assert "private_files" in status.local_node.capabilities
    assert "dangerous_operations" in status.local_node.capabilities
    assert set(status.local_node.capabilities) == set(status.local_node.requires_approval)
    assert "production_deploy" in status.local_node.disabled
    assert "persistent_memory" in status.local_node.disabled
    assert "live_discord_gateway" in status.local_node.disabled


def test_missing_local_node_keeps_hybrid_private_work_gated() -> None:
    simulator = _load_local_dev_module()

    status = simulator.build_local_dev_control_plane_status(local_node_available=False)
    decision = simulator.preview_route_with_local_dev_control_plane(
        "read my local file",
        mode="official_hybrid_private",
        local_node_available=False,
    )

    assert status.local_node.available is False
    assert status.local_node.capabilities == ()
    assert decision.route == "local_node_required"
    assert decision.unavailable_reason == "local_node_missing"


def test_available_local_node_integrates_with_route_preview() -> None:
    simulator = _load_local_dev_module()

    decision = simulator.preview_route_with_local_dev_control_plane(
        "run a shell command",
        mode="official_hybrid_private",
        local_node_available=True,
    )

    assert decision.route == "hybrid_coordination"
    assert decision.requested_capability == "pc_operations"
    assert decision.local_node_required is True
    assert decision.approval_required is True
    assert decision.dangerous_operation is True


def test_local_dev_fixture_trust_context_never_claims_production_trust() -> None:
    simulator = _load_local_dev_module()

    context = simulator.build_local_dev_fixture_trust_context()

    assert context["profile"] == "local_dev_control_plane"
    assert context["production_trust_material"] is False
    assert context["signature_algorithm"] == "test-static-signature"
    assert context["registry_entry_exists"] is True
    assert context["verifier_class"] == "StaticSignatureVerifier"
