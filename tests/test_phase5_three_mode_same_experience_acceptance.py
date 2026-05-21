from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_public_capabilities_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import public_capabilities

    return public_capabilities


def _load_three_mode_fixture() -> dict[str, object]:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "phase5_three_mode_same_experience.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_three_modes_share_the_same_public_capability_names() -> None:
    capabilities = _load_public_capabilities_module()
    fixture = _load_three_mode_fixture()
    manifest = capabilities.build_public_capability_manifest()
    listed = set(manifest["capabilities"])

    assert manifest["default_action"] == "deny"
    for key in fixture["required_common_public_names"]:
        assert key in listed

    per_mode_names = []
    for mode in fixture["modes"].values():
        names = (
            set(mode["expected_available"])
            | set(mode["expected_gated"])
            | set(mode["expected_docs_only"])
            | set(mode["expected_disabled"])
        )
        per_mode_names.append(names)

    assert per_mode_names
    assert all(names == per_mode_names[0] for names in per_mode_names)


def test_three_modes_share_identical_capability_categories() -> None:
    fixture = _load_three_mode_fixture()
    modes = fixture["modes"]
    category_names = ("expected_available", "expected_gated", "expected_docs_only", "expected_disabled")
    baseline_mode = modes["full_private_self_host"]

    for mode_name, mode in modes.items():
        for category in category_names:
            assert set(mode[category]) == set(baseline_mode[category]), f"{mode_name}:{category}"


def test_three_modes_do_not_silently_enable_dangerous_capabilities() -> None:
    capabilities = _load_public_capabilities_module()
    fixture = _load_three_mode_fixture()

    for mode_name, mode in fixture["modes"].items():
        assert mode["posture"]
        for key in mode["expected_disabled"]:
            capability = capabilities.get_public_capability(key)
            assert capability is not None, f"{mode_name}:{key}"
            assert capability.execution == "disabled", f"{mode_name}:{key}"
            assert capability.public_safe is False, f"{mode_name}:{key}"
            assert capabilities.is_public_capability_enabled(key) is False, f"{mode_name}:{key}"

    for key in fixture["forbidden_enabled_capabilities"]:
        assert capabilities.is_public_capability_enabled(key) is False


def test_three_modes_keep_gated_capabilities_explicit_and_non_persistent() -> None:
    capabilities = _load_public_capabilities_module()
    fixture = _load_three_mode_fixture()

    allowed_gated_execution = {"proposal_only", "quarantine_only", "contract_only"}
    for mode_name, mode in fixture["modes"].items():
        for key in mode["expected_gated"]:
            capability = capabilities.get_public_capability(key)
            assert capability is not None, f"{mode_name}:{key}"
            assert capability.execution in allowed_gated_execution, f"{mode_name}:{key}"
            assert capability.memory_persisted is False, f"{mode_name}:{key}"
            assert capability.requires_approval is True, f"{mode_name}:{key}"


def test_three_modes_keep_docs_only_capabilities_visible_but_non_executable() -> None:
    capabilities = _load_public_capabilities_module()
    fixture = _load_three_mode_fixture()

    for mode_name, mode in fixture["modes"].items():
        for key in mode["expected_docs_only"]:
            capability = capabilities.get_public_capability(key)
            assert capability is not None, f"{mode_name}:{key}"
            assert capability.execution == "docs_only", f"{mode_name}:{key}"
            assert capability.public_safe is True, f"{mode_name}:{key}"
            assert capability.user_visible is True, f"{mode_name}:{key}"
            assert capability.memory_persisted is False, f"{mode_name}:{key}"
            assert capability.requires_approval is False, f"{mode_name}:{key}"
            assert capability.executable_now is False, f"{mode_name}:{key}"
            assert capabilities.is_public_capability_enabled(key) is False, f"{mode_name}:{key}"


def test_three_modes_keep_public_smoke_surface_available_without_private_capabilities() -> None:
    capabilities = _load_public_capabilities_module()
    fixture = _load_three_mode_fixture()

    for mode_name, mode in fixture["modes"].items():
        for key in mode["expected_available"]:
            capability = capabilities.get_public_capability(key)
            assert capability is not None, f"{mode_name}:{key}"
            assert capability.execution == "available", f"{mode_name}:{key}"
            assert capability.public_safe is True, f"{mode_name}:{key}"
            assert capability.memory_persisted is False, f"{mode_name}:{key}"
            assert capabilities.is_public_capability_enabled(key) is True, f"{mode_name}:{key}"
