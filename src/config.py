"""Configuration loading for the ORA Discord bot."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional


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
    gaming_processes: list[str]

    # Model Modes (Router)
    model_modes: dict[str, str]
    router_thresholds: dict[str, float]

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from environment variables."""

        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            raise ConfigError("環境変数 DISCORD_BOT_TOKEN が未設定です。")

        app_id_raw = os.getenv("DISCORD_APP_ID")
        if app_id_raw:
            try:
                app_id = int(app_id_raw)
            except ValueError:
                app_id = 0 # Default if invalid
        else:
            app_id = 0 # Optional (Library will auto-fetch)

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

            except ValueError:
                pass
                
        # Stable Diffusion API
        sd_api_url = "http://127.0.0.1:8188" # Force ComfyUI Port
        
        # Gaming Processes
        gaming_processes_str = os.getenv("GAMING_PROCESSES", "valorant.exe,javaw.exe,ffxiv_dx11.exe,osu!.exe")
        gaming_processes = [p.strip() for p in gaming_processes_str.split(",") if p.strip()]

        # Model Modes Configuration
        # Maps mode name to batch file name
        model_modes = {
            "instruct": "start_vllm_instruct.bat",
            "thinking": "start_vllm_thinking.bat",
            "gaming": "start_vllm_gaming.bat"
        }
        
        # Router Thresholds
        router_thresholds = {
            "confidence_cutoff": 0.72,
            "sticky_duration": 180.0  # seconds
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
            sd_api_url=sd_api_url,
            gaming_processes=gaming_processes,
            model_modes=model_modes,
            router_thresholds=router_thresholds,
        )

    def validate(self) -> None:
        """Validate configuration and log warnings for missing optional values."""
        logger = logging.getLogger(__name__)
        
        if not self.admin_user_id:
            logger.warning("ADMIN_USER_ID is not set. Admin-only commands will be unavailable.")
        
        if not self.search_api_key:
            logger.warning("SEARCH_API_KEY is not set. Web search will use DuckDuckGo (slower/rate-limited).")
            
        if not self.dev_guild_id:
            logger.info("ORA_DEV_GUILD_ID is not set. Commands will be synced globally (can take up to 1 hour).")
