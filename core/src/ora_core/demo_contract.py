from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


YONERAI_DEMO_CONTRACT_VERSION = "yonerai-public-demo/v1"
YONERAI_DEMO_SCHEMA_VERSION = "1.0"

DemoSectionName = Literal[
    "public_core",
    "mode_boundary",
    "route_preview",
    "provider_planner",
    "execution_spine",
    "hybrid_trust",
    "managed_download",
    "self_evolution",
    "limitations",
]

DEMO_SECTION_ORDER: tuple[DemoSectionName, ...] = (
    "public_core",
    "mode_boundary",
    "route_preview",
    "provider_planner",
    "execution_spine",
    "hybrid_trust",
    "managed_download",
    "self_evolution",
    "limitations",
)

DEMO_LIMITATIONS: tuple[str, ...] = (
    "no_production_oracle",
    "no_live_discord",
    "no_persistent_memory",
    "local_memory_opt_in_only",
    "no_google_login",
    "no_deploy",
    "no_official_cloud_runtime_in_public_repo",
    "no_external_provider_live_generation",
    "no_live_provider_by_default",
    "installer_dry_run_only",
    "proposal_only_self_evolution",
)


@dataclass(frozen=True)
class YoneraiDemoSection:
    name: DemoSectionName
    status: str
    summary: str
    checks: tuple[dict[str, object], ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["checks"] = [dict(check) for check in self.checks]
        return payload


@dataclass(frozen=True)
class YoneraiDemoResult:
    ok: bool
    contract: str
    schema_version: str
    sections: tuple[YoneraiDemoSection, ...]
    limitations: tuple[str, ...]
    cli_entrypoint: str = "yonerai demo"
    quickstart_alias: str = "yonerai quickstart"
    credentials_required: bool = False
    network_required: bool = False
    oracle_required: bool = False
    live_discord_required: bool = False
    persistent_memory_required: bool = False
    google_login_required: bool = False
    deploy_required: bool = False
    official_cloud_runtime_included: bool = False
    production_trust_material: bool = False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "contract": self.contract,
            "schema_version": self.schema_version,
            "cli_entrypoint": self.cli_entrypoint,
            "quickstart_alias": self.quickstart_alias,
            "credentials_required": self.credentials_required,
            "network_required": self.network_required,
            "oracle_required": self.oracle_required,
            "live_discord_required": self.live_discord_required,
            "persistent_memory_required": self.persistent_memory_required,
            "google_login_required": self.google_login_required,
            "deploy_required": self.deploy_required,
            "official_cloud_runtime_included": self.official_cloud_runtime_included,
            "production_trust_material": self.production_trust_material,
            "sections": [section.to_public_dict() for section in self.sections],
            "limitations": list(self.limitations),
        }


def build_demo_section(
    name: DemoSectionName,
    *,
    summary: str,
    checks: tuple[dict[str, object], ...],
    status: str = "ok",
) -> YoneraiDemoSection:
    return YoneraiDemoSection(name=name, status=status, summary=summary, checks=checks)


def build_demo_result(sections: tuple[YoneraiDemoSection, ...]) -> YoneraiDemoResult:
    _assert_demo_sections(sections)
    return YoneraiDemoResult(
        ok=all(section.status == "ok" for section in sections),
        contract=YONERAI_DEMO_CONTRACT_VERSION,
        schema_version=YONERAI_DEMO_SCHEMA_VERSION,
        sections=sections,
        limitations=DEMO_LIMITATIONS,
    )


def _assert_demo_sections(sections: tuple[YoneraiDemoSection, ...]) -> None:
    names = tuple(section.name for section in sections)
    if names != DEMO_SECTION_ORDER:
        raise ValueError("demo sections must match the public demo contract order")
    for section in sections:
        if not section.checks:
            raise ValueError(f"demo section must include at least one check: {section.name}")
