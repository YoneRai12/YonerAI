from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from yonerai_cli.release_manifest import (
    ManifestError,
    format_manifest_verify_pretty,
    load_manifest_file,
    load_test_trust_fixture,
    parse_artifact_args,
    verify_manifest,
)


class ManifestCommandError(Exception):
    pass


def add_manifest_parser(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    lang_choices: tuple[str, ...],
    color_choices: tuple[str, ...],
) -> None:
    manifest = subcommands.add_parser("manifest", help="Validate local YonerAI release manifests without installing.")
    manifest_subcommands = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_verify = manifest_subcommands.add_parser("verify", help="Validate a local release manifest file.")
    manifest_verify.add_argument("manifest_path", help="Local manifest JSON path. Remote URLs are rejected.")
    manifest_verify.add_argument(
        "--artifact",
        action="append",
        help="Optional ARTIFACT_ID=LOCAL_FILE mapping for local SHA256/size verification. Repeatable.",
    )
    manifest_verify.add_argument(
        "--test-trust-fixture",
        help="Local non-production test trust fixture for signed manifest verification. Remote URLs are rejected.",
    )
    manifest_verify.add_argument("--require-signed", action="store_true", help="Reject manifests without verified signatures.")
    manifest_output = manifest_verify.add_mutually_exclusive_group()
    manifest_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    manifest_output.add_argument("--pretty", action="store_true", help="Print a readable verification summary.")
    manifest_verify.add_argument("--lang", choices=lang_choices, default="en", help="Pretty output language. Default: en.")
    manifest_verify.add_argument("--color", choices=color_choices, default="auto", help="Pretty output color mode. Default: auto.")


def handle_manifest_command(
    args: argparse.Namespace,
    *,
    print_json: Callable[[dict[str, Any]], None],
) -> int:
    try:
        artifacts = parse_artifact_args(args.artifact)
        test_trust_fixture = load_test_trust_fixture(args.test_trust_fixture) if args.test_trust_fixture else None
        report = verify_manifest(
            load_manifest_file(args.manifest_path),
            artifact_paths=artifacts,
            require_signed=args.require_signed,
            test_trust_fixture=test_trust_fixture,
        )
    except ManifestError as exc:
        raise ManifestCommandError(str(exc)) from exc
    if args.json:
        print_json(report)
    else:
        print(format_manifest_verify_pretty(report, lang=args.lang, color=args.color))
    return 0 if report["ok"] else 1
