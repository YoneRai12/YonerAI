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
    assert ("GET", "/v1/oracle/runs/{run_id}") in endpoints
    assert ("GET", "/v1/rate-limit") in endpoints
    assert ("GET", "/v1/status") in endpoints
    assert ("POST", "/v1/evolve/proposals") in endpoints
    assert ("GET", "/v1/evolve/proposals") in endpoints
    assert len(report["endpoints"]) == 10
    assert report["self_evolution_boundary"]["raw_prompts_allowed_in_public_repo"] is False
    assert report["self_evolution_boundary"]["auto_pr_merge_deploy_allowed"] is False


def test_official_api_endpoints_define_auth_schema_rate_limit_and_privacy() -> None:
    from ora_core.official import build_official_api_contract_fixture

    report = build_official_api_contract_fixture()
    schema_base = ROOT / "docs" / "contracts" / "schemas"

    for endpoint in report["endpoints"]:
        assert endpoint["auth"]
        assert endpoint["implemented_in_public_repo"] is False
        assert endpoint["fixture_available"] is True
        assert endpoint["fixture_support"] == "contract_only"
        assert endpoint["response_schema"]["schema_ref"]
        assert (schema_base / endpoint["response_schema"]["schema_ref"]).exists()
        if endpoint["method"] == "POST":
            assert endpoint["request_schema"]["required"] is True
            assert (schema_base / endpoint["request_schema"]["schema_ref"]).exists()
        else:
            assert endpoint["request_schema"]["required"] is False
        assert endpoint["rate_limit"]["quota_exceeded_status"] == 429
        assert "Retry-After" in endpoint["rate_limit"]["headers"]
        bucket_description = endpoint["rate_limit"]["headers"]["X-YonerAI-RateLimit-Bucket"]
        assert "user_quota" in bucket_description
        assert "device_quota" in bucket_description
        assert "provider_quota" in bucket_description
        assert " device," not in bucket_description
        error_required = endpoint["error_schema"]["properties"]["error"]["required"]
        assert "retry_after" in error_required
        privacy = endpoint["privacy_boundary"]
        assert privacy["raw_prompt_allowed"] is False
        assert privacy["private_file_content_allowed"] is False
        assert privacy["local_memory_allowed"] is False
        assert privacy["local_node_payload_allowed"] is False
        assert privacy["provider_keys_allowed"] is False
        assert privacy["local_absolute_paths_allowed"] is False
        assert privacy["openai_shared_traffic_allowed"] is False


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
    assert schema["properties"]["endpoints"]["minItems"] == 10


def test_official_api_schema_files_are_valid_json() -> None:
    schema_dir = ROOT / "docs" / "contracts" / "schemas" / "official-api-0.1"
    schema_files = sorted(schema_dir.glob("*.schema.json"))

    assert len(schema_files) >= 13
    for schema_path in schema_files:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://yonerai.com/contracts/official-api-0.1/")
        assert schema["type"] == "object"


def test_rate_limit_policy_keeps_shared_traffic_off_and_local_fallback() -> None:
    from ora_core.official import build_rate_limit_policy_report

    report = build_rate_limit_policy_report()

    assert report["schema_version"] == "yonerai-rate-limit-policy/v0.1"
    assert report["policy_state"] == "contract_only"
    assert report["shared_traffic"]["openai_shared_traffic_enabled"] is False
    assert report["shared_traffic"]["free_usage_claimed"] is False
    assert report["fallback"]["cloud_quota_exceeded"] == "local_mock_or_loopback_provider"
    assert report["quota_exceeded_response"]["status"] == 429
    assert "retry_after" in report["quota_exceeded_response"]["required_fields"]
    assert "Retry-After" in report["headers"]
    assert "user_quota" in report["headers"]["X-YonerAI-RateLimit-Bucket"]
    assert "device_quota" in report["headers"]["X-YonerAI-RateLimit-Bucket"]
    assert "provider_quota" in report["headers"]["X-YonerAI-RateLimit-Bucket"]
    assert " device," not in report["headers"]["X-YonerAI-RateLimit-Bucket"]
    assert set(report["quotas"]) >= {
        "anonymous",
        "authenticated",
        "device_quota",
        "user_quota",
        "provider_quota",
        "cloud_contract",
        "oracle_queue",
        "abuse",
    }


def test_official_api_status_is_fixture_only_and_private_safe() -> None:
    from ora_core.official import build_official_api_status_report

    report = build_official_api_status_report(auth_state="dry_run")
    serialized = json.dumps(report, sort_keys=True)

    assert report["schema_version"] == "yonerai-official-api-status/v0.1"
    assert report["official_api_configured"] is False
    assert report["endpoint_url"] == "not_configured"
    assert report["official_backend_called"] is False
    assert report["production_backend_included"] is False
    assert report["shared_traffic_enabled"] is False
    assert report["private_content_exclusion"]["provider_keys_allowed"] is False
    assert "sk-" not in serialized
    assert "C:\\Users" not in serialized


def test_official_api_docs_capture_aws_handoff_and_rate_limit_boundaries() -> None:
    handoff = (ROOT / "docs" / "private_handoff" / "AWS_OFFICIAL_API_HANDOFF.md").read_text(encoding="utf-8")
    policy = (ROOT / "docs" / "policy" / "API_RATE_LIMIT_POLICY.md").read_text(encoding="utf-8")
    contract = (ROOT / "docs" / "contracts" / "OFFICIAL_API_CONTRACT_0_1.md").read_text(encoding="utf-8")

    assert "No production AWS credential" in handoff
    assert "no production secrets" in handoff.lower()
    assert "Retry-After" in policy
    assert "OpenAI shared traffic is off by default" in policy
    assert "yonerai api status --pretty --lang ja" in contract
    assert "production AWS backend is included here" in contract


def test_sync_contract_rejects_unknown_direction_and_auth_state() -> None:
    from ora_core.official import build_sync_preview_report, build_sync_status_report

    with pytest.raises(ValueError, match="unsupported sync direction"):
        build_sync_preview_report(direction="sideways")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="unsupported auth state"):
        build_sync_status_report(auth_state="complete")  # type: ignore[arg-type]
