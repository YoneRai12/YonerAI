from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse

from .output import CliRow, CliSection, ColorMode, render_report


FIRST_RUN_SCHEMA_VERSION = "yonerai-first-run/v1"
LOCAL_LLM_PROBE_TIMEOUT_SECONDS = 1.0


@dataclass(frozen=True)
class LocalLLMProbeCandidate:
    provider: str
    label: str
    base_url: str
    probe_path: str


DEFAULT_LOCAL_LLM_CANDIDATES = (
    LocalLLMProbeCandidate(
        provider="ollama",
        label="Ollama",
        base_url="http://127.0.0.1:11434",
        probe_path="api/tags",
    ),
    LocalLLMProbeCandidate(
        provider="openai_compatible_local",
        label="LM Studio / OpenAI-compatible local",
        base_url="http://127.0.0.1:1234/v1",
        probe_path="models",
    ),
)


def build_first_run_report(
    *,
    provider_setup: Mapping[str, object] | None = None,
    repo_version: str | None = None,
    env: Mapping[str, str | None] | None = None,
    local_llm_candidates: tuple[LocalLLMProbeCandidate, ...] | None = None,
) -> dict[str, object]:
    source = dict(os.environ if env is None else env)
    local_llm = detect_local_llm(source, candidates=local_llm_candidates)
    setup = summarize_provider_setup(provider_setup or {}, local_llm)
    first_ask = _recommended_first_ask(setup)
    return {
        "schema_version": FIRST_RUN_SCHEMA_VERSION,
        "command": "yonerai start",
        "ok": True,
        "repo_version": repo_version,
        "network_scope": "loopback_only",
        "live_provider_call_performed": False,
        "local_llm_generation_performed": False,
        "steps": _first_run_steps(first_ask),
        "local_llm": local_llm,
        "provider_setup": setup,
        "current_capabilities": _current_capabilities(),
        "limitations": _limitations(),
        "actions_not_performed": _actions_not_performed(),
        "recommended_first_ask": first_ask,
    }


def detect_local_llm(
    env: Mapping[str, str | None],
    *,
    candidates: tuple[LocalLLMProbeCandidate, ...] | None = None,
) -> dict[str, object]:
    configured, config_error = _configured_candidate(env)
    if config_error is not None:
        return {
            "status": "blocked",
            "loopback_only": True,
            "probe_performed": False,
            "configured_endpoint_allowed": False,
            "rejected_non_loopback": config_error == "non_loopback_rejected",
            "detected_provider": None,
            "detected_label": None,
            "endpoint_label": None,
            "message": _local_llm_message("blocked"),
            "probes": [],
        }

    probe_candidates = (configured,) if configured is not None else (candidates or DEFAULT_LOCAL_LLM_CANDIDATES)
    probes = tuple(_probe_local_candidate(candidate) for candidate in probe_candidates)
    detected = next((probe for probe in probes if probe["status"] == "detected"), None)
    if detected is not None:
        return {
            "status": "detected",
            "loopback_only": True,
            "probe_performed": True,
            "configured_endpoint_allowed": True if configured is not None else None,
            "rejected_non_loopback": False,
            "detected_provider": detected["provider"],
            "detected_label": detected["label"],
            "endpoint_label": detected["endpoint_label"],
            "message": _local_llm_message("detected"),
            "probes": list(probes),
        }
    return {
        "status": "unavailable",
        "loopback_only": True,
        "probe_performed": bool(probe_candidates),
        "configured_endpoint_allowed": True if configured is not None else None,
        "rejected_non_loopback": False,
        "detected_provider": None,
        "detected_label": None,
        "endpoint_label": None,
        "message": _local_llm_message("unavailable"),
        "probes": list(probes),
    }


def summarize_provider_setup(provider_setup: Mapping[str, object], local_llm: Mapping[str, object]) -> dict[str, object]:
    providers = provider_setup.get("providers") if isinstance(provider_setup, Mapping) else []
    by_id = {
        str(provider.get("provider_id")): provider
        for provider in providers
        if isinstance(provider, Mapping) and provider.get("provider_id")
    }
    return {
        "mock": {
            "plain_state": "ready_now",
            "explanation": "Works now without API keys. This is the safest first ask path.",
            "command": 'yonerai ask "hello" --provider mock --json',
        },
        "local": _local_provider_summary(by_id.get("local", {}), local_llm),
        "openai_compatible": _external_provider_summary(by_id.get("openai-compatible", {})),
    }


def format_first_run_pretty(report: Mapping[str, object], *, lang: str = "en", color: ColorMode = "auto") -> str:
    if lang == "ja":
        return render_report("YonerAI はじめての起動", _first_run_sections_ja(report), color=color)
    return render_report("YonerAI start", _first_run_sections_en(report), color=color)


def _configured_candidate(env: Mapping[str, str | None]) -> tuple[LocalLLMProbeCandidate | None, str | None]:
    raw_provider = env.get("ORA_LOCAL_LLM_PROVIDER")
    raw_base_url = env.get("ORA_LOCAL_LLM_BASE_URL")
    raw_enabled = env.get("ORA_LOCAL_LLM_ENABLED")
    if not any(str(value or "").strip() for value in (raw_provider, raw_base_url, raw_enabled)):
        return None, None
    try:
        from ora_core.providers import local_llm

        provider = local_llm.normalize_local_llm_provider(raw_provider)
        base_url = local_llm.validate_loopback_base_url(
            raw_base_url or _default_base_url_for_provider(provider)
        )
    except Exception as exc:
        return None, _classify_config_error(exc)
    return (
        LocalLLMProbeCandidate(
            provider=provider,
            label=_provider_label(provider),
            base_url=base_url,
            probe_path=_probe_path_for_provider(provider),
        ),
        None,
    )


def _probe_local_candidate(candidate: LocalLLMProbeCandidate) -> dict[str, object]:
    try:
        from ora_core.providers.local_llm import validate_loopback_base_url

        base_url = validate_loopback_base_url(candidate.base_url)
    except Exception:
        return _probe_result(candidate, "blocked", reason="loopback_policy_rejected")

    url = _join_url(base_url, candidate.probe_path)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=LOCAL_LLM_PROBE_TIMEOUT_SECONDS) as response:
            raw = response.read()
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        return _probe_result(candidate, "unavailable", reason=f"http_status_{exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError):
        return _probe_result(candidate, "unavailable", reason="connection_failed")

    if status < 200 or status >= 300:
        return _probe_result(candidate, "unavailable", reason=f"http_status_{status}")
    try:
        json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _probe_result(candidate, "unavailable", reason="invalid_json")
    return _probe_result(candidate, "detected", reason=None)


def _probe_result(candidate: LocalLLMProbeCandidate, status: str, *, reason: str | None) -> dict[str, object]:
    return {
        "provider": candidate.provider,
        "label": candidate.label,
        "endpoint_label": _endpoint_label(candidate.base_url),
        "status": status,
        "reason": reason,
    }


def _join_url(base_url: str, path_suffix: str) -> str:
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/")
    suffix = path_suffix.strip("/")
    path = f"{base_path}/{suffix}" if base_path else f"/{suffix}"
    return parsed._replace(path=path).geturl()


def _endpoint_label(base_url: str) -> str:
    parsed = urlparse(base_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"loopback:{port}"


def _classify_config_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "loopback" in message or "credential" in message or "query" in message or "fragment" in message:
        return "non_loopback_rejected"
    return "invalid_configuration"


def _default_base_url_for_provider(provider: str) -> str:
    if provider == "openai_compatible_local":
        return "http://127.0.0.1:1234/v1"
    return "http://127.0.0.1:11434"


def _probe_path_for_provider(provider: str) -> str:
    if provider == "openai_compatible_local":
        return "models"
    return "api/tags"


def _provider_label(provider: str) -> str:
    if provider == "openai_compatible_local":
        return "LM Studio / OpenAI-compatible local"
    return "Ollama"


def _local_provider_summary(provider: Mapping[str, object], local_llm: Mapping[str, object]) -> dict[str, object]:
    setup_status = str(provider.get("setup_status") or "unknown")
    detected = local_llm.get("status") == "detected"
    if setup_status == "live_ready" and detected:
        state = "ready_for_explicit_live"
        explanation = "A loopback local LLM was detected and the local provider is enabled."
        next_step = 'yonerai ask "hello" --provider local --live --json'
    elif detected:
        state = "local_server_detected_enable_env"
        explanation = "A loopback local LLM was detected. Enable it before using provider local."
        next_step = 'set ORA_LOCAL_LLM_ENABLED=1, then run yonerai ask "hello" --provider local --live --json'
    elif local_llm.get("status") == "blocked":
        state = "blocked_by_loopback_policy"
        explanation = "Configured Local LLM URL was rejected before any request because it is not a safe loopback endpoint."
        next_step = "Use localhost, 127.0.0.1, or ::1 only."
    else:
        state = "not_found"
        explanation = "No loopback Ollama or LM Studio style endpoint was detected."
        next_step = "Start a local LLM server on loopback, or use the mock provider first."
    return {
        "plain_state": state,
        "setup_status": setup_status,
        "loopback_only": True,
        "explanation": explanation,
        "next_step": next_step,
    }


def _external_provider_summary(provider: Mapping[str, object]) -> dict[str, object]:
    setup_status = str(provider.get("setup_status") or "unknown")
    if setup_status == "live_ready":
        state = "configured_for_explicit_live"
        explanation = "OpenAI-compatible settings are present. Actual calls still require --live."
        next_step = 'yonerai ask "hello" --provider openai-compatible --live --json'
    elif setup_status == "live_opt_in_required":
        state = "needs_live_opt_in"
        explanation = "Base URL and key are present, but live execution is still disabled."
        next_step = "Set YONERAI_OPENAI_COMPATIBLE_LIVE=1 only when you want a live call."
    elif setup_status in {"missing_configuration", "unknown"}:
        state = "not_configured"
        explanation = "No OpenAI-compatible provider is configured. The default path does not need a key."
        next_step = "Use the mock provider first, or configure base URL, API key, and live opt-in later."
    else:
        state = "needs_attention"
        explanation = "OpenAI-compatible setup is present but not ready."
        next_step = "Run yonerai doctor --pretty for details."
    return {
        "plain_state": state,
        "setup_status": setup_status,
        "requires_live_flag": True,
        "explanation": explanation,
        "next_step": next_step,
    }


def _recommended_first_ask(provider_setup: Mapping[str, object]) -> dict[str, object]:
    local_provider = provider_setup.get("local") if isinstance(provider_setup.get("local"), Mapping) else {}
    if isinstance(local_provider, Mapping) and local_provider.get("plain_state") == "ready_for_explicit_live":
        return {
            "provider": "local",
            "command": 'yonerai ask "hello" --provider local --live --json',
            "why": "A loopback local model is enabled, so this can use the local provider with explicit --live.",
        }
    return {
        "provider": "mock",
        "command": 'yonerai ask "hello" --provider mock --json',
        "why": "This works immediately without provider keys, ORA_LOCAL_LLM_ENABLED, or a local model server.",
    }


def _first_run_steps(first_ask: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        {
            "step": 1,
            "command": "yonerai demo --pretty",
            "does": "Shows the current public alpha capability slice.",
            "does_not": "Does not call live providers or Discord.",
        },
        {
            "step": 2,
            "command": "yonerai doctor --pretty --lang ja",
            "does": "Checks local CLI, manifest, provider setup, and safety boundaries.",
            "does_not": "Does not install, mutate PATH, or run the demo.",
        },
        {
            "step": 3,
            "command": "yonerai start --json",
            "does": "Checks only loopback Local LLM endpoints and explains setup state.",
            "does_not": "Does not send a prompt to a model.",
        },
        {
            "step": 4,
            "command": str(first_ask["command"]),
            "does": "Runs the first safe ask path.",
            "does_not": "Does not enable unsupported production features.",
        },
    ]


def _current_capabilities() -> list[str]:
    return [
        "Credential-free demo and doctor commands.",
        "Mock provider ask with a public-safe run_id.",
        "Workspace File Access Guard for explicitly selected files inside an allowlisted workspace.",
        "Loopback-only Local LLM provider execution when explicitly enabled with --live.",
        "OpenAI-compatible provider path behind explicit --live and environment opt-in.",
        "Optional redacted local run ledger via --ledger.",
    ]


def _limitations() -> list[str]:
    return [
        "Not production-ready.",
        "No Official Managed Cloud runtime in this public repo.",
        "No production Oracle control plane.",
        "No live Discord restoration.",
        "No arbitrary shell execution.",
        "No arbitrary local file access, folder crawling, PDF/image parsing, or automatic file summarization.",
        "No production installer, npm, or winget channel.",
        "Persistent memory is not complete; local memory remains explicit opt-in only.",
    ]


def _actions_not_performed() -> list[str]:
    return [
        "no external provider call",
        "no local LLM text generation",
        "no non-loopback network call",
        "no file read",
        "no shell execution",
        "no install",
        "no PATH mutation",
        "no deploy",
    ]


def _local_llm_message(status: str) -> str:
    if status == "detected":
        return "A loopback local LLM endpoint responded to a metadata probe."
    if status == "blocked":
        return "Configured Local LLM endpoint was rejected by the loopback-only policy."
    return "No loopback local LLM endpoint responded. You can still use the mock provider."


def _first_run_sections_en(report: Mapping[str, object]) -> tuple[CliSection, ...]:
    local_llm = report["local_llm"] if isinstance(report.get("local_llm"), Mapping) else {}
    provider_setup = report["provider_setup"] if isinstance(report.get("provider_setup"), Mapping) else {}
    first_ask = report["recommended_first_ask"] if isinstance(report.get("recommended_first_ask"), Mapping) else {}
    return (
        CliSection(
            "First 5 minutes",
            tuple(
                CliRow(f"step_{step['step']}", step["command"], "ok", note=str(step["does"]))
                for step in report.get("steps", [])
                if isinstance(step, Mapping)
            ),
        ),
        CliSection(
            "Local LLM check",
            (
                CliRow("status", local_llm.get("status", "unknown"), _status_level(local_llm.get("status"))),
                CliRow("scope", "loopback only", "ok"),
                CliRow("detected", local_llm.get("detected_label") or "none", "ok" if local_llm.get("status") == "detected" else "warn"),
                CliRow("message", local_llm.get("message", "unknown"), _status_level(local_llm.get("status"))),
            ),
        ),
        CliSection(
            "Provider setup",
            _provider_rows_en(provider_setup),
        ),
        CliSection(
            "First ask",
            (
                CliRow("provider", first_ask.get("provider", "mock"), "ok"),
                CliRow("command", first_ask.get("command", 'yonerai ask "hello" --provider mock --json'), "ok"),
                CliRow("why", first_ask.get("why", "Works without provider keys."), "ok"),
            ),
        ),
        CliSection("Still unavailable", _list_rows(report.get("limitations", []), prefix="limit")),
    )


def _first_run_sections_ja(report: Mapping[str, object]) -> tuple[CliSection, ...]:
    local_llm = report["local_llm"] if isinstance(report.get("local_llm"), Mapping) else {}
    provider_setup = report["provider_setup"] if isinstance(report.get("provider_setup"), Mapping) else {}
    first_ask = report["recommended_first_ask"] if isinstance(report.get("recommended_first_ask"), Mapping) else {}
    return (
        CliSection(
            "最初の5分",
            tuple(
                CliRow(f"{step['step']}. コマンド", step["command"], "ok", note=_step_note_ja(int(step["step"])))
                for step in report.get("steps", [])
                if isinstance(step, Mapping)
            ),
        ),
        CliSection(
            "ローカルLLM確認",
            (
                CliRow("状態", _local_status_ja(local_llm.get("status")), _status_level(local_llm.get("status"))),
                CliRow("範囲", "loopback のみ", "ok"),
                CliRow("検出", local_llm.get("detected_label") or "なし", "ok" if local_llm.get("status") == "detected" else "warn"),
                CliRow("説明", _local_message_ja(local_llm.get("status")), _status_level(local_llm.get("status"))),
            ),
        ),
        CliSection(
            "プロバイダー設定",
            _provider_rows_ja(provider_setup),
        ),
        CliSection(
            "最初の ask",
            (
                CliRow("provider", first_ask.get("provider", "mock"), "ok"),
                CliRow("command", first_ask.get("command", 'yonerai ask "hello" --provider mock --json'), "ok"),
                CliRow("理由", _first_ask_why_ja(first_ask.get("provider")), "ok"),
            ),
        ),
        CliSection(
            "いまできること",
            (
                CliRow("demo / doctor", "認証情報なしで実行できます", "ok"),
                CliRow("run_id", "mock ask は公開してよい run_id を返します", "ok"),
                CliRow("ファイル", "ワークスペース内ファイルアクセス制御のみです", "ok"),
                CliRow("ledger", "--ledger 指定時だけローカルに redacted 履歴を書きます", "ok"),
            ),
        ),
        CliSection("まだ使えないもの", _list_rows_ja(report.get("limitations", []))),
    )


def _provider_rows_en(provider_setup: Mapping[str, object]) -> tuple[CliRow, ...]:
    rows = []
    for provider_id in ("mock", "local", "openai_compatible"):
        provider = provider_setup.get(provider_id)
        if isinstance(provider, Mapping):
            rows.append(CliRow(provider_id, provider.get("plain_state", "unknown"), _plain_state_level(provider.get("plain_state")), note=str(provider.get("explanation", ""))))
    return tuple(rows)


def _provider_rows_ja(provider_setup: Mapping[str, object]) -> tuple[CliRow, ...]:
    labels = {"mock": "mock", "local": "local LLM", "openai_compatible": "OpenAI-compatible"}
    rows = []
    for provider_id in ("mock", "local", "openai_compatible"):
        provider = provider_setup.get(provider_id)
        if isinstance(provider, Mapping):
            rows.append(
                CliRow(
                    labels[provider_id],
                    _plain_state_ja(provider.get("plain_state")),
                    _plain_state_level(provider.get("plain_state")),
                    note=_provider_explanation_ja(provider_id, provider.get("plain_state")),
                )
            )
    return tuple(rows)


def _list_rows(values: object, *, prefix: str) -> tuple[CliRow, ...]:
    if not isinstance(values, list):
        return ()
    return tuple(CliRow(f"{prefix}_{index}", value, "warn") for index, value in enumerate(values, start=1))


def _list_rows_ja(values: object) -> tuple[CliRow, ...]:
    if not isinstance(values, list):
        return ()
    translated = [_limitation_ja(str(value)) for value in values]
    return tuple(CliRow(f"制限_{index}", value, "warn") for index, value in enumerate(translated, start=1))


def _status_level(status: object) -> str:
    if status == "detected":
        return "ok"
    if status == "blocked":
        return "fail"
    return "warn"


def _plain_state_level(state: object) -> str:
    if state in {"ready_now", "ready_for_explicit_live", "configured_for_explicit_live"}:
        return "ok"
    if state in {"blocked_by_loopback_policy", "needs_attention"}:
        return "fail"
    return "warn"


def _step_note_ja(step: int) -> str:
    notes = {
        1: "現在の capability slice を見るだけです",
        2: "インストールや PATH 変更はしません",
        3: "loopback のメタデータ確認だけで、prompt は送りません",
        4: "最初に安全な ask path を試します",
    }
    return notes.get(step, "")


def _local_status_ja(status: object) -> str:
    if status == "detected":
        return "検出済み"
    if status == "blocked":
        return "安全ポリシーで拒否"
    return "未検出"


def _local_message_ja(status: object) -> str:
    if status == "detected":
        return "loopback のローカルLLMがメタデータ確認に応答しました。"
    if status == "blocked":
        return "設定されたURLは loopback-only ポリシーに合わないため呼びません。"
    return "ローカルLLMは見つかりません。mock provider はそのまま使えます。"


def _plain_state_ja(state: object) -> str:
    mapping = {
        "ready_now": "今すぐ利用できます",
        "ready_for_explicit_live": "--live 指定で利用できます",
        "configured_for_explicit_live": "--live 指定で利用できます",
        "local_server_detected_enable_env": "ローカルサーバー検出、env 有効化が必要です",
        "not_found": "未検出",
        "not_configured": "未設定",
        "needs_live_opt_in": "live opt-in が必要です",
        "blocked_by_loopback_policy": "loopback ポリシーで拒否",
        "needs_attention": "確認が必要です",
    }
    return mapping.get(str(state), "不明")


def _provider_explanation_ja(provider_id: str, state: object) -> str:
    if provider_id == "mock":
        return "API key なしで最初に試す経路です"
    if provider_id == "local":
        if state == "ready_for_explicit_live":
            return "ローカルLLMは loopback のみ許可されます"
        if state == "local_server_detected_enable_env":
            return "ORA_LOCAL_LLM_ENABLED=1 を設定してから使います"
        if state == "blocked_by_loopback_policy":
            return "localhost / 127.0.0.1 / ::1 だけ許可します"
        return "Ollama / LM Studio 風の loopback endpoint を確認します"
    if state == "configured_for_explicit_live":
        return "外部 provider は常に --live が必要です"
    return "未設定でも demo と mock ask は使えます"


def _first_ask_why_ja(provider: object) -> str:
    if provider == "local":
        return "ローカルLLMが loopback で動いている場合の最初の実行です"
    return "API key やローカルモデルなしで動く最初の実行です"


def _limitation_ja(value: str) -> str:
    mapping = {
        "Not production-ready.": "本番 ready ではありません。",
        "No Official Managed Cloud runtime in this public repo.": "この public repo には Official Managed Cloud runtime はありません。",
        "No production Oracle control plane.": "production Oracle control plane はありません。",
        "No live Discord restoration.": "live Discord は復旧済みではありません。",
        "No arbitrary shell execution.": "任意 shell 実行はできません。",
        "No arbitrary local file access, folder crawling, PDF/image parsing, or automatic file summarization.": "任意ファイルアクセス、フォルダ巡回、PDF/画像解析、自動ファイル要約はまだありません。",
        "No production installer, npm, or winget channel.": "production installer、npm、winget はまだありません。",
        "Persistent memory is not complete; local memory remains explicit opt-in only.": "persistent memory は完成ではなく、local memory は明示 opt-in のみです。",
    }
    return mapping.get(value, value)
