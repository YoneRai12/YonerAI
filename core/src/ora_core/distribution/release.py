from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel


UTC = timezone.utc


class ReleaseVerificationError(RuntimeError):
    pass


class ReleaseArtifact(BaseModel):
    path: str
    sha256: str
    size_bytes: int


class ReleaseManifest(BaseModel):
    schema_version: Literal["yonerai-distribution-release-manifest/v1"] = (
        "yonerai-distribution-release-manifest/v1"
    )
    profile: Literal["distribution_node_mvp"] = "distribution_node_mvp"
    product: str
    version: str
    created_at: datetime
    expires_at: datetime
    minimum_supported_version: str | None = None
    capability_manifest_sha256: str
    provenance_sha256: str
    artifact: ReleaseArtifact


class ReleaseProvenance(BaseModel):
    schema_version: Literal["yonerai-distribution-release-provenance/v1"] = (
        "yonerai-distribution-release-provenance/v1"
    )
    profile: Literal["distribution_node_mvp"] = "distribution_node_mvp"
    created_at: datetime
    builder: str
    build_command: str
    git_commit: str | None = None
    source_tree: str = "git"
    artifact_sha256: str
    capability_manifest_sha256: str


class ReleaseSignature(BaseModel):
    schema_version: Literal["yonerai-distribution-release-signature/v1"] = (
        "yonerai-distribution-release-signature/v1"
    )
    algorithm: Literal["ed25519"] = "ed25519"
    key_id: str
    signature_b64: str


class ReleaseVerificationResult(BaseModel):
    manifest: ReleaseManifest
    provenance: ReleaseProvenance
    signature: ReleaseSignature
    trusted_version_before_verify: str | None = None


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _version_key(version: str) -> tuple[int, ...]:
    parts = []
    for raw in str(version or "").replace("-", ".").split("."):
        raw = raw.strip()
        if not raw:
            continue
        if raw.isdigit():
            parts.append(int(raw))
            continue
        digits = "".join(ch for ch in raw if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


def _public_key_from_b64(public_key_b64: str) -> Ed25519PublicKey:
    raw = base64.b64decode(public_key_b64.encode("ascii"))
    return Ed25519PublicKey.from_public_bytes(raw)


def _private_key_from_b64(private_key_b64: str) -> Ed25519PrivateKey:
    raw = base64.b64decode(private_key_b64.encode("ascii"))
    return Ed25519PrivateKey.from_private_bytes(raw)


def _public_key_id(public_key_b64: str) -> str:
    return _sha256_bytes(base64.b64decode(public_key_b64.encode("ascii")))


def generate_ed25519_keypair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(private_raw).decode("ascii"), base64.b64encode(public_raw).decode("ascii")


def build_signed_release_bundle(
    *,
    artifact_path: str | Path,
    version: str,
    product: str,
    capability_manifest_path: str | Path,
    private_key_b64: str,
    out_dir: str | Path,
    expires_in_hours: int = 24,
    minimum_supported_version: str | None = None,
    builder: str | None = None,
    build_command: str | None = None,
    git_commit: str | None = None,
) -> dict[str, Path]:
    artifact = Path(artifact_path)
    capability_manifest = Path(capability_manifest_path)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    capability_sha = sha256_path(capability_manifest)
    artifact_sha = sha256_path(artifact)
    if not git_commit:
        try:
            git_cwd = artifact.parent if (artifact.parent / ".git").exists() else Path.cwd()
            git_commit = (
                subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(git_cwd))
                .decode("utf-8")
                .strip()
            )
        except Exception:
            git_commit = None

    provenance = ReleaseProvenance(
        created_at=now,
        builder=builder or os.getenv("USERNAME") or os.getenv("USER") or "unknown",
        build_command=build_command or "python scripts/create_release.py",
        git_commit=git_commit,
        artifact_sha256=artifact_sha,
        capability_manifest_sha256=capability_sha,
    )
    provenance_payload = provenance.model_dump(mode="json")
    provenance_sha = _sha256_bytes(_canonical_json(provenance_payload))

    manifest = ReleaseManifest(
        product=product,
        version=version,
        created_at=now,
        expires_at=now + timedelta(hours=max(1, int(expires_in_hours))),
        minimum_supported_version=minimum_supported_version,
        capability_manifest_sha256=capability_sha,
        provenance_sha256=provenance_sha,
        artifact=ReleaseArtifact(
            path=artifact.name,
            sha256=artifact_sha,
            size_bytes=artifact.stat().st_size,
        ),
    )
    manifest_payload = manifest.model_dump(mode="json")

    public_key_b64 = base64.b64encode(
        _private_key_from_b64(private_key_b64)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    envelope = {"manifest": manifest_payload, "provenance": provenance_payload}
    signature_raw = _private_key_from_b64(private_key_b64).sign(_canonical_json(envelope))
    signature = ReleaseSignature(
        key_id=_public_key_id(public_key_b64),
        signature_b64=base64.b64encode(signature_raw).decode("ascii"),
    )

    manifest_path = output_dir / "release-manifest.json"
    provenance_path = output_dir / "release-provenance.json"
    signature_path = output_dir / "release-signature.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    provenance_path.write_text(
        json.dumps(provenance_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    signature_path.write_text(
        json.dumps(signature.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "manifest_path": manifest_path,
        "provenance_path": provenance_path,
        "signature_path": signature_path,
    }


def verify_release_bundle(
    *,
    manifest_path: str | Path,
    provenance_path: str | Path,
    signature_path: str | Path,
    public_key_b64: str,
    capability_manifest_path: str | Path,
    artifact_path: str | Path,
    trusted_version: str | None = None,
    now: datetime | None = None,
    future_skew_seconds: int = 300,
) -> ReleaseVerificationResult:
    manifest = ReleaseManifest.model_validate_json(Path(manifest_path).read_text(encoding="utf-8"))
    provenance = ReleaseProvenance.model_validate_json(Path(provenance_path).read_text(encoding="utf-8"))
    signature = ReleaseSignature.model_validate_json(Path(signature_path).read_text(encoding="utf-8"))

    expected_key_id = _public_key_id(public_key_b64)
    if signature.key_id != expected_key_id:
        raise ReleaseVerificationError("Signed metadata key_id does not match the pinned public key.")

    envelope = {
        "manifest": manifest.model_dump(mode="json"),
        "provenance": provenance.model_dump(mode="json"),
    }
    signature_raw = base64.b64decode(signature.signature_b64.encode("ascii"))
    try:
        _public_key_from_b64(public_key_b64).verify(signature_raw, _canonical_json(envelope))
    except InvalidSignature as exc:
        raise ReleaseVerificationError("Signed metadata verification failed.") from exc

    actual_provenance_sha = _sha256_bytes(_canonical_json(provenance.model_dump(mode="json")))
    if actual_provenance_sha != manifest.provenance_sha256:
        raise ReleaseVerificationError("Provenance digest does not match the release manifest.")

    actual_capability_sha = sha256_path(capability_manifest_path)
    if actual_capability_sha != manifest.capability_manifest_sha256:
        raise ReleaseVerificationError("Capability manifest digest does not match the signed release manifest.")

    artifact = Path(artifact_path)
    if sha256_path(artifact) != manifest.artifact.sha256:
        raise ReleaseVerificationError("Artifact digest mismatch.")
    if artifact.stat().st_size != manifest.artifact.size_bytes:
        raise ReleaseVerificationError("Artifact size mismatch.")
    if provenance.artifact_sha256 != manifest.artifact.sha256:
        raise ReleaseVerificationError("Provenance artifact digest mismatch.")

    current_time = now.astimezone(UTC) if now else datetime.now(UTC)
    if manifest.created_at.astimezone(UTC) > current_time + timedelta(seconds=max(0, future_skew_seconds)):
        raise ReleaseVerificationError("Release metadata is from the future.")
    if manifest.expires_at.astimezone(UTC) <= current_time:
        raise ReleaseVerificationError("Release metadata is stale.")

    if trusted_version and _version_key(manifest.version) < _version_key(trusted_version):
        raise ReleaseVerificationError(
            f"Rollback detected: trusted_version={trusted_version} manifest_version={manifest.version}"
        )

    if manifest.minimum_supported_version and _version_key(manifest.version) < _version_key(
        manifest.minimum_supported_version
    ):
        raise ReleaseVerificationError("Release version is below minimum_supported_version.")

    return ReleaseVerificationResult(
        manifest=manifest,
        provenance=provenance,
        signature=signature,
        trusted_version_before_verify=trusted_version,
    )
