from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))


def test_account_status_is_contract_only_without_tokens() -> None:
    from ora_core.official import build_account_status_report

    report = build_account_status_report(auth_state="dry_run")
    serialized = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == "yonerai-account-sync/v0.1"
    assert report["auth_session"]["production_login_enabled"] is False
    assert report["auth_session"]["pkce_required"] is True
    assert report["auth_session"]["state_required"] is True
    assert report["auth_session"]["loopback_redirect_only"] is True
    assert report["local_profile"]["provider_keys_stored"] is False
    assert "refresh_token_plaintext_allowed" in serialized
    assert "sk-" not in serialized


def test_cloud_to_local_sync_requires_linked_selected_conversation() -> None:
    from ora_core.official import build_sync_preview_report

    blocked = build_sync_preview_report(direction="cloud_to_local", auth_state="dry_run", selected=False)
    allowed = build_sync_preview_report(direction="cloud_to_local", auth_state="linked", selected=True)

    assert blocked["decision"]["state"] == "blocked"
    assert blocked["decision"]["reason"] == "account_not_linked"
    assert blocked["ok"] is False
    assert allowed["decision"]["state"] == "allowed"
    assert allowed["decision"]["reason"] == "linked_selected_cloud_conversation"
    assert allowed["official_backend_called"] is False
    assert allowed["sync_performed"] is False


def test_local_to_cloud_requires_explicit_approval_and_excludes_private_content() -> None:
    from ora_core.official import build_sync_preview_report

    preview = build_sync_preview_report(
        direction="local_to_cloud",
        auth_state="linked",
        selected=True,
        contains_private_file_content=True,
        contains_local_memory=True,
        contains_local_node_payload=True,
    )
    exclusion = preview["private_content_exclusion"]

    assert preview["decision"]["state"] == "approval_required"
    assert preview["decision"]["requires_explicit_approval"] is True
    assert exclusion["private_file_content_excluded"] is True
    assert exclusion["local_memory_excluded"] is True
    assert exclusion["local_node_payload_excluded"] is True
    assert "no automatic local-to-cloud upload" in preview["actions_not_performed"]
    assert "no OpenAI shared traffic" in preview["actions_not_performed"]


def test_sync_approval_dry_run_never_records_or_performs_sync() -> None:
    from ora_core.official import build_sync_approval_dry_run_report

    report = build_sync_approval_dry_run_report(
        direction="local_to_cloud",
        auth_state="linked",
        selected=True,
        explicit_approval=True,
    )

    assert report["operation"] == "sync_approve_dry_run"
    assert report["decision"]["state"] == "allowed"
    assert report["dry_run"] is True
    assert report["approval_recorded"] is False
    assert report["sync_performed"] is False
    assert report["official_backend_called"] is False


def test_official_api_contract_lists_required_endpoints_without_public_backend() -> None:
    from ora_core.official import build_official_api_contract_fixture

    report = build_official_api_contract_fixture()
    endpoints = {(item["method"], item["path"]) for item in report["endpoints"]}

    assert report["schema_version"] == "yonerai-official-api-contract/v0.1"
    assert report["production_backend_included"] is False
    assert ("GET", "/v1/account/me") in endpoints
    assert ("GET", "/v1/conversations") in endpoints
    assert ("POST", "/v1/sync/preview") in endpoints
    assert ("POST", "/v1/sync/approve") in endpoints
    assert ("POST", "/v1/oracle/runs") in endpoints
    assert ("GET", "/v1/oracle/runs/{id}") in endpoints
    assert ("GET", "/v1/rate-limit") in endpoints
    assert ("GET", "/v1/status") in endpoints
    assert report["self_evolution_boundary"]["raw_prompts_allowed_in_public_repo"] is False
    assert report["self_evolution_boundary"]["auto_pr_merge_deploy_allowed"] is False


def test_official_api_contract_fixture_file_matches_builder() -> None:
    from ora_core.official import build_official_api_contract_fixture

    fixture_path = ROOT / "docs" / "contracts" / "fixtures" / "official-api-contract-0.1.fixture.json"
    schema_path = ROOT / "docs" / "contracts" / "schemas" / "official-api-contract-0.1.schema.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert fixture == build_official_api_contract_fixture()
    assert schema["properties"]["schema_version"]["const"] == "yonerai-official-api-contract/v0.1"
    assert schema["properties"]["production_backend_included"]["const"] is False
    assert schema["properties"]["auth"]["properties"]["refresh_token_plaintext_allowed"]["const"] is False


def test_rate_limit_policy_keeps_shared_traffic_off_and_local_fallback() -> None:
    from ora_core.official import build_rate_limit_policy_report

    report = build_rate_limit_policy_report()

    assert report["schema_version"] == "yonerai-rate-limit-policy/v0.1"
    assert report["policy_state"] == "contract_only"
    assert report["shared_traffic"]["openai_shared_traffic_enabled"] is False
    assert report["shared_traffic"]["free_usage_claimed"] is False
    assert report["fallback"]["cloud_quota_exceeded"] == "local_mock_or_loopback_provider"


def test_sync_contract_rejects_unknown_direction_and_auth_state() -> None:
    from ora_core.official import build_sync_preview_report, build_sync_status_report

    with pytest.raises(ValueError, match="unsupported sync direction"):
        build_sync_preview_report(direction="sideways")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="unsupported auth state"):
        build_sync_status_report(auth_state="complete")  # type: ignore[arg-type]
