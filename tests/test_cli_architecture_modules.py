from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_SRC = ROOT / "clients" / "cli"
CORE_SRC = ROOT / "core" / "src"
for path in (CLI_SRC, CORE_SRC):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


EXPECTED_MODULES = (
    "yonerai_cli.cli_dispatch",
    "yonerai_cli.cli_parser",
    "yonerai_cli.commands.ask",
    "yonerai_cli.commands.auth",
    "yonerai_cli.commands.config",
    "yonerai_cli.commands.diagnostics",
    "yonerai_cli.commands.discord",
    "yonerai_cli.commands.hybrid",
    "yonerai_cli.commands.manifest",
    "yonerai_cli.commands.memory",
    "yonerai_cli.commands.node",
    "yonerai_cli.commands.ops",
    "yonerai_cli.commands.oracle",
    "yonerai_cli.commands.policy",
    "yonerai_cli.commands.providers",
    "yonerai_cli.commands.route",
    "yonerai_cli.commands.runs",
    "yonerai_cli.commands.search",
    "yonerai_cli.commands.update",
    "yonerai_cli.screens.agent_console",
    "yonerai_cli.screens.ask",
    "yonerai_cli.screens.auth_privacy",
    "yonerai_cli.screens.diagnostics",
    "yonerai_cli.screens.evolve",
    "yonerai_cli.screens.home",
    "yonerai_cli.screens.labels",
    "yonerai_cli.screens.policy",
    "yonerai_cli.screens.runs",
    "yonerai_cli.screens.settings",
    "yonerai_cli.screens.memory",
    "yonerai_cli.screens.node",
    "yonerai_cli.screens.oracle",
    "yonerai_cli.screens.safety",
    "yonerai_cli.screens.providers",
    "yonerai_cli.screens.update",
    "yonerai_cli.services.config_service",
    "yonerai_cli.services.core_api_service",
    "yonerai_cli.services.interactive_service",
    "yonerai_cli.services.ledger_service",
    "yonerai_cli.services.memory_service",
    "yonerai_cli.services.update_service",
    "yonerai_cli.tui.aliases",
    "yonerai_cli.tui.keymap",
    "yonerai_cli.tui.palette",
    "yonerai_cli.tui.renderer",
)


def test_cli_is_thin_entrypoint_after_modularization() -> None:
    import yonerai_cli.cli as cli

    cli_path = Path(cli.__file__)
    line_count = len(cli_path.read_text(encoding="utf-8").splitlines())

    assert line_count < 350


def test_interactive_shell_keeps_shared_labels_in_screen_modules() -> None:
    import yonerai_cli.interactive as interactive

    interactive_path = Path(interactive.__file__)
    line_count = len(interactive_path.read_text(encoding="utf-8").splitlines())

    assert line_count < 1250


def test_diagnostics_command_keeps_pretty_renderers_in_screen_module() -> None:
    import yonerai_cli.commands.diagnostics as diagnostics
    import yonerai_cli.screens.diagnostics as diagnostics_screen

    command_path = Path(diagnostics.__file__)
    screen_path = Path(diagnostics_screen.__file__)

    assert len(command_path.read_text(encoding="utf-8").splitlines()) < 500
    assert len(screen_path.read_text(encoding="utf-8").splitlines()) < 650
    assert diagnostics._build_doctor_report is not None
    assert diagnostics_screen._format_doctor_pretty is not None


def test_expected_cli_modules_are_importable() -> None:
    for module_name in EXPECTED_MODULES:
        module = importlib.import_module(module_name)
        assert module is not None


def test_parser_keeps_representative_commands_after_split() -> None:
    from yonerai_cli.cli import build_parser

    parser = build_parser()

    assert parser.parse_args(["policy", "status", "--json"]).command == "policy"
    assert parser.parse_args(["manifest", "verify", "releases/manifest.example.json", "--json"]).command == "manifest"
    assert parser.parse_args(["chat", "--script", "--lang", "ja"]).command == "chat"


def test_rust_boundary_proposal_limits_rust_to_future_native_edges() -> None:
    text = (ROOT / "docs" / "architecture" / "RUST_BOUNDARY_PROPOSAL.md").read_text(encoding="utf-8")

    assert "YonerAI CLI Local Runtime remains Python-first" in text
    assert "No Rust code is added in this lane" in text
    assert "Launcher" in text
    assert "Updater / install verifier" in text
    assert "Local Node daemon" in text
    assert "Relay client" in text
    assert "do not rewrite interactive UX in Rust" in text
    assert "no PATH/admin/service mutation by default" in text
