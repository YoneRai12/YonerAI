from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLIENTS_CLI = ROOT / "clients" / "cli"
if str(CLIENTS_CLI) not in sys.path:
    sys.path.insert(0, str(CLIENTS_CLI))


def test_provider_sharing_default_off_and_requires_confirm(tmp_path: Path) -> None:
    from yonerai_cli.services.provider_sharing_service import (
        build_provider_sharing_enable_report,
        build_provider_sharing_status_report,
    )

    store = tmp_path / "provider-sharing.json"
    status = build_provider_sharing_status_report(store_path=store)
    denied = build_provider_sharing_enable_report("conv-1", store_path=store)
    status_after_denied = build_provider_sharing_status_report(store_path=store)

    assert status["shared_traffic_default"] is False
    assert status["implicit_consent_allowed"] is False
    assert status["conversation_count"] == 0
    assert denied["ok"] is False
    assert denied["decision"]["state"] == "approval_required"
    assert denied["decision"]["written"] is False
    assert denied["error"]["code"] == "provider_sharing_consent_required"
    assert status_after_denied["conversation_count"] == 0


def test_provider_sharing_enable_disable_and_local_only_rejection(tmp_path: Path) -> None:
    from yonerai_cli.services.provider_sharing_service import (
        build_provider_sharing_disable_report,
        build_provider_sharing_enable_report,
        build_provider_sharing_status_report,
    )

    store = tmp_path / "provider-sharing.json"
    local_only = build_provider_sharing_enable_report(
        "conv-local",
        sync_policy="local_only",
        confirm=True,
        store_path=store,
    )
    enabled = build_provider_sharing_enable_report("conv-2", confirm=True, store_path=store)
    status = build_provider_sharing_status_report(conversation_id="conv-2", store_path=store)
    disabled = build_provider_sharing_disable_report("conv-2", store_path=store)

    assert local_only["ok"] is False
    assert local_only["error"]["code"] == "local_only_provider_sharing_rejected"
    assert enabled["ok"] is True
    assert enabled["conversation"]["provider_data_policy"] == "openai_shared_explicit"
    assert enabled["conversation"]["raw_body_stored"] is False
    assert enabled["conversation"]["provider_key_stored"] is False
    assert status["conversation"]["consent_state"] == "enabled"
    assert disabled["conversation"]["provider_data_policy"] == "none"
    assert disabled["conversation"]["consent_state"] == "disabled"


def test_provider_sharing_resolution_and_context_preview(tmp_path: Path) -> None:
    from yonerai_cli.services.provider_sharing_service import (
        ProviderSharingError,
        build_context_preview,
        build_provider_sharing_enable_report,
        resolve_provider_data_policy,
    )

    store = tmp_path / "provider-sharing.json"
    local = resolve_provider_data_policy(
        conversation_id="conv-local",
        sync_policy="local_only",
        requested_policy=None,
        store_path=store,
    )
    assert local["provider_data_policy"] == "local_provider"
    assert local["openai_shared_traffic_enabled"] is False

    try:
        resolve_provider_data_policy(
            conversation_id="conv-3",
            sync_policy="cloud_to_local",
            requested_policy="openai_shared_explicit",
            store_path=store,
        )
    except ProviderSharingError as exc:
        assert exc.code == "provider_sharing_consent_required"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("OpenAI shared traffic was allowed without consent")

    build_provider_sharing_enable_report("conv-3", confirm=True, store_path=store)
    shared = resolve_provider_data_policy(
        conversation_id="conv-3",
        sync_policy="cloud_to_local",
        requested_policy="openai_shared_explicit",
        store_path=store,
    )
    preview = build_context_preview(prompt="hello world", provider_policy=shared)

    assert shared["provider_data_policy"] == "openai_shared_explicit"
    assert shared["openai_shared_traffic_enabled"] is True
    assert preview["current_message_included"] is True
    assert preview["full_history_included"] is False
    assert "local/workspace files" in preview["excluded_data_categories"]


def test_provider_sharing_cli(tmp_path: Path, capsys) -> None:
    from yonerai_cli import cli

    store = tmp_path / "provider-sharing.json"
    rc = cli.main(["privacy", "provider-sharing", "enable", "conv-4", "--store", str(store), "--json"])
    denied = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert denied["error"]["code"] == "provider_sharing_consent_required"

    rc = cli.main(["privacy", "provider-sharing", "enable", "conv-4", "--confirm", "--store", str(store), "--json"])
    enabled = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert enabled["conversation"]["provider_data_policy"] == "openai_shared_explicit"

    rc = cli.main(["privacy", "provider-sharing", "status", "conv-4", "--store", str(store), "--json"])
    status = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert status["conversation"]["consent_state"] == "enabled"
