from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
FIXTURE = ROOT / "tests" / "fixtures" / "self_evolution" / "queue_signals.json"
EMPTY_FIXTURE = ROOT / "tests" / "fixtures" / "self_evolution" / "empty_queue_signals.json"
for path in (CLIENTS_CLI, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


class _PlainStringIO(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_queue_signal_rejects_private_or_action_taking_fields() -> None:
    from src.self_evolution import UnsafeSignalError, normalize_queue_signal

    payload = {
        "feature_id": "install.first_run",
        "surface": "installer",
        "mode": "official_bridge",
        "outcome": "blocked",
        "dropoff_stage": "install",
        "complaint_class": "missing_guidance",
        "provider_class": "none",
        "latency_bucket": "none",
    }

    for field in ("raw_prompt", "rawPrompt", "user_id", "api_key", "open_pr", "deploy", "release_note"):
        unsafe = dict(payload)
        unsafe[field] = "unsafe"
        with pytest.raises(UnsafeSignalError):
            normalize_queue_signal(unsafe)

    unsafe_path = dict(payload)
    unsafe_path["complaint_class"] = "missing_guidance"
    unsafe_path["evidence"] = r"C:\Users\fixture\secret.txt"
    with pytest.raises(UnsafeSignalError):
        normalize_queue_signal(unsafe_path)


def test_evolve_status_json_is_proposal_only(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["evolve", "status", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    serialized = json.dumps(output, sort_keys=True)
    assert output["schema_version"] == "yonerai-self-evolution-queue/v0.1"
    assert output["proposal_only"] is True
    assert output["input_policy"]["raw_prompt_allowed"] is False
    assert output["input_policy"]["pii_allowed"] is False
    assert output["input_policy"]["stable_user_tracking_allowed"] is False
    assert "no code mutation" in output["actions_not_performed"]
    assert "C:" + "\\Users" not in serialized
    assert "api_key" not in serialized


def test_evolve_simulate_json_contains_required_candidate_fields(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["evolve", "simulate", "--fixture", str(FIXTURE), "--json"]) == 0

    raw = capsys.readouterr().out
    output = json.loads(raw)
    proposal = output["proposals"][0]
    candidate = proposal["candidate"]
    assert output["dry_run"] is True
    assert output["signal_count"] == 2
    assert proposal["proposal_only"] is True
    assert proposal["github_write_allowed"] is False
    assert proposal["deploy_allowed"] is False
    assert proposal["auto_apply_allowed"] is False
    assert {
        "user_impact",
        "frequency_hint",
        "privacy_risk",
        "implementation_cost",
        "provider_independence_impact",
        "same_experience_impact",
        "test_plan",
        "rollback_plan",
        "release_note_draft",
        "social_post_draft",
    } <= set(candidate)
    assert str(FIXTURE.parent) not in raw


def test_evolve_simulate_preserves_explicit_empty_signal_fixture(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["evolve", "simulate", "--fixture", str(EMPTY_FIXTURE), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["signal_count"] == 0
    assert output["proposal_count"] == 0
    assert output["proposals"] == []


def test_evolve_proposals_list_and_show_are_stable(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["evolve", "proposals", "list", "--fixture", str(FIXTURE), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)

    proposal_id = listed["proposals"][0]["proposal_id"]
    assert proposal_id == "proposal-tui.slash_help"
    assert listed["proposals"][0]["feature_id"] == "tui.slash_help"

    assert cli.main(["evolve", "proposals", "show", proposal_id, "--fixture", str(FIXTURE), "--json"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["proposal"]["proposal_id"] == proposal_id
    assert shown["proposal"]["approval_state"] in {"proposed", "needs_owner"}
    assert shown["proposal"]["candidate"]["rollback_plan"].startswith("Reject or archive")


def test_queue_show_accepts_bounded_long_feature_ids() -> None:
    from src.self_evolution import build_queue_show_report, normalize_queue_signal

    feature_id = "a" * 80
    signal = normalize_queue_signal(
        {
            "feature_id": feature_id,
            "surface": "tui",
            "mode": "local_cli",
            "outcome": "confused",
            "dropoff_stage": "settings",
            "complaint_class": "missing_guidance",
            "provider_class": "mock",
            "latency_bucket": "lt_1s",
        }
    )

    report = build_queue_show_report(f"proposal-{feature_id}", [signal])

    assert report["ok"] is True
    assert report["proposal"]["proposal_id"] == f"proposal-{feature_id}"


def test_tui_evolve_command_is_available_in_japanese_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/自己進化\n/evolve\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "自己進化プロポーザル" in output
    assert "proposal-only" in output
    assert "合成/低解像度signalだけ" in output
    assert "yonerai evolve simulate --pretty --lang ja" in output
    assert str(tmp_path) not in output


def test_tui_slash_completion_includes_evolve_without_english_alias_in_japanese() -> None:
    from yonerai_cli.tui import slash_command_summary, slash_command_words

    words = slash_command_words("ja")
    summary = slash_command_summary("ja")

    assert "/自己進化" in words
    assert "/evolve" not in words
    assert "/自己進化" in summary
    assert "Self-evolution" not in summary


def test_cli_evolve_rejects_missing_or_private_fixture_without_traceback(tmp_path: Path, capsys) -> None:
    from yonerai_cli import cli

    missing = FIXTURE.parent / "missing.json"
    assert cli.main(["evolve", "simulate", "--fixture", str(missing), "--json"]) == 2
    captured = capsys.readouterr()

    assert "self-evolution fixture is unavailable" in captured.err
    assert "Traceback" not in captured.err

    outside = tmp_path / "signals.json"
    outside.write_text('{"signals": []}', encoding="utf-8")
    assert cli.main(["evolve", "simulate", "--fixture", str(outside), "--json"]) == 2
    captured = capsys.readouterr()

    assert "self-evolution fixture must be inside the current workspace" in captured.err
    assert "Traceback" not in captured.err
    assert str(tmp_path) not in captured.err
