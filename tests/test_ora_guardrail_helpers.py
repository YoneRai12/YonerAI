from __future__ import annotations

import importlib
import sys


def test_guardrail_response_interpreter_prefers_recovered_json() -> None:
    from src.cogs.ora_guardrail_helpers import interpret_guardrail_response

    decision = interpret_guardrail_response('prefix {"safe": false, "reason": "loop"} suffix')

    assert decision == {"safe": False, "reason": "loop"}


def test_guardrail_response_interpreter_keeps_legacy_keyword_fallback() -> None:
    from src.cogs.ora_guardrail_helpers import interpret_guardrail_response

    decision = interpret_guardrail_response('model text says "safe": false but not valid json')

    assert decision == {"safe": False, "reason": "Keyword detected"}


def test_guardrail_response_interpreter_keeps_pass_fallback() -> None:
    from src.cogs.ora_guardrail_helpers import interpret_guardrail_response

    assert interpret_guardrail_response(None) == {"safe": True, "reason": "Pass"}
    assert interpret_guardrail_response("not json") == {"safe": True, "reason": "Pass"}


def test_guardrail_response_interpreter_preserves_wrapper_json_extractor() -> None:
    from src.cogs.ora_guardrail_helpers import interpret_guardrail_response

    calls: list[str] = []

    def extractor(text: str) -> list[str]:
        calls.append(text)
        return ['{"safe": true, "reason": "custom"}']

    decision = interpret_guardrail_response("custom content", json_extractor=extractor)

    assert decision == {"safe": True, "reason": "custom"}
    assert calls == ["custom content"]


def test_guardrail_response_interpreter_status_is_public_safe() -> None:
    from src.cogs.ora_guardrail_helpers import guardrail_response_interpreter_status

    status = guardrail_response_interpreter_status()

    assert status == {
        "name": "ora_guardrail_response_interpreter",
        "source": "src/cogs/ora_guardrail_helpers.py",
        "status": "ok",
        "available": True,
        "provider_call_performed": False,
        "broad_ora_refactor": False,
    }


def test_guardrail_helper_import_does_not_load_discord_runtime() -> None:
    removed = {
        name: sys.modules.pop(name)
        for name in list(sys.modules)
        if name == "discord"
        or name.startswith("discord.")
        or name in {"src.cogs.ora_guardrail_helpers", "src.cogs.ora_pure_helpers"}
    }
    try:
        importlib.import_module("src.cogs.ora_guardrail_helpers")
        loaded = {name for name in sys.modules if name == "discord" or name.startswith("discord.")}
    finally:
        sys.modules.update(removed)

    assert loaded == set()
