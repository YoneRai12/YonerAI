from __future__ import annotations

from typing import TextIO

from yonerai_cli.auth_policy import build_google_auth_status, build_google_login_dry_run, build_google_login_staging
from yonerai_cli.config import save_cli_config


DEFAULT_STAGING_ORIGIN = "https://api-staging.yonerai.com"


def run_auth_onboarding(
    config: dict[str, object],
    *,
    config_path: str | None,
    config_exists: bool,
    script: bool,
    lang: str,
    input_stream: TextIO,
    output_stream: TextIO,
    color: str,
) -> None:
    del color
    if config_exists or script or not input_stream.isatty():
        return
    if config.get("auth_onboarding_seen") is True:
        return

    if lang == "ja":
        output_stream.write("YonerAI account / 認証\n")
        output_stream.write("1) ローカルだけで使う（推奨）\n")
        output_stream.write("2) Googleログインを確認する（α / staging または dry-run）\n")
        output_stream.write("3) 後で設定する\n")
    else:
        output_stream.write("YonerAI account / auth\n")
        output_stream.write("1) Use local only. Continue without login.\n")
        output_stream.write("2) Check Google login. Uses staging if configured, otherwise dry-run.\n")
        output_stream.write("3) Set up later.\n")
    output_stream.write("> ")
    output_stream.flush()

    choice = input_stream.readline().strip().lower()
    config["auth_onboarding_seen"] = True
    save_cli_config(config, config_path)
    if choice not in {"2", "google", "login", "staging", "dry-run", "dryrun"}:
        if lang == "ja":
            output_stream.write(
                "認証は後で大丈夫です。ローカル CLI はそのまま使えます。\n"
                "cloud/local 同期は将来も明示承認が必要です。\n"
            )
        else:
            output_stream.write(
                "Auth can be configured later. Local CLI works without login. "
                "Cloud/local sync will require future explicit approval.\n"
            )
        return

    status = build_google_auth_status(config)
    report = build_google_login_staging(config) if status.get("staging_login_available") else build_google_login_dry_run(config)

    if lang == "ja":
        output_stream.write(
            "Googleログイン dry-run / staging の境界だけ確認します。正式ログイン、token 保存、"
            "自動の cloud 連携はここでは行いません。\n"
        )
    else:
        output_stream.write(
            "Checking Google login contract. No production Google login, token storage, "
            "or cloud account link is performed.\n"
        )
    output_stream.write(_format_onboarding_auth_preview(status, report, lang=lang))
    output_stream.write("\n")


def _format_onboarding_auth_preview(
    status: dict[str, object],
    report: dict[str, object],
    *,
    lang: str,
) -> str:
    del report
    staging = status.get("staging") if isinstance(status.get("staging"), dict) else {}
    origin = str(staging.get("origin") or "").strip()
    if not origin or origin in {"not_configured", "invalid_or_disallowed"}:
        origin = DEFAULT_STAGING_ORIGIN
    available = True

    if lang == "ja":
        return "\n".join(
            (
                "認証プレビュー",
                f"  Googleログイン: {'簡単ログイン可 (既定の staging 接続先)' if available else 'dry-run のみ'}",
                "  本番ログイン: 使えません",
                f"  接続先: {origin}",
                "  境界: Google token保存なし / refresh token保存なし / private自動アップロードなし",
                "  操作: `/ログイン` （英語: `/login`）",
                "",
            )
        )

    return "\n".join(
        (
            "Auth preview",
            f"  google_login: {'available (staging)' if available else 'dry-run only'}",
            f"  staging_origin: {origin}",
            "  boundaries: no Google token storage / no refresh token storage / no private auto-upload",
            "  next: /login",
            "",
        )
    )
