from __future__ import annotations

import sys
from pathlib import Path


def _load_route_preview_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import route_preview

    return route_preview


def test_public_docs_route_to_cloud_only_in_managed_cloud() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route("summarize public docs", mode="official_managed_cloud")

    assert decision.route == "cloud_only"
    assert decision.cloud_allowed is True
    assert decision.private_data_allowed is False
    assert decision.approval_required is False
    assert decision.disabled is False
    assert "preview_only_no_execution" in decision.non_claims


def test_managed_cloud_refuses_private_file_access() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route("read my local file", mode="official_managed_cloud")

    assert decision.route == "disabled"
    assert decision.requested_capability == "private_files"
    assert decision.private_data_allowed is False
    assert decision.cloud_allowed is False
    assert decision.unavailable_reason == "capability_disabled"


def test_hybrid_private_routes_private_file_work_to_local_node_requirement() -> None:
    route_preview = _load_route_preview_module()

    missing_node = route_preview.preview_route("read my local file", mode="official_hybrid_private")
    with_node = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
    )

    assert missing_node.route == "local_node_required"
    assert missing_node.local_node_required is True
    assert missing_node.approval_required is True
    assert missing_node.unavailable_reason == "local_node_missing"
    assert with_node.route == "hybrid_coordination"
    assert with_node.private_data_allowed is True
    assert with_node.approval_required is True
    assert with_node.signed_origin_verified is False


def test_shell_command_preview_requires_local_node_and_approval() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "run a shell command",
        mode="official_hybrid_private",
        has_local_node=True,
    )

    assert decision.route == "hybrid_coordination"
    assert decision.requested_capability == "pc_operations"
    assert decision.local_node_required is True
    assert decision.approval_required is True
    assert decision.dangerous_operation is True
    assert decision.cloud_allowed is False


def test_hybrid_private_unverified_node_is_not_routed_to_private_work() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_unverified",
    )

    assert decision.route == "local_node_required"
    assert decision.unavailable_reason == "unverified_node_denied"
    assert decision.local_node_verification_state == "present_unverified"
    assert decision.signed_origin_verified is False
    assert decision.local_node_capability_declared is False


def test_hybrid_private_verified_node_routes_declared_capability() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("private_files",),
    )

    assert decision.route == "hybrid_coordination"
    assert decision.unavailable_reason is None
    assert decision.local_node_verification_state == "present_verified"
    assert decision.signed_origin_verified is True
    assert decision.local_node_capability_declared is True
    assert decision.approval_required is True


def test_hybrid_private_verified_node_without_capability_is_disabled() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("local_tools",),
    )

    assert decision.route == "disabled"
    assert decision.disabled is True
    assert decision.unavailable_reason == "local_node_capability_not_declared"
    assert decision.signed_origin_verified is True
    assert decision.local_node_capability_declared is False


def test_invalid_local_node_states_are_gated() -> None:
    route_preview = _load_route_preview_module()

    cases = {
        "expired": "expired_node_manifest",
        "invalid_signature": "invalid_node_signature",
        "wrong_audience": "wrong_audience_node_manifest",
    }
    for state, unavailable_reason in cases.items():
        decision = route_preview.preview_route(
            "run a shell command",
            mode="official_hybrid_private",
            has_local_node=True,
            local_node_verification_state=state,
        )
        assert decision.route == "local_node_required"
        assert decision.unavailable_reason == unavailable_reason
        assert decision.signed_origin_verified is False


def test_live_discord_and_deployment_are_disabled() -> None:
    route_preview = _load_route_preview_module()

    discord = route_preview.preview_route("open Discord live bot", mode="official_hybrid_private", has_local_node=True)
    deploy = route_preview.preview_route("create deployment", mode="full_private_self_host", has_local_node=True)

    assert discord.route == "disabled"
    assert discord.unavailable_reason == "unknown_capability"
    assert "no_live_discord" in discord.non_claims
    assert deploy.route == "disabled"
    assert deploy.requested_capability == "production_deploy"
    assert deploy.unavailable_reason == "capability_disabled"


def test_self_host_routes_local_work_to_owner_responsibility() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route("run local heavy work", mode="full_private_self_host", has_local_node=True)

    assert decision.route == "self_host_local"
    assert decision.cloud_allowed is False
    assert decision.approval_required is True
    assert decision.local_node_required is False


def test_unknown_requested_capability_is_disabled() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "do something",
        mode="official_managed_cloud",
        requested_capability="unknown.future.capability",
    )

    assert decision.route == "disabled"
    assert decision.disabled is True
    assert decision.unavailable_reason == "unknown_capability"
    assert decision.approval_required is True
