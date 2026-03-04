from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_ts(raw: str) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    idx = int(round(0.95 * (len(vals) - 1)))
    idx = max(0, min(len(vals) - 1, idx))
    return float(vals[idx])


def _extract_payload(record: dict[str, Any]) -> dict[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute 7-day rolling KPI for Core route runs.")
    parser.add_argument(
        "--log",
        default=os.getenv("ORA_TRACE_LOG", "logs/agent_trace.jsonl"),
        help="Path to trace JSONL. Default: ORA_TRACE_LOG or logs/agent_trace.jsonl",
    )
    parser.add_argument("--days", type=int, default=7, help="Rolling window in days (default: 7)")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(
            json.dumps(
                {
                    "window_days": int(args.days),
                    "sample_count": 0,
                    "budget_stop_rate": 0.0,
                    "p95_total_ms": 0.0,
                    "error": f"log_not_found:{log_path}",
                },
                ensure_ascii=False,
            )
        )
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(args.days)))
    sample_count = 0
    budget_stop_count = 0
    total_ms_values: list[float] = []

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("event") != "core.run.metrics":
                continue
            ts = _parse_ts(rec.get("ts"))
            if ts is None or ts < cutoff:
                continue

            payload = _extract_payload(rec)
            sample_count += 1
            if bool(payload.get("budget_stop")):
                budget_stop_count += 1
            try:
                total_ms = float(payload.get("total_ms", 0.0))
            except Exception:
                total_ms = 0.0
            if total_ms > 0:
                total_ms_values.append(total_ms)

    budget_stop_rate = (budget_stop_count / sample_count) if sample_count else 0.0
    out = {
        "window_days": int(args.days),
        "sample_count": sample_count,
        "budget_stop_rate": round(budget_stop_rate, 4),
        "p95_total_ms": round(_p95(total_ms_values), 2),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
