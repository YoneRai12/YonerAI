from __future__ import annotations

import sys
from pathlib import Path


def _load_public_capabilities_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import public_capabilities

    return public_capabilities


def test_unknown_public_capability_is_denied_by_default() -> None:
    capabilities = _load_public_capabilities_module()

    assert capabilities.get_public_capability("unknown.future_capability") is None
    assert capabilities.is_public_capability_enabled("unknown.future_capability") is False
    assert capabilities.build_public_capability_manifest()["default_action"] == "deny"


def test_private_and_control_plane_capabilities_are_not_enabled_public_capabilities() -> None:
    capabilities = _load_public_capabilities_module()

    for key in (
        "private_runtime.inventory",
        "control_plane.official_cloud_runtime",
        "discord.gateway_complete",
        "web.final_ui",
    ):
        capability = capabilities.get_public_capability(key)
        assert capability is not None
        assert capability.execution == "disabled"
        assert capability.public_safe is False
        assert capabilities.is_public_capability_enabled(key) is False


def test_tools_mcp_is_contract_only_or_disabled_by_default() -> None:
    capabilities = _load_public_capabilities_module()

    safe_subset = capabilities.get_public_capability("tools.mcp.safe_subset")
    dynamic_execution = capabilities.get_public_capability("tools.mcp.dynamic_execution")
    shell = capabilities.get_public_capability("tools.shell")

    assert safe_subset is not None
    assert safe_subset.execution == "contract_only"
    assert safe_subset.executable_now is False
    assert capabilities.is_public_capability_enabled("tools.mcp.safe_subset") is False

    assert dynamic_execution is not None
    assert dynamic_execution.execution == "disabled"
    assert capabilities.is_public_capability_enabled("tools.mcp.dynamic_execution") is False

    assert shell is not None
    assert shell.execution == "disabled"
    assert capabilities.is_public_capability_enabled("tools.shell") is False


def test_memory_and_self_evolution_capabilities_remain_policy_gated() -> None:
    capabilities = _load_public_capabilities_module()

    proposal = capabilities.get_public_capability("self_evolution.proposal_only")
    memory_quarantine = capabilities.get_public_capability("memory.candidate_quarantine")
    persistent_memory = capabilities.get_public_capability("memory.persistent")

    assert proposal is not None
    assert proposal.execution == "proposal_only"
    assert proposal.memory_persisted is False
    assert proposal.requires_approval is True
    assert capabilities.is_public_capability_enabled("self_evolution.proposal_only") is True

    assert memory_quarantine is not None
    assert memory_quarantine.execution == "quarantine_only"
    assert memory_quarantine.memory_persisted is False
    assert memory_quarantine.requires_approval is True
    assert capabilities.is_public_capability_enabled("memory.candidate_quarantine") is True

    assert persistent_memory is not None
    assert persistent_memory.execution == "disabled"
    assert persistent_memory.memory_persisted is False
    assert capabilities.is_public_capability_enabled("memory.persistent") is False


def test_public_api_cli_web_local_llm_surfaces_are_explicitly_listed() -> None:
    capabilities = _load_public_capabilities_module()
    manifest = capabilities.build_public_capability_manifest()
    listed = manifest["capabilities"]

    for key in (
        "api.health",
        "api.public_messages.mock_offline",
        "api.agent_run.mock_offline",
        "cli.health",
        "cli.message_mock",
        "cli.run_mock",
        "web.temporary_chat_smoke",
        "web.safe_error_display",
        "local_llm.loopback_ollama",
        "local_llm.loopback_openai_compatible",
    ):
        capability = capabilities.get_public_capability(key)
        assert capability is not None
        assert capability.execution == "available"
        assert capability.memory_persisted is False
        assert capabilities.is_public_capability_enabled(key) is True
        assert listed[key]["executable_now"] is True

    japanese_cli = capabilities.get_public_capability("native_japanese_cli.contract")
    assert japanese_cli is not None
    assert japanese_cli.execution == "contract_only"
    assert capabilities.is_public_capability_enabled("native_japanese_cli.contract") is False
