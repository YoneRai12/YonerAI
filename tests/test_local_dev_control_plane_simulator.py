from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import sys
from pathlib import Path


def _load_local_dev_module():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core.hybrid import local_dev_control_plane

    return local_dev_control_plane


def test_local_dev_control_plane_reports_non_production_status() -> None:
    simulator = _load_local_dev_module()

    status = simulator.build_local_dev_control_plane_status()

    assert status.schema_version == simulator.LOCAL_DEV_CONTROL_PLANE_SCHEMA_VERSION
    assert status.profile == "local_dev_control_plane"
    assert status.official_cloud_stub_available is True
    assert status.official_private_control_plane_ready is False
    assert status.production_trust_material is False
    assert status.network_required is False
    assert status.local_node.non_production is True
    assert status.local_node.trust_material == "test_signed_manifest_only"
    assert status.local_node.verification_state == "present_verified"
    assert status.local_node.signed_origin_verified is True
    assert status.local_node.trusted is False




def test_local_dev_control_plane_status_uses_runtime_time_by_default() -> None:
    simulator = _load_local_dev_module()

    assert simulator.build_local_dev_control_plane_status.__defaults__ is None
    assert simulator.build_local_dev_control_plane_status.__kwdefaults__["now"] is None
def test_local_dev_node_capabilities_are_declared_and_approval_gated() -> None:
    simulator = _load_local_dev_module()

    status = simulator.build_local_dev_control_plane_status()

    assert "private_files" in status.local_node.capabilities
    assert "dangerous_operations" in status.local_node.capabilities
    assert set(status.local_node.capabilities) == set(status.local_node.requires_approval)
    assert set(status.local_node.capabilities) == set(status.local_node.declared_capabilities)
    assert "production_deploy" in status.local_node.disabled
    assert "persistent_memory" in status.local_node.disabled
    assert "live_discord_gateway" in status.local_node.disabled


def test_missing_local_node_keeps_hybrid_private_work_gated() -> None:
    simulator = _load_local_dev_module()

    status = simulator.build_local_dev_control_plane_status(local_node_available=False)
    decision = simulator.preview_route_with_local_dev_control_plane(
        "read my local file",
        mode="official_hybrid_private",
        local_node_available=False,
    )

    assert status.local_node.available is False
    assert status.local_node.verification_state == "missing"
    assert status.local_node.capabilities == ()
    assert decision.route == "local_node_required"
    assert decision.unavailable_reason == "local_node_missing"
    assert decision.local_node_verification_state == "missing"


def test_available_local_node_integrates_with_route_preview() -> None:
    simulator = _load_local_dev_module()

    decision = simulator.preview_route_with_local_dev_control_plane(
        "run a shell command",
        mode="official_hybrid_private",
        local_node_available=True,
    )

    assert decision.route == "hybrid_coordination_preview"
    assert decision.requested_capability == "pc_operations"
    assert decision.local_node_required is True
    assert decision.approval_required is True
    assert decision.dangerous_operation is True
    assert decision.local_node_verification_state == "present_verified"
    assert decision.signed_origin_verified is True


def test_unverified_local_node_denies_declared_private_capabilities() -> None:
    simulator = _load_local_dev_module()

    status = simulator.build_local_dev_control_plane_status(verify_test_manifest=False)
    decision = simulator.preview_route_with_local_dev_control_plane(
        "read my local file",
        mode="official_hybrid_private",
        verify_test_manifest=False,
    )

    assert status.local_node.available is True
    assert status.local_node.verification_state == "present_unverified"
    assert status.local_node.signed_origin_verified is False
    assert status.local_node.capabilities == ()
    assert status.local_node.requires_approval == ()
    assert "signed_manifest_not_verified" in status.local_node.verification_reasons
    assert decision.route == "local_node_required"
    assert decision.unavailable_reason == "unverified_node_denied"
    assert decision.local_node_verification_state == "present_unverified"


def test_expired_manifest_is_rejected_by_local_dev_control_plane() -> None:
    simulator = _load_local_dev_module()
    from ora_core.hybrid import local_node_manifest

    private_key_b64, public_key_b64 = local_node_manifest.generate_test_local_node_keypair()
    manifest = local_node_manifest.build_test_local_node_manifest(expires_at="2026-05-21T01:00:00Z")
    signed = local_node_manifest.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)

    status = simulator.build_local_dev_control_plane_status(
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert status.local_node.verification_state == "expired"
    assert status.local_node.capabilities == ()
    assert "expired_manifest" in status.local_node.verification_reasons


def test_wrong_audience_manifest_is_rejected_by_local_dev_control_plane() -> None:
    simulator = _load_local_dev_module()
    from ora_core.hybrid import local_node_manifest

    private_key_b64, public_key_b64 = local_node_manifest.generate_test_local_node_keypair()
    manifest = local_node_manifest.build_test_local_node_manifest(audience="other-audience")
    signed = local_node_manifest.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)

    status = simulator.build_local_dev_control_plane_status(
        signed_manifest=signed,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert status.local_node.verification_state == "wrong_audience"
    assert status.local_node.capabilities == ()
    assert "wrong_audience" in status.local_node.verification_reasons


def test_tampered_manifest_is_rejected_by_local_dev_control_plane() -> None:
    simulator = _load_local_dev_module()
    from ora_core.hybrid import local_node_manifest

    private_key_b64, public_key_b64 = local_node_manifest.generate_test_local_node_keypair()
    manifest = local_node_manifest.build_test_local_node_manifest()
    signed = local_node_manifest.sign_local_node_manifest(manifest, private_key_b64=private_key_b64)
    tampered = replace(
        signed,
        manifest=replace(
            signed.manifest,
            capabilities=signed.manifest.capabilities + ("unknown.future.capability",),
        ),
    )

    status = simulator.build_local_dev_control_plane_status(
        signed_manifest=tampered,
        public_key_b64=public_key_b64,
        now=datetime(2026, 5, 21, 12, tzinfo=timezone.utc),
    )

    assert status.local_node.verification_state == "invalid_signature"
    assert status.local_node.capabilities == ()
    assert "invalid_signature" in status.local_node.verification_reasons


def test_local_dev_fixture_trust_context_never_claims_production_trust() -> None:
    simulator = _load_local_dev_module()

    context = simulator.build_local_dev_fixture_trust_context()

    assert context["profile"] == "local_dev_control_plane"
    assert context["production_trust_material"] is False
    assert context["signature_algorithm"] == "test-static-signature"
    assert context["registry_entry_exists"] is True
    assert context["verifier_class"] == "StaticSignatureVerifier"
