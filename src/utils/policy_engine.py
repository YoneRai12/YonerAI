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

def _parse_csv_env(name: str) -> set[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return set()
    return {x.strip() for x in raw.split(",") if x.strip()}


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

    # Global owner knobs (applies to both profiles):
    # - ORA_OWNER_APPROVALS: high|critical_only|off
    # - ORA_OWNER_APPROVAL_SKIP_TOOLS: CSV of tool names to skip approval for
    global_owner_mode = (os.getenv("ORA_OWNER_APPROVALS") or "").strip().lower()
    global_owner_skip = _parse_csv_env("ORA_OWNER_APPROVAL_SKIP_TOOLS")

    # CRITICAL in shared for guests is blocked unless explicitly allowed.
    allow_shared_critical = _parse_bool_env("ORA_SHARED_ALLOW_CRITICAL", False)

    if prof == "shared":
        # Owner approvals in shared are strict by default, but can be relaxed explicitly.
        shared_owner_mode = (os.getenv("ORA_SHARED_OWNER_APPROVALS") or global_owner_mode or "high").strip().lower()
        shared_owner_skip = _parse_csv_env("ORA_SHARED_OWNER_APPROVAL_SKIP_TOOLS") | global_owner_skip

        # Guest approval threshold (default: require approval from MEDIUM+ i.e. score>=30).
        raw_thr = (os.getenv("ORA_SHARED_GUEST_APPROVAL_MIN_SCORE") or "30").strip()
        try:
            guest_thr = int(raw_thr)
        except Exception:
            guest_thr = 30
        guest_thr = max(0, min(200, guest_thr))

        if (not is_owner) and score >= 90 and (not allow_shared_critical):
            return PolicyDecision(
                allowed=False,
                requires_approval=False,
                requires_code=False,
                reason="shared_guest_critical_blocked",
            )

        # Owner in shared: allow optional skip/relax.
        if is_owner and tool_name and tool_name in shared_owner_skip:
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                requires_code=False,
                reason="shared_owner_skip_approval",
            )

        if is_owner and shared_owner_mode == "off":
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                requires_code=False,
                reason="shared_owner_approvals_off",
            )

        if is_owner and shared_owner_mode == "critical_only":
            if score >= 90:
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    requires_code=True,
                    reason="shared_owner_critical_requires_code",
                )
            # Below CRITICAL: no approval.
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                requires_code=False,
                reason="shared_owner_no_approval_below_critical",
            )

        # Default shared policy:
        # - owner: approvals for MEDIUM+ (score>=30), code for CRITICAL
        # - guest: approvals from guest_thr (default 30), code for CRITICAL
        if score >= 90:
            return PolicyDecision(
                allowed=True,
                requires_approval=True,
                requires_code=True,
                reason="shared_critical_requires_code",
            )
        min_thr = 30 if is_owner else guest_thr
        if score >= min_thr:
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
    if is_owner:
        # Quality-of-life knobs for owner in private profile.
        # Keep defaults strict; allow explicit opt-outs for trusted solo use.
        skip = _parse_csv_env("ORA_PRIVATE_OWNER_APPROVAL_SKIP_TOOLS") | global_owner_skip
        if tool_name and tool_name in skip:
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                requires_code=False,
                reason="private_owner_skip_approval",
            )

        # ORA_PRIVATE_OWNER_APPROVALS:
        # - high (default): require approval for HIGH+ (score>=60) and code for CRITICAL (>=90)
        # - critical_only: only CRITICAL requires approval/code
        # - off: no approvals at all (not recommended)
        mode = (os.getenv("ORA_PRIVATE_OWNER_APPROVALS") or global_owner_mode or "high").strip().lower()
        if mode == "off":
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                requires_code=False,
                reason="private_owner_approvals_off",
            )
        if mode == "critical_only":
            if score >= 90:
                return PolicyDecision(
                    allowed=True,
                    requires_approval=True,
                    requires_code=True,
                    reason="private_owner_critical_requires_code",
                )
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                requires_code=False,
                reason="private_owner_no_approval_below_critical",
            )

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
