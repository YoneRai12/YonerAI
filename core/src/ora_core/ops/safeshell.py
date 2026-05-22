from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OperationPlan:
    operation_id: str
    status: str
    command_preview: tuple[str, ...]
    execution_performed: bool
    approval_required: bool
    reason: str
    mcp_policy: dict[str, object]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["command_preview"] = list(self.command_preview)
        return payload


class SafeShellPlanner:
    _DIAGNOSTICS = {
        "python-version": ("python", "--version"),
        "git-status": ("git", "status", "--short"),
        "node-version": ("node", "--version"),
    }

    def plan(self, operation: str) -> OperationPlan:
        normalized = _normalize_operation(operation)
        if normalized in self._DIAGNOSTICS:
            return OperationPlan(
                operation_id=normalized,
                status="planned",
                command_preview=self._DIAGNOSTICS[normalized],
                execution_performed=False,
                approval_required=False,
                reason="diagnostic_allowlist_plan_only",
                mcp_policy=_mcp_policy_summary(normalized),
            )
        return OperationPlan(
            operation_id=normalized or "unknown",
            status="denied",
            command_preview=(),
            execution_performed=False,
            approval_required=True,
            reason="arbitrary_shell_disabled",
            mcp_policy=_mcp_policy_summary(normalized),
        )


def plan_operation(operation: str) -> OperationPlan:
    return SafeShellPlanner().plan(operation)


def _normalize_operation(operation: str) -> str:
    return " ".join(str(operation or "").strip().lower().replace("_", "-").split())


def _mcp_policy_summary(operation: str) -> dict[str, object]:
    try:
        from src.cogs.mcp_policy import is_mcp_tool_denied, load_mcp_deny_patterns

        patterns = load_mcp_deny_patterns()
        denied = is_mcp_tool_denied(operation, patterns)
    except Exception:
        patterns = ["delete", "deploy", "shell", "run"]
        denied = True
    return {
        "source": "src/cogs/mcp_policy.py",
        "default_deny_patterns": list(patterns),
        "denied": denied,
        "execution_performed": False,
    }
