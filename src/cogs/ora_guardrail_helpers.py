from __future__ import annotations

import json
from collections.abc import Callable

from .ora_pure_helpers import extract_json_objects

JsonExtractor = Callable[[str], list[str]]
GuardrailDecision = dict[str, object]


def interpret_guardrail_response(
    content: object,
    *,
    json_extractor: JsonExtractor = extract_json_objects,
) -> GuardrailDecision:
    """Interpret the legacy ORA guardrail model response without runtime side effects."""
    text = "" if content is None else str(content)
    if text:
        json_objects = json_extractor(text)
        if json_objects:
            try:
                return json.loads(json_objects[0])
            except Exception:
                pass

        if '"safe": false' in text.lower():
            return {"safe": False, "reason": "Keyword detected"}

    return {"safe": True, "reason": "Pass"}


def guardrail_response_interpreter_status() -> dict[str, object]:
    sample = interpret_guardrail_response('{"safe": false, "reason": "fixture"}')
    return {
        "name": "ora_guardrail_response_interpreter",
        "source": "src/cogs/ora_guardrail_helpers.py",
        "status": "ok" if sample == {"safe": False, "reason": "fixture"} else "unavailable",
        "available": sample == {"safe": False, "reason": "fixture"},
        "provider_call_performed": False,
        "broad_ora_refactor": False,
    }


__all__ = [
    "guardrail_response_interpreter_status",
    "interpret_guardrail_response",
]
