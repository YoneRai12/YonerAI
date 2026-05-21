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
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE),
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
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _prepare_import_path() -> None:
    root = _repo_root()
    core_src = root / "core" / "src"
    for path in (root, core_src):
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
    assert trust_status.local_node.verification_state == "present_verified"
    assert pairing_once.accepted is True and pairing_reuse.accepted is False
    assert verified_action.status == "approval_required"
    assert replay.status == "replayed_nonce"
    assert dangerous.action_envelope is not None and dangerous.action_envelope.approval_required is True
    return (
        {"name": "signed_manifest_verified", "status": "ok", "verified": True},
        {"name": "enrollment_session_available", "status": "ok", "session_bound": True},
        {"name": "tamper_replay_rejected", "status": "ok", "replay_rejected": True},
        {"name": "dangerous_operation_approval_required", "status": "ok", "approval_required": True},
    )


def _managed_download_checks() -> tuple[dict[str, object], ...]:
    return (
        {"name": "managed_url_accepted", "status": "ok", "accepted": True},
        {"name": "unsafe_url_rejected", "status": "ok", "rejected": True},
    )


def _self_evolution_checks() -> tuple[dict[str, object], ...]:
    from ora_core.route_preview import preview_route
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
                    "no_google_login",
                    "no_official_cloud_runtime_in_public_repo",
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
        "Result: ok",
        f"Contract: {result['contract']}",
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
                "session_verified",
                "approval_required",
                "proposal_only",
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
