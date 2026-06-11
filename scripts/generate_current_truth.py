from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMVER_TAG_RE = re.compile(r"^v(?P<version>[0-9]+(?:\.[0-9]+){2}(?:-[0-9A-Za-z.-]+)?)$")
STAGING_API_HOST = "api-staging.yonerai.com"


def _run_git(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def _version_key(version: str) -> tuple[int, int, int, int, str]:
    core, _, suffix = version.partition("-")
    parts: list[int] = []
    for piece in core.split(".")[:3]:
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    prerelease_rank = 0 if suffix else 1
    return (parts[0], parts[1], parts[2], prerelease_rank, suffix)


def _latest_tags() -> tuple[str, str]:
    raw_tags = _run_git(["tag", "--list", "v*", "--sort=version:refname"]).splitlines()
    stable: list[tuple[tuple[int, int, int, int, str], str]] = []
    prerelease: list[tuple[tuple[int, int, int, int, str], str]] = []
    for tag in raw_tags:
        match = SEMVER_TAG_RE.fullmatch(tag.strip())
        if not match:
            continue
        version = match.group("version")
        row = (_version_key(version), tag.strip())
        if "-" in version:
            prerelease.append(row)
        else:
            stable.append(row)
    latest_stable = max(stable)[1] if stable else "unknown"
    latest_prerelease = max(prerelease)[1] if prerelease else "unknown"
    return latest_stable, latest_prerelease


def _main_head_short() -> str:
    for ref in ("public/main", "origin/main", "main", "HEAD"):
        value = _run_git(["rev-parse", "--short", ref])
        if value:
            return value
    return "unknown"


def build_current_truth(*, generated_date: str | None = None) -> str:
    latest_stable, latest_prerelease = _latest_tags()
    date_text = generated_date or dt.datetime.now(dt.UTC).date().isoformat()
    main_head = _main_head_short()
    return "\n".join(
        [
            "# YonerAI Current Truth",
            "",
            "This file is the public anchor that AI lanes should read before making",
            "release, CLI, API, or status claims. It intentionally avoids private",
            "runtime inventory, internal URLs, secrets, local paths, and control-plane",
            "details.",
            "",
            f"- generated_date_utc: {date_text}",
            f"- latest_stable_tag: {latest_stable}",
            f"- latest_prerelease_tag: {latest_prerelease}",
            f"- main_head_short: {main_head}",
            f"- staging_api_base_host: {STAGING_API_HOST}",
            "",
            "## Open Production Blockers",
            "",
            "- Production Google login is not enabled in the public CLI.",
            "- Official Managed Cloud remains external/private and contract-only from",
            "  the public repository.",
            "- Production Oracle/cloud runtime is not included in the public repository.",
            "- Production signing/trust-store validation is not complete.",
            "- Live Discord/token operation is not included.",
            "- Local private memory/file content must not auto-upload.",
            "- OpenAI shared traffic remains disabled by default.",
            "- `agent:run` and `admin:*` scopes are frozen until a separate threat-model",
            "  gate approves them.",
            "",
            "## Required First Read",
            "",
            "AI lanes must read this file together with `AGENTS.md` and",
            "`docs/process/YONERAI_CODEX_WORKFLOW.md` before making public claims.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the public YonerAI CURRENT_TRUTH.md anchor.")
    parser.add_argument("--output", default="CURRENT_TRUTH.md")
    parser.add_argument("--date", help="Override generated_date_utc for deterministic tests.")
    args = parser.parse_args(argv)

    output = ROOT / args.output
    output.write_text(build_current_truth(generated_date=args.date), encoding="utf-8", newline="\n")
    print(output.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
