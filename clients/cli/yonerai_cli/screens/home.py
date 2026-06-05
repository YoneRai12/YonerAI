from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from yonerai_cli.screens.labels import (
    _agent_mode_label,
    _approval_label,
    _file_access_label,
    _provider_label,
    _safe,
    _yes_no,
)


def format_home_screen(lines: Iterable[str]) -> str:
    """Render the interactive home screen from precomputed display lines."""

    return "\n".join(lines)


def build_home_policy_line(report: dict[str, Any] | None, *, lang: str) -> str:
    policies = report.get("policies") if isinstance(report, dict) and isinstance(report.get("policies"), dict) else {}
    provider = policies.get("provider") if isinstance(policies.get("provider"), dict) else {}
    permission = policies.get("permission") if isinstance(policies.get("permission"), dict) else {}
    runtime = policies.get("runtime") if isinstance(policies.get("runtime"), dict) else {}
    update = policies.get("update") if isinstance(policies.get("update"), dict) else {}
    memory = policies.get("memory_sync") if isinstance(policies.get("memory_sync"), dict) else {}
    if lang == "ja":
        source = "ローカル設定 + 公開契約"
        live = "外部live=" + ("オン" if provider.get("live_external_provider_enabled") else "オフ")
        shell = "任意shell=" + ("有効" if permission.get("arbitrary_shell_execution") else "無効")
        cloud = "公式cloud=" + ("有効" if runtime.get("official_cloud_runtime_in_public_repo") else "無効")
        oracle = "本番Oracle=" + ("有効" if runtime.get("production_oracle_in_public_repo") else "無効")
        update_state = "自動更新=" + ("有効" if update.get("auto_apply_enabled") else "なし")
        memory_state = "local->cloud自動同期=" + ("有効" if memory.get("local_private_auto_upload") else "なし")
        return " / ".join((source, live, shell, cloud, oracle, update_state, memory_state))
    source = "local config + public contracts"
    live = f"external_live={bool(provider.get('live_external_provider_enabled'))}"
    shell = f"arbitrary_shell={bool(permission.get('arbitrary_shell_execution'))}"
    cloud = f"official_cloud={bool(runtime.get('official_cloud_runtime_in_public_repo'))}"
    oracle = f"production_oracle={bool(runtime.get('production_oracle_in_public_repo'))}"
    update_state = f"auto_update={bool(update.get('auto_apply_enabled'))}"
    memory_state = f"local_private_auto_upload={bool(memory.get('local_private_auto_upload'))}"
    return " / ".join((source, live, shell, cloud, oracle, update_state, memory_state))


def build_home_safety_line(report: dict[str, Any] | None, *, config: dict[str, object], lang: str) -> str:
    policies = report.get("policies") if isinstance(report, dict) and isinstance(report.get("policies"), dict) else {}
    permission = policies.get("permission") if isinstance(policies.get("permission"), dict) else {}
    provider = policies.get("provider") if isinstance(policies.get("provider"), dict) else {}
    approval = str(permission.get("approval_mode") or config.get("approval_mode") or "prompt")
    file_access = str(permission.get("file_access_mode") or config.get("file_access_mode") or "workspace_only")
    tools = str(permission.get("tools_mode") or config.get("tools_mode") or "dry_run")
    shell_enabled = bool(permission.get("arbitrary_shell_execution"))
    live_enabled = bool(provider.get("live_external_provider_enabled"))
    if lang == "ja":
        return " / ".join(
            (
                f"承認={_approval_label(approval, lang='ja')}",
                f"ファイル={_file_access_label(file_access, lang='ja')}",
                f"ツール={tools}",
                "任意shell=" + ("有効" if shell_enabled else "無効"),
                "外部live=" + ("オン" if live_enabled else "オフ"),
            )
        )
    return " / ".join(
        (
            f"approval={approval}",
            f"file_access={file_access}",
            f"tools={tools}",
            f"arbitrary_shell={shell_enabled}",
            f"external_live={live_enabled}",
        )
    )

def _welcome(
    lang: str,
    *,
    provider: str,
    live: bool,
    config_exists: bool,
    config: dict[str, object],
    ledger_path: str | None,
    policy_report: dict[str, Any] | None = None,
) -> str:
    ledger = "オン" if ledger_path else "オフ"
    ledger_en = "on" if ledger_path else "off"
    model = _safe(config.get("model_preference") or "auto")
    agent_mode = _safe(config.get("agent_mode") or "plan_readonly")
    update_notice = "オン" if config.get("update_notice_enabled") else "オフ"
    update_notice_en = "on" if config.get("update_notice_enabled") else "off"
    policy_line = build_home_policy_line(policy_report, lang=lang)
    safety_line = build_home_safety_line(policy_report, config=config, lang=lang)
    if lang == "ja":
        return format_home_screen(
            (
                "YonerAI ミッションコントロール CLI",
                "日本語モード。/ヘルプ でコマンドを表示します。",
                "状態ヘッダー",
                f"  提供元（AI接続元）: {_provider_label(provider, lang='ja')}",
                f"  モデル（AIモデル）: {model}",
                f"  作業モード: {_agent_mode_label(agent_mode, lang='ja')}",
                "  経路（処理方法）: 未実行",
                "  ローカルノード: 待機中（ローカル開発 / ループバック限定）",
                f"  履歴: {ledger}（秘匿済みローカル履歴）",
                f"  安全: {safety_line}",
                f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'} / 設定={'既存' if config_exists else '初期値'}",
                f"  更新通知: {update_notice}（ローカルmanifest確認のみ）",
                f"  ポリシー: {policy_line}",
                "  認証/同期/プライバシー: Google OAuthドライランのみ / local->cloud自動同期なし / 共有トラフィックオフ",
                "  自己進化: proposal-only / 合成signalだけ / 自動PR・deployなし",
                "使う: そのまま質問を書く / / で候補表示 / /入力 / /コマンド / /設定 / /モード / /計画 / /レビュー / /権限 / /モデル / /提供元 / /安全 / /ポリシー / /進行 / /履歴 / /認証 / /同期 / /自己進化 / /更新",
                "設定を変える: /選択 <番号> <値>",
                "",
            )
        )
    return format_home_screen(
        (
            "YonerAI Mission Control CLI",
            "English mode. Type /help for commands.",
            f"provider={provider} model={model} agent_mode={agent_mode} route=not_run local_node=standby ledger={ledger_en} live={'on' if live else 'off'} update_notice={update_notice_en} config={'found' if config_exists else 'created/default'}",
            f"Safety: {safety_line}",
            f"Policy: {policy_line}",
            "Auth/sync/privacy: Google OAuth dry-run only / no automatic local-to-cloud sync / shared traffic off",
            "Self-evolution: proposal-only, synthetic signals only, no PR/deploy/mutation",
            "Use: type a message, / for suggestions, /composer, /palette, /settings, /mode, /plan, /review, /permissions, /models, /providers, /safety, /policy, /progress, /runs, /auth, /sync, /evolve, /update",
            "",
        )
    )
