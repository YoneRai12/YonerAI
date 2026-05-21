from __future__ import annotations

from src.self_evolution import (
    SELF_EVOLUTION_LOOP_VERSION,
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
    assert proposal.owner_approval_required is True
    assert proposal.auto_apply_allowed is False
    assert proposal.github_write_allowed is False
    assert proposal.deploy_allowed is False
    assert "public-safe regression fixture" in proposal.test_idea


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
    assert proposal.github_write_allowed is False
    assert proposal.deploy_allowed is False
    assert "no_raw_prompt_or_completion_ingestion" in proposal.non_actions


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
    assert payload["github_write_allowed"] is False
    assert payload["deploy_allowed"] is False
