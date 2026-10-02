from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class CapabilityDeniedError(RuntimeError):
    pass


class CapabilityManifest(BaseModel):
    schema_version: Literal["yonerai-distribution-capabilities/v1"] = (
        "yonerai-distribution-capabilities/v1"
    )
    profile: Literal["distribution_node_mvp"] = "distribution_node_mvp"
    default_action: Literal["deny", "allow"] = "deny"
    capabilities: dict[str, bool] = Field(default_factory=dict)

    @classmethod
    def from_path(cls, path: str | Path) -> "CapabilityManifest":
        raw = Path(path).read_text(encoding="utf-8")
        manifest = cls.model_validate(json.loads(raw))
        if manifest.default_action != "deny":
            raise CapabilityDeniedError("Distribution Node MVP requires capability manifest default_action=deny.")
        return manifest


class CapabilityPolicy:
    def __init__(self, manifest: CapabilityManifest | None = None, *, enabled: bool = False):
        self.manifest = manifest
        self.enabled = enabled

    def is_allowed(self, capability: str) -> bool:
        if not self.enabled:
            return True
        if not self.manifest:
            return False
        if capability in self.manifest.capabilities:
            return bool(self.manifest.capabilities[capability])
        return self.manifest.default_action == "allow"

    def require(self, capability: str) -> None:
        if self.is_allowed(capability):
            return
        raise CapabilityDeniedError(f"Capability '{capability}' is not declared for Distribution Node MVP.")

    def require_tool(self, tool_name: str, required_capability: str | None = None) -> None:
        capability = required_capability or f"tools.{tool_name}"
        if not self.enabled:
            return
        if not self.manifest:
            raise CapabilityDeniedError("Capability policy is unavailable.")
        if capability not in self.manifest.capabilities:
            raise CapabilityDeniedError(
                f"Tool '{tool_name}' has no declared capability in the Distribution Node manifest."
            )
        self.require(capability)
