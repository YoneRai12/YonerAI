from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from ora_core.planning.task_classifier import TaskClassification, classify_task
from ora_core.providers import ProviderError, ProviderRequest, ProviderResponse, build_default_provider_registry
from ora_core.providers.registry import ProviderRegistry, normalize_provider_id
from ora_core.route_preview import preview_route

from .boundaries import build_boundary_checks_for_task
from .ledger import RunLedger, build_run_ledger_from_env, safe_summary
from .legacy_text import normalize_legacy_generated_text


AUTO_RUNTIME_SCHEMA_VERSION = "yonerai-auto-runtime/v0.1"
_PUBLIC_CLOUD_CONTRACT_PREVIEW_TASK = "public reasoning over public documentation"

AutoDifficulty = Literal["instant", "task", "agent"]
AutoPrivacy = Literal["public", "private", "local_file", "dangerous"]
AutoRoute = Literal["instant_local", "local_llm", "hybrid_node", "cloud_contract_candidate", "deny"]

_LIVE_CAPABLE_PROVIDERS = {"local", "openai-compatible", "anthropic", "gemini"}
_EXTERNAL_LIVE_PROVIDERS = {"openai-compatible", "anthropic", "gemini"}


def build_auto_runtime_status_report() -> dict[str, object]:
    return {
        "schema_version": AUTO_RUNTIME_SCHEMA_VERSION,
        "ok": True,
        "status": "available",
        "command": "yonerai ask --auto --json",
        "routes": ["instant_local", "local_llm", "hybrid_node", "cloud_contract_candidate", "deny"],
        "difficulty_classes": ["instant", "task", "agent"],
        "privacy_classes": ["public", "private", "local_file", "dangerous"],
        "mock_provider_default": True,
        "local_llm_loopback_only": True,
        "live_external_provider_default": False,
        "mock_search_supported": True,
        "live_search_default": False,
        "reviewer_plan_supported": True,
        "ledger_supported": True,
        "network_required": False,
        "production_oracle_used": False,
        "official_cloud_runtime_implemented": False,
        "actions_not_performed": [
            "no arbitrary shell execution",
            "no arbitrary file access",
            "no live Discord",
            "no production Oracle",
            "no official cloud runtime",
            "no provider key output",
        ],
    }


@dataclass(frozen=True)
class AutoRuntimeDecision:
    difficulty: AutoDifficulty
    privacy: AutoPrivacy
    route: AutoRoute
    approval_required: bool
    search_needed: bool
    tool_needed: bool
    local_file_context: bool
    provider_id: str
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        return {
            "difficulty": self.difficulty,
            "privacy": self.privacy,
            "route": self.route,
            "route_strategy": self.route,
            "approval_required": self.approval_required,
            "search_needed": self.search_needed,
            "tool_needed": self.tool_needed,
            "local_file_context": self.local_file_context,
            "provider_id": self.provider_id,
            "reasons": list(self.reasons),
            "private_file_content_sent_to_cloud": False,
            "provider_key_sent_to_cloud": False,
            "raw_prompt_body_sent_to_cloud": False,
        }


def build_auto_runtime_report(
    task_text: str,
    *,
    provider_prompt: str | None = None,
    provider: str = "auto",
    live: bool = False,
    ledger: RunLedger | None = None,
    registry: ProviderRegistry | None = None,
    context_events: Sequence[Mapping[str, object]] | None = None,
    local_file_context: bool = False,
    client_type: str = "cli",
) -> dict[str, object]:
    task = _normalize_task(task_text)
    provider_prompt = provider_prompt if provider_prompt is not None else task
    ledger = ledger or build_run_ledger_from_env()
    registry = registry or build_default_provider_registry()
    classification = classify_task(task)
    decision = decide_auto_runtime_route(
        task,
        classification=classification,
        provider=provider,
        live=live,
        local_file_context=local_file_context,
    )
    route_decision = _route_decision(task, decision, classification)
    boundary_checks = build_boundary_checks_for_task(
        classification,
        requested_tool="local_tool" if decision.tool_needed else None,
        mock_search=decision.search_needed,
        client_type=client_type,
    )
    provider_decision = _provider_decision(registry, decision.provider_id, decision, live=live)
    run = ledger.create_run(
        task_text=task,
        classification=_classification_payload(classification, decision),
        route_decision=route_decision,
        provider_decision=provider_decision,
        approval_required=decision.approval_required,
        disabled_reason="approval_required" if decision.approval_required else None,
    )
    ledger.append_event(run.run_id, "auto_runtime_decision", "ok", _decision_summary(decision))

    for event in context_events or ():
        if not isinstance(event, Mapping):
            ledger.append_event(run.run_id, "context_event_ignored", "warn", "invalid context event type")
            continue
        ledger.append_event(
            run.run_id,
            str(event.get("name") or "context"),
            str(event.get("status") or "ok"),
            str(event.get("summary") or ""),
        )

    search_report = _mock_search_report(task, decision)
    if search_report["needed"]:
        ledger.append_event(run.run_id, "mock_search_plan", "ok", str(search_report["summary"]))

    reviewer_plan = _reviewer_plan(task, decision)
    if reviewer_plan["enabled"]:
        ledger.append_event(
            run.run_id,
            "auto_reviewer_plan",
            "ok",
            f"subtasks={reviewer_plan['subtask_count']} reviewer={reviewer_plan['reviewer']['role']}",
        )

    if decision.route == "deny":
        run = ledger.fail_run(run.run_id, error_summary="approval_required", blocked=True)
        return _base_report(
            task=task,
            decision=decision,
            classification=classification,
            route_decision=route_decision,
            boundary_checks=boundary_checks,
            provider_decision=provider_decision,
            run=run.to_public_dict(),
            search_report=search_report,
            reviewer_plan=reviewer_plan,
            ok=False,
            live_call_performed=False,
            error={
                "code": "approval_required",
                "message": "ask --auto denied this task because it needs unsafe or unavailable local/tool approval.",
            },
        )

    if decision.route == "cloud_contract_candidate":
        oracle_report = _execute_oracle_stub(task, classification, route_decision, ledger=ledger, run_id=run.run_id)
        response = oracle_report["response"] if isinstance(oracle_report.get("response"), dict) else {}
        if response.get("status") == "completed":
            run = ledger.complete_run(run.run_id, result_summary=str(response.get("redacted_summary") or "oracle stub completed"))
            ok = True
            error = None
        else:
            run = ledger.fail_run(run.run_id, error_summary=str(response.get("disabled_reason") or "oracle_stub_denied"), blocked=True)
            ok = False
            error = {"code": "oracle_stub_denied", "message": response.get("disabled_reason") or "oracle stub denied the task"}
        report = _base_report(
            task=task,
            decision=decision,
            classification=classification,
            route_decision=route_decision,
            boundary_checks=boundary_checks,
            provider_decision=provider_decision,
            run=run.to_public_dict(),
            search_report=search_report,
            reviewer_plan=reviewer_plan,
            ok=ok,
            live_call_performed=False,
            response=None,
            error=error,
        )
        report["oracle_stub"] = oracle_report
        return report

    local_node_report = _local_node_report(decision)
    if local_node_report["used"]:
        ledger.append_event(run.run_id, "hybrid_node_route", "ok", str(local_node_report["summary"]))

    provider_result = _execute_provider(
        registry,
        decision.provider_id,
        provider_prompt,
        model=_model_id(provider_decision),
        live=live,
        run_id=run.run_id,
    )
    if provider_result["ok"]:
        response = provider_result["response"]
        assert isinstance(response, ProviderResponse)
        ledger.append_event(run.run_id, "provider_response", "ok", _response_summary(response))
        run = ledger.complete_run(run.run_id, result_summary=_response_summary(response))
        report = _base_report(
            task=task,
            decision=decision,
            classification=classification,
            route_decision=route_decision,
            boundary_checks=boundary_checks,
            provider_decision=provider_decision,
            run=run.to_public_dict(),
            search_report=search_report,
            reviewer_plan=reviewer_plan,
            ok=True,
            live_call_performed=bool(provider_result["live_call_performed"]),
            response=response.to_public_dict(),
            error=None,
        )
    else:
        error = provider_result["error"]
        assert isinstance(error, dict)
        ledger.append_event(run.run_id, "provider_error", "failed", str(error.get("message") or error.get("code") or "provider_error"))
        run = ledger.fail_run(run.run_id, error_summary=str(error.get("message") or error.get("code") or "provider_error"))
        report = _base_report(
            task=task,
            decision=decision,
            classification=classification,
            route_decision=route_decision,
            boundary_checks=boundary_checks,
            provider_decision=provider_decision,
            run=run.to_public_dict(),
            search_report=search_report,
            reviewer_plan=reviewer_plan,
            ok=False,
            live_call_performed=bool(provider_result["live_call_performed"]),
            response=None,
            error=error,
        )
    report["local_node"] = local_node_report
    return report


def decide_auto_runtime_route(
    task_text: str,
    *,
    classification: TaskClassification | None = None,
    provider: str = "auto",
    live: bool = False,
    local_file_context: bool = False,
) -> AutoRuntimeDecision:
    classification = classification or classify_task(task_text)
    normalized_provider = normalize_provider_id(provider)
    if normalized_provider == "auto":
        normalized_provider = "mock"
    difficulty = _difficulty_for(classification, task_text)
    privacy = _privacy_for(classification, local_file_context=local_file_context)
    search_needed = "web_research" in classification.required_capabilities
    tool_needed = bool({"local_tools", "pc_operations", "dangerous_operations"} & set(classification.required_capabilities))
    reasons = [
        f"classification:{classification.category}",
        f"risk:{classification.risk}",
        f"difficulty:{difficulty}",
        f"privacy:{privacy}",
    ]

    if privacy == "dangerous":
        return AutoRuntimeDecision(
            difficulty=difficulty,
            privacy=privacy,
            route="deny",
            approval_required=True,
            search_needed=search_needed,
            tool_needed=tool_needed,
            local_file_context=local_file_context,
            provider_id=normalized_provider,
            reasons=tuple(reasons + ["dangerous_or_tool_operation_denied"]),
        )
    if local_file_context or privacy == "private":
        if normalized_provider == "local" and live:
            route: AutoRoute = "local_llm"
            private_provider_id = "local"
            private_reasons = ["private_context_kept_local", "local_provider_requested"]
        else:
            route = "hybrid_node"
            private_provider_id = "mock"
            private_reasons = ["private_context_kept_local"]
            if normalized_provider in _EXTERNAL_LIVE_PROVIDERS:
                private_reasons.append("external_provider_blocked_for_private_context")
            elif normalized_provider == "local":
                private_reasons.append("local_provider_requires_live_for_private_context")
            else:
                private_reasons.append("mock_local_safe_path")
        return AutoRuntimeDecision(
            difficulty=difficulty,
            privacy="local_file" if local_file_context else privacy,
            route=route,
            approval_required=False,
            search_needed=search_needed,
            tool_needed=tool_needed,
            local_file_context=local_file_context,
            provider_id=private_provider_id,
            reasons=tuple(reasons + private_reasons),
        )
    if normalized_provider == "local":
        return AutoRuntimeDecision(
            difficulty=difficulty,
            privacy=privacy,
            route="local_llm",
            approval_required=False,
            search_needed=search_needed,
            tool_needed=tool_needed,
            local_file_context=local_file_context,
            provider_id=normalized_provider,
            reasons=tuple(reasons + ["local_provider_requested"]),
        )
    if difficulty == "agent" and privacy == "public":
        return AutoRuntimeDecision(
            difficulty=difficulty,
            privacy=privacy,
            route="cloud_contract_candidate",
            approval_required=False,
            search_needed=search_needed,
            tool_needed=tool_needed,
            local_file_context=local_file_context,
            provider_id="oracle-stub",
            reasons=tuple(reasons + ["hard_public_task_uses_oracle_stub_contract"]),
        )
    return AutoRuntimeDecision(
        difficulty=difficulty,
        privacy=privacy,
        route="instant_local",
        approval_required=False,
        search_needed=search_needed,
        tool_needed=tool_needed,
        local_file_context=local_file_context,
        provider_id=normalized_provider,
        reasons=tuple(reasons + ["mock_or_local_safe_path"]),
    )


def _classification_payload(classification: TaskClassification, decision: AutoRuntimeDecision) -> dict[str, object]:
    payload = classification.to_public_dict()
    payload["auto_difficulty"] = decision.difficulty
    payload["auto_privacy"] = decision.privacy
    payload["auto_route"] = decision.route
    return payload


def _route_decision(task: str, decision: AutoRuntimeDecision, classification: TaskClassification) -> dict[str, object]:
    if decision.route == "cloud_contract_candidate":
        route = preview_route(
            _PUBLIC_CLOUD_CONTRACT_PREVIEW_TASK,
            mode="official_hybrid_private",
            requested_capability="cloud_orchestration",
            risk_hint="hard public reasoning",
        ).to_public_dict()
    elif decision.route == "hybrid_node":
        route = preview_route(
            task,
            mode="official_hybrid_private",
            requested_capability="private_files" if decision.privacy == "local_file" else "local_tools",
            has_local_node=True,
            local_node_verification_state="present_verified",
            local_node_capabilities=("private_files", "local_tools", "mock_search", "ledger"),
            require_enrolled_verified_session=True,
            session_verification_state="enrolled_verified",
        ).to_public_dict()
    else:
        route = preview_route(
            task,
            mode="full_private_self_host",
            requested_capability="public_docs" if classification.category in {"simple_chat", "summarize_public"} else None,
        ).to_public_dict()
    route["auto_runtime"] = decision.to_public_dict()
    route["route_strategy"] = decision.route
    route["privacy_class"] = decision.privacy
    route["approval_state"] = "required" if decision.approval_required else "not_required"
    route["cloud_contract_candidate"] = decision.route == "cloud_contract_candidate"
    route["private_file_content_sent_to_cloud"] = False
    route["provider_key_sent_to_cloud"] = False
    route["raw_prompt_body_sent_to_cloud"] = False
    return route


def _provider_decision(
    registry: ProviderRegistry,
    provider_id: str,
    decision: AutoRuntimeDecision,
    *,
    live: bool,
) -> dict[str, object]:
    if provider_id == "oracle-stub":
        return {
            "provider_id": "oracle-stub",
            "provider_available": True,
            "provider_configured": True,
            "provider_reason": None,
            "model_id": "local-dev-oracle-stub-fixture",
            "live_call_performed": False,
            "requires_live": False,
            "local_only": True,
            "external_provider_allowed": False,
            "route": decision.route,
        }
    status = registry.status_for(provider_id)
    return {
        "provider_id": provider_id,
        "provider_available": status.available,
        "provider_configured": status.configured,
        "provider_reason": status.reason,
        "model_id": _model_for_provider(provider_id, decision),
        "live_call_performed": False,
        "requires_live": provider_id in _LIVE_CAPABLE_PROVIDERS,
        "live_requested": live,
        "local_only": provider_id in {"mock", "local"},
        "external_provider_allowed": provider_id in _EXTERNAL_LIVE_PROVIDERS and live and decision.privacy == "public",
        "route": decision.route,
    }


def _execute_provider(
    registry: ProviderRegistry,
    provider_id: str,
    prompt: str,
    *,
    model: str,
    live: bool,
    run_id: str,
) -> dict[str, object]:
    adapter = registry.resolve(provider_id)
    status = adapter.status()
    if not status.available:
        return {
            "ok": False,
            "live_call_performed": False,
            "error": {"code": "provider_unavailable", "message": status.reason or "provider unavailable"},
        }
    if provider_id in _EXTERNAL_LIVE_PROVIDERS and not live:
        return {
            "ok": False,
            "live_call_performed": False,
            "error": {"code": "live_required", "message": f"{provider_id} execution requires --live and env opt-in."},
        }
    allow_live_call = bool(live and provider_id in _LIVE_CAPABLE_PROVIDERS)
    try:
        response = adapter.generate(
            ProviderRequest(prompt=prompt, model=model, metadata={"run_id": run_id}),
            allow_live_call=allow_live_call,
        )
    except ProviderError as exc:
        return {
            "ok": False,
            "live_call_performed": _provider_error_after_live_attempt(provider_id, allow_live_call, exc),
            "error": exc.to_public_dict(),
        }
    return {
        "ok": True,
        "live_call_performed": bool(allow_live_call),
        "response": _normalize_provider_response(response),
    }


def _execute_oracle_stub(
    task: str,
    classification: TaskClassification,
    route_decision: dict[str, object],
    *,
    ledger: RunLedger,
    run_id: str,
) -> dict[str, object]:
    try:
        from ora_core.hybrid.oracle_stub import (
            LocalDevOracleStubQueue,
            build_oracle_stub_request,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        reason = f"oracle_stub_unavailable:{type(exc).__name__}"
        ledger.append_event(run_id, "oracle_stub_import", "failed", reason)
        return {
            "schema_version": "yonerai-oracle-stub/v0.1",
            "ok": False,
            "operation": "import",
            "status": "failed",
            "local_dev_stub": True,
            "request": {},
            "queue": {},
            "response": {
                "status": "failed",
                "disabled_reason": reason,
                "redacted_summary": "oracle stub unavailable in this environment",
            },
            "network_required": False,
            "provider_call_performed": False,
            "production_oracle_used": False,
            "official_cloud_runtime_implemented": False,
        }

    request = build_oracle_stub_request(
        task_text=task,
        classification=classification.to_public_dict(),
        route_decision=route_decision,
        run_id=run_id,
    )
    queue = LocalDevOracleStubQueue()
    item = queue.enqueue(request)
    ledger.append_event(run_id, "oracle_stub_enqueued", "ok" if request.disabled_reason is None else "blocked", f"queue_id={item.queue_id}")
    completed = queue.process_next()
    if completed is None or completed.response is None:
        ledger.append_event(run_id, "oracle_stub_result", "failed", "oracle stub queue processing failed")
        return {
            "schema_version": "yonerai-oracle-stub/v0.1",
            "ok": False,
            "operation": "queue",
            "status": "failed",
            "local_dev_stub": True,
            "request": request.to_public_dict(),
            "queue": completed.to_public_dict() if completed is not None else {},
            "response": {
                "status": "failed",
                "disabled_reason": "oracle_stub_queue_processing_failed",
                "redacted_summary": "oracle stub queue processing failed",
            },
            "network_required": False,
            "provider_call_performed": False,
            "production_oracle_used": False,
            "official_cloud_runtime_implemented": False,
        }
    response = completed.response
    ledger.append_event(run_id, "oracle_stub_result", response.status, response.redacted_summary)
    return {
        "schema_version": "yonerai-oracle-stub/v0.1",
        "ok": response.status == "completed",
        "operation": "queue",
        "status": response.status,
        "local_dev_stub": True,
        "request": request.to_public_dict(),
        "queue": completed.to_public_dict(),
        "response": response.to_public_dict(),
        "network_required": False,
        "provider_call_performed": False,
        "production_oracle_used": False,
        "official_cloud_runtime_implemented": False,
    }


def _mock_search_report(task: str, decision: AutoRuntimeDecision) -> dict[str, object]:
    if not decision.search_needed:
        return {
            "needed": False,
            "mode": "not_requested",
            "network_performed": False,
            "results": [],
            "summary": "search not requested",
        }
    from ora_core.search import MockSearchAdapter, SearchRequest, build_live_search_disabled_boundary

    results = [result.to_public_dict() for result in MockSearchAdapter().search(SearchRequest(query=task))]
    return {
        "needed": True,
        "mode": "mock",
        "network_performed": False,
        "live_boundary": build_live_search_disabled_boundary(task),
        "results": results,
        "summary": f"mock_search_results={len(results)}",
    }


def _reviewer_plan(task: str, decision: AutoRuntimeDecision) -> dict[str, object]:
    if decision.difficulty != "agent":
        return {
            "enabled": False,
            "subtask_count": 0,
            "subtasks": [],
            "reviewer": {"role": "reviewer", "required": False},
            "provider_calls_performed": False,
            "source": "deterministic_auto_runtime",
        }
    subtasks = [
        {
            "id": "T1",
            "role": "planner",
            "goal": "Identify constraints, privacy boundary, and the safest execution surface.",
            "success_criteria": "route and non-actions are explicit",
        },
        {
            "id": "T2",
            "role": "executor",
            "goal": "Run only the selected public-safe local or stub execution path.",
            "success_criteria": "run_id and ledger events are recorded",
        },
        {
            "id": "T3",
            "role": "reviewer",
            "goal": "Check for boundary violations before presenting the result.",
            "success_criteria": "no secrets, private file content, shell, live Discord, or production cloud use",
        },
    ]
    return {
        "enabled": True,
        "subtask_count": len(subtasks),
        "subtasks": subtasks,
        "reviewer": {
            "role": "reviewer",
            "required": True,
            "checks": [
                "no_provider_key_output",
                "no_private_file_content_to_cloud",
                "no_arbitrary_shell",
                "no_live_discord",
                "no_production_oracle",
            ],
        },
        "provider_calls_performed": False,
        "source": "docs/AGENT_SWARM.md deterministic fallback concepts",
        "legacy_runtime_imported": False,
        "task_summary": safe_summary(task, max_chars=160),
    }


def _local_node_report(decision: AutoRuntimeDecision) -> dict[str, object]:
    if decision.route != "hybrid_node":
        return {"used": False, "summary": "local node not required", "network_performed": False}
    return {
        "used": True,
        "mode": "local_dev_fixture",
        "verified_session_fixture": True,
        "loopback_only": True,
        "network_performed": False,
        "public_tunnel_used": False,
        "message_body_persisted": False,
        "private_file_content_sent_to_cloud": False,
        "summary": "verified local-dev Local Node fixture selected; execution stayed local",
    }


def _base_report(
    *,
    task: str,
    decision: AutoRuntimeDecision,
    classification: TaskClassification,
    route_decision: dict[str, object],
    boundary_checks: dict[str, dict[str, object]],
    provider_decision: dict[str, object],
    run: dict[str, object],
    search_report: dict[str, object],
    reviewer_plan: dict[str, object],
    ok: bool,
    live_call_performed: bool,
    response: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": AUTO_RUNTIME_SCHEMA_VERSION,
        "ok": ok,
        "command": "yonerai ask --auto",
        "task_summary": safe_summary(task, max_chars=220),
        "auto": decision.to_public_dict(),
        "classification": _classification_payload(classification, decision),
        "route": route_decision,
        "provider": provider_decision,
        "run": run,
        "response": response,
        "search": search_report,
        "reviewer_plan": reviewer_plan,
        "boundary_checks": boundary_checks,
        "live_call_performed": live_call_performed,
        "error": error,
        "boundaries": {
            "network_required": False,
            "mock_search_only": search_report["mode"] == "mock",
            "live_search_performed": False,
            "shell_execution_performed": False,
            "arbitrary_file_access_performed": False,
            "private_file_content_sent_to_cloud_contract": False,
            "provider_key_output": False,
            "live_discord_used": False,
            "production_oracle_used": False,
            "official_cloud_runtime_implemented": False,
            "deploy_performed": False,
            "raw_prompt_persisted": False,
            "raw_completion_persisted": False,
        },
        "actions_not_performed": [
            "no arbitrary shell execution",
            "no arbitrary file access",
            "no live Discord",
            "no production Oracle",
            "no official cloud runtime",
            "no deploy",
            "no public tunnel",
            "no provider key output",
            "no live external provider call by default",
            "no private file content sent to cloud contract",
        ],
    }


def _difficulty_for(classification: TaskClassification, task_text: str) -> AutoDifficulty:
    low = task_text.lower()
    if classification.category in {"long_running", "coding"} or classification.complexity in {"advanced", "long_running"}:
        return "agent"
    if any(marker in low for marker in ("hard public reasoning", "review", "multi-step", "subtask", "agent", "large codebase")):
        return "agent"
    if classification.complexity == "standard":
        return "task"
    return "instant"


def _privacy_for(classification: TaskClassification, *, local_file_context: bool) -> AutoPrivacy:
    if classification.risk in {"dangerous", "pc_operation", "unsupported"}:
        return "dangerous"
    if local_file_context:
        return "local_file"
    if classification.risk == "private_data":
        return "private"
    return "public"


def _model_for_provider(provider_id: str, decision: AutoRuntimeDecision) -> str:
    if provider_id == "mock":
        return f"mock-{decision.difficulty}"
    if provider_id == "local":
        return "local-auto-runtime"
    if provider_id == "oracle-stub":
        return "local-dev-oracle-stub-fixture"
    return "auto-runtime-explicit-live"


def _model_id(provider_decision: Mapping[str, object]) -> str:
    return str(provider_decision.get("model_id") or "auto-runtime")


def _response_summary(response: ProviderResponse) -> str:
    return safe_summary(f"{response.provider}/{response.model}: {response.output_text}", max_chars=500)


def _normalize_provider_response(response: ProviderResponse) -> ProviderResponse:
    cleaned = normalize_legacy_generated_text(response.output_text)
    if cleaned == response.output_text:
        return response
    return ProviderResponse(
        provider=response.provider,
        model=response.model,
        output_text=cleaned,
        deterministic=response.deterministic,
        finish_reason=response.finish_reason,
    )


def _provider_error_after_live_attempt(provider_id: str, allow_live_call: bool, exc: ProviderError) -> bool:
    if not allow_live_call:
        return False
    if provider_id == "local" and exc.code == "local_provider_error":
        return True
    return exc.code in {"provider_http_error", "provider_connection_error", "provider_bad_response"}


def _decision_summary(decision: AutoRuntimeDecision) -> str:
    return (
        f"difficulty={decision.difficulty} privacy={decision.privacy} route={decision.route} "
        f"search={str(decision.search_needed).lower()} tool={str(decision.tool_needed).lower()}"
    )


def _normalize_task(task_text: str) -> str:
    return " ".join(str(task_text or "").split())
