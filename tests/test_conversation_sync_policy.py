from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def test_conversation_policy_defaults_and_local_only_boundary(tmp_path: Path) -> None:
    from yonerai_cli.services.conversation_sync_policy_service import (
        build_conversation_policy_set_report,
        build_conversation_policy_status_report,
    )

    store = tmp_path / "conversation-policies.json"
    status = build_conversation_policy_status_report(store_path=store)

    assert status["conversation_count"] == 0
    assert status["defaults"]["local_origin"] == "local_only"
    assert status["defaults"]["cloud_origin"] == "cloud_to_local"

    report = build_conversation_policy_set_report("local-conv-1", "local_only", store_path=store)
    conversation = report["conversation"]

    assert report["ok"] is True
    assert report["sync_performed"] is False
    assert report["local_to_cloud_upload_performed"] is False
    assert report["official_worker_dispatch_performed"] is False
    assert conversation["sync_policy"] == "local_only"
    assert conversation["execution"]["official_worker_allowed"] is False
    assert conversation["execution"]["local_loopback_required"] is True
    assert conversation["memory"]["inherits_conversation_policy"] is True
    assert conversation["memory"]["cloud_memory_index_allowed"] is False


def test_conversation_policy_bidirectional_requires_confirm(tmp_path: Path) -> None:
    from yonerai_cli.services.conversation_sync_policy_service import (
        build_conversation_policy_list_report,
        build_conversation_policy_set_report,
    )

    store = tmp_path / "conversation-policies.json"

    denied = build_conversation_policy_set_report("local-conv-2", "bidirectional_explicit", store_path=store)
    listed_after_denied = build_conversation_policy_list_report(store_path=store)

    assert denied["ok"] is False
    assert denied["decision"]["state"] == "approval_required"
    assert denied["decision"]["written"] is False
    assert listed_after_denied["conversation_count"] == 0

    approved = build_conversation_policy_set_report(
        "local-conv-2",
        "bidirectional_explicit",
        confirm=True,
        store_path=store,
    )

    assert approved["ok"] is True
    assert approved["conversation"]["sync_policy"] == "bidirectional_explicit"
    assert approved["conversation"]["memory"]["cloud_memory_index_allowed"] is True


def test_conversation_policy_cloud_to_local_and_pause(tmp_path: Path) -> None:
    from yonerai_cli.services.conversation_sync_policy_service import (
        build_conversation_policy_pause_report,
        build_conversation_policy_set_report,
    )

    store = tmp_path / "conversation-policies.json"

    cloud = build_conversation_policy_set_report(
        "cloud-conv-1",
        "cloud_to_local",
        origin="cloud",
        store_path=store,
    )
    paused = build_conversation_policy_pause_report("cloud-conv-1", store_path=store)

    assert cloud["conversation"]["origin"] == "cloud"
    assert cloud["conversation"]["sync_policy"] == "cloud_to_local"
    assert cloud["conversation"]["execution"]["official_worker_allowed"] is True
    assert cloud["local_to_cloud_upload_performed"] is False
    assert paused["conversation"]["sync_policy"] == "paused"
    assert paused["conversation"]["execution"]["execution_allowed"] is False


def test_conversation_policy_rejects_private_markers(tmp_path: Path) -> None:
    from yonerai_cli.services.conversation_sync_policy_service import (
        ConversationSyncPolicyError,
        build_conversation_policy_set_report,
    )

    store = tmp_path / "conversation-policies.json"

    try:
        build_conversation_policy_set_report("C:\\Users\\owner\\secret", "local_only", store_path=store)
    except ConversationSyncPolicyError as exc:
        assert exc.code == "conversation_id_private_rejected"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("private local path marker was accepted")


def test_conversation_policy_cli_and_tui_alias(tmp_path: Path, capsys) -> None:
    from yonerai_cli import cli
    from yonerai_cli.tui.aliases import canonical_command

    store = tmp_path / "conversation-policies.json"

    rc = cli.main(
        [
            "sync",
            "conversation",
            "set",
            "conv-1",
            "local_only",
            "--store",
            str(store),
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert output["conversation"]["sync_policy"] == "local_only"
    assert output["conversation"]["execution"]["official_worker_allowed"] is False
    assert canonical_command("/会話") == "/sync"
    assert canonical_command("/conversation") == "/sync"


def test_conversation_policy_cli_requires_confirm_for_bidirectional(tmp_path: Path, capsys) -> None:
    from yonerai_cli import cli

    store = tmp_path / "conversation-policies.json"
    rc = cli.main(
        [
            "sync",
            "conversation",
            "set",
            "conv-2",
            "bidirectional_explicit",
            "--store",
            str(store),
            "--json",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert output["ok"] is False
    assert output["decision"]["state"] == "approval_required"
    assert output["local_to_cloud_upload_performed"] is False
