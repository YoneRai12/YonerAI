from __future__ import annotations

import ast
import sys
import types
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
ORA_PATH = REPO_ROOT / "src" / "cogs" / "ora.py"


class _SkillLoader:
    skills = {"dynamic_web": object()}

    def get_schema(self, skill_name: str) -> dict[str, object]:
        assert skill_name == "dynamic_web"
        return {"name": "browser_nav", "source": "skill"}


class _Bot:
    config = SimpleNamespace(admin_user_id=999, profile="private", sub_admin_ids=set())


def _build_context_tools_fixture(tools: list[dict[str, object]]):
    source = ORA_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    ora_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ORACog")
    method = next(
        node
        for node in ora_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "get_context_tools"
    )
    module = ast.Module(
        body=[
            ast.ClassDef(
                name="OraToolSchemaFixture",
                bases=[],
                keywords=[],
                body=[
                    ast.FunctionDef(
                        name="__init__",
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg="self")],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=[
                            ast.Assign(
                                targets=[ast.Attribute(value=ast.Name(id="self", ctx=ast.Load()), attr="bot", ctx=ast.Store())],
                                value=ast.Name(id="bot", ctx=ast.Load()),
                            ),
                            ast.Assign(
                                targets=[
                                    ast.Attribute(
                                        value=ast.Name(id="self", ctx=ast.Load()),
                                        attr="tool_handler",
                                        ctx=ast.Store(),
                                    )
                                ],
                                value=ast.Call(
                                    func=ast.Name(id="SimpleNamespace", ctx=ast.Load()),
                                    args=[],
                                    keywords=[
                                        ast.keyword(
                                            arg="skill_loader",
                                            value=ast.Call(func=ast.Name(id="skill_loader_factory", ctx=ast.Load()), args=[], keywords=[]),
                                        )
                                    ],
                                ),
                            ),
                        ],
                        decorator_list=[],
                    ),
                    ast.FunctionDef(
                        name="_get_tool_schemas",
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg="self")],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=[ast.Return(value=ast.Call(func=ast.Name(id="list", ctx=ast.Load()), args=[ast.Name(id="tools", ctx=ast.Load())], keywords=[]))],
                        decorator_list=[],
                    ),
                    method,
                ],
                decorator_list=[],
            )
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    namespace = {
        "SimpleNamespace": SimpleNamespace,
        "bot": _Bot(),
        "skill_loader_factory": _SkillLoader,
        "tools": tools,
    }
    exec(compile(module, str(ORA_PATH), "exec"), namespace)
    return namespace["OraToolSchemaFixture"]()


def _install_registry_fixture(monkeypatch) -> None:
    registry = types.ModuleType("src.cogs.tools.registry")
    registry.get_tool_schemas = lambda: [
        {"name": "music_play", "source": "registry_duplicate"},
        {"name": "web_search_api", "source": "registry"},
    ]
    monkeypatch.setitem(sys.modules, "src.cogs.tools.registry", registry)


def test_ora_context_tools_dedupes_dynamic_sources_and_filters_by_client(monkeypatch) -> None:
    _install_registry_fixture(monkeypatch)
    fixture = _build_context_tools_fixture(
        [
            {"name": "music_play", "source": "builtin"},
            {"name": "dom_click", "source": "builtin"},
            {"name": "safe_tool", "source": "builtin"},
            {"name": ""},
        ]
    )

    discord_names = {tool["name"]: tool for tool in fixture.get_context_tools("discord")}
    web_names = {tool["name"]: tool for tool in fixture.get_context_tools("web")}

    assert "dom_click" not in discord_names
    assert "browser_nav" not in discord_names
    assert discord_names["music_play"]["source"] == "builtin"
    assert "safe_tool" in discord_names
    assert "web_search_api" in discord_names

    assert "music_play" not in web_names
    assert "dom_click" in web_names
    assert "browser_nav" in web_names


def test_ora_context_tools_non_owner_keeps_allowlist_and_denies_unknown(monkeypatch) -> None:
    _install_registry_fixture(monkeypatch)
    fixture = _build_context_tools_fixture(
        [
            {"name": "music_play"},
            {"name": "web_download"},
            {"name": "dangerous_unknown"},
            {"name": "dom_click"},
        ]
    )

    names = {tool["name"] for tool in fixture.get_context_tools("discord", user_id=123)}

    assert names == {"music_play", "web_search_api"}
