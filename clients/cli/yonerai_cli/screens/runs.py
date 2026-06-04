from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.labels import _provider_label, _route_label, _run_status_label, _safe


def format_runs_list_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    ledger = report.get("ledger") or {}
    file_backed = ledger.get("file_backed", "unknown")
    if lang == "ja":
        title = "YonerAI 実行履歴"
        ledger_title = "履歴"
        recent_title = "最近の実行"
        empty_text = "選択したlocal ledgerには履歴がありません"
        path_label = "出力にpathを保存"
        guidance = '履歴を残すには: yonerai ask "hello" --auto --ledger .yonerai-runs.jsonl --json'
    else:
        title = "YonerAI runs"
        ledger_title = "Ledger"
        recent_title = "Recent"
        empty_text = "none in selected local ledger"
        path_label = "path_persisted_in_output"
        guidance = 'To keep history: yonerai ask "hello" --auto --ledger .yonerai-runs.jsonl --json'
    rows = tuple(
        CliRow(
            str(run["run_id"]),
            f"{run['status']} {run['provider_decision'].get('provider_id', 'unknown')} {run['task_summary']}",
            "ok" if run["status"] == "completed" else "warn",
        )
        for run in report["runs"]
    ) or (CliRow("runs", empty_text, "warn"),)
    if not ledger.get("file_backed"):
        rows = rows + (CliRow("next", guidance, "warn"),)
    return render_report(
        title,
        (
            CliSection(
                ledger_title,
                (
                    CliRow("file_backed", file_backed, _optional_bool_status(file_backed)),
                    CliRow("local_only", ledger.get("local_only", True), "ok"),
                    CliRow(
                        path_label,
                        ledger.get("path_persisted_in_output", False),
                        "fail" if ledger.get("path_persisted_in_output") else "ok",
                    ),
                ),
            ),
            CliSection(recent_title, rows),
        ),
        color=color,
    )


def format_run_show_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    title = "YonerAI 実行" if lang == "ja" else "YonerAI run"
    if not report["ok"]:
        error_title = "エラー" if lang == "ja" else "Error"
        return render_report(title, (CliSection(error_title, (CliRow("error", report["error"]["message"], "fail"),)),), color=color)
    run = report["run"]
    ledger = report.get("ledger") or {}
    file_backed = ledger.get("file_backed", "unknown")
    events = tuple(CliRow(event["name"], f"{event['status']} {event['summary']}", "ok" if event["status"] == "ok" else "warn") for event in run["events"])
    progress_events = tuple(event for event in run["events"] if str(event.get("name") or "").startswith("task_progress_"))
    if lang == "ja":
        progress_rows = tuple(
            CliRow(
                _progress_step_label_ja(str(event.get("name") or "").removeprefix("task_progress_")),
                f"{_progress_state_label_ja(event.get('status'))}: "
                f"{_progress_summary_ja(str(event.get('name') or '').removeprefix('task_progress_'), event.get('summary'))}",
                _progress_status_for_cli(event.get("status")),
            )
            for event in progress_events
        )
        agent_rows = _run_agent_rows_ja(run)
    else:
        progress_rows = tuple(
            CliRow(
                str(event.get("name") or "").removeprefix("task_progress_"),
                f"{event.get('status')}: {event.get('summary')}",
                _progress_status_for_cli(event.get("status")),
            )
            for event in progress_events
        )
        agent_rows = _run_agent_rows_en(run)
    sections = (
        CliSection(
            "履歴" if lang == "ja" else "Ledger",
            (
                CliRow("file_backed", file_backed, _optional_bool_status(file_backed)),
                CliRow("local_only", ledger.get("local_only", True), "ok"),
                CliRow("raw_prompt_persisted", ledger.get("raw_prompt_persisted", False), "fail" if ledger.get("raw_prompt_persisted") else "ok"),
            ),
        ),
        CliSection(
            "実行" if lang == "ja" else "Run",
            (
                CliRow("run_id", run["run_id"], "ok"),
                CliRow("status", _run_status_ja(run["status"]) if lang == "ja" else run["status"], "ok" if run["status"] == "completed" else "warn"),
                CliRow("task_summary", run["task_summary"], "ok"),
                CliRow("provider", run["provider_decision"].get("provider_id", "unknown"), "ok"),
            ),
        ),
        CliSection("進行状況" if lang == "ja" else "Task progress", progress_rows or (CliRow("progress", "not recorded", "warn"),)),
        CliSection("エージェント計画" if lang == "ja" else "Agent plan", agent_rows),
        CliSection("イベント" if lang == "ja" else "Events", events or (CliRow("events", "none", "warn"),)),
    )
    return render_report(title, sections, color=color)


def _optional_bool_status(value: object) -> str:
    if value is True:
        return "ok"
    if value is False:
        return "warn"
    return "fail"


def _progress_status_for_cli(state: object) -> str:
    if state == "done":
        return "ok"
    if state == "skipped":
        return "skipped"
    if state == "blocked":
        return "warn"
    if state == "error":
        return "fail"
    if state == "running":
        return "warn"
    return "warn"


def _progress_step_label_ja(value: object) -> str:
    mapping = {
        "classify": "分類",
        "route": "経路選択",
        "provider_selection": "提供元選択",
        "execution": "実行",
        "review": "レビュー",
        "result": "結果",
    }
    return mapping.get(str(value), str(value or "不明"))


def _progress_state_label_ja(value: object) -> str:
    mapping = {
        "pending": "待機",
        "running": "実行中",
        "done": "完了",
        "skipped": "スキップ",
        "blocked": "ブロック",
        "error": "エラー",
    }
    return mapping.get(str(value), str(value or "不明"))


def _progress_summary_ja(step: object, summary: object) -> str:
    text = str(summary or "")
    step_id = str(step)
    if step_id == "classify" and "difficulty=" in text:
        return text.replace("difficulty=instant", "難易度=即時").replace("difficulty=task", "難易度=タスク").replace(
            "difficulty=agent", "難易度=複雑"
        ).replace("privacy=public", "公開").replace("privacy=local_file", "ローカルファイル").replace("privacy=private", "非公開")
    if step_id == "route" and "route=" in text:
        return text.replace("route=instant_local", "経路=ローカル即時").replace("route=local_llm", "経路=ローカルLLM").replace(
            "route=cloud_contract_candidate", "経路=クラウド候補"
        ).replace("route=deny", "経路=拒否").replace("approval_required=false", "承認不要").replace(
            "approval_required=true", "承認必要"
        )
    if step_id == "provider_selection" and "provider=" in text:
        return text.replace("provider=mock", "提供元=モック").replace("provider=oracle-stub", "提供元=オラクルスタブ").replace(
            "provider=local", "提供元=ローカル"
        )
    if step_id == "execution":
        if text.startswith("executed route="):
            return "選択した安全な経路で実行しました"
        if text.startswith("execution skipped"):
            return "安全上、実行をスキップしました"
        if text.startswith("execution stopped"):
            return "実行を停止しました"
    if step_id == "review":
        if text.startswith("reviewer plan not required"):
            return "この経路ではレビュー計画は不要です"
        if text.startswith("subagents_planned="):
            return text.replace("subagents_planned=", "担当計画=").replace(" reviewer_required=true", " / レビューあり")
    if step_id == "result":
        if text.startswith("completed"):
            return "完了しました"
        if text.startswith("blocked"):
            return "ブロックされました"
    return text or "記録なし"


def _run_status_ja(value: object) -> str:
    mapping = {"completed": "完了", "failed": "失敗", "blocked": "ブロック", "running": "実行中", "created": "作成済み"}
    return mapping.get(str(value), str(value or "不明"))


def _run_agent_rows_ja(run: dict[str, Any]) -> tuple[CliRow, ...]:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    reviewer_event = next((event for event in events if isinstance(event, dict) and event.get("name") == "auto_reviewer_plan"), None)
    return (
        CliRow("レビュー計画", reviewer_event.get("summary") if isinstance(reviewer_event, dict) else "記録なし", "ok" if reviewer_event else "skipped"),
        CliRow("実エージェント起動", "なし（計画表示のみ）", "ok"),
    )


def _run_agent_rows_en(run: dict[str, Any]) -> tuple[CliRow, ...]:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    reviewer_event = next((event for event in events if isinstance(event, dict) and event.get("name") == "auto_reviewer_plan"), None)
    return (
        CliRow("reviewer_plan", reviewer_event.get("summary") if isinstance(reviewer_event, dict) else "not recorded", "ok" if reviewer_event else "skipped"),
        CliRow("subagents_started", False, "ok"),
    )


def _format_run_progress(run: dict[str, Any], *, lang: str) -> str:
    progress_events = _run_progress_events(run)
    if not progress_events:
        return "進行状況: 記録なし\n" if lang == "ja" else "Task progress: not recorded\n"
    lines = ["進行状況" if lang == "ja" else "Task progress"]
    for event in progress_events:
        step = str(event.get("name") or "").removeprefix("task_progress_")
        if lang == "ja":
            lines.append(
                f"  {_progress_state_label(event.get('status'), lang='ja')}: "
                f"{_progress_step_label(step, lang='ja')} - {_progress_summary_label(step, event.get('summary'), lang='ja')}"
            )
        else:
            lines.append(f"  {event.get('status')}: {_safe(step)} - {_safe(event.get('summary') or '')}")
    lines.append("")
    return "\n".join(lines)

def _format_run_agents(run: dict[str, Any], *, lang: str) -> str:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    reviewer_event = next((event for event in events if isinstance(event, dict) and event.get("name") == "auto_reviewer_plan"), None)
    if lang == "ja":
        lines = ["エージェント計画"]
        if reviewer_event:
            lines.append(f"  レビュー計画: {_safe(reviewer_event.get('summary') or '')}")
        else:
            lines.append("  この履歴にはレビュー計画の記録がありません。")
        lines.append("  実サブエージェント起動: なし（計画表示のみ）")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Agent plan",
            f"  reviewer_plan: {_safe(reviewer_event.get('summary') if isinstance(reviewer_event, dict) else 'not recorded')}",
            "  subagents_started: false",
            "",
        )
    )

def _run_progress_events(run: dict[str, Any]) -> list[dict[str, Any]]:
    events = run.get("events") if isinstance(run.get("events"), list) else []
    return [event for event in events if isinstance(event, dict) and str(event.get("name") or "").startswith("task_progress_")]

def _run_route(run: dict[str, Any]) -> object:
    route_decision = run.get("route_decision") if isinstance(run.get("route_decision"), dict) else {}
    auto_runtime = route_decision.get("auto_runtime") if isinstance(route_decision.get("auto_runtime"), dict) else {}
    return route_decision.get("route_strategy") or auto_runtime.get("route") or route_decision.get("route") or "unknown"

def _run_provider(run: dict[str, Any]) -> object:
    provider_decision = run.get("provider_decision") if isinstance(run.get("provider_decision"), dict) else {}
    return provider_decision.get("provider_id") or "unknown"

def _format_runs(report: dict[str, Any], *, lang: str) -> str:
    runs = report.get("runs") if isinstance(report.get("runs"), list) else []
    if not runs:
        if lang == "ja":
            return "\n".join(
                (
                    "実行履歴: まだありません",
                    "履歴は明示したローカル履歴だけを読みます。",
                    "対話画面では /選択 5 オン で秘匿済みローカル履歴を有効化できます。",
                    "",
                )
            )
        return "Runs: none yet\nLedger is opt-in and local-only.\n"
    lines = ["実行履歴" if lang == "ja" else "Runs"]
    for run in runs:
        if isinstance(run, dict):
            route = _run_route(run)
            provider = _run_provider(run)
            event_count = len(_run_progress_events(run))
            if lang == "ja":
                lines.append(
                    f"  実行ID（run_id）{run.get('run_id')}: {_run_status_label(run.get('status'), lang='ja')} "
                    f"{run.get('task_summary')} / 経路={_route_label(route, lang='ja')} / "
                    f"提供元={_provider_label(provider, lang='ja')} / 進行={event_count}件"
                )
            else:
                lines.append(
                    f"  {run.get('run_id')}: {run.get('status')} {run.get('task_summary')} "
                    f"/ route={_safe(route)} / provider={_safe(provider)} / progress_events={event_count}"
                )
    lines.append("")
    return "\n".join(_safe(line) for line in lines)

def _format_run(report: dict[str, Any], *, lang: str) -> str:
    if not report.get("ok"):
        return "実行が見つかりません\n" if lang == "ja" else "Run not found\n"
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    if lang == "ja":
        return "\n".join(
            (
                "実行",
                f"  実行ID（run_id）: {_safe(run.get('run_id') or 'none')}",
                f"  状態: {_run_status_label(run.get('status'), lang='ja')}",
                f"  経路（処理方法）: {_route_label(_run_route(run), lang='ja')}",
                f"  提供元（AI接続元）: {_provider_label(_run_provider(run), lang='ja')}",
                f"  タスク: {_safe(run.get('task_summary') or 'なし')}",
                "",
                _format_run_progress(run, lang="ja").rstrip(),
                _format_run_agents(run, lang="ja").rstrip(),
                "",
            )
        )
    return "\n".join(
        (
            "Run",
            f"  run_id: {_safe(run.get('run_id') or 'none')}",
            f"  status: {_safe(run.get('status') or 'unknown')}",
            f"  route: {_safe(_run_route(run))}",
            f"  provider: {_safe(_run_provider(run))}",
            f"  task: {_safe(run.get('task_summary') or 'none')}",
            "",
            _format_run_progress(run, lang="en").rstrip(),
            _format_run_agents(run, lang="en").rstrip(),
            "",
        )
    )


def _progress_step_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "step")
    return {
        "classify": "分類",
        "route": "経路選択",
        "provider_selection": "提供元選択",
        "execution": "実行",
        "review": "レビュー",
        "result": "結果",
    }.get(str(value), _safe(value or "不明"))

def _progress_state_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    return {
        "pending": "待機",
        "running": "実行中",
        "done": "完了",
        "skipped": "スキップ",
        "blocked": "ブロック",
        "error": "エラー",
        "ok": "完了",
        "failed": "エラー",
    }.get(str(value), _safe(value or "不明"))

def _progress_summary_label(step: object, summary: object, *, lang: str) -> str:
    text = _safe(summary or "")
    if lang != "ja":
        return text
    return (
        text.replace("difficulty=instant", "難易度=即時")
        .replace("difficulty=task", "難易度=タスク")
        .replace("difficulty=agent", "難易度=複雑")
        .replace("privacy=public", "公開")
        .replace("privacy=local_file", "ローカルファイル")
        .replace("privacy=private", "非公開")
        .replace("route=instant_local", "経路=ローカル即時")
        .replace("route=local_llm", "経路=ローカルLLM")
        .replace("route=cloud_contract_candidate", "経路=クラウド候補")
        .replace("route=deny", "経路=拒否")
        .replace("approval_required=false", "承認不要")
        .replace("approval_required=true", "承認必要")
        .replace("provider=mock", "提供元=モック")
        .replace("provider=oracle-stub", "提供元=オラクルスタブ")
        .replace("provider=local", "提供元=ローカル")
    )
