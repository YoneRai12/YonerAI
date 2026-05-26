from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|(?=[0-9A-Za-z-]*[A-Za-z-])[0-9A-Za-z-]+)"
    r"(?:\.(?:0|[1-9]\d*|(?=[0-9A-Za-z-]*[A-Za-z-])[0-9A-Za-z-]+))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
DATEVER_RE = re.compile(r"^\d{4}\.(?:0?[1-9]|1[0-2])\.(?:0?[1-9]|[12]\d|3[01])$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
BLOCKER_RE = re.compile(r"\b(UNRESOLVED_P0|UNRESOLVED_P1|SECURITY_BLOCKER|RELEASE_BLOCKER)\b", re.IGNORECASE)
MUTABLE_ARTIFACT_RE = re.compile(r"(latest|main|source)\.zip$", re.IGNORECASE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Block unsafe or incomplete YonerAI GitHub releases.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Default: current directory.")
    parser.add_argument("--tag", help="Release tag to validate. Defaults to v<VERSION>.")
    parser.add_argument("--artifact", help="Generated local release asset to hash and compare.")
    parser.add_argument(
        "--github-prerelease",
        choices=("true", "false", "auto"),
        default="auto",
        help="GitHub Release prerelease flag. Default: infer from VERSION.",
    )
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    errors = validate_release_gate(
        repo_root=repo_root,
        tag=args.tag,
        artifact=Path(args.artifact) if args.artifact else None,
        github_prerelease=args.github_prerelease,
    )
    if errors:
        print("[FAIL] YonerAI release gate blocked release:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("[OK] YonerAI release gate passed.")
    return 0


def validate_release_gate(
    *,
    repo_root: Path,
    tag: str | None = None,
    artifact: Path | None = None,
    github_prerelease: str = "auto",
) -> list[str]:
    errors: list[str] = []
    version = _read_text(repo_root / "VERSION", errors, "VERSION")
    product = _read_text(repo_root / "PRODUCT_NAME", errors, "PRODUCT_NAME") or "YonerAI"
    if not version:
        return errors
    expected_tag = f"v{version}"
    actual_tag = tag or expected_tag
    if actual_tag != expected_tag:
        errors.append(f"VERSION/tag mismatch: VERSION={version} tag={actual_tag}")
    if not _is_supported_version(version):
        errors.append(f"VERSION is not supported by release gate: {version}")

    release_note = repo_root / "docs" / "releases" / f"{version}.md"
    if not release_note.exists():
        errors.append(f"release note missing: {release_note.relative_to(repo_root)}")
    else:
        _validate_release_note(release_note, errors)

    manifest_path = repo_root / "releases" / f"manifest.v{version}.json"
    manifest = _load_manifest(manifest_path, errors, repo_root)
    if manifest:
        _validate_manifest(version, product, manifest, errors)

    artifact_path = (repo_root / artifact).resolve() if artifact and not artifact.is_absolute() else artifact
    if artifact_path is not None:
        _validate_artifact(version, product, artifact_path, manifest, errors)

    expected_prerelease = _is_prerelease(version)
    if github_prerelease != "auto":
        actual_prerelease = github_prerelease == "true"
        if actual_prerelease != expected_prerelease:
            errors.append(
                f"GitHub prerelease mismatch: VERSION expects prerelease={str(expected_prerelease).lower()} "
                f"but workflow provided {github_prerelease}"
            )
    return errors


def _read_text(path: Path, errors: list[str], label: str) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        errors.append(f"{label} file missing or unreadable: {path}")
        return ""


def _validate_release_note(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    for index, line in enumerate(text.splitlines(), 1):
        lower = line.lower()
        if BLOCKER_RE.search(line):
            errors.append(f"release note contains unresolved blocker marker at {path.name}:{index}")
        if "production-ready" in lower and not _is_negated_claim(lower, "production-ready"):
            errors.append(f"release note overclaims production readiness at {path.name}:{index}")
        positive_overclaims = (
            "official cloud runnable",
            "official cloud complete",
            "full hybrid complete",
            "discord restored",
            "installer ready",
            "npm/winget ready",
        )
        for phrase in positive_overclaims:
            if phrase in lower and not _is_negated_claim(lower, phrase):
                errors.append(f"release note overclaims '{phrase}' at {path.name}:{index}")


def _is_negated_claim(line: str, phrase: str) -> bool:
    normalized = line.lstrip("-*+ \t")
    phrase_index = normalized.find(phrase)
    if phrase_index < 0:
        return False
    prefix = normalized[:phrase_index].strip()
    if not prefix:
        return False
    return bool(
        re.search(
            r"(?:^|\b)(?:no|not|never|without|cannot|can't|do not|don't|does not|doesn't|must not)\b",
            prefix,
        )
    )


def _load_manifest(path: Path, errors: list[str], repo_root: Path) -> dict[str, Any] | None:
    if not path.exists():
        errors.append(f"release manifest missing: {path.relative_to(repo_root)}")
        return None
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"release manifest is not JSON: {path.name}: {exc}")
        return None
    if not isinstance(manifest, dict):
        errors.append(f"release manifest must be a JSON object: {path.name}")
        return None
    return manifest


def _validate_manifest(version: str, product: str, manifest: dict[str, Any], errors: list[str]) -> None:
    if manifest.get("version") != version:
        errors.append(f"manifest version mismatch: {manifest.get('version')} != {version}")
    release = manifest.get("release") if isinstance(manifest.get("release"), dict) else {}
    if release.get("tag") != f"v{version}":
        errors.append(f"manifest release tag mismatch: {release.get('tag')} != v{version}")
    if manifest.get("production_ready") is not False:
        errors.append("public release manifest must keep production_ready=false")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("manifest must contain at least one artifact")
        return
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append("manifest artifact entry must be an object")
            continue
        url = str(artifact.get("url") or "")
        filename = url.rsplit("/", 1)[-1]
        kind = str(artifact.get("kind") or "")
        target = str(artifact.get("target") or "")
        expected = _expected_artifact_name(product, version, kind, target)
        if expected and filename != expected:
            errors.append(f"artifact filename must be versioned: expected {expected}, got {filename}")
        if MUTABLE_ARTIFACT_RE.search(filename):
            errors.append(f"artifact filename must not be mutable: {filename}")
        sha256 = artifact.get("sha256")
        if not isinstance(sha256, str) or SHA256_RE.fullmatch(sha256) is None:
            errors.append(f"artifact {artifact.get('id') or filename} sha256 is missing or invalid")
        signature = artifact.get("signature") if isinstance(artifact.get("signature"), dict) else {}
        if signature.get("status") == "signed" and signature.get("algorithm") == "none":
            errors.append(f"artifact {artifact.get('id') or filename} cannot be signed with algorithm=none")


def _validate_artifact(
    version: str,
    product: str,
    artifact_path: Path,
    manifest: dict[str, Any] | None,
    errors: list[str],
) -> None:
    expected_name = f"{product}-{version}.zip"
    if artifact_path.name != expected_name:
        errors.append(f"release asset name must be {expected_name}, got {artifact_path.name}")
    if not artifact_path.exists():
        errors.append(f"release asset missing: {artifact_path}")
        return
    digest = _sha256_file(artifact_path)
    size = artifact_path.stat().st_size
    if manifest is None:
        return
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), list) else []
    matching = [
        artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and str(artifact.get("url") or "").rsplit("/", 1)[-1] == artifact_path.name
    ]
    if not matching:
        errors.append(f"manifest has no artifact entry for release asset {artifact_path.name}")
        return
    artifact = matching[0]
    if artifact.get("sha256") != digest:
        errors.append(f"release asset sha256 mismatch for {artifact_path.name}")
    if artifact.get("size_bytes") != size:
        errors.append(f"release asset size mismatch for {artifact_path.name}")


def _expected_artifact_name(product: str, version: str, kind: str, target: str) -> str | None:
    if kind == "source_archive" and target == "source-any":
        return f"{product}-{version}.zip"
    if kind == "windows_zip" and target == "windows-x64":
        return f"{product}-{version}-windows-x64.zip"
    if kind == "manifest" and target == "universal-any":
        return f"{product}-{version}-manifest.json"
    return None


def _is_prerelease(version: str) -> bool:
    return "-" in version.split("+", 1)[0]


def _is_supported_version(version: str) -> bool:
    return bool(SEMVER_RE.fullmatch(version) or DATEVER_RE.fullmatch(version))


def _sha256_file(path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
