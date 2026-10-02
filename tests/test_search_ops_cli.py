from __future__ import annotations

import json
import sys
from pathlib import Path


def _prepare_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for path in (repo_root / "core" / "src", repo_root / "clients" / "cli"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def _clear_modules(monkeypatch, *module_names: str) -> None:
    for module_name in module_names:
        monkeypatch.delitem(sys.modules, module_name, raising=False)


def _write_attacker_redaction_package(tmp_path: Path) -> Path:
    src_package = tmp_path / "src"
    utils_package = src_package / "utils"
    utils_package.mkdir(parents=True)
    (src_package / "__init__.py").write_text("", encoding="utf-8")
    (utils_package / "__init__.py").write_text("", encoding="utf-8")
    marker = tmp_path / "attacker_redaction_imported.txt"
    (utils_package / "redaction.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
        "def redact_text(value):\n"
        "    return value\n"
        "def redact_json(value):\n"
        "    return value\n",
        encoding="utf-8",
    )
    return marker


def _write_attacker_core_module(tmp_path: Path, module_path: str) -> Path:
    package = tmp_path / "ora_core"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    marker = tmp_path / f"attacker_{module_path.replace('/', '_')}_imported.txt"
    target = package / module_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.name == "__init__.py":
        target.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
            "raise RuntimeError('attacker ora_core package imported')\n",
            encoding="utf-8",
        )
    else:
        (target.parent / "__init__.py").write_text("", encoding="utf-8")
        target.write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
            "raise RuntimeError('attacker ora_core module imported')\n",
            encoding="utf-8",
        )
    return marker


def test_trusted_cli_import_paths_keep_core_before_repo_and_cwd(tmp_path, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    repo_root = Path(cli.__file__).resolve().parents[3]
    core_src = repo_root / "core" / "src"
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.syspath_prepend(str(tmp_path))

    cli._prepare_trusted_cli_import_paths()

    assert sys.path[0] == str(core_src)
    assert sys.path[1] == str(repo_root)
    assert sys.path.index(str(core_src)) < sys.path.index(str(repo_root))
    assert sys.path.index(str(repo_root)) < sys.path.index(str(tmp_path))


def test_repo_self_checks_preserve_core_import_precedence(tmp_path, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    repo_root = Path(cli.__file__).resolve().parents[3]
    core_src = repo_root / "core" / "src"
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.syspath_prepend(str(tmp_path))

    redaction_check = cli._run_redaction_self_check()
    mcp_check = cli._run_mcp_deny_policy_self_check()

    assert redaction_check["ok"] is True
    assert redaction_check["status"] == "ok"
    assert redaction_check["network_required"] is False
    assert mcp_check["ok"] is True
    assert mcp_check["status"] == "ok"
    assert mcp_check["network_required"] is False

    assert sys.path.index(str(core_src)) < sys.path.index(str(repo_root))
    assert sys.path.index(str(repo_root)) < sys.path.index(str(tmp_path))


def test_mock_search_adapter_returns_deterministic_fixture() -> None:
    _prepare_paths()
    from ora_core.search import MockSearchAdapter, SearchRequest

    results = MockSearchAdapter().search(SearchRequest(query="YonerAI alpha2"))

    assert len(results) == 2
    assert results[0].source == "mock"
    assert "YonerAI alpha2" in results[0].snippet


def test_cli_search_mock_has_no_network(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["search", "mock", "YonerAI", "alpha2", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert output["adapter"] == "mock"
    assert output["network_performed"] is False
    assert output["results"][0]["source"] == "mock"
    assert output["run"]["run_id"].startswith("run_")
    assert output["run"]["status"] == "completed"


def test_cli_search_mock_records_redacted_ledger(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    ledger = tmp_path / "runs.jsonl"

    rc = cli.main(["search", "mock", "YonerAI", "alpha2", "--json", "--ledger", str(ledger)])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert output["run"]["status"] == "completed"
    assert output["run"]["classification"]["category"] == "mock_web_search"
    assert output["ledger"]["file_backed"] is True
    assert str(ledger) not in captured.out
    ledger_text = ledger.read_text(encoding="utf-8")
    assert output["run"]["run_id"] in ledger_text
    assert "mock_search_results" in ledger_text


def test_cli_search_live_is_disabled_by_default(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["search", "live", "YonerAI", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 1
    assert output["ok"] is False
    assert output["query"] == "YonerAI"
    assert output["network_performed"] is False
    assert output["live_boundary"]["status"] == "disabled"
    assert output["live_boundary"]["reason"] == "live_search_not_implemented"
    assert "no network request was performed" in output["live_boundary"]["message"]
    assert output["live_boundary"]["requires_explicit_live_provider"] is True
    assert "no network request" in output["live_boundary"]["actions_not_performed"]
    assert output["error"]["code"] == "search_live_disabled"
    assert output["run"]["run_id"].startswith("run_")
    assert output["run"]["status"] == "blocked"


def test_cli_search_live_whitespace_query_still_returns_boundary_json(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["search", "live", "   ", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 1
    assert output["ok"] is False
    assert output["query"] == ""
    assert output["network_performed"] is False
    assert output["live_boundary"]["reason"] == "live_search_not_implemented"
    assert output["run"]["task_summary"] == "search live"
    assert captured.err == ""


def test_cli_search_live_records_blocked_run_without_network(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    ledger = tmp_path / "runs.jsonl"

    rc = cli.main(["search", "live", "YonerAI", "--json", "--ledger", str(ledger)])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 1
    assert output["run"]["status"] == "blocked"
    assert output["run"]["disabled_reason"] == "live_search_not_implemented"
    assert output["network_performed"] is False
    assert str(ledger) not in captured.out
    assert "live_search_boundary" in ledger.read_text(encoding="utf-8")


def test_cli_search_live_pretty_reports_no_network_boundary(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["search", "live", "YonerAI", "--pretty", "--color", "never"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "Live search boundary" in captured.out
    assert "live_search_not_implemented" in captured.out
    assert "Live search is disabled" in captured.out
    assert "no network request" in captured.out


def test_safeshell_plans_allowlisted_diagnostic_without_execution() -> None:
    _prepare_paths()
    from ora_core.ops import plan_operation

    plan = plan_operation("git-status").to_public_dict()

    assert plan["status"] == "planned"
    assert plan["command_preview"] == ["git", "status", "--short"]
    assert plan["execution_performed"] is False
    assert plan["approval_required"] is False
    assert plan["mcp_policy"]["source"] == "src/cogs/mcp_policy.py"


def test_safeshell_denies_arbitrary_shell() -> None:
    _prepare_paths()
    from ora_core.ops import plan_operation

    plan = plan_operation("rm -rf workspace").to_public_dict()

    assert plan["status"] == "denied"
    assert plan["execution_performed"] is False
    assert plan["approval_required"] is True
    assert plan["reason"] == "arbitrary_shell_disabled"


def test_cli_ops_plan_json(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["ops", "plan", "python-version", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert output["shell_executed"] is False
    assert output["mutation_performed"] is False
    assert output["plan"]["command_preview"] == ["python", "--version"]


def test_cli_ops_plan_does_not_import_mcp_policy_from_cwd(tmp_path, capsys, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    attacker_policy = tmp_path / "src" / "cogs" / "mcp_policy.py"
    attacker_policy.parent.mkdir(parents=True)
    (tmp_path / "src" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "cogs" / "__init__.py").write_text("", encoding="utf-8")
    marker = tmp_path / "attacker_imported.txt"
    attacker_policy.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
        "def load_mcp_deny_patterns():\n"
        "    return ['attacker-pattern']\n"
        "def is_mcp_tool_denied(operation, patterns):\n"
        "    return False\n",
        encoding="utf-8",
    )
    _clear_modules(monkeypatch, "src", "src.cogs", "src.cogs.mcp_policy")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    rc = cli.main(["ops", "plan", "python-version", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert marker.exists() is False
    assert "attacker-pattern" not in output["plan"]["mcp_policy"]["default_deny_patterns"]


def test_cli_ops_plan_does_not_import_ora_core_from_cwd(tmp_path, capsys, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    marker = _write_attacker_core_module(tmp_path, "ops/__init__.py")
    _clear_modules(monkeypatch, "ora_core", "ora_core.ops")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    rc = cli.main(["ops", "plan", "python-version", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert marker.exists() is False
    assert output["plan"]["command_preview"] == ["python", "--version"]


def test_cli_route_preview_does_not_import_ora_core_from_cwd(tmp_path, capsys, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    marker = _write_attacker_core_module(tmp_path, "route_preview.py")
    _clear_modules(monkeypatch, "ora_core", "ora_core.route_preview")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    rc = cli.main(["route", "preview", "summarize", "public", "docs", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert marker.exists() is False
    assert output["schema_version"] == "three-mode-route-preview-0.3"
    assert output["route"]


def test_cli_search_mock_does_not_import_redaction_from_cwd(tmp_path, capsys, monkeypatch) -> None:
    _prepare_paths()
    _clear_modules(monkeypatch, "src", "src.utils", "src.utils.redaction")
    from yonerai_cli import cli

    marker = _write_attacker_redaction_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    rc = cli.main(["search", "mock", "YonerAI", "alpha2", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert marker.exists() is False


def test_cli_discord_synthetic_does_not_import_redaction_from_cwd(tmp_path, capsys, monkeypatch) -> None:
    _prepare_paths()
    _clear_modules(monkeypatch, "src", "src.utils", "src.utils.redaction")
    from yonerai_cli import cli

    marker = _write_attacker_redaction_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    rc = cli.main(["discord", "synthetic", "hello", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert marker.exists() is False


def test_cli_discord_synthetic_records_redacted_ledger(tmp_path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    ledger = tmp_path / "runs.jsonl"

    rc = cli.main(["discord", "synthetic", "hello", "--json", "--ledger", str(ledger)])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert output["live_discord"] is False
    assert output["run"]["run_id"].startswith("run_")
    assert output["run"]["status"] == "completed"
    assert output["run"]["classification"]["category"] == "synthetic_discord_gateway"
    assert output["ledger"]["file_backed"] is True
    assert str(ledger) not in captured.out
    assert "synthetic_discord_gateway" in ledger.read_text(encoding="utf-8")
