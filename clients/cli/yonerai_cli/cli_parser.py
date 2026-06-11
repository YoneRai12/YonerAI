from __future__ import annotations

import argparse

from yonerai_cli.commands.api import STATUS_PROFILE_CHOICES, add_api_parser
from yonerai_cli.commands.audit import add_audit_parser
from yonerai_cli.commands.ask import add_ask_parser, add_plan_parser
from yonerai_cli.commands.auth import add_auth_parser, add_privacy_parser
from yonerai_cli.commands.config import add_config_parser
from yonerai_cli.commands.discord import add_discord_parser
from yonerai_cli.commands.evolve import add_evolve_parser
from yonerai_cli.commands.hybrid import add_hybrid_parser
from yonerai_cli.commands.manifest import add_manifest_parser
from yonerai_cli.commands.memory import add_memory_parser
from yonerai_cli.commands.node import add_node_parser, add_relay_parser
from yonerai_cli.commands.ops import add_ops_parser
from yonerai_cli.commands.oracle import add_oracle_parser
from yonerai_cli.commands.policy import add_policy_parser
from yonerai_cli.commands.project import add_project_parser
from yonerai_cli.commands.providers import add_providers_parser
from yonerai_cli.commands.route import add_route_parser
from yonerai_cli.commands.runs import add_runs_parser
from yonerai_cli.commands.search import add_search_parser
from yonerai_cli.commands.sync import add_sync_parser
from yonerai_cli.commands.update import add_install_parser, add_update_parser
from yonerai_cli.services.core_api_service import DEFAULT_API_ORIGIN


LANG_CHOICES = ("en", "ja")
COLOR_CHOICES = ("auto", "never", "always")
PLAN_PROVIDER_CHOICES = ("auto", "mock", "openai-compatible", "local", "anthropic", "gemini")
PLAN_MODE_CHOICES = (
    "managed-contract",
    "hybrid",
    "self-host",
    "official_managed_cloud",
    "official_hybrid_private",
    "full_private_self_host",
)


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--api-origin",
        default=DEFAULT_API_ORIGIN,
        help=f"Loopback Core API origin. Default: {DEFAULT_API_ORIGIN}",
    )

    parser = argparse.ArgumentParser(
        prog="yonerai",
        description=(
            "YonerAI CLI Local Runtime. "
            "Includes an interactive terminal shell, safe provider readiness, auto routing, and diagnostics. "
            "It is not a deploy tool or Official Managed Cloud runtime."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=False)

    login = subcommands.add_parser("login", help="Start staging Google login for the public CLI. Production login is disabled.")
    login.add_argument("--staging", action="store_true", default=True, help="Use staging login. This is the only supported mode.")
    login.add_argument("--bridge", action="store_true", help="Call the staging CLI auth bridge start endpoint.")
    login.add_argument("--open-browser", action="store_true", help="Open the staging Google auth URL after bridge start.")
    login.add_argument("--wait-linked", action="store_true", help="Poll until the staging CLI bridge links or times out.")
    login.add_argument("--timeout-seconds", type=float, default=10.0, help="Network timeout. Default: 10.")
    login.add_argument("--max-wait-seconds", type=float, default=120.0, help="Maximum wait for --wait-linked. Default: 120.")
    login.add_argument("--poll-interval-seconds", type=float, default=2.0, help="Polling interval. Default: 2.")
    login.add_argument("--config-path", help="Optional local CLI config path.")
    login_output = login.add_mutually_exclusive_group()
    login_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    login_output.add_argument("--pretty", action="store_true", help="Print a readable staging login report.")
    login.add_argument("--lang", choices=LANG_CHOICES, default="ja", help="Pretty output language. Default: ja.")
    login.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    whoami = subcommands.add_parser("whoami", help="Show the linked staging account without exposing tokens.")
    whoami.add_argument("--config-path", help="Optional local CLI config path.")
    whoami.add_argument("--timeout-seconds", type=float, default=10.0, help="Network timeout. Default: 10.")
    whoami_output = whoami.add_mutually_exclusive_group()
    whoami_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    whoami_output.add_argument("--pretty", action="store_true", help="Print a readable account report.")
    whoami.add_argument("--lang", choices=LANG_CHOICES, default="ja", help="Pretty output language. Default: ja.")
    whoami.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto.")

    chat = subcommands.add_parser(
        "chat", aliases=["interactive"], help="Start the Japanese-first interactive YonerAI terminal."
    )
    chat.add_argument("--config-path", help="Optional local CLI config path. Defaults to the user config directory.")
    chat.add_argument(
        "--lang", choices=LANG_CHOICES, help="Interactive language. Defaults to saved config or first-launch selection."
    )
    chat.add_argument(
        "--provider",
        choices=PLAN_PROVIDER_CHOICES,
        help="Provider preference for chat messages. Defaults to saved config.",
    )
    chat.add_argument(
        "--live", action="store_true", help="Explicitly allow configured live provider/local LLM execution."
    )
    chat.add_argument("--ledger-path", "--ledger", dest="ledger_path", help="Optional redacted JSONL run ledger path.")
    chat.add_argument("--script", action="store_true", help="Read chat lines from stdin even when stdin is not a TTY.")
    chat.add_argument("--color", choices=COLOR_CHOICES, default="auto", help="Output color mode. Default: auto.")

    add_config_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)

    add_auth_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)
    add_privacy_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)
    add_api_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)
    add_project_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)
    add_audit_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)
    add_sync_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)
    add_evolve_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)

    subcommands.add_parser("health", parents=[shared], help="Check the local Core API health endpoint.")

    smoke = subcommands.add_parser("smoke", help="Run the credential-free in-process public MVP smoke.")
    smoke_output = smoke.add_mutually_exclusive_group()
    smoke_output.add_argument("--json", action="store_true", help="Print compact machine-readable JSON.")
    smoke_output.add_argument("--pretty", action="store_true", help="Print a detailed human-readable summary.")

    demo = subcommands.add_parser(
        "demo",
        aliases=["quickstart"],
        help="Run a credential-free public YonerAI demo after clone.",
    )
    demo_output = demo.add_mutually_exclusive_group()
    demo_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    demo_output.add_argument("--pretty", action="store_true", help="Print a readable sectioned demo summary.")

    start = subcommands.add_parser("start", help="Guide the first local YonerAI run for non-engineers.")
    start.add_argument("--guided", action="store_true", help="Show copyable next actions for the first five minutes.")
    start_output = start.add_mutually_exclusive_group()
    start_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    start_output.add_argument("--pretty", action="store_true", help="Print a readable first-run guide.")
    start.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    start.add_argument(
        "--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto."
    )

    doctor = subcommands.add_parser("doctor", help="Run offline, non-mutating setup diagnostics.")
    doctor_output = doctor.add_mutually_exclusive_group()
    doctor_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    doctor_output.add_argument("--pretty", action="store_true", help="Print a readable diagnostic summary.")
    doctor.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    doctor.add_argument(
        "--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto."
    )

    add_providers_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)

    add_policy_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)

    status = subcommands.add_parser("status", help="Print offline public demo and installer readiness status.")
    status.add_argument("status_command", nargs="?", choices=("check",), default="check")
    status_output = status.add_mutually_exclusive_group()
    status_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    status_output.add_argument("--pretty", action="store_true", help="Print a readable status summary.")
    status.add_argument(
        "--source", choices=("local", "fixture"), default="local", help="Status source. Default: local."
    )
    status.add_argument(
        "--status-source",
        help="Optional local status-feed JSON path or allowlisted HTTPS status URL. URL fetch also requires --allow-network-status-fetch.",
    )
    status.add_argument(
        "--allow-network-status-fetch",
        action="store_true",
        help="Explicitly allow fetching an allowlisted HTTPS status URL. Disabled by default.",
    )
    status.add_argument("--profile", choices=STATUS_PROFILE_CHOICES, default="operational")
    status.add_argument("--lang", choices=LANG_CHOICES, default="en", help="Pretty output language. Default: en.")
    status.add_argument(
        "--color", choices=COLOR_CHOICES, default="auto", help="Pretty output color mode. Default: auto."
    )

    add_manifest_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)

    add_route_parser(
        subcommands,
        mode_choices=("official_managed_cloud", "official_hybrid_private", "full_private_self_host"),
        color_choices=COLOR_CHOICES,
    )

    add_node_parser(subcommands, color_choices=COLOR_CHOICES)
    add_relay_parser(subcommands, color_choices=COLOR_CHOICES)

    add_oracle_parser(subcommands, color_choices=COLOR_CHOICES)

    add_hybrid_parser(subcommands, provider_choices=("mock", "local"), color_choices=COLOR_CHOICES)

    add_plan_parser(
        subcommands,
        provider_choices=PLAN_PROVIDER_CHOICES,
        mode_choices=PLAN_MODE_CHOICES,
        color_choices=COLOR_CHOICES,
    )
    add_ask_parser(
        subcommands,
        provider_choices=PLAN_PROVIDER_CHOICES,
        mode_choices=PLAN_MODE_CHOICES,
        lang_choices=LANG_CHOICES,
        color_choices=COLOR_CHOICES,
    )

    add_search_parser(subcommands, color_choices=COLOR_CHOICES)

    add_discord_parser(subcommands, color_choices=COLOR_CHOICES)

    add_install_parser(subcommands, color_choices=COLOR_CHOICES)
    add_update_parser(subcommands, color_choices=COLOR_CHOICES)

    add_ops_parser(subcommands, color_choices=COLOR_CHOICES)

    add_memory_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)

    add_runs_parser(subcommands, lang_choices=LANG_CHOICES, color_choices=COLOR_CHOICES)

    message = subcommands.add_parser("message", parents=[shared], help="Send a local public message smoke request.")
    message.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    message.add_argument("prompt", nargs="+")

    run = subcommands.add_parser("run", parents=[shared], help="Create a local Surface API run smoke request.")
    run.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    run.add_argument("prompt", nargs="+")

    return parser
