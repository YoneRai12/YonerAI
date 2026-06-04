from __future__ import annotations

from typing import TextIO

from yonerai_cli.auth_policy import build_google_login_dry_run
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
        output_stream.write("1) 後で設定する（ローカルCLIはそのまま使えます）\n")
        output_stream.write("2) Googleログインをdry-runで確認する（本番ログインはしません）\n")
    else:
        output_stream.write("YonerAI account / auth\n")
        output_stream.write("1) Set up later. Local CLI works without login.\n")
        output_stream.write("2) Preview Google login dry-run. No production login starts.\n")
    output_stream.write("> ")
    output_stream.flush()

    choice = input_stream.readline().strip().lower()
    config["auth_onboarding_seen"] = True
    save_cli_config(config, config_path)
    if choice not in {"2", "google", "login", "dry-run", "dryrun"}:
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

    report = build_google_login_dry_run(config)
    if lang == "ja":
        output_stream.write(
            "Googleログイン dry-run を確認します。本番Googleログイン、ブラウザ起動、token保存、"
            "cloud account link は行いません。\n"
        )
    else:
        output_stream.write(
            "Previewing Google login dry-run. No production Google login, browser launch, token storage, "
            "or cloud account link is performed.\n"
        )
    output_stream.write(format_auth_pretty(report, lang=lang, color=color))
    output_stream.write("\n")
