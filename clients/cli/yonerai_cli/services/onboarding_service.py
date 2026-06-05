from __future__ import annotations

from typing import TextIO

from yonerai_cli.auth_policy import build_google_auth_status, build_google_login_dry_run, build_google_login_staging
from yonerai_cli.commands.auth import format_auth_pretty
from yonerai_cli.config import save_cli_config


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
    if config_exists or script or not input_stream.isatty():
        return
    if config.get("auth_onboarding_seen") is True:
        return

    if lang == "ja":
        output_stream.write("YonerAI account / 認証\n")
        output_stream.write("1) ローカルだけで使う（ログインなしで続ける）\n")
        output_stream.write("2) Googleログインを確認する（staging設定があればstaging、なければdry-run）\n")
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
                "認証は後で設定できます。ローカルCLIはログインなしで使えます。"
                "cloud/local同期は将来の明示承認が必要です。\n"
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
            "Googleログイン dry-run/staging 契約を確認します。本番Googleログイン、token保存、"
            "cloud account link は行いません。\n"
        )
    else:
        output_stream.write(
            "Checking Google login contract. No production Google login, token storage, "
            "or cloud account link is performed.\n"
        )
    output_stream.write(format_auth_pretty(report, lang=lang, color=color))
    output_stream.write("\n")
