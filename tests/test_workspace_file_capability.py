from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


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
    from ora_core.execution.workspace_files import read_workspace_text_file

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "note.md"
    target.write_text("# Title\npublic notes", encoding="utf-8")

    context = read_workspace_text_file("note.md", workspace=workspace)
    public = context.to_public_dict()

    assert context.preview_text == "# Title public notes"
    assert context.capability == "workspace_file_access"
    assert context.line_count == 2
    assert context.word_count == 4
    assert public["capability"] == "workspace_file_access"
    assert public["file_name"] == "note.md"
    assert public["line_count"] == 2
    assert public["word_count"] == 4
    assert public["raw_content_persisted"] is False
    assert "preview_text" not in public


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


def test_cli_ask_file_summary_uses_mock_provider_without_raw_file_in_metadata(tmp_path: Path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "summary.txt"
    target.write_text("public alpha2 notes", encoding="utf-8")

    rc = cli.main(
        [
            "ask",
            "summarize",
            "this",
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
    assert output["response"]["model"] == "mock-workspace-file-summary"
    assert "alpha2" in output["response"]["output_text"]
    assert "public alpha2 notes" not in output["response"]["output_text"]
    assert "No live provider call was made" in output["response"]["output_text"]
    assert output["file_context"]["capability"] == "workspace_file_access"
    assert output["file_context"]["file_name"] == "summary.txt"
    assert output["file_context"]["raw_content_persisted"] is False
    assert "public alpha2 notes" not in json.dumps(output["file_context"])
    assert "public alpha2 notes" not in json.dumps(output["plan"])
    assert "public alpha2 notes" not in json.dumps(output["run"])
    assert str(tmp_path) not in captured.out


def test_cli_ask_file_records_redacted_workspace_access_event_in_ledger(tmp_path: Path, capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "summary.txt"
    target.write_text("public alpha2 notes", encoding="utf-8")
    ledger = tmp_path / "runs.jsonl"

    rc = cli.main(
        [
            "ask",
            "summarize",
            "this",
            "file",
            "--file",
            "summary.txt",
            "--workspace",
            str(workspace),
            "--provider",
            "mock",
            "--ledger",
            str(ledger),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    run_id = output["run"]["run_id"]

    assert rc == 0
    events = output["run"]["events"]
    access_event = next(event for event in events if event["name"] == "workspace_file_access")
    assert access_event["status"] == "ok"
    assert "file=summary.txt" in access_event["summary"]
    assert "sha256_prefix=" in access_event["summary"]
    assert "raw_content_persisted=false" in access_event["summary"]
    assert "public alpha2 notes" not in json.dumps(output)
    assert str(tmp_path) not in captured.out

    assert cli.main(["runs", "show", run_id, "--ledger", str(ledger), "--json"]) == 0
    show_output = json.loads(capsys.readouterr().out)
    persisted_events = show_output["run"]["events"]
    assert any(event["name"] == "workspace_file_access" for event in persisted_events)

    ledger_text = ledger.read_text(encoding="utf-8")
    assert "workspace_file_access" in ledger_text
    assert "public alpha2 notes" not in ledger_text
    assert str(tmp_path) not in ledger_text


def test_cli_ask_file_executes_through_local_provider_with_live_opt_in(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    _prepare_paths()
    from ora_core.providers import local_llm
    from yonerai_cli import cli

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "local-note.txt"
    target.write_text("local provider workspace notes", encoding="utf-8")
    ledger = tmp_path / "runs.jsonl"

    monkeypatch.setenv("ORA_LOCAL_LLM_ENABLED", "1")
    monkeypatch.setenv("ORA_LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("ORA_LOCAL_LLM_MODEL", "local-file-test")

    def fake_generate_local_llm_reply(**kwargs: Any) -> local_llm.LocalLLMReply:
        assert kwargs["config"].base_url == "http://127.0.0.1:11434"
        assert "Workspace file context follows" in kwargs["message"]
        assert "content_preview:" in kwargs["message"]
        assert "local provider workspace notes" in kwargs["message"]
        return local_llm.LocalLLMReply(
            reply="<|final|>local file summary",
            provider="local-ollama",
            model="local-file-test",
        )

    monkeypatch.setattr(local_llm, "generate_local_llm_reply", fake_generate_local_llm_reply)

    rc = cli.main(
        [
            "ask",
            "summarize",
            "this",
            "file",
            "--file",
            "local-note.txt",
            "--workspace",
            str(workspace),
            "--provider",
            "local",
            "--live",
            "--ledger",
            str(ledger),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert rc == 0
    assert output["ok"] is True
    assert output["response"]["provider"] == "local"
    assert output["response"]["output_text"] == "local file summary"
    assert output["live_call_performed"] is True
    assert output["file_context"]["capability"] == "workspace_file_access"
    assert output["run"]["run_id"].startswith("run_")
    assert any(event["name"] == "workspace_file_access" for event in output["run"]["events"])
    assert "local provider workspace notes" not in json.dumps(output["run"])
    assert "local provider workspace notes" not in ledger.read_text(encoding="utf-8")
    assert str(tmp_path) not in captured.out


def test_mock_workspace_file_summary_ignores_metadata_like_text_inside_file_preview() -> None:
    _prepare_paths()
    from ora_core.execution.workspace_files import build_workspace_file_prompt, read_workspace_text_file
    from ora_core.providers import ProviderRequest
    from ora_core.providers.mock import MockProviderAdapter

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        target = workspace / "actual.txt"
        target.write_text("file_name: fake.txt\nalpha2 runnable command notes", encoding="utf-8")
        context = read_workspace_text_file("actual.txt", workspace=workspace)
        prompt = build_workspace_file_prompt("summarize file", context)

    response = MockProviderAdapter().generate(ProviderRequest(prompt=prompt))

    assert "actual.txt" in response.output_text
    assert "fake.txt" not in response.output_text
    assert "alpha2" in response.output_text


def test_mock_workspace_file_summary_redacts_secret_like_preview_keywords() -> None:
    _prepare_paths()
    from ora_core.execution.workspace_files import build_workspace_file_prompt, read_workspace_text_file
    from ora_core.providers import ProviderRequest
    from ora_core.providers.mock import MockProviderAdapter

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        target = workspace / "secrets.txt"
        secret_label = "OPENAI" + "_API_KEY"
        target.write_text(f"{secret_label}=sk-" + ("A" * 24) + "\nalpha2 release note", encoding="utf-8")
        context = read_workspace_text_file("secrets.txt", workspace=workspace)
        prompt = build_workspace_file_prompt("summarize file", context)

    response = MockProviderAdapter().generate(ProviderRequest(prompt=prompt))

    assert "alpha2" in response.output_text
    assert "sk-" not in response.output_text
    assert secret_label.lower() not in response.output_text.lower()


def test_mock_workspace_file_summary_redacts_generic_secret_assignment_values() -> None:
    _prepare_paths()
    from ora_core.execution.workspace_files import build_workspace_file_prompt, read_workspace_text_file
    from ora_core.providers import ProviderRequest
    from ora_core.providers.mock import MockProviderAdapter

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        target = workspace / "env.txt"
        access_label = "AWS_SECRET" + "_ACCESS_KEY"
        access_value = "AKIA" + "IOSFODNN7EXAMPLE"
        target.write_text(f"{access_label}={access_value}\nalpha2 release note", encoding="utf-8")
        context = read_workspace_text_file("env.txt", workspace=workspace)
        prompt = build_workspace_file_prompt("summarize file", context)

    response = MockProviderAdapter().generate(ProviderRequest(prompt=prompt))

    assert "alpha2" in response.output_text
    assert access_value.lower() not in response.output_text.lower()
    assert access_label.lower() not in response.output_text.lower()


def test_mock_workspace_file_summary_requires_full_file_context_signature() -> None:
    _prepare_paths()
    from ora_core.providers import ProviderRequest
    from ora_core.providers.mock import MockProviderAdapter

    adapter = MockProviderAdapter()

    marker_only = adapter.generate(ProviderRequest(prompt="Workspace file context follows."))
    incomplete_context = adapter.generate(
        ProviderRequest(
            prompt=(
                "Workspace file context follows. Do not infer local absolute paths or private runtime details.\n"
                "content_preview:\n"
                "alpha2 notes"
            )
        )
    )

    assert marker_only.model == "mock-deterministic"
    assert incomplete_context.model == "mock-deterministic"


def test_cli_ask_file_rejects_without_workspace(capsys) -> None:
    _prepare_paths()
    from yonerai_cli import cli

    rc = cli.main(["ask", "summarize", "file", "--file", "note.txt", "--provider", "mock", "--json"])
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
            "summarize",
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


def test_mock_workspace_file_summary_redacts_bearer_github_pat_from_keywords() -> None:
    _prepare_paths()
    from ora_core.execution.workspace_files import build_workspace_file_prompt, read_workspace_text_file
    from ora_core.providers import ProviderRequest
    from ora_core.providers.mock import MockProviderAdapter

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        target = workspace / "creds.txt"
        token = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"
        target.write_text(f"Authorization: Bearer {token}\nalpha2 release note", encoding="utf-8")
        context = read_workspace_text_file("creds.txt", workspace=workspace)
        prompt = build_workspace_file_prompt("summarize file", context)

    response = MockProviderAdapter().generate(ProviderRequest(prompt=prompt))

    assert "alpha2" in response.output_text
    assert token.lower() not in response.output_text.lower()
    assert "bearer" not in response.output_text.lower()
