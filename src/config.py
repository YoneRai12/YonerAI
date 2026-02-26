"""Configuration loading for the ORA Discord bot."""

from __future__ import annotations

import logging
import json
import os
import sys
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml

# --- Cost Management Constants ---
COST_TZ = "UTC"
# --- Storage & state directory ---
# 1. Environment Variable Priority
# 2. Legacy L: Drive Check (User Environment)
# 3. Default Local 'data' directory

_env_root = os.getenv("ORA_DATA_ROOT")

if _env_root:
    DATA_ROOT = _env_root
else:
    # Default portable path
    DATA_ROOT = os.path.join(os.getcwd(), "data")

def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _sanitize_id(raw: str) -> str:
    """Keep instance/profile identifiers filesystem-friendly."""
    out = "".join(ch for ch in (raw or "").strip() if ch.isalnum() or ch in {"-", "_"})
    return out[:80]


def resolve_profile(default: str = "private") -> str:
    """
    Resolve ORA_PROFILE.
    Note: validation (erroring on invalid values) is done in Config.load().
    """
    raw = (os.getenv("ORA_PROFILE") or default).strip().lower()
    raw = _sanitize_id(raw) or default
    if raw not in {"private", "shared"}:
        return default
    return raw


def resolve_instance_id(data_root: str) -> str:
    """
    Resolve ORA_INSTANCE_ID.
    - If ORA_INSTANCE_ID is set: use it (sanitized).
    - Else: use a persisted UUID in <ORA_DATA_ROOT>/instance_id.txt (stable per PC).
    - In pytest: do not persist to disk.
    """
    explicit = _sanitize_id(os.getenv("ORA_INSTANCE_ID") or "")
    if explicit:
        return explicit

    # Avoid writing files during unit tests/collection.
    if "pytest" in sys.modules:
        return "test-instance"

    root = Path(data_root)
    id_path = root / "instance_id.txt"
    try:
        if id_path.exists():
            val = _sanitize_id(id_path.read_text(encoding="utf-8", errors="ignore"))
            if val:
                return val
    except Exception:
        pass

    new_id = uuid.uuid4().hex
    try:
        root.mkdir(parents=True, exist_ok=True)
        id_path.write_text(new_id, encoding="utf-8")
    except Exception:
        # Fall back to ephemeral ID if the root isn't writable.
        pass
    return new_id


def resolve_state_root(*, data_root: str, instance_id: str, profile: str) -> str:
    return os.path.join(str(data_root), "instances", str(instance_id), str(profile))


def resolve_bot_db_path(raw: Optional[str] = None) -> str:
    """
    Resolve ORA_BOT_DB consistently across bot + web backend + scripts.
    - Absolute/path-like values are used as-is.
    - Bare filenames are placed under DB_DIR for the current profile+instance.
    """
    val = (raw if raw is not None else os.getenv("ORA_BOT_DB")) or ""
    val = val.strip()
    if not val:
        return DEFAULT_DB_PATH
    if os.path.isabs(val) or ("/" in val) or ("\\" in val):
        return val
    return os.path.join(DB_DIR, val)


# Optional escape hatch for older installs that rely on ORA_State/ORA_Logs layout.
USE_LEGACY_DATA_LAYOUT = _parse_bool_env("ORA_LEGACY_DATA_LAYOUT", False)

# Resolve profile + instance first (used by default path computation).
ORA_PROFILE = resolve_profile()
ORA_INSTANCE_ID = resolve_instance_id(DATA_ROOT)
STATE_ROOT = resolve_state_root(data_root=DATA_ROOT, instance_id=ORA_INSTANCE_ID, profile=ORA_PROFILE)
DB_DIR = os.path.join(STATE_ROOT, "db")
SECRETS_DIR = os.path.join(STATE_ROOT, "secrets")

# Define subdirectories based on root
if USE_LEGACY_DATA_LAYOUT:
    # Legacy logic: If simple string like "L:\" is used, we assume root-level folders if matching legacy.
    _is_legacy_style = _env_root and (":" in _env_root) and (len(_env_root) <= 4)
    if _is_legacy_style and os.name == "nt":
        DEFAULT_STATE_DIR = os.path.join(DATA_ROOT, "ORA_State")
        DEFAULT_MEMORY_DIR = os.path.join(DATA_ROOT, "ORA_Memory")
        DEFAULT_TEMP_DIR = os.path.join(DATA_ROOT, "ORA_Temp")
        DEFAULT_LOG_DIR = os.path.join(DATA_ROOT, "ORA_Logs")
    else:
        DEFAULT_STATE_DIR = os.path.join(DATA_ROOT, "state")
        DEFAULT_MEMORY_DIR = os.path.join(DATA_ROOT, "memory")
        DEFAULT_TEMP_DIR = os.path.join(DATA_ROOT, "temp")
        DEFAULT_LOG_DIR = os.path.join(DATA_ROOT, "logs")
else:
    DEFAULT_STATE_DIR = os.path.join(STATE_ROOT, "state")
    DEFAULT_MEMORY_DIR = os.path.join(STATE_ROOT, "memory")
    DEFAULT_TEMP_DIR = os.path.join(STATE_ROOT, "tmp")
    DEFAULT_LOG_DIR = os.path.join(STATE_ROOT, "logs")

STATE_DIR = os.getenv("ORA_STATE_DIR", DEFAULT_STATE_DIR)
MEMORY_DIR = os.getenv("ORA_MEMORY_DIR", DEFAULT_MEMORY_DIR)
LOG_DIR = os.getenv("ORA_LOG_DIR", DEFAULT_LOG_DIR)
TEMP_DIR = os.getenv("ORA_TEMP_DIR", DEFAULT_TEMP_DIR)

# Profile/instance-scoped defaults for paths that are commonly used outside Config.load().
DEFAULT_DB_PATH = os.path.join(DB_DIR, "ora_bot.db")


def _apply_profile_secrets() -> None:
    """
    Optional: allow per-profile secrets without juggling multiple .env files.
    If a file exists under SECRETS_DIR, load it into env.

    Rationale: UI/installer-managed secrets should survive restarts even when .env already
    contains a value. Presence of a secrets file is an explicit local choice, so it wins.
    """
    base = Path(SECRETS_DIR)
    try:
        if not base.exists():
            return
    except Exception:
        return
    for p in base.glob("*.txt"):
        try:
            env_key = (p.stem or "").strip().upper()
            if not env_key:
                continue
            if not all(ch.isalnum() or ch == "_" for ch in env_key):
                continue
            val = p.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        if val:
            os.environ[env_key] = val

    # Compatibility: some components look for either key name.
    brt = (os.getenv("BROWSER_REMOTE_TOKEN") or "").strip()
    obrt = (os.getenv("ORA_BROWSER_REMOTE_TOKEN") or "").strip()
    if brt and not obrt:
        os.environ["ORA_BROWSER_REMOTE_TOKEN"] = brt
    if obrt and not brt:
        os.environ["BROWSER_REMOTE_TOKEN"] = obrt


_apply_profile_secrets()


def _apply_settings_overrides() -> None:
    """
    Optional: allow non-secret config to be set via the local web UI without editing .env.

    - Stored under STATE_DIR so it remains profile/instance-scoped.
    - Default behavior: overrides win for keys present in settings_override.json.
      (The UI exists to avoid editing .env.)
    - Backward compatible: older settings files without a "mode" key behave like "fill".
    """
    from pathlib import Path

    path = Path(STATE_DIR) / "settings_override.json"
    try:
        if not path.exists():
            return
        raw = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(raw, dict):
            return
        mode = (raw.get("mode") or "fill")
        if not isinstance(mode, str):
            mode = "fill"
        mode = mode.strip().lower()
        if mode not in {"fill", "override"}:
            mode = "fill"
        env_map = raw.get("env")
        if not isinstance(env_map, dict):
            return
        for k, v in env_map.items():
            if not isinstance(k, str) or not k.strip():
                continue
            if v is None:
                continue
            if not isinstance(v, str):
                v = str(v)
            if mode == "fill" and (os.getenv(k) or "").strip():
                continue
            os.environ[k] = v
    except Exception:
        return


_apply_settings_overrides()

# ---------------------------------------------------------------------------
# Env aliases (compat)
# ---------------------------------------------------------------------------

def _apply_env_aliases() -> None:
    """
    Keep legacy/alias keys in sync.

    Some parts of the codebase historically used different env var names.
    The Setup UI may also expose alias keys for compatibility.
    """
    pairs = [
        ("PUBLIC_BASE_URL", "ORA_PUBLIC_BASE_URL"),
        ("LOG_CHANNEL_ID", "ORA_LOG_CHANNEL_ID"),
        ("BROWSER_REMOTE_TOKEN", "ORA_BROWSER_REMOTE_TOKEN"),
    ]
    for a, b in pairs:
        av = (os.getenv(a) or "").strip()
        bv = (os.getenv(b) or "").strip()
        if av and not bv:
            os.environ[b] = av
        if bv and not av:
            os.environ[a] = bv


_apply_env_aliases()

# Buffer & Sync Constants
SAFETY_BUFFER_RATIO = 0.95
AUTO_SYNC_INTERVAL = 20  # Increased from 5 to reduce blocking latency

# Burn Lane: Gemini Trial ($300 limit)
# Stable Lane: OpenAI Shared (gp-4o-mini: 2.5M tokens/day!)
# High Lane: OpenAI Shared High (gpt-4o: 250k tokens/day)
# BYOK Lane: User Keys (Optional Limits)
#
# --- External Config Loading ---


def _load_yaml_config() -> dict:
    """Load config.yaml if it exists, otherwise return defaults."""
    path = os.path.join(os.getcwd(), "config.yaml")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load config.yaml: {e}")
    return {}

_external_config = _load_yaml_config()
COST_LIMITS = _external_config.get("cost_limits", {})
ROUTER_CONFIG = _external_config.get("router_config", {})

# Fallback Defaults (Minimal) if YAML is missing
if not COST_LIMITS:
    # (Leaving empty as indicator, or provide minimal fallback)
    COST_LIMITS = {"high": {}, "stable": {}}

if not ROUTER_CONFIG:
    ROUTER_CONFIG = {
        "coding_model": "gpt-5.1-codex-mini",
        "standard_model": "gpt-5.1-codex-mini"
    }

class ConfigError(RuntimeError):
    """Raised when configuration is invalid."""


@dataclass(frozen=True)
class Config:
    """Validated configuration for the bot."""

    profile: str
    instance_id: str
    data_root: str
    state_root: str
    db_dir: str
    secrets_dir: str
    token: str
    app_id: int
    ora_api_base_url: Optional[str]
    ora_core_api_url: Optional[str]
    public_base_url: Optional[str]
    dev_guild_id: Optional[int]
    log_level: str
    log_dir: str
    state_dir: str  # Added
    memory_dir: str # Added
    temp_dir: str   # Added
    db_path: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    privacy_default: str
    # VOICEVOX configuration
    voicevox_api_url: str
    voicevox_speaker_id: int
    # Search API configuration
    search_api_key: Optional[str]
    search_engine: str
    # Speech-to-text configuration
    stt_model: str
    # Default setting for search progress narration (0 = off, 1 = on)
    speak_search_progress_default: int
    admin_user_id: Optional[int]
    # Stable Diffusion Configuration
    sd_api_url: str
    # Gaming Mode
    gaming_processes: List[str]
    model_modes: Dict[str, str]
    router_thresholds: Dict[str, float]
    log_channel_id: int
    startup_notify_channel_id: Optional[int] # Changed from int to Optional[int]
    feature_proposal_channel_id: Optional[int]
    sub_admin_ids: set[int]
    vc_admin_ids: set[int]
    vision_provider: str
    llm_priority: str  # Added Phase 21: cloud or local

    # Core route-band model plan skeleton (v1)
    fast_main_model: str = "gpt-5-mini"
    task_main_model: str = "gpt-5-mini"
    agent_main_model: str = "gpt-5-mini"
    agent_code_model: str = "gpt-5.1-codex-mini"
    agent_security_model: str = "gpt-5-mini"
    agent_search_model: str = "gpt-5-mini"

    # Notification IDs (Phase 42)
    ora_web_notify_id: Optional[int] = None
    ora_api_notify_id: Optional[int] = None
    config_ui_notify_id: Optional[int] = None
    web_chat_notify_id: Optional[int] = None
    config_page_notify_id: Optional[int] = None

    # ComfyUI (Optional)
    comfy_dir: Optional[str] = None
    comfy_bat: Optional[str] = None

    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_default_model: str = "gpt-5-mini"
    gemini_api_key: Optional[str] = None

    # Architecture Mode
    force_standalone: bool = False

    # Auth Strategy (added for Cloudflare Tunnel)
    auth_strategy: str = "local"

    # Model Policies (from YAML)
    model_policies: Dict[str, List[str]] = field(default_factory=dict)

    # Browser Proxy (Software Kill Switch)
    browser_proxy: Optional[str] = None

    # Remote Control Auth Token
    browser_remote_token: Optional[str] = None

    # Tunnel Hostname (Phase 62)
    tunnel_hostname: Optional[str] = None

    # Startup safety (default OFF)
    auto_open_local_interfaces: bool = False
    auto_start_tunnels: bool = False
    tunnels_allow_quick: bool = False

    # Swarm Orchestration (2026 Prep)
    swarm_enabled: bool = False
    swarm_max_tasks: int = 3
    swarm_max_workers: int = 3
    swarm_max_retries: int = 1
    swarm_subtask_timeout_sec: int = 90
    swarm_merge_model: str = "gpt-5-mini"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment variables."""

        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            # CI / tests should not require real secrets. This avoids smoke tests failing on imports.
            allow_missing = os.getenv("ORA_ALLOW_MISSING_SECRETS", "").strip().lower() in {"1", "true", "yes", "on"}
            is_ci = os.getenv("CI", "").strip().lower() in {"1", "true", "yes", "on"}
            try:
                import sys
                is_pytest = "pytest" in sys.modules
            except Exception:
                is_pytest = False
            if allow_missing or is_ci or is_pytest:
                token = "ci_dummy_token"
            else:
                raise ConfigError("環境変数 DISCORD_BOT_TOKEN が未設定です。")

        # Auth Strategy
        auth_strategy = os.getenv("AUTH_STRATEGY", "local").lower()
        if auth_strategy not in {"local", "cloudflare"}:
            auth_strategy = "local"

        llm_priority = os.getenv("ORA_LLM_PRIORITY", "cloud").lower()
        if llm_priority not in {"local", "cloud"}:
            llm_priority = "cloud"

        vision_provider = os.getenv("VISION_PROVIDER", llm_priority).lower()
        if vision_provider not in {"local", "openai"}:
            vision_provider = llm_priority if llm_priority != "cloud" else "openai"

        # Browser Proxy
        browser_proxy = os.getenv("BROWSER_PROXY")

        openai_key = os.getenv("OPENAI_API_KEY")


        app_id_raw = os.getenv("DISCORD_APP_ID")
        if app_id_raw:
            try:
                app_id = int(app_id_raw)
            except ValueError:
                app_id = 0  # Default if invalid
        else:
            app_id = 0  # Optional (Library will auto-fetch)

        ora_base_url = os.getenv("ORA_API_BASE_URL")
        if ora_base_url:
            ora_base_url = ora_base_url.rstrip("/")

        ora_core_url = os.getenv("ORA_CORE_API_URL")
        if ora_core_url:
            ora_core_url = ora_core_url.rstrip("/")

        public_base_url = os.getenv("PUBLIC_BASE_URL")
        if public_base_url:
            public_base_url = public_base_url.rstrip("/")

        dev_guild_raw = os.getenv("ORA_DEV_GUILD_ID")
        dev_guild_id: Optional[int] = None
        if dev_guild_raw:
            try:
                dev_guild_id = int(dev_guild_raw)
            except ValueError as exc:  # pragma: no cover - validation only
                raise ConfigError("ORA_DEV_GUILD_ID は数値で指定してください。") from exc

        log_level_raw = os.getenv("LOG_LEVEL", "INFO").strip()
        if log_level_raw.isdigit():
            val = int(log_level_raw)
            level_name = logging.getLevelName(val)
            if not isinstance(level_name, str) or level_name not in logging.getLevelNamesMapping():
                raise ConfigError(f"LOG_LEVEL に不明な数値 {val} が指定されています。")
            log_level = level_name
        else:
            log_level = log_level_raw.upper()
            if log_level not in logging.getLevelNamesMapping():
                raise ConfigError("LOG_LEVEL に不明な値が指定されています。")

        # Profile selection (M1: private/shared)
        profile_raw = (os.getenv("ORA_PROFILE") or "private").strip().lower()
        if profile_raw not in {"private", "shared"}:
            raise ConfigError("ORA_PROFILE は private または shared を指定してください。")

        instance_id = resolve_instance_id(DATA_ROOT)
        state_root = resolve_state_root(data_root=DATA_ROOT, instance_id=instance_id, profile=profile_raw)
        db_dir = os.path.join(state_root, "db")
        secrets_dir = os.path.join(state_root, "secrets")

        # Ensure DB dir exists (best-effort)
        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception:
            pass

        db_path = resolve_bot_db_path(os.getenv("ORA_BOT_DB"))

        llm_base_url = os.getenv("LLM_BASE_URL", "http://localhost:8008/v1").rstrip("/")
        llm_api_key = os.getenv("LLM_API_KEY", "EMPTY")
        llm_model = os.getenv("LLM_MODEL", "gpt-5-mini")
        default_main_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
        fast_main_model = os.getenv("ORA_FAST_MAIN_MODEL", default_main_model).strip() or default_main_model
        task_main_model = os.getenv("ORA_TASK_MAIN_MODEL", default_main_model).strip() or default_main_model
        agent_main_model = os.getenv("ORA_AGENT_MAIN_MODEL", default_main_model).strip() or default_main_model
        agent_code_model = os.getenv("ORA_AGENT_CODE_MODEL", "gpt-5.1-codex-mini").strip() or "gpt-5.1-codex-mini"
        agent_security_model = os.getenv("ORA_AGENT_SECURITY_MODEL", default_main_model).strip() or default_main_model
        agent_search_model = os.getenv("ORA_AGENT_SEARCH_MODEL", default_main_model).strip() or default_main_model

        privacy_default = os.getenv("PRIVACY_DEFAULT", "private").lower()
        if privacy_default not in {"private", "public"}:
            privacy_default = "private"

        # VoiceVox configuration
        voicevox_api_url = os.getenv("VOICEVOX_API_URL", "http://localhost:50021").rstrip("/")
        voicevox_speaker_id_raw = os.getenv("VOICEVOX_SPEAKER_ID", "1")
        try:
            voicevox_speaker_id = int(voicevox_speaker_id_raw)
        except ValueError:
            voicevox_speaker_id = 1

        # Search API configuration
        search_api_key = os.getenv("SEARCH_API_KEY")
        search_engine = os.getenv("SEARCH_ENGINE", "google")

        # Google Cloud (Gemini API)
        os.getenv("GOOGLE_API_KEY")

        # OpenAI Configuration
        openai_key = os.getenv("OPENAI_API_KEY")

        # Speech-to-text configuration
        stt_model = os.getenv("STT_MODEL", "tiny")

        # Default for speaking search progress (0=off, 1=on)
        speak_search_progress_default_raw = os.getenv("SPEAK_SEARCH_PROGRESS_DEFAULT", "0")
        try:
            speak_search_progress_default = int(speak_search_progress_default_raw)
        except ValueError:
            speak_search_progress_default = 0
        speak_search_progress_default = 1 if speak_search_progress_default else 0

        # Admin User ID
        admin_user_id_raw = os.getenv("ADMIN_USER_ID")
        admin_user_id: Optional[int] = None
        if admin_user_id_raw:
            try:
                admin_user_id = int(admin_user_id_raw)
            except ValueError:
                pass

        # Sub Admins & VC Admins (List)
        sub_admin_ids = set()
        sub_admin_raw = os.getenv("SUB_ADMIN_IDS", "")
        if sub_admin_raw:
            try:
                sub_admin_ids = {int(x.strip()) for x in sub_admin_raw.split(",") if x.strip()}
            except Exception:
                pass

        vc_admin_ids = set()
        vc_admin_raw = os.getenv("VC_ADMIN_IDS", "")
        if vc_admin_raw:
            try:
                vc_admin_ids = {int(x.strip()) for x in vc_admin_raw.split(",") if x.strip()}
            except Exception:
                pass

        def _parse_optional_int(value: Optional[str]) -> Optional[int]:
            if value is None:
                return None
            cleaned = value.strip().strip('"').strip("'")
            if not cleaned:
                return None
            try:
                return int(cleaned)
            except ValueError:
                return None

        # Debug Log Channel
        log_channel_raw = os.getenv("ORA_LOG_CHANNEL_ID") or os.getenv("LOG_CHANNEL_ID", "0")  # Support both keys
        log_channel_id = _parse_optional_int(log_channel_raw) or 0

        # Startup Notification Channel (Separate from logs)
        startup_channel_raw = os.getenv("STARTUP_NOTIFY_CHANNEL_ID")
        startup_notify_channel_id: Optional[int] = _parse_optional_int(startup_channel_raw)

        # Feature Proposal Channel
        proposal_channel_raw = os.getenv("FEATURE_PROPOSAL_CHANNEL_ID")
        feature_proposal_channel_id: Optional[int] = _parse_optional_int(proposal_channel_raw)

        # Memory & State Dirs are handled globally at top

        # Gaming Processes
        gaming_processes_str = os.getenv("GAMING_PROCESSES", "valorant.exe,javaw.exe,ffxiv_dx11.exe,osu!.exe")
        gaming_processes = [p.strip() for p in gaming_processes_str.split(",") if p.strip()]

        # Notification IDs
        ora_web_notify_raw = os.getenv("ORA_WEB_NOTIFY_ID")
        ora_web_notify_id = _parse_optional_int(ora_web_notify_raw)

        ora_api_notify_raw = os.getenv("ORA_API_NOTIFY_ID")
        ora_api_notify_id = _parse_optional_int(ora_api_notify_raw)

        config_ui_notify_raw = os.getenv("CONFIG_UI_NOTIFY_ID")
        config_ui_notify_id = _parse_optional_int(config_ui_notify_raw)

        web_chat_notify_raw = os.getenv("WEB_CHAT_NOTIFY_ID")
        web_chat_notify_id = _parse_optional_int(web_chat_notify_raw)

        config_page_notify_raw = os.getenv("CONFIG_PAGE_NOTIFY_ID")
        config_page_notify_id = _parse_optional_int(config_page_notify_raw)

        tunnel_hostname = os.getenv("TUNNEL_HOSTNAME")

        def _parse_bool_env(name: str, default: bool = False) -> bool:
            raw = os.getenv(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        # Startup safety toggles (default OFF unless explicitly enabled)
        auto_open_local_interfaces = _parse_bool_env("ORA_AUTO_OPEN_LOCAL_INTERFACES", False) or _parse_bool_env(
            "ORA_AUTO_OPEN_UI", False
        )
        auto_start_tunnels = _parse_bool_env("ORA_AUTO_START_TUNNELS", False) or _parse_bool_env(
            "ORA_AUTO_TUNNEL", False
        )
        tunnels_allow_quick = _parse_bool_env("ORA_TUNNELS_ALLOW_QUICK", False)

        # Model Modes Configuration
        # Maps mode name to batch file name
        model_modes = {
            "instruct": "start_vllm_instruct.bat",
            "thinking": "start_vllm_thinking.bat",
            "gaming": "start_vllm_gaming.bat",
        }

        # Router Thresholds
        router_thresholds = {
            "confidence_cutoff": 0.72,
            "sticky_duration": 180.0,  # seconds
        }

        # Stable Diffusion & ComfyUI
        sd_api_url = os.getenv("SD_API_URL", "http://127.0.0.1:7860")
        comfy_dir = os.getenv("COMFY_DIR")
        comfy_bat = os.getenv("COMFY_BAT")

        # Swarm Orchestration
        swarm_enabled = os.getenv("ORA_SWARM_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
        swarm_max_tasks = _parse_optional_int(os.getenv("ORA_SWARM_MAX_TASKS")) or 3
        swarm_max_workers = _parse_optional_int(os.getenv("ORA_SWARM_MAX_WORKERS")) or 3
        swarm_max_retries = _parse_optional_int(os.getenv("ORA_SWARM_MAX_RETRIES")) or 1
        swarm_subtask_timeout_sec = _parse_optional_int(os.getenv("ORA_SWARM_SUBTASK_TIMEOUT_SEC")) or 90
        swarm_merge_model = os.getenv("ORA_SWARM_MERGE_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"

        return cls(
            profile=profile_raw,
            instance_id=instance_id,
            data_root=DATA_ROOT,
            state_root=state_root,
            db_dir=db_dir,
            secrets_dir=secrets_dir,
            token=token,
            app_id=app_id,
            ora_api_base_url=ora_base_url,
            ora_core_api_url=ora_core_url,
            public_base_url=public_base_url,
            dev_guild_id=dev_guild_id,
            log_level=log_level,
            log_dir=LOG_DIR,
            state_dir=STATE_DIR,
            memory_dir=MEMORY_DIR,
            temp_dir=TEMP_DIR,
            db_path=db_path,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            privacy_default=privacy_default,
            voicevox_api_url=voicevox_api_url,
            voicevox_speaker_id=voicevox_speaker_id,
            search_api_key=search_api_key,
            search_engine=search_engine,
            stt_model=stt_model,
            speak_search_progress_default=speak_search_progress_default,
            admin_user_id=admin_user_id,
            sd_api_url=sd_api_url,
            comfy_dir=comfy_dir,
            comfy_bat=comfy_bat,
            gaming_processes=gaming_processes,
            model_modes=model_modes,
            router_thresholds=router_thresholds,
            openai_api_key=openai_key,
            openai_default_model=os.getenv("OPENAI_DEFAULT_MODEL", "gpt-5-mini"),
            gemini_api_key=os.getenv("GOOGLE_API_KEY"),
            log_channel_id=log_channel_id,
            startup_notify_channel_id=startup_notify_channel_id,
            sub_admin_ids=sub_admin_ids,
            vc_admin_ids=vc_admin_ids,
            feature_proposal_channel_id=feature_proposal_channel_id,
            vision_provider=vision_provider,
            llm_priority=llm_priority,
            fast_main_model=fast_main_model,
            task_main_model=task_main_model,
            agent_main_model=agent_main_model,
            agent_code_model=agent_code_model,
            agent_security_model=agent_security_model,
            agent_search_model=agent_search_model,
            ora_web_notify_id=ora_web_notify_id,
            ora_api_notify_id=ora_api_notify_id,
            config_ui_notify_id=config_ui_notify_id,
            web_chat_notify_id=web_chat_notify_id,
            config_page_notify_id=config_page_notify_id,
            tunnel_hostname=tunnel_hostname,
            auto_open_local_interfaces=auto_open_local_interfaces,
            auto_start_tunnels=auto_start_tunnels,
            tunnels_allow_quick=tunnels_allow_quick,
            # comfy_dir already passed above at line 373
            force_standalone=os.getenv("FORCE_STANDALONE", "false").lower() == "true",
            auth_strategy=auth_strategy,
            model_policies=_external_config.get("model_policies", {}),
            browser_proxy=browser_proxy,
            browser_remote_token=os.getenv("BROWSER_REMOTE_TOKEN"),
            swarm_enabled=swarm_enabled,
            swarm_max_tasks=max(1, min(8, swarm_max_tasks)),
            swarm_max_workers=max(1, min(8, swarm_max_workers)),
            swarm_max_retries=max(0, min(5, swarm_max_retries)),
            swarm_subtask_timeout_sec=max(20, min(600, swarm_subtask_timeout_sec)),
            swarm_merge_model=swarm_merge_model,
        )

    def validate(self) -> None:
        """Validate configuration and log warnings for missing optional values."""
        logger = logging.getLogger(__name__)

        if not self.admin_user_id:
            logger.debug("ADMIN_USER_ID is not set. Admin-only commands will be unavailable.")

        if not self.search_api_key:
            logger.debug("SEARCH_API_KEY is not set. Web search will use DuckDuckGo (slower/rate-limited).")

        if not self.dev_guild_id:
            logger.info("ORA_DEV_GUILD_ID is not set. Commands will be synced globally (can take up to 1 hour).")
