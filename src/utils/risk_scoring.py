from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    level: str  # LOW | MEDIUM | HIGH | CRITICAL
    reasons: List[str]


_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_sk", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("pem_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt_like", re.compile(r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")),
    ("discord_webhook", re.compile(r"discord\.com/api/webhooks/\d+/\S+")),
]


def _iter_strings(value: Any) -> Iterable[str]:
    if value is None:
        return
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                yield k
            yield from _iter_strings(v)
        return
    if isinstance(value, list):
        for it in value:
            yield from _iter_strings(it)


def _risk_level(score: int) -> str:
    if score >= 90:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


def score_tool_risk(tool_name: str, args: Dict[str, Any] | None, *, tags: List[str] | None = None) -> RiskAssessment:
    name = (tool_name or "").lower()
    tags_set = {str(t).lower() for t in (tags or [])}
    args = args or {}

    score = 0
    reasons: list[str] = []

    # 0) Tag-based hints (registry-supplied)
    # Keep these conservative; policy/allowlists still decide what runs.
    if "download" in tags_set:
        score += 35
        reasons.append("tag:download(+35)")
    if "sandbox" in tags_set:
        score += 10
        reasons.append("tag:sandbox(+10)")

    # 1) Base score by tool type/name
    if name.startswith("mcp__") or "mcp" in tags_set:
        score += 35
        reasons.append("mcp_remote_tool(+35)")

    read_markers = ("read", "grep", "find", "tree", "list", "get_", "fetch", "recall")
    if any(m in name for m in read_markers) and not any(m in name for m in ("delete", "remove", "wipe", "reset", "push", "publish")):
        score += 5
        reasons.append("read_like(+5)")

    write_markers = ("write", "edit", "apply", "patch", "update", "set_", "create", "generate")
    if any(m in name for m in write_markers):
        score += 30
        reasons.append("write_like(+30)")

    delete_markers = ("delete", "remove", "wipe", "format", "reset")
    if any(m in name for m in delete_markers):
        score += 60
        reasons.append("delete_or_reset(+60)")

    external_markers = ("publish", "deploy", "release", "push", "webhook")
    if any(m in name for m in external_markers):
        score += 80
        reasons.append("external_publish_like(+80)")

    shell_markers = ("system_control", "system_shell", "safe_shell", "shell", "cmd", "powershell")
    if any(m in name for m in shell_markers) or "system_control" in name:
        score += 60
        reasons.append("command_execution(+60)")

    browser_control = {"web_remote_control", "web_action", "web_record_screen", "web_set_view", "web_navigate"}
    if name in browser_control:
        score += 70
        reasons.append("remote_browser_control(+70)")
    if name == "web_download":
        score += 60
        reasons.append("download(+60)")

    # 2) Args-based risk bumps
    # Path traversal / outside workspace heuristics
    workspace_root = os.getcwd().replace("\\", "/").lower()
    for s in _iter_strings(args):
        low = s.replace("\\", "/").lower()
        if "../" in low or low.startswith(".."):
            score += 40
            reasons.append("path_traversal_like(+40)")
            break
        if re.match(r"^[a-z]:/", low) or low.startswith("/"):
            # absolute paths are higher risk than workspace-relative
            score += 30
            reasons.append("absolute_path(+30)")
            break

    # Sensitive file targets
    sensitive_files = (".env", "secrets", "token", "credentials", "service-account.json")
    for s in _iter_strings(args):
        low = s.lower()
        if any(x in low for x in sensitive_files):
            score += 50
            reasons.append("sensitive_target(+50)")
            break

    # Secret-looking strings in args
    for s in _iter_strings(args):
        for label, pat in _SECRET_PATTERNS:
            if pat.search(s):
                score += 80
                reasons.append(f"secret_like:{label}(+80)")
                # One hit is enough to push to CRITICAL
                break
        else:
            continue
        break

    # Clamp
    score = max(0, min(200, score))
    lvl = _risk_level(score)
    return RiskAssessment(score=score, level=lvl, reasons=reasons)
