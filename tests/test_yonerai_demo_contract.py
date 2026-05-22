from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _load_demo_contract():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    if str(core_src) not in sys.path:
        sys.path.insert(0, str(core_src))

    from ora_core import demo_contract

    return demo_contract


def test_yonerai_demo_contract_shape_and_boundaries() -> None:
    demo_contract = _load_demo_contract()
    sections = tuple(
        demo_contract.build_demo_section(
            name,
            summary=f"{name} summary",
            checks=({"name": f"{name}_check", "status": "ok"},),
        )
        for name in demo_contract.DEMO_SECTION_ORDER
    )

    result = demo_contract.build_demo_result(sections).to_public_dict()

    assert result["ok"] is True
    assert result["contract"] == "yonerai-public-demo/v1"
    assert result["schema_version"] == "1.0"
    assert result["cli_entrypoint"] == "yonerai demo"
    assert result["quickstart_alias"] == "yonerai quickstart"
    assert [section["name"] for section in result["sections"]] == [
        "public_core",
        "mode_boundary",
        "route_preview",
        "provider_planner",
        "hybrid_trust",
        "managed_download",
        "self_evolution",
        "limitations",
    ]
    assert result["credentials_required"] is False
    assert result["network_required"] is False
    assert result["oracle_required"] is False
    assert result["live_discord_required"] is False
    assert result["persistent_memory_required"] is False
    assert result["google_login_required"] is False
    assert result["deploy_required"] is False
    assert result["official_cloud_runtime_included"] is False
    assert result["production_trust_material"] is False
    assert set(result["limitations"]) >= {
        "no_production_oracle",
        "no_live_discord",
        "no_persistent_memory",
        "no_google_login",
        "no_official_cloud_runtime_in_public_repo",
        "proposal_only_self_evolution",
    }


def test_yonerai_demo_contract_rejects_missing_or_reordered_sections() -> None:
    demo_contract = _load_demo_contract()
    missing = tuple(
        demo_contract.build_demo_section(
            name,
            summary=f"{name} summary",
            checks=({"name": f"{name}_check", "status": "ok"},),
        )
        for name in demo_contract.DEMO_SECTION_ORDER[:-1]
    )
    reordered = tuple(reversed(missing + (demo_contract.build_demo_section(
        "limitations",
        summary="limitations summary",
        checks=({"name": "limitations_check", "status": "ok"},),
    ),)))

    with pytest.raises(ValueError, match="demo sections"):
        demo_contract.build_demo_result(missing)
    with pytest.raises(ValueError, match="demo sections"):
        demo_contract.build_demo_result(reordered)


def test_yonerai_demo_contract_requires_checks_per_section() -> None:
    demo_contract = _load_demo_contract()
    sections = tuple(
        demo_contract.build_demo_section(
            name,
            summary=f"{name} summary",
            checks=() if name == "public_core" else ({"name": f"{name}_check", "status": "ok"},),
        )
        for name in demo_contract.DEMO_SECTION_ORDER
    )

    with pytest.raises(ValueError, match="public_core"):
        demo_contract.build_demo_result(sections)
