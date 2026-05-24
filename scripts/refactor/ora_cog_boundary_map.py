from __future__ import annotations

import argparse
import ast
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TARGET = Path("src/cogs/ora.py")
DEFAULT_JSON_OUTPUT = Path("docs/architecture/ora_cog_function_map.json")
DEFAULT_MARKDOWN_OUTPUT = Path("docs/architecture/ORA_COG_FUNCTION_MAP.md")
SCHEMA_VERSION = "yonerai-ora-cog-function-map/v1"

_DISCORD_HINTS = {
    "discord",
    "Interaction",
    "Message",
    "Embed",
    "app_commands",
    "commands",
    "tasks",
    "response",
    "followup",
    "send_message",
    "send",
    "reply",
}
_PROVIDER_HINTS = {
    "_llm",
    "llm",
    "LLMClient",
    "UnifiedClient",
    "unified_client",
    "core_client",
    "chat_handler",
    "chat",
    "_perform_guardrail_check",
}
_MEMORY_HINTS = {
    "memory",
    "MemoryCog",
    "memory_group",
    "vector_memory",
    "conversation_history",
}
_FILE_HINTS = {
    "open",
    "Path",
    "read_text",
    "write_text",
    "aiofiles",
    "attachment",
    "attachments",
    "download",
    "save",
    "CACHE_DIR",
    "dataset",
}
_TOOL_HINTS = {
    "ToolHandler",
    "tool_handler",
    "tools",
    "_get_tool_schemas",
    "get_context_tools",
    "SafeShell",
    "safe_shell",
    "mcp",
}
_NETWORK_HINTS = {
    "aiohttp",
    "ClientSession",
    "DDGS",
    "SearchClient",
    "_public_base_url",
    "_ora_api_base_url",
    "fetch",
}
_SYSTEM_HINTS = {
    "psutil",
    "subprocess",
    "HardwareManager",
    "DesktopWatcher",
    "desktop",
    "process",
    "reload_extension",
    "system",
}
_PURE_EXTRACTION_TARGETS = {
    "_clean_content": "src/cogs/ora_pure_helpers.py",
    "_detect_spam": "src/cogs/ora_pure_helpers.py",
    "_extract_json_objects": "src/cogs/ora_pure_helpers.py",
    "_is_input_spam": "src/cogs/ora_pure_helpers.py",
    "_strip_route_json": "src/cogs/ora_pure_helpers.py",
}


@dataclass(frozen=True)
class Definition:
    qualname: str
    name: str
    kind: str
    line_start: int
    line_end: int
    parent: str | None
    decorators: tuple[str, ...]
    inputs: tuple[str, ...]
    return_annotation: str | None
    docstring: str | None
    calls: tuple[str, ...]
    side_effects: tuple[str, ...]
    safety_risk: str
    extraction_candidate: bool
    target_module: str | None
    required_tests: tuple[str, ...]
    responsibility: str

    def to_public_dict(self, callers: tuple[str, ...]) -> dict[str, Any]:
        return {
            "qualname": self.qualname,
            "name": self.name,
            "kind": self.kind,
            "line_range": {"start": self.line_start, "end": self.line_end},
            "parent": self.parent,
            "responsibility": self.responsibility,
            "inputs": list(self.inputs),
            "outputs": _output_summary(self),
            "callers": list(callers),
            "callees": list(self.calls),
            "decorators": list(self.decorators),
            "side_effects": list(self.side_effects),
            "safety_risk": self.safety_risk,
            "extraction_candidate": self.extraction_candidate,
            "target_module": self.target_module,
            "required_tests": list(self.required_tests),
        }


@dataclass(frozen=True)
class InternalBlock:
    qualname: str
    parent: str
    line_start: int
    line_end: int
    responsibility: str
    side_effects: tuple[str, ...]
    safety_risk: str
    extraction_candidate: bool
    target_module: str | None
    required_tests: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "qualname": self.qualname,
            "parent": self.parent,
            "line_range": {"start": self.line_start, "end": self.line_end},
            "responsibility": self.responsibility,
            "side_effects": list(self.side_effects),
            "safety_risk": self.safety_risk,
            "extraction_candidate": self.extraction_candidate,
            "target_module": self.target_module,
            "required_tests": list(self.required_tests),
        }


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def _decorator_name(node: ast.AST) -> str:
    return _unparse(node) or node.__class__.__name__


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return None


def _collect_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
            call_name = _call_name(child)
            if call_name:
                names.add(call_name)
    return names


def _collect_calls(node: ast.AST) -> tuple[str, ...]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name:
                calls.add(name)
    return tuple(sorted(calls))


def _side_effects(node: ast.AST, decorators: tuple[str, ...]) -> tuple[str, ...]:
    haystack = {name.lower() for name in _collect_names(node)}
    haystack.update(decorator.lower() for decorator in decorators)
    effects: list[str] = []
    if _matches(haystack, _DISCORD_HINTS):
        effects.append("discord")
    if _matches(haystack, _PROVIDER_HINTS):
        effects.append("provider_or_llm")
    if _matches(haystack, _MEMORY_HINTS):
        effects.append("memory")
    if _matches(haystack, _FILE_HINTS):
        effects.append("file")
    if _matches(haystack, _TOOL_HINTS):
        effects.append("tool_or_shell_policy")
    if _matches(haystack, _NETWORK_HINTS):
        effects.append("network")
    if _matches(haystack, _SYSTEM_HINTS):
        effects.append("system_or_process")
    return tuple(effects)


def _matches(haystack: set[str], hints: set[str]) -> bool:
    return bool(haystack.intersection({hint.lower() for hint in hints}))


def _safety_risk(side_effects: tuple[str, ...], name: str, decorators: tuple[str, ...]) -> str:
    if any(effect in side_effects for effect in ("system_or_process", "tool_or_shell_policy", "network", "file")):
        return "high"
    if any(effect in side_effects for effect in ("discord", "provider_or_llm", "memory")):
        return "medium"
    if decorators:
        return "medium"
    if name in _PURE_EXTRACTION_TARGETS:
        return "low"
    return "low"


def _required_tests(name: str, side_effects: tuple[str, ...], extraction_candidate: bool) -> tuple[str, ...]:
    tests: list[str] = []
    if extraction_candidate:
        tests.append("characterization parity before wrapper extraction")
    if "discord" in side_effects:
        tests.append("discord-free static or mock interaction test")
    if "provider_or_llm" in side_effects:
        tests.append("provider mocked or local-fixture execution test")
    if "file" in side_effects:
        tests.append("workspace/temp-file allowlist test")
    if "tool_or_shell_policy" in side_effects:
        tests.append("deny-by-default tool boundary test")
    if "network" in side_effects:
        tests.append("network-disabled fixture test")
    if "system_or_process" in side_effects:
        tests.append("read-only diagnostic fixture test")
    return tuple(tests or ["static map coverage only"])


def _inputs(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> tuple[str, ...]:
    if isinstance(node, ast.ClassDef):
        return tuple(f"base:{_unparse(base) or base.__class__.__name__}" for base in node.bases)
    args = []
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        annotation = _unparse(arg.annotation)
        args.append(f"{arg.arg}: {annotation}" if annotation else arg.arg)
    if node.args.vararg:
        args.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg:
        args.append(f"**{node.args.kwarg.arg}")
    return tuple(args)


def _output_summary(definition: Definition) -> str:
    if definition.kind == "ClassDef":
        return "class instance"
    prefix = "async coroutine" if definition.kind == "AsyncFunctionDef" else "return value"
    if definition.return_annotation:
        return f"{prefix}; annotation: {definition.return_annotation}"
    return prefix


def _responsibility(name: str, docstring: str | None, decorators: tuple[str, ...], side_effects: tuple[str, ...]) -> str:
    if docstring:
        first = " ".join(docstring.strip().split())
        if first:
            return first[:180]
    if name == "ORACog":
        return "Discord-facing ORA facade that wires legacy runtime managers, commands, providers, tools, and memory."
    if name == "__init__":
        return "Initializes ORACog runtime dependencies and mutable state."
    if decorators:
        return "Discord command/listener/task entrypoint."
    if side_effects:
        return f"Legacy helper with {', '.join(side_effects)} boundary involvement."
    if name in _PURE_EXTRACTION_TARGETS:
        return "Pure text or JSON helper suitable for wrapper-based extraction."
    return "Legacy helper or setup block."


def _iter_direct_definitions(node: ast.AST) -> list[ast.AST]:
    body = getattr(node, "body", [])
    return [child for child in body if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]


def _iter_live_direct_definitions(node: ast.AST) -> list[ast.AST]:
    definitions = _iter_direct_definitions(node)
    live_names: set[str] = set()
    live_reversed: list[ast.AST] = []
    for child in reversed(definitions):
        if child.name in live_names:
            continue
        live_names.add(child.name)
        live_reversed.append(child)
    return list(reversed(live_reversed))


def _walk_definitions(node: ast.AST, parent: str | None = None) -> list[Definition]:
    definitions: list[Definition] = []
    for child in _iter_live_direct_definitions(node):
        name = child.name
        qualname = f"{parent}.{name}" if parent else name
        decorators = tuple(_decorator_name(decorator) for decorator in getattr(child, "decorator_list", []))
        docstring = ast.get_docstring(child)
        calls = _collect_calls(child)
        side_effects = _side_effects(child, decorators)
        extraction_candidate = name in _PURE_EXTRACTION_TARGETS and not side_effects
        target_module = _PURE_EXTRACTION_TARGETS.get(name) if extraction_candidate else None
        definitions.append(
            Definition(
                qualname=qualname,
                name=name,
                kind=child.__class__.__name__,
                line_start=child.lineno,
                line_end=getattr(child, "end_lineno", child.lineno),
                parent=parent,
                decorators=decorators,
                inputs=_inputs(child),
                return_annotation=_unparse(getattr(child, "returns", None)),
                docstring=docstring,
                calls=calls,
                side_effects=side_effects,
                safety_risk=_safety_risk(side_effects, name, decorators),
                extraction_candidate=extraction_candidate,
                target_module=target_module,
                required_tests=_required_tests(name, side_effects, extraction_candidate),
                responsibility=_responsibility(name, docstring, decorators, side_effects),
            )
        )
        definitions.extend(_walk_definitions(child, qualname))
    return definitions


def _find_class(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    return next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name), None)


def _find_direct_method(class_node: ast.ClassDef, method_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    methods = [
        node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name
    ]
    return methods[-1] if methods else None


_NESTED_SCOPE_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _walk_method_body(method: ast.FunctionDef | ast.AsyncFunctionDef):
    stack = list(reversed(method.body))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, _NESTED_SCOPE_NODES):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _find_name_assignment(method: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> ast.Assign | ast.AnnAssign | None:
    for node in _walk_method_body(method):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return node
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node
    return None


def _find_for_iterating_name(method: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> ast.For | ast.AsyncFor | None:
    for node in _walk_method_body(method):
        if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.iter, ast.Name) and node.iter.id == name:
            return node
    return None


def _test_mentions_name_truthiness(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == name:
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"bool", "len"}:
        return bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id == name
    if isinstance(node, ast.BoolOp):
        return any(_test_mentions_name_truthiness(value, name) for value in node.values)
    return False


def _find_if_testing_name(method: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> ast.If | None:
    for node in _walk_method_body(method):
        if isinstance(node, ast.If) and _test_mentions_name_truthiness(node.test, name):
            return node
    return None


def _find_call_by_name(method: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> ast.Call | None:
    for node in _walk_method_body(method):
        if isinstance(node, ast.Call) and _call_name(node.func) == name:
            return node
    return None


def _internal_blocks(tree: ast.Module) -> list[InternalBlock]:
    ora_class = _find_class(tree, "ORACog")
    if ora_class is None:
        return []

    blocks: list[InternalBlock] = []

    large_message = _find_direct_method(ora_class, "_send_large_message")
    if large_message is not None:
        chunks_assignment = _find_name_assignment(large_message, "chunks")
        chunks_loop = _find_for_iterating_name(large_message, "chunks")
        if chunks_assignment is not None and chunks_loop is not None:
            blocks.append(
                InternalBlock(
                    qualname="ORACog._send_large_message.large_message_chunking",
                    parent="ORACog._send_large_message",
                    line_start=chunks_assignment.lineno,
                    line_end=getattr(chunks_loop, "end_lineno", chunks_loop.lineno),
                    responsibility="Split a Discord-bound response into 1900-character chunks while keeping the first chunk tied to the reply.",
                    side_effects=(),
                    safety_risk="low",
                    extraction_candidate=True,
                    target_module="src/cogs/ora_message_format_helpers.py",
                    required_tests=("characterization parity before wrapper extraction",),
                )
            )

    guardrail = _find_direct_method(ora_class, "_perform_guardrail_check")
    if guardrail is not None:
        content_if = _find_if_testing_name(guardrail, "content")
        if content_if is not None:
            blocks.append(
                InternalBlock(
                    qualname="ORACog._perform_guardrail_check.guardrail_response_interpretation",
                    parent="ORACog._perform_guardrail_check",
                    line_start=content_if.lineno,
                    line_end=getattr(content_if, "end_lineno", content_if.lineno),
                    responsibility="Interpret a guardrail model response by preferring recovered JSON and falling back to a conservative safe=false keyword check.",
                    side_effects=(),
                    safety_risk="low",
                    extraction_candidate=True,
                    target_module="src/cogs/ora_guardrail_helpers.py",
                    required_tests=("characterization parity before wrapper extraction",),
                )
            )
        else:
            delegated_call = _find_call_by_name(guardrail, "interpret_ora_guardrail_response")
            if delegated_call is not None:
                blocks.append(
                    InternalBlock(
                        qualname="ORACog._perform_guardrail_check.guardrail_response_interpretation",
                        parent="ORACog._perform_guardrail_check",
                        line_start=delegated_call.lineno,
                        line_end=getattr(delegated_call, "end_lineno", delegated_call.lineno),
                        responsibility="Delegate guardrail model response interpretation to the extracted pure helper.",
                        side_effects=(),
                        safety_risk="low",
                        extraction_candidate=False,
                        target_module="src/cogs/ora_guardrail_helpers.py",
                        required_tests=("wrapper compatibility test",),
                    )
                )

    return blocks


def _normalize_callee(raw_call: str, known_qualnames: set[str], current_parent: str | None) -> str:
    if raw_call.startswith("self.") and current_parent:
        candidate = f"{current_parent}.{raw_call.removeprefix('self.')}"
        return candidate if candidate in known_qualnames else raw_call
    if current_parent:
        nested_candidate = f"{current_parent}.{raw_call}"
        if nested_candidate in known_qualnames:
            return nested_candidate
    if raw_call in known_qualnames:
        return raw_call
    return raw_call


def build_ora_cog_function_map(repo_root: str | Path = ".", target: str | Path = DEFAULT_TARGET) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    target_path = root / target
    source = _read_text(target_path)
    tree = ast.parse(source, filename=_relative(target_path, root))
    definitions = _walk_definitions(tree)
    known_qualnames = {definition.qualname for definition in definitions}

    normalized_definitions: list[Definition] = []
    for definition in definitions:
        normalized_calls = tuple(
            sorted({_normalize_callee(call, known_qualnames, definition.parent) for call in definition.calls})
        )
        normalized_definitions.append(
            Definition(
                qualname=definition.qualname,
                name=definition.name,
                kind=definition.kind,
                line_start=definition.line_start,
                line_end=definition.line_end,
                parent=definition.parent,
                decorators=definition.decorators,
                inputs=definition.inputs,
                return_annotation=definition.return_annotation,
                docstring=definition.docstring,
                calls=normalized_calls,
                side_effects=definition.side_effects,
                safety_risk=definition.safety_risk,
                extraction_candidate=definition.extraction_candidate,
                target_module=definition.target_module,
                required_tests=definition.required_tests,
                responsibility=definition.responsibility,
            )
        )

    callers: dict[str, set[str]] = {definition.qualname: set() for definition in normalized_definitions}
    for definition in normalized_definitions:
        for call in definition.calls:
            if call in callers:
                callers[call].add(definition.qualname)

    definitions_payload = [
        definition.to_public_dict(tuple(sorted(callers[definition.qualname])))
        for definition in sorted(normalized_definitions, key=lambda item: (item.line_start, item.qualname))
    ]
    internal_blocks = [
        block.to_public_dict()
        for block in sorted(_internal_blocks(tree), key=lambda item: (item.line_start, item.qualname))
    ]
    extraction_candidates = [
        item["qualname"]
        for item in definitions_payload
        if item["extraction_candidate"]
    ]
    extraction_candidates.extend(
        item["qualname"]
        for item in internal_blocks
        if item["extraction_candidate"]
    )
    risk_counts = {
        risk: sum(1 for item in definitions_payload if item["safety_risk"] == risk)
        for risk in ("low", "medium", "high")
    }
    side_effect_counts: dict[str, int] = {}
    for item in definitions_payload:
        for side_effect in item["side_effects"]:
            side_effect_counts[side_effect] = side_effect_counts.get(side_effect, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "target": _relative(target_path, root),
        "source_lines": len(source.splitlines()),
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "definition_count": len(definitions_payload),
        "risk_counts": risk_counts,
        "side_effect_counts": dict(sorted(side_effect_counts.items())),
        "extraction_candidates": extraction_candidates,
        "internal_blocks": internal_blocks,
        "definitions": definitions_payload,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# ORA Cog Function Map",
        "",
        "This document is generated from `src/cogs/ora.py` using AST inspection. It does not import the Discord runtime.",
        "",
        "## Summary",
        "",
        f"- Target: `{payload['target']}`",
        f"- Source lines: `{payload['source_lines']}`",
        f"- Source SHA-256: `{payload['source_sha256']}`",
        f"- Definitions mapped: `{payload['definition_count']}`",
        f"- Risk counts: `{json.dumps(payload['risk_counts'], sort_keys=True)}`",
        f"- Side-effect counts: `{json.dumps(payload['side_effect_counts'], sort_keys=True)}`",
        "",
        "## Top Responsibilities",
        "",
        "- Discord command facade: slash commands, listeners, task loops, interaction replies.",
        "- Runtime dependency wiring: managers, handlers, LLM clients, cost manager, watcher, storage.",
        "- Permission and privacy policy: owner checks, privacy defaults, linked account state.",
        "- System and desktop diagnostics: process list, status, desktop watcher, reload entrypoints.",
        "- Provider and guardrail bridge: prompt handling, guardrail LLM call, model/client selection.",
        "- Tool boundary surface: schema assembly, context filtering, tool handler integration.",
        "- File and attachment handling: dataset upload, attachment/image processing, cache paths.",
        "- Memory and points surface: memory clear, rank, points, conversation queue paths.",
        "- Text cleanup and route/tool JSON recovery: legacy tags, route JSON stripping, tool-call recovery.",
        "- Discord compatibility shims: mock interaction helpers and reaction handling.",
        "",
        "## Extraction Candidates",
        "",
    ]
    candidates = payload["extraction_candidates"]
    if candidates:
        for candidate in candidates:
            target = _target_for_candidate(payload, candidate)
            lines.append(f"- `{candidate}` -> `{target}`")
    else:
        lines.append("- None. No pure helper met the current extraction heuristic.")
    lines.extend(["", "## Internal Block Map", ""])
    internal_blocks = payload.get("internal_blocks") or []
    if internal_blocks:
        lines.append("| Lines | Qualname | Responsibility | Side effects | Risk | Candidate | Target | Required tests |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for item in internal_blocks:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"{item['line_range']['start']}-{item['line_range']['end']}",
                        f"`{item['qualname']}`",
                        _md_cell(item["responsibility"]),
                        ", ".join(item["side_effects"]) or "none",
                        item["safety_risk"],
                        "yes" if item["extraction_candidate"] else "no",
                        f"`{item['target_module']}`" if item["target_module"] else "",
                        _md_cell("; ".join(item["required_tests"])),
                    ]
                )
                + " |"
            )
    else:
        lines.append("- None. No significant internal blocks met the current extraction heuristic.")
    lines.extend(["", "## Definition Map", ""])
    lines.append(
        "| Lines | Qualname | Responsibility | Side effects | Risk | Candidate | Target | Required tests |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for item in payload["definitions"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{item['line_range']['start']}-{item['line_range']['end']}",
                    f"`{item['qualname']}`",
                    _md_cell(item["responsibility"]),
                    ", ".join(item["side_effects"]) or "none",
                    item["safety_risk"],
                    "yes" if item["extraction_candidate"] else "no",
                    f"`{item['target_module']}`" if item["target_module"] else "",
                    _md_cell("; ".join(item["required_tests"])),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Interface Map", ""])
    lines.append("| Lines | Qualname | Inputs | Outputs | Callers | Local callees |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    known_qualnames = {item["qualname"] for item in payload["definitions"]}
    for item in payload["definitions"]:
        local_callees = [callee for callee in item["callees"] if callee in known_qualnames]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"{item['line_range']['start']}-{item['line_range']['end']}",
                    f"`{item['qualname']}`",
                    _md_cell(", ".join(item["inputs"]) or "none"),
                    _md_cell(item["outputs"]),
                    _md_cell(", ".join(f"`{caller}`" for caller in item["callers"]) or "none"),
                    _md_cell(", ".join(f"`{callee}`" for callee in sorted(local_callees)) or "none"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Call Graph Notes", ""])
    for item in payload["definitions"]:
        callers = item["callers"]
        callees = [callee for callee in item["callees"] if callee in known_qualnames]
        if not callers and not callees:
            continue
        lines.append(f"### `{item['qualname']}`")
        if callers:
            lines.append(f"- Callers: {', '.join(f'`{caller}`' for caller in callers)}")
        if callees:
            lines.append(f"- Local callees: {', '.join(f'`{callee}`' for callee in sorted(callees))}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _md_cell(value: str) -> str:
    return " ".join(str(value).replace("|", "\\|").split())


def _target_for_candidate(payload: dict[str, Any], candidate: str) -> str:
    for section in ("definitions", "internal_blocks"):
        for item in payload.get(section, []):
            if item["qualname"] == candidate and item.get("target_module"):
                return item["target_module"]
    return "unknown"


def write_outputs(payload: dict[str, Any], json_output: Path, markdown_output: Path) -> None:
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_output.write_text(render_markdown(payload), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a static ORA Cog boundary map without importing runtime code.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Target module path relative to repo root.")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT), help="JSON output path relative to repo root.")
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN_OUTPUT), help="Markdown output path relative to repo root.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown outputs.")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    payload = build_ora_cog_function_map(repo_root, args.target)
    if args.write:
        write_outputs(payload, repo_root / args.json_output, repo_root / args.markdown_output)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
