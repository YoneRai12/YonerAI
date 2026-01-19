
import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Dict, Literal, Optional

from src.config import STATE_DIR

logger = logging.getLogger("ORA.UserPrefs")

Mode = Literal["private", "smart"]

@dataclass
class UserConfig:
    mode: Mode
    onboarded_at_iso: str
    allow_cloud_images: bool = False # Future extension

class UserPrefs:
    def __init__(self):
        self.state_file = os.path.join(STATE_DIR, "user_prefs.json")
        self.prefs: Dict[str, UserConfig] = {} # user_id -> UserConfig
        self._load()

    def _load(self):
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for uid, raw in data.items():
                    self.prefs[uid] = UserConfig(**raw)
        except Exception as e:
            logger.error(f"Failed to load user prefs: {e}")

    def _save(self):
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                raw = {k: asdict(v) for k, v in self.prefs.items()}
                json.dump(raw, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save user prefs: {e}")

    def get_mode(self, user_id: int) -> Optional[Mode]:
        user_str = str(user_id)
        if user_str in self.prefs:
            return self.prefs[user_str].mode
        return None

    def set_mode(self, user_id: int, mode: Mode):
        from datetime import datetime
        user_str = str(user_id)
        self.prefs[user_str] = UserConfig(
            mode=mode,
            onboarded_at_iso=datetime.now().isoformat()
        )
        self._save()

    def is_onboarded(self, user_id: int) -> bool:
        return str(user_id) in self.prefs
