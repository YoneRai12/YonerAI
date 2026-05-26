from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.release_gate import validate_release_gate


def _write_release_fixture(tmp_path: Path, *, version: str = "1.2.3-alpha.1", note: str | None = None) -> Path:
    product = "YonerAI"
    repo = tmp_path / "repo"
    (repo / "docs" / "releases").mkdir(parents=True)
    (repo / "releases").mkdir(parents=True)
    (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
    (repo / "PRODUCT_NAME").write_text(product + "\n", encoding="utf-8")
    artifact = repo / f"{product}-{version}.zip"
    artifact.write_bytes(b"release fixture")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    (repo / "docs" / "releases" / f"{version}.md").write_text(
        note
        or f"# 2026.05.27 - YonerAI v{version} test\n\nNot production-ready.\nNo official cloud runtime.\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "yonerai-installer-bootstrap-manifest/v1",
        "product": product,
        "channel": "alpha" if "alpha" in version else "stable",
        "version": version,
        "published_at": "2026-05-27T00:00:00Z",
        "production_ready": False,
        "release": {
            "tag": f"v{version}",
            "github_release_url": f"https://github.com/YoneRai12/YonerAI/releases/tag/v{version}",
            "manifest_status": "unsigned_example",
        },
        "minimum_requirements": {"python": ">=3.11", "windows": "10 or newer", "network_required": False},
        "artifacts": [
            {
                "id": f"yonerai-{version}-source-archive",
                "kind": "source_archive",
                "target": "source-any",
                "os": "any",
                "arch": "any",
                "url": f"https://github.com/YoneRai12/YonerAI/releases/download/v{version}/{artifact.name}",
                "sha256": digest,
                "size_bytes": artifact.stat().st_size,
                "signature": {
                    "status": "placeholder_non_production",
                    "algorithm": "none",
                    "key_id": "PLACEHOLDER_NON_PRODUCTION_KEY",
                    "signature": "PLACEHOLDER_NON_PRODUCTION_SIGNATURE",
                },
            }
        ],
    }
    (repo / "releases" / f"manifest.v{version}.json").write_text(json.dumps(manifest), encoding="utf-8")
    return repo


def test_release_gate_accepts_versioned_manifest_and_matching_asset(tmp_path: Path) -> None:
    repo = _write_release_fixture(tmp_path)

    errors = validate_release_gate(
        repo_root=repo,
        tag="v1.2.3-alpha.1",
        artifact=repo / "YonerAI-1.2.3-alpha.1.zip",
        github_prerelease="true",
    )

    assert errors == []


def test_release_gate_blocks_tag_version_mismatch(tmp_path: Path) -> None:
    repo = _write_release_fixture(tmp_path)

    errors = validate_release_gate(
        repo_root=repo,
        tag="v1.2.3-alpha.2",
        artifact=repo / "YonerAI-1.2.3-alpha.1.zip",
        github_prerelease="true",
    )

    assert any("VERSION/tag mismatch" in error for error in errors)


def test_release_gate_blocks_mutable_or_unversioned_asset_name(tmp_path: Path) -> None:
    repo = _write_release_fixture(tmp_path)
    manifest_path = repo / "releases" / "manifest.v1.2.3-alpha.1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0]["url"] = "https://github.com/YoneRai12/YonerAI/releases/download/v1.2.3-alpha.1/YonerAI-latest.zip"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_release_gate(repo_root=repo, tag="v1.2.3-alpha.1", github_prerelease="true")

    assert any("artifact filename must be versioned" in error for error in errors)
    assert any("must not be mutable" in error for error in errors)


def test_release_gate_blocks_sha256_mismatch(tmp_path: Path) -> None:
    repo = _write_release_fixture(tmp_path)
    manifest_path = repo / "releases" / "manifest.v1.2.3-alpha.1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_release_gate(
        repo_root=repo,
        tag="v1.2.3-alpha.1",
        artifact=repo / "YonerAI-1.2.3-alpha.1.zip",
        github_prerelease="true",
    )

    assert any("sha256 mismatch" in error for error in errors)


def test_release_gate_blocks_prerelease_flag_mismatch(tmp_path: Path) -> None:
    repo = _write_release_fixture(tmp_path)

    errors = validate_release_gate(
        repo_root=repo,
        tag="v1.2.3-alpha.1",
        artifact=repo / "YonerAI-1.2.3-alpha.1.zip",
        github_prerelease="false",
    )

    assert any("GitHub prerelease mismatch" in error for error in errors)


def test_release_gate_blocks_positive_production_overclaim(tmp_path: Path) -> None:
    repo = _write_release_fixture(tmp_path, note="# Release\n\nThis is production-ready.\n")

    errors = validate_release_gate(repo_root=repo, tag="v1.2.3-alpha.1", github_prerelease="true")

    assert any("overclaims production readiness" in error for error in errors)
