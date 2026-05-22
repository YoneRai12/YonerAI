from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from ora_core.providers import ProviderRequest, build_default_provider_registry
from ora_core.providers.registry import ProviderRegistry
from ora_core.route_preview import preview_route

from .provider_selection import ProviderSelection, select_provider_for_task
from .task_classifier import TaskClassification, classify_task


EXECUTION_PLAN_SCHEMA_VERSION = "yonerai-execution-plan/v1"
PlanMode = Literal["official_managed_cloud", "official_hybrid_private", "full_private_self_host"]
EstimatedExecutionSurface = Literal["cloud_contract", "local_node", "self_host", "external_provider", "disabled"]


@dataclass(frozen=True)
class PlanStep:
    name: str
    status: str
    execution: bool
    detail: str

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalGate:
    reason: str
    required: bool
    execution_blocked: bool

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPlan:
    ok: bool
    command: str
    task: str
    dry_run: bool
    execution_performed: bool
    classification: TaskClassification
    provider_selection: ProviderSelection
    route_decision: dict[str, object]
    estimated_execution_surface: EstimatedExecutionSurface
    steps: tuple[PlanStep, ...]
    approval_gates: tuple[ApprovalGate, ...]
    disabled_reasons: tuple[str, ...]
    safety_checks: dict[str, dict[str, object]]
    provider_registry: tuple[dict[str, object], ...]

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": EXECUTION_PLAN_SCHEMA_VERSION,
            "ok": self.ok,
            "command": self.command,
            "task": self.task,
            "dry_run": self.dry_run,
            "execution_performed": self.execution_performed,
            "classification": self.classification.to_public_dict(),
            "risk": self.classification.risk,
            "required_capabilities": list(self.classification.required_capabilities),
            "route": self.route_decision,
            "provider": self.provider_selection.to_public_dict(),
            "model": {
                "tier": self.provider_selection.model_tier,
                "model_id": self.provider_selection.model_id,
            },
            "approval": {
                "required": any(gate.required for gate in self.approval_gates),
                "gates": [gate.to_public_dict() for gate in self.approval_gates],
            },
            "disabled_reasons": list(self.disabled_reasons),
            "estimated_execution_surface": self.estimated_execution_surface,
            "steps": [step.to_public_dict() for step in self.steps],
            "safety_checks": self.safety_checks,
            "boundary_adapters": {
                key: value
                for key, value in self.safety_checks.items()
                if key in {"web_search", "tool_boundary"}
            },
            "provider_registry": list(self.provider_registry),
            "large_codebase_connections": [
                {
                    "name": "mcp_deny_policy",
                    "source": "src/cogs/mcp_policy.py",
                    "execution": False,
                    "status": self.safety_checks["mcp_deny_policy"]["status"],
                },
                {
                    "name": "managed_download_guard",
                    "source": "core/src/ora_core/brain/process.py",
                    "execution": False,
                    "status": self.safety_checks["managed_download_guard"]["status"],
                },
            ],
            "side_effects": {
                "provider_call": False,
                "network_call": False,
                "shell": False,
                "file_access": False,
                "discord": False,
                "memory_persisted": False,
                "deploy": False,
            },
            "boundaries": {
                "official_cloud_runtime_in_public_repo": False,
                "official_managed_cloud": "contract_only_external",
                "live_discord_required": False,
                "persistent_memory_required": False,
                "google_login_required": False,
                "production_db_required": False,
            },
            "non_claims": [
                "preview_only_no_execution",
                "no_provider_call",
                "no_shell_or_file_access",
                "no_live_discord",
                "no_memory_persistence",
                "no_deploy",
                "not_production_ready",
            ],
        }


def build_execution_plan(
    task_text: str,
    *,
    command: str = "yonerai plan",
    mode: str = "managed-contract",
    provider: str = "auto",
    dry_run: bool = True,
    registry: ProviderRegistry | None = None,
) -> ExecutionPlan:
    raw_task = " ".join(str(task_text or "").split())
    if not raw_task:
        task = ""
    else:
        task = _safe_task_text(raw_task)
    normalized_mode = normalize_plan_mode(mode)
    registry = registry or build_default_provider_registry()
    classification = classify_task(raw_task)
    requested_capability = _route_capability(classification)
    route = preview_route(
        raw_task,
        mode=normalized_mode,
        requested_capability=requested_capability,
        has_local_node=False,
        risk_hint=_route_risk_hint(classification),
    ).to_public_dict()
    provider_selection = select_provider_for_task(
        classification,
        mode=normalized_mode,
        provider_preference=provider,
        registry=registry,
    )
    from ora_core.execution.boundaries import build_boundary_checks_for_task

    safety_checks = {
        "mcp_deny_policy": _mcp_deny_policy_check(classification),
        "managed_download_guard": _managed_download_guard_check(task),
        **build_boundary_checks_for_task(classification),
    }
    disabled_reasons = _disabled_reasons(route, provider_selection, safety_checks)
    approval_gates = _approval_gates(route, provider_selection, safety_checks)
    steps = (
        PlanStep("classify_task", "ok", False, classification.category),
        PlanStep("select_provider_model", "ok", False, f"{provider_selection.provider_id}/{provider_selection.model_tier}"),
        PlanStep("preview_route", "ok", False, str(route.get("route"))),
        PlanStep("safety_policy_checks", "ok", False, "mcp_deny_policy, managed_download_guard, search/tool boundary"),
    )
    return ExecutionPlan(
        ok=classification.risk != "unsupported",
        command=command,
        task=task,
        dry_run=dry_run,
        execution_performed=False,
        classification=classification,
        provider_selection=provider_selection,
        route_decision=route,
        estimated_execution_surface=_surface_for_route(route),
        steps=steps,
        approval_gates=tuple(approval_gates),
        disabled_reasons=tuple(dict.fromkeys(disabled_reasons)),
        safety_checks=safety_checks,
        provider_registry=tuple(registry.list_statuses()),
    )


def normalize_plan_mode(mode: str | None) -> PlanMode:
    text = str(mode or "managed-contract").strip().lower().replace("_", "-")
    aliases = {
        "managed": "official_managed_cloud",
        "managed-contract": "official_managed_cloud",
        "official-managed-cloud": "official_managed_cloud",
        "official_managed_cloud": "official_managed_cloud",
        "hybrid": "official_hybrid_private",
        "official-hybrid-private": "official_hybrid_private",
        "official_hybrid_private": "official_hybrid_private",
        "self-host": "full_private_self_host",
        "selfhost": "full_private_self_host",
        "full-private-self-host": "full_private_self_host",
        "full_private_self_host": "full_private_self_host",
    }
    normalized = aliases.get(text)
    if normalized is None:
        raise ValueError("unsupported plan mode")
    return normalized  # type: ignore[return-value]


def _route_capability(classification: TaskClassification) -> str:
    if classification.category in {"simple_chat", "summarize_public"}:
        return "public_docs"
    if classification.category == "local_private_file":
        return "private_files"
    if classification.category == "pc_operation":
        return "pc_operations"
    if classification.category == "dangerous_operation":
        return "dangerous_operations"
    if classification.category == "long_running":
        return "heavy_work"
    if classification.category == "unsupported":
        return "unknown"
    return "cloud_orchestration"


def _route_risk_hint(classification: TaskClassification) -> str | None:
    if classification.category == "dangerous_operation":
        return "dangerous"
    if classification.category == "pc_operation":
        return "pc operation"
    if classification.category == "local_private_file":
        return "private data"
    return None


def _surface_for_route(route: dict[str, object]) -> EstimatedExecutionSurface:
    route_name = str(route.get("route") or "")
    if route_name == "managed_cloud_contract_only":
        return "cloud_contract"
    if route_name in {"local_node_required", "enrolled_verified_node_required", "hybrid_coordination_preview"}:
        return "local_node"
    if route_name == "self_host_local_preview":
        return "self_host"
    if route_name == "external_official_service_required":
        return "external_provider"
    return "disabled"


def _mcp_deny_policy_check(classification: TaskClassification) -> dict[str, object]:
    try:
        from src.cogs.mcp_policy import is_mcp_tool_denied
    except Exception:
        return {
            "ok": False,
            "status": "fail",
            "runtime_execution": False,
            "dynamic_mcp_tools_allowed": False,
            "reason": "mcp_deny_policy_unavailable",
        }
    patterns = ["delete", "deploy", "shell", "run"]
    denied = all(is_mcp_tool_denied(name, patterns) for name in ("delete_file", "deploy_release", "run_shell"))
    safe_allowed = not is_mcp_tool_denied("generate_artwork", patterns)
    relevant = classification.category in {"pc_operation", "dangerous_operation"}
    return {
        "ok": denied and safe_allowed,
        "status": "ok" if denied and safe_allowed else "fail",
        "runtime_execution": False,
        "dynamic_mcp_tools_allowed": False,
        "dangerous_names_denied": denied,
        "safe_name_allowed": safe_allowed,
        "relevant_to_task": relevant,
        "approval_reason": "mcp_tool_denied_by_default" if relevant and denied else None,
    }


def _managed_download_guard_check(task: str) -> dict[str, object]:
    urls = re.findall(r"https?://[^\s\"'<>]+", task)
    relevant = "download" in task.lower() or bool(urls)
    try:
        from ora_core.brain.process import MainProcess
    except Exception:
        return {
            "ok": False,
            "status": "fail",
            "network_performed": False,
            "download_performed": False,
            "relevant_to_task": relevant,
            "reason": "managed_download_guard_unavailable",
        }
    process = object.__new__(MainProcess)
    managed = process._coerce_download_link(url="/v1/files/planner-preview/download", label="planner preview")
    unsafe_url = urls[0] if urls else "https://example.com/not-managed.bin"
    unsafe = process._coerce_download_link(url=unsafe_url, label="external download")
    return {
        "ok": managed is not None and unsafe is None,
        "status": "ok" if managed is not None and unsafe is None else "fail",
        "network_performed": False,
        "download_performed": False,
        "managed_url_accepted": managed is not None,
        "unsafe_url_rejected": unsafe is None,
        "relevant_to_task": relevant,
        "approval_reason": "external_download_not_permitted" if relevant and unsafe is None and urls else None,
    }


def _disabled_reasons(
    route: dict[str, object],
    provider_selection: ProviderSelection,
    safety_checks: dict[str, dict[str, object]],
) -> list[str]:
    reasons = list(provider_selection.disabled_reasons)
    route_reason = route.get("unavailable_reason")
    if route_reason:
        reasons.append(str(route_reason))
    if safety_checks["mcp_deny_policy"].get("relevant_to_task"):
        reasons.append("mcp_deny_policy")
    if safety_checks["managed_download_guard"].get("approval_reason"):
        reasons.append("managed_download_guard")
    for key in ("web_search", "tool_boundary"):
        reason = safety_checks.get(key, {}).get("reason")
        if reason and reason not in {"not_requested", "no_tool_requested"}:
            reasons.append(str(reason))
    return reasons


def _approval_gates(
    route: dict[str, object],
    provider_selection: ProviderSelection,
    safety_checks: dict[str, dict[str, object]],
) -> list[ApprovalGate]:
    gates: list[ApprovalGate] = []
    if route.get("approval_required"):
        gates.append(ApprovalGate("route_requires_approval", True, True))
    if provider_selection.approval_required:
        gates.append(ApprovalGate("task_risk_requires_approval", True, True))
    mcp_reason = safety_checks["mcp_deny_policy"].get("approval_reason")
    if mcp_reason:
        gates.append(ApprovalGate(str(mcp_reason), True, True))
    download_reason = safety_checks["managed_download_guard"].get("approval_reason")
    if download_reason:
        gates.append(ApprovalGate(str(download_reason), True, True))
    return gates


def preview_mock_provider_response(prompt: str) -> dict[str, object]:
    registry = build_default_provider_registry()
    adapter = registry.resolve("mock")
    return adapter.generate(ProviderRequest(prompt=prompt)).to_public_dict()


def _safe_task_text(task: str) -> str:
    redacted = re.sub(r"(?:(?<=^)|(?<=[\s\"'(<]))[A-Za-z]:[\\/][^\s\"'<>|]+", "[local_path_redacted]", task)
    redacted = re.sub(r"(?:(?<=^)|(?<=[\s\"'(<]))/(?:home|users|root|etc|var|tmp)/[^\s\"'<>|]+", "[local_path_redacted]", redacted)
    redacted = re.sub(r"sk-[A-Za-z0-9_-]{10,}", "[secret_redacted]", redacted)
    redacted = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "[secret_redacted]", redacted)
    return redacted[:500]
