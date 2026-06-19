"""YonerAI Romaji Composer tests.

Covers: deterministic offline conversion, composer state machine
(buffer/convert/commit/revert), loopback-only local LLM boundary, cloud
opt-in gate (disabled by default), privacy redaction, and the interactive
slash-command flow (/入力, /変換, /確定, /戻す, /辞書, /文体, /ime).
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = REPO_ROOT / "clients" / "cli"
CORE_SRC = REPO_ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from yonerai_cli.ime.local_enhancer import (
    EnhancerError,
    _NoRedirectHandler,
    enhance_with_local_llm,
    is_loopback_endpoint,
)
from yonerai_cli.ime.romaji_composer import RomajiComposer
from yonerai_cli.ime.romaji_rules import convert_text, convert_token


class _PlainStringIO(io.StringIO):
    def isatty(self) -> bool:
        return False


# --- deterministic romaji rules (offline, no network) ---


def test_basic_romaji_to_kana() -> None:
    assert convert_token("konnichiha") == "こんにちは"
    assert convert_token("arigatou") == "ありがとう"
    assert convert_token("nihongo") == "にほんご"


def test_sokuon_youon_and_n_handling() -> None:
    assert convert_token("kitte") == "きって"
    assert convert_token("kyou") == "きょう"
    assert convert_token("shashin") == "しゃしん"
    assert convert_token("sanpo") == "さんぽ"
    assert convert_token("hon") == "ほん"


def test_punctuation_mapping() -> None:
    assert convert_token("hai,sou.") == "はい、そう。"
    assert convert_token("nani?") == "なに？"


def test_unconvertible_token_returns_none() -> None:
    assert convert_token("xyz123") is None


def test_mixed_japanese_english_paragraph_preserves_english() -> None:
    converted = convert_text("watashi ha YonerAI wo tukau")
    assert "YonerAI" in converted
    assert "わたし" in converted
    assert "つかう" in converted


def test_user_dictionary_overrides_token() -> None:
    converted = convert_text("toukyou ni iku", dictionary={"toukyou": "東京"})
    assert converted.startswith("東京")
    assert "いく" in converted


# --- composer state machine ---


def test_convert_commit_flow() -> None:
    composer = RomajiComposer()
    composer.enable()
    composer.append("konnichiha")
    result = composer.convert()
    assert result["ok"] is True
    assert result["candidate"] == "こんにちは"
    committed = composer.commit()
    assert committed == "こんにちは"
    assert composer.state.raw_buffer == ""
    assert composer.state.converted_candidate is None


def test_revert_restores_romaji_buffer() -> None:
    composer = RomajiComposer()
    composer.enable()
    composer.append("arigatou")
    composer.convert()
    restored = composer.revert()
    assert restored == "arigatou"
    assert composer.state.converted_candidate is None
    assert composer.commit() is None


def test_append_after_conversion_invalidates_candidate() -> None:
    composer = RomajiComposer()
    composer.enable()
    composer.append("konnichiha")
    composer.convert()
    assert composer.state.converted_candidate is not None

    buffer_text = composer.append("sekai")

    assert buffer_text == "konnichiha sekai"
    assert composer.state.converted_candidate is None
    assert composer.commit() is None


def test_convert_empty_buffer_rejected() -> None:
    composer = RomajiComposer()
    result = composer.convert()
    assert result["ok"] is False
    assert result["reason"] == "empty_buffer"


def test_audit_records_are_redacted() -> None:
    composer = RomajiComposer()
    composer.append("himitsu no bunsho")
    composer.convert()
    assert len(composer.state.audit) == 1
    record = composer.state.audit[0]
    assert record["raw_text_included"] is False
    assert record["converted_text_included"] is False
    assert record["provider_mode"] == "deterministic"
    assert record["route"] == "deterministic"
    serialized = json.dumps(record, ensure_ascii=False)
    assert "himitsu" not in serialized
    assert "ひみつ" not in serialized


def test_status_contains_no_raw_text() -> None:
    composer = RomajiComposer()
    composer.append("naisho no naiyou")
    status = composer.status()
    serialized = json.dumps(status, ensure_ascii=False)
    assert "naisho" not in serialized
    assert status["global_os_ime"] is False
    assert status["buffer_chars"] == len("naisho no naiyou")


# --- local LLM enhancer: loopback-only boundary ---


def test_loopback_endpoint_validation() -> None:
    assert is_loopback_endpoint("http://127.0.0.1:8080") is True
    assert is_loopback_endpoint("http://localhost:1234") is True
    assert is_loopback_endpoint("http://[::1]:9000") is True
    assert is_loopback_endpoint("http://192.168.1.5:8080") is False
    assert is_loopback_endpoint("https://api.example.com") is False
    assert is_loopback_endpoint("file:///etc/passwd") is False


def test_enhancer_rejects_non_loopback() -> None:
    with pytest.raises(EnhancerError):
        enhance_with_local_llm("konnichiha", endpoint="https://api.example.com")


def test_composer_rejects_non_loopback_endpoint() -> None:
    composer = RomajiComposer()
    with pytest.raises(ValueError):
        composer.set_local_llm_endpoint("https://api.example.com")


def test_loopback_request_opener_disables_proxies_and_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_handlers: list[Any] = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": "安全"}}]}).encode("utf-8")

    class FakeOpener:
        def open(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
            assert request.full_url == "http://127.0.0.1:8080/v1/chat/completions"
            assert timeout == 20.0
            return FakeResponse()

    def fake_build_opener(*handlers: Any) -> FakeOpener:
        captured_handlers.extend(handlers)
        return FakeOpener()

    monkeypatch.setenv("HTTP_PROXY", "http://192.0.2.10:8888")
    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)
    result = enhance_with_local_llm("himitsu", endpoint="http://127.0.0.1:8080")

    assert result == "安全"
    proxy_handlers = [handler for handler in captured_handlers if isinstance(handler, urllib.request.ProxyHandler)]
    assert len(proxy_handlers) == 1
    assert proxy_handlers[0].proxies == {}
    assert any(isinstance(handler, _NoRedirectHandler) for handler in captured_handlers)


def test_loopback_request_opener_rejects_redirects() -> None:
    request = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", method="POST")
    handler = _NoRedirectHandler()

    redirected = handler.redirect_request(
        request,
        fp=None,
        code=302,
        msg="Found",
        headers={},
        newurl="https://api.example.com/collect",
    )

    assert redirected is None


def test_local_llm_enhancement_with_fake_transport() -> None:
    def fake_transport(request: urllib.request.Request, timeout: float) -> bytes:
        assert request.full_url.startswith("http://127.0.0.1:")
        return json.dumps(
            {"choices": [{"message": {"content": "こんにちは、世界。"}}]}
        ).encode("utf-8")

    composer = RomajiComposer(transport=fake_transport)
    composer.set_local_llm_endpoint("http://127.0.0.1:8080")
    composer.set_provider_mode("local_llm")
    composer.append("konnichiha, sekai.")
    result = composer.convert()
    assert result["ok"] is True
    assert result["candidate"] == "こんにちは、世界。"
    assert result["route"] == "local_llm_loopback"


def test_local_llm_failure_falls_back_to_deterministic() -> None:
    def failing_transport(request: urllib.request.Request, timeout: float) -> bytes:
        raise OSError("connection refused")

    composer = RomajiComposer(transport=failing_transport)
    composer.set_local_llm_endpoint("http://127.0.0.1:8080")
    composer.set_provider_mode("local_llm")
    composer.append("konnichiha")
    result = composer.convert()
    assert result["ok"] is True
    assert result["candidate"] == "こんにちは"
    assert result["route"] == "deterministic"
    assert "fallback" in str(result["notice"])


def test_local_llm_skips_sensitive_buffer_before_transport() -> None:
    calls: list[str] = []

    def fake_transport(request: urllib.request.Request, timeout: float) -> bytes:
        calls.append(request.full_url)
        return json.dumps({"choices": [{"message": {"content": "should not run"}}]}).encode("utf-8")

    composer = RomajiComposer(transport=fake_transport)
    composer.set_local_llm_endpoint("http://127.0.0.1:8080")
    composer.set_provider_mode("local_llm")
    composer.append("C:\\Users\\owner\\secret.txt")

    result = composer.convert()

    assert calls == []
    assert result["route"] == "deterministic"
    assert "sensitive marker" in str(result["notice"])


# --- cloud gate: disabled by default ---


def test_cloud_mode_requires_explicit_opt_in() -> None:
    composer = RomajiComposer()
    with pytest.raises(PermissionError):
        composer.set_provider_mode("cloud_opt_in")
    composer.confirm_cloud_opt_in()
    composer.set_provider_mode("cloud_opt_in")
    composer.append("konnichiha")
    result = composer.convert()
    assert result["ok"] is True
    assert "contract-only" in str(result["notice"])


def test_default_mode_is_deterministic_offline() -> None:
    composer = RomajiComposer()
    assert composer.state.provider_mode == "deterministic"
    assert composer.state.cloud_opt_in_confirmed is False


# --- interactive command flow ---


def _interactive_modules():
    from yonerai_cli.config import DEFAULT_CONFIG, save_cli_config
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    return DEFAULT_CONFIG, save_cli_config, InteractiveCallbacks, InteractiveOptions, run_interactive_cli


def _run_interactive(tmp_path: Path, script: str, *, lang: str = "ja") -> tuple[str, list[str]]:
    DEFAULT_CONFIG, save_cli_config, InteractiveCallbacks, InteractiveOptions, run_interactive_cli = (
        _interactive_modules()
    )
    config_path = tmp_path / "cli-config.json"
    config = dict(DEFAULT_CONFIG)
    config["language"] = lang
    save_cli_config(config, config_path)
    sent_tasks: list[str] = []

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(task: str, provider: str, live: bool, ledger_path: str | None, lang: str) -> dict[str, Any]:
        sent_tasks.append(task)
        return {
            "ok": True,
            "run": {"id": "run_ime_test"},
            "response": {"output_text": f"received {task}"},
            "auto": {"provider": provider, "route": "mock"},
            "live_call_performed": live,
            "ledger": {"path": ledger_path, "enabled": bool(ledger_path)},
        }

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), provider="mock", script=True, color="never"),
        InteractiveCallbacks(providers=providers, ask_auto=ask_auto, runs_list=runs_list, runs_show=runs_show),
        stdin=_PlainStringIO(script),
        stdout=stdout,
    )
    assert rc == 0
    return stdout.getvalue(), sent_tasks


def test_interactive_composer_full_flow_japanese(tmp_path: Path) -> None:
    output, sent_tasks = _run_interactive(
        tmp_path,
        "/入力 on\nkonnichiha\n/変換\n/確定\n/入力 off\n/quit\n",
    )
    assert "ローマ字コンポーザー: オン" in output
    assert "こんにちは" in output
    assert sent_tasks == ["こんにちは"]
    assert "ローマ字コンポーザー: オフ" in output


def test_interactive_typing_does_not_send_while_composing(tmp_path: Path) -> None:
    output, sent_tasks = _run_interactive(
        tmp_path,
        "/ime on\nkonnichiha\nsekai\n/quit\n",
    )
    assert sent_tasks == []
    assert "バッファ" in output


def test_interactive_revert_restores_buffer(tmp_path: Path) -> None:
    output, sent_tasks = _run_interactive(
        tmp_path,
        "/入力 on\narigatou\n/変換\n/戻す\n/quit\n",
    )
    assert sent_tasks == []
    assert "ありがとう" in output
    assert "ローマ字バッファを復元しました" in output


def test_interactive_dictionary_and_style(tmp_path: Path) -> None:
    output, sent_tasks = _run_interactive(
        tmp_path,
        "/入力 on\n/辞書 add toukyou=東京\ntoukyou ni iku\n/変換\n/確定\n/文体 ですます調\n/quit\n",
    )
    assert "辞書に追加しました" in output
    assert sent_tasks and sent_tasks[0].startswith("東京")
    assert "文体を設定しました" in output


def test_interactive_dictionary_preserves_add_prefix_keys(tmp_path: Path) -> None:
    output, sent_tasks = _run_interactive(
        tmp_path,
        "/ime on\n/dict add address=住所\naddress\n/convert\n/commit\n/quit\n",
        lang="en",
    )
    assert "Dictionary entry added." in output
    assert sent_tasks == ["住所"]


def test_interactive_ime_status_and_cloud_gate(tmp_path: Path) -> None:
    output, sent_tasks = _run_interactive(
        tmp_path,
        "/ime status\n/ime cloud on\n/quit\n",
    )
    assert "ローマ字コンポーザー状態" in output
    assert "YonerAI CLI 内の入力補助です" in output
    assert "クラウド変換の注意" in output
    assert "/ime cloud on confirm" in output
    assert sent_tasks == []


def test_interactive_disabled_composer_passes_text_through(tmp_path: Path) -> None:
    output, sent_tasks = _run_interactive(tmp_path, "konnichiha\n/quit\n")
    assert sent_tasks == ["konnichiha"]


def test_no_secrets_or_paths_in_output(tmp_path: Path) -> None:
    output, _ = _run_interactive(
        tmp_path,
        "/入力 on\nhimitsu no memo\n/変換\n/ime status\n/quit\n",
    )
    assert str(tmp_path) not in output
    assert "sk-" not in output
    assert "Traceback" not in output
