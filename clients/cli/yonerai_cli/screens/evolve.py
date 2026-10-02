from __future__ import annotations

from typing import Any

from yonerai_cli.screens.labels import _safe, _yes_no


def _format_evolve_status(report: dict[str, Any], *, lang: str) -> str:
    actions = report.get("actions_not_performed") if isinstance(report.get("actions_not_performed"), list) else []
    policy = report.get("input_policy") if isinstance(report.get("input_policy"), dict) else {}
    if lang == "ja":
        lines = [
            "自己進化プロポーザル",
            f"  状態: {_safe(report.get('status') or '不明')}",
            f"  proposal-only: {_yes_no(report.get('proposal_only'), lang='ja')}",
            f"  既定signal数: {_safe(report.get('default_signal_count') or 0)}",
            "  入力: 合成/低解像度signalだけ",
            f"  raw prompt許可: {_yes_no(policy.get('raw_prompt_allowed'), lang='ja')}",
            f"  PII許可: {_yes_no(policy.get('pii_allowed'), lang='ja')}",
            f"  安定ユーザー追跡: {_yes_no(policy.get('stable_user_tracking_allowed'), lang='ja')}",
            "  実行しないこと:",
        ]
        for action in actions[:8]:
            lines.append(f"    - {_safe(action)}")
        lines.append("  試す: yonerai evolve simulate --pretty --lang ja")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Self-evolution proposals",
            f"  status: {_safe(report.get('status') or 'unknown')}",
            f"  proposal_only: {bool(report.get('proposal_only'))}",
            f"  default_signal_count: {_safe(report.get('default_signal_count') or 0)}",
            "  input: synthetic low-resolution signals only",
            f"  raw_prompt_allowed: {bool(policy.get('raw_prompt_allowed'))}",
            f"  pii_allowed: {bool(policy.get('pii_allowed'))}",
            f"  stable_user_tracking_allowed: {bool(policy.get('stable_user_tracking_allowed'))}",
            "  actions_not_performed: " + ", ".join(_safe(action) for action in actions[:8]),
            "  try: yonerai evolve simulate --pretty --lang en",
            "",
        )
    )


def _format_evolve_unavailable(lang: str) -> str:
    if lang == "ja":
        return "自己進化プロポーザルキューはこのビルドでは利用できません。\n"
    return "Self-evolution proposal queue is unavailable in this build.\n"
