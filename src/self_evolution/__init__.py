"""Public-safe self-evolution proposal utilities.

This package is intentionally proposal-only. It does not collect telemetry,
scrape external sources, mutate code, create branches, merge pull requests, or
deploy anything.
"""

from .proposals import ProposalPacket, generate_proposal, generate_proposals_from_fixture
from .scoring import ScoreBreakdown, score_signal
from .signals import SignalEvent, UnsafeSignalError, load_signal_fixture, normalize_signal

__all__ = [
    "ProposalPacket",
    "ScoreBreakdown",
    "SignalEvent",
    "UnsafeSignalError",
    "generate_proposal",
    "generate_proposals_from_fixture",
    "load_signal_fixture",
    "normalize_signal",
    "score_signal",
]
