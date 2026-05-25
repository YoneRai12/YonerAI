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


def test_public_docs_route_is_contract_only_in_managed_cloud() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route("summarize public docs", mode="official_managed_cloud")

    assert decision.route == "managed_cloud_contract_only"
    assert decision.cloud_allowed is False
    assert decision.runtime_available_in_public_repo is False
    assert decision.public_repo_support_status == "contract_only"
    assert decision.implementation_owner == "official_private"
    assert decision.external_official_service_required is True
    assert decision.contract_only is True
    assert decision.public_repo_execution_available is False
    assert decision.unavailable_reason == "official_managed_cloud_runtime_not_included_in_public_repo"
    assert decision.private_data_allowed is False
    assert decision.approval_required is True
    assert decision.disabled is False
    assert "preview_only_no_execution" in decision.non_claims
    assert "official_managed_cloud_runtime_not_in_public_repo" in decision.non_claims
    payload = decision.to_public_dict()
    assert payload["route_strategy"] == "cloud_contract_only"
    assert payload["privacy_class"] == "public"
    assert payload["cloud_escape_reason"] == "official_managed_cloud_runtime_not_included_in_public_repo"
    assert payload["cloud_escape_erased_approval_audit_args_hash"] is False
    assert payload["audit_requirements"]["cloud_escape_preserves_approval"] is True


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
    assert missing_node.to_public_dict()["route_strategy"] == "deny"
    assert missing_node.local_node_required is True
    assert missing_node.approval_required is True
    assert missing_node.unavailable_reason == "local_node_missing"
    assert with_node.route == "hybrid_coordination_preview"
    assert with_node.to_public_dict()["route_strategy"] == "hybrid"
    assert with_node.private_data_allowed is True
    assert with_node.approval_required is True
    assert with_node.signed_origin_verified is False
    assert with_node.public_repo_execution_available is False


def test_hybrid_public_reasoning_can_be_cloud_contract_candidate_without_private_content() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "hard public reasoning over public API docs",
        mode="official_hybrid_private",
    )
    payload = decision.to_public_dict()

    assert decision.route == "cloud_contract_candidate"
    assert payload["route_strategy"] == "cloud_contract_candidate"
    assert decision.requested_capability == "cloud_orchestration"
    assert payload["task_class"] == "public_reasoning"
    assert payload["privacy_class"] == "public"
    assert decision.cloud_allowed is True
    assert decision.approval_required is True
    assert payload["cloud_contract_candidate"] is True
    assert payload["audit_requirements"]["cloud_escape"] is True
    assert payload["audit_requirements"]["cloud_escape_preserves_approval"] is True
    assert payload["audit_requirements"]["cloud_escape_preserves_args_hash"] is True
    assert payload["audit_requirements"]["args_hash_required"] is True
    assert payload["private_file_content_sent_to_cloud"] is False
    assert payload["provider_key_sent_to_cloud"] is False
    assert payload["raw_prompt_body_sent_to_cloud"] is False
    assert payload["oracle_stub_eligible"] is True
    assert payload["oracle_stub_status"] == "eligible_local_dev_stub"


def test_hybrid_public_reasoning_with_dangerous_terms_is_not_downgraded_to_cloud_candidate() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "hard public reasoning to format disk",
        mode="official_hybrid_private",
    )
    payload = decision.to_public_dict()

    assert decision.route == "local_node_required"
    assert payload["route_strategy"] == "deny"
    assert payload["task_class"] == "dangerous"
    assert decision.requested_capability == "dangerous_operations"
    assert decision.dangerous_operation is True
    assert payload["privacy_class"] == "restricted"
    assert payload["cloud_contract_candidate"] is False
    assert payload["oracle_stub_eligible"] is False
    assert payload["oracle_stub_status"] == "not_eligible"


def test_delete_terms_are_classified_as_dangerous_before_pc_operation() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "delete public docs after hard public reasoning",
        mode="official_hybrid_private",
    )
    payload = decision.to_public_dict()

    assert payload["task_class"] == "dangerous"
    assert decision.requested_capability == "dangerous_operations"
    assert payload["route_strategy"] == "deny"
    assert payload["cloud_contract_candidate"] is False
    assert payload["oracle_stub_eligible"] is False


def test_route_keyword_matching_avoids_partial_word_false_positives() -> None:
    route_preview = _load_route_preview_module()

    undelete_decision = route_preview.preview_route(
        "explain undelete behavior in public docs",
        mode="official_hybrid_private",
    )
    indestructible_decision = route_preview.preview_route(
        "summarize indestructible public material",
        mode="official_hybrid_private",
    )
    run_decision = route_preview.preview_route(
        "start the run",
        mode="official_hybrid_private",
    )
    pc_operations_decision = route_preview.preview_route(
        "plan pc operations",
        mode="official_hybrid_private",
    )

    assert undelete_decision.operation_class == "public_docs"
    assert indestructible_decision.operation_class == "public_docs"
    assert run_decision.operation_class == "pc_operation"
    assert pc_operations_decision.operation_class == "pc_operation"


def test_plural_private_file_terms_still_block_cloud_candidate() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "hard public reasoning over my private files",
        mode="official_hybrid_private",
    )
    payload = decision.to_public_dict()

    assert decision.operation_class == "private_data"
    assert payload["route_strategy"] == "deny"
    assert payload["privacy_class"] == "private"
    assert payload["cloud_contract_candidate"] is False
    assert payload["private_file_content_sent_to_cloud"] is False
    assert payload["oracle_stub_eligible"] is False


def test_plural_local_tool_terms_stay_local_gated() -> None:
    route_preview = _load_route_preview_module()

    local_tools_decision = route_preview.preview_route(
        "reason over public data in local tools",
        mode="official_hybrid_private",
    )
    tool_executions_decision = route_preview.preview_route(
        "plan tool executions over public data",
        mode="official_hybrid_private",
    )

    assert local_tools_decision.operation_class == "local_tool"
    assert local_tools_decision.to_public_dict()["route_strategy"] == "deny"
    assert tool_executions_decision.operation_class == "local_tool"
    assert tool_executions_decision.to_public_dict()["route_strategy"] == "deny"


def test_hybrid_private_reasoning_with_private_file_stays_local_node_gated() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "hard reasoning over my private file",
        mode="official_hybrid_private",
    )
    payload = decision.to_public_dict()

    assert decision.route == "local_node_required"
    assert payload["route_strategy"] == "deny"
    assert payload["privacy_class"] == "private"
    assert payload["cloud_contract_candidate"] is False
    assert payload["private_file_content_sent_to_cloud"] is False


def test_shell_command_preview_requires_local_node_and_approval() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "run a shell command",
        mode="official_hybrid_private",
        has_local_node=True,
    )

    assert decision.route == "hybrid_coordination_preview"
    assert decision.to_public_dict()["route_strategy"] == "hybrid"
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

    assert decision.route == "hybrid_coordination_preview"
    assert decision.unavailable_reason is None
    assert decision.local_node_verification_state == "present_verified"
    assert decision.signed_origin_verified is True
    assert decision.local_node_capability_declared is True
    assert decision.approval_required is True


def test_hybrid_private_requires_enrolled_session_when_requested() -> None:
    route_preview = _load_route_preview_module()

    missing_session = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("private_files",),
        require_enrolled_verified_session=True,
    )
    pending_session = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("private_files",),
        require_enrolled_verified_session=True,
        session_verification_state="pairing_pending",
    )

    assert missing_session.route == "enrolled_verified_node_required"
    assert missing_session.unavailable_reason == "local_node_session_required"
    assert missing_session.session_required is True
    assert missing_session.session_verification_state == "missing"
    assert missing_session.session_gate_satisfied is False
    assert pending_session.route == "enrolled_verified_node_required"
    assert pending_session.unavailable_reason == "pairing_pending"


def test_hybrid_private_not_required_session_state_is_rejected_when_session_required() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("private_files",),
        require_enrolled_verified_session=True,
        session_verification_state="not_required",
    )

    assert decision.route == "enrolled_verified_node_required"
    assert decision.unavailable_reason == "local_node_session_required"
    assert decision.session_required is True
    assert decision.session_verification_state == "missing"
    assert decision.session_verified is False
    assert decision.session_gate_satisfied is False


def test_hybrid_private_enrolled_verified_session_routes_declared_capability() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route(
        "read my local file",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("private_files",),
        require_enrolled_verified_session=True,
        session_verification_state="enrolled_verified",
    )

    assert decision.route == "hybrid_coordination_preview"
    assert decision.unavailable_reason is None
    assert decision.session_required is True
    assert decision.session_enrolled is True
    assert decision.session_verified is True
    assert decision.session_gate_satisfied is True
    assert decision.signed_origin_verified is True


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




def test_deployment_word_variants_do_not_bypass_disabled_gate() -> None:
    route_preview = _load_route_preview_module()

    deploying = route_preview.preview_route(
        "hard public reasoning before deploying to prod",
        mode="official_hybrid_private",
    )
    redeploy = route_preview.preview_route(
        "hard public reasoning before redeploy to prod",
        mode="official_hybrid_private",
    )

    assert deploying.operation_class == "deployment"
    assert deploying.requested_capability == "production_deploy"
    assert deploying.route == "disabled"
    assert deploying.to_public_dict()["cloud_contract_candidate"] is False

    assert redeploy.operation_class == "deployment"
    assert redeploy.requested_capability == "production_deploy"
    assert redeploy.route == "disabled"
    assert redeploy.to_public_dict()["cloud_contract_candidate"] is False

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

    assert decision.route == "self_host_local_preview"
    assert decision.to_public_dict()["route_strategy"] == "local_only"
    assert decision.cloud_allowed is False
    assert decision.approval_required is True
    assert decision.local_node_required is False
    assert decision.runtime_available_in_public_repo is True
    assert decision.public_repo_support_status == "public_local_supported"
    assert decision.public_repo_execution_available is False


def test_self_host_public_docs_are_local_preferred() -> None:
    route_preview = _load_route_preview_module()

    decision = route_preview.preview_route("summarize public docs", mode="full_private_self_host", has_local_node=True)

    assert decision.route == "self_host_local_preview"
    assert decision.to_public_dict()["route_strategy"] == "local_preferred"


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
