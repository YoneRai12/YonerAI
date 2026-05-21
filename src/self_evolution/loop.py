from __future__ import annotations

from dataclasses import asdict, dataclass
from collections.abc import Mapping
from typing import Literal

from .context import SafeRouteTrustContext, normalize_route_trust_context


SELF_EVOLUTION_LOOP_VERSION = "proposal-only-self-evolution-loop-0.1"

SyntheticEventType = Literal[
    "feature_used",
    "failed_step",
    "dropoff",
    "bug_report",
    "support_ticket",
    "user_feedback",
]
PrivacyClassification = Literal["synthetic", "public_fixture", "privacy_sensitive"]
ProposalCategory = Literal["product_improvement", "bug_fix", "support_response", "onboarding", "guardrail"]


@dataclass(frozen=True)
class SyntheticEvolutionEvent:
    event_type: SyntheticEventType
    summary: str
    severity: int
    confidence: float
    privacy_classification: PrivacyClassification = "synthetic"


@dataclass(frozen=True)
class EvolutionClassification:
    category: ProposalCategory
    severity: int
    confidence: float
    privacy_classification: PrivacyClassification
    accepted: bool
    reason: str
    approval_gate: str

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvolutionProposal:
    schema_version: str
    event_type: SyntheticEventType
    category: ProposalCategory
    severity: int
    confidence: float
    privacy_classification: PrivacyClassification
    proposal_only: bool
    owner_approval_required: bool
    auto_apply_allowed: bool
    github_write_allowed: bool
    deploy_allowed: bool
    reply_draft: str
    issue_draft: str
    test_idea: str
    patch_plan: str
    rollback_plan: str
    required_approval_gate: str
    redacted_summary: str
    route_trust_context: SafeRouteTrustContext | None
    scorecard: EvolutionProposalScorecard
    approval_draft: EvolutionApprovalDraft
    non_actions: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        if self.route_trust_context is not None:
            payload["route_trust_context"] = self.route_trust_context.to_public_dict()
        payload["scorecard"] = self.scorecard.to_public_dict()
        payload["approval_draft"] = self.approval_draft.to_public_dict()
        payload["non_actions"] = list(self.non_actions)
        return payload


@dataclass(frozen=True)
class EvolutionProposalScorecard:
    user_impact: int
    frequency_hint: int
    risk: int
    implementation_cost: int
    provider_independence_gain: int
    mode_experience_gain: int
    rollback_complexity: int
    confidence: float

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvolutionApprovalDraft:
    required_approver: str
    test_plan: str
    patch_plan: str
    rollback_plan: str
    release_note_draft: str
    go_to_market_note: str | None
    proposal_only: bool
    github_write_allowed: bool
    deploy_allowed: bool

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_synthetic_event(event: SyntheticEvolutionEvent) -> EvolutionClassification:
    if event.privacy_classification == "privacy_sensitive":
        return EvolutionClassification(
            category="guardrail",
            severity=event.severity,
            confidence=event.confidence,
            privacy_classification=event.privacy_classification,
            accepted=False,
            reason="privacy_sensitive_event_rejected",
            approval_gate="owner_review_required_before_any_follow_up",
        )
    if event.confidence < 0.5:
        return EvolutionClassification(
            category="guardrail",
            severity=event.severity,
            confidence=event.confidence,
            privacy_classification=event.privacy_classification,
            accepted=True,
            reason="low_confidence_requires_owner_review",
            approval_gate="owner_review_required",
        )
    if event.event_type == "bug_report":
        category: ProposalCategory = "bug_fix"
    elif event.event_type == "support_ticket":
        category = "support_response"
    elif event.event_type in {"failed_step", "dropoff"}:
        category = "onboarding"
    else:
        category = "product_improvement"
    return EvolutionClassification(
        category=category,
        severity=event.severity,
        confidence=event.confidence,
        privacy_classification=event.privacy_classification,
        accepted=True,
        reason="synthetic_public_safe_event_classified",
        approval_gate="owner_review_required",
    )


def _bounded_severity(value: int) -> int:
    return max(1, min(5, value))


def _bounded_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def _redact_summary(summary: str, privacy_classification: PrivacyClassification) -> str:
    cleaned = " ".join(summary.split()).strip()
    if privacy_classification == "privacy_sensitive":
        return "[redacted synthetic privacy-sensitive event]"
    return cleaned[:180] or "Synthetic event summary unavailable."


def generate_evolution_proposal(
    event: SyntheticEvolutionEvent,
    route_trust_context: Mapping[str, object] | SafeRouteTrustContext | None = None,
) -> EvolutionProposal:
    normalized_event = SyntheticEvolutionEvent(
        event_type=event.event_type,
        summary=event.summary,
        severity=_bounded_severity(event.severity),
        confidence=_bounded_confidence(event.confidence),
        privacy_classification=event.privacy_classification,
    )
    classification = classify_synthetic_event(normalized_event)
    summary = _redact_summary(normalized_event.summary, normalized_event.privacy_classification)
    blocked = not classification.accepted
    safe_context = None if blocked or route_trust_context is None else normalize_route_trust_context(route_trust_context)
    context_note = _context_note(safe_context)
    reply_draft = (
        "Thanks for the report. This synthetic fixture suggests a proposal should be reviewed by the owner."
        f"{context_note}"
        if not blocked
        else "This event was rejected before proposal generation because it is privacy-sensitive."
    )
    issue_draft = (
        f"[proposal-only] {classification.category}: {summary}{context_note}"
        if not blocked
        else "[rejected] privacy-sensitive event requires manual handling outside this simulator"
    )
    test_idea = (
        f"Add a public-safe regression fixture for {normalized_event.event_type}."
        if classification.category in {"bug_fix", "onboarding", "product_improvement"}
        else "Add a support response review fixture."
    )
    patch_plan = (
        "Draft a narrow patch plan after owner approval; do not mutate code from this simulator."
        f"{context_note}"
        if not blocked
        else "No patch plan generated for rejected privacy-sensitive input."
    )
    rollback_plan = (
        "If owner review rejects this proposal, discard the proposal packet without branch, PR, merge, deploy, or release."
    )
    scorecard = _build_scorecard(normalized_event, classification, safe_context)
    approval_draft = _build_approval_draft(
        event=normalized_event,
        classification=classification,
        summary=summary,
        test_idea=test_idea,
        patch_plan=patch_plan,
        rollback_plan=rollback_plan,
        scorecard=scorecard,
        blocked=blocked,
    )
    return EvolutionProposal(
        schema_version=SELF_EVOLUTION_LOOP_VERSION,
        event_type=normalized_event.event_type,
        category=classification.category,
        severity=classification.severity,
        confidence=classification.confidence,
        privacy_classification=classification.privacy_classification,
        proposal_only=True,
        owner_approval_required=True,
        auto_apply_allowed=False,
        github_write_allowed=False,
        deploy_allowed=False,
        reply_draft=reply_draft,
        issue_draft=issue_draft,
        test_idea=test_idea,
        patch_plan=patch_plan,
        rollback_plan=rollback_plan,
        required_approval_gate=classification.approval_gate,
        redacted_summary=summary,
        route_trust_context=safe_context,
        scorecard=scorecard,
        approval_draft=approval_draft,
        non_actions=(
            "no_real_telemetry_collection",
            "no_raw_prompt_or_completion_ingestion",
            "no_code_mutation",
            "no_issue_creation",
            "no_branch_or_pr_creation",
            "no_auto_merge",
            "no_deploy",
        ),
    )


def _context_note(context: SafeRouteTrustContext | None) -> str:
    if context is None:
        return ""
    if context.diagnosis == "hybrid_local_node_missing":
        return " Route/trust diagnosis: Local Node is missing, so private or local work remains gated."
    if context.diagnosis == "hybrid_local_node_unverified":
        return " Route/trust diagnosis: Local Node is present but unverified, so private or local work remains denied."
    if context.diagnosis in {
        "hybrid_local_node_expired",
        "hybrid_local_node_invalid_signature",
        "hybrid_local_node_wrong_audience",
    }:
        return " Route/trust diagnosis: Local Node manifest verification failed, so route preview must stay gated."
    if context.diagnosis == "hybrid_capability_not_declared":
        return " Route/trust diagnosis: verified Local Node did not declare the requested capability."
    if context.diagnosis == "hybrid_coordination_requires_owner_approval":
        return " Route/trust diagnosis: verified hybrid coordination still requires owner approval."
    return " Route/trust diagnosis: public-safe route context was recorded for owner review."


def _build_scorecard(
    event: SyntheticEvolutionEvent,
    classification: EvolutionClassification,
    context: SafeRouteTrustContext | None,
) -> EvolutionProposalScorecard:
    severity = _bounded_severity(event.severity)
    hybrid_context = context is not None and context.mode == "official_hybrid_private"
    route_blocked = context is not None and context.route in {"local_node_required", "disabled"}
    return EvolutionProposalScorecard(
        user_impact=severity,
        frequency_hint=3 if event.event_type in {"failed_step", "bug_report", "support_ticket"} else 2,
        risk=5 if classification.privacy_classification == "privacy_sensitive" else max(2, severity if route_blocked else severity - 1),
        implementation_cost=3 if classification.category in {"bug_fix", "onboarding"} else 2,
        provider_independence_gain=3 if event.event_type in {"failed_step", "bug_report"} else 2,
        mode_experience_gain=5 if hybrid_context or route_blocked else 2,
        rollback_complexity=2 if classification.category in {"support_response", "onboarding"} else 3,
        confidence=classification.confidence,
    )


def _build_approval_draft(
    *,
    event: SyntheticEvolutionEvent,
    classification: EvolutionClassification,
    summary: str,
    test_idea: str,
    patch_plan: str,
    rollback_plan: str,
    scorecard: EvolutionProposalScorecard,
    blocked: bool,
) -> EvolutionApprovalDraft:
    required_approver = "owner" if scorecard.risk >= 4 or blocked else "maintainer"
    release_note = (
        f"Proposal-only candidate for {classification.category}: {summary}"
        if not blocked
        else "No release note draft for rejected privacy-sensitive input."
    )
    go_to_market_note = (
        "Highlight safer Hybrid Private onboarding after owner approval."
        if event.event_type in {"failed_step", "support_ticket"} and not blocked
        else None
    )
    return EvolutionApprovalDraft(
        required_approver=required_approver,
        test_plan=test_idea,
        patch_plan=patch_plan,
        rollback_plan=rollback_plan,
        release_note_draft=release_note,
        go_to_market_note=go_to_market_note,
        proposal_only=True,
        github_write_allowed=False,
        deploy_allowed=False,
    )
