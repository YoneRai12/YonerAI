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


def test_cli_search_live_is_disabled_by_default(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["search", "live", "YonerAI", "--json"])
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 1
    assert output["ok"] is False
    assert output["network_performed"] is False
    assert output["error"]["code"] == "search_live_disabled"


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
