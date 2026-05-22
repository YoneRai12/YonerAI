from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BoundaryDecision:
    name: str
    available: bool
    execution_performed: bool
    status: str
    reason: str | None = None
    fixture: tuple[dict[str, str], ...] = ()

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["fixture"] = [dict(item) for item in self.fixture]
        return payload


class SearchBoundaryAdapter:
    def __init__(self, *, mock_enabled: bool = False) -> None:
        self.mock_enabled = mock_enabled

    def status(self, classification: Any) -> BoundaryDecision:
        if self.mock_enabled:
            return BoundaryDecision(
                name="web_search",
                available=True,
                execution_performed=False,
                status="mock",
                reason="mock_search_fixture_only",
                fixture=({"title": "YonerAI public fixture", "source": "mock"},),
            )
        reason = "web_search_unavailable_by_default" if "web_research" in classification.required_capabilities else "not_requested"
        return BoundaryDecision(
            name="web_search",
            available=False,
            execution_performed=False,
            status="disabled",
            reason=reason,
        )


class ToolBoundaryAdapter:
    def status_for(self, tool_name: str | None) -> BoundaryDecision:
        name = str(tool_name or "").strip().lower()
        if not name:
            return BoundaryDecision(
                name="tool_boundary",
                available=False,
                execution_performed=False,
                status="disabled",
                reason="no_tool_requested",
            )
        if name in {"web_search", "search"}:
            return BoundaryDecision(
                name="tool_boundary",
                available=False,
                execution_performed=False,
                status="disabled",
                reason="tool_live_execution_disabled",
            )
        try:
            from src.cogs.mcp_policy import is_mcp_tool_denied, load_mcp_deny_patterns

            denied = is_mcp_tool_denied(name, load_mcp_deny_patterns())
        except Exception:
            denied = True
        return BoundaryDecision(
            name="tool_boundary",
            available=False,
            execution_performed=False,
            status="denied",
            reason="tool_denied_by_default" if denied else "unknown_tool_denied_by_default",
        )


def build_boundary_checks_for_task(
    classification: Any,
    *,
    requested_tool: str | None = None,
    mock_search: bool = False,
) -> dict[str, dict[str, object]]:
    search = SearchBoundaryAdapter(mock_enabled=mock_search).status(classification)
    tool = ToolBoundaryAdapter().status_for(requested_tool)
    return {
        "web_search": search.to_public_dict(),
        "tool_boundary": tool.to_public_dict(),
    }
