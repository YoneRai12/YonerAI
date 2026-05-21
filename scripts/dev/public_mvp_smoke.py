from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
import io
import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


PUBLIC_MVP_SMOKE_CONTRACT = "public-mvp-smoke-0.5"
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
    os.environ["ORA_DOTENV_PATH"] = str(_repo_root() / ".codex-public-smoke-missing.env")
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
    try:
        body = response.json()
    except Exception as exc:  # pragma: no cover - defensive command-line guard
        raise AssertionError(f"{endpoint} did not return JSON") from exc
    if not isinstance(body, dict):
        raise AssertionError(f"{endpoint} returned non-object JSON")
    return body


def _assert_managed_download_contract() -> dict[str, str]:
    from ora_core.brain.process import MainProcess

    process = object.__new__(MainProcess)
    safe_urls = (
        "/v1/files/file_public_smoke/download",
        "/s/share_public_smoke",
        "https://files.yonerai.com/v1/files/file_public_smoke/download",
    )
    unsafe_urls = (
        "https://example.com/file.bin",
        "http://files.yonerai.com/v1/files/file_public_smoke/download",
        "/v1/files/../admin",
        r"C:\private\file.txt",
    )

    accepted: list[dict[str, Any] | None] = []
    for url in safe_urls:
        item = process._coerce_download_link(url=url, label="smoke artifact")
        assert item is not None, f"managed download URL was rejected: {url}"
        accepted.append(item)

    rejected: list[dict[str, Any] | None] = []
    for url in unsafe_urls:
        item = process._coerce_download_link(url=url, label="unsafe artifact")
        assert item is None, f"unsafe download URL was accepted: {url}"
        rejected.append(item)

    return {
        "endpoint": "managed-download-contract",
        "status": "ok",
        "accepted": str(len(accepted)),
        "rejected": str(len(rejected)),
    }


def _assert_differentiation_contract() -> dict[str, str]:
    from ora_core.hybrid.local_dev_control_plane import build_local_dev_control_plane_status
    from ora_core.route_preview import preview_route
    from ora_core.three_mode import MODES, build_three_mode_capability_surface
    from src.self_evolution import SyntheticEvolutionEvent, generate_evolution_proposal

    surface = build_three_mode_capability_surface()
    modes = surface["modes"]
    assert sorted(modes) == sorted(MODES), "three-mode surface did not include all modes"
    for mode in MODES:
        profile = modes[mode]
        assert profile["same_user_experience"] is True, f"{mode} did not preserve same experience"
        assert profile["production_deploy_enabled"] is False, f"{mode} enabled production deploy"
        assert profile["persistent_memory_enabled"] is False, f"{mode} enabled persistent memory"

    docs_route = preview_route("summarize public docs", mode="official_managed_cloud")
    private_route = preview_route("read my local file", mode="official_hybrid_private")
    local_dev = build_local_dev_control_plane_status()
    evolution = generate_evolution_proposal(
        SyntheticEvolutionEvent(
            event_type="bug_report",
            summary="Synthetic public smoke fixture proposes a safer route-preview regression test.",
            severity=4,
            confidence=0.8,
        )
    )

    assert docs_route.route == "managed_cloud_contract_only", "public docs did not report managed-cloud contract-only preview"
    assert docs_route.runtime_available_in_public_repo is False, "managed cloud claimed public repo runtime"
    assert docs_route.public_repo_execution_available is False, "managed cloud claimed public repo execution"
    assert private_route.route == "local_node_required", "private work did not require Local Node"
    assert local_dev.profile == "local_dev_control_plane", "local-dev simulator profile mismatch"
    assert local_dev.production_trust_material is False, "local-dev simulator claimed production trust material"
    assert local_dev.official_private_control_plane_ready is False, "local-dev simulator claimed private control-plane ready"
    assert evolution.proposal_only is True, "self-evolution proposal was not proposal-only"
    assert evolution.auto_apply_allowed is False, "self-evolution allowed auto-apply"
    assert evolution.github_write_allowed is False, "self-evolution allowed GitHub write"
    assert evolution.deploy_allowed is False, "self-evolution allowed deploy"

    return {
        "endpoint": "yonerai-differentiation-contract",
        "status": "ok",
        "modes": str(len(MODES)),
        "route_preview": f"{docs_route.route},{private_route.route}",
        "local_dev_control_plane": "non_production_simulator",
        "self_evolution": "proposal_only",
    }


def _assert_mode_boundary_contract() -> dict[str, str]:
    from ora_core.three_mode import build_three_mode_capability_surface

    surface = build_three_mode_capability_surface()
    modes = surface["modes"]
    managed = modes["official_managed_cloud"]
    hybrid = modes["official_hybrid_private"]
    self_host = modes["full_private_self_host"]

    assert self_host["runtime_available_in_public_repo"] is True, "self-host public-local runtime was not marked available"
    assert self_host["public_repo_support_status"] == "public_local_supported"
    assert hybrid["runtime_available_in_public_repo"] is False, "hybrid claimed official runtime in public repo"
    assert hybrid["public_repo_support_status"] == "local_node_contract_and_dev_simulator"
    assert managed["runtime_available_in_public_repo"] is False, "managed cloud claimed public repo runtime"
    assert managed["public_repo_support_status"] == "contract_only"
    assert managed["implementation_owner"] == "official_private"
    assert managed["external_official_service"] is True
    assert managed["contract_only"] is True

    return {
        "endpoint": "mode-boundary-contract",
        "status": "ok",
        "self_host": "public_local_supported",
        "hybrid_private": "local_node_contract_and_dev_simulator_supported",
        "managed_cloud": "official_private_external_contract_only",
        "official_cloud_runtime_included": "false",
        "real_telemetry_included": "false",
        "production_oracle_included": "false",
        "production_trust_store_included": "false",
        "hybrid_trust_contract": "test_only",
        "local_dev_control_plane": "non_production_simulator",
    }


def _assert_hybrid_trust_contract() -> dict[str, str]:
    from ora_core.hybrid import local_node_manifest
    from ora_core.hybrid.local_dev_control_plane import build_local_dev_control_plane_status
    from ora_core.route_preview import preview_route

    now = datetime(2026, 5, 21, 12, tzinfo=timezone.utc)
    private_key_b64, public_key_b64 = local_node_manifest.generate_test_local_node_keypair()
    manifest = local_node_manifest.build_test_local_node_manifest()
    signed = local_node_manifest.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)

    verified_status = build_local_dev_control_plane_status(
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=now,
    )
    tampered_status = build_local_dev_control_plane_status(
        signed_manifest=replace(
            signed,
            manifest=replace(
                signed.manifest,
                capabilities=signed.manifest.capabilities + ("unknown.future.capability",),
            ),
        ),
        public_key_b64=public_key_b64,
        now=now,
    )

    expired_private_key_b64, expired_public_key_b64 = local_node_manifest.generate_test_local_node_keypair()
    expired_manifest = local_node_manifest.build_test_local_node_manifest(expires_at="2026-05-21T01:00:00Z")
    expired_signed = local_node_manifest.sign_local_node_manifest(
        expired_manifest,
        private_key_b64=expired_private_key_b64,
    )
    expired_status = build_local_dev_control_plane_status(
        signed_manifest=expired_signed,
        public_key_b64=expired_public_key_b64,
        now=now,
    )
    dangerous_route = preview_route(
        "run a shell command",
        mode="official_hybrid_private",
        has_local_node=True,
        local_node_verification_state=verified_status.local_node.verification_state,
        local_node_capabilities=verified_status.local_node.capabilities,
    )

    assert verified_status.local_node.verification_state == "present_verified", "test manifest was not verified"
    assert verified_status.local_node.signed_origin_verified is True, "signed origin was not verified"
    assert verified_status.local_node.trusted is False, "test manifest claimed trust"
    assert verified_status.production_trust_material is False, "test manifest claimed production trust material"
    assert tampered_status.local_node.verification_state == "invalid_signature", "tamper was not rejected"
    assert expired_status.local_node.verification_state == "expired", "expired manifest was not rejected"
    assert dangerous_route.route == "hybrid_coordination_preview", "dangerous verified route did not route through hybrid preview"
    assert dangerous_route.approval_required is True, "dangerous verified route did not require approval"
    assert dangerous_route.signed_origin_verified is True, "verified route did not report signed origin"

    return {
        "endpoint": "hybrid-trust-contract",
        "status": "ok",
        "local_node_signature_status": "test_manifest_verified",
        "tamper_rejected": "true",
        "expired_rejected": "true",
        "dangerous_capability_still_gated": "true",
        "production_trust_material": "false",
    }


def _assert_enrolled_hybrid_slice_contract() -> dict[str, str]:
    from ora_core.hybrid import (
        InMemoryNonceStore,
        LocalNodeEnrollmentRequest,
        action_args_hash,
        build_local_dev_enrolled_session_fixture,
        build_unsigned_local_node_action_envelope,
        consume_pairing_code,
        create_pairing_challenge,
        evaluate_local_dev_session_binding,
        generate_test_local_node_keypair,
        sign_local_node_manifest,
        build_test_local_node_manifest,
        sign_local_node_action_envelope,
        verify_local_node_action_envelope,
    )
    from ora_core.route_preview import preview_route
    from src.self_evolution import SyntheticEvolutionEvent, generate_evolution_proposal

    now = datetime(2026, 5, 21, 0, 5, tzinfo=timezone.utc)
    session, _signed_manifest, private_key_b64, public_key_b64 = build_local_dev_enrolled_session_fixture(
        capability="local_tools",
        now=now,
    )
    assert session is not None, "enrollment pairing did not produce a session"
    pairing_private_key_b64, pairing_public_key_b64 = generate_test_local_node_keypair()
    pairing_manifest = build_test_local_node_manifest(capabilities=("local_tools",))
    pairing_signed = sign_local_node_manifest(pairing_manifest, private_key_b64=pairing_private_key_b64)
    pairing_request = LocalNodeEnrollmentRequest(
        node_id=pairing_manifest.identity.node_id,
        key_id=pairing_signed.signature.key_id,
        mode="official_hybrid_private",
        requested_capabilities=pairing_manifest.capabilities,
    )
    pairing_challenge = create_pairing_challenge(pairing_request, pairing_code="123456")
    pairing_once = consume_pairing_code(
        pairing_challenge,
        pairing_code="123456",
        signed_manifest=pairing_signed,
        public_key_b64=pairing_public_key_b64,
        now=now,
    )
    pairing_reuse = consume_pairing_code(
        pairing_once.challenge,
        pairing_code="123456",
        signed_manifest=pairing_signed,
        public_key_b64=pairing_public_key_b64,
        now=now,
    )
    args_hash = action_args_hash({"action": "synthetic_preview"})
    unsigned = build_unsigned_local_node_action_envelope(
        action_id="public-smoke-action",
        node_id=session.enrolled_node_id,
        session_id=session.session_id,
        mode=session.mode,
        capability="local_tools",
        args_hash=args_hash,
        nonce="public-smoke-action-nonce",
    )
    signed_action = sign_local_node_action_envelope(unsigned, private_key_b64=private_key_b64)
    verified_action = verify_local_node_action_envelope(
        signed_action,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=args_hash,
        nonce_store=InMemoryNonceStore(),
        mode=session.mode,
        now=now,
    )
    replay = verify_local_node_action_envelope(
        signed_action,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=args_hash,
        nonce_store=InMemoryNonceStore(max_entries=1),
        mode=session.mode,
        now=now,
    )
    nonce_store = InMemoryNonceStore()
    assert verify_local_node_action_envelope(
        signed_action,
        session=session,
        public_key_b64=public_key_b64,
        expected_args_hash=args_hash,
        nonce_store=nonce_store,
        mode=session.mode,
        now=now,
    ).signature_valid is True
    replay_rejected = verify_local_node_action_envelope(
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
            summary="Synthetic enrolled hybrid public smoke proposal.",
            severity=4,
            confidence=0.8,
        ),
        route_trust_context=route.to_public_dict(),
    )

    assert verified_action.status == "approval_required", "signed envelope did not require approval"
    assert replay.status == "approval_required", "fresh nonce verification did not pass"
    assert replay_rejected.status == "replayed_nonce", "replayed nonce was not rejected"
    assert dangerous.action_envelope is not None, "dangerous binding did not include action decision"
    assert dangerous.action_envelope.approval_required is True, "dangerous capability was not approval gated"
    assert pairing_once.accepted is True, "pairing code was not accepted once"
    assert pairing_reuse.accepted is False, "pairing code reuse was not rejected"
    assert route.route == "hybrid_coordination_preview", "enrolled hybrid route did not coordinate"
    assert route.session_verified is True, "route did not report enrolled verified session"
    assert proposal.proposal_only is True, "self-evolution proposal was not proposal-only"
    assert proposal.approval_draft.github_write_allowed is False, "approval draft allowed GitHub write"
    assert proposal.approval_draft.deploy_allowed is False, "approval draft allowed deploy"

    return {
        "endpoint": "enrolled-hybrid-slice-contract",
        "status": "ok",
        "local_node_manifest_verified": "true",
        "enrollment_pairing_once": "true",
        "session_bound": "true",
        "signed_envelope_verified": "true",
        "replay_rejected": "true",
        "dangerous_capability_approval_required": "true",
        "route_preview_enrolled_hybrid": route.route,
        "self_evolution_scorecard_proposal_only": "true",
    }


def run_smoke() -> dict[str, Any]:
    previous_env = {key: os.environ.get(key) for key in _PUBLIC_ENV_KEYS}
    try:
        app = _fresh_core_app()
        checks: list[dict[str, str]] = []

        with TestClient(app, client=("127.0.0.1", 50000)) as client:
            health = client.get("/health")
            health_body = _assert_json_response(health, endpoint="/health")
            assert health.status_code == 200, "/health did not return 200"
            assert health_body.get("ok") is True, "/health ok flag was not true"
            checks.append({"endpoint": "/health", "status": "ok"})

            message = client.post(
                "/v1/public/messages",
                json={"message": "hello public MVP", "mode": "mock", "conversation_id": "public-mvp-smoke"},
            )
            message_body = _assert_json_response(message, endpoint="/v1/public/messages")
            assert message.status_code == 200, "/v1/public/messages did not return 200"
            assert message_body.get("ok") is True, "public message ok flag was not true"
            assert message_body.get("mode") == "mock", "public message mode was not mock"
            assert message_body.get("provider") == "offline-mock", "public message provider was not offline-mock"
            assert message_body.get("memory_persisted") is False, "public message persisted memory"
            assert message_body.get("requires_approval") is False, "public message unexpectedly required approval"
            checks.append(
                {
                    "endpoint": "/v1/public/messages",
                    "status": "ok",
                    "mode": "mock",
                    "provider": "offline-mock",
                }
            )

            run = client.post(
                "/api/v1/agent/run",
                json={"prompt": "hello public MVP", "mode": "mock", "conversation_id": "public-mvp-smoke"},
            )
            run_body = _assert_json_response(run, endpoint="/api/v1/agent/run")
            assert run.status_code == 200, "/api/v1/agent/run did not return 200"
            assert run_body.get("ok") is True, "agent run ok flag was not true"
            assert run_body.get("status") == "completed", "agent run did not complete in mock mode"
            assert run_body.get("provider") == "offline-mock", "agent run provider was not offline-mock"
            assert run_body.get("memory_persisted") is False, "agent run persisted memory"
            assert str(run_body.get("events_url", "")).startswith("/api/v1/agent/runs/")
            assert str(run_body.get("results_url", "")).startswith("/api/v1/agent/runs/")
            checks.append(
                {
                    "endpoint": "/api/v1/agent/run",
                    "status": "ok",
                    "mode": "mock",
                    "provider": "offline-mock",
                }
            )

            checks.append(_assert_managed_download_contract())
            checks.append(_assert_differentiation_contract())
            checks.append(_assert_mode_boundary_contract())
            checks.append(_assert_hybrid_trust_contract())
            checks.append(_assert_enrolled_hybrid_slice_contract())

        return {
            "ok": True,
            "contract": PUBLIC_MVP_SMOKE_CONTRACT,
            "credentials_required": False,
            "external_provider_required": False,
            "live_discord_required": False,
            "production_deploy_required": False,
            "persistent_memory_required": False,
            "checks": checks,
        }
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _format_pretty_result(result: dict[str, Any]) -> str:
    checks = result["checks"]
    lines = [
        "YonerAI public MVP smoke",
        "Result: ok",
        f"Contract: {result['contract']}",
        f"Checks passed: {len(checks)}",
        "Boundaries:",
        f"- credentials_required: {str(result['credentials_required']).lower()}",
        f"- external_provider_required: {str(result['external_provider_required']).lower()}",
        f"- live_discord_required: {str(result['live_discord_required']).lower()}",
        f"- production_deploy_required: {str(result['production_deploy_required']).lower()}",
        f"- persistent_memory_required: {str(result['persistent_memory_required']).lower()}",
        "Checks:",
    ]
    for check in checks:
        details = [check["endpoint"], check["status"]]
        if "mode" in check:
            details.append(f"mode={check['mode']}")
        if "provider" in check:
            details.append(f"provider={check['provider']}")
        lines.append(f"- {' | '.join(details)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the credential-free YonerAI public MVP smoke.")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Print compact machine-readable JSON.")
    output.add_argument("--pretty", action="store_true", help="Print a detailed human-readable summary.")
    args = parser.parse_args(argv)

    try:
        result = run_smoke()
    except Exception as exc:
        public_error = str(exc) if isinstance(exc, AssertionError) else "public MVP smoke failed"
        failure = {"ok": False, "contract": PUBLIC_MVP_SMOKE_CONTRACT, "error": public_error}
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True) if args.json else f"FAIL: {public_error}")
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    elif args.pretty:
        print(_format_pretty_result(result))
    else:
        print("YonerAI public MVP smoke: ok")
        for check in result["checks"]:
            print(f"- {check['endpoint']}: {check['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
