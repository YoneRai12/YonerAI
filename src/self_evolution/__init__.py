"""Public-safe self-evolution proposal utilities.

This package is intentionally proposal-only. It does not collect telemetry,
scrape external sources, mutate code, create branches, merge pull requests, or
deploy anything.
"""

from .proposals import ProposalPacket, generate_proposal, generate_proposals_from_fixture
from .scoring import ScoreBreakdown, score_signal
from .signals import SignalEvent, UnsafeSignalError, load_signal_fixture, normalize_signal
from .context import SafeRouteTrustContext, normalize_route_trust_context
from .loop import (
    SELF_EVOLUTION_LOOP_VERSION,
    EvolutionApprovalDraft,
    EvolutionClassification,
    EvolutionProposal,
    EvolutionProposalScorecard,
    SyntheticEvolutionEvent,
    classify_synthetic_event,
    generate_evolution_proposal,
)

__all__ = [
    "SELF_EVOLUTION_LOOP_VERSION",
    "EvolutionClassification",
    "EvolutionApprovalDraft",
    "EvolutionProposal",
    "EvolutionProposalScorecard",
    "ProposalPacket",
    "ScoreBreakdown",
    "SignalEvent",
    "SafeRouteTrustContext",
    "SyntheticEvolutionEvent",
    "UnsafeSignalError",
    "classify_synthetic_event",
    "generate_evolution_proposal",
    "generate_proposal",
    "generate_proposals_from_fixture",
    "load_signal_fixture",
    "normalize_signal",
    "normalize_route_trust_context",
    "score_signal",
]
