from __future__ import annotations

from src.utils.route_policy import band_from_route_score, is_agent_band_allowed


def test_route_band_mapping_boundaries() -> None:
    assert band_from_route_score(0.0) == "instant"
    assert band_from_route_score(0.30) == "instant"
    assert band_from_route_score(0.31) == "task"
    assert band_from_route_score(0.60) == "task"
    assert band_from_route_score(0.61) == "agent"
    assert band_from_route_score(1.0) == "agent"


def test_agent_band_gate_requires_dev_ui_or_admin() -> None:
    assert is_agent_band_allowed(verified_admin=False, dev_ui_enabled=False) is False
    assert is_agent_band_allowed(verified_admin=True, dev_ui_enabled=False) is True
    assert is_agent_band_allowed(verified_admin=False, dev_ui_enabled=True) is True

