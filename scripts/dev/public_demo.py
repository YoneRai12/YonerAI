from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import importlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


_PUBLIC_ENV_KEYS = (
    "ORA_ALLOW_MISSING_SECRETS",
    "ORA_BOT_DB",
    "ORA_DOTENV_PATH",
    "DISCORD_TOKEN",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ORA_CORE_API_TOKEN",
    "ORA_LOCAL_LLM_BASE_URL",
    "ORA_LOCAL_LLM_ENABLED",
    "ORA_LOCAL_LLM_PUBLIC_TOKEN",
)
_PRIVATE_MARKERS = (
    re.compile(r"[A-Za-z]:[\\/]+[^\s\"'<>|]+", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'=])/(root|etc|home|users|var|tmp)/", re.IGNORECASE),
    re.compile(
        r"(api[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret|google[_-]?client[_-]?secret|authorization)",
        re.IGNORECASE,
    ),
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
_PUBLIC_CREDENTIAL_ENV_KEYS = (
    "DISCORD_TOKEN",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ORA_CORE_API_TOKEN",
    "ORA_LOCAL_LLM_BASE_URL",
    "ORA_LOCAL_LLM_ENABLED",
    "ORA_LOCAL_LLM_PUBLIC_TOKEN",
    "YONERAI_OPENAI_COMPATIBLE_API_KEY",
    "YONERAI_OPENAI_COMPATIBLE_BASE_URL",
    "YONERAI_OPENAI_COMPATIBLE_LIVE",
    "YONERAI_OPENAI_COMPATIBLE_MODEL",
    "YONERAI_ANTHROPIC_API_KEY",
    "YONERAI_GEMINI_API_KEY",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prepare_import_path() -> None:
    root = _repo_root()
    core_src = root / "core" / "src"
    cli_src = root / "clients" / "cli"
    for path in (root, core_src, cli_src):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _prepare_public_env() -> None:
    os.environ["ORA_ALLOW_MISSING_SECRETS"] = "1"
    os.environ["ORA_BOT_DB"] = "sqlite+aiosqlite:///:memory:"
    os.environ["ORA_DOTENV_PATH"] = str(_repo_root() / ".codex-public-demo-missing.env")
    for key in _PUBLIC_CREDENTIAL_ENV_KEYS:
        os.environ.pop(key, None)


def _clear_public_runtime_modules() -> None:
    for name in list(sys.modules):
        if name == "ora_core" or name.startswith("ora_core.") or name in {"src.config"} or name.startswith("src.web."):
            sys.modules.pop(name, None)


def _fresh_core_app() -> Any:
    _prepare_import_path()
    _prepare_public_env()
    _clear_public_runtime_modules()
    with redirect_stdout(io.StringIO()):
        main_mod = importlib.import_module("ora_core.main")
    from ora_core.api.routes.agent_runs import reset_surface_agent_run_store
    from ora_core.sessions import reset_public_conversation_session_store

    reset_surface_agent_run_store()
    reset_public_conversation_session_store()
    return main_mod.app


def _assert_json_response(response: Any, *, endpoint: str) -> dict[str, Any]:
    body = response.json()
    if not isinstance(body, dict):
        raise AssertionError(f"{endpoint} returned non-object JSON")
    return body


def _find_run_event(run: object, event_name: str) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    events = run.get("events", ())
    if not isinstance(events, list):
        return None
    for event in events:
        if isinstance(event, dict) and event.get("name") == event_name:
            return event
    return None


def _public_core_checks() -> tuple[dict[str, object], ...]:
    app = _fresh_core_app()
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        health = client.get("/health")
        health_body = _assert_json_response(health, endpoint="/health")
        message = client.post(
            "/v1/public/messages",
            json={"message": "hello YonerAI demo", "mode": "mock", "conversation_id": "public-demo"},
        )
        message_body = _assert_json_response(message, endpoint="/v1/public/messages")
        run = client.post(
            "/api/v1/agent/run",
            json={"prompt": "hello YonerAI demo", "mode": "mock", "conversation_id": "public-demo"},
        )
        run_body = _assert_json_response(run, endpoint="/api/v1/agent/run")

    assert health.status_code == 200 and health_body.get("ok") is True
    assert message.status_code == 200 and message_body.get("provider") == "offline-mock"
    assert message_body.get("memory_persisted") is False
    assert run.status_code == 200 and run_body.get("status") == "completed"
    assert run_body.get("provider") == "offline-mock"
    assert run_body.get("memory_persisted") is False
    return (
        {"name": "health", "status": "ok", "endpoint": "/health"},
        {
            "name": "mock_message",
            "status": "ok",
            "endpoint": "/v1/public/messages",
            "provider": "offline-mock",
            "memory_persisted": False,
        },
        {
            "name": "run_contract",
            "status": "ok",
            "endpoint": "/api/v1/agent/run",
            "provider": "offline-mock",
            "memory_persisted": False,
        },
    )


def _mode_boundary_checks() -> tuple[dict[str, object], ...]:
    from ora_core.three_mode import build_three_mode_capability_surface

    modes = build_three_mode_capability_surface()["modes"]
    self_host = modes["full_private_self_host"]
    hybrid = modes["official_hybrid_private"]
    managed = modes["official_managed_cloud"]
    assert self_host["public_repo_support_status"] == "public_local_supported"
    assert hybrid["public_repo_support_status"] == "local_node_contract_and_dev_simulator"
    assert managed["public_repo_support_status"] == "contract_only"
    assert managed["runtime_available_in_public_repo"] is False
    return (
        {"name": "self_host", "status": "ok", "public_repo_support": "public_local_supported"},
        {
            "name": "hybrid_private",
            "status": "ok",
            "public_repo_support": "local_node_contract_and_dev_simulator_supported",
        },
        {
            "name": "managed_cloud",
            "status": "ok",
            "public_repo_support": "official_private_external_contract_only",
            "runtime_available_in_public_repo": False,
        },
    )


def _route_preview_checks() -> tuple[dict[str, object], ...]:
    from ora_core.route_preview import preview_route

    public_docs = preview_route("summarize public docs", mode="official_managed_cloud")
    private_file = preview_route(
        "read my local file",
        mode="official_hybrid_private",
        requested_capability="private_files",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("private_files",),
        require_enrolled_verified_session=True,
        session_verification_state="enrolled_verified",
    )
    dangerous_shell = preview_route(
        "run shell command",
        mode="official_hybrid_private",
        requested_capability="dangerous_operations",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("dangerous_operations",),
        require_enrolled_verified_session=True,
        session_verification_state="enrolled_verified",
        risk_hint="dangerous",
    )
    assert public_docs.route == "managed_cloud_contract_only"
    assert private_file.route == "hybrid_coordination_preview"
    assert private_file.session_verified is True
    assert dangerous_shell.approval_required is True
    return (
        {"name": "public_docs_task", "status": "ok", "route": public_docs.route},
        {
            "name": "private_local_file_task",
            "status": "ok",
            "route": private_file.route,
            "session_verified": private_file.session_verified,
        },
        {
            "name": "dangerous_shell_task",
            "status": "ok",
            "route": dangerous_shell.route,
            "approval_required": dangerous_shell.approval_required,
        },
    )


def _provider_planner_checks() -> tuple[dict[str, object], ...]:
    from ora_core.planning import build_execution_plan
    from ora_core.planning.execution_plan import preview_mock_provider_response
    from ora_core.providers import build_default_provider_registry, build_provider_setup_report
    from ora_core.search import MockSearchAdapter, SearchRequest, build_live_search_disabled_boundary

    registry = build_default_provider_registry()
    statuses = {status["provider_id"]: status for status in registry.list_statuses()}
    provider_setup = build_provider_setup_report(registry=registry)
    setup_by_provider = {
        str(provider["provider_id"]): provider
        for provider in provider_setup["providers"]
        if isinstance(provider, dict) and provider.get("provider_id")
    }
    mock_response = preview_mock_provider_response("hello YonerAI provider planner demo")
    search_results = MockSearchAdapter().search(SearchRequest(query="YonerAI alpha2 capability slice"))
    live_search_boundary = build_live_search_disabled_boundary("YonerAI alpha2 capability slice")
    public_plan = build_execution_plan("summarize public docs", mode="hybrid").to_public_dict()
    coding_plan = build_execution_plan("fix this Python test", mode="hybrid", provider="openai-compatible").to_public_dict()
    private_plan = build_execution_plan("read my local file", mode="hybrid").to_public_dict()
    dangerous_plan = build_execution_plan("delete file and run shell command", mode="hybrid").to_public_dict()
    download_plan = build_execution_plan("download https://example.com/not-managed.bin", mode="hybrid").to_public_dict()

    assert statuses["mock"]["available"] is True
    assert statuses["openai-compatible"]["available"] is False
    assert "anthropic" in statuses and "gemini" in statuses
    assert provider_setup["network_probe_performed"] is False
    assert setup_by_provider["local"]["loopback_only"] is True
    assert "set YONERAI_OPENAI_COMPATIBLE_BASE_URL" in setup_by_provider["openai-compatible"]["setup_blockers"]
    assert mock_response["provider"] == "mock"
    assert search_results and search_results[0].source == "mock"
    assert live_search_boundary["network_performed"] is False
    assert live_search_boundary["reason"] == "live_search_not_implemented"
    assert public_plan["classification"]["category"] == "summarize_public"
    assert public_plan["side_effects"]["provider_call"] is False
    assert coding_plan["classification"]["category"] == "coding"
    assert private_plan["provider"]["local_node_required"] is True
    assert dangerous_plan["approval"]["required"] is True
    assert download_plan["safety_checks"]["managed_download_guard"]["network_performed"] is False
    return (
        {
            "name": "provider_registry",
            "status": "ok",
            "provider": "mock",
            "provider_status": "available",
            "external_provider_configured": statuses["openai-compatible"]["configured"],
            "external_provider_available": statuses["openai-compatible"]["available"],
            "live_call_performed": False,
        },
        {
            "name": "external_provider_availability",
            "status": "ok",
            "openai_compatible": statuses["openai-compatible"]["available"],
            "anthropic": statuses["anthropic"]["available"],
            "gemini": statuses["gemini"]["available"],
            "live_call_performed": False,
        },
        {
            "name": "provider_setup_blockers",
            "status": "ok",
            "local_provider_available": setup_by_provider["local"]["available"],
            "local_provider_blockers": ",".join(str(item) for item in setup_by_provider["local"]["setup_blockers"]),
            "local_loopback_only": setup_by_provider["local"]["loopback_only"],
            "openai_compatible_live_ready": setup_by_provider["openai-compatible"]["live_ready"],
            "openai_compatible_blockers": ",".join(
                str(item) for item in setup_by_provider["openai-compatible"]["setup_blockers"]
            ),
            "network_probe_performed": provider_setup["network_probe_performed"],
            "live_call_performed": provider_setup["live_call_performed"],
        },
        {
            "name": "provider_runtime_e2e_fixtures",
            "status": "ok",
            "openai_compatible": "local_mock_http_server_tested",
            "local_llm": "loopback_mock_http_server_tested",
            "run_ledger": "redacted_success_and_error_paths_tested",
            "network_probe_performed": False,
            "live_call_performed": False,
            "external_network_call_performed": False,
        },
        {
            "name": "mock_provider_response",
            "status": "ok",
            "provider": mock_response["provider"],
            "model": mock_response["model"],
            "deterministic": mock_response["deterministic"],
            "live_call_performed": False,
        },
        {
            "name": "public_summarize_plan",
            "status": "ok",
            "task_category": public_plan["classification"]["category"],
            "risk": public_plan["risk"],
            "provider": public_plan["provider"]["provider_id"],
            "model_tier": public_plan["model"]["tier"],
            "execution_surface": public_plan["estimated_execution_surface"],
            "execution_performed": public_plan["execution_performed"],
        },
        {
            "name": "coding_plan",
            "status": "ok",
            "task_category": coding_plan["classification"]["category"],
            "model_tier": coding_plan["model"]["tier"],
            "provider": coding_plan["provider"]["provider_id"],
            "provider_status": "available" if coding_plan["provider"]["provider_available"] else "unavailable",
            "disabled_reason": ",".join(coding_plan["disabled_reasons"]),
        },
        {
            "name": "private_file_plan",
            "status": "ok",
            "task_category": private_plan["classification"]["category"],
            "local_node_required": private_plan["provider"]["local_node_required"],
            "approval_required": private_plan["approval"]["required"],
            "execution_surface": private_plan["estimated_execution_surface"],
        },
        {
            "name": "dangerous_shell_plan",
            "status": "ok",
            "task_category": dangerous_plan["classification"]["category"],
            "approval_required": dangerous_plan["approval"]["required"],
            "guard": "mcp_deny_policy",
            "execution_performed": dangerous_plan["execution_performed"],
        },
        {
            "name": "download_guard_plan",
            "status": "ok",
            "guard": "managed_download_guard",
            "network_performed": download_plan["safety_checks"]["managed_download_guard"]["network_performed"],
            "download_performed": download_plan["safety_checks"]["managed_download_guard"]["download_performed"],
            "execution_performed": download_plan["execution_performed"],
        },
        {
            "name": "mock_web_search",
            "status": "ok",
            "adapter": "mock",
            "result_count": len(search_results),
            "network_performed": False,
        },
        {
            "name": "live_search_boundary",
            "status": "ok",
            "adapter": "live",
            "reason": live_search_boundary["reason"],
            "network_performed": live_search_boundary["network_performed"],
            "requires_explicit_live_provider": live_search_boundary["requires_explicit_live_provider"],
            "actions_not_performed": ",".join(str(action) for action in live_search_boundary["actions_not_performed"]),
        },
    )


def _execution_spine_checks() -> tuple[dict[str, object], ...]:
    from ora_core.execution import (
        FileRunLedger,
        InMemoryRunLedger,
        execute_task,
        legacy_text_normalizer_status,
        normalize_legacy_generated_text,
    )
    from ora_core.execution.workspace_files import (
        build_workspace_file_access_event,
        build_workspace_file_prompt,
        read_workspace_text_file,
    )
    from ora_core.memory import LocalMemoryStore
    from ora_core.providers import build_default_provider_registry
    import tempfile

    ledger = InMemoryRunLedger()
    mock_result = execute_task(
        "summarize public docs",
        mode="self-host",
        provider="mock",
        ledger=ledger,
    ).to_public_dict()
    dangerous_result = execute_task(
        "delete file and run shell command",
        mode="hybrid",
        provider="mock",
        ledger=ledger,
    ).to_public_dict()
    registry_statuses = {status["provider_id"]: status for status in build_default_provider_registry().list_statuses()}
    legacy_status = legacy_text_normalizer_status()
    cleaned_legacy_text = normalize_legacy_generated_text("<|final|>demo")

    assert mock_result["ok"] is True
    assert mock_result["response"]["provider"] == "mock"
    assert mock_result["run"]["status"] == "completed"
    assert mock_result["run"]["persistence"]["raw_prompt_persisted"] is False
    assert dangerous_result["ok"] is False
    assert dangerous_result["run"]["status"] == "blocked"
    assert dangerous_result["error"]["code"] == "approval_required"
    assert legacy_status["execution_spine_connected"] is True
    assert cleaned_legacy_text == "demo"
    with tempfile.TemporaryDirectory(prefix="yonerai-demo-workspace-") as temp_dir:
        temp_root = Path(temp_dir)
        workspace = temp_root / "workspace"
        workspace.mkdir()
        (workspace / "note.txt").write_text("public alpha2 notes", encoding="utf-8")
        file_context = read_workspace_text_file("note.txt", workspace=workspace)
        file_ledger = FileRunLedger(temp_root / "runs.jsonl")
        file_result = execute_task(
            "summarize this file",
            provider_prompt=build_workspace_file_prompt("summarize this file", file_context),
            mode="self-host",
            provider="mock",
            ledger=file_ledger,
            context_events=(build_workspace_file_access_event(file_context),),
        ).to_public_dict()
        persisted_file_run = FileRunLedger(temp_root / "runs.jsonl").get_run(str(file_result["run"]["run_id"]))
        workspace_event = _find_run_event(file_result["run"], "workspace_file_access")
        ledger_text = (temp_root / "runs.jsonl").read_text(encoding="utf-8")
    assert file_result["ok"] is True
    assert file_result["response"]["model"] == "mock-workspace-file-summary"
    assert file_result["run"]["status"] == "completed"
    assert persisted_file_run is not None, "workspace file run was not persisted"
    assert workspace_event is not None, "workspace file access event missing from demo run"
    assert workspace_event["status"] == "ok"
    assert "raw_content_persisted=false" in workspace_event["summary"]
    assert "public alpha2 notes" not in json.dumps(file_result)
    assert "public alpha2 notes" not in ledger_text
    with tempfile.TemporaryDirectory(prefix="yonerai-demo-memory-") as temp_dir:
        memory_store = LocalMemoryStore(Path(temp_dir) / "memory.jsonl")
        memory_record = memory_store.add("demo memory sk-" + ("A" * 24), tags=("alpha2",))
        memory_count = len(memory_store.list())
    assert "sk-" not in memory_record.text
    return (
        {
            "name": "mock_provider_execution",
            "status": "ok",
            "provider": mock_result["response"]["provider"],
            "run_id": mock_result["run"]["run_id"],
            "run_status": mock_result["run"]["status"],
            "live_call_performed": mock_result["live_call_performed"],
            "raw_prompt_persisted": mock_result["run"]["persistence"]["raw_prompt_persisted"],
        },
        {
            "name": "dangerous_task_blocked",
            "status": "ok",
            "run_status": dangerous_result["run"]["status"],
            "approval_required": dangerous_result["run"]["approval_required"],
            "error": dangerous_result["error"]["code"],
        },
        {
            "name": "workspace_file_provider_execution",
            "status": "ok",
            "provider": file_result["response"]["provider"],
            "model": file_result["response"]["model"],
            "run_id": file_result["run"]["run_id"],
            "run_status": file_result["run"]["status"],
            "ledger_file_backed": True,
            "workspace_file_access_event": True,
            "raw_content_persisted": False,
            "raw_prompt_persisted": file_result["run"]["persistence"]["raw_prompt_persisted"],
            "live_call_performed": file_result["live_call_performed"],
        },
        {
            "name": "local_provider_registry",
            "status": "ok",
            "provider": "local",
            "configured": registry_statuses["local"]["configured"],
            "available": registry_statuses["local"]["available"],
            "loopback_only": True,
        },
        {
            "name": "legacy_ora_text_normalizer",
            "status": "ok",
            "source": legacy_status["source"],
            "execution_spine_connected": legacy_status["execution_spine_connected"],
            "broad_ora_refactor": legacy_status["broad_ora_refactor"],
        },
        {
            "name": "search_tool_boundaries",
            "status": "ok",
            "web_search": mock_result["boundary_checks"]["web_search"]["status"],
            "tool_boundary": mock_result["boundary_checks"]["tool_boundary"]["status"],
            "ora_tool_schema_boundary": mock_result["boundary_checks"]["ora_tool_schema_boundary"]["status"],
            "ora_guardrail_response_interpreter": mock_result["boundary_checks"]["ora_guardrail_response_interpreter"][
                "status"
            ],
            "guardrail_provider_call_performed": mock_result["boundary_checks"]["ora_guardrail_response_interpreter"][
                "provider_call_performed"
            ],
            "live_tool_execution": False,
            "network_performed": False,
        },
        {
            "name": "local_memory_opt_in",
            "status": "ok",
            "cloud_synced": False,
            "raw_prompt_persisted": False,
            "record_count": memory_count,
        },
    )


def _hybrid_trust_checks() -> tuple[dict[str, object], ...]:
    from ora_core.hybrid import (
        InMemoryNonceStore,
        LocalNodeEnrollmentRequest,
        action_args_hash,
        build_local_dev_enrolled_session_fixture,
        build_test_local_node_manifest,
        build_unsigned_local_node_action_envelope,
        consume_pairing_code,
        create_pairing_challenge,
        evaluate_local_dev_session_binding,
        generate_test_local_node_keypair,
        sign_local_node_action_envelope,
        sign_local_node_manifest,
        verify_local_node_action_envelope,
    )
    from ora_core.hybrid.local_dev_control_plane import build_local_dev_control_plane_status

    now = datetime(2026, 5, 21, 0, 5, tzinfo=timezone.utc)
    session, _signed_manifest, private_key_b64, public_key_b64 = build_local_dev_enrolled_session_fixture(
        capability="local_tools",
        now=now,
    )
    assert session is not None
    manifest_private_key_b64, manifest_public_key_b64 = generate_test_local_node_keypair()
    manifest = build_test_local_node_manifest(capabilities=("local_tools",))
    signed_manifest = sign_local_node_manifest(manifest, private_key_b64=manifest_private_key_b64)
    request = LocalNodeEnrollmentRequest(
        node_id=manifest.identity.node_id,
        key_id=signed_manifest.signature.key_id,
        mode="official_hybrid_private",
        requested_capabilities=manifest.capabilities,
    )
    challenge = create_pairing_challenge(request, pairing_code="123456")
    pairing_once = consume_pairing_code(
        challenge,
        pairing_code="123456",
        signed_manifest=signed_manifest,
        public_key_b64=manifest_public_key_b64,
        now=now,
    )
    pairing_reuse = consume_pairing_code(
        pairing_once.challenge,
        pairing_code="123456",
        signed_manifest=signed_manifest,
        public_key_b64=manifest_public_key_b64,
        now=now,
    )
    args_hash = action_args_hash({"action": "synthetic_preview"})
    unsigned = build_unsigned_local_node_action_envelope(
        action_id="public-demo-action",
        node_id=session.enrolled_node_id,
        session_id=session.session_id,
        mode=session.mode,
        capability="local_tools",
        args_hash=args_hash,
        nonce="public-demo-action-nonce",
    )
    signed_action = sign_local_node_action_envelope(unsigned, private_key_b64=private_key_b64)
    nonce_store = InMemoryNonceStore()
    verified_action = verify_local_node_action_envelope(
        signed_action,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=args_hash,
        nonce_store=nonce_store,
        mode=session.mode,
        now=now,
    )
    replay = verify_local_node_action_envelope(
        signed_action,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=args_hash,
        nonce_store=nonce_store,
        mode=session.mode,
        now=now,
    )
    dangerous = evaluate_local_dev_session_binding(
        capability="dangerous_operations",
        enrollment_state="enrolled_verified",
        now=now,
    )
    trust_status = build_local_dev_control_plane_status(
        signed_manifest=signed_manifest,
        public_key_b64=manifest_public_key_b64,
        now=now,
    )
    from ora_core.discord_gateway import SyntheticDiscordGatewayAdapter

    discord = SyntheticDiscordGatewayAdapter().handle_mention("hello from demo").to_public_dict()
    assert trust_status.local_node.verification_state == "present_verified"
    assert pairing_once.accepted is True and pairing_reuse.accepted is False
    assert verified_action.status == "approval_required"
    assert replay.status == "replayed_nonce"
    assert dangerous.action_envelope is not None and dangerous.action_envelope.approval_required is True
    assert discord["live_discord"] is False
    assert discord["final_once"] is True
    return (
        {"name": "signed_manifest_verified", "status": "ok", "verified": True},
        {"name": "enrollment_session_available", "status": "ok", "session_bound": True},
        {"name": "tamper_replay_rejected", "status": "ok", "replay_rejected": True},
        {"name": "dangerous_operation_approval_required", "status": "ok", "approval_required": True},
        {
            "name": "synthetic_discord_gateway",
            "status": "ok",
            "synthetic": discord["synthetic"],
            "live_discord": discord["live_discord"],
            "final_once": discord["final_once"],
            "token_required": discord["token_required"],
        },
    )


def _managed_download_checks() -> tuple[dict[str, object], ...]:
    from ora_core.brain.process import MainProcess
    from ora_core.status_contract import build_official_status_contract
    from yonerai_cli.install_planner import build_windows_install_plan_from_default

    process = object.__new__(MainProcess)
    managed_download = process._coerce_download_link(
        url="/v1/files/public-demo/download",
        label="public demo artifact",
    )
    unsafe_download = process._coerce_download_link(
        url="https://example.com/not-managed.bin",
        label="unsafe artifact",
    )
    status_contract = build_official_status_contract(source="fixture")
    install_plan = build_windows_install_plan_from_default(_repo_root())
    assert managed_download is not None
    assert unsafe_download is None
    assert status_contract["production_service_called"] is False
    assert install_plan["download_performed"] is False
    return (
        {
            "name": "managed_url_accepted",
            "status": "ok",
            "accepted": True,
            "guard": "managed_download_guard",
        },
        {
            "name": "unsafe_url_rejected",
            "status": "ok",
            "rejected": True,
            "guard": "managed_download_guard",
        },
        {
            "name": "official_status_contract",
            "status": "ok",
            "official_cloud_runtime_included": status_contract["official_cloud_runtime_included"],
            "oracle_control_plane_production_ready": status_contract["oracle_control_plane_production_ready"],
            "network_performed": status_contract["production_service_called"],
        },
        {
            "name": "windows_install_dry_run",
            "status": "ok",
            "dry_run": install_plan["dry_run"],
            "download_performed": install_plan["download_performed"],
            "install_performed": install_plan["install_performed"],
            "path_mutation": install_plan["path_mutation"],
        },
    )


def _self_evolution_checks() -> tuple[dict[str, object], ...]:
    from ora_core.route_preview import preview_route
    from ora_core.hybrid import (
        FIXTURE_NOW,
        build_memory_candidate_fixture,
        evaluate_donation_policy,
        evaluate_memory_candidate_policy,
    )
    from src.self_evolution import SyntheticEvolutionEvent, generate_evolution_proposal

    route = preview_route(
        "use local tool",
        mode="official_hybrid_private",
        requested_capability="local_tools",
        has_local_node=True,
        local_node_verification_state="present_verified",
        local_node_capabilities=("local_tools",),
        require_enrolled_verified_session=True,
        session_verification_state="enrolled_verified",
    )
    proposal = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="failed_step",
            summary="Synthetic demo event requests clearer Local Node enrollment guidance.",
            severity=4,
            confidence=0.8,
        ),
        route_trust_context=route.to_public_dict(),
    )
    assert proposal.proposal_only is True
    assert proposal.scorecard.mode_experience_gain >= 1
    assert proposal.approval_draft.github_write_allowed is False
    assert proposal.approval_draft.deploy_allowed is False
    memory_fixture = build_memory_candidate_fixture()
    donation_policy = evaluate_donation_policy(
        memory_fixture.envelope,
        trust_registry=memory_fixture.trust_registry,
        nonce_store=memory_fixture.nonce_store,
        signature_verifier=memory_fixture.signature_verifier,
        now=FIXTURE_NOW,
    )
    memory_policy = evaluate_memory_candidate_policy(memory_fixture.envelope)
    assert donation_policy.action == "quarantine"
    assert donation_policy.trusted is False
    assert donation_policy.requires_approval is True
    assert memory_policy.status == "quarantined"
    assert memory_policy.memory_persisted is False
    return (
        {"name": "synthetic_event", "status": "ok", "event_type": proposal.event_type},
        {"name": "proposal_only_output", "status": "ok", "proposal_only": proposal.proposal_only},
        {"name": "scorecard", "status": "ok", "mode_experience_gain": proposal.scorecard.mode_experience_gain},
        {
            "name": "approval_draft",
            "status": "ok",
            "github_write_allowed": proposal.approval_draft.github_write_allowed,
            "deploy_allowed": proposal.approval_draft.deploy_allowed,
        },
        {
            "name": "memory_candidate_fixture_quarantined",
            "status": "ok",
            "donation_action": donation_policy.action,
            "trusted": donation_policy.trusted,
            "approval_required": donation_policy.requires_approval,
            "memory_status": memory_policy.status,
            "memory_persisted": memory_policy.memory_persisted,
        },
    )


def _limitation_checks(limitations: tuple[str, ...]) -> tuple[dict[str, object], ...]:
    return tuple({"name": name, "status": "not_included"} for name in limitations)


def run_demo() -> dict[str, object]:
    previous_env = {key: os.environ.get(key) for key in _PUBLIC_ENV_KEYS}
    try:
        _prepare_import_path()
        from ora_core.demo_contract import build_demo_result, build_demo_section

        sections = (
            build_demo_section(
                "public_core",
                summary="Credential-free local public MVP checks: health, mock message, and run contract.",
                checks=_public_core_checks(),
            ),
            build_demo_section(
                "mode_boundary",
                summary="Self-host is public/local, Hybrid exposes Local Node contracts, Managed Cloud is external contract-only.",
                checks=_mode_boundary_checks(),
            ),
            build_demo_section(
                "route_preview",
                summary="Preview-only routes show contract-only cloud, enrolled Hybrid, and approval-gated dangerous work.",
                checks=_route_preview_checks(),
            ),
            build_demo_section(
                "provider_planner",
                summary="Provider registry, mock provider, task classification, model selection, and execution-plan preview.",
                checks=_provider_planner_checks(),
            ),
            build_demo_section(
                "execution_spine",
                summary="Mock provider execution, redacted run ledger, local provider registry, and disabled search/tool boundaries.",
                checks=_execution_spine_checks(),
            ),
            build_demo_section(
                "hybrid_trust",
                summary="Test-only Local Node manifest, enrollment/session, signed action, replay denial, and approval gate.",
                checks=_hybrid_trust_checks(),
            ),
            build_demo_section(
                "managed_download",
                summary="Managed download URLs are accepted while arbitrary or unsafe URLs are rejected.",
                checks=_managed_download_checks(),
            ),
            build_demo_section(
                "self_evolution",
                summary="Synthetic self-evolution produces scorecard and approval draft without auto actions.",
                checks=_self_evolution_checks(),
            ),
            build_demo_section(
                "limitations",
                summary="Public demo boundaries: no production Oracle, live Discord, persistent memory, Google login, or deploy.",
                checks=_limitation_checks((
                    "no_production_oracle",
                    "no_live_discord",
                "no_persistent_memory",
                "local_memory_opt_in_only",
                "no_google_login",
                "no_official_cloud_runtime_in_public_repo",
                "no_live_provider_by_default",
                "installer_dry_run_only",
                "proposal_only_self_evolution",
                "no_deploy",
            )),
            ),
        )
        return build_demo_result(sections).to_public_dict()
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def format_pretty_demo(result: dict[str, object]) -> str:
    sections = result["sections"]
    assert isinstance(sections, list)
    lines = [
        "YonerAI public demo",
        "YonerAI CLI:",
        "- command: yonerai demo --pretty",
        "- json: yonerai demo --json",
        "- quickstart_alias: yonerai quickstart",
        "Result: ok",
        f"Contract: {result['contract']}",
        f"Schema: {result['schema_version']}",
        "Demo Experience:",
        "- Self-host local public MVP",
        "- Hybrid Local Node contract/dev simulator",
        "- Managed Cloud external contract-only",
        "- Route preview, provider planning, execution spine, enrolled Local Node trust/session simulator, managed download guard",
        "- Proposal-only self-evolution scorecard and approval draft",
        "Boundaries:",
        f"- credentials_required: {str(result['credentials_required']).lower()}",
        f"- network_required: {str(result['network_required']).lower()}",
        f"- oracle_required: {str(result['oracle_required']).lower()}",
        f"- live_discord_required: {str(result['live_discord_required']).lower()}",
        f"- persistent_memory_required: {str(result['persistent_memory_required']).lower()}",
        f"- google_login_required: {str(result['google_login_required']).lower()}",
        f"- deploy_required: {str(result['deploy_required']).lower()}",
        f"- official_cloud_runtime_included: {str(result['official_cloud_runtime_included']).lower()}",
        "Sections:",
    ]
    for section in sections:
        assert isinstance(section, dict)
        lines.append(f"- {section['name']}: {section['status']} - {section['summary']}")
        for check in section["checks"]:
            assert isinstance(check, dict)
            detail = [str(check["name"]), str(check["status"])]
            for key in (
                "route",
                "provider",
                "public_repo_support",
                "memory_persisted",
                "session_verified",
                "approval_required",
                "guard",
                "task_category",
                "risk",
                "model",
                "model_tier",
                "execution_surface",
                "provider_status",
                "external_provider_configured",
                "external_provider_available",
                "disabled_reason",
                "live_call_performed",
                "execution_performed",
                "run_id",
                "run_status",
                "ledger_file_backed",
                "workspace_file_access_event",
                "raw_content_persisted",
                "raw_prompt_persisted",
                "loopback_only",
                "web_search",
                "tool_boundary",
                "live_tool_execution",
                "network_performed",
                "download_performed",
                "proposal_only",
                "mode_experience_gain",
                "github_write_allowed",
                "deploy_allowed",
                "donation_action",
                "trusted",
                "memory_status",
                "openai_compatible",
                "local_llm",
                "run_ledger",
                "anthropic",
                "gemini",
                "local_provider_available",
                "local_provider_blockers",
                "local_loopback_only",
                "openai_compatible_live_ready",
                "openai_compatible_blockers",
                "adapter",
                "result_count",
                "reason",
                "requires_explicit_live_provider",
                "actions_not_performed",
                "external_network_call_performed",
                "record_count",
                "cloud_synced",
                "synthetic",
                "live_discord",
                "final_once",
                "token_required",
                "official_cloud_runtime_included",
                "oracle_control_plane_production_ready",
                "dry_run",
                "install_performed",
                "path_mutation",
            ):
                if key in check:
                    detail.append(f"{key}={str(check[key]).lower()}")
            lines.append(f"  - {' | '.join(detail)}")
    return "\n".join(lines)


def _safe_demo_error(exc: Exception) -> str:
    if not isinstance(exc, AssertionError):
        return "YonerAI public demo failed"
    message = " ".join(str(exc).split())[:220]
    if not message or any(pattern.search(message) for pattern in _PRIVATE_MARKERS):
        return "YonerAI public demo failed"
    return message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the credential-free YonerAI public demo.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    output.add_argument("--pretty", action="store_true", help="Print a readable sectioned demo summary.")
    args = parser.parse_args(argv)
    try:
        result = run_demo()
    except Exception as exc:
        public_error = _safe_demo_error(exc)
        failure = {"ok": False, "contract": "yonerai-public-demo/v1", "error": public_error}
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True) if args.json else f"FAIL: {public_error}")
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(format_pretty_demo(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
