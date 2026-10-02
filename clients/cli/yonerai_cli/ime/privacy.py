"""Privacy boundaries for the Romaji Composer.

Conversion audit records never contain raw buffer text, converted private
text, provider keys, or local absolute paths. Cloud enhancement is disabled
by default and requires explicit opt-in with visible privacy wording.
"""

from __future__ import annotations

import re


_PRIVATE_PATH_RE = re.compile(r"([A-Za-z]:[\\/]+Users[\\/]+|/(?:home|root|Users)/)", re.IGNORECASE)
_KEY_RE = re.compile(r"(sk-[A-Za-z0-9_-]{10,}|api[_-]?key|-----BEGIN [A-Z ]*PRIVATE KEY-----)", re.IGNORECASE)


def redacted_summary(raw_text: str, converted_text: str | None) -> dict[str, object]:
    """Build a redacted, audit-safe summary of one conversion."""
    return {
        "raw_chars": len(raw_text),
        "converted_chars": len(converted_text) if converted_text is not None else 0,
        "raw_text_included": False,
        "converted_text_included": False,
    }


def contains_sensitive_markers(text: str) -> bool:
    """True when text looks like it carries keys or local absolute paths."""
    return bool(_PRIVATE_PATH_RE.search(text) or _KEY_RE.search(text))


def cloud_privacy_wording(lang: str) -> str:
    if lang == "ja":
        return "\n".join(
            (
                "クラウド変換の注意",
                "  有効化すると変換対象の文章が外部プロバイダーに送信されます。",
                "  秘密情報・ローカルパス・個人情報を含む文章では使わないでください。",
                "  既定はオフです。有効化には /ime cloud on confirm が必要です。",
            )
        )
    return "\n".join(
        (
            "Cloud conversion notice",
            "  When enabled, the text being converted is sent to an external provider.",
            "  Do not use it for text containing secrets, local paths, or personal data.",
            "  Disabled by default. Enabling requires /ime cloud on confirm.",
        )
    )
