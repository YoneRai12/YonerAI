from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class SettingSpec:
    key: str
    kind: str  # "env" | "secret"
    category: str
    default: str | None = None
    description: str | None = None
    input: str | None = None  # "bool" | "number" | "text" | "textarea" | "json"
    locked: bool = False  # visible but not editable from UI

    def to_json(self) -> dict:
        return asdict(self)


def _is_secret_key(key: str) -> bool:
    k = (key or "").strip().upper()
    if not k:
        return False

    # OAuth client IDs are not secrets; keep them visible.
    if k.endswith("_CLIENT_ID") or k.endswith("_APP_ID"):
        return False

    # Tokens, API keys, secrets, webhooks.
    hints = (
        "_TOKEN",
        "API_KEY",
        "_SECRET",
        "WEBHOOK",
        "PASSWORD",
        "NEXTAUTH_SECRET",
    )
    if any(h in k for h in hints):
        return True

    # Generic fallback: *_KEY (but not *_PUBLIC_KEY).
    if k.endswith("_KEY") and not k.endswith("_PUBLIC_KEY"):
        return True

    return False


def _category_for(key: str) -> str:
    k = (key or "").strip().upper()
    if not k:
        return "Other"

    if k in {"ADMIN_USER_ID", "SUB_ADMIN_IDS", "VC_ADMIN_IDS"}:
        return "Roles"

    if k.startswith("DISCORD_") or k.endswith("_GUILD_ID") or k.endswith("_CHANNEL_ID") or k.endswith("_ROLE_ID"):
        return "Discord"

    if k.startswith("OPENAI_") or k.startswith("ANTHROPIC_") or k.startswith("GROK_") or k.startswith("GOOGLE_"):
        return "Providers"

    if k.startswith("SEARCH_"):
        return "Search"

    if k.startswith("VOICEVOX_") or k.startswith("STT_") or k.startswith("ORA_VOICE_"):
        return "Voice"

    if k.startswith("LLM_") or k.startswith("ORA_LLM_") or k.startswith("VISION_"):
        return "Models"

    if k.startswith("ORA_PUBLIC_") or k.startswith("ORA_SUBADMIN_") or k.startswith("ORA_OWNER_") or k.startswith(
        "ORA_PRIVATE_"
    ) or k.startswith("ORA_SHARED_") or k in {"ORA_PUBLIC_TOOLS", "ORA_SUBADMIN_TOOLS", "ORA_OWNER_ONLY_TOOLS"}:
        return "Permissions"

    if k.startswith("ORA_APPROVAL_"):
        return "Approvals"

    if k.startswith("ORA_MCP_"):
        return "MCP"

    if k.startswith("ORA_MUSIC_") or k.startswith("ORA_SPOTIFY_"):
        return "Music"

    if k.startswith("ORA_RELAY_") or k.startswith("CLOUDFLARE_") or k.startswith("TUNNEL_"):
        return "Relay/Tunnel"

    if k.startswith("ORA_REMOTION_"):
        return "Remotion"

    if k.startswith("ORA_SANDBOX_"):
        return "Sandbox"

    if k.startswith("ORA_SWARM_"):
        return "Swarm"

    if k.startswith("ORA_SCHEDULER_"):
        return "Scheduler"

    if k.startswith("AUTH_") or k.startswith("NEXTAUTH_") or k.startswith("ORA_CORS_"):
        return "Web/Auth"

    if k.startswith("ORA_TRACE_") or k.startswith("LOG_"):
        return "Logging/Debug"

    if k.startswith("ORA_DATA_") or k.startswith("ORA_STATE_") or k.startswith("ORA_LOG_") or k.startswith(
        "ORA_MEMORY_"
    ) or k.startswith("ORA_TEMP_") or k in {"ORA_BOT_DB", "ORA_DATA_ROOT", "ORA_PROFILE", "ORA_INSTANCE_ID"}:
        return "Storage"

    if k.startswith("BROWSER_") or k.startswith("ORA_BROWSER_") or k.startswith("REQUIRE_BROWSER_"):
        return "Browser"

    if k.endswith("_URL") or "BASE_URL" in k:
        return "URLs"

    return "Other"


def _infer_input_type(key: str, default: str | None, description: str | None) -> str:
    k = (key or "").strip().upper()
    d = (default or "").strip()
    desc = (description or "").lower()

    if k.endswith("_JSON"):
        return "json"

    if d in {"0", "1"}:
        return "bool"

    if d.isdigit() and (k.endswith("_SEC") or k.endswith("_PORT") or k.endswith("_DAYS") or k.endswith("_ROWS") or k.endswith("_BYTES")):
        return "number"

    if "comma-separated" in desc or k.endswith("_IDS") or k.endswith("_TOOLS") or k.endswith("_ORIGINS") or k.endswith("_PATTERNS"):
        return "textarea"

    if len(d) > 80 or "\n" in d:
        return "textarea"

    return "text"


def _parse_env_example_lines(lines: Iterable[str]) -> list[SettingSpec]:
    out: list[SettingSpec] = []
    comment_block: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            comment_block = []
            continue
        if stripped.startswith("#"):
            # Drop leading "# " and keep human text.
            txt = stripped.lstrip("#").strip()
            if txt:
                comment_block.append(txt)
            continue
        if "=" not in stripped:
            comment_block = []
            continue
        key, val = stripped.split("=", 1)
        key = key.strip().upper()
        if not _KEY_RE.match(key):
            comment_block = []
            continue
        default = val.strip()
        desc = "\n".join(comment_block).strip() if comment_block else None
        kind = "secret" if _is_secret_key(key) else "env"
        spec = SettingSpec(
            key=key,
            kind=kind,
            category=_category_for(key),
            default=default or None,
            description=desc,
            input=_infer_input_type(key, default, desc),
        )
        out.append(spec)
        comment_block = []
    return out


def load_settings_schema(*, repo_root: str | None = None) -> list[SettingSpec]:
    """
    Build a UI-friendly settings schema from `.env.example`.

    This is used by the Setup UI and settings endpoints to keep the editable key list in sync.
    """
    root = Path(repo_root or os.getcwd())
    path = root / ".env.example"
    specs: list[SettingSpec] = []
    try:
        if path.exists():
            specs = _parse_env_example_lines(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except Exception:
        specs = []

    # Add a few compatibility/alias keys referenced in code but not always present in .env.example.
    extra = [
        "ORA_LOG_CHANNEL_ID",  # alias for LOG_CHANNEL_ID
        "ORA_PUBLIC_BASE_URL",  # alias for PUBLIC_BASE_URL
        "ORA_BROWSER_REMOTE_TOKEN",  # alias for BROWSER_REMOTE_TOKEN
    ]
    existing = {s.key for s in specs}
    for k in extra:
        if k in existing:
            continue
        specs.append(
            SettingSpec(
                key=k,
                kind="secret" if _is_secret_key(k) else "env",
                category=_category_for(k),
                default=None,
                description="(compat/alias key)",
                input=_infer_input_type(k, None, None),
            )
        )

    # Keys that cannot be safely changed from the profile-scoped override store because
    # they impact early path resolution (profile/instance/data root).
    locked_env = {
        "ORA_DATA_ROOT",
        "ORA_PROFILE",
        "ORA_INSTANCE_ID",
        "ORA_LEGACY_DATA_LAYOUT",
        "ORA_STATE_DIR",
        "ORA_MEMORY_DIR",
        "ORA_LOG_DIR",
        "ORA_TEMP_DIR",
    }
    out2: list[SettingSpec] = []
    for s in specs:
        if s.kind == "env" and s.key in locked_env:
            out2.append(SettingSpec(**{**s.to_json(), "locked": True}))
        else:
            out2.append(s)
    specs = out2

    # Stable order: category then key
    specs.sort(key=lambda s: (s.category, s.key))
    return specs


def secret_filename_for_key(key: str) -> str:
    """
    Map an env key to a stable secrets file name under SECRETS_DIR.
    """
    raw = (key or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_]+", "_", raw)
    raw = raw.strip("_")[:120] or "secret"
    return raw + ".txt"
