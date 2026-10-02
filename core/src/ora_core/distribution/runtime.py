from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

from .capabilities import CapabilityManifest, CapabilityPolicy
from .release import ReleaseVerificationError, ReleaseVerificationResult, verify_release_bundle


class TrustedReleaseState(BaseModel):
    schema_version: str = "yonerai-distribution-release-state/v1"
    trusted_version: str | None = None


class DistributionRuntime:
    def __init__(
        self,
        *,
        enabled: bool,
        capability_policy: CapabilityPolicy,
        verification: ReleaseVerificationResult | None = None,
        state_path: str | None = None,
    ):
        self.enabled = enabled
        self.capability_policy = capability_policy
        self.verification = verification
        self.state_path = state_path

    def require_capability(self, capability: str) -> None:
        self.capability_policy.require(capability)

    def require_tool(self, tool_name: str, required_capability: str | None = None) -> None:
        self.capability_policy.require_tool(tool_name, required_capability)


_current_runtime = DistributionRuntime(enabled=False, capability_policy=CapabilityPolicy(enabled=False))


def configure_current_runtime(runtime: DistributionRuntime) -> DistributionRuntime:
    global _current_runtime
    _current_runtime = runtime
    return runtime


def get_current_runtime() -> DistributionRuntime:
    return _current_runtime


def _load_release_state(path: Path) -> TrustedReleaseState:
    if not path.exists():
        return TrustedReleaseState()
    return TrustedReleaseState.model_validate_json(path.read_text(encoding="utf-8"))


def _save_release_state(path: Path, trusted_version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = TrustedReleaseState(trusted_version=trusted_version).model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _truthy_env(name: str) -> bool:
    return str(os.getenv(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def build_runtime_from_env() -> DistributionRuntime:
    enabled = _truthy_env("ORA_DISTRIBUTION_NODE_ENABLE")
    if not enabled:
        return configure_current_runtime(
            DistributionRuntime(enabled=False, capability_policy=CapabilityPolicy(enabled=False))
        )

    capability_manifest_path = os.getenv("ORA_DISTRIBUTION_CAPABILITY_MANIFEST")
    manifest_path = os.getenv("ORA_DISTRIBUTION_RELEASE_MANIFEST")
    provenance_path = os.getenv("ORA_DISTRIBUTION_RELEASE_PROVENANCE")
    signature_path = os.getenv("ORA_DISTRIBUTION_RELEASE_SIGNATURE")
    public_key_b64 = os.getenv("ORA_DISTRIBUTION_RELEASE_PUBLIC_KEY")
    artifact_path = os.getenv("ORA_DISTRIBUTION_RELEASE_ARTIFACT")
    if not all([capability_manifest_path, manifest_path, provenance_path, signature_path, public_key_b64, artifact_path]):
        raise ReleaseVerificationError("Distribution Node MVP is enabled but release verification inputs are incomplete.")

    capability_manifest = CapabilityManifest.from_path(capability_manifest_path)
    policy = CapabilityPolicy(capability_manifest, enabled=True)

    state_path = Path(
        os.getenv("ORA_DISTRIBUTION_RELEASE_STATE", str(Path("data") / "distribution_node_release_state.json"))
    )
    trusted_state = _load_release_state(state_path)
    verification = verify_release_bundle(
        manifest_path=manifest_path,
        provenance_path=provenance_path,
        signature_path=signature_path,
        public_key_b64=public_key_b64,
        capability_manifest_path=capability_manifest_path,
        artifact_path=artifact_path,
        trusted_version=trusted_state.trusted_version,
    )
    _save_release_state(state_path, verification.manifest.version)

    runtime = DistributionRuntime(
        enabled=True,
        capability_policy=policy,
        verification=verification,
        state_path=str(state_path),
    )
    return configure_current_runtime(runtime)
