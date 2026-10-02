from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


def format_oracle_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    request = report.get("request") if isinstance(report.get("request"), dict) else {}
    response = report.get("response") if isinstance(report.get("response"), dict) else {}
    rows = (
        CliRow("operation", report.get("operation", "status"), "ok"),
        CliRow("status", report.get("status"), "ok" if report.get("ok") else "fail"),
        CliRow("local_dev_stub", report.get("local_dev_stub", True), "ok"),
        CliRow("route_strategy", request.get("route_strategy", "n/a"), "ok" if report.get("ok") else "warn"),
        CliRow("privacy_class", request.get("privacy_class", "n/a"), "ok" if request.get("privacy_class") == "public" else "warn"),
        CliRow("run_id", request.get("run_id", "n/a"), "ok"),
    )
    boundaries = (
        CliRow("network_required", report.get("network_required", False), "fail" if report.get("network_required") else "ok"),
        CliRow("provider_call_performed", report.get("provider_call_performed", False), "fail" if report.get("provider_call_performed") else "ok"),
        CliRow("production_oracle_used", report.get("production_oracle_used", False), "fail" if report.get("production_oracle_used") else "ok"),
        CliRow("raw_prompt_included", response.get("raw_prompt_included", False), "fail" if response.get("raw_prompt_included") else "ok"),
        CliRow(
            "private_file_content_included",
            response.get("private_file_content_included", False),
            "fail" if response.get("private_file_content_included") else "ok",
        ),
    )
    non_actions = tuple(CliRow("not_performed", item, "ok") for item in report.get("actions_not_performed", []))
    return render_report(
        "YonerAI Oracle stub",
        (
            CliSection("Local-dev fixture", rows),
            CliSection("Boundaries", boundaries),
            CliSection("Actions not performed", non_actions or (CliRow("actions", "none", "warn"),)),
        ),
        color=color,
    )
