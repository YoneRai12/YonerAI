from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from yonerai_cli import __version__
from yonerai_cli.release_manifest import (
    ManifestError,
    format_manifest_verify_pretty,
    load_manifest_file,
    parse_artifact_args,
    verify_manifest,
)


DEFAULT_API_ORIGIN = "http://127.0.0.1:8001"
TOKEN_ENV = "ORA_CORE_API_TOKEN"
PRIVATE_MARKERS = (
    re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+", re.IGNORECASE),
    re.compile(r"(?:^|[\s\"'=])/(root|etc|home|users|var|tmp)/", re.IGNORECASE),
    re.compile(
        r"(api[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret|google[_-]?client[_-]?secret|authorization)",
        re.IGNORECASE,
    ),
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class CliError(Exception):
    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def _is_loopback_host(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def normalize_loopback_origin(origin: str) -> str:
    try:
        parsed = urllib.parse.urlparse(origin)
    except ValueError as exc:
        raise CliError("api origin is invalid.") from exc
    if parsed.scheme not in {"http", "https"}:
        raise CliError("api origin must use http or https.")
    if parsed.username or parsed.password:
        raise CliError("api origin must not include credentials.")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise CliError("api origin must be an origin only, without path, query, or fragment.")
    if not _is_loopback_host(parsed.hostname):
        raise CliError("api origin must be loopback: localhost, 127.0.0.1, or ::1.")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", "")).rstrip("/")


def request_json(method: str, origin: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{normalize_loopback_origin(origin)}{path}"
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    token = os.getenv(TOKEN_ENV)
    if token:
        headers["X-ORA-Core-Token"] = token
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return _load_response_json(response.read())
    except urllib.error.HTTPError as exc:
        raise CliError(_safe_http_error(exc), exit_code=1) from exc
    except urllib.error.URLError:
        raise CliError("request failed: could not reach loopback Core API.", exit_code=1)
    except TimeoutError as exc:
        raise CliError("request timed out.", exit_code=1) from exc


def _load_response_json(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CliError("failed to parse JSON response.", exit_code=1) from exc
    if not isinstance(data, dict):
        raise CliError("response JSON must be an object.", exit_code=1)
    return data


def _safe_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        data = json.loads(exc.read().decode("utf-8"))
    except Exception:
        return f"request failed with status {exc.code}."
    detail = data.get("detail") if isinstance(data, dict) else None
    if isinstance(detail, dict):
        return _format_error_body(exc.code, detail, fallback_code=data.get("error") if isinstance(data, dict) else None)
    if isinstance(detail, str):
        return f"request failed with status {exc.code}: {_safe_error_text(detail, fallback='request failed')}"
    if isinstance(data, dict):
        return _format_error_body(exc.code, data)
    return f"request failed with status {exc.code}."


def _safe_error_text(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.split())
    if not cleaned:
        return fallback
    if any(pattern.search(cleaned) for pattern in PRIVATE_MARKERS):
        return fallback
    return cleaned[:220]


def _format_error_body(status_code: int, body: dict[str, Any], *, fallback_code: object | None = None) -> str:
    code = _safe_error_text(body.get("error") or fallback_code or "error", fallback="error")
    message = _safe_error_text(body.get("message"), fallback="request failed")
    parts = [f"request failed with status {status_code}: {code}: {message}"]
    context = []
    for key in ("mode", "provider", "model", "status"):
        safe_value = _safe_error_text(body.get(key), fallback="")
        if safe_value:
            context.append(f"{key}={safe_value}")
    if context:
        parts.append(f"({', '.join(context)})")
    return " ".join(parts)


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _build_doctor_report() -> dict[str, Any]:
    manifest_path = _repo_root() / "releases" / "manifest.example.json"
    manifest_report: dict[str, Any]
    try:
        manifest_report = verify_manifest(load_manifest_file(str(manifest_path)))
    except ManifestError as exc:
        manifest_report = {"ok": False, "errors": [str(exc)]}
    return {
        "ok": bool(manifest_report.get("contract_valid", manifest_report.get("ok"))),
        "command": "yonerai doctor",
        "schema_version": "yonerai-doctor/v1",
        "python": {
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "supported": sys.version_info >= (3, 11),
        },
        "cli": {
            "import_ok": True,
            "package_version": __version__,
            "demo_command_available": True,
            "quickstart_alias_available": True,
        },
        "manifest": {
            "example_present": manifest_path.exists(),
            "contract_valid": bool(manifest_report.get("contract_valid", manifest_report.get("ok"))),
            "install_ready": bool(manifest_report.get("install_ready", False)),
            "signature_state": manifest_report.get("signature_state"),
            "non_production_reason": manifest_report.get("non_production_reason"),
        },
        "credentials": {
            TOKEN_ENV: "present_redacted" if os.getenv(TOKEN_ENV) else "absent",
            "required_for_demo": False,
        },
        "boundaries": {
            "network_required": False,
            "install_mutation": False,
            "path_mutation": False,
            "official_cloud_runtime_included": False,
            "live_discord_required": False,
            "persistent_memory_required": False,
            "oracle_required": False,
            "deploy_required": False,
        },
        "errors": manifest_report.get("errors", []),
    }


def _print_doctor_pretty(report: dict[str, Any]) -> None:
    print("YonerAI doctor")
    print(f"- ok: {_bool_text(report['ok'])}")
    python_report = report["python"]
    print(f"- python: {python_report['version']} supported={_bool_text(python_report['supported'])}")
    cli_report = report["cli"]
    print(f"- cli_import: {_bool_text(cli_report['import_ok'])}")
    print(f"- package_version: {cli_report['package_version']}")
    manifest_report = report["manifest"]
    print(f"- manifest_example_valid: {_bool_text(manifest_report['contract_valid'])}")
    print(f"- manifest_install_ready: {_bool_text(manifest_report['install_ready'])}")
    print(f"- signature_state: {manifest_report['signature_state']}")
    print(f"- credentials_required_for_demo: {_bool_text(report['credentials']['required_for_demo'])}")
    print("Boundaries:")
    for key, value in report["boundaries"].items():
        print(f"- {key}: {_bool_text(value)}")
    if report["errors"]:
        print("Errors:")
        for error in report["errors"]:
            print(f"- {error}")


def _bool_text(value: object) -> str:
    return "true" if value is True else "false" if value is False else str(value)


def _run_public_mvp_smoke(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_repo_import_path()
        public_mvp_smoke = _load_public_mvp_smoke_module()
    except Exception as exc:
        raise CliError("public MVP smoke is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else []
        return public_mvp_smoke.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        code = exc.code if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:
        raise CliError("public MVP smoke failed.", exit_code=1) from exc


def _run_public_demo(*, json_output: bool = False, pretty: bool = False) -> int:
    try:
        _prepare_repo_import_path()
        public_demo = _load_public_demo_module()
    except Exception as exc:
        raise CliError("YonerAI public demo is unavailable.", exit_code=1) from exc
    try:
        argv = ["--json"] if json_output else ["--pretty"] if pretty else ["--pretty"]
        return public_demo.main(argv)
    except SystemExit as exc:
        if exc.code is None:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        raise CliError("YonerAI public demo failed.", exit_code=1) from exc


def _prepare_repo_import_path() -> None:
    text = str(_repo_root())
    if text not in sys.path:
        sys.path.insert(0, text)


def _load_repo_script_module(module_name: str, script_relative_path: str) -> Any:
    script_path = _repo_root() / script_relative_path
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise CliError("public script module is unavailable.", exit_code=1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_public_mvp_smoke_module() -> Any:
    return _load_repo_script_module("yonerai_trusted_public_mvp_smoke", "scripts/dev/public_mvp_smoke.py")


def _load_public_demo_module() -> Any:
    return _load_repo_script_module("yonerai_trusted_public_demo", "scripts/dev/public_demo.py")


def _prepare_core_import_path() -> None:
    core_src = _repo_root() / "core" / "src"
    text = str(core_src)
    if text not in sys.path:
        sys.path.insert(0, text)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _preview_route(args: argparse.Namespace) -> dict[str, Any]:
    try:
        _prepare_core_import_path()
        from ora_core.route_preview import preview_route
    except Exception as exc:
        raise CliError("route preview is unavailable.", exit_code=1) from exc

    prompt = _prompt_from_args(args.task)
    local_node_state = args.local_node_state
    has_local_node = args.has_local_node or local_node_state in {
        "present_unverified",
        "present_verified",
        "expired",
        "invalid_signature",
        "wrong_audience",
    }
    if local_node_state == "missing":
        has_local_node = False
    local_node_capabilities = tuple(args.local_node_capability or ()) or None
    require_session = args.require_enrolled_verified_session or args.session_state is not None
    decision = preview_route(
        prompt,
        mode=args.mode,
        requested_capability=args.capability,
        has_local_node=has_local_node,
        local_node_verification_state=local_node_state,
        local_node_capabilities=local_node_capabilities,
        require_enrolled_verified_session=require_session,
        session_verification_state=args.session_state,
        risk_hint=args.risk_hint,
    )
    return decision.to_public_dict()


def _prompt_from_args(parts: list[str]) -> str:
    prompt = " ".join(parts).strip()
    if not prompt:
        raise CliError("prompt must not be empty.")
    return prompt


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--api-origin",
        default=DEFAULT_API_ORIGIN,
        help=f"Loopback Core API origin. Default: {DEFAULT_API_ORIGIN}",
    )

    parser = argparse.ArgumentParser(
        prog="yonerai",
        description=(
            "YonerAI local public MVP smoke CLI. "
            "Not the final product CLI, not native Japanese CLI, and not a deploy tool."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("health", parents=[shared], help="Check the local Core API health endpoint.")

    smoke = subcommands.add_parser("smoke", help="Run the credential-free in-process public MVP smoke.")
    smoke_output = smoke.add_mutually_exclusive_group()
    smoke_output.add_argument("--json", action="store_true", help="Print compact machine-readable JSON.")
    smoke_output.add_argument("--pretty", action="store_true", help="Print a detailed human-readable summary.")

    demo = subcommands.add_parser(
        "demo",
        aliases=["quickstart"],
        help="Run a credential-free public YonerAI demo after clone.",
    )
    demo_output = demo.add_mutually_exclusive_group()
    demo_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    demo_output.add_argument("--pretty", action="store_true", help="Print a readable sectioned demo summary.")

    doctor = subcommands.add_parser("doctor", help="Run offline, non-mutating setup diagnostics.")
    doctor_output = doctor.add_mutually_exclusive_group()
    doctor_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    doctor_output.add_argument("--pretty", action="store_true", help="Print a readable diagnostic summary.")

    manifest = subcommands.add_parser("manifest", help="Validate local YonerAI release manifests without installing.")
    manifest_subcommands = manifest.add_subparsers(dest="manifest_command", required=True)
    manifest_verify = manifest_subcommands.add_parser("verify", help="Validate a local release manifest file.")
    manifest_verify.add_argument("manifest_path", help="Local manifest JSON path. Remote URLs are rejected.")
    manifest_verify.add_argument(
        "--artifact",
        action="append",
        help="Optional ARTIFACT_ID=LOCAL_FILE mapping for local SHA256/size verification. Repeatable.",
    )
    manifest_verify.add_argument("--require-signed", action="store_true", help="Reject manifests without production signatures.")
    manifest_output = manifest_verify.add_mutually_exclusive_group()
    manifest_output.add_argument("--json", action="store_true", help="Print stable machine-readable JSON.")
    manifest_output.add_argument("--pretty", action="store_true", help="Print a readable verification summary.")

    route = subcommands.add_parser("route", help="Preview safe YonerAI task routing without executing it.")
    route_subcommands = route.add_subparsers(dest="route_command", required=True)
    route_preview = route_subcommands.add_parser("preview", help="Preview cloud/local/hybrid/disabled routing.")
    route_preview.add_argument("task", nargs="+")
    route_preview.add_argument(
        "--mode",
        choices=["official_managed_cloud", "official_hybrid_private", "full_private_self_host"],
        default="official_managed_cloud",
    )
    route_preview.add_argument("--capability", help="Optional explicit capability name.")
    route_preview.add_argument("--risk-hint", help="Optional public-safe operation class hint.")
    route_preview.add_argument("--has-local-node", action="store_true", help="Preview as if a user Local Node is available.")
    route_preview.add_argument(
        "--local-node-state",
        choices=[
            "missing",
            "present_unverified",
            "present_verified",
            "expired",
            "invalid_signature",
            "wrong_audience",
        ],
        help="Optional test-only Local Node verification state for route preview.",
    )
    route_preview.add_argument(
        "--local-node-capability",
        action="append",
        help="Optional declared capability for a verified test Local Node manifest. Repeatable.",
    )
    route_preview.add_argument(
        "--require-enrolled-verified-session",
        action="store_true",
        help="Require a public-safe enrolled verified Local Node session state for local work previews.",
    )
    route_preview.add_argument(
        "--session-state",
        choices=[
            "missing",
            "unenrolled",
            "pairing_pending",
            "enrolled_unverified",
            "enrolled_verified",
            "expired",
            "revoked",
            "wrong_audience",
        ],
        help="Optional public-safe Local Node enrollment/session state for route preview.",
    )

    message = subcommands.add_parser("message", parents=[shared], help="Send a local public message smoke request.")
    message.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    message.add_argument("prompt", nargs="+")

    run = subcommands.add_parser("run", parents=[shared], help="Create a local Surface API run smoke request.")
    run.add_argument("--mode", choices=["mock", "offline", "local"], default="mock")
    run.add_argument("prompt", nargs="+")

    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        _print_json(request_json("GET", args.api_origin, "/health"))
        return 0
    if args.command == "smoke":
        return _run_public_mvp_smoke(json_output=args.json, pretty=args.pretty)
    if args.command in {"demo", "quickstart"}:
        return _run_public_demo(json_output=args.json, pretty=args.pretty)
    if args.command == "doctor":
        report = _build_doctor_report()
        if args.json:
            _print_json(report)
        else:
            _print_doctor_pretty(report)
        return 0 if report["ok"] else 1
    if args.command == "manifest" and args.manifest_command == "verify":
        try:
            artifacts = parse_artifact_args(args.artifact)
            report = verify_manifest(
                load_manifest_file(args.manifest_path),
                artifact_paths=artifacts,
                require_signed=args.require_signed,
            )
        except ManifestError as exc:
            raise CliError(str(exc), exit_code=2) from exc
        if args.json:
            _print_json(report)
        else:
            print(format_manifest_verify_pretty(report))
        return 0 if report["ok"] else 1
    if args.command == "route" and args.route_command == "preview":
        _print_json(_preview_route(args))
        return 0
    if args.command == "message":
        prompt = _prompt_from_args(args.prompt)
        _print_json(request_json("POST", args.api_origin, "/v1/public/messages", {"message": prompt, "mode": args.mode}))
        return 0
    if args.command == "run":
        prompt = _prompt_from_args(args.prompt)
        _print_json(request_json("POST", args.api_origin, "/api/v1/agent/run", {"prompt": prompt, "mode": args.mode}))
        return 0
    parser.error("unknown command")
    return 2


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
