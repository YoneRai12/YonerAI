from __future__ import annotations

from typing import Any

from yonerai_cli.screens.labels import _provider_label, _route_label, _safe
from yonerai_cli.screens.runs import _progress_state_label, _progress_step_label


PROGRESS_STEPS: tuple[str, ...] = (
    "classify",
    "route",
    "provider_selection",
    "execution",
    "review",
    "result",
)


def format_thinking_status(
    *,
    lang: str,
    provider: str,
    live: bool,
    memory_enabled: bool,
) -> str:
    if lang == "ja":
        lines = [
            "進行表示",
            "  次の通常メッセージでは、この順番で安全に処理します。",
            "  生の思考内容は表示しません。表示するのは状態・経路・結果要約だけです。",
            "",
            f"  提供元（AI接続先）: {_provider_label(provider, lang='ja')}",
            f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'}",
            f"  記憶参照: {'有効（IDだけ記録）' if memory_enabled else '無効'}",
            "",
        ]
        for index, step in enumerate(PROGRESS_STEPS, start=1):
            lines.append(f"  {index}. {_progress_step_label(step, lang='ja')}: 待機中")
        lines.extend(
            (
                "",
                "ブロック時の表示",
                "  dangerous / private / workspace外file / cloud候補禁止 は approval_required または deny として表示します。",
                "",
            )
        )
        return "\n".join(lines)
    lines = [
        "Progress display",
        "  Normal messages flow through these safe states.",
        "  Raw chain-of-thought is never shown; only state, route, and redacted result summaries are shown.",
        "",
        f"  provider: {_safe(provider)}",
        f"  live: {'on explicit' if live else 'off by default'}",
        f"  memory: {'enabled ids only' if memory_enabled else 'disabled'}",
        "",
    ]
    for index, step in enumerate(PROGRESS_STEPS, start=1):
        lines.append(f"  {index}. {_progress_step_label(step, lang='en')}: pending")
    lines.extend(
        (
            "",
            "Blocked state",
            "  dangerous/private/outside-workspace/cloud-disallowed tasks show approval_required or deny.",
            "",
        )
    )
    return "\n".join(lines)


def format_running_preview(report: dict[str, Any] | None, *, lang: str) -> str:
    if not isinstance(report, dict):
        return "進行状況: まだありません\n" if lang == "ja" else "Progress: none yet\n"
    auto = report.get("auto") if isinstance(report.get("auto"), dict) else {}
    provider = report.get("provider") if isinstance(report.get("provider"), dict) else {}
    progress = report.get("task_progress") if isinstance(report.get("task_progress"), dict) else {}
    steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    run_id = run.get("run_id") or run.get("id") or "none"
    provider_id = provider.get("provider_id") or auto.get("provider_id") or auto.get("provider") or "unknown"
    if lang == "ja":
        lines = [
            "進行状況",
            f"  実行ID（run_id）: {_safe(run_id)}",
            f"  経路（処理方法）: {_route_label(auto.get('route'), lang='ja')}",
            f"  提供元（AI接続先）: {_provider_label(provider_id, lang='ja')}",
        ]
        if not steps:
            lines.append("  進行イベント: まだ記録がありません。")
        for step in steps:
            if isinstance(step, dict):
                lines.append(
                    f"  {_progress_state_label(step.get('state'), lang='ja')}: "
                    f"{_progress_step_label(step.get('id'), lang='ja')}"
                )
        lines.append("")
        return "\n".join(lines)
    lines = [
        "Progress",
        f"  run_id: {_safe(run_id)}",
        f"  route: {_safe(auto.get('route') or 'unknown')}",
        f"  provider: {_safe(provider_id)}",
    ]
    if not steps:
        lines.append("  progress_events: none yet")
    for step in steps:
        if isinstance(step, dict):
            lines.append(f"  {_safe(step.get('state') or 'pending')}: {_progress_step_label(step.get('id'), lang='en')}")
    lines.append("")
    return "\n".join(lines)
