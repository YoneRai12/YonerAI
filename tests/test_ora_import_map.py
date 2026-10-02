from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "refactor" / "ora_py_static_surface.py"
RUNTIME_IMPORT_MODULES = ("discord", "src.cogs.ora", "src.bot")


def _loaded_runtime_modules() -> set[str]:
    loaded: set[str] = set()
    for module_name in sys.modules:
        for runtime_root in RUNTIME_IMPORT_MODULES:
            if module_name == runtime_root or module_name.startswith(f"{runtime_root}."):
                loaded.add(module_name)
    return loaded


def _load_analyzer():
    spec = importlib.util.spec_from_file_location("ora_py_static_surface", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_static_surface_pins_oracog_facade_without_runtime_import():
    runtime_baseline = _loaded_runtime_modules()
    analyzer = _load_analyzer()

    assert _loaded_runtime_modules() == runtime_baseline

    surface = analyzer.analyze_ora_surface(REPO_ROOT)

    assert _loaded_runtime_modules() == runtime_baseline
    assert surface["target"] == "src/cogs/ora.py"
    assert surface["setup"]["present"] is True
    assert surface["setup"]["async"] is True
    assert surface["oracog"]["line"] is not None


def test_oracog_required_methods_and_init_attributes_are_present():
    analyzer = _load_analyzer()
    surface = analyzer.analyze_ora_surface(REPO_ROOT)
    method_names = {method["name"] for method in surface["oracog"]["methods"]}
    init_attrs = set(surface["oracog"]["init_attributes"])

    assert {
        "handle_prompt",
        "get_context_tools",
        "_check_permission",
        "_get_tool_schemas",
        "_is_input_spam",
        "_perform_guardrail_check",
        "_process_attachments",
        "_process_embed_images",
    }.issubset(method_names)
    assert {
        "bot",
        "tool_handler",
        "vision_handler",
        "chat_handler",
        "cost_manager",
        "safe_shell",
        "user_prefs",
        "soul_prompt",
        "unified_client",
    }.issubset(init_attrs)


def test_static_surface_records_known_inbound_references():
    analyzer = _load_analyzer()
    surface = analyzer.analyze_ora_surface(REPO_ROOT)
    inbound = {item["file"]: item["patterns"] for item in surface["inbound_references"]}

    assert "src/bot.py" in inbound
    assert "scripts/verify_startup.py" in inbound
    assert "scripts/verify_tool_integrity.py" in inbound
    assert "src/utils/health_inspector.py" in inbound
    assert "direct_oracog_import" in inbound["src/bot.py"]


def test_static_surface_records_duplicate_method_names_for_future_cleanup():
    analyzer = _load_analyzer()
    surface = analyzer.analyze_ora_surface(REPO_ROOT)

    assert "_get_tool_schemas" in surface["oracog"]["duplicate_methods"]


def test_static_surface_output_is_deterministic_json():
    analyzer = _load_analyzer()
    first = analyzer.analyze_ora_surface(REPO_ROOT)
    second = analyzer.analyze_ora_surface(REPO_ROOT)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
