from __future__ import annotations

from typing import Any, Mapping

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


def format_status_snapshot_pretty(report: Mapping[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    if not report.get("ok"):
        error = report.get("error") if isinstance(report.get("error"), Mapping) else {}
        title = "状態" if lang == "ja" else "Status"
        message = _safe(error.get("message") or "status unavailable")
        code = _safe(error.get("code") or "unknown")
        return "\n".join((title, f"  error: {code}", f"  message: {message}", ""))
    snapshot = report.get("snapshot") if isinstance(report.get("snapshot"), Mapping) else {}
    overall = snapshot.get("overall") if isinstance(snapshot.get("overall"), Mapping) else {}
    components = snapshot.get("components") if isinstance(snapshot.get("components"), list) else []
    component = report.get("component") if isinstance(report.get("component"), Mapping) else None
    compatibility = report.get("compatibility") if isinstance(report.get("compatibility"), Mapping) else {}
    cache = report.get("cache") if isinstance(report.get("cache"), Mapping) else {}
    title = "YonerAI 状態" if lang == "ja" else "YonerAI Status"
    production_label = "本番" if lang == "ja" else "production"
    production_value = "未主張" if lang == "ja" else "not_claimed"
    rows: list[CliRow] = [
        _row("schema", snapshot.get("schema_version")),
        _row("overall", _triple(overall)),
        _row("generated_at", snapshot.get("generated_at")),
        _row("stale_after_seconds", snapshot.get("stale_after_seconds")),
        _row("components", len(components)),
        _row("cache", _cache_summary(cache)),
        _row("min_cli_version", compatibility.get("min_cli_version") or "not_provided"),
        _row(production_label, production_value),
    ]
    if component is not None:
        rows.extend(
            [
                _row("selected_component", component.get("id")),
                _row("component_state", _triple(component)),
                _row("component_message", component.get("message")),
            ]
        )
    else:
        for item in components:
            if isinstance(item, Mapping):
                rows.append(_row(str(item.get("id") or "component"), _component_summary(item)))
    sections = [
        CliSection("snapshot", tuple(rows)),
        CliSection("boundary", tuple(CliRow("note", line) for line in _footer(lang))),
    ]
    body = render_report(title, sections, color=color)
    return body


def format_status_snapshot_compact(report: Mapping[str, Any], *, lang: str = "ja") -> str:
    if not report.get("ok"):
        error = report.get("error") if isinstance(report.get("error"), Mapping) else {}
        if lang == "ja":
            return f"状態を取得できません: {_safe(error.get('message') or error.get('code') or 'unknown')}\n"
        return f"Status unavailable: {_safe(error.get('message') or error.get('code') or 'unknown')}\n"
    snapshot = report.get("snapshot") if isinstance(report.get("snapshot"), Mapping) else {}
    overall = snapshot.get("overall") if isinstance(snapshot.get("overall"), Mapping) else {}
    components = snapshot.get("components") if isinstance(snapshot.get("components"), list) else []
    worker = _component_by_id(components, "official_execution_worker")
    provider = _component_by_id(components, "provider_gateway")
    queue = _component_by_id(components, "run_queue")
    if lang == "ja":
        return "\n".join(
            (
                "状態",
                f"  全体: {_triple(overall)}",
                f"  提供ゲートウェイ: {_component_summary(provider) if provider else 'unknown'}",
                f"  公式実行ワーカー: {_component_summary(worker) if worker else 'unknown'}",
                f"  実行キュー: {_component_summary(queue) if queue else 'unknown'}",
                "  本番クラウド: 未主張",
                "  秘密/内部情報: 出力しません",
                "",
            )
        )
    return "\n".join(
        (
            "Status",
            f"  overall: {_triple(overall)}",
            f"  provider_gateway: {_component_summary(provider) if provider else 'unknown'}",
            f"  official_execution_worker: {_component_summary(worker) if worker else 'unknown'}",
            f"  run_queue: {_component_summary(queue) if queue else 'unknown'}",
            "  production_cloud: not claimed",
            "  private details: not printed",
            "",
        )
    )


def _component_by_id(components: list[object], component_id: str) -> Mapping[str, object] | None:
    for item in components:
        if isinstance(item, Mapping) and item.get("id") == component_id:
            return item
    return None


def _component_summary(item: Mapping[str, object]) -> str:
    stale = " stale" if item.get("stale") else ""
    return f"{_safe(item.get('health'))}/{_safe(item.get('availability'))}/{_safe(item.get('stage'))}{stale}"


def _triple(item: Mapping[str, object]) -> str:
    return f"{_safe(item.get('health'))}/{_safe(item.get('availability'))}/{_safe(item.get('stage'))}"


def _cache_summary(cache: Mapping[str, object]) -> str:
    if cache.get("source_cache_supported"):
        return "etag/cache-control"
    return "not_reported"


def _row(label: str, value: object) -> CliRow:
    return CliRow(label, _safe(value))


def _footer(lang: str) -> tuple[str, ...]:
    if lang == "ja":
        return (
            "StatusSnapshot v1 は公開安全な状態だけを表示します。",
            "worker はクラウド側 heartbeat が古い場合 offline として扱います。",
            "本番 Oracle/cloud/login は含みません。",
        )
    return (
        "StatusSnapshot v1 prints only public-safe status.",
        "Worker health is derived from cloud heartbeat freshness.",
        "Production Oracle/cloud/login are not included.",
    )


def _safe(value: object) -> str:
    text = str(value if value is not None else "unknown")
    return text.replace("\n", " ").replace("\r", " ")[:240]
