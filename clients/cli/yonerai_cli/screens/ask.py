from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report


def format_execution_plan_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    classification = report["classification"]
    provider = report["provider"]
    route = report["route"]
    model = report["model"]
    approval = report["approval"]
    side_effects = report["side_effects"]
    safety = report["safety_checks"]
    disabled_reasons = report.get("disabled_reasons") or []
    sections = (
        CliSection(
            "Task",
            (
                CliRow("command", report["command"], "ok"),
                CliRow("category", classification["category"], "ok"),
                CliRow("risk", classification["risk"], "warn" if classification["risk"] != "safe_public" else "ok"),
                CliRow("complexity", classification["complexity"], "ok"),
                CliRow("execution_surface", report["estimated_execution_surface"], "warn" if approval["required"] else "ok"),
            ),
        ),
        CliSection(
            "Route and provider",
            (
                CliRow("route", route["route"], "warn" if route.get("unavailable_reason") else "ok"),
                CliRow("mode", route["mode"], "ok"),
                CliRow("provider", provider["provider_id"], "ok" if provider["provider_available"] else "warn"),
                CliRow("provider_available", provider["provider_available"], "ok" if provider["provider_available"] else "warn"),
                CliRow("model_tier", model["tier"], "ok"),
                CliRow("model", model["model_id"], "ok"),
            ),
        ),
        CliSection(
            "Approval and disabled reasons",
            (
                CliRow("approval_required", approval["required"], "warn" if approval["required"] else "ok"),
                CliRow("disabled_reasons", ", ".join(disabled_reasons) if disabled_reasons else "none", "warn" if disabled_reasons else "ok"),
            ),
        ),
        CliSection(
            "Safety checks",
            (
                CliRow("mcp_deny_policy", safety["mcp_deny_policy"]["status"], "ok" if safety["mcp_deny_policy"]["ok"] else "fail"),
                CliRow(
                    "managed_download_guard",
                    safety["managed_download_guard"]["status"],
                    "ok" if safety["managed_download_guard"]["ok"] else "fail",
                ),
                CliRow("provider_call", side_effects["provider_call"], "fail" if side_effects["provider_call"] else "ok"),
                CliRow("network_call", side_effects["network_call"], "fail" if side_effects["network_call"] else "ok"),
                CliRow("shell", side_effects["shell"], "fail" if side_effects["shell"] else "ok"),
                CliRow("file_access", side_effects["file_access"], "fail" if side_effects["file_access"] else "ok"),
                CliRow("deploy", side_effects["deploy"], "fail" if side_effects["deploy"] else "ok"),
            ),
        ),
    )
    return render_report("YonerAI execution plan", sections, color=color)


def format_execution_result_pretty(report: dict[str, Any], *, color: ColorMode = "auto") -> str:
    if report.get("run") is None or report.get("plan") is None:
        error = report.get("error") or {}
        return render_report(
            "YonerAI ask",
            (CliSection("Error", (CliRow(str(error.get("code") or "error"), error.get("message") or "request failed", "fail"),)),),
            color=color,
        )
    run = report["run"]
    plan = report["plan"]
    response = report.get("response") or {}
    error = report.get("error") or {}
    boundary = report.get("boundary_checks") or {}
    ledger = report.get("ledger") or {}
    file_backed = ledger.get("file_backed", "unknown")
    provider = plan["provider"]
    sections = (
        CliSection(
            "Run",
            (
                CliRow("run_id", run["run_id"], "ok"),
                CliRow("status", run["status"], "ok" if run["status"] == "completed" else "warn"),
                CliRow("category", plan["classification"]["category"], "ok"),
                CliRow("approval_required", run["approval_required"], "warn" if run["approval_required"] else "ok"),
                CliRow("file_backed", file_backed, _optional_bool_status(file_backed)),
            ),
        ),
        CliSection(
            "Provider",
            (
                CliRow("provider", provider["provider_id"], "ok" if provider["provider_available"] else "warn"),
                CliRow("model", response.get("model") or plan["model"]["model_id"], "ok"),
                CliRow("live_call_performed", report["live_call_performed"], "warn" if report["live_call_performed"] else "ok"),
            ),
        ),
        CliSection(
            "Answer",
            (
                CliRow("ok", report["ok"], "ok" if report["ok"] else "warn"),
                CliRow("output", response.get("output_text") or error.get("message") or "none", "ok" if report["ok"] else "warn"),
            ),
        ),
        CliSection(
            "Boundaries",
            (
                CliRow("web_search", boundary.get("web_search", {}).get("status", "unknown"), "ok"),
                CliRow("tool_boundary", boundary.get("tool_boundary", {}).get("status", "unknown"), "ok"),
                CliRow(
                    "ora_tool_schema_boundary",
                    boundary.get("ora_tool_schema_boundary", {}).get("status", "unknown"),
                    "ok" if boundary.get("ora_tool_schema_boundary", {}).get("status") == "ok" else "warn",
                ),
                CliRow(
                    "ora_guardrail_response_interpreter",
                    boundary.get("ora_guardrail_response_interpreter", {}).get("status", "unknown"),
                    "ok" if boundary.get("ora_guardrail_response_interpreter", {}).get("status") == "ok" else "warn",
                ),
                CliRow("shell", plan["side_effects"]["shell"], "fail" if plan["side_effects"]["shell"] else "ok"),
                CliRow("file_access", plan["side_effects"]["file_access"], "fail" if plan["side_effects"]["file_access"] else "ok"),
                CliRow("memory_persisted", run["persistence"]["memory_persisted"], "fail" if run["persistence"]["memory_persisted"] else "ok"),
            ),
        ),
    )
    return render_report("YonerAI ask", sections, color=color)


def format_auto_runtime_pretty(report: dict[str, Any], *, lang: str = "en", color: ColorMode = "auto") -> str:
    if report.get("run") is None or report.get("auto") is None:
        error = report.get("error") or {}
        return render_report(
            "YonerAI ask --auto",
            (CliSection("Error", (CliRow(str(error.get("code") or "error"), error.get("message") or "request failed", "fail"),)),),
            color=color,
        )
    run = report["run"] if isinstance(report.get("run"), dict) else {}
    auto = report["auto"] if isinstance(report.get("auto"), dict) else {}
    provider = report["provider"] if isinstance(report.get("provider"), dict) else {}
    response = report["response"] if isinstance(report.get("response"), dict) else {}
    search = report["search"] if isinstance(report.get("search"), dict) else {}
    reviewer = report["reviewer_plan"] if isinstance(report.get("reviewer_plan"), dict) else {}
    task_progress = report["task_progress"] if isinstance(report.get("task_progress"), dict) else {}
    boundaries = report["boundaries"] if isinstance(report.get("boundaries"), dict) else {}
    error = report["error"] if isinstance(report.get("error"), dict) else {}
    ledger = report["ledger"] if isinstance(report.get("ledger"), dict) else {}
    actions_not_performed = tuple(str(item) for item in report.get("actions_not_performed") or ())
    if lang == "ja":
        return render_report(
            "YonerAI ask --auto",
            _auto_runtime_sections_ja(
                report=report,
                run=run,
                auto=auto,
                provider=provider,
                response=response,
                search=search,
                reviewer=reviewer,
                task_progress=task_progress,
                boundaries=boundaries,
                error=error,
                ledger=ledger,
                actions_not_performed=actions_not_performed,
            ),
            color=color,
        )
    sections = (
        CliSection(
            "Auto runtime",
            (
                CliRow("run_id", run.get("run_id"), "ok" if run.get("run_id") else "warn"),
                CliRow("status", run.get("status"), "ok" if run.get("status") == "completed" else "warn"),
                CliRow("difficulty", auto.get("difficulty"), "ok"),
                CliRow("privacy", auto.get("privacy"), "ok" if auto.get("privacy") == "public" else "warn"),
                CliRow("route", auto.get("route"), "fail" if auto.get("route") == "deny" else "ok"),
                CliRow("route_label", _auto_route_label_en(auto.get("route")), "fail" if auto.get("route") == "deny" else "ok"),
                CliRow("approval_required", auto.get("approval_required"), "warn" if auto.get("approval_required") else "ok"),
            ),
        ),
        CliSection(
            "Execution",
            (
                CliRow("provider", provider.get("provider_id"), "ok" if provider.get("provider_available") else "warn"),
                CliRow("model", response.get("model") or provider.get("model_id"), "ok"),
                CliRow("live_call_performed", report.get("live_call_performed"), "warn" if report.get("live_call_performed") else "ok"),
                CliRow("output", response.get("output_text") or error.get("message") or "none", "ok" if report.get("ok") else "warn"),
            ),
        ),
        CliSection(
            "Ledger",
            (
                CliRow("enabled", ledger.get("enabled", False), "ok" if ledger.get("enabled") else "warn"),
                CliRow("file_backed", ledger.get("file_backed", False), _optional_bool_status(ledger.get("file_backed", False))),
                CliRow("local_only", ledger.get("local_only", True), "ok"),
                CliRow("raw_prompt_persisted", ledger.get("raw_prompt_persisted", False), "fail" if ledger.get("raw_prompt_persisted") else "ok"),
                CliRow("next", _runs_next_command(run, ledger), "ok" if ledger.get("file_backed") else "warn"),
            ),
        ),
        CliSection(
            "Task progress",
            tuple(
                CliRow(
                    str(step.get("id") or "step"),
                    f"{step.get('state')}: {step.get('summary')}",
                    _progress_status_for_cli(step.get("state")),
                )
                for step in _progress_steps(task_progress)
            )
            or (CliRow("progress", "not recorded", "warn"),),
        ),
        CliSection(
            "Search and reviewer",
            (
                CliRow("search_mode", search.get("mode"), "ok" if search.get("mode") in {"mock", "not_requested"} else "warn"),
                CliRow("search_results", len(search.get("results") or []), "ok"),
                CliRow("reviewer_plan", reviewer.get("enabled"), "ok" if reviewer.get("enabled") else "skipped"),
                CliRow("subtasks", reviewer.get("subtask_count"), "ok" if reviewer.get("enabled") else "skipped"),
            ),
        ),
        CliSection(
            "Boundaries",
            (
                CliRow("private_file_to_cloud", boundaries.get("private_file_content_sent_to_cloud_contract"), "fail" if boundaries.get("private_file_content_sent_to_cloud_contract") else "ok"),
                CliRow("live_search_performed", boundaries.get("live_search_performed"), "fail" if boundaries.get("live_search_performed") else "ok"),
                CliRow("shell_execution", boundaries.get("shell_execution_performed"), "fail" if boundaries.get("shell_execution_performed") else "ok"),
                CliRow("production_oracle", boundaries.get("production_oracle_used"), "fail" if boundaries.get("production_oracle_used") else "ok"),
                CliRow("official_cloud_runtime", boundaries.get("official_cloud_runtime_implemented"), "fail" if boundaries.get("official_cloud_runtime_implemented") else "ok"),
            ),
        ),
        CliSection(
            "Non-actions",
            tuple(CliRow(f"no_{index}", item, "ok") for index, item in enumerate(actions_not_performed[:6], start=1)),
        ),
    )
    return render_report("YonerAI ask --auto", sections, color=color)


def _auto_runtime_sections_ja(
    *,
    report: dict[str, Any],
    run: dict[str, Any],
    auto: dict[str, Any],
    provider: dict[str, Any],
    response: dict[str, Any],
    search: dict[str, Any],
    reviewer: dict[str, Any],
    task_progress: dict[str, Any],
    boundaries: dict[str, Any],
    error: dict[str, Any],
    ledger: dict[str, Any],
    actions_not_performed: tuple[str, ...],
) -> tuple[CliSection, ...]:
    return (
        CliSection(
            "判断",
            (
                CliRow("run_id", run.get("run_id"), "ok" if run.get("run_id") else "warn"),
                CliRow("状態", _run_status_ja(run.get("status")), "ok" if run.get("status") == "completed" else "warn"),
                CliRow("難しさ", _auto_difficulty_ja(auto.get("difficulty")), "ok"),
                CliRow("privacy", _auto_privacy_ja(auto.get("privacy")), "ok" if auto.get("privacy") == "public" else "warn"),
                CliRow("経路", _auto_route_label_ja(auto.get("route")), "fail" if auto.get("route") == "deny" else "ok"),
                CliRow("承認", "必要" if auto.get("approval_required") else "不要", "warn" if auto.get("approval_required") else "ok"),
            ),
        ),
        CliSection(
            "実行",
            (
                CliRow("provider", provider.get("provider_id"), "ok" if provider.get("provider_available") else "warn"),
                CliRow("model", response.get("model") or provider.get("model_id"), "ok"),
                CliRow("live呼び出し", _yes_no_ja(report.get("live_call_performed")), "warn" if report.get("live_call_performed") else "ok"),
                CliRow("出力", response.get("output_text") or error.get("message") or "なし", "ok" if report.get("ok") else "warn"),
            ),
        ),
        CliSection(
            "履歴",
            (
                CliRow("有効", _yes_no_ja(ledger.get("enabled", False)), "ok" if ledger.get("enabled") else "warn"),
                CliRow("file-backed", _yes_no_ja(ledger.get("file_backed", False)), _optional_bool_status(ledger.get("file_backed", False))),
                CliRow("local-only", _yes_no_ja(ledger.get("local_only", True)), "ok"),
                CliRow("raw prompt保存", _yes_no_ja(ledger.get("raw_prompt_persisted", False)), "fail" if ledger.get("raw_prompt_persisted") else "ok"),
                CliRow("次に見る", _runs_next_command(run, ledger), "ok" if ledger.get("file_backed") else "warn"),
            ),
        ),
        CliSection(
            "進行状況",
            tuple(
                CliRow(
                    _progress_step_label_ja(step.get("id")),
                    f"{_progress_state_label_ja(step.get('state'))}: {_progress_summary_ja(step.get('id'), step.get('summary'))}",
                    _progress_status_for_cli(step.get("state")),
                )
                for step in _progress_steps(task_progress)
            )
            or (CliRow("進行", "記録なし", "warn"),),
        ),
        CliSection(
            "検索とレビュー",
            (
                CliRow("検索", _search_mode_ja(search.get("mode")), "ok" if search.get("mode") in {"mock", "not_requested"} else "warn"),
                CliRow("検索結果数", len(search.get("results") or []), "ok"),
                CliRow("レビュー計画", _yes_no_ja(reviewer.get("enabled")), "ok" if reviewer.get("enabled") else "skipped"),
                CliRow("担当数", reviewer.get("subtask_count"), "ok" if reviewer.get("enabled") else "skipped"),
                CliRow("実エージェント起動", "なし（計画表示のみ）", "ok"),
            ),
        ),
        CliSection(
            "境界",
            (
                CliRow("private fileをcloudへ送信", _yes_no_ja(boundaries.get("private_file_content_sent_to_cloud_contract")), "fail" if boundaries.get("private_file_content_sent_to_cloud_contract") else "ok"),
                CliRow("live search", _yes_no_ja(boundaries.get("live_search_performed")), "fail" if boundaries.get("live_search_performed") else "ok"),
                CliRow("shell実行", _yes_no_ja(boundaries.get("shell_execution_performed")), "fail" if boundaries.get("shell_execution_performed") else "ok"),
                CliRow("production Oracle", _yes_no_ja(boundaries.get("production_oracle_used")), "fail" if boundaries.get("production_oracle_used") else "ok"),
                CliRow("official cloud runtime", _yes_no_ja(boundaries.get("official_cloud_runtime_implemented")), "fail" if boundaries.get("official_cloud_runtime_implemented") else "ok"),
            ),
        ),
        CliSection(
            "この実行がしないこと",
            tuple(CliRow(f"未実行{index}", _provider_non_action_ja(item), "ok") for index, item in enumerate(actions_not_performed[:6], start=1)),
        ),
    )


def _optional_bool_status(value: object) -> str:
    if value is True:
        return "ok"
    if value is False:
        return "warn"
    return "fail"


def _yes_no_ja(value: object) -> str:
    return "はい" if bool(value) else "いいえ"


def _provider_non_action_ja(value: str) -> str:
    mapping = {
        "no live provider call": "live provider呼び出しなし",
        "no provider key output": "provider key出力なし",
        "no live Discord": "live Discord接続なし",
        "no production Oracle": "production Oracleなし",
        "no official cloud runtime": "official cloud runtimeなし",
        "no shell execution": "shell実行なし",
        "no file read": "ファイル読み取りなし",
        "no network search": "network検索なし",
    }
    return mapping.get(value, value)


def _auto_route_label_en(route: object) -> str:
    mapping = {
        "instant_local": "run immediately through local mock/provider-safe path",
        "local_llm": "run through explicit loopback-only local LLM",
        "hybrid_node": "keep private/local-file context on the local Hybrid node path",
        "cloud_contract_candidate": "public hard task queued to local-dev Oracle stub envelope",
        "deny": "blocked because approval or unsafe capability would be required",
    }
    return mapping.get(str(route), "unknown route")


def _auto_route_label_ja(route: object) -> str:
    mapping = {
        "instant_local": "ローカルで即時実行",
        "local_llm": "loopback-only local LLMで実行",
        "hybrid_node": "private/local-fileをローカルHybrid側に留める",
        "cloud_contract_candidate": "公開タスクだけlocal-dev Oracle stubへ",
        "deny": "危険または未承認のため拒否",
    }
    return mapping.get(str(route), "不明")


def _progress_steps(task_progress: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    steps = task_progress.get("steps") if isinstance(task_progress.get("steps"), list) else []
    return tuple(step for step in steps if isinstance(step, dict))


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
        if text.startswith("result returned"):
            return "秘匿済みの安全な結果を返しました"
        if text.startswith("blocked safely"):
            return "安全にブロックしました"
        if text.startswith("result unavailable"):
            return "結果は利用できません"
    return text


def _auto_difficulty_ja(value: object) -> str:
    mapping = {"instant": "すぐ返せる", "task": "通常タスク", "agent": "複数手順"}
    return mapping.get(str(value), str(value or "不明"))


def _auto_privacy_ja(value: object) -> str:
    mapping = {"public": "公開情報", "private": "private扱い", "local_file": "選択ファイル内", "dangerous": "危険操作"}
    return mapping.get(str(value), str(value or "不明"))


def _run_status_ja(value: object) -> str:
    mapping = {"completed": "完了", "failed": "失敗", "blocked": "ブロック", "running": "実行中", "created": "作成済み"}
    return mapping.get(str(value), str(value or "不明"))


def _search_mode_ja(value: object) -> str:
    mapping = {"mock": "mock検索", "not_requested": "検索なし", "live": "live検索"}
    return mapping.get(str(value), str(value or "不明"))


def _runs_next_command(run: dict[str, Any], ledger: dict[str, Any]) -> str:
    run_id = str(run.get("run_id") or "<run_id>")
    if ledger.get("file_backed"):
        return f"yonerai runs show {run_id} --ledger <local.jsonl> --json"
    return '履歴を残すには: yonerai ask "hello" --auto --ledger .yonerai-runs.jsonl --json'
