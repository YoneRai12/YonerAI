"""Configuration loading for the ORA Discord bot."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

# --- Cost Management Constants ---
COST_TZ = "UTC"
if os.name == "nt":
    STATE_DIR = r"L:\ORA_State"
else:
    # Mac/Linux path
    STATE_DIR = os.path.expanduser("~/ORA_State")

# Buffer & Sync Constants
SAFETY_BUFFER_RATIO = 0.95
AUTO_SYNC_INTERVAL = 20  # Increased from 5 to reduce blocking latency

# Burn Lane: Gemini Trial ($300 limit)
# Stable Lane: OpenAI Shared (gp-4o-mini: 2.5M tokens/day!)
# High Lane: OpenAI Shared High (gpt-4o: 250k tokens/day)
# BYOK Lane: User Keys (Optional Limits)
#
# --- USER DEFINED MODEL LIMITS (2026 Policy) ---
# "gpt-5.1, gpt-5.1-codex, gpt-5, gpt-5-codex, gpt-5-chat-latest, gpt-4.1, gpt-4o, o1, o3
#  全体で 1 日あたり最大 25 万トークン"
#
# "gpt-5.1-codex-mini, gpt-5-mini, gpt-5-nano, gpt-4.1-mini, gpt-4.1-nano, gpt-4o-mini,
#  o1-mini, o3-mini, o4-mini, codex-mini-latest
#  全体で 1 日あたり最大 250 万トークン"
# -----------------------------------------------
COST_LIMITS = {
    "high": {
        "openai": {
            "daily_tokens": 250_000,
            "hard_stop": True,
            "models": {
                "gpt-5.1",
                "gpt-5.1-codex",
                "gpt-5",
                "gpt-5-codex",
                "gpt-5-chat-latest",
                "gpt-4.1",
                "gpt-4o",
                "o1",
                "o3",
            },
        },
    },
    "stable": {
        "openai": {
            "daily_tokens": 2_500_000,
            "hard_stop": True,
            "models": {
                "gpt-5.1-codex-mini",
                "gpt-5-mini",
                "gpt-5-nano",
                "gpt-4.1-mini",
                "gpt-4.1-nano",
                "gpt-4o-mini",
                "o1-mini",
                "o3-mini",
                "o4-mini",
                "codex-mini-latest",
            },
        },
        "gemini_dev": {"daily_tokens": 200_000, "monthly_tokens": 2_000_000, "hard_stop": True},
    },
    "burn": {
        "gemini_trial": {"total_usd": 300.0, "hard_stop": True},
    },
    "byok": {
        "openai": {"hard_stop": False},
        "claude": {"hard_stop": False},
        "grok": {"hard_stop": False},
    },
}

# --- Router Configuration ---
ROUTER_CONFIG = {
    "coding_model": "gpt-5.1-codex",  # Reverted to codex with /responses endpoint fix
    "high_intel_model": "gpt-5.1",
    "standard_model": "gpt-5-mini",
    "vision_model": "gemini-2.0-flash-exp",
    "coding_keywords": [
        "コード",
        "実装",
        "バグ",
        "エラー",
        "修正",
        "関数",
        "変数",
        "API",
        "python",
        "javascript",
        "program",
        "tree",
        "structure",
        "file",
        "list",
        "check",
        "system",
        "deploy",
        "debug",
        "fix",
        "html",
        "css",
        "ts",
        "tsx",
        "jsx",
        "json",
        "config",
        "ツリー",
        "構成",
        "ファイル",
        "システム",
        "デバッグ",
        "直して",
        "確認",
        "フォルダ",
        "ディレクトリ",
        "階層",
    ],
    "high_intel_keywords": ["解説", "詳しく", "理由", "分析", "なぜ", "とは", "比較", "設計"],
    "complexity_char_threshold": 50,
}


class ConfigError(RuntimeError):
    """Raised when configuration is invalid."""


@dataclass(frozen=True)
class Config:
    """Validated configuration for the bot."""

    token: str
    app_id: int
    ora_api_base_url: Optional[str]
    public_base_url: Optional[str]
    dev_guild_id: Optional[int]
    log_level: str
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

    # External API Keys (Phase 29)
    openai_api_key: Optional[str]
    gemini_api_key: Optional[str]  # Already loaded as GOOGLE_API_KEY in env, but good to have here?
    # actually GOOGLE_API_KEY is used by google_client directly from os.environ usually.
    # Let's standardize on Config.
    log_channel_id: int
    startup_notify_channel_id: Optional[int]
    sub_admin_ids: set[int]
    vc_admin_ids: set[int]
    feature_proposal_channel_id: Optional[int]
    vision_provider: str

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment variables."""

        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            raise ConfigError("環境変数 DISCORD_BOT_TOKEN が未設定です。")

        vision_provider = os.getenv("VISION_PROVIDER", "local").lower()
        if vision_provider not in {"local", "openai"}:
            vision_provider = "local"  # Fallback

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
            level_name = logging.getLevelName(int(log_level_raw))
            if not isinstance(level_name, str) or level_name not in logging.getLevelNamesMapping():
                raise ConfigError("LOG_LEVEL に不明な値が指定されています。")
            log_level = level_name
        else:
            log_level = log_level_raw.upper()
            if log_level not in logging.getLevelNamesMapping():
                raise ConfigError("LOG_LEVEL に不明な値が指定されています。")

        db_path = os.getenv("ORA_BOT_DB", "ora_bot.db")

        llm_base_url = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1").rstrip("/")
        llm_api_key = os.getenv("LLM_API_KEY", "EMPTY")
        llm_model = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct-AWQ")

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
        google_api_key = os.getenv("GOOGLE_API_KEY")

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
            except:
                pass

        vc_admin_ids = set()
        vc_admin_raw = os.getenv("VC_ADMIN_IDS", "")
        if vc_admin_raw:
            try:
                vc_admin_ids = {int(x.strip()) for x in vc_admin_raw.split(",") if x.strip()}
            except:
                pass

        # Debug Log Channel
        log_channel_raw = os.getenv("ORA_LOG_CHANNEL_ID") or os.getenv("LOG_CHANNEL_ID", "0")  # Support both keys
        try:
            log_channel_id = int(log_channel_raw)
        except ValueError:
            log_channel_id = 0

        # Startup Notification Channel (Separate from logs)
        startup_channel_raw = os.getenv("STARTUP_NOTIFY_CHANNEL_ID")
        startup_notify_channel_id: Optional[int] = None
        if startup_channel_raw:
            try:
                startup_notify_channel_id = int(startup_channel_raw)
            except ValueError:
                pass

        # Feature Proposal Channel
        proposal_channel_raw = os.getenv("FEATURE_PROPOSAL_CHANNEL_ID")
        feature_proposal_channel_id: Optional[int] = None
        if proposal_channel_raw:
            try:
                feature_proposal_channel_id = int(proposal_channel_raw)
            except ValueError:
                pass

        # Stable Diffusion API
        sd_api_url = "http://127.0.0.1:8188"  # Force ComfyUI Port

        # Gaming Processes
        gaming_processes_str = os.getenv("GAMING_PROCESSES", "valorant.exe,javaw.exe,ffxiv_dx11.exe,osu!.exe")
        gaming_processes = [p.strip() for p in gaming_processes_str.split(",") if p.strip()]

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

        return cls(
            token=token,
            app_id=app_id,
            ora_api_base_url=ora_base_url,
            public_base_url=public_base_url,
            dev_guild_id=dev_guild_id,
            log_level=log_level,
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
            sd_api_url=os.getenv("SD_API_URL", "http://127.0.0.1:7860"),
            gaming_processes=gaming_processes,
            model_modes=model_modes,
            router_thresholds=router_thresholds,
            openai_api_key=openai_key,
            gemini_api_key=os.getenv("GOOGLE_API_KEY"),
            log_channel_id=log_channel_id,
            startup_notify_channel_id=startup_notify_channel_id,
            sub_admin_ids=sub_admin_ids,
            vc_admin_ids=vc_admin_ids,
            feature_proposal_channel_id=feature_proposal_channel_id,
            vision_provider=vision_provider,
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
