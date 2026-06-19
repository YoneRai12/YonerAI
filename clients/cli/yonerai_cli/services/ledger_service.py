from __future__ import annotations

from typing import Any, Mapping


def build_ledger_status(ledger_path: str | None, *, env: Mapping[str, str]) -> dict[str, object]:
    configured = bool((ledger_path or env.get("YONERAI_RUN_LEDGER_PATH") or "").strip())
    return {
        "enabled": configured,
        "file_backed": configured,
        "local_only": True,
        "path_persisted_in_output": False,
        "raw_prompt_persisted": False,
        "raw_completion_persisted": False,
    }


def start_cli_boundary_run(
    ledger: Any,
    *,
    task_text: str,
    category: str,
    route: str,
    provider_id: str,
    provider_available: bool,
    disabled_reason: str | None = None,
):
    return ledger.create_run(
        task_text=task_text,
        classification={"category": category, "risk": "safe_public", "source": "yonerai_cli"},
        route_decision={"route": route, "mode": "public_cli", "network_required": False},
        provider_decision={
            "provider_id": provider_id,
            "provider_available": provider_available,
            "live_call_performed": False,
        },
        approval_required=False,
        disabled_reason=disabled_reason,
    )
