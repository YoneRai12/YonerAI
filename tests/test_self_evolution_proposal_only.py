from __future__ import annotations

from pathlib import Path

import pytest

from src.self_evolution import UnsafeSignalError, generate_proposal, generate_proposals_from_fixture, normalize_signal


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "self_evolution" / "sample_signals.json"


def test_generates_owner_reviewable_proposals_from_synthetic_fixture():
    proposals = generate_proposals_from_fixture(FIXTURE)

    assert len(proposals) == 2
    for proposal in proposals:
        markdown = proposal.to_markdown()
        assert proposal.owner_decision_required is True
        assert proposal.approved is False
        assert "Status: owner review required" in markdown
        assert "This proposal is not auto-applied" in markdown
        assert "no automatic code mutation" in markdown
        assert "no automatic branch, PR, merge, deploy, or release" in markdown
        assert "no real telemetry collection" in markdown
        assert "no SNS scraping" in markdown


@pytest.mark.parametrize(
    "field_name",
    [
        "raw_prompt",
        "raw_completion",
        "chain_of_thought",
        "file_content",
        "user_id",
        "ip",
        "discord_user_id",
        "token",
        "secret",
        "create_branch",
        "open_pr",
        "merge",
        "deploy",
        "apply_patch",
        "commit",
        "release",
        "scrape_url",
        "sns_query",
        "competitor_scrape",
        "live_telemetry_source",
    ],
)
def test_rejects_forbidden_fields(field_name):
    payload = _safe_payload()
    payload[field_name] = "unsafe"

    with pytest.raises(UnsafeSignalError):
        normalize_signal(payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "user_api_key",
        "raw_prompt_text",
        "discord_token",
        "google_client_secret",
        "private_path",
        "secret_value",
        "deploy_request",
        "client_secret_value",
        "prod_open_pr_flag",
        "external_sns_query_text",
    ],
)
def test_rejects_forbidden_field_prefix_suffix_bypasses(field_name):
    payload = _safe_payload()
    payload[field_name] = "unsafe"

    with pytest.raises(UnsafeSignalError):
        normalize_signal(payload)


def test_allows_safe_synthetic_extra_fields():
    payload = _safe_payload()
    payload["provider_independence_gain"] = "Synthetic product scoring note only."

    signal = normalize_signal(payload)

    assert signal.id == "sample-safe"


@pytest.mark.parametrize(
    "unsafe_value_factory",
    [
        lambda: "sk-" + ("x" * 24),
        lambda: "Q:" + "\\synthetic\\secret.txt",
        lambda: "/root/.config/example",
        lambda: "/etc/example.conf",
        lambda: "/var/log/example.log",
        lambda: "/tmp/example.txt",
        lambda: "/Users/example/private.txt",
        lambda: "/home/example/private.txt",
        lambda: "https://" + "example.invalid/source",
    ],
)
def test_rejects_secret_path_or_live_url_values(unsafe_value_factory):
    payload = _safe_payload()
    payload["evidence"] = [unsafe_value_factory()]

    with pytest.raises(UnsafeSignalError):
        normalize_signal(payload)


def test_rejects_non_dict_signal_payload():
    with pytest.raises(UnsafeSignalError, match="signal payload must be a dictionary"):
        normalize_signal("unsafe")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "unsafe_value"),
    [
        ("source", "live_telemetry_source"),
        ("privacy_class", "personal"),
        ("created_at", "2026-05-19T11:00:00Z"),
    ],
)
def test_rejects_live_source_personal_class_or_exact_timestamp(field_name, unsafe_value):
    payload = _safe_payload()
    payload[field_name] = unsafe_value

    with pytest.raises(UnsafeSignalError):
        normalize_signal(payload)


def test_score_does_not_become_approval():
    signal = normalize_signal(_safe_payload(severity=5, frequency=5))
    proposal = generate_proposal(signal)

    assert proposal.score.priority >= 1
    assert proposal.owner_decision_required is True
    assert proposal.approved is False
    assert "approved: false" in proposal.to_markdown()


def _safe_payload(severity: int = 3, frequency: int = 3) -> dict[str, object]:
    return {
        "id": "sample-safe",
        "source": "synthetic_fixture",
        "kind": "docs_confusion",
        "summary": "Readers need a clearer public-safe capability explanation.",
        "severity": severity,
        "frequency": frequency,
        "evidence": ["Synthetic fixture evidence only."],
        "created_at": "2026-05-19",
        "privacy_class": "synthetic",
        "approval_required": True,
    }
