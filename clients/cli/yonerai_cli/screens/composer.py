from __future__ import annotations

from typing import Any, TextIO

from yonerai_cli.ime import RomajiComposer
from yonerai_cli.ime.privacy import cloud_privacy_wording
from yonerai_cli.screens.labels import _agent_mode_label, _provider_label, _safe
from yonerai_cli.tui.aliases import canonical_value as _canonical_value


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
    if lang == "ja":
        return "\n".join(
            (
                "入力欄",
                "  そのまま日本語で質問を書くと ask --auto 経路で実行します。",
                "  / を入力すると候補が出ます。候補が出ない端末では /コマンド と /選択 を使います。",
                "  Enterで送信。Tab/矢印: 利用できる端末では補完候補の移動に使います。",
                "",
                "今の入力状態",
                f"  提供元（AI接続先）: {_provider_label(provider, lang='ja')}",
                f"  モデル（AIモデル）: {model}",
                f"  作業モード: {mode}",
                f"  ライブ接続: {'オン（明示許可）' if live else 'オフ（初期値）'}",
                f"  記憶: {'オン' if bool(config.get('memory_enabled')) else 'オフ'} / raw内容は表示・送信しません",
                "",
                "使えるショートカット",
                "  /設定        設定カテゴリ",
                "  /モデル      PC内モデル/モデル選択",
                "  /提供元      AI接続元の状態",
                "  /安全        安全境界",
                "  /履歴        実行履歴",
                "  /コンテキスト 参照できる文脈",
                "  @planner / @reviewer / @researcher / @implementer / @tester",
                "",
                "禁止していること",
                "  任意shell実行なし / workspace外ファイル読み取りなし / provider key表示なし",
                "  local private memory の自動uploadなし / production Oracle・cloud実行なし",
                "",
            )
        )
    return "\n".join(
        (
            "Input composer",
            "  Type a normal message to run through ask --auto.",
            "  Type / for suggestions. If completion is unavailable, use /palette and /select.",
            "  Tab/arrows: used for completion when the terminal supports it.",
            "",
            "Current input state",
            f"  provider: {_safe(provider)}",
            f"  model: {model}",
            f"  agent_mode: {mode}",
            f"  live: {'on explicit' if live else 'off by default'}",
            f"  memory: {'on' if bool(config.get('memory_enabled')) else 'off'} / raw content is not shown or sent",
            "",
            "Shortcuts",
            "  /settings /models /providers /safety /runs /context",
            "  @planner / @reviewer / @researcher / @implementer / @tester",
            "",
            "Boundaries",
            "  no arbitrary shell, no files outside workspace, no provider key output",
            "  no local private memory auto-upload, no production Oracle/cloud runtime",
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
        "ja": "ローマ字コンポーザー: オン。文章はバッファに溜まり、/変換 → /確定 で送信します。/入力 off で解除。\n",
        "en": "Romaji composer: on. Text is buffered; use /convert then /commit to send. /input off to disable.\n",
    },
    "disabled": {
        "ja": "ローマ字コンポーザー: オフ。通常入力に戻りました。\n",
        "en": "Romaji composer: off. Back to normal input.\n",
    },
    "empty": {"ja": "バッファが空です。先にローマ字で文章を入力してください。\n", "en": "Buffer is empty. Type romaji text first.\n"},
    "candidate": {"ja": "変換候補:", "en": "Conversion candidate:"},
    "next_steps": {"ja": "  /確定 で送信、/戻す でローマ字に戻す", "en": "  /commit to send, /revert to restore romaji"},
    "no_candidate": {"ja": "変換候補がありません。先に /変換 してください。\n", "en": "No candidate. Run /convert first.\n"},
    "committed": {"ja": "確定しました。送信します。\n", "en": "Committed. Sending.\n"},
    "nothing_to_revert": {"ja": "戻せる変換がありません。\n", "en": "Nothing to revert.\n"},
    "reverted": {"ja": "変換を取り消し、ローマ字バッファに戻しました。\n", "en": "Conversion undone; romaji buffer restored.\n"},
    "dict_added": {"ja": "辞書に追加しました。\n", "en": "Dictionary entry added.\n"},
    "dict_invalid": {"ja": "形式: /辞書 add tokyo=東京\n", "en": "Format: /dict add tokyo=東京\n"},
    "dict_empty": {"ja": "辞書は空です。/辞書 add tokyo=東京 で追加できます。\n", "en": "Dictionary is empty. Add with /dict add tokyo=東京.\n"},
    "dict_list": {"ja": "辞書:", "en": "Dictionary:"},
    "style_set": {"ja": "文体を設定しました。\n", "en": "Style profile set.\n"},
    "cloud_needs_confirm": {
        "ja": "クラウド変換は既定でオフです。文言を確認のうえ /ime cloud on confirm で有効化してください。\n",
        "en": "Cloud conversion is disabled by default. Review the notice, then enable with /ime cloud on confirm.\n",
    },
    "cloud_enabled": {"ja": "クラウド変換 opt-in を記録しました（この build では contract-only）。\n", "en": "Cloud opt-in recorded (contract-only in this build).\n"},
    "cloud_disabled": {"ja": "クラウド変換をオフにしました。\n", "en": "Cloud conversion disabled.\n"},
    "endpoint_set": {"ja": "ローカルLLMエンドポイントを設定しました（loopback限定）。\n", "en": "Local LLM endpoint set (loopback only).\n"},
    "endpoint_invalid": {
        "ja": "エンドポイントは localhost / 127.0.0.1 / ::1 のみ許可です。\n",
        "en": "Endpoint must be localhost / 127.0.0.1 / ::1 only.\n",
    },
    "mode_set": {"ja": "変換モードを設定しました。\n", "en": "Provider mode set.\n"},
    "mode_invalid": {
        "ja": "モードは deterministic / local_llm のいずれかです（cloud は /ime cloud on confirm）。\n",
        "en": "Mode must be deterministic or local_llm (cloud via /ime cloud on confirm).\n",
    },
    "ime_help": {
        "ja": "使い方: /ime on|off|status / /ime mode <deterministic|local_llm> / /ime endpoint <loopback URL> / /ime cloud on confirm|off\n",
        "en": "Usage: /ime on|off|status / /ime mode <deterministic|local_llm> / /ime endpoint <loopback URL> / /ime cloud on confirm|off\n",
    },
}


def _composer_msg(lang: str, key: str) -> str:
    entry = _COMPOSER_MESSAGES.get(key, {})
    return entry.get(lang if lang == "ja" else "en", "")


def _composer_buffer_preview(buffer_text: str, lang: str) -> str:
    label = "バッファ" if lang == "ja" else "buffer"
    hint = "/変換 で日本語にできます" if lang == "ja" else "use /convert to convert"
    return f"[{label} {len(buffer_text)}字] {buffer_text}\n  ({hint})\n"


def _format_composer_status(status: dict[str, object], lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "ローマ字コンポーザー状態",
                f"  有効: {'オン' if status.get('composer_enabled') else 'オフ'}",
                f"  変換モード: {status.get('provider_mode')}",
                f"  ローカルLLM endpoint: {'設定済（loopback）' if status.get('local_llm_endpoint_set') else '未設定'}",
                f"  文体: {status.get('style_profile')}",
                f"  辞書件数: {status.get('dictionary_entries')}",
                f"  バッファ文字数: {status.get('buffer_chars')}",
                f"  変換候補: {'あり' if status.get('candidate_ready') else 'なし'}",
                f"  クラウドopt-in: {'確認済' if status.get('cloud_opt_in_confirmed') else '未確認（既定オフ）'}",
                "  注意: これはOS全体のIMEではなく、YonerAI CLI内だけの入力支援です。",
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


# Slash-command handlers for the composer (/convert /commit /revert /dict /style).
# Kept here (not in interactive.py) so the interactive shell stays a thin
# dispatcher per the screen-module architecture rule.
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
    # /style
    if args:
        composer.set_style_profile(" ".join(args))
        _write(output_stream, _composer_msg(lang, "style_set"))
    else:
        current = composer.state.style_profile or ("未設定" if lang == "ja" else "not set")
        label = "文体" if lang == "ja" else "style"
        _write(output_stream, f"{label}: {current}\n")
    return {}
