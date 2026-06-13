from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def test_home_primary_next_action_prefers_local_llm_when_app_is_installed() -> None:
    from yonerai_cli.screens.home import _home_primary_next_action

    provider_report = {
        "local_llm": {
            "status": "not_detected",
            "installed_apps": [
                {"label": "Ollama", "installed": True},
                {"label": "LM Studio", "installed": False},
            ],
        }
    }

    next_ja, next_en = _home_primary_next_action(
        provider_report,
        login_next_ja="/ログイン",
        login_next_en="/login",
        provider="mock",
        local_llm_enabled=False,
    )

    assert next_ja == "そのまま話す"
    assert next_en == "Type a normal message"


def test_home_short_actions_prefers_local_llm_when_app_is_installed() -> None:
    from yonerai_cli.screens.home import _home_short_actions

    provider_report = {
        "local_llm": {
            "status": "not_detected",
            "installed_apps": [
                {"label": "LM Studio", "installed": True},
            ],
        }
    }

    actions_ja, actions_en = _home_short_actions(
        provider_report,
        provider="mock",
        local_llm_enabled=False,
        login_next_ja="/ログイン",
        login_next_en="/login",
    )

    assert actions_ja == ("そのまま話す", "/ローカルLLM", "/ログイン")
    assert actions_en == ("Type a normal message", "/local-llm", "/login")


def test_provider_and_model_compact_summaries_stay_short_and_actionable() -> None:
    from yonerai_cli.screens.providers import format_models_compact, format_providers_compact

    report = {
        "providers": [
            {"provider_id": "mock", "plain_state": "ready_now"},
            {"provider_id": "local", "plain_state": "not_enabled_or_not_detected"},
        ],
        "local_llm": {
            "endpoint_label": "Ollama / 127.0.0.1:11434",
            "installed_apps": [{"label": "Ollama", "installed": True}],
        },
    }
    config = {
        "model_preference": "auto",
        "provider_preference": "mock",
        "local_llm_enabled": False,
    }

    providers_text = format_providers_compact(report, lang="ja")
    models_text = format_models_compact(config, report, lang="ja")

    assert "提供元" in providers_text
    assert "次: /ローカルLLM 使う" in providers_text
    assert "private自動送信なし" in providers_text
    assert "そのまま使えます" not in providers_text

    assert "モデル" in models_text
    assert "次: /ローカルLLM 使う" in models_text
    assert "候補: Ollama / LM Studio" in models_text
    assert "自動インストールなし" in models_text
    assert "既定endpoint" not in models_text


def test_startup_prelude_shows_short_login_hint_for_staging(monkeypatch, tmp_path: Path) -> None:
    from yonerai_cli.interactive import _startup_prelude

    monkeypatch.setenv("YONERAI_STAGING_AUTH_ORIGIN", "https://api-staging.yonerai.com")
    config = {"_runtime_config_path": str(tmp_path / "cli-config.json")}

    text = _startup_prelude(config=config, lang="ja", update_notice=None)

    assert "login" in text
    assert "/ログイン" in text
    assert "whoami" not in text
    assert "ローカルだけならそのまま話せます" in text


def test_home_welcome_stays_chat_first_and_shell_free() -> None:
    from yonerai_cli.screens.home import _welcome

    text = _welcome(
        "ja",
        provider="mock",
        live=False,
        config_exists=True,
        config={
            "model_preference": "auto",
            "memory_enabled": True,
            "update_notice_enabled": True,
            "_runtime_config_path": "",
        },
        ledger_path=None,
        provider_report={
            "local_llm": {
                "status": "detected",
                "detected_label": "Ollama",
            }
        },
    )

    assert "会話: そのまま入力" in text
    assert "コマンド: / で候補を開く" in text
    assert "yonerai login" not in text


def test_display_command_alias_prefers_in_app_bare_commands() -> None:
    from yonerai_cli.screens.home import _display_command_alias

    assert _display_command_alias("/ログイン", lang="ja", mode="ja_with_en") == "ログイン (/ログイン / login)"
    assert _display_command_alias("/更新", lang="ja", mode="ja_only") == "更新 (/更新)"
    assert _display_command_alias("/login", lang="en", mode="en_with_ja") == "login (/login / ログイン)"


def test_home_auth_summary_uses_conservative_session_wording_and_expiry_states() -> None:
    from yonerai_cli.screens.home import _home_auth_summary

    linked = _home_auth_summary({"staging_auth_state": "linked", "staging": {"configured": True}})
    expired = _home_auth_summary({"staging_auth_state": "expired", "staging": {"configured": True}})
    pending = _home_auth_summary({"staging_auth_state": "pending", "staging": {"configured": True}})

    assert linked == ("staging セッションあり", "staging session saved", "/認証", "/auth")
    assert expired == ("期限切れ (α/staging)", "expired (alpha/staging)", "/ログイン", "/login")
    assert pending == ("ログイン待ち (α/staging)", "login pending (alpha/staging)", "/ログイン", "/login")
