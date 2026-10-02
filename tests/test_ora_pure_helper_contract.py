from __future__ import annotations

import ast
from pathlib import Path

from src.cogs.ora_pure_helpers import (
    clean_content,
    detect_spam,
    extract_json_objects,
    is_input_spam,
    strip_route_json,
)


def _build_ora_helper_fixture():
    source_path = Path(__file__).resolve().parents[1] / "src" / "cogs" / "ora.py"
    source = source_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    ora_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ORACog")
    helper_names = {
        "_clean_content",
        "_detect_spam",
        "_extract_json_objects",
        "_is_input_spam",
        "_strip_route_json",
    }
    helper_methods = [
        node for node in ora_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in helper_names
    ]
    assert {node.name for node in helper_methods} == helper_names

    module = ast.Module(
        body=[
            ast.Import(names=[ast.alias(name="logging")]),
            ast.Assign(
                targets=[ast.Name(id="logger", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id="logging", ctx=ast.Load()), attr="getLogger", ctx=ast.Load()),
                    args=[ast.Constant(value=__name__)],
                    keywords=[],
                ),
            ),
            ast.ClassDef(
                name="OraHelperFixture",
                bases=[],
                keywords=[],
                body=helper_methods,
                decorator_list=[],
            ),
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)

    namespace: dict[str, object] = {
        "clean_content": clean_content,
        "clean_ora_content": clean_content,
        "detect_ora_spam": detect_spam,
        "extract_ora_json_objects": extract_json_objects,
        "is_ora_input_spam": is_input_spam,
        "strip_ora_route_json": strip_route_json,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["OraHelperFixture"]()


def test_ora_pure_spam_helpers_are_deterministic_without_discord_runtime() -> None:
    helpers = _build_ora_helper_fixture()

    assert detect_spam("short") is False
    assert detect_spam("a" * 600) is True
    assert is_input_spam("please repeat this 10000 times") is True
    assert is_input_spam("a normal short request") is False
    assert helpers._detect_spam("a" * 600) == detect_spam("a" * 600)
    assert helpers._is_input_spam("a normal short request") == is_input_spam("a normal short request")


def test_ora_pure_json_helpers_handle_tool_calls_and_route_blocks() -> None:
    helpers = _build_ora_helper_fixture()

    recovered = extract_json_objects('[TOOL_CALLS] search ARGS {"query": "yonerai"}')
    assert recovered == ['{"tool": "search", "args": {"query": "yonerai"}}']
    assert helpers._extract_json_objects('[TOOL_CALLS] search ARGS {"query": "yonerai"}') == recovered

    recovered_with_brace = extract_json_objects('[TOOL_CALLS] search ARGS {"query": "brace } inside"}')
    assert recovered_with_brace == ['{"tool": "search", "args": {"query": "brace } inside"}}']

    malformed_tool_call = '[TOOL_CALLS] search ARGS oops {"safe": false}'
    assert extract_json_objects(malformed_tool_call) == ['{"safe": false}']

    route_payload = '{"route_eval": {"route": "internal"}, "visible": false}'
    visible_payload = '{"visible": true}'
    brace_payload = '{"message": "brace } inside", "ok": true}'
    assert extract_json_objects(f"{route_payload}\n{visible_payload}\n{brace_payload}") == [visible_payload, brace_payload]

    content = f"before {visible_payload} middle {route_payload} after"
    assert strip_route_json(content) == f"before {visible_payload} middle  after"
    assert helpers._strip_route_json(content) == strip_route_json(content)


def test_ora_pure_content_cleaner_removes_internal_channel_tags() -> None:
    helpers = _build_ora_helper_fixture()

    assert helpers._clean_content("<|analysis|>hidden<|final|> visible ") == "hidden visible"
    assert clean_content("<|analysis|>hidden<|final|> visible ") == helpers._clean_content(
        "<|analysis|>hidden<|final|> visible "
    )
