from __future__ import annotations

from typing import Mapping

from ora_core.execution import build_run_ledger_from_env, execute_task
from ora_core.execution.ledger import RunLedger
from ora_core.route_preview import preview_route

from .oracle_stub import DEFAULT_ORACLE_STUB_TASK, build_oracle_stub_queue_report
from .relay_node_e2e import build_local_dev_relay_node_e2e_report
from .wire_contract import assert_public_safe_wire_payload


HYBRID_EXECUTION_SLICE_SCHEMA_VERSION = "yonerai-hybrid-execution-slice/v0.1"
DEFAULT_HYBRID_EXECUTION_TASK = "summarize public docs through local-dev hybrid node"
DEFAULT_HYBRID_EXECUTION_ORACLE_TASK = DEFAULT_ORACLE_STUB_TASK


def build_hybrid_execution_slice_status_report() -> dict[str, object]:
    return {
        "schema_version": HYBRID_EXECUTION_SLICE_SCHEMA_VERSION,
        "ok": True,
        "operation": "status",
        "status": "local_dev_hybrid_execution_slice_available",
        "command": "yonerai hybrid run --json",
        "local_dev_only": True,
        "in_process_relay_transport": True,
        "loopback_only": True,
        "provider_execution_supported": ["mock", "local"],
        "oracle_stub_supported": True,
        "ledger_supported": True,
        "network_required": False,
        "production_oracle_used": False,
        "official_cloud_runtime_implemented": False,
        "production_trust_material": False,
        "actions_not_performed": _hybrid_non_actions(),
    }


def build_hybrid_execution_slice_report(
    task_text: str = DEFAULT_HYBRID_EXECUTION_TASK,
    *,
    provider: str = "mock",
    live: bool = False,
    ledger: RunLedger | None = None,
    env: Mapping[str, str] | None = None,
    oracle_task_text: str = DEFAULT_HYBRID_EXECUTION_ORACLE_TASK,
) -> dict[str, object]:
    task = _normalize_task(task_text) or DEFAULT_HYBRID_EXECUTION_TASK
    ledger = ledger or build_run_ledger_from_env()

    route_matrix = _build_route_matrix()
    selected_route = _selected_route(task)
    local_node_runtime = build_local_dev_relay_node_e2e_report(env or {}, requested_capability="mock_search")
    relay_proxy = local_node_runtime.get("http_proxy_fixture")
    local_node_public_safety_violations = assert_public_safe_wire_payload(local_node_runtime)
    provider_result = execute_task(
        task,
        mode="self-host",
        provider=provider,
        live=live,
        ledger=ledger,
        context_events=_hybrid_context_events(selected_route, local_node_runtime),
        client_type="cli",
    ).to_public_dict()
    oracle_stub = build_oracle_stub_queue_report(
        _oracle_candidate_task(selected_route, oracle_task_text),
        ledger=ledger,
    )

    ok = (
        bool(local_node_runtime.get("ok"))
        and not local_node_public_safety_violations
        and bool(provider_result.get("ok"))
        and bool(oracle_stub.get("ok"))
        and _route_matrix_ok(route_matrix)
    )
    return {
        "schema_version": HYBRID_EXECUTION_SLICE_SCHEMA_VERSION,
        "ok": ok,
        "operation": "run",
        "command": "yonerai hybrid run",
        "task_summary": "public-safe local-dev hybrid execution slice",
        "selected_route": selected_route,
        "route_matrix": route_matrix,
        "local_node_runtime": {
            "schema_version": local_node_runtime.get("schema_version"),
            "ok": local_node_runtime.get("ok"),
            "mode": local_node_runtime.get("mode"),
            "relay": local_node_runtime.get("relay"),
            "transport": local_node_runtime.get("transport"),
            "node_flow": local_node_runtime.get("node_flow"),
            "pairing": local_node_runtime.get("pairing"),
            "http_proxy_fixture": relay_proxy,
            "public_safety_violations": list(local_node_public_safety_violations),
        },
        "provider_execution": provider_result,
        "oracle_stub_execution": oracle_stub,
        "run_ids": {
            "provider_run_id": _nested(provider_result, "run", "run_id"),
            "oracle_run_id": _nested(oracle_stub, "request", "run_id"),
        },
        "boundaries": {
            "local_dev_only": True,
            "loopback_only": True,
            "in_process_relay_transport": True,
            "message_body_persisted": False,
            "raw_prompt_sent_to_oracle_stub": False,
            "private_file_content_sent_to_oracle_stub": False,
            "provider_key_sent_to_oracle_stub": False,
            "live_external_provider_default": False,
            "production_oracle_used": False,
            "official_cloud_runtime_implemented": False,
            "official_managed_cloud_public_repo_status": "external_contract_only",
            "live_discord_used": False,
            "deploy_performed": False,
        },
        "actions_not_performed": _hybrid_non_actions(),
    }


def _build_route_matrix() -> list[dict[str, object]]:
    cases = (
        {
            "name": "local_first_public_docs",
            "task": "summarize public docs",
            "mode": "full_private_self_host",
        },
        {
            "name": "hybrid_private_file_local_node",
            "task": "read selected workspace file",
            "mode": "official_hybrid_private",
            "requested_capability": "private_files",
            "has_local_node": True,
            "local_node_verification_state": "present_verified",
            "local_node_capabilities": ("private_files",),
            "require_enrolled_verified_session": True,
            "session_verification_state": "enrolled_verified",
        },
        {
            "name": "cloud_contract_public_reasoning",
            "task": DEFAULT_ORACLE_STUB_TASK,
            "mode": "official_hybrid_private",
        },
        {
            "name": "deny_dangerous_operation",
            "task": "delete file and run shell command",
            "mode": "official_hybrid_private",
            "requested_capability": "dangerous_operations",
            "has_local_node": True,
            "local_node_verification_state": "present_verified",
            "local_node_capabilities": ("local_tools",),
            "require_enrolled_verified_session": True,
            "session_verification_state": "enrolled_verified",
            "risk_hint": "dangerous",
        },
    )
    matrix: list[dict[str, object]] = []
    for case in cases:
        decision = preview_route(
            str(case["task"]),
            mode=str(case["mode"]),
            requested_capability=_optional_str(case.get("requested_capability")),
            has_local_node=bool(case.get("has_local_node", False)),
            local_node_verification_state=_optional_str(case.get("local_node_verification_state")),
            local_node_capabilities=case.get("local_node_capabilities"),  # type: ignore[arg-type]
            require_enrolled_verified_session=bool(case.get("require_enrolled_verified_session", False)),
            session_verification_state=_optional_str(case.get("session_verification_state")),
            risk_hint=_optional_str(case.get("risk_hint")),
        ).to_public_dict()
        matrix.append(
            {
                "name": case["name"],
                "task_class": decision.get("task_class"),
                "privacy_class": decision.get("privacy_class"),
                "route": decision.get("route"),
                "route_strategy": decision.get("route_strategy"),
                "node_posture_state": decision.get("node_posture_state"),
                "capability_gate": decision.get("capability_gate"),
                "approval_state": decision.get("approval_state"),
                "oracle_stub_eligible": decision.get("oracle_stub_eligible"),
                "private_file_content_sent_to_cloud": decision.get("private_file_content_sent_to_cloud"),
                "raw_prompt_body_sent_to_cloud": decision.get("raw_prompt_body_sent_to_cloud"),
                "provider_key_sent_to_cloud": decision.get("provider_key_sent_to_cloud"),
            }
        )
    return matrix


def _selected_route(task: str) -> dict[str, object]:
    return preview_route(
        task,
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("local_tools",),
        require_enrolled_verified_session=True,
        session_verification_state="enrolled_verified",
    ).to_public_dict()


def _hybrid_context_events(
    selected_route: dict[str, object],
    local_node_runtime: dict[str, object],
) -> tuple[dict[str, object], ...]:
    proxy = local_node_runtime.get("http_proxy_fixture")
    proxy_status = "unavailable"
    proxy_capability = "unknown"
    proxy_hash_only = False
    if isinstance(proxy, dict):
        proxy_status = str(proxy.get("status") or "unknown")
        proxy_capability = str(proxy.get("capability") or "unknown")
        proxy_hash_only = bool(proxy.get("session_token_hash_only"))
    return (
        {
            "name": "hybrid_route_decision",
            "status": "ok",
            "summary": (
                f"route_strategy={selected_route.get('route_strategy')} "
                f"privacy_class={selected_route.get('privacy_class')} "
                f"node_posture={selected_route.get('node_posture_state') or 'none'}"
            ),
        },
        {
            "name": "hybrid_local_node_proxy",
            "status": "ok" if proxy_status == "completed" else "blocked",
            "summary": (
                f"relay_status={proxy_status} capability={proxy_capability} "
                f"hash_only_session={str(proxy_hash_only).lower()}"
            ),
        },
    )


def _oracle_candidate_task(selected_route: dict[str, object], oracle_task_text: str) -> str:
    if selected_route.get("route_strategy") == "cloud_contract_candidate":
        return DEFAULT_ORACLE_STUB_TASK
    return _normalize_task(oracle_task_text) or DEFAULT_ORACLE_STUB_TASK


def _route_matrix_ok(route_matrix: list[dict[str, object]]) -> bool:
    by_name = {str(item.get("name")): item for item in route_matrix}
    return (
        by_name.get("local_first_public_docs", {}).get("route_strategy") == "local_preferred"
        and by_name.get("hybrid_private_file_local_node", {}).get("route_strategy") == "hybrid"
        and by_name.get("cloud_contract_public_reasoning", {}).get("route_strategy") == "cloud_contract_candidate"
        and by_name.get("deny_dangerous_operation", {}).get("route_strategy") == "deny"
        and by_name.get("hybrid_private_file_local_node", {}).get("private_file_content_sent_to_cloud") is False
        and by_name.get("cloud_contract_public_reasoning", {}).get("oracle_stub_eligible") is True
    )


def _hybrid_non_actions() -> list[str]:
    return [
        "no production Oracle",
        "no official cloud runtime",
        "no production signing key",
        "no production trust store",
        "no live Discord",
        "no deploy",
        "no public tunnel",
        "no arbitrary shell",
        "no arbitrary file access",
        "no provider key output",
        "no external provider call by default",
        "no private file content sent to oracle stub",
        "no raw prompt body sent to oracle stub",
        "no message body persistence in relay",
    ]


def _normalize_task(task_text: str) -> str:
    return " ".join(str(task_text or "").split())


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _nested(payload: Mapping[str, object], first: str, second: str) -> object:
    child = payload.get(first)
    if not isinstance(child, Mapping):
        return None
    return child.get(second)
