from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PUBLIC_REPO = "YoneRai12/YonerAI"
AWS_REPO = "YoneRai12/YonerAI-oracle-control-plane"
WEB_REPO = "YoneRai12/YonerAIWEB"

REQUIRED_SYNC_TAGS = (
    "[AWS-OWNER-SYNC-SMOKE-READY]",
    "[YONERAIWEB-SYNC-CLIENT-READY]",
    "[PUBLIC-SYNC-CLIENT-READY]",
    "[WEB-TO-CLI-E2E-PASSED]",
)

ROLLBACK_OR_BLOCKER_TAGS = (
    "[AWS-OWNER-SYNC-SMOKE-BLOCKED]",
    "[AWS-SYNC-SMOKE-BLOCKED]",
    "[AWS-SYNC-SMOKE-GATE-BLOCKED]",
    "[PRIVATE-AWS-SMOKE-BLOCKED]",
    "[PUBLIC-SYNC-CLIENT-BLOCKED]",
    "[YONERAIWEB-SYNC-SENDER-BLOCKED]",
    "[REVIEW-BLOCKER]",
)

POST_E2E_NON_INVALIDATING_BLOCKER_TAGS = (
    "[PUBLIC-NATIVE-RUN-WINDOWS-WORKER-BLOCKED]",
)

BLOCKER_LABELS = {
    "release-blocker",
    "state:release-gate",
    "state:blocked",
    "severity:p0",
    "severity:p1",
    "p0",
    "p1",
    "security",
}

PUBLIC_RELEASE_BLOCKING_SEVERITIES = {"p0", "p1", "security"}
PUBLIC_RELEASE_CHECKLIST_MARKERS = (
    "public main",
    "public release",
    "release note",
    "tag/release",
)
NON_PUBLIC_RELEASE_CHECKLIST_MARKERS = (
    "aws ",
    "aws-",
    "yoneraiweb",
    "oracle",
    "cross-repo",
    "phase b",
    "private repo",
    "private repository",
)

OVERCLAIM_PATTERNS = (
    "production ready",
    "production-ready",
    "shipping complete",
    "shipping-complete",
    "official cloud complete",
    "official-cloud complete",
    "discord restored",
    "persistent memory complete",
    "google login complete",
    "final web ui complete",
    "tools/mcp complete",
    "full hybrid complete",
    "src/cogs/ora.py solved",
    "broad ora rename complete",
    "v7.8 started",
    "general sync ready",
    "public sync ready",
    "ai chat ready",
)


@dataclass(frozen=True)
class Blocker:
    repo: str
    kind: str
    severity: str
    reason: str
    url: str

    def as_dict(self) -> dict[str, str]:
        return {
            "repo": self.repo,
            "kind": self.kind,
            "severity": self.severity,
            "reason": self.reason,
            "url": self.url,
        }


def public_release_checklist_markers() -> tuple[str, ...]:
    try:
        version = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        version = ""
    if not version:
        return PUBLIC_RELEASE_CHECKLIST_MARKERS
    return (*PUBLIC_RELEASE_CHECKLIST_MARKERS, f"v{version} tag")


def blocks_public_release(blocker: Blocker, public_repo: str) -> bool:
    if blocker.severity not in PUBLIC_RELEASE_BLOCKING_SEVERITIES:
        return False
    if blocker.repo != public_repo:
        return False
    if blocker.kind == "release_checklist":
        lowered = blocker.reason.lower()
        if any(marker in lowered for marker in NON_PUBLIC_RELEASE_CHECKLIST_MARKERS):
            return False
        if any(marker in lowered for marker in public_release_checklist_markers()):
            return True
    return True


def blocks_phase_b(blocker: Blocker) -> bool:
    return blocker.severity in PUBLIC_RELEASE_BLOCKING_SEVERITIES


def _blocker_report(blocker: Blocker, public_repo: str) -> dict[str, Any]:
    payload = blocker.as_dict()
    payload["blocks_public_release"] = blocks_public_release(blocker, public_repo)
    return payload


def _run_gh(args: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode, completed.stdout, completed.stderr


def _gh_json(args: list[str]) -> Any:
    code, stdout, stderr = _run_gh(args)
    if code != 0:
        raise RuntimeError(stderr.strip() or stdout.strip() or f"gh command failed: {' '.join(args)}")
    if not stdout.strip():
        return None
    return json.loads(stdout)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def standalone_tag(text: str) -> str | None:
    line = first_non_empty_line(text)
    lowered = line.lower()
    if not line.startswith("[") or not line.endswith("]"):
        return None
    if line.startswith(("> ", "- ", "* ", "|")):
        return None
    if any(word in lowered for word in ("missing", "waiting for", "expected", "blocked until")):
        return None
    return line


def issue_comment_tags(issue: dict[str, Any]) -> list[dict[str, Any]]:
    tags: list[dict[str, Any]] = []
    for comment in issue.get("comments", []) or []:
        tag = standalone_tag(str(comment.get("body") or ""))
        if tag:
            tags.append(
                {
                    "tag": tag,
                    "created_at": _parse_time(comment.get("createdAt")),
                    "url": str(comment.get("url") or issue.get("url") or ""),
                }
            )
    return tags


def latest_tag(tags: list[dict[str, Any]], expected: str) -> dict[str, Any] | None:
    matches = [item for item in tags if item.get("tag") == expected and item.get("created_at") is not None]
    if not matches:
        return None
    return max(matches, key=lambda item: item["created_at"])


def is_rollback_or_blocker_tag(tag: str) -> bool:
    normalized = tag.upper()
    if tag in POST_E2E_NON_INVALIDATING_BLOCKER_TAGS:
        return False
    return (
        tag in ROLLBACK_OR_BLOCKER_TAGS
        or normalized.endswith("-BLOCKED]")
        or normalized.endswith("-BLOCKER]")
    )


def scan_overclaim_text(text: str) -> list[str]:
    findings: list[str] = []
    lowered = text.lower()
    for phrase in OVERCLAIM_PATTERNS:
        start = 0
        while True:
            index = lowered.find(phrase, start)
            if index < 0:
                break
            sentence_start = max(
                lowered.rfind(".", 0, index),
                lowered.rfind("\n", 0, index),
                lowered.rfind(":", 0, index),
                lowered.rfind(";", 0, index),
            )
            sentence_prefix = lowered[sentence_start + 1 : index]
            clause_start = max(
                sentence_start,
                lowered.rfind(",", 0, index),
                lowered.rfind(" and ", 0, index),
                lowered.rfind(" but ", 0, index),
                lowered.rfind(" or ", 0, index),
                lowered.rfind(" yet ", 0, index),
            )
            clause_prefix = lowered[clause_start + 1 : index]
            local_negation = re.search(r"\b(no|not|without|does not|do not|is not|not a)\b", clause_prefix)
            governing_negative = re.search(r"\b(forbidden|does not approve|do not claim)\b", sentence_prefix)
            if not (local_negation or governing_negative):
                findings.append(phrase)
                break
            start = index + len(phrase)
    return findings


def check_issue_552(public_repo: str) -> list[Blocker]:
    blockers: list[Blocker] = []
    issue = _gh_json(
        [
            "issue",
            "view",
            "552",
            "--repo",
            public_repo,
            "--json",
            "comments,url,state,title",
        ]
    )
    tags = issue_comment_tags(issue)
    by_tag = {item["tag"] for item in tags}
    for required in REQUIRED_SYNC_TAGS:
        if required not in by_tag:
            blockers.append(
                Blocker(public_repo, "issue_marker", "p1", f"missing required issue #552 marker {required}", issue["url"])
            )

    ready = latest_tag(tags, "[AWS-OWNER-SYNC-SMOKE-READY]")
    web = latest_tag(tags, "[YONERAIWEB-SYNC-CLIENT-READY]")
    public = latest_tag(tags, "[PUBLIC-SYNC-CLIENT-READY]")
    passed = latest_tag(tags, "[WEB-TO-CLI-E2E-PASSED]")
    if ready and web and public and passed:
        if not (ready["created_at"] <= web["created_at"] <= passed["created_at"]):
            blockers.append(
                Blocker(public_repo, "same_window", "p1", "YonerAIWEB ready tag is not in the passing window", web["url"])
            )
        if not (ready["created_at"] <= public["created_at"] <= passed["created_at"]):
            blockers.append(
                Blocker(public_repo, "same_window", "p1", "Public ready tag is not in the passing window", public["url"])
            )
        later = [
            item
            for item in tags
            if is_rollback_or_blocker_tag(str(item.get("tag") or ""))
            and item.get("created_at")
            and item["created_at"] > passed["created_at"]
        ]
        if later:
            latest = max(later, key=lambda item: item["created_at"])
            blockers.append(
                Blocker(public_repo, "stale_e2e", "p1", f"later rollback/blocker marker exists: {latest['tag']}", latest["url"])
            )
        window_blockers = [
            item
            for item in tags
            if is_rollback_or_blocker_tag(str(item.get("tag") or ""))
            and item.get("created_at")
            and ready["created_at"] < item["created_at"] < passed["created_at"]
        ]
        if window_blockers:
            latest = max(window_blockers, key=lambda item: item["created_at"])
            blockers.append(
                Blocker(
                    public_repo,
                    "stale_e2e",
                    "p1",
                    f"rollback/blocker marker exists inside passing window: {latest['tag']}",
                    latest["url"],
                )
            )
    return blockers


def find_release_issue(public_repo: str, release_issue: int | None) -> dict[str, Any] | None:
    if release_issue is not None:
        return _gh_json(
            [
                "issue",
                "view",
                str(release_issue),
                "--repo",
                public_repo,
                "--json",
                "number,title,body,state,url,labels",
            ]
        )
    issues = _gh_json(
        [
            "issue",
            "list",
            "--repo",
            public_repo,
            "--state",
            "all",
            "--search",
            "v0.23",
            "--limit",
            "50",
            "--json",
            "number,title,body,state,url,labels",
        ]
    )
    for issue in issues:
        title = str(issue.get("title") or "").lower()
        if "release gate" in title and "v0.23" in title:
            return issue
    return None


def check_release_issue(public_repo: str, release_issue: int | None) -> tuple[list[Blocker], dict[str, Any] | None]:
    issue = find_release_issue(public_repo, release_issue)
    if issue is None:
        return [
            Blocker(public_repo, "release_issue", "p1", "v0.23 Release Gate issue was not found", "")
        ], None
    blockers: list[Blocker] = []
    body = str(issue.get("body") or "")
    unchecked = [line.strip() for line in body.splitlines() if re.search(r"^- \[ \]", line.strip())]
    for line in unchecked:
        blockers.append(Blocker(public_repo, "release_checklist", "p1", f"unchecked release gate item: {line}", issue["url"]))
    for phrase in scan_overclaim_text(body):
        blockers.append(Blocker(public_repo, "release_overclaim", "p1", f"release issue body overclaims: {phrase}", issue["url"]))
    if str(issue.get("state") or "").upper() != "OPEN":
        blockers.append(Blocker(public_repo, "release_issue", "p2", "v0.23 Release Gate issue is not open", issue["url"]))
    return blockers, issue


def _label_names(pr: dict[str, Any]) -> set[str]:
    return {str(label.get("name") or "").lower() for label in pr.get("labels", []) or []}


def _status_failures(pr: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    latest_by_name: dict[str, dict[str, Any]] = {}
    for check in pr.get("statusCheckRollup", []) or []:
        name = str(check.get("name") or "unknown")
        current = latest_by_name.get(name)
        current_time = _parse_time(str(current.get("completedAt") or "")) if current else None
        check_time = _parse_time(str(check.get("completedAt") or ""))
        if current is None:
            latest_by_name[name] = check
        elif check_time is None:
            latest_by_name[name] = check
        elif current_time is not None and check_time >= current_time:
            latest_by_name[name] = check
    for check in latest_by_name.values():
        status = str(check.get("status") or "")
        conclusion = str(check.get("conclusion") or "")
        name = str(check.get("name") or "unknown")
        if status != "COMPLETED":
            failures.append(f"{name}: {status.lower()}")
        elif conclusion not in ("SUCCESS", "SKIPPED", "NEUTRAL"):
            failures.append(f"{name}: {conclusion.lower()}")
    return failures


def check_open_prs(repo: str) -> list[Blocker]:
    prs = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,url,labels,isDraft,reviewDecision,statusCheckRollup",
        ]
    )
    blockers: list[Blocker] = []
    for pr in prs:
        labels = _label_names(pr)
        matching = sorted(labels & BLOCKER_LABELS)
        if matching:
            blockers.append(
                Blocker(repo, "open_pr_label", "p1", f"open PR #{pr['number']} has blocker label(s): {', '.join(matching)}", pr["url"])
            )
        if str(pr.get("reviewDecision") or "") == "CHANGES_REQUESTED":
            blockers.append(
                Blocker(repo, "review_decision", "p1", f"open PR #{pr['number']} has changes requested", pr["url"])
            )
        if matching:
            failures = _status_failures(pr)
            for failure in failures:
                blockers.append(Blocker(repo, "ci_state", "p1", f"open PR #{pr['number']} check not green: {failure}", pr["url"]))
    return blockers


def check_pr150(aws_repo: str) -> list[Blocker]:
    try:
        pr = _gh_json(
            [
                "pr",
                "view",
                "150",
                "--repo",
                aws_repo,
                "--json",
                "number,title,state,mergedAt,url,mergeStateStatus,statusCheckRollup,reviewDecision",
            ]
        )
    except RuntimeError as exc:
        return [Blocker(aws_repo, "aws_pr_150", "p1", f"cannot read AWS PR #150: {exc}", "")]
    if str(pr.get("state") or "").upper() != "MERGED" or not pr.get("mergedAt"):
        return [Blocker(aws_repo, "aws_pr_150", "p1", "AWS Web sender contract PR #150 is not merged", pr["url"])]
    return []


def check_agents_presence(repos: list[str]) -> list[Blocker]:
    blockers: list[Blocker] = []
    for repo in repos:
        code, stdout, stderr = _run_gh(["api", f"repos/{repo}/contents/AGENTS.md?ref=main"])
        if code != 0:
            reason = stderr.strip() or stdout.strip() or "AGENTS.md not readable on main"
            blockers.append(Blocker(repo, "agents_presence", "p2", reason, f"https://github.com/{repo}"))
    return blockers


def check_release_notes(path: Path | None) -> list[Blocker]:
    if path is None:
        return []
    if not path.exists():
        return [Blocker(PUBLIC_REPO, "release_notes", "p1", f"release notes draft not found: {path}", "")]
    blockers: list[Blocker] = []
    text = path.read_text(encoding="utf-8")
    for phrase in scan_overclaim_text(text):
        blockers.append(Blocker(PUBLIC_REPO, "release_overclaim", "p1", f"release notes overclaims: {phrase}", str(path)))
    return blockers


def _extend_or_github_access(blockers: list[Blocker], repo: str, collect: Any) -> None:
    try:
        blockers.extend(collect())
    except RuntimeError as exc:
        blockers.append(Blocker(repo, "github_access", "p1", str(exc), f"https://github.com/{repo}"))


def build_report(
    *,
    public_repo: str = PUBLIC_REPO,
    aws_repo: str = AWS_REPO,
    web_repo: str = WEB_REPO,
    release_issue: int | None = None,
    release_notes: Path | None = None,
) -> dict[str, Any]:
    blockers: list[Blocker] = []
    _extend_or_github_access(blockers, public_repo, lambda: check_issue_552(public_repo))
    try:
        release_issue_blockers, issue = check_release_issue(public_repo, release_issue)
        blockers.extend(release_issue_blockers)
    except RuntimeError as exc:
        issue = None
        blockers.append(Blocker(public_repo, "github_access", "p1", str(exc), f"https://github.com/{public_repo}"))
    _extend_or_github_access(blockers, public_repo, lambda: check_open_prs(public_repo))
    _extend_or_github_access(blockers, aws_repo, lambda: check_open_prs(aws_repo))
    _extend_or_github_access(blockers, web_repo, lambda: check_open_prs(web_repo))
    _extend_or_github_access(blockers, aws_repo, lambda: check_pr150(aws_repo))
    blockers.extend(check_agents_presence([public_repo, aws_repo, web_repo]))
    blockers.extend(check_release_notes(release_notes))

    release_go = not any(blocks_public_release(blocker, public_repo) for blocker in blockers)
    safe_to_start_phase_b = not any(blocks_phase_b(blocker) for blocker in blockers)
    return {
        "release_go": release_go,
        "safe_to_start_phase_b": safe_to_start_phase_b,
        "release_gate_issue": None if issue is None else {"number": issue.get("number"), "url": issue.get("url")},
        "blockers": [_blocker_report(blocker, public_repo) for blocker in blockers],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only cross-repo YonerAI v0.23 release gate checker.")
    parser.add_argument("--public-repo", default=PUBLIC_REPO)
    parser.add_argument("--aws-repo", default=AWS_REPO)
    parser.add_argument("--web-repo", default=WEB_REPO)
    parser.add_argument("--release-issue", type=int, default=None)
    parser.add_argument("--release-notes", type=Path, default=None)
    parser.add_argument("--fail-on-blockers", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = build_report(
            public_repo=args.public_repo,
            aws_repo=args.aws_repo,
            web_repo=args.web_repo,
            release_issue=args.release_issue,
            release_notes=args.release_notes,
        )
    except RuntimeError as exc:
        blocker = Blocker(PUBLIC_REPO, "github_access", "p1", str(exc), "")
        report = {
            "release_go": False,
            "safe_to_start_phase_b": False,
            "blockers": [_blocker_report(blocker, PUBLIC_REPO)],
        }
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    if args.fail_on_blockers and not report.get("release_go"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
