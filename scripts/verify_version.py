import argparse
import re
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
DATEVER_RE = re.compile(r"^\d{4}\.(?:0?[1-9]|1[0-2])\.(?:0?[1-9]|[12]\d|3[01])$")


def normalize_tag(tag: str) -> str:
    tag = tag.strip()
    if tag.startswith("refs/tags/"):
        tag = tag[len("refs/tags/") :]
    if tag.startswith("v"):
        tag = tag[1:]
    return tag


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify VERSION file and optional git tag consistency.")
    parser.add_argument("--tag", default="", help="Tag to verify (e.g. v5.0.0 or refs/tags/v5.0.0)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    version_file = root / "VERSION"
    if not version_file.exists():
        print("[FAIL] VERSION file not found.")
        return 1

    version = version_file.read_text(encoding="utf-8").strip()
    if not (SEMVER_RE.match(version) or DATEVER_RE.match(version)):
        print(f"[FAIL] VERSION '{version}' is not a supported version string (expected X.Y.Z or YYYY.M.D).")
        return 1

    if args.tag:
        tag_version = normalize_tag(args.tag)
        if version != tag_version:
            print(f"[FAIL] VERSION mismatch. VERSION={version} tag={tag_version}")
            return 1
        print(f"[OK] VERSION matches tag: {version}")
    else:
        kind = "SemVer" if SEMVER_RE.match(version) else "DateVer"
        print(f"[OK] VERSION is valid {kind}: {version}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
