from __future__ import annotations


from src.utils.policy_engine import decide_tool_policy


def test_private_owner_default_requires_high_approval(monkeypatch) -> None:
    monkeypatch.delenv("ORA_PRIVATE_OWNER_APPROVALS", raising=False)
    monkeypatch.delenv("ORA_PRIVATE_OWNER_APPROVAL_SKIP_TOOLS", raising=False)
    monkeypatch.delenv("ORA_OWNER_APPROVALS", raising=False)
    monkeypatch.delenv("ORA_OWNER_APPROVAL_SKIP_TOOLS", raising=False)
    d = decide_tool_policy(
        profile="private",
        role="owner",
        tool_name="web_download",
        risk_score=60,
        risk_level="HIGH",
    )
    assert d.allowed is True
    assert d.requires_approval is True


def test_private_owner_skip_tool_disables_approval(monkeypatch) -> None:
    monkeypatch.delenv("ORA_OWNER_APPROVALS", raising=False)
    monkeypatch.delenv("ORA_OWNER_APPROVAL_SKIP_TOOLS", raising=False)
    monkeypatch.setenv("ORA_PRIVATE_OWNER_APPROVAL_SKIP_TOOLS", "web_download,read_web_page")
    d = decide_tool_policy(
        profile="private",
        role="owner",
        tool_name="web_download",
        risk_score=60,
        risk_level="HIGH",
    )
    assert d.allowed is True
    assert d.requires_approval is False


def test_private_owner_critical_only(monkeypatch) -> None:
    monkeypatch.delenv("ORA_OWNER_APPROVALS", raising=False)
    monkeypatch.delenv("ORA_OWNER_APPROVAL_SKIP_TOOLS", raising=False)
    monkeypatch.setenv("ORA_PRIVATE_OWNER_APPROVALS", "critical_only")
    d1 = decide_tool_policy(
        profile="private",
        role="owner",
        tool_name="web_download",
        risk_score=60,
        risk_level="HIGH",
    )
    assert d1.requires_approval is False

    d2 = decide_tool_policy(
        profile="private",
        role="owner",
        tool_name="system_control",
        risk_score=95,
        risk_level="CRITICAL",
    )
    assert d2.requires_approval is True
    assert d2.requires_code is True
