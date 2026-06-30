from __future__ import annotations

from datetime import datetime, timezone

from scripts import yonerai_release_gate as gate
from scripts.yonerai_release_gate import (
    Blocker,
    build_report,
    blocks_public_release,
    check_issue_552,
    issue_comment_tags,
    latest_tag,
    scan_overclaim_text,
    standalone_tag,
)


def test_standalone_tag_accepts_first_line_tag() -> None:
    assert standalone_tag("[PUBLIC-SYNC-CLIENT-READY]\n\nbody") == "[PUBLIC-SYNC-CLIENT-READY]"


def test_standalone_tag_rejects_status_summary_mentions() -> None:
    assert standalone_tag("- [ ] [PUBLIC-SYNC-CLIENT-READY] missing") is None
    assert standalone_tag("> [PUBLIC-SYNC-CLIENT-READY]") is None
    assert standalone_tag("[PUBLIC-SYNC-CLIENT-READY] missing") is None


def test_issue_comment_tags_use_latest_timestamp() -> None:
    issue = {
        "comments": [
            {"body": "[PUBLIC-SYNC-CLIENT-READY]\nold", "createdAt": "2026-06-30T18:00:00Z", "url": "old"},
            {"body": "[PUBLIC-SYNC-CLIENT-READY]\nnew", "createdAt": "2026-06-30T18:34:09Z", "url": "new"},
        ]
    }

    tags = issue_comment_tags(issue)
    latest = latest_tag(tags, "[PUBLIC-SYNC-CLIENT-READY]")

    assert latest is not None
    assert latest["created_at"] == datetime(2026, 6, 30, 18, 34, 9, tzinfo=timezone.utc)
    assert latest["url"] == "new"


def test_check_issue_552_rejects_blocker_inside_passing_window(monkeypatch) -> None:
    issue = {
        "url": "issue-url",
        "comments": [
            {"body": "[AWS-OWNER-SYNC-SMOKE-READY]\nready", "createdAt": "2026-06-30T18:00:00Z", "url": "ready"},
            {
                "body": "[YONERAIWEB-SYNC-CLIENT-READY]\nweb",
                "createdAt": "2026-06-30T18:01:00Z",
                "url": "web",
            },
            {
                "body": "[PUBLIC-SYNC-CLIENT-READY]\npublic",
                "createdAt": "2026-06-30T18:02:00Z",
                "url": "public",
            },
            {
                "body": "[AWS-OWNER-SYNC-SMOKE-BLOCKED]\nrollback",
                "createdAt": "2026-06-30T18:03:00Z",
                "url": "blocked",
            },
            {
                "body": "[WEB-TO-CLI-E2E-PASSED]\npassed",
                "createdAt": "2026-06-30T18:04:00Z",
                "url": "passed",
            },
        ],
    }
    monkeypatch.setattr(gate, "_gh_json", lambda _args: issue)

    blockers = check_issue_552("repo")

    assert any(blocker.kind == "stale_e2e" and blocker.url == "blocked" for blocker in blockers)


def test_check_issue_552_rejects_generic_blocker_tag_after_pass(monkeypatch) -> None:
    issue = {
        "url": "issue-url",
        "comments": [
            {"body": "[AWS-OWNER-SYNC-SMOKE-READY]\nready", "createdAt": "2026-06-30T18:00:00Z", "url": "ready"},
            {
                "body": "[YONERAIWEB-SYNC-CLIENT-READY]\nweb",
                "createdAt": "2026-06-30T18:01:00Z",
                "url": "web",
            },
            {
                "body": "[PUBLIC-SYNC-CLIENT-READY]\npublic",
                "createdAt": "2026-06-30T18:02:00Z",
                "url": "public",
            },
            {
                "body": "[WEB-TO-CLI-E2E-PASSED]\npassed",
                "createdAt": "2026-06-30T18:03:00Z",
                "url": "passed",
            },
            {
                "body": "[AWS-PUBLIC-ALLOWLIST-BLOCKER]\nblocked",
                "createdAt": "2026-06-30T18:04:00Z",
                "url": "generic-blocker",
            },
        ],
    }
    monkeypatch.setattr(gate, "_gh_json", lambda _args: issue)

    blockers = check_issue_552("repo")

    assert any(blocker.kind == "stale_e2e" and blocker.url == "generic-blocker" for blocker in blockers)


def test_check_issue_552_does_not_invalidate_e2e_for_phase_b_blocker(monkeypatch) -> None:
    issue = {
        "url": "issue-url",
        "comments": [
            {"body": "[AWS-OWNER-SYNC-SMOKE-READY]\nready", "createdAt": "2026-06-30T18:00:00Z", "url": "ready"},
            {
                "body": "[YONERAIWEB-SYNC-CLIENT-READY]\nweb",
                "createdAt": "2026-06-30T18:01:00Z",
                "url": "web",
            },
            {
                "body": "[PUBLIC-SYNC-CLIENT-READY]\npublic",
                "createdAt": "2026-06-30T18:02:00Z",
                "url": "public",
            },
            {
                "body": "[WEB-TO-CLI-E2E-PASSED]\npassed",
                "createdAt": "2026-06-30T18:03:00Z",
                "url": "passed",
            },
            {
                "body": "[PUBLIC-NATIVE-RUN-WINDOWS-WORKER-BLOCKED]\nphase b",
                "createdAt": "2026-06-30T18:04:00Z",
                "url": "phase-b",
            },
        ],
    }
    monkeypatch.setattr(gate, "_gh_json", lambda _args: issue)

    blockers = check_issue_552("repo")

    assert not any(blocker.kind == "stale_e2e" for blocker in blockers)


def test_public_release_go_ignores_non_public_repo_blockers(monkeypatch) -> None:
    def fake_check_open_prs(repo: str) -> list[Blocker]:
        if repo == gate.PUBLIC_REPO:
            return []
        return [Blocker(repo, "open_pr_label", "p1", "private release gate remains open", f"https://example.invalid/{repo}")]

    monkeypatch.setattr(gate, "check_issue_552", lambda _repo: [])
    monkeypatch.setattr(gate, "check_release_issue", lambda _repo, _issue: ([], {"number": 592, "url": "issue"}))
    monkeypatch.setattr(gate, "check_open_prs", fake_check_open_prs)
    monkeypatch.setattr(gate, "check_pr150", lambda _repo: [Blocker(_repo, "aws_pr_150", "p1", "not merged", "pr")])
    monkeypatch.setattr(gate, "check_agents_presence", lambda _repos: [])
    monkeypatch.setattr(gate, "check_release_notes", lambda _path: [])

    report = build_report()

    assert report["release_go"] is True
    assert report["safe_to_start_phase_b"] is False
    assert report["blockers"]
    assert all(item["blocks_public_release"] is False for item in report["blockers"])


def test_public_release_go_blocks_public_repo_blockers(monkeypatch) -> None:
    monkeypatch.setattr(gate, "check_issue_552", lambda _repo: [])
    monkeypatch.setattr(
        gate,
        "check_release_issue",
        lambda repo, _issue: ([Blocker(repo, "release_checklist", "p1", "Public release notes unchecked", "issue")], {}),
    )
    monkeypatch.setattr(gate, "check_open_prs", lambda _repo: [])
    monkeypatch.setattr(gate, "check_pr150", lambda _repo: [])
    monkeypatch.setattr(gate, "check_agents_presence", lambda _repos: [])
    monkeypatch.setattr(gate, "check_release_notes", lambda _path: [])

    report = build_report()

    assert report["release_go"] is False
    assert report["safe_to_start_phase_b"] is False
    assert report["blockers"][0]["blocks_public_release"] is True


def test_release_checklist_classifies_cross_repo_items_as_non_public_release_blockers() -> None:
    aws_item = Blocker(
        gate.PUBLIC_REPO,
        "release_checklist",
        "p1",
        "unchecked release gate item: - [ ] AWS PR #150 merged to main",
        "issue",
    )
    web_item = Blocker(
        gate.PUBLIC_REPO,
        "release_checklist",
        "p1",
        "unchecked release gate item: - [ ] YonerAIWEB governance cleanup remains tracked",
        "issue",
    )
    phase_b_item = Blocker(
        gate.PUBLIC_REPO,
        "release_checklist",
        "p1",
        "unchecked release gate item: - [ ] Phase B issue opened only after release",
        "issue",
    )
    oracle_item = Blocker(
        gate.PUBLIC_REPO,
        "release_checklist",
        "p1",
        "unchecked release gate item: - [ ] Oracle DB migration completed",
        "issue",
    )
    aws_release_note_item = Blocker(
        gate.PUBLIC_REPO,
        "release_checklist",
        "p1",
        "unchecked release gate item: - [ ] AWS release notes checked for no overclaim",
        "issue",
    )
    public_item = Blocker(
        gate.PUBLIC_REPO,
        "release_checklist",
        "p1",
        "unchecked release gate item: - [ ] Release notes checked for no overclaim",
        "issue",
    )

    assert blocks_public_release(aws_item, gate.PUBLIC_REPO) is False
    assert blocks_public_release(web_item, gate.PUBLIC_REPO) is False
    assert blocks_public_release(phase_b_item, gate.PUBLIC_REPO) is False
    assert blocks_public_release(oracle_item, gate.PUBLIC_REPO) is False
    assert blocks_public_release(aws_release_note_item, gate.PUBLIC_REPO) is False
    assert blocks_public_release(public_item, gate.PUBLIC_REPO) is True


def test_scan_overclaim_text_blocks_positive_claims() -> None:
    findings = scan_overclaim_text("This release is production ready and public sync ready.")

    assert "production ready" in findings
    assert "public sync ready" in findings


def test_scan_overclaim_text_allows_negative_non_claims() -> None:
    findings = scan_overclaim_text("This is not production ready. No general sync ready claim is made.")

    assert findings == []


def test_scan_overclaim_text_allows_forbidden_claim_lists() -> None:
    findings = scan_overclaim_text(
        "This release gate does not approve production readiness, public sync ready, or AI chat ready claims."
    )

    assert findings == []


def test_scan_overclaim_text_allows_do_not_claim_lists() -> None:
    findings = scan_overclaim_text(
        "Do not claim production-ready, shipping-complete, Discord restored, or Tools/MCP complete."
    )

    assert findings == []


def test_scan_overclaim_text_blocks_positive_claim_after_semicolon_negation() -> None:
    findings = scan_overclaim_text("Not production ready; public sync ready.")

    assert "public sync ready" in findings


def test_scan_overclaim_text_blocks_positive_claim_after_prior_sentence_negation() -> None:
    findings = scan_overclaim_text("This is not ready. It is production ready.")

    assert "production ready" in findings


def test_scan_overclaim_text_blocks_positive_claim_after_conjunction_negation() -> None:
    findings = scan_overclaim_text("No production-ready claim and public sync ready. Not production ready but AI chat ready.")

    assert "public sync ready" in findings
    assert "ai chat ready" in findings


def test_scan_overclaim_text_blocks_agents_forbidden_claims() -> None:
    findings = scan_overclaim_text(
        "Discord restored. Google login complete. Tools/MCP complete. v7.8 started."
    )

    assert "discord restored" in findings
    assert "google login complete" in findings
    assert "tools/mcp complete" in findings
    assert "v7.8 started" in findings
