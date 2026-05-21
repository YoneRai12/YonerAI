from __future__ import annotations

import sys
from pathlib import Path


def _load_three_mode_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import three_mode

    return three_mode


def test_three_mode_surface_uses_same_capability_names_for_every_mode() -> None:
    three_mode = _load_three_mode_module()
    surface = three_mode.build_three_mode_capability_surface()

    assert surface["schema_version"] == three_mode.THREE_MODE_CAPABILITY_SURFACE_VERSION
    assert surface["default_action"] == "deny"
    names_by_mode = []
    for mode in three_mode.MODES:
        profile = three_mode.get_mode_capability_profile(mode)
        names_by_mode.append(tuple(capability.name for capability in profile.capabilities))

    assert names_by_mode
    assert all(names == three_mode.CAPABILITY_NAMES for names in names_by_mode)


def test_official_managed_cloud_cannot_access_private_or_pc_capabilities() -> None:
    three_mode = _load_three_mode_module()
    profile = three_mode.get_mode_capability_profile("official_managed_cloud")

    assert profile.same_user_experience is True
    assert profile.runtime_available_in_public_repo is False
    assert profile.public_repo_support_status == "contract_only"
    assert profile.implementation_owner == "official_private"
    assert profile.external_official_service is True
    assert profile.contract_only is True
    assert profile.disabled_reason == "official_managed_cloud_runtime_not_included_in_public_repo"
    assert profile.production_deploy_enabled is False
    assert profile.persistent_memory_enabled is False
    assert profile.capability("public_ui_sync_support").status == "gated"
    assert profile.capability("cloud_orchestration").status == "gated"
    assert profile.capability("private_files").status == "disabled"
    assert profile.capability("private_files").private_data_allowed is False
    assert profile.capability("pc_operations").status == "disabled"
    assert profile.capability("local_tools").status == "disabled"
    assert profile.capability("dangerous_operations").status == "disabled"


def test_hybrid_private_requires_local_node_for_private_heavy_and_dangerous_work() -> None:
    three_mode = _load_three_mode_module()
    profile = three_mode.get_mode_capability_profile("official_hybrid_private")

    assert profile.runtime_available_in_public_repo is False
    assert profile.public_repo_support_status == "local_node_contract_and_dev_simulator"
    assert profile.implementation_owner == "public_contract_plus_private_coordination"
    assert profile.external_official_service is True
    assert profile.contract_only is False
    assert "local_node_contracts_and_dev_simulator" in str(profile.disabled_reason)
    assert profile.capability("public_ui_sync_support").status == "gated"
    assert profile.capability("cloud_orchestration").status == "gated"
    for name in ("local_node", "private_files", "pc_operations", "local_tools", "heavy_work", "dangerous_operations"):
        capability = profile.capability(name)
        assert capability.status == "gated"
        assert capability.requires_approval is True
        assert capability.local_node_required is True

    assert profile.capability("private_files").private_data_allowed is True
    assert profile.capability("dangerous_operations").dangerous_operation is True


def test_full_private_self_host_is_broader_but_still_owner_gated() -> None:
    three_mode = _load_three_mode_module()
    profile = three_mode.get_mode_capability_profile("full_private_self_host")

    assert profile.runtime_available_in_public_repo is True
    assert profile.public_repo_support_status == "public_local_supported"
    assert profile.implementation_owner == "self_host_operator"
    assert profile.external_official_service is False
    assert profile.contract_only is False
    assert profile.disabled_reason is None
    assert profile.capability("local_node").status == "available"
    assert profile.capability("cloud_orchestration").status == "disabled"
    for name in ("private_files", "pc_operations", "local_tools", "heavy_work", "dangerous_operations"):
        capability = profile.capability(name)
        assert capability.status == "gated"
        assert capability.requires_approval is True


def test_dangerous_and_unfinished_capabilities_are_never_silently_enabled() -> None:
    three_mode = _load_three_mode_module()

    for mode in three_mode.MODES:
        profile = three_mode.get_mode_capability_profile(mode)
        assert profile.production_deploy_enabled is False
        assert profile.persistent_memory_enabled is False
        assert profile.capability("production_deploy").status == "disabled"
        assert profile.capability("persistent_memory").status == "disabled"
        dangerous = profile.capability("dangerous_operations")
        assert dangerous.status in {"gated", "disabled"}
        assert dangerous.requires_approval is True
        assert dangerous.dangerous_operation is True


def test_self_evolution_is_proposal_only_and_gated_in_all_modes() -> None:
    three_mode = _load_three_mode_module()

    for mode in three_mode.MODES:
        capability = three_mode.get_mode_capability_profile(mode).capability("self_evolution_proposals")
        assert capability.status == "gated"
        assert capability.public_safe is True
        assert capability.requires_approval is True
        assert "proposal-only" in capability.reason
