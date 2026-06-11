from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def test_command_palette_display_modes_and_dim_aliases() -> None:
    from yonerai_cli.tui.palette import slash_command_summary

    ja_only = slash_command_summary("ja", display_mode="ja_only", color="never")
    ja_with_en = slash_command_summary("ja", display_mode="ja_with_en", color="always")
    en_with_ja = slash_command_summary("en", display_mode="en_with_ja", color="always")
    en_only = slash_command_summary("en", display_mode="en_only", color="never")

    assert "/設定" in ja_only
    assert "/settings" not in ja_only
    assert "/設定" in ja_with_en
    assert "/settings" in ja_with_en
    assert "\x1b[2m" in ja_with_en
    assert "/settings" in en_with_ja
    assert "/設定" in en_with_ja
    assert "\x1b[2m" in en_with_ja
    assert "/settings" in en_only
    assert "/設定" not in en_only


def test_command_display_config_aliases_are_persisted(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["config", "set", "コマンド表示", "日本語+英語", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["config"]["command_display_mode"] == "ja_with_en"
    assert str(tmp_path) not in json.dumps(output, ensure_ascii=False)

