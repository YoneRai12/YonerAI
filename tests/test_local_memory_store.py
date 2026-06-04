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


def test_local_memory_store_add_list_delete_export_redacts(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.memory import LocalMemoryStore

    store = LocalMemoryStore(tmp_path / "memory.jsonl")
    record = store.add(
        "remember sk-" + ("A" * 24) + " and AIzaSy" + ("B" * 24) + " for public docs",
        tags=("Alpha2", "safe_tag"),
    )
    listed = store.list()
    exported = store.export()

    assert record.memory_id.startswith("mem_")
    assert "sk-" not in record.text
    assert "AIzaSy" not in record.text
    assert listed[0].tags == ("alpha2", "safe_tag")
    assert exported["cloud_synced"] is False
    assert store.delete(record.memory_id) is True
    assert store.list() == []


def test_cli_memory_add_requires_confirm_local(tmp_path: Path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    store = tmp_path / "memory.jsonl"
    rc = cli.main(["memory", "add", "remember", "this", "--store", str(store), "--json"])
    captured = capsys.readouterr()

    assert rc == 2
    assert "requires --confirm-local" in captured.err
    assert not store.exists()


def test_cli_memory_add_list_delete(tmp_path: Path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    store = tmp_path / "memory.jsonl"
    rc_add = cli.main(
        [
            "memory",
            "add",
            "remember",
            "public",
            "docs",
            "--store",
            str(store),
            "--confirm-local",
            "--tag",
            "alpha2",
            "--json",
        ]
    )
    add_output = json.loads(capsys.readouterr().out)
    memory_id = add_output["record"]["memory_id"]
    rc_list = cli.main(["memory", "list", "--store", str(store), "--json"])
    list_output = json.loads(capsys.readouterr().out)
    rc_delete = cli.main(["memory", "delete", memory_id, "--store", str(store), "--json"])
    delete_output = json.loads(capsys.readouterr().out)

    assert rc_add == 0
    assert add_output["cloud_synced"] is False
    assert add_output["raw_prompt_persisted"] is False
    assert rc_list == 0
    assert list_output["count"] == 1
    assert list_output["records"][0]["tags"] == ["alpha2"]
    assert rc_delete == 0
    assert delete_output["deleted"] is True
    assert str(tmp_path) not in json.dumps(add_output)


def test_cli_memory_export_is_local_only(tmp_path: Path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    store = tmp_path / "memory.jsonl"
    assert cli.main(["memory", "add", "alpha", "--store", str(store), "--confirm-local", "--json"]) == 0
    capsys.readouterr()
    rc = cli.main(["memory", "export", "--store", str(store), "--json"])
    output = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert output["operation"] == "export"
    assert output["cloud_synced"] is False
    assert output["count"] == 1

def test_cli_memory_add_uses_repo_redactor_outside_repo_root(tmp_path: Path, capsys, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    monkeypatch.chdir(tmp_path)
    store = tmp_path / "memory.jsonl"
    token_param = "access" + "_token"
    webhook_host = "discord.com" + "/api/webhooks"
    text = (
        f"callback https://example.test/cb?{token_param}=LEAKED_QUERY_TOKEN "
        f"and webhook https://{webhook_host}/123456789012345678/AbCdEfGhIjKlMnOpQrStUvWxYz-12345"
    )
    rc = cli.main(["memory", "add", text, "--store", str(store), "--confirm-local", "--json"])
    output = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert output["raw_prompt_persisted"] is False
    assert "text" not in output["record"]
    assert output["record"]["raw_text_included"] is False
    assert "LEAKED_QUERY_TOKEN" not in output["record"]["redacted_summary"]
    assert "discord.com/api/webhooks" not in output["record"]["redacted_summary"]


def test_memory_record_has_boundary_fields_and_forget_is_redacted(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.memory import LocalMemoryStore

    store = LocalMemoryStore(tmp_path / "memory.jsonl")
    record = store.add("prefer concise Japanese answers", scope="procedural", tags=("Preference",))
    forgotten = store.forget(record.id)
    inactive = store.list(include_inactive=True)[0]

    assert record.scope == "procedural"
    assert record.sync_policy == "local_to_cloud_requires_approval"
    assert record.status == "active"
    assert record.to_public_dict()["raw_prompt_persisted"] is False
    assert forgotten is True
    assert store.list() == []
    assert inactive.status == "forgotten"
    assert inactive.redacted_summary == "[forgotten]"
    assert inactive.sync_policy == "never_sync"


def test_cli_memory_status_add_list_forget_and_sync_preview(tmp_path: Path, capsys, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    store = tmp_path / "memory.jsonl"
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(store))

    assert cli.main(["memory", "status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["store_path_output"] is False
    assert str(tmp_path) not in json.dumps(status)

    assert cli.main(["memory", "add", "local preference", "--scope", "local", "--json"]) == 0
    added = json.loads(capsys.readouterr().out)
    memory_id = added["record"]["memory_id"]
    assert added["record"]["scope"] == "local_private"
    assert added["record"]["sync_policy"] == "never_sync"
    assert "text" not in added["record"]
    assert added["record"]["raw_text_included"] is False

    assert cli.main(["memory", "status", "--json"]) == 0
    status_after_add = json.loads(capsys.readouterr().out)
    serialized_status = json.dumps(status_after_add, ensure_ascii=False)
    assert status_after_add["recent_records_included"] is False
    assert "local preference" not in serialized_status
    assert memory_id not in serialized_status

    assert cli.main(["memory", "list", "--scope", "local", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["count"] == 1
    assert "text" not in listed["records"][0]
    assert listed["records"][0]["raw_text_included"] is False

    assert cli.main(["memory", "sync", "preview", "--direction", "local-to-cloud", "--json"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["decision"]["state"] == "blocked"
    assert preview["decision"]["reason"] == "local_private_memory_never_syncs"
    assert preview["official_backend_called"] is False
    assert "no automatic local-to-cloud upload" in preview["actions_not_performed"]

    assert cli.main(["memory", "forget", memory_id, "--json"]) == 0
    forgotten = json.loads(capsys.readouterr().out)
    assert forgotten["forgotten"] is True
    assert str(tmp_path) not in json.dumps(forgotten)


def test_cli_memory_cloud_preview_config_blocks_standalone_sync(tmp_path: Path, capsys, monkeypatch) -> None:
    _prepare_paths()
    from yonerai_cli import cli
    from yonerai_cli.config import DEFAULT_CONFIG, save_cli_config

    config_path = tmp_path / "cli-config.json"
    config = dict(DEFAULT_CONFIG)
    config["memory_cloud_to_local_preview_enabled"] = False
    save_cli_config(config, config_path)
    monkeypatch.setenv("YONERAI_CLI_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("YONERAI_MEMORY_STORE_PATH", str(tmp_path / "memory.jsonl"))

    assert cli.main(["memory", "sync", "preview", "--direction", "cloud-to-local", "--json"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["decision"]["state"] == "blocked"
    assert preview["decision"]["reason"] == "cloud_to_local_preview_disabled_by_config"
    assert preview["sync_allowed"] is False
    assert preview["sync_performed"] is False
    assert "cloud-to-local memory preview disabled by CLI config" in preview["actions_not_performed"]

    assert cli.main(["memory", "status", "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["sync_previews"]["cloud_to_local"]["decision"]["state"] == "blocked"
    assert status["sync_previews"]["cloud_to_local"]["decision"]["reason"] == "cloud_to_local_preview_disabled_by_config"
    assert str(tmp_path) not in json.dumps(status)


def test_secret_like_memory_is_redacted_and_never_syncs(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.memory import LocalMemoryStore, build_memory_sync_preview

    store = LocalMemoryStore(tmp_path / "memory.jsonl")
    record = store.add("token=alpha-secret-fixture and C:\\Users\\person\\secret.txt", scope="shared_preference")
    preview = build_memory_sync_preview(store.list(), direction="local_to_cloud", explicit_approval=True)
    serialized = json.dumps(record.to_public_dict(), ensure_ascii=False)

    assert record.sensitivity == "secret_like"
    assert record.sync_policy == "never_sync"
    assert "alpha-secret-fixture" not in serialized
    assert "C:\\Users" not in serialized
    assert preview["decision"]["state"] == "blocked"
    assert preview["decision"]["reason"] == "secret_like_or_local_only_memory_never_syncs"


def test_local_path_memory_is_local_only_and_never_syncs(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.memory import LocalMemoryStore, build_memory_sync_preview

    store = LocalMemoryStore(tmp_path / "memory.jsonl")
    record = store.add("review C:\\Users\\person\\Documents\\private.txt later", scope="shared_preference")
    preview = build_memory_sync_preview(store.list(), direction="local_to_cloud", explicit_approval=True)
    serialized = json.dumps(record.to_public_dict(), ensure_ascii=False)

    assert record.sensitivity == "local_only"
    assert record.sync_policy == "never_sync"
    assert "C:\\Users" not in serialized
    assert "[local_path_redacted]" in serialized
    assert preview["decision"]["state"] == "blocked"
    assert preview["decision"]["reason"] == "secret_like_or_local_only_memory_never_syncs"


def test_unix_local_path_memory_roots_are_redacted_without_slash_command_false_positive(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.memory import LocalMemoryStore, build_memory_sync_preview

    unix_paths = (
        "/workspace/YonerAI/.env",
        "/opt/app/secret.txt",
        "/mnt/c/Users/person/private.txt",
        "/srv/data/key",
    )
    for index, local_path in enumerate(unix_paths):
        store = LocalMemoryStore(tmp_path / f"memory-{index}.jsonl")
        record = store.add(f"review {local_path} later", scope="shared_preference")
        preview = build_memory_sync_preview(store.list(), direction="local_to_cloud", explicit_approval=True)
        serialized = json.dumps(record.to_public_dict(), ensure_ascii=False)

        assert record.sensitivity == "local_only"
        assert record.sync_policy == "never_sync"
        assert local_path not in serialized
        assert "[local_path_redacted]" in serialized
        assert record.to_public_dict()["local_absolute_path_persisted"] is False
        assert preview["decision"]["state"] == "blocked"
        assert preview["decision"]["reason"] == "secret_like_or_local_only_memory_never_syncs"

    command_store = LocalMemoryStore(tmp_path / "command-memory.jsonl")
    command_record = command_store.add("remember /help and /api/v1/status routes", scope="shared_preference")
    command_serialized = json.dumps(command_record.to_public_dict(), ensure_ascii=False)

    assert command_record.sensitivity != "local_only"
    assert "/help" in command_serialized
    assert "/api/v1/status" in command_serialized


def test_memory_sync_preview_honors_per_record_sync_policy(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.memory import LocalMemoryStore, build_memory_sync_preview

    store = LocalMemoryStore(tmp_path / "memory.jsonl")
    record = store.add("low resolution feature signal", scope="self_evolution_signal")
    preview = build_memory_sync_preview(store.list(), direction="local_to_cloud", explicit_approval=True)

    assert record.sync_policy == "never_sync"
    assert preview["decision"]["state"] == "blocked"
    assert preview["decision"]["reason"] == "record_sync_policy_does_not_allow_local_to_cloud"
    assert preview["sync_allowed"] is False


def test_cli_memory_store_read_error_is_controlled(tmp_path: Path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    directory = tmp_path / "memory-dir"
    directory.mkdir()

    result = cli.main(["ask", "hello", "--auto", "--memory-store", str(directory), "--json"])
    captured = capsys.readouterr()

    assert result == 1
    assert "failed to read local memory store" in captured.err
    assert captured.out == ""
    assert str(tmp_path) not in captured.err


def test_self_evolution_signal_memory_is_low_resolution_only() -> None:
    _prepare_paths()
    from ora_core.memory import MemoryStoreError, build_self_evolution_signal_memory

    signal = build_self_evolution_signal_memory(
        {
            "feature_id": "tui.memory",
            "surface": "cli",
            "mode": "local",
            "outcome": "completed",
            "dropoff_stage": "none",
            "complaint_class": "none",
            "provider_class": "mock",
            "latency_bucket": "lt_1s",
        }
    )
    public = signal.to_public_dict()

    assert public["scope"] == "self_evolution_signal"
    assert public["proposal_only"] is True
    assert public["raw_prompt_included"] is False
    assert public["pii_included"] is False

    try:
        build_self_evolution_signal_memory(
            {
                "feature_id": "tui.memory",
                "surface": "cli",
                "mode": "local",
                "outcome": "completed",
                "dropoff_stage": "none",
                "complaint_class": "none",
                "provider_class": "mock",
                "latency_bucket": "lt_1s",
                "raw_prompt": "my private prompt",
            }
        )
    except MemoryStoreError as exc:
        assert exc.code == "unsafe_self_evolution_signal"
    else:
        raise AssertionError("raw prompt field must be rejected")
