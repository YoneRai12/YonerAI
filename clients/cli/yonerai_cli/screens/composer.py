from __future__ import annotations

from typing import Any, TextIO

from yonerai_cli.ime import RomajiComposer
from yonerai_cli.ime.privacy import cloud_privacy_wording
from yonerai_cli.screens.labels import _agent_mode_label, _provider_label, _safe
from yonerai_cli.tui.aliases import canonical_value as _canonical_value

_COMMON_COMMANDS_JA = (
    "/ログイン",
    "/ローカルLLM",
    "/更新",
    "/設定",
)
_COMMON_COMMANDS_EN = (
    "/login",
    "/local-llm",
    "/update",
    "/settings",
)


def _write(stream: TextIO, text: str) -> None:
    stream.write(text)
    stream.flush()


def format_input_composer(
    *,
    lang: str,
    config: dict[str, object],
    provider: str,
    live: bool,
) -> str:
    model = _safe(config.get("model_preference") or "auto")
    mode = _agent_mode_label(config.get("agent_mode") or "plan_readonly", lang=lang)
    display_mode = str(config.get("command_display_mode") or ("ja_with_en" if lang == "ja" else "en_with_ja"))
    if lang == "ja":
        return "\n".join(
            (
                "入力欄",
                "  そのまま入力して会話します。/ で候補、Esc で閉じる、Enter で送信。",
                f"  接続: {_provider_label(provider, lang='ja')} / モデル: {model} / モード: {mode}",
                f"  記憶: {'オン' if bool(config.get('memory_enabled')) else 'オフ'} / 外部live: {'オン（明示時のみ）' if live else 'オフ（既定）'}",
                "  よく使う: "
                + " ・ ".join(
                    _display_common_command(command, lang=lang, mode=display_mode)
                    for command in _COMMON_COMMANDS_JA
                ),
                "  境界: shellなし / ワークスペース外ファイルなし / key表示なし / private自動uploadなし",
                "",
            )
        )
    return "\n".join(
        (
            "Input composer",
            "  Talk normally. / opens commands, Esc closes, Enter sends.",
            f"  connection: {_provider_label(provider, lang='en')} / model: {model} / mode: {mode}",
            f"  live: {'on explicit' if live else 'off by default'} / memory: {'on' if bool(config.get('memory_enabled')) else 'off'}",
            "  shortcuts: "
            + " · ".join(
                _display_common_command(command, lang=lang, mode=display_mode)
                for command in _COMMON_COMMANDS_EN
            ),
            "  boundaries: no shell / no outside-workspace files / no key output / no private auto-upload",
            "",
        )
    )


def composer_capability_summary(*, lang: str, config: dict[str, object]) -> dict[str, Any]:
    return {
        "ok": True,
        "lang": lang,
        "slash_completion": True,
        "plain_fallback": True,
        "agent_mentions": ["planner", "reviewer", "researcher", "implementer", "tester"],
        "live_provider_enabled": bool(config.get("live_provider_enabled")),
        "memory_enabled": bool(config.get("memory_enabled")),
        "actions_not_performed": [
            "no shell execution",
            "no workspace file auto-read",
            "no provider key output",
            "no cloud upload",
        ],
    }


_COMPOSER_MESSAGES: dict[str, dict[str, str]] = {
    "enabled": {
        "ja": "ローマ字コンポーザー: オン。文はバッファに溜まります。/convert と /commit で送信できます。/input off で解除します。\n",
        "en": "Romaji composer: on. Text is buffered; use /convert then /commit to send. /input off to disable.\n",
    },
    "disabled": {
        "ja": "ローマ字コンポーザー: オフ。通常入力に戻りました。\n",
        "en": "Romaji composer: off. Back to normal input.\n",
    },
    "empty": {
        "ja": "バッファが空です。先にローマ字で入力してください。\n",
        "en": "Buffer is empty. Type romaji text first.\n",
    },
    "candidate": {"ja": "変換候補:", "en": "Conversion candidate:"},
    "next_steps": {"ja": "  /commit で送信、/revert でローマ字へ戻します", "en": "  /commit to send, /revert to restore romaji"},
    "no_candidate": {
        "ja": "変換候補がありません。先に /convert を実行してください。\n",
        "en": "No candidate. Run /convert first.\n",
    },
    "committed": {"ja": "送信テキストを確定しました。続けて送信します。\n", "en": "Committed. Sending.\n"},
    "nothing_to_revert": {"ja": "戻せる変換がありません。\n", "en": "Nothing to revert.\n"},
    "reverted": {"ja": "変換を戻し、ローマ字バッファを復元しました。\n", "en": "Conversion undone; romaji buffer restored.\n"},
    "dict_added": {"ja": "辞書に追加しました。\n", "en": "Dictionary entry added.\n"},
    "dict_invalid": {"ja": "形式: /dict add tokyo=東京\n", "en": "Format: /dict add tokyo=東京\n"},
    "dict_empty": {"ja": "辞書は空です。/dict add tokyo=東京 で追加できます。\n", "en": "Dictionary is empty. Add with /dict add tokyo=東京.\n"},
    "dict_list": {"ja": "辞書:", "en": "Dictionary:"},
    "style_set": {"ja": "文体を設定しました。\n", "en": "Style profile set.\n"},
    "cloud_needs_confirm": {
        "ja": "クラウド変換は既定でオフです。説明を確認したうえで /ime cloud on confirm で明示有効化してください。\n",
        "en": "Cloud conversion is disabled by default. Review the notice, then enable with /ime cloud on confirm.\n",
    },
    "cloud_enabled": {
        "ja": "クラウド変換の opt-in を記録しました。この build では contract-only です。\n",
        "en": "Cloud opt-in recorded (contract-only in this build).\n",
    },
    "cloud_disabled": {"ja": "クラウド変換をオフにしました。\n", "en": "Cloud conversion disabled.\n"},
    "endpoint_set": {
        "ja": "ローカルLLM endpoint を設定しました（loopback のみ）。\n",
        "en": "Local LLM endpoint set (loopback only).\n",
    },
    "endpoint_invalid": {
        "ja": "endpoint は localhost / 127.0.0.1 / ::1 のみ設定できます。\n",
        "en": "Endpoint must be localhost / 127.0.0.1 / ::1 only.\n",
    },
    "mode_set": {"ja": "変換モードを設定しました。\n", "en": "Provider mode set.\n"},
    "mode_invalid": {
        "ja": "モードは deterministic / local_llm のどちらかです。cloud は /ime cloud on confirm で明示有効化します。\n",
        "en": "Mode must be deterministic or local_llm (cloud via /ime cloud on confirm).\n",
    },
    "ime_help": {
        "ja": "使い方: /ime on|off|status ・ /ime mode <deterministic|local_llm> ・ /ime endpoint <loopback URL> ・ /ime cloud on confirm|off\n",
        "en": "Usage: /ime on|off|status · /ime mode <deterministic|local_llm> · /ime endpoint <loopback URL> · /ime cloud on confirm|off\n",
    },
}


def _composer_msg(lang: str, key: str) -> str:
    entry = _COMPOSER_MESSAGES.get(key, {})
    return entry.get(lang if lang == "ja" else "en", "")


def _composer_buffer_preview(buffer_text: str, lang: str) -> str:
    label = "バッファ" if lang == "ja" else "buffer"
    hint = "/convert で日本語にできます" if lang == "ja" else "use /convert to convert"
    suffix = "文字" if lang == "ja" else "chars"
    return f"[{label} {len(buffer_text)}{suffix}] {buffer_text}\n  ({hint})\n"


def _display_common_command(command: str, *, lang: str, mode: str) -> str:
    pair_map = {
        "/ログイン": "/login",
        "/ローカルLLM": "/local-llm",
        "/更新": "/update",
        "/設定": "/settings",
    }
    english = pair_map.get(command, command)
    japanese = next((ja for ja, en in pair_map.items() if en == command), command)
    if lang == "ja":
        if mode == "ja_only":
            return japanese
        return f"{japanese} ({english})"
    if mode == "en_only":
        return english
    return f"{english} ({japanese})"


def _format_composer_status(status: dict[str, object], lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "ローマ字コンポーザー状態",
                f"  有効: {'オン' if status.get('composer_enabled') else 'オフ'}",
                f"  変換モード: {status.get('provider_mode')}",
                f"  ローカルLLM endpoint: {'設定済み（loopback）' if status.get('local_llm_endpoint_set') else '未設定'}",
                f"  文体: {status.get('style_profile')}",
                f"  辞書項目数: {status.get('dictionary_entries')}",
                f"  バッファ文字数: {status.get('buffer_chars')}",
                f"  変換候補: {'あり' if status.get('candidate_ready') else 'なし'}",
                f"  クラウド opt-in: {'確認済み' if status.get('cloud_opt_in_confirmed') else '未確認（既定オフ）'}",
                "  補足: これは OS 全体の IME ではなく、YonerAI CLI 内の入力補助です。",
                "",
            )
        )
    return "\n".join(
        (
            "Romaji composer status",
            f"  enabled: {status.get('composer_enabled')}",
            f"  provider_mode: {status.get('provider_mode')}",
            f"  local_llm_endpoint_set: {status.get('local_llm_endpoint_set')}",
            f"  style_profile: {status.get('style_profile')}",
            f"  dictionary_entries: {status.get('dictionary_entries')}",
            f"  buffer_chars: {status.get('buffer_chars')}",
            f"  candidate_ready: {status.get('candidate_ready')}",
            f"  cloud_opt_in_confirmed: {status.get('cloud_opt_in_confirmed')}",
            "  note: this is a CLI-local composer, not a global OS IME.",
            "",
        )
    )


def _handle_ime_command(
    args: list[str],
    *,
    composer: RomajiComposer,
    lang: str,
    output_stream: TextIO,
) -> dict[str, object]:
    if not args or _canonical_value(args[0]) == "status":
        _write(output_stream, _format_composer_status(composer.status(), lang))
        return {}
    head = _canonical_value(args[0])
    if head == "on":
        composer.enable()
        _write(output_stream, _composer_msg(lang, "enabled"))
        return {}
    if head == "off":
        composer.disable()
        _write(output_stream, _composer_msg(lang, "disabled"))
        return {}
    if head == "mode" and len(args) >= 2:
        mode = args[1].strip().lower()
        if mode not in {"deterministic", "local_llm"}:
            _write(output_stream, _composer_msg(lang, "mode_invalid"))
            return {}
        composer.set_provider_mode(mode)
        _write(output_stream, _composer_msg(lang, "mode_set"))
        return {}
    if head == "endpoint" and len(args) >= 2:
        try:
            composer.set_local_llm_endpoint(args[1].strip())
        except ValueError:
            _write(output_stream, _composer_msg(lang, "endpoint_invalid"))
            return {}
        _write(output_stream, _composer_msg(lang, "endpoint_set"))
        return {}
    if head == "cloud" and len(args) >= 2:
        action = _canonical_value(args[1])
        if action == "off":
            composer.state.cloud_opt_in_confirmed = False
            if composer.state.provider_mode == "cloud_opt_in":
                composer.set_provider_mode("deterministic")
            _write(output_stream, _composer_msg(lang, "cloud_disabled"))
            return {}
        if action == "on":
            confirmed = len(args) >= 3 and args[2].strip().lower() == "confirm"
            _write(output_stream, cloud_privacy_wording(lang) + "\n")
            if not confirmed:
                _write(output_stream, _composer_msg(lang, "cloud_needs_confirm"))
                return {}
            composer.confirm_cloud_opt_in()
            composer.set_provider_mode("cloud_opt_in")
            _write(output_stream, _composer_msg(lang, "cloud_enabled"))
            return {}
    _write(output_stream, _composer_msg(lang, "ime_help"))
    return {}


def _handle_composer_command(
    command: str,
    args: list[str],
    *,
    composer: RomajiComposer,
    lang: str,
    output_stream: TextIO,
) -> dict[str, object]:
    if command == "/convert":
        result = composer.convert()
        if not result.get("ok"):
            _write(output_stream, _composer_msg(lang, "empty"))
            return {}
        notice = str(result.get("notice") or "")
        candidate = str(result.get("candidate"))
        lines = [_composer_msg(lang, "candidate"), f"  {candidate}"]
        if notice:
            lines.append(f"  ({notice})")
        lines.append(_composer_msg(lang, "next_steps"))
        _write(output_stream, "\n".join(lines) + "\n")
        return {}
    if command == "/commit":
        committed = composer.commit()
        if committed is None:
            _write(output_stream, _composer_msg(lang, "no_candidate"))
            return {}
        _write(output_stream, _composer_msg(lang, "committed"))
        return {"send_text": committed}
    if command == "/revert":
        restored = composer.revert()
        if restored is None:
            _write(output_stream, _composer_msg(lang, "nothing_to_revert"))
            return {}
        _write(output_stream, _composer_msg(lang, "reverted"))
        _write(output_stream, _composer_buffer_preview(restored, lang))
        return {}
    if command == "/dict":
        dict_args = list(args)
        if dict_args and _canonical_value(dict_args[0]) == "add":
            dict_args.pop(0)
        joined = " ".join(dict_args)
        if "=" in joined:
            romaji, _, japanese = joined.partition("=")
            romaji = romaji.strip()
            try:
                composer.add_dictionary_entry(romaji, japanese)
            except ValueError:
                _write(output_stream, _composer_msg(lang, "dict_invalid"))
                return {}
            _write(output_stream, _composer_msg(lang, "dict_added"))
            return {}
        entries = composer.state.user_dictionary
        if not entries:
            _write(output_stream, _composer_msg(lang, "dict_empty"))
            return {}
        body = "\n".join(f"  {romaji} -> {japanese}" for romaji, japanese in sorted(entries.items()))
        _write(output_stream, _composer_msg(lang, "dict_list") + "\n" + body + "\n")
        return {}
    if args:
        composer.set_style_profile(" ".join(args))
        _write(output_stream, _composer_msg(lang, "style_set"))
    else:
        current = composer.state.style_profile or ("未設定" if lang == "ja" else "not set")
        label = "文体" if lang == "ja" else "style"
        _write(output_stream, f"{label}: {current}\n")
    return {}
