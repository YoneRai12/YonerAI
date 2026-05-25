from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path


def _load_output_module():
    cli_src = Path(__file__).resolve().parents[1] / "clients" / "cli"
    if str(cli_src) not in sys.path:
        sys.path.insert(0, str(cli_src))
    from yonerai_cli import output

    return output


def test_cli_output_plain_report_is_deterministic():
    output = _load_output_module()

    rendered = output.render_report(
        "YonerAI test",
        (
            output.CliSection(
                "Checks",
                (
                    output.CliRow("demo", "available", "ok"),
                    output.CliRow("installer", "not implemented", "warn"),
                ),
            ),
        ),
        color="never",
    )

    assert rendered == "\n".join(
        [
            "YonerAI test",
            "",
            "Checks",
            "[OK] demo     : available",
            "[WARN] installer: not implemented",
        ]
    )
    assert "\033[" not in rendered


def test_cli_output_auto_color_falls_back_when_rich_is_missing():
    output = _load_output_module()
    stream = StringIO()

    rendered = output.render_report(
        "YonerAI test",
        (output.CliSection("Checks", (output.CliRow("demo", "available", "ok"),)),),
        color="auto",
        stream=stream,
    )

    assert "[OK] demo: available" in rendered
    assert "\033[" not in rendered


def test_cli_output_auto_color_checks_optional_rich_before_ansi():
    output = _load_output_module()

    class TtyStream:
        def isatty(self):
            return True

    assert output._color_enabled("auto", stream=TtyStream(), rich_probe=lambda: False) is False
    assert output._color_enabled("auto", stream=TtyStream(), rich_probe=lambda: True) is True


def test_cli_output_color_always_is_opt_in():
    output = _load_output_module()

    rendered = output.render_report(
        "YonerAI test",
        (output.CliSection("Checks", (output.CliRow("demo", "available", "ok"),)),),
        color="always",
    )

    assert "\033[" in rendered


def test_cli_output_escapes_ascii_control_characters_in_values():
    output = _load_output_module()

    rendered = output.render_report(
        "YonerAI test",
        (
            output.CliSection(
                "Checks",
                (output.CliRow("requested_capability", "safe\x1b[31mred\x1b[0m", "ok"),),
            ),
        ),
        color="never",
    )

    assert "\\x1b[31m" in rendered
    assert "\\x1b[0m" in rendered
    assert "\x1b" not in rendered


def test_cli_output_escapes_control_characters_in_labels_notes_and_titles():
    output = _load_output_module()

    rendered = output.render_report(
        "YonerAI\x1b title",
        (
            output.CliSection(
                "Checks\x1b section",
                (output.CliRow("label\x1b", "value", "warn", "note\x1b"),),
            ),
        ),
        color="never",
    )

    assert "\\x1b title" in rendered
    assert "\\x1b section" in rendered
    assert "label\\x1b" in rendered
    assert "note\\x1b" in rendered
    assert "\x1b" not in rendered
