from __future__ import annotations

import json

from scripts.dev import public_mvp_smoke


def test_public_mvp_smoke_runs_without_credentials(monkeypatch) -> None:
    for key in (
        "DISCORD_TOKEN",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "ORA_CORE_API_TOKEN",
        "ORA_LOCAL_LLM_BASE_URL",
        "ORA_LOCAL_LLM_ENABLED",
        "ORA_LOCAL_LLM_PUBLIC_TOKEN",
    ):
        monkeypatch.setenv(key, "must-be-cleared-by-smoke")

    result = public_mvp_smoke.run_smoke()

    assert result["ok"] is True
    assert result["contract"] == public_mvp_smoke.PUBLIC_MVP_SMOKE_CONTRACT
    assert result["credentials_required"] is False
    assert result["external_provider_required"] is False
    assert result["live_discord_required"] is False
    assert result["production_deploy_required"] is False
    assert result["persistent_memory_required"] is False
    assert [check["endpoint"] for check in result["checks"]] == [
        "/health",
        "/v1/public/messages",
        "/api/v1/agent/run",
        "managed-download-contract",
        "yonerai-differentiation-contract",
        "hybrid-trust-contract",
        "enrolled-hybrid-slice-contract",
    ]
    managed_download_check = result["checks"][-4]
    assert managed_download_check == {
        "endpoint": "managed-download-contract",
        "status": "ok",
        "accepted": "3",
        "rejected": "4",
    }
    differentiation_check = result["checks"][-3]
    assert differentiation_check == {
        "endpoint": "yonerai-differentiation-contract",
        "status": "ok",
        "modes": "3",
        "route_preview": "cloud_only,local_node_required",
        "local_dev_control_plane": "simulator",
        "self_evolution": "proposal_only",
    }
    trust_check = result["checks"][-2]
    assert trust_check == {
        "endpoint": "hybrid-trust-contract",
        "status": "ok",
        "local_node_signature_status": "test_manifest_verified",
        "tamper_rejected": "true",
        "expired_rejected": "true",
        "dangerous_capability_still_gated": "true",
        "production_trust_material": "false",
    }
    enrolled_check = result["checks"][-1]
    assert enrolled_check == {
        "endpoint": "enrolled-hybrid-slice-contract",
        "status": "ok",
        "local_node_manifest_verified": "true",
        "enrollment_pairing_once": "true",
        "session_bound": "true",
        "signed_envelope_verified": "true",
        "replay_rejected": "true",
        "dangerous_capability_approval_required": "true",
        "route_preview_enrolled_hybrid": "hybrid_coordination",
        "self_evolution_scorecard_proposal_only": "true",
    }
    assert "must-be-cleared-by-smoke" not in json.dumps(result)


def test_public_mvp_smoke_restores_environment(monkeypatch) -> None:
    monkeypatch.setenv("ORA_DOTENV_PATH", "original.env")
    monkeypatch.setenv("ORA_ALLOW_MISSING_SECRETS", "0")
    monkeypatch.setenv("OPENAI_API_KEY", "existing-test-key")

    result = public_mvp_smoke.run_smoke()

    assert result["ok"] is True
    assert public_mvp_smoke.os.environ["ORA_DOTENV_PATH"] == "original.env"
    assert public_mvp_smoke.os.environ["ORA_ALLOW_MISSING_SECRETS"] == "0"
    assert public_mvp_smoke.os.environ["OPENAI_API_KEY"] == "existing-test-key"


def test_public_mvp_smoke_cli_json_output_is_deterministic(capsys) -> None:
    exit_code = public_mvp_smoke.main(["--json"])

    assert exit_code == 0
    body = json.loads(capsys.readouterr().out)
    assert body["ok"] is True
    assert body["contract"] == public_mvp_smoke.PUBLIC_MVP_SMOKE_CONTRACT
    assert body["checks"] == [
        {"endpoint": "/health", "status": "ok"},
        {
            "endpoint": "/v1/public/messages",
            "mode": "mock",
            "provider": "offline-mock",
            "status": "ok",
        },
        {
            "endpoint": "/api/v1/agent/run",
            "mode": "mock",
            "provider": "offline-mock",
            "status": "ok",
        },
        {
            "accepted": "3",
            "endpoint": "managed-download-contract",
            "rejected": "4",
            "status": "ok",
        },
        {
            "endpoint": "yonerai-differentiation-contract",
            "local_dev_control_plane": "simulator",
            "modes": "3",
            "route_preview": "cloud_only,local_node_required",
            "self_evolution": "proposal_only",
            "status": "ok",
        },
        {
            "dangerous_capability_still_gated": "true",
            "endpoint": "hybrid-trust-contract",
            "expired_rejected": "true",
            "local_node_signature_status": "test_manifest_verified",
            "production_trust_material": "false",
            "status": "ok",
            "tamper_rejected": "true",
        },
        {
            "dangerous_capability_approval_required": "true",
            "endpoint": "enrolled-hybrid-slice-contract",
            "enrollment_pairing_once": "true",
            "local_node_manifest_verified": "true",
            "replay_rejected": "true",
            "route_preview_enrolled_hybrid": "hybrid_coordination",
            "self_evolution_scorecard_proposal_only": "true",
            "session_bound": "true",
            "signed_envelope_verified": "true",
            "status": "ok",
        },
    ]
    assert "run_id" not in body
    assert "session_id" not in body


def test_public_mvp_smoke_cli_pretty_output_summarizes_boundaries(capsys) -> None:
    exit_code = public_mvp_smoke.main(["--pretty"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "YonerAI public MVP smoke" in output
    assert "Result: ok" in output
    assert "Checks passed: 7" in output
    assert "- credentials_required: false" in output
    assert "- external_provider_required: false" in output
    assert "- live_discord_required: false" in output
    assert "- production_deploy_required: false" in output
    assert "- persistent_memory_required: false" in output
    assert "/health | ok" in output
    assert "/v1/public/messages | ok | mode=mock | provider=offline-mock" in output
    assert "/api/v1/agent/run | ok | mode=mock | provider=offline-mock" in output
    assert "managed-download-contract | ok" in output
    assert "yonerai-differentiation-contract | ok" in output
    assert "hybrid-trust-contract | ok" in output
    assert "enrolled-hybrid-slice-contract | ok" in output
    assert "Traceback" not in output


def test_public_mvp_smoke_cli_masks_unexpected_failures(monkeypatch, capsys) -> None:
    def fail_unexpectedly():
        raise RuntimeError("private runtime detail")

    monkeypatch.setattr(public_mvp_smoke, "run_smoke", fail_unexpectedly)

    exit_code = public_mvp_smoke.main(["--json"])

    assert exit_code == 1
    body = json.loads(capsys.readouterr().out)
    assert body == {
        "ok": False,
        "contract": public_mvp_smoke.PUBLIC_MVP_SMOKE_CONTRACT,
        "error": "public MVP smoke failed",
    }
