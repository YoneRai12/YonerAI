from __future__ import annotations

import re
import zlib
from collections.abc import Callable, Iterator

_CHANNEL_TAG_PATTERN = re.compile(r"<\|.*?\|>")
_INPUT_SPAM_PATTERNS = (
    r"(?i)(repeat|copy|write|print).{0,20}(\d{4,}|limit|max|infinity).{0,20}(times|lines|copies)",
    r"(?i)(copy|repeat).{0,10}(\d{3,})",
    r"(a{10,}|w{10,})",
)
_TOOL_CALLS_PREFIX_PATTERN = re.compile(r"\[TOOL_CALLS\]\s*(\w+)\s*[\[\(]?ARGS[\]\)]?\s*", re.DOTALL)
WarnCallback = Callable[[str], None]
JsonBlock = tuple[int, int, str]


def clean_content(text: str) -> str:
    """Remove internal tags like <|channel|> from generated text."""
    cleaned = _CHANNEL_TAG_PATTERN.sub("", text)
    return cleaned.strip()


def detect_spam(text: str, *, warn: WarnCallback | None = None) -> bool:
    """Detect highly repetitive generated text without Discord runtime dependencies."""
    if not text or len(text) < 500:
        return False

    compressed = zlib.compress(text.encode("utf-8"))
    ratio = len(compressed) / len(text)
    if ratio < 0.12:
        if warn:
            warn(f"🛡️ Spam Output Blocked: Length={len(text)}, Ratio={ratio:.3f}")
        return True
    return False


def is_input_spam(text: str, *, warn: WarnCallback | None = None) -> bool:
    """Detect repetitive or explicit repeat-abuse user input."""
    if not text:
        return False

    for pattern in _INPUT_SPAM_PATTERNS:
        if re.search(pattern, text):
            if warn:
                warn(f"🛡️ Input Spam Blocked (Pattern): {pattern}")
            return True

    if len(text) > 400:
        compressed = zlib.compress(text.encode("utf-8"))
        ratio = len(compressed) / len(text)
        if ratio < 0.12:
            if warn:
                warn(f"🛡️ Input Spam Blocked (Ratio): {ratio:.3f}")
            return True
    return False


def extract_json_objects(text: str, *, warn: WarnCallback | None = None) -> list[str]:
    """Extract top-level JSON objects while preserving legacy tool-call recovery."""
    if "[TOOL_CALLS]" in text:
        tool_calls = _extract_tool_call_objects(text, warn=warn)
        if tool_calls:
            return tool_calls

    objects: list[str] = []
    for _, _, json_str in _iter_balanced_json_blocks(text):
        if "route_eval" not in json_str:
            objects.append(json_str)
    return objects


def strip_route_json(content: str, *, info: WarnCallback | None = None) -> str:
    """Remove balanced JSON object blocks containing route_eval."""
    if "route_eval" not in content:
        return content

    parts: list[str] = []
    last_index = 0
    removed = False
    for start, end, json_block in _iter_balanced_json_blocks(content):
        if "route_eval" not in json_block:
            continue
        parts.append(content[last_index:start])
        last_index = end
        removed = True
        if info:
            info(f"Stripped Route JSON: {json_block[:50]}...")
    if not removed:
        return content
    parts.append(content[last_index:])
    return "".join(parts)


def _extract_tool_call_objects(text: str, *, warn: WarnCallback | None = None) -> list[str]:
    objects: list[str] = []
    for match in _TOOL_CALLS_PREFIX_PATTERN.finditer(text):
        if match.end() >= len(text) or text[match.end()] != "{":
            continue
        block = _first_balanced_json_block(text, match.end())
        if block is None:
            continue
        tool_name = match.group(1)
        _, _, args_json = block
        objects.append(f'{{"tool": "{tool_name}", "args": {args_json}}}')
        if warn:
            warn(f"Recovered tool call from [TOOL_CALLS] format: {tool_name}")
    return objects


def _first_balanced_json_block(text: str, start_pos: int = 0) -> JsonBlock | None:
    for block in _iter_balanced_json_blocks(text[start_pos:]):
        start, end, json_str = block
        return start + start_pos, end + start_pos, json_str
    return None


def _iter_balanced_json_blocks(text: str) -> Iterator[JsonBlock]:
    stack = 0
    start_index = -1
    in_string = False
    escape = False

    for index, char in enumerate(text):
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            if stack == 0:
                start_index = index
            stack += 1
            continue
        if char == "}" and stack > 0:
            stack -= 1
            if stack == 0 and start_index != -1:
                end_index = index + 1
                yield start_index, end_index, text[start_index:end_index]
                start_index = -1


__all__ = [
    "clean_content",
    "detect_spam",
    "extract_json_objects",
    "is_input_spam",
    "strip_route_json",
]
