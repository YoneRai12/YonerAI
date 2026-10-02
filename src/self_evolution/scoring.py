from __future__ import annotations

from dataclasses import dataclass

from .signals import SignalEvent


@dataclass(frozen=True)
class ScoreBreakdown:
    product_fit: int
    user_pain: int
    implementation_cost: int
    provider_independence_gain: int
    same_experience_gain: int
    hype_debt_risk: int
    privacy_risk: int
    priority: int


def _clamp(value: int) -> int:
    return max(1, min(5, value))


def score_signal(signal: SignalEvent) -> ScoreBreakdown:
    product_fit = _clamp(signal.severity + (1 if signal.kind in {"complaint", "drop_off", "failure"} else 0))
    user_pain = _clamp(signal.severity + signal.frequency - 2)
    implementation_cost = _clamp(3 if signal.kind in {"docs_confusion", "onboarding"} else 4)
    provider_independence_gain = _clamp(3 + (1 if "provider" in signal.summary.lower() else 0))
    same_experience_gain = _clamp(3 + (1 if "same" in signal.summary.lower() or "surface" in signal.summary.lower() else 0))
    hype_debt_risk = _clamp(2 + (1 if "launch" in signal.summary.lower() else 0))
    privacy_risk = _clamp(1 if signal.privacy_class in {"public_fixture", "synthetic"} else 3)

    positive = product_fit + user_pain + provider_independence_gain + same_experience_gain
    risk = implementation_cost + hype_debt_risk + privacy_risk
    priority = _clamp(round((positive - risk + 10) / 3))

    return ScoreBreakdown(
        product_fit=product_fit,
        user_pain=user_pain,
        implementation_cost=implementation_cost,
        provider_independence_gain=provider_independence_gain,
        same_experience_gain=same_experience_gain,
        hype_debt_risk=hype_debt_risk,
        privacy_risk=privacy_risk,
        priority=priority,
    )
