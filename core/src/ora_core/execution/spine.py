from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ora_core.planning import build_execution_plan
from ora_core.providers import ProviderError, ProviderRequest, ProviderResponse, build_default_provider_registry
from ora_core.providers.registry import ProviderRegistry

from .boundaries import build_boundary_checks_for_task
from .ledger import RunLedger, build_run_ledger_from_env, safe_summary
from .legacy_text import normalize_legacy_generated_text


EXECUTION_RESULT_SCHEMA_VERSION = "yonerai-execution-result/v1"


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    run: dict[str, object]
    plan: dict[str, object]
    response: dict[str, object] | None
    boundary_checks: dict[str, dict[str, object]]
    live_call_performed: bool
    error: dict[str, object] | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": EXECUTION_RESULT_SCHEMA_VERSION,
            "ok": self.ok,
            "run": self.run,
            "plan": self.plan,
            "response": self.response,
            "boundary_checks": self.boundary_checks,
            "live_call_performed": self.live_call_performed,
            "error": self.error,
        }


def execute_task(
    task_text: str,
    *,
    provider_prompt: str | None = None,
    mode: str = "self-host",
    provider: str = "auto",
    live: bool = False,
    ledger: RunLedger | None = None,
    registry: ProviderRegistry | None = None,
    context_events: Sequence[Mapping[str, object]] | None = None,
    requested_tool: str | None = None,
    client_type: str = "discord",
) -> ExecutionResult:
    ledger = ledger or build_run_ledger_from_env()
    registry = registry or build_default_provider_registry()
    provider_prompt = provider_prompt if provider_prompt is not None else task_text
    plan = build_execution_plan(
        task_text,
        command="yonerai ask",
        mode=mode,
        provider=provider,
        dry_run=False,
        registry=registry,
    )
    plan_public = plan.to_public_dict()
    disabled_reason = ", ".join(plan.disabled_reasons) if plan.disabled_reasons else None
    run = ledger.create_run(
        task_text=task_text,
        classification=plan.classification.to_public_dict(),
        route_decision=plan.route_decision,
        provider_decision=plan.provider_selection.to_public_dict(),
        approval_required=bool(plan_public["approval"]["required"]),
        disabled_reason=disabled_reason,
    )
    ledger.append_event(run.run_id, "plan_created", "ok", f"{plan.classification.category}/{plan.provider_selection.provider_id}")
    boundary_checks = build_boundary_checks_for_task(
        plan.classification,
        requested_tool=requested_tool,
        client_type=client_type,
    )
    ledger.append_event(run.run_id, "boundary_checks", "ok", "web_search_and_tool_boundaries_disabled")
    for event in context_events or ():
        name = str(event.get("name") or "context")
        status = str(event.get("status") or "ok")
        summary = str(event.get("summary") or "")
        ledger.append_event(run.run_id, name, status, summary)

    if bool(plan_public["approval"]["required"]):
        ledger.append_event(run.run_id, "execution_blocked", "blocked", "approval_required")
        run = ledger.fail_run(run.run_id, error_summary="approval_required", blocked=True)
        return ExecutionResult(
            ok=False,
            run=run.to_public_dict(),
            plan=plan_public,
            response=None,
            boundary_checks=boundary_checks,
            live_call_performed=False,
            error={"code": "approval_required", "message": "Task requires approval and remains preview-only."},
        )

    adapter = registry.resolve(plan.provider_selection.provider_id)
    provider_status = adapter.status()
    if not provider_status.available:
        ledger.append_event(run.run_id, "provider_unavailable", "blocked", provider_status.reason or "provider unavailable")
        run = ledger.fail_run(run.run_id, error_summary=provider_status.reason or "provider_unavailable", blocked=True)
        return ExecutionResult(
            ok=False,
            run=run.to_public_dict(),
            plan=plan_public,
            response=None,
            boundary_checks=boundary_checks,
            live_call_performed=False,
            error={"code": "provider_unavailable", "message": provider_status.reason or "provider unavailable"},
        )

    live_capable_providers = {"local", "openai-compatible", "anthropic", "gemini"}
    allow_live_call = bool(live and adapter.provider_id in live_capable_providers)
    if adapter.provider_id in {"openai-compatible", "anthropic", "gemini"} and not live:
        label = adapter.provider_id.replace("-", " ").title()
        ledger.append_event(run.run_id, "execution_blocked", "blocked", f"{adapter.provider_id}_requires_live")
        run = ledger.fail_run(run.run_id, error_summary=f"{adapter.provider_id}_requires_explicit_live", blocked=True)
        return ExecutionResult(
            ok=False,
            run=run.to_public_dict(),
            plan=plan_public,
            response=None,
            boundary_checks=boundary_checks,
            live_call_performed=False,
            error={"code": "live_required", "message": f"{label} execution requires --live and env opt-in."},
        )

    try:
        request = ProviderRequest(
            prompt=provider_prompt,
            model=plan.provider_selection.model_id,
            metadata={"run_id": run.run_id},
        )
        provider_response = _normalize_provider_response(adapter.generate(request, allow_live_call=allow_live_call))
    except ProviderError as exc:
        ledger.append_event(run.run_id, "provider_error", "failed", exc.message)
        run = ledger.fail_run(run.run_id, error_summary=exc.message)
        live_call_attempted = _provider_error_after_live_attempt(adapter.provider_id, allow_live_call, exc)
        return ExecutionResult(
            ok=False,
            run=run.to_public_dict(),
            plan=plan_public,
            response=None,
            boundary_checks=boundary_checks,
            live_call_performed=live_call_attempted,
            error=exc.to_public_dict(),
        )

    ledger.append_event(run.run_id, "provider_response", "ok", _response_summary(provider_response))
    run = ledger.complete_run(run.run_id, result_summary=_response_summary(provider_response))
    return ExecutionResult(
        ok=True,
        run=run.to_public_dict(),
        plan=plan_public,
        response=provider_response.to_public_dict(),
        boundary_checks=boundary_checks,
        live_call_performed=bool(allow_live_call),
        error=None,
    )


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
