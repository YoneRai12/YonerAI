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
    assert [section["name"] for section in output["sections"]] == [
        "public_core",
        "mode_boundary",
        "route_preview",
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


def test_public_demo_pretty_output_contains_key_sections(capsys) -> None:
    public_demo = _load_public_demo()

    assert public_demo.main(["--pretty"]) == 0

    output = capsys.readouterr().out
    assert "YonerAI public demo" in output
    assert "public_core: ok" in output
    assert "mode_boundary: ok" in output
    assert "route_preview: ok" in output
    assert "hybrid_trust: ok" in output
    assert "managed_download: ok" in output
    assert "self_evolution: ok" in output
    assert "limitations: ok" in output
    assert "official_cloud_runtime_included: false" in output
    assert "deploy_required: false" in output


def test_public_demo_failure_output_redacts_local_paths(monkeypatch, capsys) -> None:
    public_demo = _load_public_demo()
    private_path = "C:" + "\\Users\\dev\\secret.txt"

    def fail_public_core():
        raise AssertionError(f"failed at {private_path}")

    monkeypatch.setattr(public_demo, "_public_core_checks", fail_public_core)

    assert public_demo.main(["--json"]) == 1

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["ok"] is False
    assert output["error"] == "YonerAI public demo failed"
    assert private_path not in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
