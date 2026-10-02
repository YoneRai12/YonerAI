from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import ci_quality_scans


def test_ci_quality_scan_allows_linux_path_fixtures_under_tests(tmp_path: Path) -> None:
    fixture = tmp_path / "tests" / "path_fixture.py"
    fixture.parent.mkdir()
    fixture.write_text(
        'HOME_FIXTURE = "/home/runner/project"\nROOT_FIXTURE = "/root/project"\n',
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("tests/path_fixture.py")])

    assert errors == []


def test_ci_quality_scan_blocks_linux_path_leak_outside_tests(tmp_path: Path) -> None:
    source = tmp_path / "src" / "leak.py"
    source.parent.mkdir()
    source.write_text('LEAK = "/home/runner/project"\n', encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("src/leak.py")])

    assert any("possible local absolute path leak" in error for error in errors)


def test_ci_quality_scan_blocks_windows_forward_slash_path_leak_outside_tests(tmp_path: Path) -> None:
    source = tmp_path / "src" / "leak.py"
    source.parent.mkdir()
    source.write_text('LEAK = "C:/Users/runner/project"\n', encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("src/leak.py")])

    assert any("possible local absolute path leak" in error for error in errors)


def test_ci_quality_scan_scans_typescript_and_launcher_files(tmp_path: Path) -> None:
    tsx_source = tmp_path / "clients" / "web" / "app" / "page.tsx"
    tsx_source.parent.mkdir(parents=True)
    tsx_source.write_text('const leak = "C:/Users/runner/project";\n', encoding="utf-8")
    cmd_source = tmp_path / "scripts" / "start.cmd"
    cmd_source.parent.mkdir()
    cmd_source.write_text("set " + "API_KEY" + "=" + "abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8")
    shell_source = tmp_path / "scripts" / "start.sh"
    shell_source.write_text("export " + "DISCORD_TOKEN" + "=" + "abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(
        tmp_path,
        [
            Path("clients/web/app/page.tsx"),
            Path("scripts/start.cmd"),
            Path("scripts/start.sh"),
        ],
    )

    assert any("possible local absolute path leak" in error for error in errors)
    assert sum("possible secret or token literal" in error for error in errors) == 2


def test_ci_quality_scan_blocks_common_unlabeled_token_prefixes(tmp_path: Path) -> None:
    source = tmp_path / "src" / "leak.py"
    source.parent.mkdir()
    github_pat = "github_pat_" + "A" * 24
    slack_token = "xoxb-" + "B" * 24
    aws_key = "AKIA" + "C" * 16
    google_key = "AIza" + "D" * 35
    bearer = "Authorization: Bearer " + "E" * 24
    source.write_text(
        "\n".join(
            (
                f"GITHUB = {github_pat!r}",
                f"SLACK = {slack_token!r}",
                f"AWS = {aws_key!r}",
                f"GOOGLE = {google_key!r}",
                f"HEADER = {bearer!r}",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("src/leak.py")])

    assert sum("possible secret or token literal" in error for error in errors) == 5


def test_ci_quality_scan_allows_safe_env_and_property_references(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    env_ref = "process" + ".env" + ".DISCORD_CLIENT_SECRET"
    access_token = "access" + "Token"
    account_access_token = "account.access" + "_token"
    token_access_token = "token.access" + "Token"
    source.write_text(
        "\n".join(
            (
                f"clientSecret: {env_ref},",
                f"token.{access_token} = {account_access_token}",
                f"session.{access_token} = {token_access_token}",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert errors == []


def test_ci_quality_scan_still_blocks_literal_token_assigned_to_access_token(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    source.write_text("token.accessToken = 'sk-" + "A" * 24 + "'\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert any("possible secret or token literal" in error for error in errors)


def test_ci_quality_scan_blocks_secret_fallbacks_after_env_references(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    env_ref = "process" + ".env" + ".DISCORD_CLIENT_SECRET"
    source.write_text("clientSecret = " + env_ref + " || '" + "A" * 24 + "'\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert any("possible secret or token literal" in error for error in errors)


def test_ci_quality_scan_blocks_secret_fallbacks_after_access_token_references(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    access_token = "access" + "Token"
    source.write_text(
        f"token.{access_token} = token.{access_token} || '" + "A" * 24 + "'\n",
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert any("possible secret or token literal" in error for error in errors)


def test_ci_quality_scan_blocks_literal_before_safe_env_reference_on_same_line(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    env_ref = "process" + ".env" + ".DISCORD_CLIENT_SECRET"
    source.write_text("clientSecret = '" + "A" * 24 + "'; const safe = " + env_ref + "\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert any("possible secret or token literal" in error for error in errors)


def test_ci_quality_scan_blocks_literal_before_safe_access_token_reference_on_same_line(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    access_token = "access" + "Token"
    account_access_token = "account.access" + "_token"
    source.write_text(
        "clientSecret = '" + "A" * 24 + f"'; token.{access_token} = {account_access_token}\n",
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert any("possible secret or token literal" in error for error in errors)


def test_ci_quality_scan_allows_safe_access_token_reference_with_comment(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    access_token = "access" + "Token"
    account_access_token = "account.access" + "_token"
    source.write_text(f"token.{access_token} = {account_access_token}; // provider callback\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert errors == []


def test_ci_quality_scan_allows_safe_access_token_reference_before_other_statement(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    access_token = "access" + "Token"
    account_access_token = "account.access" + "_token"
    source.write_text(
        f"token.{access_token} = {account_access_token}; console.log('done')\n",
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert errors == []


def test_ci_quality_scan_allows_safe_env_reference_before_other_string_field(tmp_path: Path) -> None:
    source = tmp_path / "clients" / "web" / "auth.ts"
    source.parent.mkdir(parents=True)
    env_ref = "process" + ".env" + ".DISCORD_CLIENT_SECRET"
    source.write_text(f"clientSecret: {env_ref}, callbackUrl: \"http://localhost:3000\"\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("clients/web/auth.ts")])

    assert errors == []


def test_ci_quality_scan_blocks_bidi_markers_and_question_mark_mojibake(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "public.md"
    source.parent.mkdir()
    source.write_text(
        "safe" + chr(0x202E) + "hidden\n" + "broken 日本語" + "?" * 4 + " text\n",
        encoding="utf-8",
    )

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("docs/public.md")])

    assert any("hidden unicode marker" in error for error in errors)
    assert any("possible mojibake" in error for error in errors)


def test_ci_quality_scan_allows_ascii_question_mark_runs_and_initial_bom(tmp_path: Path) -> None:
    source = tmp_path / "docs" / "public.md"
    source.parent.mkdir()
    source.write_text("\ufeffwhy????\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("docs/public.md")])

    assert errors == []


def test_ci_quality_scan_blocks_escaped_terminal_sequence_literals(tmp_path: Path) -> None:
    source = tmp_path / "src" / "terminal.py"
    source.parent.mkdir()
    escaped_csi = "\\" + "x1b[31m"
    source.write_text(f'print("{escaped_csi}red")\n', encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("src/terminal.py")])

    assert any("terminal escape sequence literal" in error for error in errors)


def test_ci_quality_scan_allows_existing_shell_color_variables(tmp_path: Path) -> None:
    source = tmp_path / "start.sh"
    source.write_text("GREEN='\\033[0;32m'\nCYAN='\\033[0;36m'\nNC='\\033[0m'\n", encoding="utf-8")

    errors = ci_quality_scans.scan_paths(tmp_path, [Path("start.sh")])

    assert errors == []


def test_ci_quality_scan_git_fallback_handles_missing_git(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def raise_os_error(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(ci_quality_scans.subprocess, "run", raise_os_error)

    assert ci_quality_scans._changed_files(tmp_path) == []
    assert ci_quality_scans._tracked_files(tmp_path) == []


def test_changed_files_uses_explicit_github_push_range_for_full_change_set(tmp_path: Path, monkeypatch) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "YonerAI Test")
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-m", "base")
    before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    (tmp_path / "first.py").write_text("FIRST = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "first.py")
    _git(tmp_path, "commit", "-m", "first")
    (tmp_path / "second.py").write_text("SECOND = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "second.py")
    _git(tmp_path, "commit", "-m", "second")
    after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("YONERAI_DIFF_BASE_SHA", before)
    monkeypatch.setenv("YONERAI_DIFF_HEAD_SHA", after)
    monkeypatch.setenv("YONERAI_DIFF_MODE", "two-dot")

    paths = {path.as_posix() for path in ci_quality_scans._changed_files(tmp_path)}

    assert {"first.py", "second.py"}.issubset(paths)


def test_changed_files_uses_explicit_pull_request_merge_base_range(tmp_path: Path, monkeypatch, capsys) -> None:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "YonerAI Test")
    (tmp_path / "common.txt").write_text("common\n", encoding="utf-8")
    _git(tmp_path, "add", "common.txt")
    _git(tmp_path, "commit", "-m", "common")

    _git(tmp_path, "checkout", "-b", "feature")
    (tmp_path / "first.py").write_text("FIRST = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "first.py")
    _git(tmp_path, "commit", "-m", "first")
    (tmp_path / "second.py").write_text("SECOND = 2\n", encoding="utf-8")
    _git(tmp_path, "add", "second.py")
    _git(tmp_path, "commit", "-m", "second")
    head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    _git(tmp_path, "checkout", "main")
    (tmp_path / "base-only.py").write_text("BASE_ONLY = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "base-only.py")
    _git(tmp_path, "commit", "-m", "base advance")
    base = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("YONERAI_DIFF_BASE_SHA", base)
    monkeypatch.setenv("YONERAI_DIFF_HEAD_SHA", head)
    monkeypatch.setenv("YONERAI_DIFF_MODE", "three-dot")

    paths = {path.as_posix() for path in ci_quality_scans._changed_files(tmp_path)}

    assert {"first.py", "second.py"}.issubset(paths)
    assert "base-only.py" not in paths
    output = capsys.readouterr().out
    assert f"range={base}...{head}" in output
    assert "path_count=2" in output


def test_changed_files_rejects_untrusted_sha_before_running_git(tmp_path: Path, monkeypatch) -> None:
    def unexpected_git(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("git must not run for an invalid SHA")

    monkeypatch.setattr(ci_quality_scans, "_run_git", unexpected_git)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("YONERAI_DIFF_BASE_SHA", "a" * 40 + ";touch-pwned")
    monkeypatch.setenv("YONERAI_DIFF_HEAD_SHA", "b" * 40)
    monkeypatch.setenv("YONERAI_DIFF_MODE", "three-dot")

    with pytest.raises(ci_quality_scans.ChangedFileSelectionError, match="full 40-character commit SHA"):
        ci_quality_scans._changed_files(tmp_path)


def test_changed_files_fails_closed_when_validated_commit_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "YonerAI Test")
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-m", "base")
    base = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("YONERAI_DIFF_BASE_SHA", base)
    monkeypatch.setenv("YONERAI_DIFF_HEAD_SHA", "f" * 40)
    monkeypatch.setenv("YONERAI_DIFF_MODE", "three-dot")

    with pytest.raises(ci_quality_scans.ChangedFileSelectionError, match="head commit is unavailable"):
        ci_quality_scans._changed_files(tmp_path)


def test_main_fails_closed_when_ci_range_configuration_is_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("YONERAI_DIFF_BASE_SHA", raising=False)
    monkeypatch.delenv("YONERAI_DIFF_HEAD_SHA", raising=False)
    monkeypatch.delenv("YONERAI_DIFF_MODE", raising=False)

    assert ci_quality_scans.main(["--changed"]) == 1
    assert "[FAIL] ci quality changed-file selection failed" in capsys.readouterr().out


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

