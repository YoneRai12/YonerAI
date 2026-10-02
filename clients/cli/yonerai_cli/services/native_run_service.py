from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from yonerai_cli.services.conversation_sync_policy_service import (
    ConversationSyncPolicyError,
    build_conversation_execution_policy,
    build_conversation_policy_list_report,
)
from yonerai_cli.services.provider_sharing_service import (
    ProviderSharingError,
    build_context_preview,
    resolve_provider_data_policy,
)
from yonerai_cli.services.control_spine_service import (
    DEFAULT_STAGING_CONTROL_SPINE_ORIGIN,
    build_control_spine_context,
    load_config_for_control_spine,
)


NATIVE_RUN_CLIENT_SCHEMA_VERSION = "yonerai-native-run-client/v0.1"
NATIVE_RUN_CONTRACT_VERSION = "yonerai.native-run.v1.staging"
CAPABILITY_MANIFEST_VERSION = "yonerai.capability-manifest.v1.staging"
MODULE_MANIFEST_VERSION = "yonerai.module-manifest.v1.staging"
STATUS_PATH = "/v1/status"
RUNS_PATH = "/v1/runs"
RUN_PATH_TEMPLATE = "/v1/runs/{run_id}"
RUN_EVENTS_PATH_TEMPLATE = "/v1/runs/{run_id}/events"
RUN_CANCEL_PATH_TEMPLATE = "/v1/runs/{run_id}/cancel"
CAPABILITIES_PATH = "/v1/capabilities"
MODULES_PATH = "/v1/modules"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,160}$")
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,120}$")
MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,120}$")
CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,120}$")

HeaderJsonTransport = Callable[
    [str, str, Mapping[str, str], Mapping[str, object] | None, float],
    tuple[int, Mapping[str, object], Mapping[str, str]],
]


class NativeRunServiceError(ValueError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code

    def to_safe_error(self) -> dict[str, object]:
        return _safe_error(self.code, self.message, status_code=self.status_code)


def build_native_run_submit_report(
    prompt: str,
    *,
    project_id: str = "personal-staging",
    module_id: str = "run.core",
    capability: str = "run.echo",
    conversation_id: str | None = None,
    conversation_origin: str | None = None,
    sync_policy: str | None = None,
    conversation_policy_store: str | None = None,
    provider_data_policy: str | None = None,
    provider_sharing_store: str | None = None,
    idempotency_key: str | None = None,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _native_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("native_run_submit", context)
    report["run"] = None
    report["queue"] = None
    conversation_policy = _resolve_conversation_policy(
        conversation_id=conversation_id,
        conversation_origin=conversation_origin,
        sync_policy=sync_policy,
        conversation_policy_store=conversation_policy_store,
    )
    if conversation_policy is not None:
        report["conversation_policy"] = conversation_policy
        if _conversation_policy_blocks_official_dispatch(conversation_policy):
            report["ok"] = False
            report["error"] = _conversation_policy_error(conversation_policy)
            return report
    effective_sync_policy = _effective_sync_policy(conversation_policy, sync_policy)
    try:
        safe_prompt = _safe_prompt(prompt)
        provider_policy = resolve_provider_data_policy(
            conversation_id=conversation_id,
            sync_policy=effective_sync_policy,
            requested_policy=provider_data_policy,
            store_path=provider_sharing_store,
            config_path=claim_path,
        )
    except ProviderSharingError as exc:
        report["ok"] = False
        report["provider_sharing"] = {
            "provider_data_policy": provider_data_policy or "none",
            "conversation_id": conversation_id,
            "sync_policy": effective_sync_policy,
            "openai_shared_traffic_enabled": False,
            "raw_body_included": False,
            "provider_key_included": False,
            "google_token_included": False,
            "local_path_included": False,
        }
        report["error"] = exc.to_safe_error()
        return report
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["provider_sharing"] = {
            "provider_data_policy": provider_data_policy or "none",
            "conversation_id": conversation_id,
            "sync_policy": effective_sync_policy,
            "openai_shared_traffic_enabled": False,
            "raw_body_included": False,
            "provider_key_included": False,
            "google_token_included": False,
            "local_path_included": False,
        }
        report["error"] = exc.to_safe_error()
        return report
    report["provider_sharing"] = provider_policy
    report["context_preview"] = build_context_preview(prompt=safe_prompt, provider_policy=provider_policy)
    report["openai_shared_traffic_enabled"] = False
    report["openai_shared_traffic_sent"] = False
    if not _require_linked_session(report, context, "Native Run submission requires staging login."):
        return report
    provider_body_on_aws = provider_policy.get("provider_data_policy") == "openai_shared_explicit"
    provider_prepare_report: dict[str, object] | None = None
    if provider_body_on_aws:
        try:
            provider_prepare_report = _prepare_provider_gateway_context(
                context=context,
                conversation_id=_safe_text(conversation_id, fallback="conversation"),
                safe_prompt=safe_prompt,
                transport=transport,
                timeout_seconds=timeout_seconds,
            )
        except NativeRunServiceError as exc:
            report["ok"] = False
            report["error"] = exc.to_safe_error()
            return report
        report["provider_gateway_prepare"] = provider_prepare_report
    input_payload: dict[str, object] = {
        "kind": "inline_text",
        "summary": safe_prompt[:160],
        "raw_file_bytes_included": False,
        "local_absolute_paths_included": False,
    }
    body_ref: dict[str, object] | None = None
    if provider_body_on_aws:
        body_ref = {
            "conversation_id": _safe_text(conversation_id, fallback="conversation"),
            "source": "cloud_conversation",
            "message_body_included": False,
            "plaintext_value_included": False,
        }
        input_payload.update(
            {
                "kind": "cloud_conversation_ref",
                "body_boundary": "body_on_aws",
                "body_source": "aws_conversation_body",
                "body_ref": body_ref,
                "current_message_included": True,
                "message_body_included": False,
                "plaintext_value_included": False,
                "local_private_memory_included": False,
                "local_node_payload_included": False,
                "attachments_included": False,
                "provider_keys_included": False,
                "google_tokens_included": False,
            }
        )
    payload = {
        "idempotency_key": _safe_idempotency_key(idempotency_key or f"cli_{uuid.uuid4().hex}"),
        "project_id": _safe_project_id(project_id),
        "module_id": _safe_module_id(module_id),
        "capability": _safe_capability(capability),
        "privacy_class": "synthetic" if provider_body_on_aws else "metadata_only",
        "approval_state": "staging_auto_approved_metadata_only",
        "audit_reason": "Public CLI submitted an explicit-consent staging provider run."
        if provider_body_on_aws
        else "Public CLI submitted a metadata-only staging Native Run.",
        "body_boundary": "body_on_aws" if provider_body_on_aws else "metadata_only",
        "input": input_payload,
        "provider_data_policy": provider_policy.get("provider_data_policy"),
        "provider_sharing": _provider_sharing_payload(provider_policy),
        "context_preview": report["context_preview"],
        "files": [],
    }
    if provider_prepare_report is not None:
        payload["provider_gateway_prepare"] = {
            "message_body_included": False,
            "provider_traffic_allowed": bool(provider_prepare_report.get("provider_traffic_allowed")),
            "context_manifest_raw_content_included": False,
        }
    if conversation_policy is not None:
        payload["conversation_id"] = _safe_text(conversation_policy.get("conversation_id"), fallback="conversation")
        payload["sync_policy"] = _safe_text(conversation_policy.get("sync_policy"), fallback="cloud_to_local")
        payload["body_on_aws"] = True
    if body_ref is not None:
        payload["body_ref"] = body_ref
        payload["message_body_included"] = False
        payload["plaintext_value_included"] = False
    if conversation_policy is not None:
        payload["conversation"] = _conversation_policy_payload(conversation_policy)
    try:
        status_code, body, headers = _request_json(
            "POST",
            context,
            RUNS_PATH,
            _auth_headers(context),
            payload,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    _merge_response_metadata(report, status_code, headers)
    if status_code == 401:
        report["ok"] = False
        _mark_staging_session_rejected(report, body)
        report["error"] = _staging_session_rejected_error(body, status_code=status_code)
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _service_error_from_body("native_run_submit_failed", body, status_code=status_code)
        return report
    try:
        _assert_public_safe_payload(body)
        report["run"] = _sanitize_run(body.get("run") if isinstance(body.get("run"), Mapping) else {})
        report["queue"] = _sanitize_queue(body.get("queue") if isinstance(body.get("queue"), Mapping) else {})
        report["contract_version"] = _safe_text(body.get("contract_version"), fallback=NATIVE_RUN_CONTRACT_VERSION)
        report["provider_call_enabled"] = bool(body.get("provider_call_enabled", False))
        report["openai_shared_traffic_enabled"] = bool(
            provider_policy.get("openai_shared_traffic_enabled") and report["provider_call_enabled"]
        )
        report["openai_shared_traffic_sent"] = bool(report["openai_shared_traffic_enabled"])
        if report["openai_shared_traffic_sent"]:
            report["actions_not_performed"] = [
                item for item in report["actions_not_performed"] if item != "no OpenAI shared traffic"
            ]
        report["raw_private_content_logged"] = bool(body.get("raw_private_content_logged", False))
        report["request_waited_for_worker_completion"] = bool(body.get("request_waited_for_worker_completion", False))
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
    return report


def build_native_run_status_report(
    run_id: str,
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    return _build_run_get_report(
        "native_run_status",
        run_id,
        path=RUN_PATH_TEMPLATE.format(run_id=quote(_safe_run_id(run_id), safe="")),
        config=config,
        env=env,
        claim_path=claim_path,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )


def build_native_run_result_report(
    run_id: str,
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    report = _build_run_get_report(
        "native_run_result",
        run_id,
        path=RUN_PATH_TEMPLATE.format(run_id=quote(_safe_run_id(run_id), safe="")),
        config=config,
        env=env,
        claim_path=claim_path,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    run = report.get("run") if isinstance(report.get("run"), Mapping) else {}
    report["result"] = {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "result_ref": run.get("result_ref"),
        "result_summary": run.get("result_summary") or ("not_ready" if report.get("ok") else "unavailable"),
        "raw_chain_of_thought_included": False,
        "google_token_included": False,
        "provider_key_included": False,
    }
    return report


def build_native_run_events_report(
    run_id: str,
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _native_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("native_run_events", context)
    report["requested_run_id"] = _safe_run_id(run_id)
    report["events"] = []
    if not _require_linked_session(report, context, "Native Run events require staging login."):
        return report
    try:
        status_code, body, headers = _request_json(
            "GET",
            context,
            RUN_EVENTS_PATH_TEMPLATE.format(run_id=quote(_safe_run_id(run_id), safe="")),
            _auth_headers(context),
            None,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    _merge_response_metadata(report, status_code, headers)
    if status_code == 401:
        report["ok"] = False
        _mark_staging_session_rejected(report, body)
        report["error"] = _staging_session_rejected_error(body, status_code=status_code)
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _service_error_from_body("native_run_events_failed", body, status_code=status_code)
        return report
    try:
        _assert_public_safe_payload(body)
        raw_events = body.get("events") if isinstance(body.get("events"), list) else []
        report["events"] = [_sanitize_event(item) for item in raw_events if isinstance(item, Mapping)]
        report["event_count"] = len(report["events"])
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
    return report


def build_native_run_cancel_report(
    run_id: str,
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _native_context(config=config, env=env, claim_path=claim_path)
    report = _base_report("native_run_cancel", context)
    report["requested_run_id"] = _safe_run_id(run_id)
    if not _require_linked_session(report, context, "Native Run cancellation requires staging login."):
        return report
    try:
        status_code, body, headers = _request_json(
            "POST",
            context,
            RUN_CANCEL_PATH_TEMPLATE.format(run_id=quote(_safe_run_id(run_id), safe="")),
            _auth_headers(context),
            {"audit_reason": "Public CLI requested staging Native Run cancellation."},
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    _merge_response_metadata(report, status_code, headers)
    if status_code == 401:
        report["ok"] = False
        _mark_staging_session_rejected(report, body)
        report["error"] = _staging_session_rejected_error(body, status_code=status_code)
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _service_error_from_body("native_run_cancel_failed", body, status_code=status_code)
        return report
    try:
        _assert_public_safe_payload(body)
        report["run"] = _sanitize_run(body.get("run") if isinstance(body.get("run"), Mapping) else {})
        report["cancellation"] = _sanitize_mapping(body.get("cancellation") if isinstance(body.get("cancellation"), Mapping) else {})
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
    return report


def build_worker_status_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _native_context(config=config, env=env, claim_path=claim_path, allow_default_origin=True)
    report = _base_report("worker_status", context)
    try:
        status_code, body, headers = _request_json(
            "GET",
            context,
            STATUS_PATH,
            {},
            None,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    _merge_response_metadata(report, status_code, headers)
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _service_error_from_body("worker_status_failed", body, status_code=status_code)
        return report
    try:
        snapshot = body.get("status_snapshot") if isinstance(body.get("status_snapshot"), Mapping) else {}
        if not snapshot and isinstance(body.get("owner_worker"), Mapping):
            snapshot = body["owner_worker"]  # type: ignore[index]
        _assert_public_safe_payload(snapshot)
        report["worker"] = _sanitize_worker_status(snapshot)
        report["native_run"] = _sanitize_mapping(body.get("native_run") if isinstance(body.get("native_run"), Mapping) else {})
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
    return report


def build_capability_list_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _native_context(config=config, env=env, claim_path=claim_path, allow_default_origin=True)
    report = _base_report("capability_list", context)
    report["capabilities"] = []
    return _build_public_manifest_report(
        report,
        context,
        CAPABILITIES_PATH,
        payload_key="capabilities",
        sanitizer=_sanitize_capability,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )


def build_module_list_report(
    *,
    config: Mapping[str, object] | None = None,
    env: Mapping[str, str | None] | None = None,
    claim_path: str | None = None,
    transport: HeaderJsonTransport | None = None,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    context = _native_context(config=config, env=env, claim_path=claim_path, allow_default_origin=True)
    report = _base_report("module_list", context)
    report["modules"] = []
    return _build_public_manifest_report(
        report,
        context,
        MODULES_PATH,
        payload_key="modules",
        sanitizer=_sanitize_module,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )


def load_config_for_native_run(config_path: str | None) -> dict[str, object]:
    return load_config_for_control_spine(config_path)


def _resolve_conversation_policy(
    *,
    conversation_id: str | None,
    conversation_origin: str | None,
    sync_policy: str | None,
    conversation_policy_store: str | None,
) -> dict[str, object] | None:
    if not conversation_id and not sync_policy:
        return None
    safe_conversation_id = conversation_id or "native-run-inline"
    policy = sync_policy
    origin = conversation_origin
    if policy is None and conversation_policy_store is not None:
        stored = build_conversation_policy_list_report(store_path=conversation_policy_store)
        conversations = stored.get("conversations") if isinstance(stored.get("conversations"), list) else []
        for item in conversations:
            if not isinstance(item, Mapping):
                continue
            if item.get("conversation_id") == safe_conversation_id:
                policy = str(item.get("sync_policy") or "")
                origin = str(item.get("origin") or "")
                break
    if policy is None:
        policy = "local_only"
    if origin is None:
        origin = "cloud" if policy == "cloud_to_local" else "local"
    try:
        return build_conversation_execution_policy(
            conversation_id=safe_conversation_id,
            sync_policy=policy,
            origin=origin,
        )
    except ConversationSyncPolicyError as exc:
        raise NativeRunServiceError(exc.code, exc.message) from exc


def _conversation_policy_blocks_official_dispatch(conversation_policy: Mapping[str, object]) -> bool:
    execution = conversation_policy.get("execution") if isinstance(conversation_policy.get("execution"), Mapping) else {}
    if execution.get("execution_allowed") is False:
        return True
    return execution.get("official_worker_allowed") is False


def _conversation_policy_error(conversation_policy: Mapping[str, object]) -> dict[str, object]:
    execution = conversation_policy.get("execution") if isinstance(conversation_policy.get("execution"), Mapping) else {}
    sync_policy = _safe_text(conversation_policy.get("sync_policy"), fallback="unknown")
    code = "conversation_sync_policy_blocks_official_worker"
    message = "Conversation sync policy blocks official worker dispatch."
    if sync_policy == "local_only":
        code = "local_only_official_worker_rejected"
        message = "local_only conversations must use local loopback execution, not the official worker."
    if sync_policy == "paused":
        code = "conversation_sync_paused"
        message = "Conversation sync is paused."
    error = _safe_error(code, message, status_code=403)
    error["reason"] = _safe_text(execution.get("reason"), fallback=str(code))
    error["next_safe_command"] = "yonerai sync conversation set <conversation_id> cloud_to_local"
    return error


def _conversation_policy_payload(conversation_policy: Mapping[str, object]) -> dict[str, object]:
    return {
        "conversation_id": _safe_text(conversation_policy.get("conversation_id"), fallback="conversation"),
        "origin": _safe_text(conversation_policy.get("origin"), fallback="unknown"),
        "sync_policy": _safe_text(conversation_policy.get("sync_policy"), fallback="unknown"),
        "message_body_included": False,
        "raw_body_included": False,
        "local_absolute_paths_included": False,
        "local_private_memory_included": False,
        "provider_keys_included": False,
    }


def _effective_sync_policy(conversation_policy: Mapping[str, object] | None, requested_policy: str | None) -> str:
    if conversation_policy is not None:
        return str(_safe_text(conversation_policy.get("sync_policy"), fallback="cloud_to_local"))
    return requested_policy or "cloud_to_local"


def _provider_sharing_payload(provider_policy: Mapping[str, object]) -> dict[str, object]:
    return {
        "conversation_id": _safe_text(provider_policy.get("conversation_id"), fallback=None),
        "sync_policy": _safe_text(provider_policy.get("sync_policy"), fallback="cloud_to_local"),
        "provider_data_policy": _safe_text(provider_policy.get("provider_data_policy"), fallback="none"),
        "consent_state": _safe_text(provider_policy.get("consent_state"), fallback="not_enabled"),
        "consent_version": _safe_text(provider_policy.get("consent_version"), fallback=None),
        "openai_shared_traffic_enabled": bool(provider_policy.get("openai_shared_traffic_enabled", False)),
        "raw_body_included": False,
        "provider_key_included": False,
        "google_token_included": False,
        "local_path_included": False,
    }


def _prepare_provider_gateway_context(
    *,
    context: Mapping[str, object],
    conversation_id: str,
    safe_prompt: str,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> dict[str, object]:
    safe_conversation_id = _safe_text(conversation_id, fallback="conversation")
    encoded_conversation_id = quote(str(safe_conversation_id), safe="")
    headers = _auth_headers(context)
    message_status, message_body, message_headers = _request_json(
        "POST",
        context,
        f"/v1/conversations/{encoded_conversation_id}/messages",
        headers,
        {
            "message_text": safe_prompt,
            "privacy_class": "synthetic",
            "role": "user",
            "body_on_aws_acknowledged": True,
        },
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    if message_status >= 400:
        raise NativeRunServiceError(
            _reason_from_body("provider_message_prepare_failed", message_body),
            "Staging provider context preparation failed.",
            status_code=message_status,
        )
    preview_status, preview_body, preview_headers = _request_json(
        "POST",
        context,
        f"/v1/conversations/{encoded_conversation_id}/provider-consent/preview",
        headers,
        {"audit_reason": "Public CLI previewed staging OpenAI shared traffic consent."},
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    if preview_status >= 400:
        raise NativeRunServiceError(
            _reason_from_body("provider_consent_preview_failed", preview_body),
            "Staging provider consent preview failed.",
            status_code=preview_status,
        )
    approve_status, approve_body, approve_headers = _request_json(
        "POST",
        context,
        f"/v1/conversations/{encoded_conversation_id}/provider-consent/approve",
        headers,
        {
            "audit_reason": "Public CLI confirmed explicit staging OpenAI shared traffic consent.",
            "explicit_provider_consent": True,
            "consent_copy_acknowledged": True,
        },
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    if approve_status >= 400:
        raise NativeRunServiceError(
            _reason_from_body("provider_consent_approve_failed", approve_body),
            "Staging provider consent approval failed.",
            status_code=approve_status,
        )
    manifest_status, manifest_body, manifest_headers = _request_json(
        "GET",
        context,
        f"/v1/conversations/{encoded_conversation_id}/context-package/manifest",
        headers,
        None,
        transport=transport,
        timeout_seconds=timeout_seconds,
    )
    if manifest_status >= 400:
        raise NativeRunServiceError(
            _reason_from_body("provider_context_manifest_failed", manifest_body),
            "Staging provider context manifest failed.",
            status_code=manifest_status,
        )
    manifest = manifest_body.get("context_manifest") if isinstance(manifest_body.get("context_manifest"), Mapping) else manifest_body
    message = message_body.get("message") if isinstance(message_body.get("message"), Mapping) else {}
    return {
        "message_created": message_status in {200, 201, 202},
        "message_body_included": bool(message.get("message_body_included", False)),
        "preview_allowed": bool(preview_body.get("allowed", False)),
        "provider_traffic_allowed": bool(approve_body.get("provider_traffic_allowed", False)),
        "context_manifest": {
            "raw_content_included": bool(
                manifest.get("raw_content_included", False) if isinstance(manifest, Mapping) else False
            ),
            "included_message_count": _safe_int(
                manifest.get("included_message_count") if isinstance(manifest, Mapping) else None,
                fallback=0,
            ),
        },
        "rate_limit_headers_present": sorted(
            set(_rate_limit_headers_present(message_headers))
            | set(_rate_limit_headers_present(preview_headers))
            | set(_rate_limit_headers_present(approve_headers))
            | set(_rate_limit_headers_present(manifest_headers))
        ),
        "raw_body_included": False,
        "provider_key_included": False,
        "google_token_included": False,
    }


def _build_run_get_report(
    operation: str,
    run_id: str,
    *,
    path: str,
    config: Mapping[str, object] | None,
    env: Mapping[str, str | None] | None,
    claim_path: str | None,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> dict[str, object]:
    context = _native_context(config=config, env=env, claim_path=claim_path)
    report = _base_report(operation, context)
    report["requested_run_id"] = _safe_run_id(run_id)
    report["run"] = None
    if not _require_linked_session(report, context, "Native Run status requires staging login."):
        return report
    try:
        status_code, body, headers = _request_json(
            "GET",
            context,
            path,
            _auth_headers(context),
            None,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    _merge_response_metadata(report, status_code, headers)
    if status_code == 401:
        report["ok"] = False
        _mark_staging_session_rejected(report, body)
        report["error"] = _staging_session_rejected_error(body, status_code=status_code)
        return report
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _service_error_from_body("native_run_status_failed", body, status_code=status_code)
        return report
    try:
        _assert_public_safe_payload(body)
        report["run"] = _sanitize_run(body.get("run") if isinstance(body.get("run"), Mapping) else {})
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
    return report


def _build_public_manifest_report(
    report: dict[str, object],
    context: Mapping[str, object],
    path: str,
    *,
    payload_key: str,
    sanitizer: Callable[[Mapping[str, object]], dict[str, object]],
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> dict[str, object]:
    try:
        status_code, body, headers = _request_json(
            "GET",
            context,
            path,
            {},
            None,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
        return report
    _merge_response_metadata(report, status_code, headers)
    if status_code >= 400:
        report["ok"] = False
        report["error"] = _service_error_from_body(f"{payload_key}_failed", body, status_code=status_code)
        return report
    try:
        _assert_public_safe_payload(body)
        report["contract_version"] = _safe_text(body.get("contract_version"), fallback="unknown")
        raw_items = body.get(payload_key) if isinstance(body.get(payload_key), list) else []
        report[payload_key] = [sanitizer(item) for item in raw_items if isinstance(item, Mapping)]
    except NativeRunServiceError as exc:
        report["ok"] = False
        report["error"] = exc.to_safe_error()
    return report


def _native_context(
    *,
    config: Mapping[str, object] | None,
    env: Mapping[str, str | None] | None,
    claim_path: str | None,
    allow_default_origin: bool = True,
) -> dict[str, object]:
    context = dict(build_control_spine_context(config=config, env=env, claim_path=claim_path))
    origin = str(context.get("origin") or "").strip()
    origin_is_valid = _is_allowed_staging_origin(origin)
    if allow_default_origin and (not context.get("origin_configured") or not origin_is_valid):
        context["origin"] = DEFAULT_STAGING_CONTROL_SPINE_ORIGIN
        context["origin_configured"] = True
        context["origin_from_default"] = True
        context["origin_invalid_replaced"] = bool(origin and origin != "not_configured" and not origin_is_valid)
    else:
        context["origin_from_default"] = False
        context["origin_invalid_replaced"] = bool(origin and origin != "not_configured" and not origin_is_valid)
    return context


def _base_report(operation: str, context: Mapping[str, object]) -> dict[str, object]:
    session_claim = context.get("session_claim") if isinstance(context.get("session_claim"), Mapping) else {}
    return {
        "schema_version": NATIVE_RUN_CLIENT_SCHEMA_VERSION,
        "contract_version": NATIVE_RUN_CONTRACT_VERSION,
        "ok": True,
        "operation": operation,
        "staging_only": True,
        "backend_url": _safe_text(context.get("origin"), fallback=DEFAULT_STAGING_CONTROL_SPINE_ORIGIN),
        "staging_origin_configured": bool(context.get("origin_configured")),
        "origin_from_default": bool(context.get("origin_from_default")),
        "origin_invalid_replaced": bool(context.get("origin_invalid_replaced")),
        "auth_state": _safe_text(context.get("auth_state"), fallback="unauthenticated"),
        "account_linked": bool(context.get("account_linked")),
        "session_available": bool(context.get("session_available")),
        "session_expires_at": _safe_text(session_claim.get("expires_at"), fallback=None),
        "official_backend_called": False,
        "production_cloud_runtime_enabled": False,
        "production_oracle_enabled": False,
        "production_login_enabled": False,
        "google_token_stored": False,
        "refresh_token_stored": False,
        "provider_key_stored": False,
        "openai_shared_traffic_enabled": False,
        "local_private_auto_upload_enabled": False,
        "raw_private_file_bytes_sent": False,
        "raw_chain_of_thought_included": False,
        "actions_not_performed": [
            "no production Google login",
            "no Google token storage",
            "no refresh token storage",
            "no provider key upload",
            "no OpenAI shared traffic",
            "no arbitrary shell/file/tool execution",
            "no local private auto-upload",
            "no raw private file bytes",
            "no production Oracle/cloud runtime",
        ],
        "next_safe_commands": [
            "yonerai login",
            "yonerai run submit \"hello\"",
            "yonerai run status <run_id>",
            "yonerai run events <run_id>",
            "yonerai run result <run_id>",
        ],
    }


def _require_linked_session(report: dict[str, object], context: Mapping[str, object], message: str) -> bool:
    if bool(context.get("account_linked")) and bool(context.get("session_available")):
        return True
    report["ok"] = False
    report["error"] = _auth_required_error(message)
    return False


def _mark_staging_session_rejected(report: dict[str, object], body: Mapping[str, object] | None = None) -> None:
    report["auth_state"] = "staging_session_rejected"
    report["account_linked"] = False
    report["session_available"] = False
    report["staging_session_rejected"] = True
    report["session_repair_action"] = "yonerai logout && yonerai login"
    report["session_rejected_reason"] = _reason_from_body("staging_session_rejected", body or {})


def _request_json(
    method: str,
    context: Mapping[str, object],
    path: str,
    headers: Mapping[str, str],
    body: Mapping[str, object] | None,
    *,
    transport: HeaderJsonTransport | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    origin = str(context.get("origin") or DEFAULT_STAGING_CONTROL_SPINE_ORIGIN).rstrip("/")
    url = f"{origin}{path}"
    caller = transport or _default_header_json_transport
    status_code, payload, response_headers = caller(method, url, dict(headers), body, timeout_seconds)
    return status_code, payload, response_headers


def _auth_headers(context: Mapping[str, object]) -> dict[str, str]:
    token = context.get("session_token")
    if not isinstance(token, str) or not token.strip():
        return {}
    return {"Authorization": f"Bearer {token}"}


def _default_header_json_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Mapping[str, object] | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, object], Mapping[str, str]]:
    data = None if body is None else json.dumps(dict(body)).encode("utf-8")
    try:
        request = Request(url, data=data, method=method.upper())
    except ValueError as exc:
        raise NativeRunServiceError("native_run_invalid_origin", "Staging Native Run origin is invalid.") from exc
    request.add_header("Accept", "application/json")
    for key, value in headers.items():
        request.add_header(key, value)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - staging origin is controlled by validated config/session.
            return int(response.status), _read_json_body(response.read()), dict(response.headers)
    except HTTPError as exc:
        if 300 <= int(exc.code) < 400:
            raise NativeRunServiceError(
                "native_run_redirect_forbidden",
                "Staging Native Run source attempted to redirect.",
                status_code=int(exc.code),
            ) from exc
        try:
            return int(exc.code), _read_json_body(exc.read()), dict(exc.headers)
        except NativeRunServiceError:
            return int(exc.code), {}, dict(exc.headers)
    except (OSError, URLError) as exc:
        raise NativeRunServiceError("native_run_unreachable", "Staging Native Run source is unreachable.") from exc


def _read_json_body(raw: bytes) -> Mapping[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NativeRunServiceError("native_run_invalid_json", "Staging Native Run source returned invalid JSON.") from exc
    if not isinstance(value, dict):
        raise NativeRunServiceError("native_run_invalid_json", "Staging Native Run source returned invalid JSON.")
    return value


def _is_allowed_staging_origin(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.path not in {"", "/"}:
        return False
    if host in {"localhost", "127.0.0.1", "::1"}:
        return parsed.scheme in {"http", "https"}
    if host not in {"api-staging.yonerai.com", "staging.yonerai.com"}:
        return False
    return parsed.scheme == "https" and parsed.port is None


def _merge_response_metadata(report: dict[str, object], status_code: int, headers: Mapping[str, str]) -> None:
    report["official_backend_called"] = True
    report["backend_status_code"] = status_code
    report["rate_limit_headers_present"] = _rate_limit_headers_present(headers)


def _sanitize_run(run: Mapping[str, object]) -> dict[str, object]:
    error = run.get("error") if isinstance(run.get("error"), Mapping) else {}
    capabilities = run.get("capability_requirements") if isinstance(run.get("capability_requirements"), list) else []
    return {
        "run_id": _safe_text(run.get("run_id"), fallback="run-redacted"),
        "project_id": _safe_text(run.get("project_id"), fallback="project-redacted"),
        "module_id": _safe_text(run.get("module_id"), fallback="module-redacted"),
        "capability_requirements": [_safe_text(item, fallback="capability:redacted") for item in capabilities],
        "privacy_class": _safe_text(run.get("privacy_class"), fallback="unknown"),
        "approval_state": _safe_text(run.get("approval_state"), fallback="unknown"),
        "status": _safe_text(run.get("status"), fallback="unknown"),
        "created_at": _safe_text(run.get("created_at"), fallback=None),
        "updated_at": _safe_text(run.get("updated_at"), fallback=None),
        "retry_count": run.get("retry_count") if isinstance(run.get("retry_count"), int) else 0,
        "timeout_seconds": run.get("timeout_seconds") if isinstance(run.get("timeout_seconds"), int) else None,
        "result_ref": _safe_text(run.get("result_ref"), fallback=None),
        "result_summary": _safe_text(run.get("result_summary"), fallback=None),
        "error": _sanitize_mapping(error),
        "provider_call_enabled": bool(run.get("provider_call_enabled", False)),
        "aws_heavy_execution_enabled": bool(run.get("aws_heavy_execution_enabled", False)),
        "raw_local_content_included": bool(run.get("raw_local_content_included", False)),
        "worker_delivery": _safe_text(run.get("worker_delivery"), fallback="outbound_polling_only"),
        "contract_version": _safe_text(run.get("contract_version"), fallback=NATIVE_RUN_CONTRACT_VERSION),
    }


def _sanitize_queue(queue: Mapping[str, object]) -> dict[str, object]:
    return {
        "backend": _safe_text(queue.get("backend"), fallback="unknown"),
        "status": _safe_text(queue.get("status"), fallback="unknown"),
        "lease_semantics": _safe_text(queue.get("lease_semantics"), fallback="unknown"),
        "retry_count": queue.get("retry_count") if isinstance(queue.get("retry_count"), int) else 0,
        "timeout_seconds": queue.get("timeout_seconds") if isinstance(queue.get("timeout_seconds"), int) else None,
        "worker_delivery": _safe_text(queue.get("worker_delivery"), fallback="outbound_polling_only"),
        "sqs_migration": _safe_text(queue.get("sqs_migration"), fallback="not_enabled"),
    }


def _sanitize_event(event: Mapping[str, object]) -> dict[str, object]:
    return {
        "event_id": _safe_text(event.get("event_id"), fallback="event-redacted"),
        "run_id": _safe_text(event.get("run_id"), fallback="run-redacted"),
        "project_id": _safe_text(event.get("project_id"), fallback="project-redacted"),
        "type": _safe_text(event.get("type") or event.get("event_type"), fallback="event"),
        "status": _safe_text(event.get("status"), fallback="unknown"),
        "summary": _safe_text(event.get("summary"), fallback="sanitized event"),
        "created_at": _safe_text(event.get("created_at"), fallback=None),
        "contract_version": _safe_text(event.get("contract_version"), fallback=NATIVE_RUN_CONTRACT_VERSION),
        "raw_prompt_logged": bool(event.get("raw_prompt_logged", False)),
        "raw_file_content_logged": bool(event.get("raw_file_content_logged", False)),
        "provider_key_logged": bool(event.get("provider_key_logged", False)),
    }


def _sanitize_worker_status(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {
        "official_execution_worker": _safe_text(
            snapshot.get("official_execution_worker") or snapshot.get("status"),
            fallback="unknown",
        ),
        "queue": _safe_text(snapshot.get("queue") or snapshot.get("connectivity"), fallback="unknown"),
        "queued_runs": snapshot.get("queued_runs") if isinstance(snapshot.get("queued_runs"), int) else 0,
        "claimed_runs": snapshot.get("claimed_runs") if isinstance(snapshot.get("claimed_runs"), int) else 0,
        "completed_runs": snapshot.get("completed_runs") if isinstance(snapshot.get("completed_runs"), int) else 0,
        "worker_delivery": _safe_text(snapshot.get("worker_delivery") or snapshot.get("connectivity"), fallback="outbound_polling_only"),
        "inbound_owner_pc_ports_required": bool(snapshot.get("inbound_owner_pc_ports_required", False)),
        "raw_local_content_included": bool(snapshot.get("raw_local_content_included", False)),
        "provider_execution_in_aws": bool(snapshot.get("provider_execution_in_aws", False)),
        "contract_version": _safe_text(snapshot.get("contract_version"), fallback="unknown"),
    }


def _sanitize_capability(item: Mapping[str, object]) -> dict[str, object]:
    return {
        "capability_id": _safe_text(item.get("capability_id") or item.get("name"), fallback="capability:redacted"),
        "module_id": _safe_text(item.get("module_id"), fallback="run.core"),
        "privacy_class": _safe_text(item.get("privacy_class"), fallback="metadata_only"),
        "provider_call_enabled": bool(item.get("provider_call_enabled", False)),
        "requires_worker": bool(item.get("requires_worker", False)),
        "worker_delivery": _safe_text(item.get("worker_delivery"), fallback="outbound_polling_only"),
    }


def _sanitize_module(item: Mapping[str, object]) -> dict[str, object]:
    capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), list) else []
    events = item.get("events") if isinstance(item.get("events"), list) else []
    return {
        "module_id": _safe_text(item.get("module_id"), fallback="module:redacted"),
        "capabilities": [_safe_text(value, fallback="capability:redacted") for value in capabilities],
        "api_surface": _safe_text(item.get("api_surface"), fallback="unknown"),
        "events": [_safe_text(value, fallback="event:redacted") for value in events],
        "public_exposure": bool(item.get("public_exposure", False)),
        "compatibility_adapter": _safe_text(item.get("compatibility_adapter"), fallback=None),
    }


def _sanitize_mapping(payload: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in payload.items():
        safe_key = _safe_text(key, fallback="field")
        if isinstance(value, Mapping):
            sanitized[str(safe_key)] = _sanitize_mapping(value)
        elif isinstance(value, list):
            sanitized[str(safe_key)] = [
                _sanitize_mapping(item) if isinstance(item, Mapping) else _safe_text(item, fallback="redacted")
                for item in value[:20]
            ]
        elif isinstance(value, bool):
            sanitized[str(safe_key)] = value
        elif isinstance(value, int):
            sanitized[str(safe_key)] = value
        else:
            sanitized[str(safe_key)] = _safe_text(value, fallback=None)
    return sanitized


def _assert_public_safe_payload(payload: object) -> None:
    forbidden_value_markers = (
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "staging_session_token",
        "api_key",
        "password",
        "c:\\users",
        "\\\\",
        "/users/",
        "/home/",
        "/root/",
        "http://10.",
        "http://192.168.",
        "http://127.",
        "169.254.169.254",
    )
    sensitive_key_markers = (
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "staging_session_token",
        "api_key",
        "password",
    )

    def reject() -> None:
        raise NativeRunServiceError(
            "native_run_private_payload_rejected",
            "Staging Native Run source returned non-public fields.",
        )

    def safe_negative_marker(value: object) -> bool:
        if value is False or value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in {"", "false", "no", "none", "not_included", "redacted"}
        return False

    def walk(value: object, key: str = "") -> None:
        lowered_key = key.lower()
        if any(marker in lowered_key for marker in sensitive_key_markers) and not safe_negative_marker(value):
            reject()
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                walk(child_value, str(child_key))
            return
        if isinstance(value, list):
            for child in value:
                walk(child, key)
            return
        if isinstance(value, str):
            lowered = value.lower()
            if any(marker in lowered for marker in forbidden_value_markers):
                reject()

    walk(payload)


def _safe_text(value: object, *, fallback: object, max_length: int = 240) -> object:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text:
        return fallback
    lowered = text.lower()
    forbidden = (
        "access_token",
        "refresh_token",
        "id_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "staging_session_token",
        "api_key",
        "password",
        "c:\\users",
        "\\\\",
        "/users/",
        "/home/",
        "/root/",
    )
    if any(marker in lowered for marker in forbidden):
        return fallback
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        return fallback
    return text[:max_length]


def _safe_prompt(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise NativeRunServiceError("native_run_prompt_required", "Native Run prompt is required.")
    if len(text) > 800:
        raise NativeRunServiceError("native_run_prompt_too_long", "Native Run prompt is too long for staging preview.")
    lowered = text.lower()
    forbidden = (
        "access_token",
        "refresh_token",
        "client_secret",
        "authorization_code",
        "google_token",
        "api_key",
        "password=",
        "c:\\users",
        "\\\\",
        "/users/",
        "/home/",
        "/root/",
    )
    if any(marker in lowered for marker in forbidden):
        raise NativeRunServiceError("native_run_prompt_rejected", "Native Run prompt looks private or secret-like.")
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise NativeRunServiceError("native_run_prompt_rejected", "Native Run prompt contains unsupported control characters.")
    return text


def _safe_run_id(value: object) -> str:
    text = str(value or "").strip()
    if not RUN_ID_RE.fullmatch(text):
        raise NativeRunServiceError("native_run_id_invalid", "Native Run id is invalid.")
    return text


def _safe_project_id(value: object) -> str:
    text = str(value or "").strip()
    if not PROJECT_ID_RE.fullmatch(text):
        raise NativeRunServiceError("native_run_project_id_invalid", "Native Run project id is invalid.")
    return text


def _safe_module_id(value: object) -> str:
    text = str(value or "").strip()
    if not MODULE_ID_RE.fullmatch(text):
        raise NativeRunServiceError("native_run_module_id_invalid", "Native Run module id is invalid.")
    return text


def _safe_capability(value: object) -> str:
    text = str(value or "").strip()
    if not CAPABILITY_RE.fullmatch(text):
        raise NativeRunServiceError("native_run_capability_invalid", "Native Run capability is invalid.")
    return text


def _safe_idempotency_key(value: object) -> str:
    text = str(value or "").strip()
    if not RUN_ID_RE.fullmatch(text):
        raise NativeRunServiceError("native_run_idempotency_key_invalid", "Native Run idempotency key is invalid.")
    return text


def _service_error_from_body(code: str, body: Mapping[str, object], *, status_code: int) -> dict[str, object]:
    detail = body.get("detail") if isinstance(body.get("detail"), Mapping) else body
    reason = _safe_text(detail.get("reason") if isinstance(detail, Mapping) else None, fallback=code)
    return _safe_error(str(reason or code), "Staging Native Run request failed.", status_code=status_code)


def _reason_from_body(code: str, body: Mapping[str, object]) -> str:
    detail = body.get("detail") if isinstance(body.get("detail"), Mapping) else body
    return str(_safe_text(detail.get("reason") if isinstance(detail, Mapping) else None, fallback=code))


def _safe_int(value: object, *, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return fallback


def _safe_error(code: str, message: str, *, status_code: int | None = None) -> dict[str, object]:
    return {
        "code": code,
        "message": message,
        "status_code": status_code,
        "private_endpoint_printed": False,
        "local_path_printed": False,
        "token_printed": False,
        "google_token_printed": False,
        "provider_key_printed": False,
    }


def _auth_required_error(message: str, *, status_code: int | None = None) -> dict[str, object]:
    error = _safe_error("staging_auth_required", message, status_code=status_code)
    error["next_safe_command"] = "yonerai login"
    return error


def _staging_session_rejected_error(body: Mapping[str, object], *, status_code: int) -> dict[str, object]:
    error = _safe_error(
        "staging_session_rejected",
        "Saved staging session was rejected by the staging backend. Run `yonerai logout` and then `yonerai login`.",
        status_code=status_code,
    )
    error["backend_reason"] = _reason_from_body("staging_session_rejected", body)
    error["next_safe_command"] = "yonerai login"
    error["repair_command"] = "yonerai logout && yonerai login"
    return error


def _rate_limit_headers_present(headers: Mapping[str, str]) -> list[str]:
    expected = {
        "x-yonerai-ratelimit-scope": "X-YonerAI-RateLimit-Scope",
        "x-yonerai-ratelimit-limit": "X-YonerAI-RateLimit-Limit",
        "x-yonerai-ratelimit-remaining": "X-YonerAI-RateLimit-Remaining",
        "x-yonerai-ratelimit-reset": "X-YonerAI-RateLimit-Reset",
        "x-yonerai-ratelimit-reason": "X-YonerAI-RateLimit-Reason",
    }
    normalized = {key.lower() for key in headers}
    return [public for key, public in expected.items() if key in normalized]


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)
