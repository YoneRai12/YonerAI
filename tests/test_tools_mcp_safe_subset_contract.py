from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "tools-mcp-safe-subset-0.1.md"


def _load_public_capabilities_module():
    core_src = ROOT / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import public_capabilities

    return public_capabilities


def test_tools_mcp_contract_keeps_runtime_execution_disabled_by_default() -> None:
    text = CONTRACT.read_text(encoding="utf-8")

    required_phrases = [
        "disabled by default",
        "Unknown tools, undeclared tools, and dynamically discovered MCP tools are denied",
        "shell execution by default",
        "file system writes by default",
        "deploy actions",
        "secret access",
        "private runtime inventory",
        "live route map exposure",
        "raw chain-of-thought exposure",
        "automatic code mutation",
        "automatic PR creation",
        "automatic merge",
        "automatic deploy",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_tools_mcp_contract_defines_approval_audit_and_japanese_cli_boundaries() -> None:
    text = CONTRACT.read_text(encoding="utf-8")

    for phrase in (
        "Approval must bind",
        "audit event",
        "tool_capability_decision",
        "Native Japanese CLI commands can be ambiguous",
        "dry-run and confirmation",
        "Self-evolution remains proposal-only",
    ):
        assert phrase in text


def test_tools_mcp_public_capability_manifest_remains_contract_only() -> None:
    capabilities = _load_public_capabilities_module()

    safe_subset = capabilities.get_public_capability("tools.mcp.safe_subset")
    dynamic_execution = capabilities.get_public_capability("tools.mcp.dynamic_execution")

    assert safe_subset is not None
    assert safe_subset.execution == "contract_only"
    assert safe_subset.executable_now is False
    assert capabilities.is_public_capability_enabled("tools.mcp.safe_subset") is False

    assert dynamic_execution is not None
    assert dynamic_execution.execution == "disabled"
    assert dynamic_execution.executable_now is False
    assert capabilities.is_public_capability_enabled("tools.mcp.dynamic_execution") is False
