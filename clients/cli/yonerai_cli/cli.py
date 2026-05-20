from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


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
