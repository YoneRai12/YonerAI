import argparse
import re
import sys
from pathlib import Path


SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|(?=[0-9A-Za-z-]*[A-Za-z-])[0-9A-Za-z-]+)"
    r"(?:\.(?:0|[1-9]\d*|(?=[0-9A-Za-z-]*[A-Za-z-])[0-9A-Za-z-]+))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
DATEVER_RE = re.compile(r"^\d{4}\.(?:0?[1-9]|1[0-2])\.(?:0?[1-9]|[12]\d|3[01])$")


def is_supported_version(version: str) -> bool:
    return bool(DATEVER_RE.match(version) or SEMVER_RE.match(version))


def version_kind(version: str) -> str:
    if DATEVER_RE.match(version):
        return "DateVer"
    if SEMVER_RE.match(version):
        return "SemVer"
    return "Unsupported"


def normalize_tag(tag: str) -> str:
    tag = tag.strip()
    if tag.startswith("refs/tags/"):
        tag = tag[len("refs/tags/") :]
    if tag.startswith("v"):
        tag = tag[1:]
    return tag


def verify_version_value(version: str, tag: str = "") -> tuple[bool, str]:
    version = version.strip()
    if not is_supported_version(version):
        return (
            False,
            f"[FAIL] VERSION '{version}' is not a supported version string "
            "(expected X.Y.Z, X.Y.Z-prerelease, or YYYY.M.D).",
        )

    if tag:
        tag_version = normalize_tag(tag)
        if version != tag_version:
            return False, f"[FAIL] VERSION mismatch. VERSION={version} tag={tag_version}"
        return True, f"[OK] VERSION matches tag: {version}"

    return True, f"[OK] VERSION is valid {version_kind(version)}: {version}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify VERSION file and optional git tag consistency.")
    parser.add_argument("--tag", default="", help="Tag to verify (e.g. v5.0.0 or refs/tags/v5.0.0)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    version_file = root / "VERSION"
    if not version_file.exists():
        print("[FAIL] VERSION file not found.")
        return 1

    ok, message = verify_version_value(version_file.read_text(encoding="utf-8"), args.tag)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
