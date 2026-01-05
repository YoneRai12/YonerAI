
import json
import os
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta
import pytz
from typing import Dict, Optional, Literal, Any
from src.config import COST_LIMITS, COST_TZ, STATE_DIR

logger = logging.getLogger("ORA.CostManager")

Lane = Literal["burn", "stable", "byok"]
Provider = Literal["local", "openai", "gemini_dev", "gemini_trial", "claude", "grok"]

@dataclass
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0

    def add(self, other: 'Usage'):
        self.tokens_in += other.tokens_in
        self.tokens_out += other.tokens_out
        self.usd += other.usd
    
    def sub(self, other: 'Usage'):
        self.tokens_in = max(0, self.tokens_in - other.tokens_in)
        self.tokens_out = max(0, self.tokens_out - other.tokens_out)
        self.usd = max(0.0, self.usd - other.usd)

@dataclass
class Bucket:
    day: str              # YYYY-MM-DD (JST)
    month: str            # YYYY-MM (JST)
    used: Usage = field(default_factory=Usage)
    reserved: Usage = field(default_factory=Usage)  # in-flight
    hard_stopped: bool = False
    last_update_iso: str = ""

@dataclass
class AllowDecision:
    allowed: bool
    reason: str = ""
    fallback_to: Optional[Provider] = None

class CostManager:
    def __init__(self):
        self.state_file = os.path.join(STATE_DIR, "cost_state.json")
        self.timezone = pytz.timezone(COST_TZ)
        self.global_buckets: Dict[str, Bucket] = {} # key = f"{lane}:{provider}"
        self.user_buckets: Dict[str, Dict[str, Bucket]] = {} # user_id -> (key -> Bucket)
        
        # New: History Storage
        # Structure: key -> List[Bucket]
        self.global_history: Dict[str, list[Bucket]] = {} 
        self.user_history: Dict[str, Dict[str, list[Bucket]]] = {}
        self.global_hourly: Dict[str, Dict[str, Usage]] = {}
        self.user_hourly: Dict[str, Dict[str, Dict[str, Usage]]] = {}

        self._load_state()

    def _get_current_time_keys(self):
        now = datetime.now(self.timezone)
        return now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")

    def _get_current_hour_key(self) -> str:
        now = datetime.now(self.timezone)
        return now.strftime("%Y-%m-%dT%H")

    def _get_bucket_key(self, lane: Lane, provider: Provider) -> str:
        return f"{lane}:{provider}"

    def _load_state(self):
        if not os.path.exists(self.state_file):
            logger.info("No cost state file found. Starting fresh.")
            return
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Restore Global Buckets
            for k, v in data.get("global_buckets", {}).items():
                self.global_buckets[k] = self._dict_to_bucket(v)
            
            # Restore Global History
            for k, v_list in data.get("global_history", {}).items():
                self.global_history[k] = [self._dict_to_bucket(b) for b in v_list]

            # Restore User Buckets
            for user_id, user_data in data.get("user_buckets", {}).items():
                self.user_buckets[user_id] = {k: self._dict_to_bucket(v) for k, v in user_data.items()}

            # Restore User History
            for user_id, user_hist_data in data.get("user_history", {}).items():
                self.user_history[user_id] = {k: [self._dict_to_bucket(b) for b in v_list] for k, v_list in user_hist_data.items()}

            # Restore Hourly Usage (Optional)
            for k, hour_map in data.get("global_hourly", {}).items():
                self.global_hourly[k] = {hour: self._dict_to_usage(u) for hour, u in hour_map.items()}
            for user_id, user_hour_map in data.get("user_hourly", {}).items():
                self.user_hourly[user_id] = {
                    k: {hour: self._dict_to_usage(u) for hour, u in hour_map.items()}
                    for k, hour_map in user_hour_map.items()
                }
                
            logger.info("Cost state loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load cost state: {e}")

    def _dict_to_bucket(self, data: dict) -> Bucket:
        return Bucket(
            day=data["day"],
            month=data["month"],
            used=Usage(**data["used"]),
            reserved=Usage(**data["reserved"]),
            hard_stopped=data.get("hard_stopped", False),
            last_update_iso=data.get("last_update_iso", "")
        )

    def _dict_to_usage(self, data: dict) -> Usage:
        return Usage(**data)

    def _prune_hourly(self, hour_map: Dict[str, Usage]) -> None:
        cutoff = datetime.now(self.timezone).replace(tzinfo=None) - timedelta(days=7)
        for hour in list(hour_map.keys()):
            try:
                dt = datetime.strptime(hour, "%Y-%m-%dT%H")
                if dt < cutoff:
                    del hour_map[hour]
            except ValueError:
                # If parsing fails, drop malformed keys to keep data clean.
                del hour_map[hour]

    def _add_hourly_usage(self, lane: Lane, provider: Provider, user_id: Optional[int], usage: Usage) -> None:
        hour_key = self._get_current_hour_key()
        bucket_key = self._get_bucket_key(lane, provider)

        if user_id is not None:
            uid = str(user_id)
            self.user_hourly.setdefault(uid, {})
            self.user_hourly[uid].setdefault(bucket_key, {})
            hour_map = self.user_hourly[uid][bucket_key]
        else:
            self.global_hourly.setdefault(bucket_key, {})
            hour_map = self.global_hourly[bucket_key]

        hour_usage = hour_map.get(hour_key)
        if hour_usage is None:
            hour_usage = Usage()
            hour_map[hour_key] = hour_usage

        hour_usage.add(usage)
        self._prune_hourly(hour_map)

    def _save_state(self):
        try:
            data = {
                "global_buckets": {k: asdict(v) for k, v in self.global_buckets.items()},
                "global_history": {k: [asdict(b) for b in v] for k, v in self.global_history.items()},
                "user_buckets": {uid: {k: asdict(v) for k, v in ubuckets.items()} for uid, ubuckets in self.user_buckets.items()},
                "user_history": {uid: {k: [asdict(b) for b in v] for k, v in uhists.items()} for uid, uhists in self.user_history.items()},
                "global_hourly": {k: {hour: asdict(u) for hour, u in hour_map.items()} for k, hour_map in self.global_hourly.items()},
                "user_hourly": {
                    uid: {k: {hour: asdict(u) for hour, u in hour_map.items()} for k, hour_map in uhists.items()}
                    for uid, uhists in self.user_hourly.items()
                }
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cost state: {e}")

    def _get_or_create_bucket(self, lane: Lane, provider: Provider, user_id: Optional[int] = None) -> Bucket:
        day_key, month_key = self._get_current_time_keys()
        bucket_key = self._get_bucket_key(lane, provider)
        
        # Determine target dictionary (Global or User)
        if user_id:
            user_str = str(user_id)
            if user_str not in self.user_buckets:
                self.user_buckets[user_str] = {}
            if user_str not in self.user_history:
                self.user_history[user_str] = {}
            
            target_map = self.user_buckets[user_str]
            history_map = self.user_history[user_str]
        else:
            target_map = self.global_buckets
            history_map = self.global_history

        if bucket_key not in history_map:
            history_map[bucket_key] = []

        bucket = target_map.get(bucket_key)
        
        if bucket is None:
            bucket = Bucket(day=day_key, month=month_key)
            target_map[bucket_key] = bucket
        else:
            # Check for Day Reset
            if bucket.day != day_key:
                # Archive old bucket if it has usage
                if bucket.used.tokens_in > 0 or bucket.used.tokens_out > 0 or bucket.used.usd > 0.0:
                    history_map[bucket_key].append(bucket)
                
                # Create new bucket
                # Check for carrying over Burn Lane/Monthly limits?
                # User Policy: "Main is Today's Usage". 
                # History tracks accumulation.
                # Burn Lane limits are total_usd. We need to check HISTORY for strict Burn Limits.
                # But for now, we just reset the day.
                
                bucket = Bucket(day=day_key, month=month_key)
                
                # Special Case: Burn Lane Persistence (if we want to NEVER reset it?)
                # Config says "total_usd": 300.0. This implies cumulative.
                # If we reset daily, we lose track of total.
                # So we must sum history + current to check limit.
                
                target_map[bucket_key] = bucket
            
                # Note: We don't check month reset specifically because day reset implies it.
                # History will contain "2024-12-31" and "2025-01-01".

        return bucket

    def can_call(self, lane: Lane, provider: Provider, user_id: Optional[int], est: Usage) -> AllowDecision:
        limits = COST_LIMITS.get(lane, {}).get(provider, {})
        if not limits:
             # No limits defined = Allowed (e.g. Local)
             return AllowDecision(allowed=True)

        if limits.get("hard_stop", False) is False:
            # Explicitly no hard stop (BYOK etc)
            return AllowDecision(allowed=True)

        bucket = self._get_or_create_bucket(lane, provider, user_id)
        
        if bucket.hard_stopped:
            return AllowDecision(allowed=False, reason="Hard Stop Active", fallback_to="local")

        # Check Daily Token Limit (Stable)
        daily_limit = limits.get("daily_tokens")
        if daily_limit:
            current_total = bucket.used.tokens_in + bucket.used.tokens_out + bucket.reserved.tokens_in + bucket.reserved.tokens_out
            est_total = est.tokens_in + est.tokens_out
            if current_total + est_total > daily_limit:
                 return AllowDecision(allowed=False, reason=f"Daily Token Limit Exceeded ({current_total}/{daily_limit})", fallback_to="local")

        # Check Burn Limit (USD)
        total_usd_limit = limits.get("total_usd")
        if total_usd_limit:
            current_usd = bucket.used.usd + bucket.reserved.usd
            if current_usd + est.usd > total_usd_limit:
                return AllowDecision(allowed=False, reason=f"Burn Budget Exceeded (${current_usd}/${total_usd_limit})", fallback_to="local")

        return AllowDecision(allowed=True)

    # --- State Helper for In-Flight ---
    _reservations: Dict[str, Usage] = {}

    def reserve(self, lane: Lane, provider: Provider, user_id: Optional[int], reservation_id: str, est: Usage) -> None:
        # Store reservation map
        self._reservations[reservation_id] = est
        
        # Add to Bucket Reserved
        bucket = self._get_or_create_bucket(lane, provider, user_id)
        bucket.reserved.add(est)
        bucket.last_update_iso = datetime.now(self.timezone).isoformat()
        self._save_state()

    def commit(self, lane: Lane, provider: Provider, user_id: Optional[int], reservation_id: str, actual: Usage) -> float:
        est = self._reservations.pop(reservation_id, None)
        bucket = self._get_or_create_bucket(lane, provider, user_id)
        
        bucket.used.add(actual)
        if est:
            bucket.reserved.sub(est)
        
        bucket.last_update_iso = datetime.now(self.timezone).isoformat()
        self._add_hourly_usage(lane, provider, user_id, actual)
        self._save_state()
        
        return bucket.used.usd

    def rollback(self, lane: Lane, provider: Provider, user_id: Optional[int], reservation_id: str, mode: Literal["release","keep"]="release") -> None:
        """
        Revert a reservation.
        mode="release": Cancel it (e.g. API error).
        mode="keep": Convert to used (e.g. partial success? or treated as consumed quota)
        Default for rollback on error is usually 'release' (don't charge).
        """
        est = self._reservations.get(reservation_id)
        if not est: 
            return

        bucket = self._get_or_create_bucket(lane, provider, user_id)
        
        if mode == "release":
            bucket.reserved.sub(est)
            del self._reservations[reservation_id]
        elif mode == "keep":
            # Treat as Used
            bucket.used.add(est)
            bucket.reserved.sub(est)
            del self._reservations[reservation_id]
            self._add_hourly_usage(lane, provider, user_id, est)
            
        bucket.last_update_iso = datetime.now(self.timezone).isoformat()
        self._save_state()

    def add_cost(self, lane: Lane, provider: Provider, user_id: Optional[int], usage: Usage) -> float:
        """
        Directly add cost (used for background tasks like memory optimization).
        """
        bucket = self._get_or_create_bucket(lane, provider, user_id)
        bucket.used.add(usage)
        bucket.last_update_iso = datetime.now(self.timezone).isoformat()
        self._add_hourly_usage(lane, provider, user_id, usage)

        # Also update Global Bucket if this was a user-specific add
        if user_id is not None:
            global_bucket = self._get_or_create_bucket(lane, provider, None)
            global_bucket.used.add(usage)
            global_bucket.last_update_iso = datetime.now(self.timezone).isoformat()
            self._add_hourly_usage(lane, provider, None, usage)
        
        self._save_state()
        logger.info(f"CostAdded: {lane}:{provider} user={user_id} used={usage}")
        return bucket.used.usd

    def get_usage_ratio(self, lane: Lane, provider: Provider) -> float:
        """Returns 0.0 to 1.0 (or >1.0) representing current daily usage vs limit."""
        limits = COST_LIMITS.get(lane, {}).get(provider, {})
        if not limits: return 0.0
        
        limit = limits.get("daily_tokens")
        if not limit: return 0.0
        
        bucket = self._get_or_create_bucket(lane, provider, None) # Global
        current = bucket.used.tokens_in + bucket.used.tokens_out + bucket.reserved.tokens_in + bucket.reserved.tokens_out
        
        return current / limit

