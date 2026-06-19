from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Callable, TextIO, TypeVar

from yonerai_cli.tui.keymap import build_prompt_completer
from yonerai_cli.tui.palette import command_palette_dialog_items


T = TypeVar("T")
ESC = chr(27)
ANSI_PREFIX = f"{ESC}["
COMMAND_PALETTE_TRIGGER = "__yonerai_command_palette__"
ORPHANED_ANSI_RE = re.compile(
    r"(?:\[(?:3|4)?8;2;(?:\d{1,3};){2}\d{1,3}m|\b(?:3|4)?8;2;(?:\d{1,3};){2}\d{1,3}m|\[\d+(?:;\d+){0,7}m)"
)

try:
    from prompt_toolkit.application.current import get_app_or_none
    from prompt_toolkit.data_structures import Point
    from prompt_toolkit.filters import Condition, has_completions, has_focus, is_done
    from prompt_toolkit.formatted_text import FormattedText
    from prompt_toolkit.layout.containers import ConditionalContainer, Float, FloatContainer, Window
    from prompt_toolkit.layout.controls import UIContent, UIControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.layout.menus import CompletionsMenu
    from prompt_toolkit.utils import get_cwidth

    PROMPT_TOOLKIT_MENU_READY = True
except Exception:  # pragma: no cover - optional dependency guard
    PROMPT_TOOLKIT_MENU_READY = False


def prompt_toolkit_console_ready(stdout: TextIO | None = None) -> bool:
    try:
        from prompt_toolkit.output.defaults import create_output
    except Exception:
        return False
    try:
        create_output(stdout=stdout)
    except Exception:
        return False
    return True


def prompt_toolkit_available(stdout: TextIO | None = None) -> bool:
    try:
        import prompt_toolkit  # noqa: F401
        from prompt_toolkit import PromptSession  # noqa: F401
        from prompt_toolkit.filters import has_completions  # noqa: F401
        from prompt_toolkit.formatted_text import HTML  # noqa: F401
        from prompt_toolkit.key_binding import KeyBindings  # noqa: F401
        from prompt_toolkit.styles import Style  # noqa: F401
        try:
            from prompt_toolkit.completion import CompleteStyle  # noqa: F401
        except Exception:
            from prompt_toolkit.shortcuts.prompt import CompleteStyle  # noqa: F401
    except Exception:
        return False
    return prompt_toolkit_console_ready(stdout)


def rich_available() -> bool:
    try:
        import rich  # noqa: F401
    except Exception:
        return False
    return True


if PROMPT_TOOLKIT_MENU_READY:

    def _truncate_to_width(text: str, width: int) -> str:
        clean = text.replace("\n", " ").strip()
        if width <= 0:
            return ""
        total = 0
        out: list[str] = []
        for ch in clean:
            ch_width = get_cwidth(ch)
            if total + ch_width > width:
                break
            out.append(ch)
            total += ch_width
        if total == get_cwidth(clean):
            return "".join(out)
        if width <= 3:
            return "." * width
        clipped_total = 0
        clipped: list[str] = []
        for ch in clean:
            ch_width = get_cwidth(ch)
            if clipped_total + ch_width > width - 3:
                break
            clipped.append(ch)
            clipped_total += ch_width
        return "".join(clipped) + "..."


    def _visible_window_bounds(
        *,
        completion_count: int,
        selected_index: int,
        available_rows: int,
    ) -> tuple[int, int]:
        if completion_count <= available_rows:
            return (0, completion_count - 1)
        half = max(0, available_rows // 2)
        start = max(0, min(selected_index - half, completion_count - available_rows))
        end = min(completion_count - 1, start + available_rows - 1)
        return (start, end)


    def _find_prompt_float_container(layout_container: object) -> FloatContainer | None:
        seen: set[int] = set()

        def _walk(node: object) -> FloatContainer | None:
            if id(node) in seen:
                return None
            seen.add(id(node))
            if isinstance(node, FloatContainer):
                return node
            if isinstance(node, ConditionalContainer):
                for child in (getattr(node, "content", None), getattr(node, "alternative_content", None)):
                    if child is None:
                        continue
                    found = _walk(child)
                    if found is not None:
                        return found
                return None
            for attr in ("children", "content", "container", "floats"):
                value = getattr(node, attr, None)
                if attr == "children" and isinstance(value, Sequence):
                    for child in value:
                        found = _walk(child)
                        if found is not None:
                            return found
                elif attr == "floats" and isinstance(value, Sequence):
                    for float_ in value:
                        content = getattr(float_, "content", None)
                        if content is None:
                            continue
                        found = _walk(content)
                        if found is not None:
                            return found
                elif value is not None and type(value).__module__.startswith("prompt_toolkit"):
                    found = _walk(value)
                    if found is not None:
                        return found
            return None

        return _walk(layout_container)


    class SlashCommandMenuControl(UIControl):
        """Compact slash menu aligned to the composer, following the Kimi-style layout."""

        _LEFT_PADDING = 2
        _MAX_EXPANDED_META_LINES = 2
        _SCROLL_OFFSET = 1

        def has_focus(self) -> bool:
            return False

        def preferred_width(self, max_available_width: int) -> int | None:
            return max_available_width

        def preferred_height(
            self,
            width: int,
            max_available_height: int,
            wrap_lines: bool,
            get_line_prefix: Callable[..., Any] | None,
        ) -> int | None:
            del wrap_lines, get_line_prefix
            app = get_app_or_none()
            complete_state = getattr(app.current_buffer, "complete_state", None) if app is not None else None
            if complete_state is None or not complete_state.completions:
                return 0
            completions = list(complete_state.completions)
            selected_index = complete_state.complete_index
            if selected_index is None:
                return min(max_available_height, len(completions) + 1)
            menu_width = max(0, width - self._LEFT_PADDING)
            marker_width = 2
            command_width = self._command_column_width(completions, menu_width, marker_width)
            gap_width = 3 if menu_width > command_width + 8 else 1
            meta_width = max(0, menu_width - marker_width - command_width - gap_width)
            selected_meta_lines = self._selected_meta_lines(
                getattr(completions[selected_index], "display_meta_text", ""),
                meta_width,
            )
            return min(max_available_height, len(completions) + len(selected_meta_lines))

        def create_content(self, width: int, height: int) -> UIContent:
            app = get_app_or_none()
            complete_state = getattr(app.current_buffer, "complete_state", None) if app is not None else None
            if complete_state is None or not complete_state.completions:
                return UIContent()

            completions = list(complete_state.completions)
            selected_index = complete_state.complete_index
            available_rows = max(1, height - 1)
            menu_width = max(0, width - self._LEFT_PADDING)
            marker_width = 2
            command_width = self._command_column_width(completions, menu_width, marker_width)
            gap_width = 3 if menu_width > command_width + 8 else 1
            meta_width = max(0, menu_width - marker_width - command_width - gap_width)

            lines: list[FormattedText] = [
                FormattedText([("class:slash-completion-menu.separator", "-" * max(0, width))])
            ]
            selected_line_index = 1

            if selected_index is None:
                end = min(len(completions) - 1, available_rows - 1)
                for index in range(0, end + 1):
                    lines.append(
                        self._render_single_line_item(
                            width=width,
                            completion=completions[index],
                            marker_width=marker_width,
                            command_width=command_width,
                            meta_width=meta_width,
                            gap_width=gap_width,
                            is_current=False,
                        )
                    )
                return UIContent(
                    get_line=lambda i: lines[i],
                    line_count=len(lines),
                    cursor_position=Point(x=0, y=selected_line_index),
                )

            selected_meta_lines = self._selected_meta_lines(
                getattr(completions[selected_index], "display_meta_text", ""),
                meta_width,
            )
            start, end = self._visible_window_bounds(
                completion_count=len(completions),
                selected_index=selected_index,
                available_rows=available_rows,
                selected_item_height=len(selected_meta_lines),
            )

            for index in range(start, end + 1):
                completion = completions[index]
                if index == selected_index:
                    selected_line_index = len(lines)
                    lines.extend(
                        self._render_selected_item_lines(
                            width=width,
                            completion=completion,
                            marker_width=marker_width,
                            command_width=command_width,
                            meta_width=meta_width,
                            gap_width=gap_width,
                            meta_lines=selected_meta_lines,
                        )
                    )
                    continue
                lines.append(
                    self._render_single_line_item(
                        width=width,
                        completion=completion,
                        marker_width=marker_width,
                        command_width=command_width,
                        meta_width=meta_width,
                        gap_width=gap_width,
                        is_current=False,
                    )
                )

            return UIContent(
                get_line=lambda i: lines[i],
                line_count=len(lines),
                cursor_position=Point(x=0, y=selected_line_index),
            )

        def _selected_meta_lines(self, text: str, meta_width: int) -> list[str]:
            clean = str(text or "").strip()
            if not clean:
                return [""]
            words = [chunk for chunk in re.split(r"\s+", clean) if chunk]
            if not words:
                return [""]
            lines: list[str] = []
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if get_cwidth(candidate) <= max(0, meta_width):
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                    if len(lines) >= self._MAX_EXPANDED_META_LINES:
                        return lines
                current = _truncate_to_width(word, max(0, meta_width)).rstrip()
            if current:
                lines.append(current)
            return lines[: self._MAX_EXPANDED_META_LINES] or [""]

        def _visible_window_bounds(
            self,
            *,
            completion_count: int,
            selected_index: int,
            available_rows: int,
            selected_item_height: int,
        ) -> tuple[int, int]:
            selected_item_height = min(selected_item_height, available_rows)
            remaining_rows = max(0, available_rows - selected_item_height)
            before = min(self._SCROLL_OFFSET, selected_index, remaining_rows)
            remaining_rows -= before
            after = min(completion_count - selected_index - 1, remaining_rows)
            remaining_rows -= after
            extra_before = min(selected_index - before, remaining_rows)
            before += extra_before
            remaining_rows -= extra_before
            extra_after = min(completion_count - selected_index - 1 - after, remaining_rows)
            after += extra_after
            return selected_index - before, selected_index + after

        def _command_column_width(
            self,
            completions: Sequence[Any],
            menu_width: int,
            marker_width: int,
        ) -> int:
            if menu_width <= 0:
                return 0
            longest = max(
                (
                    get_cwidth(
                        _truncate_to_width(
                            str(getattr(completion, "display_text", "") or getattr(completion, "text", "")).strip(),
                            menu_width,
                        )
                    )
                    for completion in completions
                ),
                default=0,
            )
            usable_width = max(0, menu_width - marker_width)
            minimum = min(usable_width, 16)
            maximum = max(minimum, min(30, usable_width // 2))
            preferred = min(longest + 2, usable_width)
            return max(minimum, min(preferred, maximum))

        def _render_single_line_item(
            self,
            *,
            width: int,
            completion: Any,
            marker_width: int,
            command_width: int,
            meta_width: int,
            gap_width: int,
            is_current: bool,
        ) -> FormattedText:
            base_style = "class:slash-completion-menu.current" if is_current else "class:slash-completion-menu.item"
            alias_style = (
                "class:slash-completion-menu.current-alias"
                if is_current
                else "class:slash-completion-menu.alias"
            )
            marker = "> " if is_current else "  "
            display_text = str(getattr(completion, "display_text", "") or getattr(completion, "text", "")).strip()
            parts = [part.strip() for part in re.split(r"\s{2,}", display_text) if part.strip()]
            primary = parts[0] if parts else str(getattr(completion, "text", "") or "")
            aliases = "  ".join(parts[1:])
            meta_text = _truncate_to_width(
                str(getattr(completion, "display_meta_text", "") or "").strip(),
                max(0, meta_width),
            )
            marker_text = marker.ljust(marker_width)
            left_padding = " " * self._LEFT_PADDING
            alias_budget = max(0, command_width - get_cwidth(primary) - 2)
            alias_text = ""
            if aliases and alias_budget > 4:
                alias_text = "  " + _truncate_to_width(aliases, alias_budget - 2)
            primary_text = _truncate_to_width(primary, max(0, command_width - get_cwidth(alias_text)))
            used = (
                get_cwidth(left_padding)
                + get_cwidth(marker_text)
                + get_cwidth(primary_text)
                + get_cwidth(alias_text)
                + gap_width
                + get_cwidth(meta_text)
            )
            trailing = " " * max(0, width - used)
            return FormattedText(
                [
                    (base_style, left_padding),
                    (base_style, marker_text),
                    (base_style, primary_text),
                    (alias_style, alias_text),
                    (base_style, " " * gap_width),
                    ("class:slash-completion-menu.meta", meta_text),
                    (base_style, trailing),
                ]
            )

        def _render_selected_item_lines(
            self,
            *,
            width: int,
            completion: Any,
            marker_width: int,
            command_width: int,
            meta_width: int,
            gap_width: int,
            meta_lines: Sequence[str],
        ) -> list[FormattedText]:
            first_line_completion = completion
            if meta_lines:
                class _DisplayProxy:
                    def __init__(self, original: Any, meta: str) -> None:
                        self.text = getattr(original, "text", "")
                        self.display_text = getattr(original, "display_text", "")
                        self.display_meta_text = meta

                first_line_completion = _DisplayProxy(completion, meta_lines[0])

            lines = [
                self._render_single_line_item(
                    width=width,
                    completion=first_line_completion,
                    marker_width=marker_width,
                    command_width=command_width,
                    meta_width=meta_width,
                    gap_width=gap_width,
                    is_current=True,
                )
            ]
            continuation_prefix = " " * (
                self._LEFT_PADDING + marker_width + command_width + gap_width
            )
            continuation_trailing = max(0, width - get_cwidth(continuation_prefix) - meta_width)
            for meta_line in meta_lines[1:]:
                lines.append(
                    FormattedText(
                        [
                            ("class:slash-completion-menu.current", continuation_prefix),
                            (
                                "class:slash-completion-menu.meta",
                                _truncate_to_width(meta_line, max(0, meta_width)),
                            ),
                            ("class:slash-completion-menu.current", " " * continuation_trailing),
                        ]
                    )
                )
            return lines


    def _should_show_slash_completion_menu(session: Any) -> bool:
        buffer = getattr(session, "default_buffer", None)
        if buffer is None:
            return False
        document = getattr(buffer, "document", None)
        if document is None:
            return False
        return bool(str(document.text_before_cursor).lstrip().startswith("/"))


    def _install_slash_completion_menu(session: Any) -> None:
        layout = getattr(session, "layout", None)
        if layout is None:
            return
        float_container = _find_prompt_float_container(getattr(layout, "container", None))
        if not isinstance(float_container, FloatContainer):
            return
        slash_menu_filter = (
            has_focus(session.default_buffer)
            & has_completions
            & ~is_done
            & Condition(lambda: _should_show_slash_completion_menu(session))
        )
        slash_menu = ConditionalContainer(
            Window(
                content=SlashCommandMenuControl(),
                dont_extend_height=True,
                height=Dimension(max=10),
                style="class:slash-completion-menu",
            ),
            filter=slash_menu_filter,
        )
        float_container.floats.insert(
            0,
            Float(
                left=0,
                right=0,
                ycursor=True,
                transparent=True,
                content=slash_menu,
                z_index=10**8,
            ),
        )
        default_menu = next(
            (
                float_
                for float_ in float_container.floats[1:]
                if isinstance(getattr(float_, "content", None), CompletionsMenu)
            ),
            None,
        )
        if default_menu is None:
            return
        default_menu.content = ConditionalContainer(
            default_menu.content,
            filter=~Condition(lambda: _should_show_slash_completion_menu(session)),
        )


else:

    def _install_slash_completion_menu(session: Any) -> None:
        del session


def _should_open_palette_on_slash(buffer_text: str) -> bool:
    return not str(buffer_text or "").strip()


def _should_use_palette_dialog(buffer_text: str) -> bool:
    stripped = str(buffer_text or "").lstrip()
    if not stripped.startswith("/"):
        return False
    return (" " not in stripped[1:]) and ("\t" not in stripped[1:])


def _slash_palette_result(buffer_text: str) -> str | None:
    return None


def _top_level_palette_result(buffer_text: str) -> str | None:
    return None


def _resolve_slash_palette_selection(*, lang: str, display_mode: str | None = None) -> str | None:
    opened, selection = open_command_palette(lang=lang, display_mode=display_mode)
    if not opened:
        return None
    if isinstance(selection, str) and selection.strip():
        return selection.strip()
    return ""


def _sanitize_terminal_text(text: str) -> str:
    clean = re.sub(re.escape(ESC) + r"\[[0-9;]*[A-Za-z]", "", text)
    return ORPHANED_ANSI_RE.sub("", clean)


def _panel_width_hint(text: str, *, title: str, stream: TextIO) -> int | None:
    is_tty = bool(getattr(stream, "isatty", lambda: False)())
    if is_tty:
        return None
    lines = [line.rstrip() for line in str(text or "").splitlines()]
    content_width = max((len(line) for line in lines), default=0)
    # Rich panels need room for borders plus horizontal padding on both sides.
    return max(48, min(160, max(content_width + 6, len(title) + 8)))


def prompt_line(  # noqa: F811
    *,
    lang: str,
    bottom_toolbar: str | None = None,
    display_mode: str | None = None,
    default_text: str = "",
) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    try:
        from prompt_toolkit.completion import CompleteStyle
    except Exception:
        from prompt_toolkit.shortcuts.prompt import CompleteStyle

    completer = build_prompt_completer(lang, display_mode=display_mode)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#111111 #dddddd",
            "completion-menu.completion.current": "bg:#0a5ea8 #ffffff bold",
            "completion.alias": "fg:#808080",
            "bottom-toolbar": "bg:#101010 #808080",
        }
    )
    prompt = HTML("<prompt>&gt;</prompt> ")
    key_bindings = KeyBindings()
    toolbar_text = bottom_toolbar or (
        "/ 候補 | ↑↓ 移動 | Enter 実行" if lang == "ja" else "/ commands | arrows move | Enter runs"
    )
    placeholder = "話しかける" if lang == "ja" else "Talk to YonerAI"

    @key_bindings.add("/")
    def _open_palette_or_insert(event) -> None:
        buffer = event.current_buffer
        palette_result = _slash_palette_result(buffer.text)
        if palette_result is not None:
            event.app.exit(result=palette_result)
            return
        buffer.insert_text("/")
        text = buffer.text.lstrip()
        if text.startswith("/") and buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    @key_bindings.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state and buffer.complete_state.completions:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
        buffer.validate_and_handle()

    @key_bindings.add("tab")
    def _complete_or_cycle(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/"):
            return
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)
            return
        buffer.complete_next()

    @key_bindings.add("s-tab")
    def _complete_previous(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/") or buffer.complete_state is None:
            return
        buffer.complete_previous()

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        complete_style=CompleteStyle.READLINE_LIKE,
        reserve_space_for_menu=6,
        rprompt=None,
        bottom_toolbar=toolbar_text,
        placeholder=placeholder,
        show_frame=True,
        style=style,
        key_bindings=key_bindings,
    )
    _install_slash_completion_menu(session)
    try:
        return str(session.prompt(prompt, default=default_text)).strip()
    except (EOFError, KeyboardInterrupt):
        return "/終了" if lang == "ja" else "/quit"


def _resolve_palette_trigger(*, lang: str, display_mode: str | None = None) -> str:
    opened, selection = open_command_palette(lang=lang, display_mode=display_mode)
    if opened and isinstance(selection, str):
        return selection.strip()
    return ""


def _palette_trigger(query: str | None = None) -> str:
    value = str(query or "").strip()
    if not value:
        return COMMAND_PALETTE_TRIGGER
    return f"{COMMAND_PALETTE_TRIGGER}:{value}"


def open_command_palette(
    *,
    lang: str,
    display_mode: str | None = None,
    query: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)

    items = command_palette_dialog_items(lang, display_mode=display_mode, query=query)
    if not items:
        return (False, None)

    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    query_text = str(query or "").strip()
    title = "YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands"
    if lang == "ja":
        text = (
            f"絞り込み: {query_text}\\n矢印で選び、Enter でそのまま実行します。"
            if query_text
            else "矢印で選び、Enter でそのまま実行します。Esc で閉じます。"
        )
    else:
        text = (
            f"filter: {query_text}\\nChoose with arrows, then press Enter to run now."
            if query_text
            else "Choose with arrows. Enter runs now. Esc closes."
        )
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=items,
            ok_text="実行" if lang == "ja" else "Run",
            cancel_text="閉じる" if lang == "ja" else "Close",
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)


def open_choice_dialog(
    *,
    title: str,
    text: str,
    values: list[tuple[str, str]],
    ok_text: str,
    cancel_text: str,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)
    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=values,
            ok_text=ok_text,
            cancel_text=cancel_text,
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)


def render_panel(text: str, *, title: str, stream: TextIO, color: str = "auto") -> bool:
    sanitized = _sanitize_terminal_text(text)
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
    except Exception:
        stream.write(f"[{title}]\n{sanitized}\n")
        return True
    force_terminal = None if color == "auto" else color != "never"
    console = Console(
        file=stream,
        force_terminal=force_terminal,
        color_system="auto",
        width=_panel_width_hint(sanitized, title=title, stream=stream),
    )
    # Interactive surfaces are plain-text first. Re-parsing partial ANSI here
    # causes header corruption and oversized panels when broken fragments slip in.
    renderable = Text(sanitized)
    console.print(Panel(renderable, title=title, border_style="cyan", expand=False, padding=(1, 2)))
    return True


def render_text_block(text: str, *, stream: TextIO, color: str = "auto") -> bool:
    sanitized = _sanitize_terminal_text(text)
    try:
        from rich.console import Console
        from rich.text import Text
    except Exception:
        stream.write(sanitized)
        return True
    force_terminal = None if color == "auto" else color != "never"
    console = Console(file=stream, force_terminal=force_terminal, color_system="auto")
    renderable = Text(sanitized)
    console.print(renderable, end="")
    return True


def run_with_status(message: str, func: Callable[[], T], *, stream: TextIO, color: str = "auto") -> T:
    try:
        from rich.console import Console
    except Exception:
        return func()
    force_terminal = None if color == "auto" else color != "never"
    console = Console(file=stream, force_terminal=force_terminal, color_system="auto")
    with console.status(message, spinner="dots"):
        return func()


def tui_capability_report() -> dict[str, object]:
    prompt_ready = prompt_toolkit_available()
    rich_ready = rich_available()
    return {
        "schema_version": "yonerai-tui-runtime/v0.6",
        "prompt_toolkit_available": prompt_ready,
        "rich_available": rich_ready,
        "slash_completion": prompt_ready,
        "command_palette_categories": True,
        "japanese_alias_completion": True,
        "japanese_value_completion": True,
        "context_value_completion": prompt_ready,
        "completion_descriptions": prompt_ready,
        "tab_completion": prompt_ready,
        "arrow_selection": prompt_ready,
        "command_palette_popup": prompt_ready,
        "status_screen": True,
        "context_screen": True,
        "memory_screen": True,
        "rich_panels": rich_ready,
        "rich_status_spinner": rich_ready,
        "plain_fallback": True,
        "json_ansi_output": False,
    }


# Clean Japanese UX overrides. These live at EOF so they supersede any older
# mojibake-prone definitions above without risking broader TUI regressions.
if PROMPT_TOOLKIT_MENU_READY:

    def _install_slash_completion_menu(session: Any) -> None:
        layout = getattr(session, "layout", None)
        if layout is None:
            return
        float_container = _find_prompt_float_container(getattr(layout, "container", None))
        if not isinstance(float_container, FloatContainer):
            return
        slash_menu_filter = (
            has_focus(session.default_buffer)
            & has_completions
            & ~is_done
            & Condition(lambda: _should_show_slash_completion_menu(session))
        )
        slash_menu = ConditionalContainer(
            Window(
                content=SlashCommandMenuControl(),
                dont_extend_height=True,
                height=Dimension(max=10),
                style="class:slash-completion-menu",
            ),
            filter=slash_menu_filter,
        )
        float_container.floats.insert(
            0,
            Float(
                left=0,
                right=0,
                ycursor=True,
                xcursor=True,
                attach_to_window=getattr(layout, "current_window", None),
                allow_cover_cursor=False,
                transparent=True,
                content=slash_menu,
                z_index=10**8,
            ),
        )
        default_menu = next(
            (
                float_
                for float_ in float_container.floats[1:]
                if isinstance(getattr(float_, "content", None), CompletionsMenu)
            ),
            None,
        )
        if default_menu is None:
            return
        default_menu.content = ConditionalContainer(
            default_menu.content,
            filter=~Condition(lambda: _should_show_slash_completion_menu(session)),
        )
else:

    def _install_slash_completion_menu(session: Any) -> None:
        del session


def _slash_palette_result(buffer_text: str) -> str | None:
    return None


def prompt_line(  # noqa: F811
    *,
    lang: str,
    bottom_toolbar: str | None = None,
    display_mode: str | None = None,
    default_text: str = "",
) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    try:
        from prompt_toolkit.completion import CompleteStyle
    except Exception:
        from prompt_toolkit.shortcuts.prompt import CompleteStyle

    completer = build_prompt_completer(lang, display_mode=display_mode)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#111111 #dddddd",
            "completion-menu.completion.current": "bg:#0a5ea8 #ffffff bold",
            "completion.alias": "fg:#808080",
            "bottom-toolbar": "bg:#101010 #808080",
        }
    )
    prompt = HTML("<prompt>&gt;</prompt> ")
    key_bindings = KeyBindings()
    toolbar_text = bottom_toolbar or (
        "/ でコマンド | Tab で中央候補 | Esc で閉じる"
        if lang == "ja"
        else "/ for commands | Tab for centered palette | Esc closes"
    )
    placeholder = "そのまま話す" if lang == "ja" else "Talk to YonerAI"

    @key_bindings.add("/")
    def _open_palette_or_insert(event) -> None:
        buffer = event.current_buffer
        buffer.insert_text("/")
        text = buffer.text.lstrip()
        if text.startswith("/") and buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    @key_bindings.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state and buffer.complete_state.completions:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
        buffer.validate_and_handle()

    @key_bindings.add("tab")
    def _complete_or_cycle(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/"):
            return
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)
            return
        buffer.complete_next()

    @key_bindings.add("s-tab")
    def _complete_previous(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/") or buffer.complete_state is None:
            return
        buffer.complete_previous()

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        complete_style=CompleteStyle.READLINE_LIKE,
        reserve_space_for_menu=7,
        rprompt=None,
        bottom_toolbar=toolbar_text,
        placeholder=placeholder,
        show_frame=True,
        style=style,
        key_bindings=key_bindings,
    )
    _install_slash_completion_menu(session)
    try:
        return str(session.prompt(prompt, default=default_text)).strip()
    except (EOFError, KeyboardInterrupt):
        return "/終了" if lang == "ja" else "/quit"


def open_command_palette(  # noqa: F811
    *,
    lang: str,
    display_mode: str | None = None,
    query: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)

    items = command_palette_dialog_items(lang, display_mode=display_mode, query=query)
    if not items:
        return (False, None)

    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    query_text = str(query or "").strip()
    title = "YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands"
    if lang == "ja":
        text = (
            f"絞り込み: {query_text}\n上下で選択し、Enter で実行します。"
            if query_text
            else "よく使う操作だけを出します。上下で選択し、Enter で実行します。"
        )
    else:
        text = (
            f"filter: {query_text}\nChoose with arrows, then press Enter to run it."
            if query_text
            else "Only common actions are shown first. Choose with arrows, then press Enter."
        )
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=items,
            ok_text="実行" if lang == "ja" else "Run",
            cancel_text="閉じる" if lang == "ja" else "Close",
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)


# Final UX overrides for visible slash suggestions and cleaner Japanese copy.
if PROMPT_TOOLKIT_MENU_READY:
    _YONERAI_SLASH_MENU_MAX_WIDTH = 72
    _YONERAI_SLASH_MENU_MIN_WIDTH = 36
    _YONERAI_SLASH_MENU_MAX_HEIGHT = 10
    _YONERAI_SLASH_MENU_TAG = "_yonerai_slash_menu"
    _YONERAI_SLASH_MENU_BOTTOM_OFFSET = 2
    _YONERAI_SLASH_MENU_BOTTOM_OFFSET = 2

    def _yonerai_prompt_toolbar(lang: str) -> str:
        if lang == "ja":
            return "/ で候補 | /l で絞り込み | Tab でパレット | Esc で閉じる"
        return "/ for commands | /l to filter | Tab for palette | Esc closes"


    def _yonerai_prompt_placeholder(lang: str) -> str:
        return "そのまま入力して会話" if lang == "ja" else "Talk to YonerAI"


    def _yonerai_quit_command(lang: str) -> str:
        return "/終了" if lang == "ja" else "/quit"


    def _yonerai_open_command_palette_text(lang: str, query_text: str) -> str:
        if lang == "ja":
            if query_text:
                return f"絞り込み: {query_text}\n上下で選択し、Enter で実行します。"
            return "よく使う短いコマンドを先に出します。上下で選択し、Enter で実行します。"
        if query_text:
            return f"filter: {query_text}\nChoose with arrows, then press Enter."
        return "Only common short commands are shown first. Choose with arrows, then press Enter."


    def _install_slash_completion_menu(session: Any) -> None:  # noqa: F811
        layout = getattr(session, "layout", None)
        if layout is None:
            return
        float_container = _find_prompt_float_container(getattr(layout, "container", None))
        if not isinstance(float_container, FloatContainer):
            return
        float_container.floats[:] = [
            float_
            for float_ in float_container.floats
            if not getattr(float_, _YONERAI_SLASH_MENU_TAG, False)
        ]
        slash_menu_filter = (
            has_focus(session.default_buffer)
            & has_completions
            & ~is_done
            & Condition(lambda: _should_show_slash_completion_menu(session))
        )
        slash_menu = ConditionalContainer(
            Window(
                content=SlashCommandMenuControl(),
                width=Dimension(
                    min=_YONERAI_SLASH_MENU_MIN_WIDTH,
                    preferred=56,
                    max=_YONERAI_SLASH_MENU_MAX_WIDTH,
                ),
                height=Dimension(min=1, max=_YONERAI_SLASH_MENU_MAX_HEIGHT),
                dont_extend_width=True,
                dont_extend_height=True,
                style="class:slash-completion-menu",
            ),
            filter=slash_menu_filter,
        )
        slash_float = Float(
            left=0,
            right=0,
            bottom=_YONERAI_SLASH_MENU_BOTTOM_OFFSET,
            transparent=True,
            content=slash_menu,
            z_index=10**8,
        )
        setattr(slash_float, _YONERAI_SLASH_MENU_TAG, True)
        float_container.floats.insert(0, slash_float)
        default_menu = next(
            (
                float_
                for float_ in float_container.floats[1:]
                if isinstance(getattr(float_, "content", None), CompletionsMenu)
            ),
            None,
        )
        if default_menu is None:
            return
        default_menu.content = ConditionalContainer(
            default_menu.content,
            filter=~Condition(lambda: _should_show_slash_completion_menu(session)),
        )


    SlashCommandMenuControl.preferred_width = (  # type: ignore[method-assign]
        lambda self, max_available_width: min(max_available_width, _YONERAI_SLASH_MENU_MAX_WIDTH)
    )


def prompt_line(  # noqa: F811
    *,
    lang: str,
    bottom_toolbar: str | None = None,
    display_mode: str | None = None,
    default_text: str = "",
) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    try:
        from prompt_toolkit.completion import CompleteStyle
    except Exception:
        from prompt_toolkit.shortcuts.prompt import CompleteStyle

    completer = build_prompt_completer(lang, display_mode=display_mode)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#111111 #dddddd",
            "completion-menu.completion.current": "bg:#0a5ea8 #ffffff bold",
            "completion.alias": "fg:#808080",
            "bottom-toolbar": "bg:#101010 #808080",
        }
    )
    prompt = HTML("<prompt>&gt;</prompt> ")
    key_bindings = KeyBindings()
    toolbar_text = bottom_toolbar or (
        _yonerai_prompt_toolbar(lang) if PROMPT_TOOLKIT_MENU_READY else "/ for commands | Tab for palette"
    )
    placeholder = (
        _yonerai_prompt_placeholder(lang) if PROMPT_TOOLKIT_MENU_READY else ("Talk to YonerAI" if lang != "ja" else "そのまま入力して会話")
    )

    @key_bindings.add("/")
    def _open_palette_or_insert(event) -> None:
        buffer = event.current_buffer
        buffer.insert_text("/")
        text = buffer.text.lstrip()
        if text.startswith("/") and buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    @key_bindings.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state and buffer.complete_state.completions:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
        buffer.validate_and_handle()

    @key_bindings.add("tab")
    def _complete_or_cycle(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/"):
            return
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)
            return
        buffer.complete_next()

    @key_bindings.add("s-tab")
    def _complete_previous(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/") or buffer.complete_state is None:
            return
        buffer.complete_previous()

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        complete_style=CompleteStyle.READLINE_LIKE,
        reserve_space_for_menu=1,
        rprompt=None,
        bottom_toolbar=toolbar_text,
        placeholder=placeholder,
        show_frame=True,
        style=style,
        key_bindings=key_bindings,
    )
    if PROMPT_TOOLKIT_MENU_READY:
        _install_slash_completion_menu(session)
    try:
        return str(session.prompt(prompt, default=default_text)).strip()
    except (EOFError, KeyboardInterrupt):
        return _yonerai_quit_command(lang) if PROMPT_TOOLKIT_MENU_READY else "/quit"


def open_command_palette(  # noqa: F811
    *,
    lang: str,
    display_mode: str | None = None,
    query: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)

    items = command_palette_dialog_items(lang, display_mode=display_mode, query=query)
    if not items:
        return (False, None)

    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    query_text = str(query or "").strip()
    title = "YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands"
    text = (
        _yonerai_open_command_palette_text(lang, query_text)
        if PROMPT_TOOLKIT_MENU_READY
        else (
            f"filter: {query_text}\nChoose with arrows, then press Enter."
            if query_text
            else "Only common short commands are shown first. Choose with arrows, then press Enter."
        )
    )
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=items,
            ok_text="実行" if lang == "ja" else "Run",
            cancel_text="閉じる" if lang == "ja" else "Close",
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)


# Final UX overrides for visible slash suggestions and cleaner Japanese copy.
if PROMPT_TOOLKIT_MENU_READY:
    _YONERAI_SLASH_MENU_MAX_WIDTH = 72
    _YONERAI_SLASH_MENU_MIN_WIDTH = 36
    _YONERAI_SLASH_MENU_MAX_HEIGHT = 10
    _YONERAI_SLASH_MENU_TAG = "_yonerai_slash_menu"

    def _yonerai_prompt_toolbar(lang: str) -> str:
        if lang == "ja":
            return "/ で候補 | /l で絞り込み | Tab でパレット | Esc で閉じる"
        return "/ for commands | /l to filter | Tab for palette | Esc closes"


    def _yonerai_prompt_placeholder(lang: str) -> str:
        return "そのまま入力して会話" if lang == "ja" else "Talk to YonerAI"


    def _yonerai_quit_command(lang: str) -> str:
        return "/終了" if lang == "ja" else "/quit"


    def _yonerai_open_command_palette_text(lang: str, query_text: str) -> str:
        if lang == "ja":
            if query_text:
                return f"絞り込み: {query_text}\n上下で選択し、Enter で実行します。"
            return "よく使う短いコマンドを先に出します。上下で選択し、Enter で実行します。"
        if query_text:
            return f"filter: {query_text}\nChoose with arrows, then press Enter."
        return "Only common short commands are shown first. Choose with arrows, then press Enter."


    def _install_slash_completion_menu(session: Any) -> None:  # noqa: F811
        layout = getattr(session, "layout", None)
        if layout is None:
            return
        float_container = _find_prompt_float_container(getattr(layout, "container", None))
        if not isinstance(float_container, FloatContainer):
            return
        float_container.floats[:] = [
            float_
            for float_ in float_container.floats
            if not getattr(float_, _YONERAI_SLASH_MENU_TAG, False)
        ]
        slash_menu_filter = (
            has_focus(session.default_buffer)
            & has_completions
            & ~is_done
            & Condition(lambda: _should_show_slash_completion_menu(session))
        )
        slash_menu = ConditionalContainer(
            Window(
                content=SlashCommandMenuControl(),
                width=Dimension(
                    min=_YONERAI_SLASH_MENU_MIN_WIDTH,
                    preferred=56,
                    max=_YONERAI_SLASH_MENU_MAX_WIDTH,
                ),
                height=Dimension(min=1, max=_YONERAI_SLASH_MENU_MAX_HEIGHT),
                dont_extend_width=True,
                dont_extend_height=True,
                style="class:slash-completion-menu",
            ),
            filter=slash_menu_filter,
        )
        slash_float = Float(
            left=0,
            right=0,
            bottom=_YONERAI_SLASH_MENU_BOTTOM_OFFSET,
            transparent=True,
            content=slash_menu,
            z_index=10**8,
        )
        setattr(slash_float, _YONERAI_SLASH_MENU_TAG, True)
        float_container.floats.insert(0, slash_float)
        default_menu = next(
            (
                float_
                for float_ in float_container.floats[1:]
                if isinstance(getattr(float_, "content", None), CompletionsMenu)
            ),
            None,
        )
        if default_menu is None:
            return
        default_menu.content = ConditionalContainer(
            default_menu.content,
            filter=~Condition(lambda: _should_show_slash_completion_menu(session)),
        )


    SlashCommandMenuControl.preferred_width = (  # type: ignore[method-assign]
        lambda self, max_available_width: min(max_available_width, _YONERAI_SLASH_MENU_MAX_WIDTH)
    )


def prompt_line(  # noqa: F811
    *,
    lang: str,
    bottom_toolbar: str | None = None,
    display_mode: str | None = None,
    default_text: str = "",
) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    try:
        from prompt_toolkit.completion import CompleteStyle
    except Exception:
        from prompt_toolkit.shortcuts.prompt import CompleteStyle

    completer = build_prompt_completer(lang, display_mode=display_mode)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#111111 #dddddd",
            "completion-menu.completion.current": "bg:#0a5ea8 #ffffff bold",
            "completion.alias": "fg:#808080",
            "bottom-toolbar": "bg:#101010 #808080",
        }
    )
    prompt = HTML("<prompt>&gt;</prompt> ")
    key_bindings = KeyBindings()
    toolbar_text = bottom_toolbar or _yonerai_prompt_toolbar(lang)
    placeholder = _yonerai_prompt_placeholder(lang)

    @key_bindings.add("/")
    def _open_palette_or_insert(event) -> None:
        buffer = event.current_buffer
        buffer.insert_text("/")
        text = buffer.text.lstrip()
        if text.startswith("/") and buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    @key_bindings.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state and buffer.complete_state.completions:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
        buffer.validate_and_handle()

    @key_bindings.add("tab")
    def _complete_or_cycle(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/"):
            return
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)
            return
        buffer.complete_next()

    @key_bindings.add("s-tab")
    def _complete_previous(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/") or buffer.complete_state is None:
            return
        buffer.complete_previous()

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        complete_style=CompleteStyle.READLINE_LIKE,
        reserve_space_for_menu=1,
        rprompt=None,
        bottom_toolbar=toolbar_text,
        placeholder=placeholder,
        show_frame=True,
        style=style,
        key_bindings=key_bindings,
    )
    _install_slash_completion_menu(session)
    try:
        return str(session.prompt(prompt, default=default_text)).strip()
    except (EOFError, KeyboardInterrupt):
        return _yonerai_quit_command(lang)


def open_command_palette(  # noqa: F811
    *,
    lang: str,
    display_mode: str | None = None,
    query: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)

    items = command_palette_dialog_items(lang, display_mode=display_mode, query=query)
    if not items:
        return (False, None)

    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    query_text = str(query or "").strip()
    title = "YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands"
    text = _yonerai_open_command_palette_text(lang, query_text)
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=items,
            ok_text="実行" if lang == "ja" else "Run",
            cancel_text="閉じる" if lang == "ja" else "Close",
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)


# Clean UTF-8 UX overrides for the interactive command surface.
if PROMPT_TOOLKIT_MENU_READY:

    def _install_slash_completion_menu(session: Any) -> None:
        layout = getattr(session, "layout", None)
        if layout is None:
            return
        float_container = _find_prompt_float_container(getattr(layout, "container", None))
        if not isinstance(float_container, FloatContainer):
            return
        slash_menu_filter = (
            has_focus(session.default_buffer)
            & has_completions
            & ~is_done
            & Condition(lambda: _should_show_slash_completion_menu(session))
        )
        slash_menu = ConditionalContainer(
            Window(
                content=SlashCommandMenuControl(),
                dont_extend_height=True,
                height=Dimension(max=12),
                style="class:slash-completion-menu",
            ),
            filter=slash_menu_filter,
        )
        float_container.floats.insert(
            0,
            Float(
                left=0,
                right=0,
                ycursor=True,
                allow_cover_cursor=False,
                transparent=True,
                content=slash_menu,
                z_index=10**8,
            ),
        )
        default_menu = next(
            (
                float_
                for float_ in float_container.floats[1:]
                if isinstance(getattr(float_, "content", None), CompletionsMenu)
            ),
            None,
        )
        if default_menu is None:
            return
        default_menu.content = ConditionalContainer(
            default_menu.content,
            filter=~Condition(lambda: _should_show_slash_completion_menu(session)),
        )


def _slash_palette_result(buffer_text: str) -> str | None:
    return None


def prompt_line(  # noqa: F811
    *,
    lang: str,
    bottom_toolbar: str | None = None,
    display_mode: str | None = None,
    default_text: str = "",
) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    try:
        from prompt_toolkit.completion import CompleteStyle
    except Exception:
        from prompt_toolkit.shortcuts.prompt import CompleteStyle

    completer = build_prompt_completer(lang, display_mode=display_mode)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#111111 #dddddd",
            "completion-menu.completion.current": "bg:#0a5ea8 #ffffff bold",
            "completion.alias": "fg:#808080",
            "bottom-toolbar": "bg:#101010 #808080",
        }
    )
    prompt = HTML("<prompt>&gt;</prompt> ")
    key_bindings = KeyBindings()
    toolbar_text = bottom_toolbar or (
        "/ で候補 / /l で絞り込み / Tab で中央一覧 / Esc で閉じる"
        if lang == "ja"
        else "/ for commands | /l to filter | Tab for centered palette | Esc closes"
    )
    placeholder = "そのまま入力して会話" if lang == "ja" else "Talk to YonerAI"

    @key_bindings.add("/")
    def _open_palette_or_insert(event) -> None:
        buffer = event.current_buffer
        buffer.insert_text("/")
        text = buffer.text.lstrip()
        if text.startswith("/") and buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    @key_bindings.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state and buffer.complete_state.completions:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
        buffer.validate_and_handle()

    @key_bindings.add("tab")
    def _complete_or_cycle(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/"):
            return
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)
            return
        buffer.complete_next()

    @key_bindings.add("s-tab")
    def _complete_previous(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/") or buffer.complete_state is None:
            return
        buffer.complete_previous()

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        complete_style=CompleteStyle.READLINE_LIKE,
        reserve_space_for_menu=10,
        rprompt=None,
        bottom_toolbar=toolbar_text,
        placeholder=placeholder,
        show_frame=True,
        style=style,
        key_bindings=key_bindings,
    )
    _install_slash_completion_menu(session)
    try:
        return str(session.prompt(prompt, default=default_text)).strip()
    except (EOFError, KeyboardInterrupt):
        return "/終了" if lang == "ja" else "/quit"


def open_command_palette(  # noqa: F811
    *,
    lang: str,
    display_mode: str | None = None,
    query: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)

    items = command_palette_dialog_items(lang, display_mode=display_mode, query=query)
    if not items:
        return (False, None)

    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    query_text = str(query or "").strip()
    title = "YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands"
    if lang == "ja":
        text = (
            f"絞り込み: {query_text}\n矢印で選び、Enter で実行します。"
            if query_text
            else "よく使う短いコマンドだけを先に表示します。矢印で選び、Enter で実行します。"
        )
    else:
        text = (
            f"filter: {query_text}\nChoose with arrows, then press Enter to run it."
            if query_text
            else "Only common short commands are shown first. Choose with arrows, then press Enter."
        )
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=items,
            ok_text="実行" if lang == "ja" else "Run",
            cancel_text="閉じる" if lang == "ja" else "Close",
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)


# Final UX overrides for the normal talkable CLI.
if PROMPT_TOOLKIT_MENU_READY:

    def _install_slash_completion_menu(session: Any) -> None:
        layout = getattr(session, "layout", None)
        if layout is None:
            return
        float_container = _find_prompt_float_container(getattr(layout, "container", None))
        if not isinstance(float_container, FloatContainer):
            return
        slash_menu_filter = (
            has_focus(session.default_buffer)
            & has_completions
            & ~is_done
            & Condition(lambda: _should_show_slash_completion_menu(session))
        )
        slash_menu = ConditionalContainer(
            Window(
                content=SlashCommandMenuControl(),
                dont_extend_height=True,
                height=Dimension(max=12),
                style="class:slash-completion-menu",
            ),
            filter=slash_menu_filter,
        )
        float_container.floats.insert(
            0,
            Float(
                left=0,
                right=0,
                ycursor=True,
                allow_cover_cursor=False,
                transparent=True,
                content=slash_menu,
                z_index=10**8,
            ),
        )
        default_menu = next(
            (
                float_
                for float_ in float_container.floats[1:]
                if isinstance(getattr(float_, "content", None), CompletionsMenu)
            ),
            None,
        )
        if default_menu is None:
            return
        default_menu.content = ConditionalContainer(
            default_menu.content,
            filter=~Condition(lambda: _should_show_slash_completion_menu(session)),
        )


def _slash_palette_result(buffer_text: str) -> str | None:
    return None


def prompt_line(  # noqa: F811
    *,
    lang: str,
    bottom_toolbar: str | None = None,
    display_mode: str | None = None,
    default_text: str = "",
) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    try:
        from prompt_toolkit.completion import CompleteStyle
    except Exception:
        from prompt_toolkit.shortcuts.prompt import CompleteStyle

    completer = build_prompt_completer(lang, display_mode=display_mode)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#111111 #dddddd",
            "completion-menu.completion.current": "bg:#0a5ea8 #ffffff bold",
            "completion.alias": "fg:#808080",
            "bottom-toolbar": "bg:#101010 #808080",
        }
    )
    prompt = HTML("<prompt>&gt;</prompt> ")
    key_bindings = KeyBindings()
    toolbar_text = bottom_toolbar or (
        "/ で候補 / /l で絞り込み / Tab で中央一覧 / Esc で閉じる"
        if lang == "ja"
        else "/ for commands | /l to filter | Tab for centered palette | Esc closes"
    )
    placeholder = "そのまま入力して会話" if lang == "ja" else "Talk to YonerAI"

    @key_bindings.add("/")
    def _open_palette_or_insert(event) -> None:
        buffer = event.current_buffer
        buffer.insert_text("/")
        text = buffer.text.lstrip()
        if text.startswith("/") and buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    @key_bindings.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state and buffer.complete_state.completions:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
        buffer.validate_and_handle()

    @key_bindings.add("tab")
    def _complete_or_cycle(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/"):
            return
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)
            return
        buffer.complete_next()

    @key_bindings.add("s-tab")
    def _complete_previous(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/") or buffer.complete_state is None:
            return
        buffer.complete_previous()

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        complete_style=CompleteStyle.READLINE_LIKE,
        reserve_space_for_menu=10,
        rprompt=None,
        bottom_toolbar=toolbar_text,
        placeholder=placeholder,
        show_frame=True,
        style=style,
        key_bindings=key_bindings,
    )
    _install_slash_completion_menu(session)
    try:
        return str(session.prompt(prompt, default=default_text)).strip()
    except (EOFError, KeyboardInterrupt):
        return "/終了" if lang == "ja" else "/quit"


def open_command_palette(  # noqa: F811
    *,
    lang: str,
    display_mode: str | None = None,
    query: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)

    items = command_palette_dialog_items(lang, display_mode=display_mode, query=query)
    if not items:
        return (False, None)

    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    query_text = str(query or "").strip()
    title = "YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands"
    if lang == "ja":
        text = (
            f"絞り込み: {query_text}\n上下で選択し、Enter で実行します。"
            if query_text
            else "よく使う短いコマンドを表示しています。上下で選択し、Enter で実行します。"
        )
    else:
        text = (
            f"filter: {query_text}\nChoose with arrows, then press Enter to run it."
            if query_text
            else "Only common short commands are shown first. Choose with arrows, then press Enter."
        )
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=items,
            ok_text="実行" if lang == "ja" else "Run",
            cancel_text="閉じる" if lang == "ja" else "Close",
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)


# Final UX overrides for visible slash suggestions and cleaner Japanese copy.
if PROMPT_TOOLKIT_MENU_READY:
    _YONERAI_SLASH_MENU_MAX_WIDTH = 72
    _YONERAI_SLASH_MENU_MIN_WIDTH = 36
    _YONERAI_SLASH_MENU_MAX_HEIGHT = 8
    _YONERAI_SLASH_MENU_LEFT_OFFSET = 1
    _YONERAI_SLASH_MENU_BOTTOM_OFFSET = 1
    _YONERAI_SLASH_MENU_TAG = "_yonerai_slash_menu"

    def _yonerai_prompt_toolbar(lang: str) -> str:
        if lang == "ja":
            return "/ で候補 | /l で絞り込み | Tab でパレット | Esc で閉じる"
        return "/ for commands | /l to filter | Tab for palette | Esc closes"


    def _yonerai_prompt_placeholder(lang: str) -> str:
        return "そのまま入力して会話" if lang == "ja" else "Talk to YonerAI"


    def _yonerai_quit_command(lang: str) -> str:
        return "/終了" if lang == "ja" else "/quit"


    def _yonerai_open_command_palette_text(lang: str, query_text: str) -> str:
        if lang == "ja":
            if query_text:
                return f"絞り込み: {query_text}\n上下で選択し、Enter で実行します。"
            return "よく使う短いコマンドを先に出します。上下で選択し、Enter で実行します。"
        if query_text:
            return f"filter: {query_text}\nChoose with arrows, then press Enter."
        return "Only common short commands are shown first. Choose with arrows, then press Enter."


    def _install_slash_completion_menu(session: Any) -> None:  # noqa: F811
        layout = getattr(session, "layout", None)
        if layout is None:
            return
        float_container = _find_prompt_float_container(getattr(layout, "container", None))
        if not isinstance(float_container, FloatContainer):
            return
        float_container.floats[:] = [
            float_
            for float_ in float_container.floats
            if not getattr(float_, _YONERAI_SLASH_MENU_TAG, False)
        ]
        slash_menu_filter = (
            has_focus(session.default_buffer)
            & has_completions
            & ~is_done
            & Condition(lambda: _should_show_slash_completion_menu(session))
        )
        slash_menu = ConditionalContainer(
            Window(
                content=SlashCommandMenuControl(),
                width=Dimension(
                    min=_YONERAI_SLASH_MENU_MIN_WIDTH,
                    preferred=56,
                    max=_YONERAI_SLASH_MENU_MAX_WIDTH,
                ),
                height=Dimension(min=1, max=_YONERAI_SLASH_MENU_MAX_HEIGHT),
                dont_extend_width=True,
                dont_extend_height=True,
                style="class:slash-completion-menu",
            ),
            filter=slash_menu_filter,
        )
        slash_float = Float(
            xcursor=False,
            ycursor=False,
            left=_YONERAI_SLASH_MENU_LEFT_OFFSET,
            bottom=_YONERAI_SLASH_MENU_BOTTOM_OFFSET,
            attach_to_window=getattr(layout, "current_window", None),
            allow_cover_cursor=False,
            transparent=True,
            content=slash_menu,
            z_index=10**8,
        )
        setattr(slash_float, _YONERAI_SLASH_MENU_TAG, True)
        float_container.floats.insert(0, slash_float)
        default_menu = next(
            (
                float_
                for float_ in float_container.floats[1:]
                if isinstance(getattr(float_, "content", None), CompletionsMenu)
            ),
            None,
        )
        if default_menu is None:
            return
        default_menu.content = ConditionalContainer(
            default_menu.content,
            filter=~Condition(lambda: _should_show_slash_completion_menu(session)),
        )


    SlashCommandMenuControl.preferred_width = (  # type: ignore[method-assign]
        lambda self, max_available_width: min(max_available_width, _YONERAI_SLASH_MENU_MAX_WIDTH)
    )


def prompt_line(  # noqa: F811
    *,
    lang: str,
    bottom_toolbar: str | None = None,
    display_mode: str | None = None,
    default_text: str = "",
) -> str:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style

    try:
        from prompt_toolkit.completion import CompleteStyle
    except Exception:
        from prompt_toolkit.shortcuts.prompt import CompleteStyle

    completer = build_prompt_completer(lang, display_mode=display_mode)
    style = Style.from_dict(
        {
            "prompt": "ansicyan bold",
            "completion-menu.completion": "bg:#111111 #dddddd",
            "completion-menu.completion.current": "bg:#0a5ea8 #ffffff bold",
            "completion.alias": "fg:#808080",
            "bottom-toolbar": "bg:#101010 #808080",
        }
    )
    prompt = HTML("<prompt>&gt;</prompt> ")
    key_bindings = KeyBindings()
    toolbar_text = bottom_toolbar or (
        _yonerai_prompt_toolbar(lang) if PROMPT_TOOLKIT_MENU_READY else "/ for commands | Tab for palette"
    )
    placeholder = (
        _yonerai_prompt_placeholder(lang) if PROMPT_TOOLKIT_MENU_READY else ("Talk to YonerAI" if lang != "ja" else "そのまま入力して会話")
    )

    @key_bindings.add("/")
    def _open_palette_or_insert(event) -> None:
        buffer = event.current_buffer
        buffer.insert_text("/")
        text = buffer.text.lstrip()
        if text.startswith("/") and buffer.complete_state is None:
            buffer.start_completion(select_first=False)

    @key_bindings.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:
        buffer = event.current_buffer
        if buffer.complete_state and buffer.complete_state.completions:
            completion = buffer.complete_state.current_completion or buffer.complete_state.completions[0]
            buffer.apply_completion(completion)
        buffer.validate_and_handle()

    @key_bindings.add("tab")
    def _complete_or_cycle(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/"):
            return
        if buffer.complete_state is None:
            buffer.start_completion(select_first=False)
            return
        buffer.complete_next()

    @key_bindings.add("s-tab")
    def _complete_previous(event) -> None:
        buffer = event.current_buffer
        text = buffer.text.lstrip()
        if not text.startswith("/") or buffer.complete_state is None:
            return
        buffer.complete_previous()

    session = PromptSession(
        completer=completer,
        complete_while_typing=True,
        complete_in_thread=True,
        complete_style=CompleteStyle.READLINE_LIKE,
        reserve_space_for_menu=1,
        rprompt=None,
        bottom_toolbar=toolbar_text,
        placeholder=placeholder,
        show_frame=True,
        style=style,
        key_bindings=key_bindings,
    )
    if PROMPT_TOOLKIT_MENU_READY:
        _install_slash_completion_menu(session)
    try:
        return str(session.prompt(prompt, default=default_text)).strip()
    except (EOFError, KeyboardInterrupt):
        return _yonerai_quit_command(lang) if PROMPT_TOOLKIT_MENU_READY else "/quit"


def open_command_palette(  # noqa: F811
    *,
    lang: str,
    display_mode: str | None = None,
    query: str | None = None,
) -> tuple[bool, str | None]:
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
        from prompt_toolkit.styles import Style
    except Exception:
        return (False, None)

    items = command_palette_dialog_items(lang, display_mode=display_mode, query=query)
    if not items:
        return (False, None)

    style = Style.from_dict(
        {
            "dialog": "bg:#111111",
            "dialog frame.label": "bg:#111111 #66b3ff bold",
            "dialog.body": "bg:#111111 #dddddd",
            "dialog shadow": "bg:#000000",
            "radio": "#bbbbbb",
            "radio-selected": "bg:#0a5ea8 #ffffff bold",
            "button": "bg:#1b1b1b #dddddd",
            "button.focused": "bg:#0a5ea8 #ffffff bold",
        }
    )
    query_text = str(query or "").strip()
    title = "YonerAI / コマンド" if lang == "ja" else "YonerAI / Commands"
    text = (
        _yonerai_open_command_palette_text(lang, query_text)
        if PROMPT_TOOLKIT_MENU_READY
        else (
            f"filter: {query_text}\nChoose with arrows, then press Enter."
            if query_text
            else "Only common short commands are shown first. Choose with arrows, then press Enter."
        )
    )
    try:
        result = radiolist_dialog(
            title=title,
            text=text,
            values=items,
            ok_text="実行" if lang == "ja" else "Run",
            cancel_text="閉じる" if lang == "ja" else "Close",
            style=style,
        )
    except Exception:
        return (False, None)
    try:
        resolved = result.run()
    except Exception:
        return (False, None)
    return (True, resolved if isinstance(resolved, str) and resolved else None)
