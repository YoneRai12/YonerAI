from __future__ import annotations

import argparse
from typing import Any, Callable

from yonerai_cli.screens.status_snapshot import format_status_snapshot_compact, format_status_snapshot_pretty
from yonerai_cli.services.status_snapshot_service import (
    StatusSnapshotError,
    build_status_snapshot_report,
)


class StatusSnapshotCommandError(Exception):
    pass


def handle_status_snapshot_command(args: argparse.Namespace, *, print_json: Callable[[dict[str, Any]], None]) -> int:
    component_id = getattr(args, "component_id", None)
    try:
        report = build_status_snapshot_report(
            source=getattr(args, "source", "live"),
            status_source=getattr(args, "status_source", None),
            allow_network_status_fetch=bool(getattr(args, "allow_network_status_fetch", False)),
            component_id=component_id,
            timeout_seconds=float(getattr(args, "timeout_seconds", 10.0)),
        )
    except StatusSnapshotError as exc:
        raise StatusSnapshotCommandError(exc.message) from exc
    if getattr(args, "json", False):
        print_json(report)
    elif getattr(args, "pretty", False):
        print(format_status_snapshot_pretty(report, lang=getattr(args, "lang", "ja"), color=getattr(args, "color", "auto")))
    else:
        print(format_status_snapshot_compact(report, lang=getattr(args, "lang", "ja")))
    return 0 if report.get("ok") else 1
