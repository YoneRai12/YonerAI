from __future__ import annotations

from typing import Any

from yonerai_cli.screens.labels import _agent_mode_label, _provider_label, _safe


def format_input_composer(
    *,
    lang: str,
    config: dict[str, object],
    provider: str,
    live: bool,
) -> str:
    model = _safe(config.get("model_preference") or "auto")
    mode = _agent_mode_label(config.get("agent_mode") or "plan_readonly", lang=lang)
    if lang == "ja":
        return "\n".join(
            (
                "入力欄",
                "  そのまま日本語で質問を書くと ask --auto 経路で実行します。",
                "  / を入力すると候補が出ます。候補が出ない端末では /コマンド と /選択 を使います。",
                "  Enterで送信。Tab/矢印: 利用できる端末では補完候補の移動に使います。",
                "",
                "今の入力状態",
                f"  提供元（AI接続先）: {_provider_label(provider, lang='ja')}",
                f"  モデル（AIモデル）: {model}",
                f"  作業モード: {mode}",
                f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'}",
                f"  記憶: {'オン' if bool(config.get('memory_enabled')) else 'オフ'} / raw内容は表示・送信しません",
                "",
                "使えるショートカット",
                "  /設定        設定カテゴリ",
                "  /モデル      PC内モデル/モデル選択",
                "  /提供元      AI接続元の状態",
                "  /安全        安全境界",
                "  /履歴        実行履歴",
                "  /コンテキスト 参照できる文脈",
                "  @planner / @reviewer / @researcher / @implementer / @tester",
                "",
                "禁止していること",
                "  任意shell実行なし / workspace外ファイル読み取りなし / provider key表示なし",
                "  local private memory の自動uploadなし / production Oracle・cloud実行なし",
                "",
            )
        )
    return "\n".join(
        (
            "Input composer",
            "  Type a normal message to run through ask --auto.",
            "  Type / for suggestions. If completion is unavailable, use /palette and /select.",
            "  Tab/arrows: used for completion when the terminal supports it.",
            "",
            "Current input state",
            f"  provider: {_safe(provider)}",
            f"  model: {model}",
            f"  agent_mode: {mode}",
            f"  live: {'on explicit' if live else 'off by default'}",
            f"  memory: {'on' if bool(config.get('memory_enabled')) else 'off'} / raw content is not shown or sent",
            "",
            "Shortcuts",
            "  /settings /models /providers /safety /runs /context",
            "  @planner / @reviewer / @researcher / @implementer / @tester",
            "",
            "Boundaries",
            "  no arbitrary shell, no files outside workspace, no provider key output",
            "  no local private memory auto-upload, no production Oracle/cloud runtime",
            "",
        )
    )


def composer_capability_summary(*, lang: str, config: dict[str, object]) -> dict[str, Any]:
    return {
        "ok": True,
        "lang": lang,
        "slash_completion": True,
        "plain_fallback": True,
        "agent_mentions": ["planner", "reviewer", "researcher", "implementer", "tester"],
        "live_provider_enabled": bool(config.get("live_provider_enabled")),
        "memory_enabled": bool(config.get("memory_enabled")),
        "actions_not_performed": [
            "no shell execution",
            "no workspace file auto-read",
            "no provider key output",
            "no cloud upload",
        ],
    }
