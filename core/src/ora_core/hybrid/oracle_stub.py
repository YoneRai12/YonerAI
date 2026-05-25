from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal

from ora_core.execution.ledger import RunLedger, safe_summary
from ora_core.planning.task_classifier import classify_task
from ora_core.route_preview import preview_route


ORACLE_STUB_SCHEMA_VERSION = "yonerai-oracle-stub/v0.1"
DEFAULT_ORACLE_STUB_TASK = "hard public reasoning over public API docs"
OracleStubStatus = Literal["queued", "completed", "denied"]


@dataclass(frozen=True)
class OracleStubRequest:
    request_id: str
    run_id: str
    task_class: str
    route_strategy: str
    approval_state: str
    audit_context: dict[str, object]
    args_hash: str
    privacy_class: str
    task_summary: str
    raw_private_content_included: bool
    raw_prompt_included: bool
    provider_key_included: bool
    network_required: bool
    production_oracle_used: bool
    official_cloud_runtime_implemented: bool
    disabled_reason: str | None
    schema_name: str = "OracleStubRequest"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OracleStubResponse:
    response_id: str
    request_id: str
    run_id: str
    status: OracleStubStatus
    route_strategy: str
    result_summary: str
    redacted_summary: str
    disabled_reason: str | None
    deterministic_fixture_result: bool
    public_repo_stub_executed: bool
    public_repo_execution_available: bool
    raw_result_included: bool
    raw_prompt_included: bool
    private_file_content_included: bool
    provider_key_included: bool
    message_body_persisted: bool
    network_call_performed: bool
    production_oracle_used: bool
    official_cloud_runtime_implemented: bool
    schema_name: str = "OracleStubResponse"

    def to_public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OracleStubQueueItem:
    queue_id: str
    request: OracleStubRequest
    status: OracleStubStatus
    enqueued_at: str
    completed_at: str | None
    response: OracleStubResponse | None
    schema_name: str = "OracleStubQueueItem"

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["request"] = self.request.to_public_dict()
        payload["response"] = self.response.to_public_dict() if self.response else None
        return payload


class LocalDevOracleStubQueue:
    def __init__(self) -> None:
        self._items: list[OracleStubQueueItem] = []

    def enqueue(self, request: OracleStubRequest) -> OracleStubQueueItem:
        item = OracleStubQueueItem(
            queue_id=f"oracle_stub_queue_{len(self._items) + 1:04d}",
            request=request,
            status="queued",
            enqueued_at=_now(),
            completed_at=None,
            response=None,
        )
        self._items.append(item)
        return item

    def process_next(self) -> OracleStubQueueItem | None:
        for index, item in enumerate(self._items):
            if item.status != "queued":
                continue
            response = process_oracle_stub_request(item.request)
            completed = OracleStubQueueItem(
                queue_id=item.queue_id,
                request=item.request,
                status=response.status,
                enqueued_at=item.enqueued_at,
                completed_at=_now(),
                response=response,
            )
            self._items[index] = completed
            return completed
        return None

    def list_items(self) -> list[OracleStubQueueItem]:
        return list(self._items)


def build_oracle_stub_status_report() -> dict[str, object]:
    return {
        "schema_version": ORACLE_STUB_SCHEMA_VERSION,
        "ok": True,
        "operation": "status",
        "status": "local_dev_stub_available",
        "queue_available": True,
        "deterministic_fixture_result": True,
        "network_required": False,
        "provider_call_performed": False,
        "production_oracle_used": False,
        "official_cloud_runtime_implemented": False,
        "production_trust_material": False,
        "raw_prompt_persisted": False,
        "private_file_content_sent_to_cloud_stub": False,
        "commands": [
            "yonerai oracle status --json",
            "yonerai oracle queue --json",
            "yonerai oracle queue hard public reasoning over public API docs --json",
        ],
        "actions_not_performed": _oracle_stub_non_actions(),
    }


def build_oracle_stub_queue_report(
    task_text: str = DEFAULT_ORACLE_STUB_TASK,
    *,
    ledger: RunLedger | None = None,
) -> dict[str, object]:
    task = " ".join(str(task_text or "").split()) or DEFAULT_ORACLE_STUB_TASK
    classification = classify_task(task)
    route = preview_route(task, mode="official_hybrid_private").to_public_dict()
    disabled_reason = _oracle_stub_disabled_reason(route)
    run = None
    run_id = ""
    ledger_task_summary = _public_task_summary(
        task_class=str(route.get("task_class") or classification.to_public_dict().get("category") or "unknown"),
        route_strategy=str(route.get("route_strategy") or "deny"),
        privacy_class=str(route.get("privacy_class") or "unknown"),
    )
    if ledger is not None:
        run = ledger.create_run(
            task_text=ledger_task_summary,
            classification=classification.to_public_dict(),
            route_decision=route,
            provider_decision=_oracle_stub_provider_decision(),
            approval_required=bool(route.get("approval_required")),
            disabled_reason=disabled_reason,
        )
        run_id = run.run_id
    else:
        run_id = _public_run_id(route)
    request = build_oracle_stub_request(
        task_text=task,
        classification=classification.to_public_dict(),
        route_decision=route,
        run_id=run_id,
        disabled_reason=disabled_reason,
    )
    queue = LocalDevOracleStubQueue()
    item = queue.enqueue(request)
    if ledger is not None and run is not None:
        ledger.append_event(
            run.run_id,
            "oracle_stub_enqueued",
            "ok" if disabled_reason is None else "blocked",
            f"queue_id={item.queue_id} route_strategy={request.route_strategy}",
        )
    completed = queue.process_next()
    if completed is None or completed.response is None:
        raise RuntimeError("oracle stub queue did not process the enqueued item")
    response = completed.response
    if ledger is not None and run is not None:
        ledger.append_event(run.run_id, "oracle_stub_result", response.status, response.redacted_summary)
        if response.status == "completed":
            run = ledger.complete_run(run.run_id, result_summary=response.redacted_summary)
        else:
            run = ledger.fail_run(run.run_id, error_summary=response.disabled_reason or "oracle_stub_denied", blocked=True)
    return {
        "schema_version": ORACLE_STUB_SCHEMA_VERSION,
        "ok": response.status == "completed",
        "operation": "queue",
        "status": response.status,
        "local_dev_stub": True,
        "request": request.to_public_dict(),
        "queue": completed.to_public_dict(),
        "response": response.to_public_dict(),
        "route": route,
        "classification": classification.to_public_dict(),
        "run": run.to_public_dict() if run is not None else None,
        "events": [
            {"name": "oracle_stub_enqueued", "status": "ok" if disabled_reason is None else "blocked"},
            {"name": "oracle_stub_result", "status": response.status},
        ],
        "network_required": False,
        "provider_call_performed": False,
        "production_oracle_used": False,
        "official_cloud_runtime_implemented": False,
        "actions_not_performed": _oracle_stub_non_actions(),
    }


def build_oracle_stub_request(
    *,
    task_text: str,
    classification: dict[str, object],
    route_decision: dict[str, object],
    run_id: str,
    disabled_reason: str | None = None,
) -> OracleStubRequest:
    route_strategy = str(route_decision.get("route_strategy") or "deny")
    task_class = str(route_decision.get("task_class") or classification.get("category") or "unknown")
    privacy_class = str(route_decision.get("privacy_class") or "unknown")
    audit_context = {
        "audit_event_required": bool((route_decision.get("audit_requirements") or {}).get("audit_event_required"))
        if isinstance(route_decision.get("audit_requirements"), dict)
        else True,
        "args_hash_required": bool((route_decision.get("audit_requirements") or {}).get("args_hash_required"))
        if isinstance(route_decision.get("audit_requirements"), dict)
        else True,
        "cloud_escape": route_strategy == "cloud_contract_candidate",
        "raw_prompt_body_sent_to_cloud": False,
        "private_file_content_sent_to_cloud": False,
        "provider_key_sent_to_cloud": False,
    }
    task_summary = _public_task_summary(
        task_class=task_class,
        route_strategy=route_strategy,
        privacy_class=privacy_class,
    )
    return OracleStubRequest(
        request_id=f"oracle_stub_request_{_short_hash(run_id)}",
        run_id=run_id,
        task_class=task_class,
        route_strategy=route_strategy,
        approval_state=str(route_decision.get("approval_state") or "not_required"),
        audit_context=audit_context,
        args_hash=_args_hash(task_summary, task_class, route_strategy, privacy_class),
        privacy_class=privacy_class,
        task_summary=task_summary,
        raw_private_content_included=False,
        raw_prompt_included=False,
        provider_key_included=False,
        network_required=False,
        production_oracle_used=False,
        official_cloud_runtime_implemented=False,
        disabled_reason=safe_summary(disabled_reason, max_chars=180) if disabled_reason else None,
    )


def process_oracle_stub_request(request: OracleStubRequest) -> OracleStubResponse:
    if request.disabled_reason is not None:
        status: OracleStubStatus = "denied"
        result_summary = f"oracle stub denied: {request.disabled_reason}"
    else:
        status = "completed"
        result_summary = f"oracle stub fixture completed {request.task_class}/{request.route_strategy}"
    redacted_summary = safe_summary(result_summary, max_chars=220)
    return OracleStubResponse(
        response_id=f"oracle_stub_response_{_short_hash(request.request_id)}",
        request_id=request.request_id,
        run_id=request.run_id,
        status=status,
        route_strategy=request.route_strategy,
        result_summary=redacted_summary,
        redacted_summary=redacted_summary,
        disabled_reason=request.disabled_reason,
        deterministic_fixture_result=True,
        public_repo_stub_executed=True,
        public_repo_execution_available=False,
        raw_result_included=False,
        raw_prompt_included=False,
        private_file_content_included=False,
        provider_key_included=False,
        message_body_persisted=False,
        network_call_performed=False,
        production_oracle_used=False,
        official_cloud_runtime_implemented=False,
    )


def oracle_stub_eligible(route_decision: dict[str, object]) -> bool:
    return _oracle_stub_disabled_reason(route_decision) is None


def _oracle_stub_disabled_reason(route_decision: dict[str, object]) -> str | None:
    if route_decision.get("dangerous_operation"):
        return "dangerous_operation_requires_private_approval"
    if route_decision.get("privacy_class") != "public":
        return "privacy_class_not_public"
    if route_decision.get("route_strategy") != "cloud_contract_candidate":
        return "route_strategy_not_cloud_contract_candidate"
    if route_decision.get("private_file_content_sent_to_cloud") is not False:
        return "private_file_content_boundary_not_proven"
    if route_decision.get("raw_prompt_body_sent_to_cloud") is not False:
        return "raw_prompt_boundary_not_proven"
    if route_decision.get("provider_key_sent_to_cloud") is not False:
        return "provider_key_boundary_not_proven"
    return None


def _oracle_stub_provider_decision() -> dict[str, object]:
    return {
        "provider_id": "oracle-stub",
        "provider_available": True,
        "provider_configured": True,
        "provider_reason": None,
        "model_tier": "disabled",
        "model_id": "local-dev-oracle-stub-fixture",
        "approval_required": True,
        "local_node_required": False,
        "external_provider_allowed": False,
        "disabled_reasons": [],
        "reasons": ["local_dev_oracle_stub_no_network"],
    }


def _oracle_stub_non_actions() -> list[str]:
    return [
        "no network call",
        "no provider call",
        "no production Oracle",
        "no official cloud runtime",
        "no private file content",
        "no raw prompt persistence",
        "no provider key",
        "no live Discord",
        "no shell execution",
        "no deploy",
    ]


def _public_task_summary(*, task_class: str, route_strategy: str, privacy_class: str) -> str:
    return safe_summary(
        f"oracle_stub_task task_class={task_class} route_strategy={route_strategy} privacy_class={privacy_class}",
        max_chars=180,
    )


def _public_run_id(route_decision: dict[str, object]) -> str:
    route_key = "|".join(
        (
            str(route_decision.get("task_class") or "unknown"),
            str(route_decision.get("route_strategy") or "deny"),
            str(route_decision.get("privacy_class") or "unknown"),
        )
    )
    return f"run_oracle_stub_{_short_hash(route_key)}"


def _args_hash(task_summary: str, task_class: str, route_strategy: str, privacy_class: str) -> str:
    return "sha256:" + _short_hash("|".join((task_summary, task_class, route_strategy, privacy_class)), length=32)


def _short_hash(value: str, *, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
