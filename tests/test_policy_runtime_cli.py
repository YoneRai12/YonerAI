from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = REPO_ROOT / "clients" / "cli"
CORE_SRC = REPO_ROOT / "core" / "src"
for path in (CLIENTS_CLI, CORE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


class _PlainStringIO(io.StringIO):
    def isatty(self) -> bool:
        return False


def test_policy_report_is_public_safe_by_default() -> None:
    from ora_core.policies import build_policy_status_report

    report = build_policy_status_report()

    assert report["schema_version"] == "yonerai-policy-runtime/v0.1"
    assert report["policies"]["provider"]["default_provider"] == "mock"
    assert report["policies"]["provider"]["key_storage_supported"] is False
    assert report["policies"]["provider"]["key_output_allowed"] is False
    assert report["policies"]["runtime"]["official_cloud_runtime_in_public_repo"] is False
    assert report["policies"]["runtime"]["production_oracle_in_public_repo"] is False
    assert report["policies"]["memory_sync"]["local_private_auto_upload"] is False
    assert report["policies"]["permission"]["arbitrary_shell_execution"] is False
    assert "no network fetch" in report["actions_not_performed"]

    serialized = json.dumps(report, ensure_ascii=False)
    assert "C:\\Users" not in serialized
    assert "/Users/" not in serialized
    assert "api_key" not in serialized.lower()


def test_policy_report_exposes_public_schema_contract() -> None:
    from ora_core.policies import (
        build_policy_schema_report,
        build_policy_status_report,
        validate_policy_runtime_contract,
    )

    report = build_policy_status_report()
    schema = build_policy_schema_report()

    assert report["policy_schema"] == schema
    assert schema["schema_version"] == "yonerai-policy-schema/v0.1"
    assert schema["policy_types"]["provider"]["config_keys"] == ["provider_preference", "live_provider_enabled"]
    assert "arbitrary_shell_execution" in schema["policy_types"]["permission"]["fixed_disabled"]
    assert "local_private_auto_upload" in schema["policy_types"]["memory_sync"]["fixed_disabled"]
    assert schema["redaction_boundary"]["contains_secrets"] is False
    assert schema["redaction_boundary"]["contains_local_paths"] is False
    assert validate_policy_runtime_contract(report) == []


def test_policy_runtime_ignores_unsafe_config_attempts_and_validator_fails_closed() -> None:
    from ora_core.policies import build_policy_status_report, validate_policy_runtime_contract

    report = build_policy_status_report(
        {
            "live_provider_enabled": True,
            "openai_data_sharing_enabled": True,
            "approval_mode": "deny",
            "file_access_mode": "disabled",
            "tools_mode": "disabled",
            "update_notice_enabled": True,
            "memory_enabled": False,
            "memory_default_scope": "procedural",
            "memory_cloud_to_local_preview_enabled": False,
            "arbitrary_shell_execution": True,
            "production_oracle_in_public_repo": True,
            "official_cloud_runtime_in_public_repo": True,
            "local_private_auto_upload": True,
        }
    )

    assert report["policies"]["provider"]["live_external_provider_enabled"] is True
    assert report["policies"]["pricing"]["shared_traffic_enabled"] is True
    assert report["policies"]["permission"]["approval_mode"] == "deny"
    assert report["policies"]["permission"]["arbitrary_shell_execution"] is False
    assert report["policies"]["runtime"]["production_oracle_in_public_repo"] is False
    assert report["policies"]["runtime"]["official_cloud_runtime_in_public_repo"] is False
    assert report["policies"]["memory_sync"]["memory_enabled"] is False
    assert report["policies"]["memory_sync"]["default_scope"] == "procedural"
    assert report["policies"]["memory_sync"]["local_private_auto_upload"] is False
    assert validate_policy_runtime_contract(report) == []

    tampered = json.loads(json.dumps(report))
    tampered["policies"]["runtime"]["production_oracle_in_public_repo"] = True
    tampered["policies"]["permission"]["arbitrary_shell_execution"] = True
    tampered["policies"]["memory_sync"]["local_private_auto_upload"] = True

    errors = validate_policy_runtime_contract(tampered)
    assert "runtime.production_oracle_in_public_repo must be false" in errors
    assert "permission.arbitrary_shell_execution must be false" in errors
    assert "memory_sync.local_private_auto_upload must be false" in errors


def test_policy_status_json_uses_local_config_without_secret_or_path_leak(tmp_path: Path, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    config_path.write_text(
        json.dumps(
            {
                "language": "ja",
                "provider_preference": "local",
                "model_preference": "llama3.1",
                "memory_enabled": False,
                "live_provider_enabled": False,
            }
        ),
        encoding="utf-8",
    )

    assert cli.main(["policy", "status", "--json", "--config-path", str(config_path)]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["policies"]["provider"]["preference"] == "local"
    assert output["policies"]["model"]["preference"] == "llama3.1"
    assert output["policies"]["memory_sync"]["memory_enabled"] is False
    assert str(tmp_path) not in json.dumps(output, ensure_ascii=False)


def test_policy_status_pretty_is_japanese_and_has_no_ansi_when_disabled(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["policy", "status", "--pretty", "--lang", "ja", "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "YonerAI ポリシー状態" in output
    assert "提供元とモデル" in output
    assert "任意shell" in output
    assert "\u30dd\u30ea\u30b7\u30fc\u69cb\u9020" in output
    assert "\u8a2d\u5b9a\u3067\u5909\u3048\u3089\u308c\u308b" in output
    assert "\u56fa\u5b9a\u3067\u7121\u52b9" in output
    assert "\u5c06\u6765\u5019\u88dc" in output
    assert "arbitrary_shell_execution" in output
    assert "signed_update_policy" in output
    assert "\x1b[" not in output


def test_policy_status_missing_core_returns_controlled_error(monkeypatch) -> None:
    from yonerai_cli.commands import policy

    original_find_spec = importlib.util.find_spec

    def fake_find_spec(name: str, *args: object, **kwargs: object) -> object:
        if name in {"ora_core", "ora_core.policies"}:
            return None
        return original_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(policy.importlib.util, "find_spec", fake_find_spec)

    args = argparse.Namespace(policy_command="status", json=True, lang="ja", color="never")
    with pytest.raises(ValueError, match="policy status report is unavailable"):
        policy.handle_policy_command(args, config={}, print_json=lambda _data: None)


def test_policy_pretty_uses_runtime_report_values_instead_of_ui_constants() -> None:
    from ora_core.policies import build_policy_status_report
    from yonerai_cli.screens.policy import format_policy_status_pretty

    report = build_policy_status_report(
        {
            "provider_preference": "local",
            "model_preference": "llama3.1",
            "approval_mode": "deny",
            "file_access_mode": "disabled",
            "tools_mode": "disabled",
            "memory_enabled": False,
            "memory_default_scope": "procedural",
            "update_notice_enabled": True,
        }
    )

    output = format_policy_status_pretty(report, lang="en", color="never")

    assert "local (default=mock)" in output
    assert "llama3.1 / configurable=True" in output
    assert "approval" in output and ": deny" in output
    assert "file access" in output and ": disabled" in output
    assert "tools" in output and ": disabled" in output
    assert "memory" in output and "enabled=False scope=procedural" in output
    assert "\x1b[" not in output


def test_auth_and_privacy_commands_still_route_after_command_split(capsys) -> None:
    from yonerai_cli import cli

    assert cli.main(["auth", "status", "--json"]) == 0
    auth_report = json.loads(capsys.readouterr().out)
    assert auth_report["production_login_enabled"] is False

    assert cli.main(["privacy", "status", "--json"]) == 0
    privacy_report = json.loads(capsys.readouterr().out)
    assert privacy_report["data_sharing"]["openai_shared_traffic_enabled"] is False


def test_tui_exposes_policy_command_and_settings_category() -> None:
    from yonerai_cli.tui import slash_command_summary, slash_command_words

    words = slash_command_words("ja")
    summary = slash_command_summary("ja")

    assert "/ポリシー" in words
    assert "/方針" in words
    assert "/policy" not in words
    assert "/ポリシー" in summary


def test_interactive_policy_screen_uses_callback(tmp_path: Path, monkeypatch, capsys) -> None:
    from yonerai_cli import cli

    config_path = tmp_path / "cli-config.json"
    monkeypatch.setattr(sys, "stdin", _PlainStringIO("/設定\n/ポリシー\n/設定 ポリシー\n/終了\n"))

    assert cli.main(["chat", "--script", "--lang", "ja", "--config-path", str(config_path), "--color", "never"]) == 0
    output = capsys.readouterr().out

    assert "YonerAI ポリシー状態" in output
    assert "提供元とモデル" in output
    assert "/設定 ポリシー" in output
    assert "ポリシー: ローカル設定 + 公開契約" in output
    assert str(tmp_path) not in output


def test_interactive_home_policy_line_uses_policy_callback(tmp_path: Path) -> None:
    from yonerai_cli.config import DEFAULT_CONFIG, save_cli_config
    from yonerai_cli.interactive import InteractiveCallbacks, InteractiveOptions, run_interactive_cli

    config_path = tmp_path / "cli-config.json"
    config = dict(DEFAULT_CONFIG)
    config["language"] = "ja"
    save_cli_config(config, config_path)

    def providers() -> dict[str, Any]:
        return {"providers": []}

    def ask_auto(*_args: Any) -> dict[str, Any]:
        return {"ok": True, "response": {"output_text": "ok"}}

    def runs_list(*_args: Any) -> dict[str, Any]:
        return {"runs": []}

    def runs_show(*_args: Any) -> dict[str, Any]:
        return {"ok": False}

    def policy_status(_config: dict[str, object]) -> dict[str, Any]:
        return {
            "policies": {
                "provider": {"live_external_provider_enabled": True},
                "permission": {
                    "approval_mode": "deny",
                    "file_access_mode": "disabled",
                    "tools_mode": "disabled",
                    "arbitrary_shell_execution": False,
                },
                "runtime": {
                    "official_cloud_runtime_in_public_repo": False,
                    "production_oracle_in_public_repo": False,
                },
                "update": {"auto_apply_enabled": False},
                "memory_sync": {"local_private_auto_upload": False},
            }
        }

    stdout = _PlainStringIO()
    rc = run_interactive_cli(
        InteractiveOptions(config_path=str(config_path), script=True, color="never"),
        InteractiveCallbacks(
            providers=providers,
            ask_auto=ask_auto,
            runs_list=runs_list,
            runs_show=runs_show,
            policy_status=policy_status,
        ),
        stdin=_PlainStringIO("/終了\n"),
        stdout=stdout,
    )
    output = stdout.getvalue()

    assert rc == 0
    assert "外部live=オン" in output
    assert "承認=拒否" in output
    assert "ファイル=無効" in output
    assert "ツール=disabled" in output
    assert "任意shell=無効" in output
    assert "公式Oracle=無効" in output
    assert "local->cloud自動同期=なし" in output
    assert str(tmp_path) not in output
