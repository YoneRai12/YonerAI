from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_TARGET = Path("src/cogs/ora.py")
SCAN_ROOTS = ("src", "scripts", "tests", "core")
REFERENCE_PATTERNS = {
    "direct_module_string": "src.cogs.ora",
    "direct_oracog_import": "from .cogs.ora import ORACog",
    "absolute_oracog_import": "from src.cogs.ora import ORACog",
    "double_quote_cog_lookup": 'get_cog("ORACog")',
    "single_quote_cog_lookup": "get_cog('ORACog')",
}


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _decorator_name(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return node.__class__.__name__


def _import_module_name(node: ast.Import | ast.ImportFrom, alias: ast.alias) -> str:
    if isinstance(node, ast.Import):
        return alias.name
    prefix = "." * node.level
    module = node.module or ""
    return f"{prefix}{module}"


def _collect_imports(tree: ast.Module) -> list[dict[str, Any]]:
    imports: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                imports.append(
                    {
                        "line": node.lineno,
                        "module": _import_module_name(node, alias),
                        "name": alias.name,
                        "asname": alias.asname,
                        "kind": node.__class__.__name__,
                    }
                )
    return sorted(imports, key=lambda item: (item["line"], item["module"], item["name"]))


def _collect_class_surface(tree: ast.Module, class_name: str) -> dict[str, Any]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods: list[dict[str, Any]] = []
            init_attrs: set[str] = set()
            method_names: list[str] = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.append(child.name)
                    methods.append(
                        {
                            "name": child.name,
                            "line": child.lineno,
                            "async": isinstance(child, ast.AsyncFunctionDef),
                            "decorators": [_decorator_name(decorator) for decorator in child.decorator_list],
                        }
                    )
                    if child.name == "__init__":
                        for nested in ast.walk(child):
                            if isinstance(nested, ast.Attribute) and isinstance(nested.value, ast.Name):
                                if nested.value.id == "self" and isinstance(nested.ctx, ast.Store):
                                    init_attrs.add(nested.attr)
            duplicates = sorted(name for name, count in Counter(method_names).items() if count > 1)
            return {
                "name": node.name,
                "line": node.lineno,
                "methods": sorted(methods, key=lambda item: (item["line"], item["name"])),
                "init_attributes": sorted(init_attrs),
                "duplicate_methods": duplicates,
            }
    return {"name": class_name, "line": None, "methods": [], "init_attributes": [], "duplicate_methods": []}


def _iter_scanned_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.py") if "reference_clawdbot" not in path.parts)
    return sorted(files)


def _collect_inbound_references(repo_root: Path, target: Path) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    target_resolved = target.resolve()
    for path in _iter_scanned_files(repo_root):
        if path.resolve() == target_resolved or path.name == "ora_py_static_surface.py":
            continue
        text = _read_text(path)
        matches = sorted(name for name, pattern in REFERENCE_PATTERNS.items() if pattern in text)
        if matches:
            references.append({"file": _relative(path, repo_root), "patterns": matches})
    return references


def analyze_ora_surface(repo_root: str | Path = ".", target: str | Path = DEFAULT_TARGET) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    target_path = root / target
    tree = ast.parse(_read_text(target_path), filename=_relative(target_path, root))
    top_level = [
        {"name": node.name, "kind": node.__class__.__name__, "line": node.lineno}
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    setup_nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "setup"]
    return {
        "target": _relative(target_path, root),
        "imports": _collect_imports(tree),
        "top_level_definitions": sorted(top_level, key=lambda item: (item["line"], item["name"])),
        "oracog": _collect_class_surface(tree, "ORACog"),
        "setup": {
            "present": bool(setup_nodes),
            "async": bool(setup_nodes and isinstance(setup_nodes[0], ast.AsyncFunctionDef)),
            "line": setup_nodes[0].lineno if setup_nodes else None,
        },
        "inbound_references": _collect_inbound_references(root, target_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Statically inspect src/cogs/ora.py without importing runtime code.")
    parser.add_argument("--repo-root", default=".", help="Repository root to inspect.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Target module path relative to repo root.")
    args = parser.parse_args()
    result = analyze_ora_surface(args.repo_root, args.target)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
