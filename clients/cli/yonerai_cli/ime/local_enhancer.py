"""Optional local LLM enhancement for paragraph-level Japanese conversion.

Loopback-only by design: this module refuses any endpoint whose host is not
localhost / 127.0.0.1 / ::1. It never probes non-loopback endpoints, never
installs models, and never runs shell commands. Failures fall back to the
deterministic converter at the call site.
"""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block redirects so loopback prompts cannot be replayed off-host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(req.full_url, code, "redirect blocked for loopback-only enhancer", headers, fp)


def _open_loopback_request(request: urllib.request.Request, timeout: float):
    """Open a loopback request without process proxy configuration or redirects."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler())
    return opener.open(request, timeout=timeout)  # noqa: S310 (loopback enforced by caller; proxies disabled)


class EnhancerError(Exception):
    pass


def is_loopback_endpoint(endpoint: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(endpoint)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _build_prompt(text: str, *, style_profile: str, dictionary: dict[str, str]) -> str:
    hints = "\n".join(f"- {romaji} -> {japanese}" for romaji, japanese in sorted(dictionary.items()))
    style_line = f"文体: {style_profile}" if style_profile else "文体: 通常"
    dict_block = f"固有名詞の変換指定:\n{hints}\n" if hints else ""
    return (
        "次のローマ字日本語（英語が混ざることもある）を自然な日本語に変換してください。"
        "意味の追加・削除はせず、変換のみ行ってください。\n"
        f"{style_line}\n{dict_block}入力:\n{text}\n出力:"
    )


def enhance_with_local_llm(
    text: str,
    *,
    endpoint: str,
    model: str = "local",
    style_profile: str = "",
    dictionary: dict[str, str] | None = None,
    timeout: float = 20.0,
    transport: Callable[[urllib.request.Request, float], bytes] | None = None,
) -> str:
    """Convert text via a loopback-only OpenAI-compatible endpoint.

    `transport` exists for tests; the default uses urllib against the loopback
    endpoint only.
    """
    if not is_loopback_endpoint(endpoint):
        raise EnhancerError("local llm endpoint must be loopback (localhost / 127.0.0.1 / ::1).")
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": _build_prompt(text, style_profile=style_profile, dictionary=dictionary or {})}
        ],
        "temperature": 0,
    }
    url = endpoint.rstrip("/") + "/v1/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        if transport is not None:
            body = transport(request, timeout)
        else:
            with _open_loopback_request(request, timeout=timeout) as response:
                body = response.read()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise EnhancerError(f"local llm enhancement failed: {type(exc).__name__}") from exc
    try:
        parsed = json.loads(body.decode("utf-8"))
        content = parsed["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise EnhancerError("local llm response was not a valid chat completion.") from exc
    if not isinstance(content, str) or not content.strip():
        raise EnhancerError("local llm returned an empty conversion.")
    return content.strip()
