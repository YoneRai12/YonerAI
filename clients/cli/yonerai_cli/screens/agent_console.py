from __future__ import annotations

from typing import Any

from yonerai_cli.config import build_config_report
from yonerai_cli.screens.labels import (
    _agent_mode_label,
    _approval_label,
    _provider_label,
    _route_label,
    _run_status_label,
    _safe,
    _selector,
)
from yonerai_cli.screens.runs import (
    _progress_state_label,
    _progress_step_label,
    _progress_summary_label,
    _run_progress_events,
)
from yonerai_cli.tui.palette import format_command_palette


def _format_chat_response(report: dict[str, Any], *, lang: str) -> str:
    run = report.get("run") if isinstance(report.get("run"), dict) else {}
    auto = report.get("auto") if isinstance(report.get("auto"), dict) else {}
    provider = report.get("provider") if isinstance(report.get("provider"), dict) else {}
    response = report.get("response") if isinstance(report.get("response"), dict) else {}
    error = report.get("error") if isinstance(report.get("error"), dict) else {}
    output = response.get("output_text") or error.get("message") or "no output"
    run_id = run.get("run_id") or run.get("id") or "none"
    provider_id = provider.get("provider_id") or auto.get("provider_id") or auto.get("provider") or "unknown"
    memory_line = _format_chat_memory_line(report, lang=lang)
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI ミッションコントロール",
                f"  実行ID（run_id）: {_safe(run_id)}",
                f"  経路（処理方法）: {_route_label(auto.get('route'), lang='ja')}",
                f"  提供元（AI接続元）: {_provider_label(provider_id, lang='ja')}",
                f"  ローカルノード: {_local_node_state(report, lang='ja')}",
                f"  履歴: {_ledger_state_from_report(report, lang='ja')}",
                "  安全: ネットワーク初期値オフ / ファイルはワークスペース内のみ / 任意シェル無効",
                f"  承認: {'必要' if auto.get('approval_required') else '不要'}",
                "",
                _format_task_progress(report, lang="ja").rstrip(),
                _format_agents(report, lang="ja").rstrip(),
                memory_line,
                "",
                f"  出力: {_safe(output)}",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI response",
            f"  run_id: {_safe(run_id)}",
            f"  route: {_safe(auto.get('route') or 'unknown')}",
            f"  provider: {_safe(provider_id)}",
            f"  local_node: {_local_node_state(report, lang='en')}",
            f"  ledger: {_ledger_state_from_report(report, lang='en')}",
            "  safety: network off by default / workspace file only / arbitrary shell disabled",
            f"  approval: {'required' if auto.get('approval_required') else 'not required'}",
            "",
            _format_task_progress(report, lang="en").rstrip(),
            _format_agents(report, lang="en").rstrip(),
            memory_line,
            "",
            f"  output: {_safe(output)}",
            "",
        )
    )


def _format_chat_memory_line(report: dict[str, Any], *, lang: str) -> str:
    memory = report.get("memory") if isinstance(report.get("memory"), dict) else {}
    ids = memory.get("used_ids") if isinstance(memory.get("used_ids"), list) else []
    safe_ids = [_safe(memory_id) for memory_id in ids[:8]]
    if not safe_ids:
        return "記憶: 参照なし" if lang == "ja" else "Memory: not used"
    joined = ", ".join(safe_ids)
    if lang == "ja":
        return f"記憶を参照しました: memory_used={joined} / raw内容は表示・送信しません"
    return f"Memory used: {joined} / raw memory content not shown or sent"


def _format_task_progress(report: dict[str, Any], *, lang: str) -> str:
    progress = report.get("task_progress") if isinstance(report.get("task_progress"), dict) else {}
    steps = progress.get("steps") if isinstance(progress.get("steps"), list) else []
    if not steps:
        return "進行状況: まだありません\n" if lang == "ja" else "Task progress: none yet\n"
    lines = ["進行状況" if lang == "ja" else "Task progress"]
    for step in steps:
        if not isinstance(step, dict):
            continue
        if lang == "ja":
            lines.append(
                f"  {_progress_state_label(step.get('state'), lang='ja')}: "
                f"{_progress_step_label(step.get('id'), lang='ja')} - "
                f"{_progress_summary_label(step.get('id'), step.get('summary'), lang='ja')}"
            )
        else:
            lines.append(f"  {step.get('state')}: {_safe(step.get('id') or 'step')} - {_safe(step.get('summary') or '')}")
    lines.append("")
    return "\n".join(lines)


def _format_tasks(last_report: dict[str, Any] | None, runs_report: dict[str, Any], *, lang: str) -> str:
    runs = runs_report.get("runs") if isinstance(runs_report.get("runs"), list) else []
    if lang == "ja":
        lines = ["タスク"]
        if isinstance(last_report, dict):
            run = last_report.get("run") if isinstance(last_report.get("run"), dict) else {}
            lines.append(f"  現在/直近: run_id={_safe(run.get('run_id') or run.get('id') or 'none')}")
            lines.append(_format_task_progress(last_report, lang="ja").rstrip())
        else:
            lines.append("  現在/直近: まだ実行がありません。通常文を入力すると ask --auto 経路でタスクを作ります。")
        if runs:
            lines.append("  最近の履歴")
            for run in runs[:5]:
                if isinstance(run, dict):
                    lines.append(
                        f"    run_id={_safe(run.get('run_id') or 'none')} "
                        f"状態={_run_status_label(run.get('status'), lang='ja')} "
                        f"進行イベント={len(_run_progress_events(run))}"
                    )
        else:
            lines.append("  最近の履歴: ローカル履歴が未設定、または記録がありません。")
        lines.append("  サブエージェント: まだ実行しません。計画表示のみです。")
        lines.append("")
        return "\n".join(lines)
    lines = ["Tasks"]
    if isinstance(last_report, dict):
        run = last_report.get("run") if isinstance(last_report.get("run"), dict) else {}
        lines.append(f"  current/recent: run_id={_safe(run.get('run_id') or run.get('id') or 'none')}")
        lines.append(_format_task_progress(last_report, lang="en").rstrip())
    else:
        lines.append("  current/recent: no run yet. Type a message to create an ask --auto task.")
    lines.append("  subagents: not started; plan display only")
    lines.append("")
    return "\n".join(lines)


def _format_agents(report: dict[str, Any] | None, *, lang: str) -> str:
    reviewer = report.get("reviewer_plan") if isinstance(report, dict) and isinstance(report.get("reviewer_plan"), dict) else {}
    subtasks = reviewer.get("subtasks") if isinstance(reviewer.get("subtasks"), list) else []
    if not reviewer:
        if lang == "ja":
            return "\n".join(
                (
                    "エージェント計画",
                    "  まだ実行結果がありません。質問後に /エージェント で確認できます。",
                    "  実サブエージェントはまだ起動しません。安全な計画表示だけです。",
                    "",
                )
            )
        return "Agent plan\n  No run yet. This is a public-safe plan display; no subagents are started.\n"
    lines = ["エージェント計画" if lang == "ja" else "Agent plan"]
    if not reviewer.get("enabled"):
        lines.append("  今回は複数担当の計画は不要です。" if lang == "ja" else "  multi-role plan: not required for this run")
    for item in subtasks:
        if isinstance(item, dict):
            if lang == "ja":
                lines.append(f"  {_agent_role_label(item.get('role'), lang='ja')}: {_safe(item.get('goal') or '')}")
            else:
                lines.append(f"  {item.get('role')}: {_safe(item.get('goal') or '')}")
    lines.append("  実サブエージェント起動: なし（計画表示のみ）" if lang == "ja" else "  subagents_started: false")
    lines.append("")
    return "\n".join(lines)


def _local_node_state(report: dict[str, Any], *, lang: str) -> str:
    local_node = report.get("local_node") if isinstance(report.get("local_node"), dict) else {}
    if local_node.get("used"):
        return "使用中（ローカル開発 / ループバック限定）" if lang == "ja" else "used local-dev loopback-only"
    return "待機中（ローカル開発 / ループバック限定）" if lang == "ja" else "standby local-dev loopback-only"


def _ledger_state_from_report(report: dict[str, Any], *, lang: str) -> str:
    ledger = report.get("ledger") if isinstance(report.get("ledger"), dict) else {}
    if ledger.get("file_backed") or ledger.get("enabled"):
        return "オン（ローカルのみ）" if lang == "ja" else "on local-only"
    return "オフ（初期値）" if lang == "ja" else "off by default"


def _agent_role_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "agent")
    return {
        "planner": "計画担当",
        "researcher": "調査担当",
        "implementer": "実装担当",
        "tester": "テスト担当",
        "reviewer": "レビュー担当",
        "executor": "実行担当",
    }.get(str(value), _safe(value or "担当"))


def _format_command_palette(lang: str) -> str:
    return format_command_palette(lang)


def _format_mode_state(config: dict[str, object], *, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    current = str(values.get("agent_mode") or "plan_readonly")
    if lang == "ja":
        return "\n".join(
            (
                "作業モード",
                f"  現在: {_agent_mode_label(current, lang='ja')}",
                "",
                f"{_selector('plan_readonly', current)} 計画（読み取り専用）: 調査・計画・確認だけ。変更や外部実行はしません。",
                f"{_selector('build_safe', current)} 安全実行: 公開runtimeで許可済みのdry-run/安全操作だけ候補にします。",
                f"{_selector('review', current)} レビュー: 差分・安全境界・テスト観点を優先します。",
                f"{_selector('memory', current)} 記憶: ローカル記憶の確認・整理を優先します。",
                "",
                "変更: /モード 計画|安全実行|レビュー|記憶",
                "ショートカット: /計画 /レビュー",
                "実サブエージェント起動: なし。表示するのは計画だけです。",
                "",
            )
        )
    return "\n".join(
        (
            "Agent mode",
            f"  current: {current}",
            "  plan_readonly: plan and inspect only",
            "  build_safe: safe public-runtime dry-run actions only",
            "  review: prioritize review and verification",
            "  memory: prioritize local memory inspection",
            "  change: /mode plan|build|review|memory",
            "  shortcuts: /plan /review",
            "  real subagent execution: none; this only displays a plan.",
            "",
        )
    )


def _format_permissions(config: dict[str, object], *, live: bool, lang: str) -> str:
    values = build_config_report(config, exists=True)["config"]
    mode = str(values.get("agent_mode") or "plan_readonly")
    approval = str(values.get("approval_mode") or "prompt")
    tools = str(values.get("tools_mode") or "dry_run")
    if lang == "ja":
        return "\n".join(
            (
                "権限と承認",
                f"  作業モード: {_agent_mode_label(mode, lang='ja')}",
                f"  承認: {_approval_label(approval, lang='ja')}",
                f"  ツール: {_safe(tools)}（public runtime は dry-run 固定）",
                f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'}",
                "",
                f"{_selector('read_only', _permission_profile(config))} 読み取り専用: 変更しない。計画・レビューだけ。",
                f"{_selector('auto_safe', _permission_profile(config))} 自動安全: 安全なdry-run候補だけ。任意shellや外部fileは不可。",
                f"{_selector('ask_before_risky', _permission_profile(config))} 危険時確認: 危険操作は approval_required / deny。",
                f"{_selector('dry_run_only', _permission_profile(config))} ドライランのみ: 実行ではなく計画だけ。",
                "",
                "変更: /権限 読み取り専用|自動安全|危険時確認|ドライランのみ",
                "境界: 任意shellなし / workspace外fileなし / provider key表示なし / local private memory自動uploadなし。",
                "",
            )
        )
    return "\n".join(
        (
            "Permissions and approval",
            f"  agent_mode: {mode}",
            f"  approval: {approval}",
            f"  tools: {tools} (public runtime is dry-run only)",
            f"  live: {'on' if live else 'off'}",
            "  profiles: read-only, auto-safe, ask-before-risky, dry-run-only",
            "  change: /permissions read-only|auto-safe|ask-before-risky|dry-run-only",
            "  boundaries: no arbitrary shell, no files outside workspace, no provider key output, no local private memory auto-upload.",
            "",
        )
    )


def _permission_profile(config: dict[str, object]) -> str:
    if config.get("approval_mode") == "deny":
        return "read_only"
    if config.get("agent_mode") == "plan_readonly":
        return "dry_run_only"
    if config.get("agent_mode") == "build_safe":
        return "auto_safe"
    return "ask_before_risky"


def _format_agent_mention_preview(text: str, *, config: dict[str, object], lang: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if not parts or not parts[0].startswith("@"):
        return None
    raw_role = parts[0][1:].strip().lower()
    role_aliases = {
        "general": "planner",
        "planner": "planner",
        "researcher": "researcher",
        "reviewer": "reviewer",
    }
    role = role_aliases.get(raw_role)
    if role is None:
        return None
    summary = _safe(parts[1] if len(parts) > 1 else "no task provided")
    mode = str(config.get("agent_mode") or "plan_readonly")
    if lang == "ja":
        return "\n".join(
            (
                "サブエージェント計画",
                f"  指名: @{raw_role} / {_agent_role_label(role, lang='ja')}",
                f"  作業モード: {_agent_mode_label(mode, lang='ja')}",
                f"  依頼要約: {summary}",
                "  状態: planned",
                "  実サブエージェント起動: なし",
                "  自律実行: なし",
                "  次にやること: 通常のメッセージとして送ると ask --auto 経路で処理します。",
                "",
            )
        )
    return "\n".join(
        (
            "Subagent plan",
            f"  mention: @{raw_role} / {role}",
            f"  agent_mode: {mode}",
            f"  request_summary: {summary}",
            "  state: planned",
            "  real_subagent_execution: none",
            "  autonomous_actions: none",
            "  next: send the task as a normal message to use ask --auto.",
            "",
        )
    )
