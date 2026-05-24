from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "refactor" / "ora_cog_boundary_map.py"
JSON_MAP_PATH = REPO_ROOT / "docs" / "architecture" / "ora_cog_function_map.json"
MARKDOWN_MAP_PATH = REPO_ROOT / "docs" / "architecture" / "ORA_COG_FUNCTION_MAP.md"
RUNTIME_IMPORT_MODULES = ("discord", "src.cogs.ora", "src.bot")


def _loaded_runtime_modules() -> set[str]:
    loaded: set[str] = set()
    for module_name in sys.modules:
        for runtime_root in RUNTIME_IMPORT_MODULES:
            if module_name == runtime_root or module_name.startswith(f"{runtime_root}."):
                loaded.add(module_name)
    return loaded


def _pop_modules(prefixes: tuple[str, ...]) -> dict[str, object]:
    removed: dict[str, object] = {}
    for module_name in list(sys.modules):
        if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in prefixes):
            removed[module_name] = sys.modules.pop(module_name)
    return removed


def _restore_modules(removed: dict[str, object]) -> None:
    for module_name, module in removed.items():
        sys.modules.setdefault(module_name, module)


def _load_mapper():
    spec = importlib.util.spec_from_file_location("ora_cog_boundary_map", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _ora_source() -> str:
    return (REPO_ROOT / "src" / "cogs" / "ora.py").read_text(encoding="utf-8-sig")


def _ast_definition_count() -> int:
    tree = ast.parse(_ora_source())
    return sum(1 for node in ast.walk(tree) if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)))


def test_ora_boundary_map_is_static_and_complete_without_runtime_import() -> None:
    removed = _pop_modules((*RUNTIME_IMPORT_MODULES, "ora_cog_boundary_map"))
    try:
        assert _loaded_runtime_modules() == set()
        mapper = _load_mapper()

        assert _loaded_runtime_modules() == set()

        payload = mapper.build_ora_cog_function_map(REPO_ROOT)

        assert _loaded_runtime_modules() == set()
        assert payload["schema_version"] == "yonerai-ora-cog-function-map/v1"
        assert payload["target"] == "src/cogs/ora.py"
        assert payload["source_lines"] == len(_ora_source().splitlines())
        assert payload["definition_count"] == _ast_definition_count()
    finally:
        _restore_modules(removed)


def test_committed_ora_boundary_map_matches_generator_output() -> None:
    mapper = _load_mapper()
    generated = mapper.build_ora_cog_function_map(REPO_ROOT)
    committed = json.loads(JSON_MAP_PATH.read_text(encoding="utf-8"))

    assert committed == generated


def test_ora_boundary_map_pins_extraction_candidates_and_risks() -> None:
    payload = json.loads(JSON_MAP_PATH.read_text(encoding="utf-8"))
    by_qualname = {item["qualname"]: item for item in payload["definitions"]}

    assert payload["extraction_candidates"] == [
        "ORACog._detect_spam",
        "ORACog._is_input_spam",
        "ORACog._extract_json_objects",
        "ORACog._clean_content",
        "ORACog._strip_route_json",
    ]
    assert by_qualname["ORACog.on_message"]["safety_risk"] == "high"
    assert "discord" in by_qualname["ORACog.on_message"]["side_effects"]
    assert by_qualname["ORACog._detect_spam"]["target_module"] == "src/cogs/ora_pure_helpers.py"
    assert by_qualname["ORACog._strip_route_json"]["side_effects"] == []


def test_ora_boundary_markdown_records_top_responsibilities_and_nonclaims() -> None:
    text = MARKDOWN_MAP_PATH.read_text(encoding="utf-8")

    assert "## Top Responsibilities" in text
    assert "Discord command facade" in text
    assert "Text cleanup and route/tool JSON recovery" in text
    assert "`ORACog._extract_json_objects` -> `src/cogs/ora_pure_helpers.py`" in text
    assert "reference_clawdbot" not in text