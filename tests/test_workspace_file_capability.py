from __future__ import annotations

import json
import sys
from pathlib import Path


def _prepare_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    core_src = repo_root / "core" / "src"
    cli_src = repo_root / "clients" / "cli"
    for path in (core_src, cli_src):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def test_workspace_file_context_reads_utf8_text(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.execution.workspace_files import (
        WORKSPACE_FILE_ACCESS_CAPABILITY,
        WORKSPACE_FILE_ACCESS_COMPAT_ALIASES,
        read_workspace_text_file,
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "note.md"
    target.write_text("# Title\npublic notes", encoding="utf-8")

    context = read_workspace_text_file("note.md", workspace=workspace)
    public = context.to_public_dict()

    assert context.preview_text == "# Title public notes"
    assert public["capability"] == WORKSPACE_FILE_ACCESS_CAPABILITY
    assert public["file_name"] == "note.md"
    assert public["raw_content_persisted"] is False
    assert "preview_text" not in public
    assert WORKSPACE_FILE_ACCESS_COMPAT_ALIASES == ("file_summary",)


def test_workspace_file_rejects_outside_traversal_and_hidden(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.execution.workspace_files import WorkspaceFileError, read_workspace_text_file

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    hidden_dir = workspace / ".hidden"
    hidden_dir.mkdir()
    hidden_file = hidden_dir / "note.txt"
    hidden_file.write_text("hidden", encoding="utf-8")

    for path, code in (("../outside.txt", "outside_workspace"), (".hidden/note.txt", "hidden_file_rejected")):
        try:
            read_workspace_text_file(path, workspace=workspace)
        except WorkspaceFileError as exc:
            assert exc.code == code
            assert str(tmp_path) not in exc.message
        else:
            raise AssertionError("workspace file policy should reject unsafe path")


def test_workspace_file_rejects_large_and_binary(tmp_path: Path) -> None:
    _prepare_paths()
    from ora_core.execution.workspace_files import WorkspaceFileError, read_workspace_text_file

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    large = workspace / "large.txt"
    large.write_text("x" * 100, encoding="utf-8")
    binary = workspace / "image.bin"
    binary.write_bytes(b"\x00\x01\x02")

    for path, code in (("large.txt", "file_too_large"), ("image.bin", "binary_file_rejected")):
        try:
            read_workspace_text_file(path, workspace=workspace, max_bytes=8)
        except WorkspaceFileError as exc:
            assert exc.code == code
        else:
            raise AssertionError("workspace file policy should reject unsafe file")


def test_cli_ask_workspace_file_access_guard_uses_mock_provider_without_raw_file_in_metadata(
    tmp_path: Path, capsys
) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "summary.txt"
    target.write_text("public alpha2 notes", encoding="utf-8")

    rc = cli.main(
        [
            "ask",
            "inspect",
            "selected",
            "file",
            "--file",
            "summary.txt",
            "--workspace",
            str(workspace),
            "--provider",
            "mock",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert output["response"]["provider"] == "mock"
    assert output["file_context"]["capability"] == "workspace_file_access"
    assert output["file_context"]["file_name"] == "summary.txt"
    assert output["file_context"]["raw_content_persisted"] is False
    assert "public alpha2 notes" not in json.dumps(output["file_context"])
    assert str(tmp_path) not in captured.out


def test_cli_ask_file_rejects_without_workspace(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["ask", "inspect", "file", "--file", "note.txt", "--provider", "mock", "--json"])
    captured = capsys.readouterr()

    assert rc == 2
    assert "--workspace is required" in captured.err


def test_cli_ask_file_error_json_does_not_leak_absolute_path(tmp_path: Path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    rc = cli.main(
        [
            "ask",
            "inspect",
            "file",
            "--file",
            "../missing.txt",
            "--workspace",
            str(workspace),
            "--provider",
            "mock",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 1
    assert output["ok"] is False
    assert output["error"]["code"] in {"file_not_found", "outside_workspace"}
    assert str(tmp_path) not in captured.out
