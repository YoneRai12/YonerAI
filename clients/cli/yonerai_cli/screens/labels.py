from __future__ import annotations

import re
from typing import Any

from yonerai_cli.config import AGENT_MODES, APPROVAL_MODES, FILE_ACCESS_MODES, PROVIDER_PREFERENCES


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"(?i)(authorization|api[_-]?key|token|secret)\s*[:=]\s*[^,\s]+"),
)
PATH_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^,\s]+", re.IGNORECASE),
    re.compile(r"/(?:home|Users|root)/[^,\s]+"),
)
CONTROL_CHARACTER_TRANSLATION: dict[int, str] = {codepoint: f"\\x{codepoint:02x}" for codepoint in range(32)}
CONTROL_CHARACTER_TRANSLATION[0x7F] = "\\x7f"
for codepoint in range(0x80, 0xA0):
    CONTROL_CHARACTER_TRANSLATION[codepoint] = f"\\x{codepoint:02x}"


def _safe(value: object) -> str:
    text = " ".join(str(value).split())
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    for pattern in PATH_PATTERNS:
        text = pattern.sub("[LOCAL_PATH]", text)
    text = text.translate(CONTROL_CHARACTER_TRANSLATION)
    return text[:500]


def _selector(option: str, selected: str) -> str:
    return ">" if option == selected else " "


def _language_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"ja": "日本語", "en": "英語"}.get(str(value), _safe(value))


def _provider_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    labels = {
        "auto": "自動（安全に選択）",
        "mock": "モック（テスト用）",
        "local": "ローカル（PC内モデル）",
        "openai-compatible": "OpenAI互換（外部API）",
        "anthropic": "Anthropic（外部API）",
        "gemini": "Gemini（外部API）",
        "unknown": "不明",
        None: "不明",
    }
    return labels.get(value, _safe(value or "不明"))


def _route_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    labels = {
        "instant_local": "ローカルで即時実行",
        "local_llm": "ローカルLLM（PC内モデル）",
        "hybrid_node": "ハイブリッド（ローカル優先）",
        "cloud_contract_candidate": "クラウド候補（ローカル開発スタブ）",
        "deny": "拒否",
    }
    return labels.get(value, _safe(value or "不明"))


def _approval_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"prompt": "毎回確認", "deny": "拒否"}.get(str(value), _safe(value))


def _agent_mode_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {
        "plan_readonly": "計画（読み取り専用）",
        "build_safe": "安全実行",
        "review": "レビュー",
        "memory": "記憶",
    }.get(str(value), _safe(value))


def _file_access_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"workspace_only": "ワークスペース内のみ", "disabled": "無効"}.get(str(value), _safe(value))


def _run_status_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    return {"completed": "完了", "failed": "失敗", "in_progress": "実行中"}.get(str(value), _safe(value or "不明"))


def _state_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    labels = {
        "ready_now": "今すぐ利用可能",
        "ready_for_explicit_local_live": "明示許可でローカル利用可能",
        "configured_for_explicit_live": "明示許可で利用可能",
        "loopback_server_detected_enable_env": "検出済み（有効化待ち）",
        "not_enabled_or_not_detected": "未有効または未検出",
        "needs_live_opt_in": "明示liveが必要",
        "not_configured": "未設定",
        "missing_configuration": "設定不足",
        "disabled": "無効",
        "blocked_by_loopback_policy": "ループバック以外のため拒否",
        "invalid_configuration": "設定が不正",
        "unknown": "不明",
    }
    return labels.get(str(value), _safe(value))


def _local_llm_status_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value or "unknown")
    labels = {
        "detected": "検出済み",
        "unavailable": "未検出",
        "blocked": "安全ポリシーで拒否",
        "ready": "利用可能",
        "ready_now": "今すぐ利用可能",
        "disabled": "無効",
        "unknown": "不明",
    }
    return labels.get(str(value), _safe(value or "不明"))


def _capability_summary(capabilities: dict[str, Any], *, lang: str) -> str:
    names = [
        ("chat", "チャット"),
        ("streaming", "ストリーミング"),
        ("json", "JSON"),
        ("tool_calling", "ツール呼び出し"),
        ("vision", "画像"),
        ("search", "検索"),
        ("embeddings", "埋め込み"),
    ]
    if lang == "ja":
        enabled = [label for key, label in names if capabilities.get(key)]
        return " / ".join(enabled) if enabled else "公開できるcapabilityは未設定"
    enabled_en = [key for key, _label in names if capabilities.get(key)]
    return ", ".join(enabled_en) if enabled_en else "none"


def _provider_hint_ja(item: dict[str, Any]) -> str:
    provider_id = str(item.get("provider_id") or "")
    hint = _safe(item.get("setup_hint") or "")
    if provider_id == "mock":
        return "設定不要。初期値で使えます"
    if provider_id == "local":
        return "Ollama / LM Studio をPC内で起動し、loopback endpointだけを設定します"
    if item.get("external_provider"):
        return "環境変数と --live が必要です。キーの値は表示・保存しません"
    return hint or "状態を確認してください"


def _setting_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    labels = {
        "language": "表示言語",
        "command_display": "コマンド表示",
        "command_display_mode": "コマンド表示",
        "provider": "提供元（AI接続元）",
        "model": "モデル（AIモデル）",
        "agent_mode": "作業モード",
        "permissions": "権限と承認",
        "approval": "承認（危険操作）",
        "file_access": "ファイルアクセス（ファイル読み取り）",
        "ledger": "履歴記録（ローカル履歴）",
        "memory_enabled": "記憶（ローカル記憶）",
        "memory_default_scope": "記憶の既定スコープ",
        "memory_cloud_to_local_preview_enabled": "cloud -> local記憶preview",
        "memory_self_evolution_signal_enabled": "self-evolution signal記憶",
        "update_notice": "更新通知（安定版/ベータ版確認）",
        "live_provider": "ライブ接続（外部/ローカル実行）",
        "network": "ネットワーク（外部通信）",
    }
    return labels.get(str(value), _safe(value))


def _value_label(value: object, *, lang: str) -> str:
    if lang != "ja":
        return _safe(value)
    if value in {"ja", "en"}:
        return _language_label(value, lang=lang)
    command_display_labels = {
        "ja_only": "日本語だけ",
        "ja_with_en": "日本語 + 英語",
        "en_with_ja": "英語 + 日本語",
        "en_only": "英語だけ",
    }
    if value in command_display_labels:
        return command_display_labels[str(value)]
    if value in PROVIDER_PREFERENCES:
        return _provider_label(value, lang=lang)
    if value in AGENT_MODES:
        return _agent_mode_label(value, lang=lang)
    if value in APPROVAL_MODES:
        return _approval_label(value, lang=lang)
    permission_labels = {
        "read_only": "読み取り専用",
        "auto_safe": "自動安全",
        "ask_before_risky": "危険時確認",
        "dry_run_only": "ドライランのみ",
    }
    if value in permission_labels:
        return permission_labels[str(value)]
    if value in FILE_ACCESS_MODES:
        return _file_access_label(value, lang=lang)
    if type(value) is bool:
        return "オン" if value else "オフ"
    return _safe(value)


def _yes_no(value: object, *, lang: str) -> str:
    if lang != "ja":
        return "true" if value else "false"
    return "はい" if value else "いいえ"
