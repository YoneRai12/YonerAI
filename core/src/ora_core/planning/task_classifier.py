from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal


TaskCategory = Literal[
    "simple_chat",
    "summarize_public",
    "research_like",
    "coding",
    "local_private_file",
    "pc_operation",
    "dangerous_operation",
    "long_running",
    "unsupported",
]
TaskRisk = Literal[
    "safe_public",
    "external_provider",
    "private_data",
    "local_tool",
    "pc_operation",
    "dangerous",
    "unsupported",
]
TaskComplexity = Literal["simple", "standard", "advanced", "long_running", "unsupported"]
RequiredCapability = Literal[
    "chat",
    "structured_output",
    "public_context",
    "web_research",
    "coding",
    "private_files",
    "local_tools",
    "pc_operations",
    "dangerous_operations",
    "long_running",
    "unsupported",
]


@dataclass(frozen=True)
class TaskClassification:
    category: TaskCategory
    risk: TaskRisk
    complexity: TaskComplexity
    required_capabilities: tuple[RequiredCapability, ...]
    reasons: tuple[str, ...]

    def to_public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["required_capabilities"] = list(self.required_capabilities)
        payload["reasons"] = list(self.reasons)
        return payload


_LOCAL_PATH_RE = re.compile(r"(?:^|[\s\"'(<])(?:[A-Za-z]:[\\/]|/(?:home|users|root|etc|var|tmp)/)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://", re.IGNORECASE)


def classify_task(task_text: str) -> TaskClassification:
    text = " ".join(str(task_text or "").split())
    low = text.lower()
    if not text:
        return _classification(
            "unsupported",
            "unsupported",
            "unsupported",
            ("unsupported",),
            ("empty_task",),
        )

    if _contains_any(low, ("live discord", "discord token", "google login", "persistent memory", "production db")):
        return _classification(
            "unsupported",
            "unsupported",
            "unsupported",
            ("unsupported",),
            ("private_or_live_feature_not_available_in_public_repo",),
        )

    if _contains_any(
        low,
        (
            "rm -rf",
            "format disk",
            "wipe",
            "delete all",
            "delete file",
            "drop database",
            "production deploy",
            "deploy to production",
            "use discord token",
        ),
    ):
        return _classification(
            "dangerous_operation",
            "dangerous",
            "advanced",
            ("dangerous_operations", "pc_operations"),
            ("destructive_or_live_operation_requested",),
        )

    if _contains_any(low, ("powershell", "shell", "terminal", "command", "execute", "run script", "install ", "path ")):
        return _classification(
            "pc_operation",
            "pc_operation",
            "advanced",
            ("pc_operations", "local_tools"),
            ("pc_or_shell_surface_requested",),
        )

    if _LOCAL_PATH_RE.search(text) or _contains_any(
        low,
        ("my local file", "local file", "private file", "my file", "desktop file", "documents folder", "private data"),
    ):
        return _classification(
            "local_private_file",
            "private_data",
            "advanced",
            ("private_files",),
            ("local_or_private_data_requested",),
        )

    if _contains_any(low, ("long running", "batch", "hours", "gpu", "large codebase", "whole repo")):
        return _classification(
            "long_running",
            "local_tool",
            "long_running",
            ("long_running", "coding"),
            ("long_running_or_large_codebase_requested",),
        )

    if _contains_any(low, ("code", "bug", "test", "pytest", "refactor", "implement", "fix ", "python", "typescript")):
        return _classification(
            "coding",
            "external_provider",
            "advanced",
            ("coding", "structured_output"),
            ("coding_or_runtime_change_requested",),
        )

    if _contains_any(low, ("research", "latest", "look up", "lookup", "search", "web")) or _URL_RE.search(text):
        return _classification(
            "research_like",
            "external_provider",
            "standard",
            ("web_research", "public_context"),
            ("research_like_public_context_requested",),
        )

    if _contains_any(low, ("summarize", "summary", "readme", "public docs", "docs")):
        return _classification(
            "summarize_public",
            "safe_public",
            "standard",
            ("public_context", "structured_output"),
            ("public_summarization_requested",),
        )

    return _classification(
        "simple_chat",
        "safe_public",
        "simple",
        ("chat",),
        ("default_simple_public_chat",),
    )


def _classification(
    category: TaskCategory,
    risk: TaskRisk,
    complexity: TaskComplexity,
    required_capabilities: tuple[RequiredCapability, ...],
    reasons: tuple[str, ...],
) -> TaskClassification:
    return TaskClassification(
        category=category,
        risk=risk,
        complexity=complexity,
        required_capabilities=required_capabilities,
        reasons=reasons,
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
