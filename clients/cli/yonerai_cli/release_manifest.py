from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


SCHEMA_VERSION = "yonerai-installer-bootstrap-manifest/v1"
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
URL_RE = re.compile(r"^(https://github\.com/YoneRai12/YonerAI/releases/download/|https://example\.invalid/)")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

CHANNELS = {"alpha", "beta", "rc", "stable"}
MANIFEST_STATUSES = {"example_placeholder", "unsigned_example", "signed"}
ARTIFACT_KINDS = {"source_archive", "windows_zip", "cli_package", "manifest"}
ARTIFACT_TARGETS = {
    "source-any",
    "windows-x64",
    "windows-arm64",
    "linux-x64",
    "linux-arm64",
    "macos-x64",
    "macos-arm64",
    "universal-any",
}
ARTIFACT_OSES = {"windows", "linux", "macos", "any"}
ARTIFACT_ARCHES = {"x64", "arm64", "universal", "any"}
SIGNATURE_STATUSES = {"signed", "placeholder_non_production"}
SIGNATURE_ALGORITHMS = {"ed25519", "none"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ArtifactCheck:
    artifact_id: str
    status: str
    expected_sha256: str
    actual_sha256: str | None = None
    expected_size_bytes: int | None = None
    actual_size_bytes: int | None = None
    reason: str | None = None


def load_manifest_file(path_text: str) -> dict[str, Any]:
    if _looks_like_url(path_text):
        raise ManifestError("manifest path must be a local file; remote URLs are not fetched.")
    path = Path(path_text)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError("manifest file could not be read.") from exc
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError("manifest file is not valid JSON.") from exc
    if not isinstance(manifest, dict):
        raise ManifestError("manifest JSON must be an object.")
    return manifest


def verify_manifest(
    manifest: dict[str, Any],
    *,
    artifact_paths: dict[str, str] | None = None,
    require_signed: bool = False,
) -> dict[str, Any]:
    errors = validate_manifest_contract(manifest)
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    artifact_list = artifacts if isinstance(artifacts, list) else []
    artifact_checks = _verify_artifacts(artifact_list, artifact_paths or {})
    errors.extend(check.reason for check in artifact_checks if check.status == "failed" and check.reason)

    signature_state = _signature_state(artifact_list)
    if require_signed and signature_state != "signed":
        errors.append("manifest is not fully signed.")

    contract_valid = not errors
    install_ready = (
        contract_valid
        and signature_state == "signed"
        and artifact_checks != []
        and all(check.status == "verified" for check in artifact_checks)
    )
    return {
        "ok": contract_valid,
        "contract_valid": contract_valid,
        "install_ready": install_ready,
        "schema_version": manifest.get("schema_version"),
        "product": manifest.get("product"),
        "channel": manifest.get("channel"),
        "version": manifest.get("version"),
        "release_tag": _release_value(manifest, "tag"),
        "manifest_status": _release_value(manifest, "manifest_status"),
        "production_ready": manifest.get("production_ready"),
        "signature_state": signature_state,
        "signature_verified": signature_state == "signed",
        "network_required": _minimum_value(manifest, "network_required"),
        "artifact_count": len(artifact_list),
        "artifact_checks": [
            {
                "artifact_id": check.artifact_id,
                "status": check.status,
                "expected_sha256": check.expected_sha256,
                "actual_sha256": check.actual_sha256,
                "expected_size_bytes": check.expected_size_bytes,
                "actual_size_bytes": check.actual_size_bytes,
                "reason": check.reason,
            }
            for check in artifact_checks
        ],
        "errors": errors,
        "non_production_reason": None if signature_state == "signed" else "signature_not_production_verified",
    }


def validate_manifest_contract(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed_top = {
        "schema_version",
        "product",
        "channel",
        "version",
        "published_at",
        "production_ready",
        "release",
        "minimum_requirements",
        "artifacts",
    }
    _check_keys(manifest, allowed_top, allowed_top, "manifest", errors)
    _expect(manifest.get("schema_version") == SCHEMA_VERSION, "schema_version is invalid.", errors)
    _expect(manifest.get("product") == "YonerAI", "product must be YonerAI.", errors)
    _expect(manifest.get("channel") in CHANNELS, "channel is invalid.", errors)
    _expect(isinstance(manifest.get("version"), str) and SEMVER_RE.match(manifest["version"]), "version is invalid.", errors)
    _expect(isinstance(manifest.get("published_at"), str), "published_at is required.", errors)
    _expect(isinstance(manifest.get("production_ready"), bool), "production_ready must be boolean.", errors)

    release = manifest.get("release")
    if not isinstance(release, dict):
        errors.append("release must be an object.")
    else:
        allowed = {"tag", "github_release_url", "manifest_status"}
        _check_keys(release, allowed, allowed, "release", errors)
        _expect(isinstance(release.get("tag"), str) and TAG_RE.match(release["tag"]), "release tag is invalid.", errors)
        _expect(
            isinstance(release.get("github_release_url"), str)
            and release["github_release_url"].startswith("https://github.com/YoneRai12/YonerAI/releases/tag/v"),
            "release URL is invalid.",
            errors,
        )
        _expect(release.get("manifest_status") in MANIFEST_STATUSES, "manifest_status is invalid.", errors)

    minimum = manifest.get("minimum_requirements")
    if not isinstance(minimum, dict):
        errors.append("minimum_requirements must be an object.")
    else:
        allowed = {"python", "windows", "network_required"}
        _check_keys(minimum, allowed, allowed, "minimum_requirements", errors)
        _expect(isinstance(minimum.get("python"), str), "minimum python requirement is invalid.", errors)
        _expect(isinstance(minimum.get("windows"), str), "minimum windows requirement is invalid.", errors)
        _expect(isinstance(minimum.get("network_required"), bool), "network_required must be boolean.", errors)

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("artifacts must be a non-empty array.")
    else:
        for index, artifact in enumerate(artifacts):
            _validate_artifact(artifact, index, bool(manifest.get("production_ready")), errors)
    return errors


def parse_artifact_args(values: list[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ManifestError("artifact mapping must use ARTIFACT_ID=LOCAL_FILE.")
        artifact_id, local_file = value.split("=", 1)
        artifact_id = artifact_id.strip()
        local_file = local_file.strip()
        if not ID_RE.match(artifact_id):
            raise ManifestError("artifact id is invalid.")
        if not local_file:
            raise ManifestError("artifact path must not be empty.")
        if _looks_like_url(local_file):
            raise ManifestError("artifact path must be a local file; remote URLs are not fetched.")
        result[artifact_id] = local_file
    return result


def format_manifest_verify_pretty(
    report: dict[str, Any],
    *,
    lang: str = "en",
    color: ColorMode = "auto",
) -> str:
    if lang == "ja":
        sections = _manifest_sections_ja(report)
        title = "YonerAI マニフェスト検証"
    else:
        sections = _manifest_sections_en(report)
        title = "YonerAI manifest verification"
    if report.get("errors"):
        error_title = "エラー" if lang == "ja" else "Errors"
        sections = (*sections, CliSection(error_title, tuple(CliRow("error", error, "fail") for error in report["errors"])))
    return render_report(title, sections, color=color)


def _manifest_sections_en(report: dict[str, Any]) -> tuple[CliSection, ...]:
    artifact_checks = tuple(
        CliRow(
            str(check["artifact_id"]),
            check["status"],
            "ok" if check["status"] == "verified" else "fail",
            note=check.get("reason"),
        )
        for check in report.get("artifact_checks", [])
    )
    return (
        CliSection(
            "Contract",
            (
                CliRow("contract_valid", report["contract_valid"], "ok" if report["contract_valid"] else "fail"),
                CliRow("install_ready", report["install_ready"], "ok" if report["install_ready"] else "warn"),
                CliRow("product", report.get("product"), "ok"),
                CliRow("version", report.get("version"), "ok"),
                CliRow("channel", report.get("channel"), "ok" if report.get("channel") in CHANNELS else "fail"),
                CliRow("release_tag", report.get("release_tag"), "ok"),
                CliRow("artifact_count", report.get("artifact_count"), "ok" if report.get("artifact_count") else "fail"),
            ),
        ),
        CliSection(
            "Security",
            (
                CliRow("sha256_present", bool(report.get("artifact_count")), "ok" if report.get("artifact_count") else "fail"),
                CliRow("signature_state", report.get("signature_state"), "ok" if report.get("signature_state") == "signed" else "warn"),
                CliRow("signature_verified", report.get("signature_verified"), "ok" if report.get("signature_verified") else "warn"),
                CliRow("non_production_reason", report.get("non_production_reason") or "none", "warn" if report.get("non_production_reason") else "ok"),
            ),
        ),
        CliSection(
            "Execution boundary",
            (
                CliRow("network_required", report.get("network_required"), "fail" if report.get("network_required") else "ok"),
                CliRow("download_performed", False, "ok"),
                CliRow("install_performed", False, "ok"),
            ),
        ),
        CliSection("Artifact checks", artifact_checks),
    )


def _manifest_sections_ja(report: dict[str, Any]) -> tuple[CliSection, ...]:
    artifact_checks = tuple(
        CliRow(
            str(check["artifact_id"]),
            "検証済み" if check["status"] == "verified" else "失敗",
            "ok" if check["status"] == "verified" else "fail",
            note=check.get("reason"),
        )
        for check in report.get("artifact_checks", [])
    )
    return (
        CliSection(
            "契約",
            (
                CliRow("契約", "有効" if report["contract_valid"] else "無効", "ok" if report["contract_valid"] else "fail"),
                CliRow("インストール準備", "完了" if report["install_ready"] else "未完了", "ok" if report["install_ready"] else "warn"),
                CliRow("プロダクト", report.get("product"), "ok"),
                CliRow("バージョン", report.get("version"), "ok"),
                CliRow("チャンネル", report.get("channel"), "ok" if report.get("channel") in CHANNELS else "fail"),
                CliRow("リリースタグ", report.get("release_tag"), "ok"),
                CliRow("成果物数", report.get("artifact_count"), "ok" if report.get("artifact_count") else "fail"),
            ),
        ),
        CliSection(
            "セキュリティ",
            (
                CliRow("SHA256", "あり" if report.get("artifact_count") else "なし", "ok" if report.get("artifact_count") else "fail"),
                CliRow("署名状態", report.get("signature_state"), "ok" if report.get("signature_state") == "signed" else "warn"),
                CliRow("署名検証", "済み" if report.get("signature_verified") else "未検証", "ok" if report.get("signature_verified") else "warn"),
                CliRow("非本番理由", report.get("non_production_reason") or "なし", "warn" if report.get("non_production_reason") else "ok"),
            ),
        ),
        CliSection(
            "実行境界",
            (
                CliRow("ネットワーク", "不要" if not report.get("network_required") else "必要", "ok" if not report.get("network_required") else "fail"),
                CliRow("ダウンロード", "実行しません", "ok"),
                CliRow("インストール", "実行しません", "ok"),
            ),
        ),
        CliSection("成果物チェック", artifact_checks),
    )


def _validate_artifact(artifact: object, index: int, production_ready: bool, errors: list[str]) -> None:
    if not isinstance(artifact, dict):
        errors.append(f"artifact {index} must be an object.")
        return
    allowed = {"id", "kind", "target", "os", "arch", "url", "sha256", "size_bytes", "signature"}
    _check_keys(artifact, allowed, allowed, f"artifact {index}", errors)
    _expect(isinstance(artifact.get("id"), str) and ID_RE.match(artifact["id"]), f"artifact {index} id is invalid.", errors)
    _expect(artifact.get("kind") in ARTIFACT_KINDS, f"artifact {index} kind is invalid.", errors)
    _expect(artifact.get("target") in ARTIFACT_TARGETS, f"artifact {index} target is invalid.", errors)
    _expect(artifact.get("os") in ARTIFACT_OSES, f"artifact {index} os is invalid.", errors)
    _expect(artifact.get("arch") in ARTIFACT_ARCHES, f"artifact {index} arch is invalid.", errors)
    _expect(isinstance(artifact.get("url"), str) and URL_RE.match(artifact["url"]), f"artifact {index} url is invalid.", errors)
    _expect(
        isinstance(artifact.get("sha256"), str) and SHA256_RE.match(artifact["sha256"]),
        f"artifact {index} sha256 is invalid.",
        errors,
    )
    _expect(isinstance(artifact.get("size_bytes"), int) and artifact["size_bytes"] > 0, f"artifact {index} size is invalid.", errors)
    signature = artifact.get("signature")
    if not isinstance(signature, dict):
        errors.append(f"artifact {index} signature must be an object.")
        return
    allowed_sig = {"status", "algorithm", "key_id", "signature"}
    _check_keys(signature, allowed_sig, allowed_sig, f"artifact {index} signature", errors)
    status = signature.get("status")
    algorithm = signature.get("algorithm")
    _expect(status in SIGNATURE_STATUSES, f"artifact {index} signature status is invalid.", errors)
    _expect(algorithm in SIGNATURE_ALGORITHMS, f"artifact {index} signature algorithm is invalid.", errors)
    _expect(isinstance(signature.get("key_id"), str), f"artifact {index} signature key_id is invalid.", errors)
    _expect(isinstance(signature.get("signature"), str), f"artifact {index} signature value is invalid.", errors)
    if status == "placeholder_non_production":
        _expect(not production_ready, f"artifact {index} placeholder signature requires non-production manifest.", errors)
        _expect(algorithm == "none", f"artifact {index} placeholder signature must use algorithm none.", errors)


def _verify_artifacts(artifacts: list[object], artifact_paths: dict[str, str]) -> list[ArtifactCheck]:
    by_id = {artifact.get("id"): artifact for artifact in artifacts if isinstance(artifact, dict) and isinstance(artifact.get("id"), str)}
    checks: list[ArtifactCheck] = []
    for artifact_id, local_path in artifact_paths.items():
        artifact = by_id.get(artifact_id)
        if not isinstance(artifact, dict):
            checks.append(ArtifactCheck(artifact_id, "failed", "", reason="artifact_id_not_in_manifest"))
            continue
        expected_sha = str(artifact.get("sha256", ""))
        expected_size = artifact.get("size_bytes") if isinstance(artifact.get("size_bytes"), int) else None
        try:
            actual_sha, actual_size = _hash_file(Path(local_path))
        except OSError:
            checks.append(ArtifactCheck(artifact_id, "failed", expected_sha, expected_size_bytes=expected_size, reason="artifact_file_unreadable"))
            continue
        if actual_sha != expected_sha:
            checks.append(
                ArtifactCheck(
                    artifact_id,
                    "failed",
                    expected_sha,
                    actual_sha256=actual_sha,
                    expected_size_bytes=expected_size,
                    actual_size_bytes=actual_size,
                    reason="sha256_mismatch",
                )
            )
            continue
        if expected_size is not None and actual_size != expected_size:
            checks.append(
                ArtifactCheck(
                    artifact_id,
                    "failed",
                    expected_sha,
                    actual_sha256=actual_sha,
                    expected_size_bytes=expected_size,
                    actual_size_bytes=actual_size,
                    reason="size_mismatch",
                )
            )
            continue
        checks.append(
            ArtifactCheck(
                artifact_id,
                "verified",
                expected_sha,
                actual_sha256=actual_sha,
                expected_size_bytes=expected_size,
                actual_size_bytes=actual_size,
            )
        )
    return checks


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _signature_state(artifacts: list[object]) -> str:
    if not artifacts:
        return "missing"
    statuses: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            statuses.append("invalid")
            continue
        signature = artifact.get("signature")
        if not isinstance(signature, dict):
            statuses.append("missing")
            continue
        statuses.append(str(signature.get("status")))
    if all(status == "signed" for status in statuses):
        return "signed"
    if any(status == "placeholder_non_production" for status in statuses):
        return "placeholder_non_production"
    return "invalid"


def _check_keys(value: dict[str, Any], required: set[str], allowed: set[str], name: str, errors: list[str]) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - allowed)
    if missing:
        errors.append(f"{name} missing fields: {', '.join(missing)}.")
    if extra:
        errors.append(f"{name} has unknown fields: {', '.join(extra)}.")


def _expect(condition: object, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _looks_like_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith(("http://", "https://"))


def _release_value(manifest: dict[str, Any], key: str) -> Any:
    release = manifest.get("release")
    return release.get(key) if isinstance(release, dict) else None


def _minimum_value(manifest: dict[str, Any], key: str) -> Any:
    minimum = manifest.get("minimum_requirements")
    return minimum.get(key) if isinstance(minimum, dict) else None


def _bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
