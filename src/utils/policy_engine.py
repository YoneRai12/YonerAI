from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    requires_code: bool
    reason: str


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def decide_tool_policy(
    *,
    profile: str,
    role: str,
    tool_name: str,
    risk_score: int,
    risk_level: str,
) -> PolicyDecision:
    """
    "事故らない" shared/guest policy as code.

    Principles:
    - Default safe.
    - shared + guest: allow LOW tools (via allowlist), MEDIUM/HIGH require approvals, CRITICAL blocked by default.
    - shared + owner: MEDIUM is allowed, HIGH/CRITICAL require approvals (owner does not bypass in shared).
    - private: keep existing owner-centric behavior; non-owner remains allowlist-based elsewhere.
    """
    prof = (profile or "private").strip().lower()
    r = (role or "guest").strip().lower()
    score = int(risk_score or 0)
    lvl = (risk_level or "").strip().upper()
    is_owner = r == "owner"

    # CRITICAL in shared for guests is blocked unless explicitly allowed.
    allow_shared_critical = _parse_bool_env("ORA_SHARED_ALLOW_CRITICAL", False)

    if prof == "shared":
        if (not is_owner) and score >= 90 and (not allow_shared_critical):
            return PolicyDecision(
                allowed=False,
                requires_approval=False,
                requires_code=False,
                reason="shared_guest_critical_blocked",
            )

        # Owner in shared does not bypass approvals.
        if score >= 90:
            return PolicyDecision(
                allowed=True,
                requires_approval=True,
                requires_code=True,
                reason="shared_critical_requires_code",
            )
        if score >= 30:
            return PolicyDecision(
                allowed=True,
                requires_approval=True,
                requires_code=False,
                reason="shared_nonlow_requires_approval",
            )
        return PolicyDecision(
            allowed=True,
            requires_approval=False,
            requires_code=False,
            reason="shared_low_allowed",
        )

    # private (default)
    if score >= 90:
        return PolicyDecision(
            allowed=True,
            requires_approval=True,
            requires_code=True,
            reason="private_critical_requires_code",
        )
    if score >= 60:
        return PolicyDecision(
            allowed=True,
            requires_approval=True,
            requires_code=False,
            reason="private_high_requires_approval",
        )

    # Keep MEDIUM+ for non-owners gated in approvals.py policy_for; but we still allow here.
    # role-based allowlist is enforced separately by src/utils/access_control.py.
    return PolicyDecision(
        allowed=True,
        requires_approval=False,
        requires_code=False,
        reason=f"private_{lvl.lower() or 'low'}_allowed",
    )

