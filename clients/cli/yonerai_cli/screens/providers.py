from __future__ import annotations

from typing import Any

from yonerai_cli.output import CliRow, CliSection, ColorMode, render_report
from yonerai_cli.screens.labels import (
    _capability_summary,
    _local_llm_status_label,
    _provider_hint_ja,
    _provider_label,
    _safe,
    _state_label,
    _yes_no,
)
from yonerai_cli.screens.settings import _provider_state
from yonerai_cli.tui import tui_capability_report


def format_providers_pretty(report: dict[str, Any], *, lang: str = "ja", color: ColorMode = "auto") -> str:
    if lang == "ja":
        title = "YonerAI プロバイダー"
        sections = _provider_sections_ja(report)
    else:
        title = "YonerAI providers"
        sections = _provider_sections_en(report)
    return render_report(title, sections, color=color)


def _provider_sections_en(report: dict[str, Any]) -> tuple[CliSection, ...]:
    providers = _provider_entries(report)
    return (
        CliSection(
            "Recommended first command",
            (
                CliRow("command", report.get("recommended_first_command"), "ok"),
                CliRow(
                    "live_call_performed",
                    report.get("live_call_performed"),
                    "fail" if report.get("live_call_performed") else "ok",
                ),
                CliRow(
                    "network_probe_performed",
                    report.get("network_probe_performed"),
                    "fail" if report.get("network_probe_performed") else "ok",
                ),
                CliRow(
                    "loopback_probe_performed",
                    report.get("loopback_probe_performed"),
                    "warn" if report.get("loopback_probe_performed") else "ok",
                ),
            ),
        ),
        *(_provider_entry_section_en(provider) for provider in providers),
        CliSection(
            "Non-actions",
            tuple(CliRow(f"no_{index}", item, "ok") for index, item in enumerate(report.get("actions_not_performed") or [], start=1)),
        ),
    )


def _provider_sections_ja(report: dict[str, Any]) -> tuple[CliSection, ...]:
    providers = _provider_entries(report)
    return (
        CliSection(
            "最初に試すコマンド",
            (
                CliRow("command", report.get("recommended_first_command"), "ok"),
                CliRow("live呼び出し", _yes_no_ja(report.get("live_call_performed")), "fail" if report.get("live_call_performed") else "ok"),
                CliRow(
                    "外部ネットワークprobe",
                    _yes_no_ja(report.get("network_probe_performed")),
                    "fail" if report.get("network_probe_performed") else "ok",
                ),
                CliRow(
                    "loopback確認",
                    _yes_no_ja(report.get("loopback_probe_performed")),
                    "warn" if report.get("loopback_probe_performed") else "ok",
                ),
            ),
        ),
        *(_provider_entry_section_ja(provider) for provider in providers),
        CliSection(
            "このコマンドがしないこと",
            tuple(
                CliRow(f"未実行{index}", _provider_non_action_ja(str(item)), "ok")
                for index, item in enumerate(report.get("actions_not_performed") or [], start=1)
            ),
        ),
    )


def _provider_entry_section_en(provider: dict[str, object]) -> CliSection:
    provider_id = str(provider.get("provider_id") or "unknown")
    return CliSection(
        provider_id,
        (
            CliRow("state", provider.get("plain_state"), _provider_plain_state_level(provider.get("plain_state"))),
            CliRow("configured", provider.get("configured"), "ok" if provider.get("configured") else "warn"),
            CliRow("available", provider.get("available"), "ok" if provider.get("available") else "warn"),
            CliRow("requires_live", provider.get("requires_live_flag", False), "warn" if provider.get("requires_live_flag") else "ok"),
            CliRow(
                "private_context_safe",
                provider.get("safe_for_private_context"),
                "ok" if provider.get("safe_for_private_context") else "warn",
            ),
            CliRow("capabilities", _provider_capability_summary(provider, lang="en"), "ok"),
            CliRow("subagents", _provider_subagent_summary(provider, lang="en"), "ok" if _provider_subagent_ready(provider) else "skipped"),
            CliRow("command", provider.get("command"), "ok"),
            CliRow("does", provider.get("does"), "ok"),
            CliRow("does_not", provider.get("does_not"), "ok"),
            CliRow("setup", provider.get("setup_hint"), "ok" if provider.get("available") else "warn"),
        ),
    )


def _provider_entry_section_ja(provider: dict[str, object]) -> CliSection:
    provider_id = str(provider.get("provider_id") or "unknown")
    return CliSection(
        _provider_label_ja(provider_id),
        (
            CliRow("状態", _provider_plain_state_text_ja(provider.get("plain_state")), _provider_plain_state_level(provider.get("plain_state"))),
            CliRow("設定済み", _yes_no_ja(provider.get("configured")), "ok" if provider.get("configured") else "warn"),
            CliRow("利用可能", _yes_no_ja(provider.get("available")), "ok" if provider.get("available") else "warn"),
            CliRow("--live必須", _yes_no_ja(provider.get("requires_live_flag", False)), "warn" if provider.get("requires_live_flag") else "ok"),
            CliRow(
                "private/local file",
                "送らない" if provider.get("safe_for_private_context") else "送らないため自動経路ではブロック",
                "ok" if provider.get("safe_for_private_context") else "warn",
            ),
            CliRow("機能", _provider_capability_summary(provider, lang="ja"), "ok"),
            CliRow("担当計画", _provider_subagent_summary(provider, lang="ja"), "ok" if _provider_subagent_ready(provider) else "skipped"),
            CliRow("コマンド", provider.get("command"), "ok"),
            CliRow("何をするか", _provider_does_ja(provider_id), "ok"),
            CliRow("何をしないか", _provider_does_not_ja(provider_id), "ok"),
            CliRow("次の設定", _provider_setup_hint_ja(provider_id, provider), "ok" if provider.get("available") else "warn"),
        ),
    )


def _provider_capability_summary(provider: dict[str, object], *, lang: str) -> str:
    capabilities = provider.get("capabilities") if isinstance(provider.get("capabilities"), dict) else {}
    if not capabilities:
        return "未確認" if lang == "ja" else "unknown"
    keys = (
        ("chat", "会話", "chat"),
        ("json", "JSON", "json"),
        ("streaming", "ストリーミング", "streaming"),
        ("tool_calling", "ツール呼び出し", "tool_calling"),
        ("vision", "画像", "vision"),
        ("search", "検索", "search"),
        ("embeddings", "埋め込み", "embeddings"),
    )
    enabled: list[str] = []
    for key, label_ja, label_en in keys:
        if capabilities.get(key) is True:
            enabled.append(label_ja if lang == "ja" else label_en)
    if not enabled:
        return "会話なし" if lang == "ja" else "no advertised capabilities"
    max_context = capabilities.get("max_context")
    suffix = ""
    if isinstance(max_context, int):
        suffix = f" / 文脈上限={max_context}" if lang == "ja" else f" / max_context={max_context}"
    return ", ".join(enabled) + suffix


def _provider_subagent_ready(provider: dict[str, object]) -> bool:
    capabilities = provider.get("capabilities") if isinstance(provider.get("capabilities"), dict) else {}
    return capabilities.get("safe_for_subagents") is True


def _provider_subagent_summary(provider: dict[str, object], *, lang: str) -> str:
    capabilities = provider.get("capabilities") if isinstance(provider.get("capabilities"), dict) else {}
    if capabilities.get("safe_for_subagents") is True:
        return "計画表示のみで利用可" if lang == "ja" else "plan display only"
    reason = str(capabilities.get("subagent_fallback_reason") or "provider_not_ready")
    if lang == "ja":
        labels = {
            "chat_capability_missing": "会話機能がないため計画表示のみ",
            "provider_unavailable_or_not_configured": "provider未設定のため計画表示のみ",
            "provider_not_registered_for_subagents": "未登録providerのため計画表示のみ",
            "provider_not_ready": "準備不足のため計画表示のみ",
        }
        return labels.get(reason, "準備不足のため計画表示のみ")
    return f"fallback: {reason}"


def _provider_entries(report: dict[str, Any]) -> tuple[dict[str, object], ...]:
    providers = report.get("providers")
    if not isinstance(providers, list):
        return ()
    return tuple(provider for provider in providers if isinstance(provider, dict))


def _provider_plain_state_level(state: object) -> str:
    if state in {"ready_now", "ready_for_explicit_local_live", "configured_for_explicit_live"}:
        return "ok"
    if state in {"blocked_by_loopback_policy", "invalid_configuration"}:
        return "fail"
    return "warn"


def _provider_label_ja(provider_id: str) -> str:
    mapping = {
        "mock": "mock provider",
        "local": "local LLM",
        "openai-compatible": "OpenAI-compatible",
        "anthropic": "Anthropic",
        "gemini": "Gemini",
    }
    return mapping.get(provider_id, provider_id)


def _provider_plain_state_text_ja(state: object) -> str:
    mapping = {
        "ready_now": "今すぐ利用可能",
        "ready_for_explicit_local_live": "明示的なlocal --liveで利用可能",
        "loopback_server_detected_enable_env": "loopbackサーバー検出済み、env有効化が必要",
        "blocked_by_loopback_policy": "loopbackポリシーで拒否",
        "not_enabled_or_not_detected": "未有効または未検出",
        "configured_for_explicit_live": "明示的な--liveで利用可能",
        "needs_live_opt_in": "provider別live opt-inが必要",
        "invalid_configuration": "設定が不正",
        "not_configured": "未設定",
    }
    return mapping.get(str(state), "不明")


def _provider_does_ja(provider_id: str) -> str:
    mapping = {
        "mock": "API keyなしで安全なrun_id付き応答を返します。",
        "local": "明示的に有効化したloopback-only local LLMを--live時だけ使います。",
        "openai-compatible": "--liveとenv opt-inがある場合だけOpenAI互換endpointを呼びます。",
        "anthropic": "--liveとenv opt-inがある場合だけAnthropicを呼びます。",
        "gemini": "--liveとenv opt-inがある場合だけGeminiを呼びます。",
    }
    return mapping.get(provider_id, "provider設定状態を表示します。")


def _provider_does_not_ja(provider_id: str) -> str:
    if provider_id == "mock":
        return "live provider、local LLM、Discord、Oracle、official cloudには接続しません。"
    if provider_id == "local":
        return "非loopback URL、埋め込みcredential、既定live実行は許可しません。"
    if provider_id in {"openai-compatible", "anthropic", "gemini"}:
        return "既定では実行せず、private/local-file自動経路には送らず、keyも表示しません。"
    return "providersコマンド自体はprovider呼び出しを実行しません。"


def _provider_setup_hint_ja(provider_id: str, provider: dict[str, object]) -> str:
    hint = str(provider.get("setup_hint") or "")
    if provider_id == "mock":
        return "設定不要です。"
    if provider_id == "local" and provider.get("plain_state") == "loopback_server_detected_enable_env":
        return "ORA_LOCAL_LLM_ENABLED=1 を設定して --provider local --live を使います。"
    if provider_id == "local" and provider.get("plain_state") == "blocked_by_loopback_policy":
        return "localhost / 127.0.0.1 / ::1 のみ許可します。credential、query、fragmentは不可です。"
    return hint


def _yes_no_ja(value: object) -> str:
    return "はい" if value is True else "いいえ"


def _provider_non_action_ja(value: str) -> str:
    mapping = {
        "no external provider call": "外部providerを呼び出しません",
        "no local LLM text generation": "local LLMへpromptを送りません",
        "no provider key output": "provider keyを表示しません",
        "no live Discord": "live Discordへ接続しません",
        "no production Oracle": "official Oracleへ接続しません",
        "no official cloud runtime": "official cloud runtimeなし",
        "no shell execution": "shell実行なし",
        "no file read": "ファイル読み取りなし",
        "no install": "installなし",
        "no PATH mutation": "PATH変更なし",
    }
    return mapping.get(value, value)


def _format_providers(report: dict[str, Any], *, lang: str) -> str:
    providers = report.get("providers") if isinstance(report.get("providers"), list) else []
    lines = ["提供元（AI接続元）" if lang == "ja" else "Providers"]
    for item in providers:
        if not isinstance(item, dict):
            continue
        capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else {}
        command = _safe(item.get("command") or 'yonerai ask "hello" --auto --json')
        if lang == "ja":
            lines.append(
                f"  {_provider_label(item.get('provider_id'), lang='ja')}: "
                f"{_state_label(item.get('plain_state') or item.get('setup_status'), lang='ja')} "
                f"（設定={_yes_no(item.get('configured'), lang='ja')}）"
            )
            lines.append(f"    次に試す: {command}")
            lines.append(f"    セットアップ: {_provider_hint_ja(item)}")
            lines.append(f"    できること: {_capability_summary(capabilities, lang=lang)}")
            lines.append(f"    しないこと: {_safe(item.get('does_not') or 'キー表示、既定のlive呼び出し、任意操作はしません')}")
        else:
            lines.append(
                f"  {item.get('provider_id')}: {item.get('plain_state') or item.get('setup_status')} "
                f"(configured={item.get('configured')})"
            )
            lines.append(f"    next: {command}")
            lines.append(f"    setup: {_safe(item.get('setup_hint') or 'No setup hint.')}")
            lines.append(f"    capabilities: {_capability_summary(capabilities, lang=lang)}")
            lines.append(f"    does_not: {_safe(item.get('does_not') or '')}")
    lines.append("  キー（秘密情報）: 表示しません。設定にも保存しません" if lang == "ja" else "  keys: redacted / not printed")
    if lang == "ja":
        lines.append("  ローカルLLM: localhost / 127.0.0.1 / ::1 だけを許可します")
        lines.append("  外部API: --live と provider別 env opt-in がある時だけ呼びます")
    lines.append("")
    return "\n".join(_safe(line) for line in lines)

def _format_models(config: dict[str, object], report: dict[str, Any], *, lang: str) -> str:
    model = _safe(config.get("model_preference") or "auto")
    local_state = _provider_state(report, "local")
    capabilities = tui_capability_report()
    if lang == "ja":
        return "\n".join(
            (
                "モデル（AIモデル）",
                f"  現在のモデル指定: {model}",
                f"  ローカルLLM（PC内モデル）: {_state_label(local_state, lang='ja')}",
                f"  補完UI: {'利用可能' if capabilities['slash_completion'] else '通常入力にフォールバック'}",
                "  変更: /モデル auto または /モデル llama3.1 など",
                "  ローカルLLM設定: localhost / 127.0.0.1 / ::1 のみ。非ループバックURLは拒否します。",
                "  Ollama例: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
                "  LM Studio例: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
                "  実行しないこと: モデルの自動インストール、外部URL探索、APIキー保存、プロンプト送信",
                "",
            )
        )
    return "\n".join(
        (
            "Models",
            f"  model_preference: {model}",
            f"  local_llm: {local_state}",
            f"  slash_completion: {capabilities['slash_completion']}",
            "  change: /model auto or /model llama3.1",
            "  local LLM endpoints: localhost / 127.0.0.1 / ::1 only",
            "  not_performed: no model installation, no external probing, no key storage, no prompt sent",
            "",
        )
    )

def _format_local_llm_setup(report: dict[str, Any], *, lang: str) -> str:
    local_state = _provider_state(report, "local")
    local_llm = report.get("local_llm") if isinstance(report.get("local_llm"), dict) else {}
    probes = local_llm.get("probes") if isinstance(local_llm.get("probes"), list) else []
    detected = str(local_llm.get("status") or "unknown")
    endpoint_label = _safe(local_llm.get("endpoint_label") or local_llm.get("detected_label") or "未検出")
    if lang == "ja":
        lines = [
            "ローカルLLMセットアップ",
            f"  現在の状態: {_state_label(local_state, lang='ja')}",
            f"  検出状態: {_local_llm_status_label(detected, lang='ja')}",
            f"  検出endpoint: {endpoint_label}",
            "  対応形態: Ollama系 / LM Studio系 / OpenAI互換のローカルHTTP API",
            "  許可する接続先: localhost / 127.0.0.1 / ::1 のみ",
            "  例（Ollama）: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
            "  例（LM Studio）: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
            "  使う: /提供元選択 ローカル。その後、この画面で通常文を入力します。",
            "  実行しないこと: 外部URL接続、APIキー保存、任意シェル実行、モデルの自動インストール",
        ]
        if probes:
            lines.append("  確認した候補（プロンプト送信なし）:")
            for probe in probes[:4]:
                if isinstance(probe, dict):
                    lines.append(
                        f"    - {_safe(probe.get('label') or probe.get('provider') or 'local')}: "
                        f"{_local_llm_status_label(probe.get('status'), lang='ja')} / {_safe(probe.get('reason') or '理由なし')}"
                    )
        lines.append("  次に試す: 先に Ollama または LM Studio を起動し、必要な env を設定してから /提供元選択 ローカル")
        lines.append("")
        return "\n".join(lines)
    return "\n".join(
        (
            "Local LLM setup",
            f"  current_state: {_safe(local_state)}",
            f"  detection_status: {_safe(detected)}",
            f"  endpoint: {endpoint_label}",
            "  supported: Ollama-style / LM Studio-style / local OpenAI-compatible HTTP API",
            "  allowed_endpoint: localhost / 127.0.0.1 / ::1 only",
            "  Ollama example: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=ollama, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:11434",
            "  LM Studio example: ORA_LOCAL_LLM_ENABLED=1, ORA_LOCAL_LLM_PROVIDER=lmstudio, ORA_LOCAL_LLM_BASE_URL=http://127.0.0.1:1234/v1",
            "  use: /provider local or yonerai ask \"hello\" --provider local --live",
            "  not_performed: no external URL, no key storage, no arbitrary shell, no model installation",
            "",
        )
    )
