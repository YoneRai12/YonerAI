from __future__ import annotations

import re

from .contracts import ProviderCapabilities, ProviderRequest, ProviderResponse, ProviderStatus


class MockProviderAdapter:
    provider_id = "mock"
    capabilities = ProviderCapabilities(
        chat=True,
        structured_output=True,
        streaming=False,
        vision=False,
        tool_use=False,
        local_only=False,
        cloud=False,
        external_provider=False,
    )

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_id=self.provider_id,
            configured=True,
            available=True,
            reason=None,
            capabilities=self.capabilities,
        )

    def generate(self, request: ProviderRequest, *, allow_live_call: bool = False) -> ProviderResponse:
        del allow_live_call
        workspace_summary = _workspace_file_summary_response(request.prompt)
        if workspace_summary is not None:
            return ProviderResponse(
                provider=self.provider_id,
                model="mock-workspace-file-summary",
                output_text=workspace_summary,
                deterministic=True,
            )
        return ProviderResponse(
            provider=self.provider_id,
            model="mock-deterministic",
            output_text="YonerAI mock provider response. No live provider call was made.",
            deterministic=True,
        )


_WORKSPACE_CONTEXT_HEADER = (
    "Workspace file context follows. Do not infer local absolute paths or private runtime details.\n"
)
_CONTENT_PREVIEW_MARKER = "content_preview:\n"
_FIELD_PATTERN = re.compile(r"^(?P<name>[a-z0-9_]+): (?P<value>.*)$", re.MULTILINE)
_REQUIRED_WORKSPACE_FIELDS = {
    "capability",
    "file_name",
    "extension",
    "size_bytes",
    "line_count",
    "word_count",
    "sha256_prefix",
    "truncated",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\b[A-Za-z0-9_-]*authorization\s*[=:]\s*bearer\s+[^\s,;]+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[^\s,;]{10,}", re.IGNORECASE),
    re.compile(
        r"\b[A-Za-z0-9_-]*(?:api[_-]?key|apikey|access[_-]?key|access[_-]?token|refresh[_-]?token|discord[_-]?token|private[_-]?key|client[_-]?secret|authorization|bearer|password|secret|token)[A-Za-z0-9_-]*\s*(?:=|:)\s*[^\s,;]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bAIzaSy[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bxox(?:b|p|a|r|s)-[A-Za-z0-9-]{10,}\b", re.IGNORECASE),
    re.compile(r"\b(?:rk|pk)_(?:live|test)_[A-Za-z0-9]{10,}\b", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}\b"),
)
_SECRET_KEYWORD_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "client_secret",
    "discord_token",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
)


def _workspace_file_summary_response(prompt: str) -> str | None:
    context = _extract_workspace_context(prompt)
    if context is None:
        return None
    fields, preview = context
    file_name = fields.get("file_name") or "selected file"
    line_count = fields.get("line_count") or "unknown"
    word_count = fields.get("word_count") or "unknown"
    truncated = fields.get("truncated") or "false"
    summary = _summarize_preview(preview)
    return (
        f"Workspace file summary for {file_name}: {summary} "
        f"File stats: {line_count} lines, {word_count} words, truncated={truncated}. "
        "No live provider call was made."
    )


def _extract_workspace_context(prompt: str) -> tuple[dict[str, str], str] | None:
    if _WORKSPACE_CONTEXT_HEADER not in prompt:
        return None
    _before_context, context = prompt.rsplit(_WORKSPACE_CONTEXT_HEADER, 1)
    if _CONTENT_PREVIEW_MARKER not in context:
        return None
    metadata, preview = context.split(_CONTENT_PREVIEW_MARKER, 1)
    fields = {match.group("name"): match.group("value").strip() for match in _FIELD_PATTERN.finditer(metadata)}
    if not _REQUIRED_WORKSPACE_FIELDS.issubset(fields):
        return None
    if fields.get("capability") != "workspace_file_access":
        return None
    if not re.fullmatch(r"[a-f0-9]{16}", fields.get("sha256_prefix", "")):
        return None
    return fields, " ".join(preview.split())


def _summarize_preview(preview: str) -> str:
    if not preview:
        return "No readable preview text was provided."
    safe_preview = _redact_secret_like_text(preview)
    words = re.findall(r"[A-Za-z0-9_][A-Za-z0-9_-]{2,}", safe_preview.lower())
    stopwords = {"and", "the", "this", "that", "with", "from", "file", "notes", "public", "secret_redacted"}
    keywords: list[str] = []
    for word in words:
        if word in stopwords or word in keywords or _is_secret_like_keyword(word):
            continue
        keywords.append(word)
        if len(keywords) >= 5:
            break
    if not keywords:
        return "Readable text was provided, but no stable keywords were extracted."
    return f"preview keywords: {', '.join(keywords)}."


def _redact_secret_like_text(text: str) -> str:
    redacted = text
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[secret_redacted]", redacted)
    return redacted


def _is_secret_like_keyword(word: str) -> bool:
    if word.startswith(
        (
            "sk-",
            "aizasy",
            "ghp_",
            "gho_",
            "ghu_",
            "ghs_",
            "ghr_",
            "github_pat_",
            "xoxb-",
            "xoxp-",
            "xoxa-",
            "xoxr-",
            "xoxs-",
            "rk_",
            "pk_",
        )
    ):
        return True
    if len(word) >= 20 and any(char.isalpha() for char in word) and any(char.isdigit() for char in word):
        return True
    return any(marker in word for marker in _SECRET_KEYWORD_MARKERS)
