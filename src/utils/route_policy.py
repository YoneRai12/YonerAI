from __future__ import annotations


def band_from_route_score(score: float) -> str:
    """Map scalar route_score [0..1] to stable band labels."""
    if score <= 0.30:
        return "instant"
    if score <= 0.60:
        return "task"
    return "agent"


def is_agent_band_allowed(*, verified_admin: bool, dev_ui_enabled: bool) -> bool:
    """Band2 entry is allowed for verified admins or explicit dev UI mode."""
    return bool(verified_admin or dev_ui_enabled)

