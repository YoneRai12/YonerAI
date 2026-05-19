from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from urllib import request
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse


DEFAULT_ENDPOINT = "http://127.0.0.1:8001/v1/public/messages"


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _validate_loopback_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not _is_loopback_host(parsed.hostname):
        raise ValueError("endpoint must be an http(s) loopback URL such as http://127.0.0.1:8001/v1/public/messages")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("endpoint must not include credentials, query strings, or fragments")
    return endpoint


def main() -> int:
    parser = argparse.ArgumentParser(description="Optional local LLM message smoke for the YonerAI Core API.")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--message", default="hello from local LLM smoke")
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    try:
        endpoint = _validate_loopback_endpoint(args.endpoint)
    except ValueError as exc:
        print(f"invalid endpoint: {exc}", file=sys.stderr)
        return 2

    payload = {
        "message": args.message,
        "mode": "local",
        "conversation_id": "local-llm-smoke",
    }
    if args.model:
        payload["model"] = args.model

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        safe_body = exc.read().decode("utf-8", errors="replace")
        print(f"local LLM smoke failed: HTTP {exc.code} {safe_body}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"local LLM smoke failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": data.get("ok"),
                "mode": data.get("mode"),
                "provider": data.get("provider"),
                "model": data.get("model"),
                "message_id": data.get("message_id"),
                "reply_preview": str(data.get("reply", ""))[:160],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if data.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
