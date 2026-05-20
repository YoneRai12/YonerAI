from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


PUBLIC_CAPABILITY_BOUNDARY_VERSION = "public-capability-boundary-0.1"

CapabilityExecution = Literal["available", "proposal_only", "quarantine_only", "contract_only", "docs_only", "disabled"]
CapabilitySurface = Literal[
    "api",
    "cli",
    "native_japanese_cli",
    "web",
    "growth_sns",
    "hybrid",
    "self_evolution",
    "local_llm",
    "memory",
    "tools_mcp",
    "private_runtime",
    "control_plane",
    "discord",
]


@dataclass(frozen=True)
class PublicCapability:
    key: str
    surface: CapabilitySurface
    execution: CapabilityExecution
    public_safe: bool
    user_visible: bool
    memory_persisted: bool
    requires_approval: bool
    summary: str

    @property
    def executable_now(self) -> bool:
        return self.execution in {"available", "proposal_only", "quarantine_only"}

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["executable_now"] = self.executable_now
        return payload


PUBLIC_CAPABILITIES: dict[str, PublicCapability] = {
    "api.health": PublicCapability(
        key="api.health",
        surface="api",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Core API health smoke endpoint.",
    ),
    "api.public_messages.mock_offline": PublicCapability(
        key="api.public_messages.mock_offline",
        surface="api",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Credential-free deterministic mock/offline public message path.",
    ),
    "api.agent_run.mock_offline": PublicCapability(
        key="api.agent_run.mock_offline",
        surface="api",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Public-safe Surface API run smoke contract.",
    ),
    "local_llm.loopback_ollama": PublicCapability(
        key="local_llm.loopback_ollama",
        surface="local_llm",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Loopback-only Ollama local provider path.",
    ),
    "local_llm.loopback_openai_compatible": PublicCapability(
        key="local_llm.loopback_openai_compatible",
        surface="local_llm",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Loopback-only OpenAI-compatible local provider path.",
    ),
    "cli.health": PublicCapability(
        key="cli.health",
        surface="cli",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Local CLI health command against loopback Core API.",
    ),
    "cli.message_mock": PublicCapability(
        key="cli.message_mock",
        surface="cli",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Local CLI mock/offline message smoke command.",
    ),
    "cli.run_mock": PublicCapability(
        key="cli.run_mock",
        surface="cli",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Local CLI mock/offline Surface API run smoke command.",
    ),
    "native_japanese_cli.contract": PublicCapability(
        key="native_japanese_cli.contract",
        surface="native_japanese_cli",
        execution="contract_only",
        public_safe=True,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Native Japanese CLI ambiguity and confirmation UX contract only.",
    ),
    "web.temporary_chat_smoke": PublicCapability(
        key="web.temporary_chat_smoke",
        surface="web",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Temporary Web Chat MVP smoke surface, not final UI.",
    ),
    "web.safe_error_display": PublicCapability(
        key="web.safe_error_display",
        surface="web",
        execution="available",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Public-safe error display without stack traces or private details.",
    ),
    "growth_sns.claim_guardrails": PublicCapability(
        key="growth_sns.claim_guardrails",
        surface="growth_sns",
        execution="docs_only",
        public_safe=True,
        user_visible=True,
        memory_persisted=False,
        requires_approval=False,
        summary="Claim-guarded demo and public narrative documentation.",
    ),
    "hybrid.connector_fixture": PublicCapability(
        key="hybrid.connector_fixture",
        surface="hybrid",
        execution="quarantine_only",
        public_safe=True,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Synthetic signed-envelope fixture with donation quarantine.",
    ),
    "self_evolution.proposal_only": PublicCapability(
        key="self_evolution.proposal_only",
        surface="self_evolution",
        execution="proposal_only",
        public_safe=True,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Public-safe self-evolution proposal-only path; no automatic mutation.",
    ),
    "memory.candidate_quarantine": PublicCapability(
        key="memory.candidate_quarantine",
        surface="memory",
        execution="quarantine_only",
        public_safe=True,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Memory candidate quarantine policy; no persistence by default.",
    ),
    "memory.persistent": PublicCapability(
        key="memory.persistent",
        surface="memory",
        execution="disabled",
        public_safe=False,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Persistent memory is not implemented in the public MVP.",
    ),
    "tools.mcp.safe_subset": PublicCapability(
        key="tools.mcp.safe_subset",
        surface="tools_mcp",
        execution="contract_only",
        public_safe=True,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Tools/MCP safe subset is contract-only until explicit allowlist tests land.",
    ),
    "tools.mcp.dynamic_execution": PublicCapability(
        key="tools.mcp.dynamic_execution",
        surface="tools_mcp",
        execution="disabled",
        public_safe=False,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Dynamic MCP execution is disabled by default in public-safe paths.",
    ),
    "tools.shell": PublicCapability(
        key="tools.shell",
        surface="tools_mcp",
        execution="disabled",
        public_safe=False,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Shell execution is not part of the public MVP.",
    ),
    "private_runtime.inventory": PublicCapability(
        key="private_runtime.inventory",
        surface="private_runtime",
        execution="disabled",
        public_safe=False,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Private runtime inventory must not be exposed in the public repo.",
    ),
    "control_plane.official_cloud_runtime": PublicCapability(
        key="control_plane.official_cloud_runtime",
        surface="control_plane",
        execution="disabled",
        public_safe=False,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Official cloud runtime is outside the public MVP.",
    ),
    "discord.gateway_complete": PublicCapability(
        key="discord.gateway_complete",
        surface="discord",
        execution="disabled",
        public_safe=False,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Discord gateway completion remains private/runtime lane work.",
    ),
    "web.final_ui": PublicCapability(
        key="web.final_ui",
        surface="web",
        execution="disabled",
        public_safe=False,
        user_visible=False,
        memory_persisted=False,
        requires_approval=True,
        summary="Final Web UI is not implemented.",
    ),
}


def get_public_capability(key: str) -> PublicCapability | None:
    return PUBLIC_CAPABILITIES.get(key)


def is_public_capability_enabled(key: str) -> bool:
    capability = get_public_capability(key)
    return bool(capability and capability.public_safe and capability.executable_now)


def build_public_capability_manifest() -> dict[str, object]:
    return {
        "schema_version": PUBLIC_CAPABILITY_BOUNDARY_VERSION,
        "default_action": "deny",
        "capabilities": {key: capability.to_public_dict() for key, capability in sorted(PUBLIC_CAPABILITIES.items())},
    }
