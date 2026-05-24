from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_public_demo():
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    for path in (repo_root, core_src):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)

    from scripts.dev import public_demo

    return public_demo


def test_public_demo_json_shape_and_boundaries(capsys) -> None:
    public_demo = _load_public_demo()

    assert public_demo.main(["--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["contract"] == "yonerai-public-demo/v1"
    assert output["schema_version"] == "1.0"
    assert output["cli_entrypoint"] == "yonerai demo"
    assert output["quickstart_alias"] == "yonerai quickstart"
    assert [section["name"] for section in output["sections"]] == [
        "public_core",
        "mode_boundary",
        "route_preview",
        "provider_planner",
        "execution_spine",
        "hybrid_trust",
        "managed_download",
        "self_evolution",
        "limitations",
    ]
    assert output["credentials_required"] is False
    assert output["network_required"] is False
    assert output["oracle_required"] is False
    assert output["live_discord_required"] is False
    assert output["persistent_memory_required"] is False
    assert output["google_login_required"] is False
    assert output["deploy_required"] is False
    assert output["official_cloud_runtime_included"] is False
    assert output["production_trust_material"] is False
    assert "session_id" not in json.dumps(output).lower()
    self_evolution = next(section for section in output["sections"] if section["name"] == "self_evolution")
    memory_fixture = next(
        check for check in self_evolution["checks"] if check["name"] == "memory_candidate_fixture_quarantined"
    )
    assert memory_fixture["donation_action"] == "quarantine"
    assert memory_fixture["trusted"] is False
    assert memory_fixture["approval_required"] is True
    assert memory_fixture["memory_status"] == "quarantined"
    assert memory_fixture["memory_persisted"] is False
    provider_planner = next(section for section in output["sections"] if section["name"] == "provider_planner")
    registry = next(check for check in provider_planner["checks"] if check["name"] == "provider_registry")
    external = next(check for check in provider_planner["checks"] if check["name"] == "external_provider_availability")
    search = next(check for check in provider_planner["checks"] if check["name"] == "mock_web_search")
    dangerous = next(check for check in provider_planner["checks"] if check["name"] == "dangerous_shell_plan")
    download = next(check for check in provider_planner["checks"] if check["name"] == "download_guard_plan")
    assert registry["provider"] == "mock"
    assert registry["live_call_performed"] is False
    assert external["live_call_performed"] is False
    assert search["network_performed"] is False
    assert dangerous["approval_required"] is True
    assert download["network_performed"] is False
    execution_spine = next(section for section in output["sections"] if section["name"] == "execution_spine")
    mock_execution = next(check for check in execution_spine["checks"] if check["name"] == "mock_provider_execution")
    legacy = next(check for check in execution_spine["checks"] if check["name"] == "legacy_ora_text_normalizer")
    tool_boundaries = next(check for check in execution_spine["checks"] if check["name"] == "search_tool_boundaries")
    memory = next(check for check in execution_spine["checks"] if check["name"] == "local_memory_opt_in")
    assert mock_execution["run_status"] == "completed"
    assert mock_execution["raw_prompt_persisted"] is False
    assert legacy["execution_spine_connected"] is True
    assert legacy["broad_ora_refactor"] is False
    assert tool_boundaries["live_tool_execution"] is False
    assert tool_boundaries["ora_tool_schema_boundary"] == "ok"
    assert tool_boundaries["ora_guardrail_response_interpreter"] == "ok"
    assert tool_boundaries["guardrail_provider_call_performed"] is False
    assert memory["cloud_synced"] is False
    assert memory["raw_prompt_persisted"] is False
    hybrid_trust = next(section for section in output["sections"] if section["name"] == "hybrid_trust")
    discord = next(check for check in hybrid_trust["checks"] if check["name"] == "synthetic_discord_gateway")
    assert discord["live_discord"] is False
    assert discord["token_required"] is False
    assert discord["final_once"] is True
    managed = next(section for section in output["sections"] if section["name"] == "managed_download")
    official_status = next(check for check in managed["checks"] if check["name"] == "official_status_contract")
    installer = next(check for check in managed["checks"] if check["name"] == "windows_install_dry_run")
    assert official_status["official_cloud_runtime_included"] is False
    assert official_status["oracle_control_plane_production_ready"] is False
    assert installer["dry_run"] is True
    assert installer["install_performed"] is False
    assert installer["path_mutation"] is False


def test_public_demo_pretty_output_contains_key_sections(capsys) -> None:
    public_demo = _load_public_demo()

    assert public_demo.main(["--pretty"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI public demo" in output
    assert "YonerAI CLI:" in output
    assert "command: yonerai demo --pretty" in output
    assert "json: yonerai demo --json" in output
    assert "quickstart_alias: yonerai quickstart" in output
    assert "Schema: 1.0" in output
    assert "Demo Experience:" in output
    assert "Managed Cloud external contract-only" in output
    assert "public_core: ok" in output
    assert "mode_boundary: ok" in output
    assert "route_preview: ok" in output
    assert "provider_planner: ok" in output
    assert "execution_spine: ok" in output
    assert "hybrid_trust: ok" in output
    assert "managed_download: ok" in output
    assert "self_evolution: ok" in output
    assert "limitations: ok" in output
    assert "official_cloud_runtime_included: false" in output
    assert "deploy_required: false" in output
    assert "managed_download_guard" in output
    assert "mock_provider_response" in output
    assert "task_category=summarize_public" in output
    assert "live_call_performed=false" in output
    assert "mock_provider_execution" in output
    assert "legacy_ora_text_normalizer" in output
    assert "raw_prompt_persisted=false" in output
    assert "github_write_allowed=false" in output
    assert "memory_candidate_fixture_quarantined" in output
    assert "donation_action=quarantine" in output
    assert "memory_status=quarantined" in output
    assert "external_provider_availability" in output
    assert "mock_web_search" in output
    assert "local_memory_opt_in" in output
    assert "synthetic_discord_gateway" in output
    assert "live_discord=false" in output
    assert "official_status_contract" in output
    assert "windows_install_dry_run" in output
    assert "dry_run=true" in output


def test_public_demo_uses_managed_download_guard(monkeypatch) -> None:
    public_demo = _load_public_demo()
    from ora_core.brain.process import MainProcess

    calls: list[str] = []

    def fake_coerce_download_link(self, *, url, label=None, file_id=None):
        del self, label, file_id
        calls.append(url)
        if str(url).startswith("/v1/files/"):
            return {"url": url}
        return None

    monkeypatch.setattr(MainProcess, "_coerce_download_link", fake_coerce_download_link)

    checks = public_demo._managed_download_checks()

    assert calls == ["/v1/files/public-demo/download", "https://example.com/not-managed.bin"]
    assert checks[0]["name"] == "managed_url_accepted"
    assert checks[0]["guard"] == "managed_download_guard"
    assert checks[1]["name"] == "unsafe_url_rejected"
    assert checks[1]["guard"] == "managed_download_guard"


def test_public_demo_failure_output_redacts_local_paths(monkeypatch, capsys) -> None:
    public_demo = _load_public_demo()
    sample_path = chr(67) + ":" + "\\LocalDemo\\fixture.txt"

    def fail_public_core():
        raise AssertionError(f"failed at {sample_path}")

    monkeypatch.setattr(public_demo, "_public_core_checks", fail_public_core)

    assert public_demo.main(["--json"]) == 1

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["error"] == "YonerAI public demo failed"
    assert sample_path not in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
