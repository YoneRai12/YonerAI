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
