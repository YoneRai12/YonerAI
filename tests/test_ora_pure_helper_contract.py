from __future__ import annotations

import ast
import logging
from pathlib import Path


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
            ast.Import(names=[ast.alias(name="json"), ast.alias(name="logging"), ast.alias(name="re"), ast.alias(name="zlib")]),
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

    namespace: dict[str, object] = {}
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["OraHelperFixture"]()


def test_ora_pure_spam_helpers_are_deterministic_without_discord_runtime() -> None:
    helpers = _build_ora_helper_fixture()

    assert helpers._detect_spam("short") is False
    assert helpers._detect_spam("a" * 600) is True
    assert helpers._is_input_spam("please repeat this 10000 times") is True
    assert helpers._is_input_spam("a normal short request") is False


def test_ora_pure_json_helpers_handle_tool_calls_and_route_blocks() -> None:
    helpers = _build_ora_helper_fixture()

    recovered = helpers._extract_json_objects('[TOOL_CALLS] search ARGS {"query": "yonerai"}')
    assert recovered == ['{"tool": "search", "args": {"query": "yonerai"}}']

    route_payload = '{"route_eval": {"route": "internal"}, "visible": false}'
    visible_payload = '{"visible": true}'
    assert helpers._extract_json_objects(f"{route_payload}\n{visible_payload}") == [visible_payload]

    content = f"before {route_payload} after"
    assert helpers._strip_route_json(content) == "before  after"


def test_ora_pure_content_cleaner_removes_internal_channel_tags() -> None:
    helpers = _build_ora_helper_fixture()

    assert helpers._clean_content("<|analysis|>hidden<|final|> visible ") == "hidden visible"

