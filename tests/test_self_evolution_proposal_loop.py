from __future__ import annotations

from src.self_evolution import (
    SELF_EVOLUTION_LOOP_VERSION,
    SafeRouteTrustContext,
    SyntheticEvolutionEvent,
    generate_evolution_proposal,
)


def test_failed_step_becomes_owner_reviewed_onboarding_proposal() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="failed_step",
            summary="Synthetic setup step failed during public smoke.",
            severity=4,
            confidence=0.8,
        )
    )

    assert proposal.schema_version == SELF_EVOLUTION_LOOP_VERSION
    assert proposal.category == "onboarding"
    assert proposal.proposal_only is True
    assert proposal.official_cloud_observation == "simulated_only"
    assert proposal.real_user_behavior_analytics is False
    assert proposal.support_email_ingestion is False
    assert proposal.owner_approval_required is True
    assert proposal.auto_apply_allowed is False
    assert proposal.auto_issue_creation is False
    assert proposal.auto_pr_creation is False
    assert proposal.auto_merge is False
    assert proposal.github_write_allowed is False
    assert proposal.deploy_allowed is False
    assert "public-safe regression fixture" in proposal.test_idea
    assert "official_cloud_observation_simulated_only" in proposal.non_actions


def test_bug_report_generates_issue_test_patch_and_rollback_drafts() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary="Synthetic route preview displayed the wrong unavailable reason.",
            severity=5,
            confidence=0.9,
        )
    )

    assert proposal.category == "bug_fix"
    assert proposal.issue_draft.startswith("[proposal-only] bug_fix")
    assert "regression fixture" in proposal.test_idea
    assert "owner approval" in proposal.patch_plan
    assert "discard the proposal packet" in proposal.rollback_plan
    assert "no_code_mutation" in proposal.non_actions


def test_support_ticket_generates_reply_draft_and_issue_candidate() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="support_ticket",
            summary="Synthetic user asks why hybrid mode needs a Local Node.",
            severity=3,
            confidence=0.7,
        )
    )

    assert proposal.category == "support_response"
    assert "Thanks for the report" in proposal.reply_draft
    assert proposal.issue_draft.startswith("[proposal-only] support_response")
    assert proposal.required_approval_gate == "owner_review_required"


def test_low_confidence_proposal_is_gated() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="user_feedback",
            summary="Synthetic vague feedback.",
            severity=2,
            confidence=0.2,
        )
    )

    assert proposal.category == "guardrail"
    assert proposal.confidence == 0.2
    assert proposal.required_approval_gate == "owner_review_required"
    assert proposal.owner_approval_required is True


def test_privacy_sensitive_event_is_redacted_and_rejected_without_auto_actions() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary="Synthetic event includes privacy-sensitive text that must not be retained.",
            severity=5,
            confidence=0.9,
            privacy_classification="privacy_sensitive",
        )
    )

    assert proposal.category == "guardrail"
    assert proposal.redacted_summary == "[redacted synthetic privacy-sensitive event]"
    assert proposal.issue_draft.startswith("[rejected]")
    assert "rejected before proposal generation" in proposal.reply_draft
    assert proposal.auto_apply_allowed is False
    assert proposal.official_cloud_observation == "simulated_only"
    assert proposal.real_user_behavior_analytics is False
    assert proposal.support_email_ingestion is False
    assert proposal.auto_issue_creation is False
    assert proposal.auto_pr_creation is False
    assert proposal.auto_merge is False
    assert proposal.github_write_allowed is False
    assert proposal.deploy_allowed is False
    assert "no_raw_prompt_or_completion_ingestion" in proposal.non_actions
    assert "no_real_user_behavior_analytics" in proposal.non_actions


def test_summary_with_private_markers_is_redacted_before_public_output() -> None:
    unsafe_summary = "Synthetic report included C:\\Users\\owner\\secret.txt and token=alpha-fixture."

    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary=unsafe_summary,
            severity=5,
            confidence=0.9,
        )
    )
    payload = proposal.to_public_dict()
    serialized = str(payload)

    assert proposal.category == "guardrail"
    assert proposal.privacy_classification == "privacy_sensitive"
    assert proposal.redacted_summary == "[redacted synthetic privacy-sensitive event]"
    assert unsafe_summary not in serialized
    assert "C:\\Users" not in serialized
    assert "token=alpha-fixture" not in serialized
    assert proposal.auto_issue_creation is False
    assert proposal.github_write_allowed is False
    assert proposal.deploy_allowed is False


def test_no_auto_apply_action_exists_in_public_output() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="feature_used",
            summary="Synthetic feature was useful.",
            severity=2,
            confidence=0.8,
        )
    )
    payload = proposal.to_public_dict()

    assert "apply" not in payload
    assert payload["auto_apply_allowed"] is False
    assert payload["official_cloud_observation"] == "simulated_only"
    assert payload["real_user_behavior_analytics"] is False
    assert payload["support_email_ingestion"] is False
    assert payload["auto_issue_creation"] is False
    assert payload["auto_pr_creation"] is False
    assert payload["auto_merge"] is False
    assert payload["github_write_allowed"] is False
    assert payload["deploy_allowed"] is False


def test_hybrid_missing_node_event_produces_route_trust_aware_proposal() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="failed_step",
            summary="Synthetic hybrid private file step was gated.",
            severity=4,
            confidence=0.8,
        ),
        route_trust_context={
            "mode": "official_hybrid_private",
            "route": "local_node_required",
            "requested_capability": "private_files",
            "local_node_verification_state": "missing",
            "approval_required": True,
            "local_node_required": True,
            "signed_origin_verified": False,
            "trusted": True,
            "production_trust_material": True,
            "unavailable_reason": "local_node_missing",
            "raw_prompt": "must not leak",
            "signature": "must not leak",
        },
    )

    payload = proposal.to_public_dict()
    context = payload["route_trust_context"]

    assert proposal.category == "onboarding"
    assert "Local Node is missing" in proposal.reply_draft
    assert context["diagnosis"] == "hybrid_local_node_missing"
    assert context["trusted"] is False
    assert context["production_trust_material"] is False
    assert "raw_prompt" not in context
    assert "signature" not in context
    assert proposal.auto_apply_allowed is False
    assert proposal.github_write_allowed is False
    assert proposal.deploy_allowed is False


def test_unverified_node_event_produces_verification_guidance() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary="Synthetic route preview allowed an unverified node.",
            severity=5,
            confidence=0.9,
        ),
        route_trust_context=SafeRouteTrustContext(
            mode="official_hybrid_private",
            route="local_node_required",
            requested_capability="pc_operations",
            local_node_verification_state="present_unverified",
            approval_required=True,
            local_node_required=True,
            signed_origin_verified=False,
            trusted=False,
            production_trust_material=False,
            unavailable_reason="unverified_node_denied",
            diagnosis="hybrid_local_node_unverified",
        ),
    )

    payload = proposal.to_public_dict()

    assert proposal.category == "bug_fix"
    assert "present but unverified" in proposal.issue_draft
    assert payload["route_trust_context"]["diagnosis"] == "hybrid_local_node_unverified"
    assert payload["route_trust_context"]["signed_origin_verified"] is False


def test_privacy_sensitive_route_context_is_not_attached() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary="Synthetic privacy-sensitive hybrid failure.",
            severity=5,
            confidence=0.9,
            privacy_classification="privacy_sensitive",
        ),
        route_trust_context={
            "mode": "official_hybrid_private",
            "route": "hybrid_coordination",
            "requested_capability": "private_files",
            "local_node_verification_state": "present_verified",
        },
    )

    payload = proposal.to_public_dict()

    assert proposal.category == "guardrail"
    assert proposal.route_trust_context is None
    assert payload["route_trust_context"] is None
    assert proposal.auto_apply_allowed is False
    assert proposal.github_write_allowed is False
    assert proposal.deploy_allowed is False


def test_failed_hybrid_route_produces_scorecard_mode_experience_gain() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="failed_step",
            summary="Synthetic enrolled Local Node route was missing a session.",
            severity=4,
            confidence=0.85,
        ),
        route_trust_context={
            "mode": "official_hybrid_private",
            "route": "local_node_required",
            "requested_capability": "private_files",
            "local_node_verification_state": "missing",
            "approval_required": True,
            "local_node_required": True,
            "signed_origin_verified": False,
            "unavailable_reason": "local_node_missing",
        },
    )

    assert proposal.scorecard.mode_experience_gain == 5
    assert proposal.scorecard.user_impact == 4
    assert proposal.approval_draft.proposal_only is True
    assert proposal.approval_draft.github_write_allowed is False
    assert proposal.approval_draft.deploy_allowed is False
    assert "owner approval" in proposal.approval_draft.patch_plan


def test_unverified_local_node_support_ticket_gets_approval_draft() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="support_ticket",
            summary="Synthetic support ticket asks how to verify a Local Node.",
            severity=3,
            confidence=0.7,
        ),
        route_trust_context={
            "mode": "official_hybrid_private",
            "route": "local_node_required",
            "requested_capability": "local_tools",
            "local_node_verification_state": "present_unverified",
            "approval_required": True,
            "local_node_required": True,
            "signed_origin_verified": False,
            "unavailable_reason": "unverified_node_denied",
        },
    )

    payload = proposal.to_public_dict()

    assert proposal.category == "support_response"
    assert proposal.scorecard.mode_experience_gain == 5
    assert proposal.approval_draft.required_approver in {"maintainer", "owner"}
    assert "support_response" in proposal.approval_draft.release_note_draft
    assert payload["scorecard"]["provider_independence_gain"] >= 2
    assert payload["approval_draft"]["proposal_only"] is True


def test_high_risk_or_privacy_sensitive_scorecard_requires_owner_approval() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary="Synthetic privacy-sensitive report.",
            severity=5,
            confidence=0.9,
            privacy_classification="privacy_sensitive",
        )
    )

    assert proposal.scorecard.risk == 5
    assert proposal.approval_draft.required_approver == "owner"
    assert proposal.approval_draft.patch_plan.startswith("No patch plan")
    assert proposal.approval_draft.deploy_allowed is False


def test_scorecard_output_remains_text_only_proposal_only() -> None:
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary="Synthetic route trust regression.",
            severity=4,
            confidence=0.75,
        )
    )
    payload = proposal.to_public_dict()

    assert payload["proposal_only"] is True
    assert payload["official_cloud_observation"] == "simulated_only"
    assert payload["real_user_behavior_analytics"] is False
    assert payload["support_email_ingestion"] is False
    assert payload["auto_issue_creation"] is False
    assert payload["auto_pr_creation"] is False
    assert payload["auto_merge"] is False
    assert payload["approval_draft"]["github_write_allowed"] is False
    assert payload["approval_draft"]["deploy_allowed"] is False
    assert "auto_apply" not in payload["approval_draft"]
    assert isinstance(payload["approval_draft"]["patch_plan"], str)
    assert isinstance(payload["approval_draft"]["rollback_plan"], str)
