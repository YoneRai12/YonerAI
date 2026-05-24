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


_WORKSPACE_CONTEXT_MARKER = "Workspace file context follows."
_FIELD_PATTERN = re.compile(r"^(?P<name>[a-z_]+): (?P<value>.*)$", re.MULTILINE)


def _workspace_file_summary_response(prompt: str) -> str | None:
    if _WORKSPACE_CONTEXT_MARKER not in prompt:
        return None
    fields = {match.group("name"): match.group("value").strip() for match in _FIELD_PATTERN.finditer(prompt)}
    preview = _extract_content_preview(prompt)
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


def _extract_content_preview(prompt: str) -> str:
    marker = "content_preview:\n"
    if marker not in prompt:
        return ""
    return " ".join(prompt.split(marker, 1)[1].split())


def _summarize_preview(preview: str) -> str:
    if not preview:
        return "No readable preview text was provided."
    words = re.findall(r"[A-Za-z0-9_][A-Za-z0-9_-]{2,}", preview.lower())
    stopwords = {"and", "the", "this", "that", "with", "from", "file", "notes", "public"}
    keywords: list[str] = []
    for word in words:
        if word in stopwords or word in keywords:
            continue
        keywords.append(word)
        if len(keywords) >= 5:
            break
    if not keywords:
        return "Readable text was provided, but no stable keywords were extracted."
    return f"preview keywords: {', '.join(keywords)}."
