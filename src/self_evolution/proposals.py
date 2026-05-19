from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .scoring import ScoreBreakdown, score_signal
from .signals import SignalEvent, load_signal_fixture


PROPOSAL_MARKDOWN_TEXT = {
    "status": "Status: owner review required",
    "not_auto_applied": "This proposal is not auto-applied. It does not authorize code changes, publication, or deployment.",
    "problem_statement": "## Problem Statement",
    "safe_evidence": "## Safe Evidence Summary",
    "candidate": "## Candidate",
    "score": "## Score",
    "required_tests": "## Required Tests",
    "rollback": "## Rollback Expectation",
    "approval_gate": "## Approval Gate",
}


@dataclass(frozen=True)
class ProposalPacket:
    id: str
    signal: SignalEvent
    score: ScoreBreakdown
    title: str
    proposed_change: str
    required_tests: tuple[str, ...]
    rollback_note: str
    owner_decision_required: bool = True
    approved: bool = False

    def to_markdown(self) -> str:
        evidence = "\n".join(f"- {item}" for item in self.signal.evidence)
        tests = "\n".join(f"- {item}" for item in self.required_tests)
        return "\n".join(
            [
                f"# Proposal: {self.title}",
                "",
                PROPOSAL_MARKDOWN_TEXT["status"],
                "",
                PROPOSAL_MARKDOWN_TEXT["not_auto_applied"],
                "",
                PROPOSAL_MARKDOWN_TEXT["problem_statement"],
                "",
                self.signal.summary,
                "",
                PROPOSAL_MARKDOWN_TEXT["safe_evidence"],
                "",
                evidence,
                "",
                PROPOSAL_MARKDOWN_TEXT["candidate"],
                "",
                self.proposed_change,
                "",
                PROPOSAL_MARKDOWN_TEXT["score"],
                "",
                f"- product_fit: {self.score.product_fit}",
                f"- user_pain: {self.score.user_pain}",
                f"- implementation_cost: {self.score.implementation_cost}",
                f"- provider_independence_gain: {self.score.provider_independence_gain}",
                f"- same_experience_gain: {self.score.same_experience_gain}",
                f"- hype_debt_risk: {self.score.hype_debt_risk}",
                f"- privacy_risk: {self.score.privacy_risk}",
                f"- priority: {self.score.priority}",
                "",
                PROPOSAL_MARKDOWN_TEXT["required_tests"],
                "",
                tests,
                "",
                PROPOSAL_MARKDOWN_TEXT["rollback"],
                "",
                self.rollback_note,
                "",
                PROPOSAL_MARKDOWN_TEXT["approval_gate"],
                "",
                "- owner_decision_required: true",
                "- approved: false",
                "- no automatic code mutation",
                "- no automatic branch, PR, merge, deploy, or release",
                "- no real telemetry collection",
                "- no SNS scraping",
                "",
            ]
        )


def generate_proposal(signal: SignalEvent) -> ProposalPacket:
    score = score_signal(signal)
    title = f"{signal.kind}: {signal.summary[:72]}"
    return ProposalPacket(
        id=f"proposal-{signal.id}",
        signal=signal,
        score=score,
        title=title,
        proposed_change=(
            "Prepare a narrow owner-reviewed improvement spec for the affected public surface. "
            "Keep implementation in a later approved lane."
        ),
        required_tests=(
            "public-safe fixture contract test",
            "forbidden field rejection test",
            "owner approval gate test",
        ),
        rollback_note="If owner review rejects the proposal, discard the proposal packet without changing runtime behavior.",
    )


def generate_proposals_from_fixture(path: str | Path) -> list[ProposalPacket]:
    return [generate_proposal(signal) for signal in load_signal_fixture(path)]
