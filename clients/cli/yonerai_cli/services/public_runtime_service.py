from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any


def _base_non_actions() -> list[str]:
    return [
        "no live Discord",
        "no production Oracle",
        "no official cloud runtime",
        "no provider key output",
        "no local file read",
        "no shell execution",
        "no install",
        "no PATH mutation",
    ]


def build_packaged_demo_report() -> dict[str, Any]:
    return {
        "ok": True,
        "contract": "yonerai-public-demo/v1",
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "cli_entrypoint": "yonerai demo",
        "quickstart_alias": "yonerai quickstart",
        "source": "packaged_cli_fallback",
        "sections": [
            {
                "name": "packaged_cli",
                "status": "ok",
                "checks": [
                    {"name": "cli_import", "status": "ok"},
                    {"name": "interactive_entrypoint", "status": "available"},
                    {"name": "policy_status", "status": "available"},
                ],
            },
            {
                "name": "limitations",
                "status": "contract_only",
                "checks": [
                    {"name": "deep_repo_smoke", "status": "not_available_without_repo_scripts"},
                    {"name": "production_cloud", "status": "not_included"},
                    {"name": "live_discord", "status": "not_included"},
                ],
            },
        ],
        "official_cloud_runtime_included": False,
        "oracle_required": False,
        "live_discord_required": False,
        "persistent_memory_required": False,
        "actions_not_performed": _base_non_actions(),
    }


def build_packaged_smoke_report() -> dict[str, Any]:
    return {
        "ok": True,
        "contract": "public-mvp-smoke-0.5",
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": "packaged_cli_fallback",
        "checks": [
            {"name": "cli_package", "status": "ok"},
            {"name": "demo_fallback", "status": "ok"},
            {"name": "repo_deep_smoke", "status": "not_available_without_repo_scripts"},
        ],
        "production_oracle_included": False,
        "official_cloud_runtime_included": False,
        "live_discord_required": False,
        "actions_not_performed": _base_non_actions(),
    }


def _print_pretty(title: str, report: dict[str, Any]) -> None:
    print(title)
    print(f"  ok: {str(report.get('ok')).lower()}")
    print(f"  source: {report.get('source')}")
    print("  not performed:")
    for item in report.get("actions_not_performed", []):
        print(f"    - {item}")


def _main(argv: list[str] | None, *, report_builder: Any, title: str) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true")
    output.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    report = report_builder()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        _print_pretty(title, report)
    return 0 if report.get("ok") else 1


class packaged_public_demo:
    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        return _main(argv, report_builder=build_packaged_demo_report, title="YonerAI public demo")


class packaged_public_mvp_smoke:
    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        return _main(argv, report_builder=build_packaged_smoke_report, title="YonerAI public MVP smoke")
