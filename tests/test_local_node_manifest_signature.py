from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sys
from pathlib import Path


def _load_manifest_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core.hybrid import local_node_manifest

    return local_node_manifest


def _signed_manifest():
    manifest_mod = _load_manifest_module()
    private_key_b64, public_key_b64 = manifest_mod.generate_test_local_node_keypair()
    manifest = manifest_mod.build_test_local_node_manifest()
    signed = manifest_mod.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)
    return manifest_mod, signed, public_key_b64


def test_valid_test_signed_manifest_verifies_without_production_trust() -> None:
    manifest_mod, signed, public_key_b64 = _signed_manifest()

    result = manifest_mod.verify_local_node_manifest(
        signed,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert result.status == "verified"
    assert result.verified is True
    assert result.trusted is False
    assert result.production_trust_material is False
    assert "private_files" in result.declared_capabilities
    assert "dangerous_operations" in result.declared_capabilities
    assert "dangerous_operations" in result.approval_required_capabilities
    assert "manifest_verified_origin_integrity_only" in result.reasons


def test_tampered_manifest_payload_fails_signature_verification() -> None:
    manifest_mod, signed, public_key_b64 = _signed_manifest()
    tampered = replace(
        signed,
        manifest=replace(
            signed.manifest,
            capabilities=signed.manifest.capabilities + ("unknown.future.capability",),
        ),
    )

    result = manifest_mod.verify_local_node_manifest(
        tampered,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert result.status == "invalid_signature"
    assert result.verified is False
    assert result.declared_capabilities == ()
    assert "invalid_signature" in result.reasons


def test_wrong_key_id_fails_before_trust() -> None:
    manifest_mod, signed, public_key_b64 = _signed_manifest()
    wrong_key = replace(signed, signature=replace(signed.signature, key_id="wrong-test-key-id"))

    result = manifest_mod.verify_local_node_manifest(
        wrong_key,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert result.status == "wrong_key_id"
    assert result.verified is False
    assert result.trusted is False
    assert "wrong_key_id" in result.reasons


def test_expired_manifest_fails() -> None:
    manifest_mod, signed, _public_key_b64 = _signed_manifest()
    private_key_b64, public_key_b64 = manifest_mod.generate_test_local_node_keypair()
    expired_manifest = replace(signed.manifest, expires_at="2026-05-21T01:00:00Z")
    expired = manifest_mod.sign_local_node_manifest(expired_manifest, private_key_b64=private_key_b64)

    result = manifest_mod.verify_local_node_manifest(
        expired,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert result.status == "expired"
    assert result.verified is False
    assert "expired_manifest" in result.reasons


def test_wrong_audience_fails() -> None:
    manifest_mod, _signed, _public_key_b64 = _signed_manifest()
    private_key_b64, public_key_b64 = manifest_mod.generate_test_local_node_keypair()
    manifest = manifest_mod.build_test_local_node_manifest(audience="other-audience")
    signed = manifest_mod.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)

    result = manifest_mod.verify_local_node_manifest(
        signed,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert result.status == "wrong_audience"
    assert result.verified is False
    assert "wrong_audience" in result.reasons


def test_unknown_capability_remains_denied_even_with_valid_signature() -> None:
    manifest_mod = _load_manifest_module()
    private_key_b64, public_key_b64 = manifest_mod.generate_test_local_node_keypair()
    manifest = manifest_mod.build_test_local_node_manifest(
        capabilities=("private_files", "unknown.future.capability"),
    )
    signed = manifest_mod.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)

    result = manifest_mod.verify_local_node_manifest(
        signed,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert result.status == "verified"
    assert result.verified is True
    assert result.declared_capabilities == ("private_files",)
    assert result.denied_capabilities == ("unknown.future.capability",)
    assert "unknown_capability_denied" in result.reasons


def test_signed_manifest_does_not_automatically_enable_dangerous_operations() -> None:
    manifest_mod, signed, public_key_b64 = _signed_manifest()

    result = manifest_mod.verify_local_node_manifest(
        signed,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert "dangerous_operations" in result.declared_capabilities
    assert "dangerous_operations" in result.approval_required_capabilities
    assert result.trusted is False
    assert result.production_trust_material is False
