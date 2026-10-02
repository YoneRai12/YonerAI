from __future__ import annotations

from yonerai_cli.config import ConfigError
from yonerai_cli.screens.labels import _safe


def _help(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "ヘルプ",
                "  会話: そのまま入力で話せます。",
                "  コマンド: / で候補を開き、/l や /u のように続けて絞り込みます。",
                "  アプリ内では `yonerai` を打ち直しません。",
                "  よく使う: `/ログイン` `/アカウント` `/セッション` `/プロジェクト` `/疎通` `/レート` `/更新`",
                "  英語alias: `/login` `/whoami` `/sessions` `/projects` `/ping` `/rate-limit` `/update` `/settings`",
                "  画面: `/設定` `/ローカルLLM` `/認証` `/更新` `/コマンド`",
                "  日本語表示でも英語コマンドをそのまま使えます。",
                "",
            )
        )
    return "\n".join(
        (
            "Help",
            "  chat: type normally",
            "  commands: use / to open suggestions, then keep typing fragments like /l or /u.",
            "  Inside the app, you do not type `yonerai` again.",
            "  Common: `/login` `/whoami` `/sessions` `/projects` `/ping` `/rate-limit` `/update`",
            "  Japanese aliases: `/ログイン` `/アカウント` `/セッション` `/プロジェクト` `/疎通` `/レート` `/更新`",
            "  Screens: `/settings` `/local-llm` `/auth` `/update` `/commands`",
            "  Japanese aliases stay available in English mode.",
            "",
        )
    )


def _non_tty_fallback(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "YonerAI Interactive CLI",
                "標準入力が TTY ではないため、対話画面は起動しませんでした。",
                "対話で使う: yonerai",
                "別名: yonerai chat",
                "スクリプトで使う: yonerai chat --script",
                "設定確認: yonerai providers --pretty --lang ja",
                "",
            )
        )
    return "\n".join(
        (
            "YonerAI Interactive CLI",
            "stdin is not a TTY, so the interactive screen did not start.",
            "Interactive: yonerai",
            "Alias: yonerai chat",
            "Scripted: yonerai chat --script",
            "Check setup: yonerai providers --pretty --lang en",
            "",
        )
    )


def _unknown(lang: str) -> str:
    return "不明なコマンドです。/ヘルプ を見てください。\n" if lang == "ja" else "Unknown command. Type /help\n"


def _bye(lang: str) -> str:
    return "終了しました\n" if lang == "ja" else "Goodbye\n"


def _config_error(lang: str, exc: ConfigError) -> str:
    message = _safe(str(exc) or "config error")
    if lang == "ja":
        return f"設定を保存できませんでした: {message}\n"
    return f"Could not save config: {message}\n"
