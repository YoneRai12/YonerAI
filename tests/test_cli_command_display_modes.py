from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def _slash_command(canonical: str) -> str:
    from yonerai_cli.tui.keymap import SLASH_COMMANDS

    return next(spec.command for spec in SLASH_COMMANDS if spec.canonical == canonical)


def test_command_palette_display_modes_and_dim_aliases() -> None:
    from yonerai_cli.tui.palette import slash_command_summary

    settings_ja = _slash_command("/settings")

    ja_only = slash_command_summary("ja", display_mode="ja_only", color="never")
    ja_with_en = slash_command_summary("ja", display_mode="ja_with_en", color="always")
    en_with_ja = slash_command_summary("en", display_mode="en_with_ja", color="always")
    en_only = slash_command_summary("en", display_mode="en_only", color="never")

    assert settings_ja in ja_only
    assert "/settings" not in ja_only
    assert settings_ja in ja_with_en
    assert "/settings" in ja_with_en
    assert "\x1b[2m" in ja_with_en
    assert "/settings" in en_with_ja
    assert settings_ja in en_with_ja
    assert "\x1b[2m" in en_with_ja
    assert "/settings" in en_only
    assert settings_ja not in en_only


def test_command_display_config_aliases_are_persisted(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))

    assert cli.main(["config", "set", "コマンド表示", "日本語+英語", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["config"]["command_display_mode"] == "ja_with_en"
    assert str(tmp_path) not in json.dumps(output, ensure_ascii=False)


def test_display_mode_value_aliases_support_japanese_labels() -> None:
    from yonerai_cli.tui.aliases import canonical_value

    assert canonical_value("日本語だけ") == "ja_only"
    assert canonical_value("日本語+英語") == "ja_with_en"
    assert canonical_value("英語+日本語") == "en_with_ja"
    assert canonical_value("英語だけ") == "en_only"


def test_prompt_completer_respects_display_mode_and_keeps_english_input_usable() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from yonerai_cli.tui.keymap import MAX_TOP_LEVEL_COMPLETIONS, build_prompt_completer

    login_ja = _slash_command("/login")
    completer = build_prompt_completer("ja", display_mode="ja_with_en")
    top = list(completer.get_completions(Document("/"), CompleteEvent()))
    english_fragment = list(completer.get_completions(Document("/lo"), CompleteEvent()))
    short_l_fragment = list(completer.get_completions(Document("/l"), CompleteEvent()))

    assert top
    assert len(top) <= MAX_TOP_LEVEL_COMPLETIONS
    assert top[0].text == login_ja
    assert "/login" in top[0].display_text
    assert english_fragment
    assert english_fragment[0].text == "/login"
    assert login_ja in english_fragment[0].display_text
    assert short_l_fragment
    assert {completion.text for completion in short_l_fragment} >= {"/login", "/logout", "/local-llm"}


def test_prompt_completer_shows_english_aliases_even_in_japanese_only_mode() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from yonerai_cli.tui.keymap import build_prompt_completer

    login_ja = _slash_command("/login")
    completer = build_prompt_completer("ja", display_mode="ja_only")
    english_fragment = list(completer.get_completions(Document("/lo"), CompleteEvent()))

    assert english_fragment
    assert english_fragment[0].text == "/login"
    assert login_ja in english_fragment[0].display_text


def test_prompt_completer_keeps_english_alias_visible_in_japanese_top_suggestions() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from yonerai_cli.tui.keymap import build_prompt_completer

    completer = build_prompt_completer("ja", display_mode="ja_only")
    top = list(completer.get_completions(Document("/"), CompleteEvent()))

    assert top
    assert top[0].text == _slash_command("/login")
    assert "/login" in top[0].display_text


def test_prompt_completer_tolerates_close_english_typo_in_japanese_mode() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from yonerai_cli.tui.keymap import build_prompt_completer

    login_ja = _slash_command("/login")
    completer = build_prompt_completer("ja", display_mode="ja_with_en")
    typo_fragment = list(completer.get_completions(Document("/loguin"), CompleteEvent()))

    assert typo_fragment
    assert typo_fragment[0].text == "/login"
    assert login_ja in typo_fragment[0].display_text


def test_prompt_completer_shows_japanese_aliases_for_japanese_query_in_english_mode() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from yonerai_cli.tui.keymap import build_prompt_completer

    login_ja = _slash_command("/login")
    completer = build_prompt_completer("en", display_mode="en_only")
    japanese_fragment = list(completer.get_completions(Document("/ロ"), CompleteEvent()))

    assert japanese_fragment
    assert japanese_fragment[0].text == login_ja
    assert "/login" in japanese_fragment[0].display_text


def test_prompt_completer_keeps_japanese_alias_visible_in_english_top_suggestions() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit.completion import CompleteEvent
    from prompt_toolkit.document import Document
    from yonerai_cli.tui.keymap import build_prompt_completer

    login_ja = _slash_command("/login")
    completer = build_prompt_completer("en", display_mode="en_only")
    top = list(completer.get_completions(Document("/"), CompleteEvent()))

    assert top
    assert top[0].text == "/login"
    assert login_ja in top[0].display_text


def test_command_palette_dialog_items_stay_short_and_user_facing() -> None:
    from yonerai_cli.tui.palette import command_palette_dialog_items

    items = command_palette_dialog_items("ja", display_mode="ja_with_en")

    assert [value for value, _label in items] == [
        "/login",
        "/local-llm",
        "/update",
        "/settings",
        "/whoami",
        "/projects",
        "/sessions",
    ]
    assert any("/login" in label for _value, label in items)
    assert any("/local-llm" in label for _value, label in items)


def test_command_palette_dialog_items_support_query_filter() -> None:
    from yonerai_cli.tui.palette import command_palette_dialog_items

    items = command_palette_dialog_items("ja", display_mode="ja_with_en", query="/lo")

    assert [value for value, _label in items] == ["/login", "/local-llm"]


def test_command_palette_dialog_items_show_english_primary_for_english_query_in_japanese_mode() -> None:
    from yonerai_cli.tui.palette import command_palette_dialog_items

    login_ja = _slash_command("/login")
    items = command_palette_dialog_items("ja", display_mode="ja_only", query="/lo")

    assert [value for value, _label in items] == ["/login", "/local-llm"]
    assert items[0][1].startswith("/login")
    assert login_ja in items[0][1]


def test_command_palette_dialog_items_keep_english_alias_visible_in_japanese_mode() -> None:
    from yonerai_cli.tui.palette import command_palette_dialog_items

    items = command_palette_dialog_items("ja", display_mode="ja_only")

    assert items
    assert items[0][0] == "/login"
    assert "/login" in items[0][1]


def test_command_palette_dialog_items_support_close_english_typo_in_japanese_mode() -> None:
    from yonerai_cli.tui.palette import command_palette_dialog_items

    login_ja = _slash_command("/login")
    items = command_palette_dialog_items("ja", display_mode="ja_only", query="/loguin")

    assert items
    assert items[0][0] == "/login"
    assert items[0][1].startswith("/login")
    assert login_ja in items[0][1]


def test_command_palette_dialog_items_support_short_english_fragment_in_japanese_mode() -> None:
    from yonerai_cli.tui.palette import command_palette_dialog_items

    items = command_palette_dialog_items("ja", display_mode="ja_with_en", query="/l")

    assert [value for value, _label in items] == ["/login", "/local-llm"]
    assert items[0][1].startswith("/login")
    assert items[0][1].count("/") >= 2


def test_command_palette_dialog_items_show_japanese_primary_for_japanese_query_in_english_mode() -> None:
    from yonerai_cli.tui.palette import command_palette_dialog_items

    login_ja = _slash_command("/login")
    items = command_palette_dialog_items("en", display_mode="en_only", query="/ロ")

    assert [value for value, _label in items] == ["/login", "/local-llm"]
    assert items[0][1].startswith(login_ja)
    assert "/login" in items[0][1]


def test_slash_key_keeps_empty_buffer_inline_and_does_not_force_modal_palette() -> None:
    from yonerai_cli.tui.renderer import _should_open_palette_on_slash, _slash_palette_result, _top_level_palette_result

    assert _should_open_palette_on_slash("")
    assert _should_open_palette_on_slash("   ")
    assert not _should_open_palette_on_slash("hello")
    assert not _should_open_palette_on_slash("/lo")
    assert _slash_palette_result("") is None
    assert _slash_palette_result("   ") is None
    assert _top_level_palette_result("/lo") is None
    assert _top_level_palette_result(f"   {_slash_command('/login')[:2]}") is None
    assert _top_level_palette_result("/update stable") is None
    assert _top_level_palette_result("hello") is None


def test_slash_palette_selection_returns_selected_command(monkeypatch) -> None:
    from yonerai_cli.tui import renderer

    monkeypatch.setattr(renderer, "open_command_palette", lambda **_kwargs: (True, "/login"))
    assert renderer._resolve_slash_palette_selection(lang="ja", display_mode="ja_only") == "/login"

    monkeypatch.setattr(renderer, "open_command_palette", lambda **_kwargs: (True, None))
    assert renderer._resolve_slash_palette_selection(lang="ja", display_mode="ja_only") == ""

    monkeypatch.setattr(renderer, "open_command_palette", lambda **_kwargs: (False, None))
    assert renderer._resolve_slash_palette_selection(lang="ja", display_mode="ja_only") is None


def test_display_command_value_completion_in_japanese() -> None:
    from yonerai_cli.tui.keymap import slash_value_words

    assert slash_value_words("/display", "ja") == [
        "日本語だけ",
        "日本語+英語",
        "英語+日本語",
        "英語だけ",
    ]


def test_prompt_line_keeps_live_slash_popup_enabled(monkeypatch) -> None:
    pytest.importorskip("prompt_toolkit")
    import prompt_toolkit
    from yonerai_cli.tui import renderer

    captured: dict[str, object] = {}

    class DummySession:
        def __init__(self, *args, **kwargs) -> None:
            captured.update(kwargs)

        def prompt(self, *_args, **_kwargs) -> str:
            return "/quit"

    monkeypatch.setattr(prompt_toolkit, "PromptSession", DummySession)

    value = renderer.prompt_line(lang="ja", display_mode="ja_with_en")

    assert value == "/quit"
    assert captured["complete_while_typing"] is True
    assert captured["show_frame"] is True
    assert captured["reserve_space_for_menu"] == 1


def test_install_slash_completion_menu_keeps_popup_above_composer() -> None:
    pytest.importorskip("prompt_toolkit")
    from prompt_toolkit import PromptSession
    from prompt_toolkit.input.defaults import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from yonerai_cli.tui import renderer

    with create_pipe_input() as pipe_input:
        session = PromptSession(input=pipe_input, output=DummyOutput(), show_frame=True)
        renderer._install_slash_completion_menu(session)
        float_container = renderer._find_prompt_float_container(session.layout.container)

    assert float_container is not None
    slash_float = next(
        float_ for float_ in float_container.floats if getattr(float_, "_yonerai_slash_menu", False)
    )
    assert getattr(slash_float, "xcursor", False) is False
    assert getattr(slash_float, "ycursor", True) is False
    assert getattr(slash_float, "allow_cover_cursor", True) is False
    assert getattr(slash_float, "left", None) == 1
    assert getattr(slash_float, "right", None) is None
    assert getattr(slash_float, "bottom", None) == 1
    assert getattr(slash_float, "attach_to_window", None) is session.layout.current_window
    assert len(float_container.floats) >= 2


def test_sanitize_terminal_text_strips_orphaned_truecolor_fragments() -> None:
    from yonerai_cli.tui.renderer import _sanitize_terminal_text

    broken = "YonerAI\n8;2;127;123;255m\n[38;2;1;2;3mCLI"
    assert _sanitize_terminal_text(broken) == "YonerAI\n\nCLI"
