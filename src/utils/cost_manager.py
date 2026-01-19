import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional

import aiohttp
import pytz

from src.config import COST_LIMITS, COST_TZ, SAFETY_BUFFER_RATIO, STATE_DIR

logger = logging.getLogger(__name__)

Lane = Literal["high", "stable", "burn", "byok", "optimization"]
Provider = Literal["local", "openai", "gemini_dev", "gemini_trial", "claude", "grok"]


@dataclass
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0

    def add(self, other: "Usage"):
        self.tokens_in += other.tokens_in
        self.tokens_out += other.tokens_out
        self.usd += other.usd

    def sub(self, other: "Usage"):
        self.tokens_in = max(0, self.tokens_in - other.tokens_in)
        self.tokens_out = max(0, self.tokens_out - other.tokens_out)
        self.usd = max(0.0, self.usd - other.usd)


@dataclass
class Bucket:
    day: str  # YYYY-MM-DD (JST)
    month: str  # YYYY-MM (JST)
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
        self.global_buckets: Dict[str, Bucket] = {}  # key = f"{lane}:{provider}"
        self.user_buckets: Dict[str, Dict[str, Bucket]] = {}  # user_id -> (key -> Bucket)

        # New: History Storage
        # Structure: key -> List[Bucket]
        self.global_history: Dict[str, list[Bucket]] = {}
        self.user_history: Dict[str, Dict[str, list[Bucket]]] = {}
        self.global_hourly: Dict[str, Dict[str, Usage]] = {}
        self.user_hourly: Dict[str, Dict[str, Dict[str, Usage]]] = {}

        # [Override] Unlimited Users (Set of User IDs)
        self.unlimited_users = set()

        self.unlimited_mode = False  # Deprecated but kept for safe migration (will be removed logic-wise)

        self._load_state()

    def toggle_unlimited_mode(self, enabled: bool, user_id: str = None):
        """
        Toggle unlimited mode for a specific user.
        If user_id is None, it acts as a Global Toggle (Legacy/Emergency).
        """
        if user_id:
            uid = str(user_id)
            if enabled:
                self.unlimited_users.add(uid)
                logger.warning(f"⚠️ SYSTEM OVERRIDE: Unlimited Mode ENABLED for User {uid}")
            else:
                self.unlimited_users.discard(uid)
                logger.info(f"ℹ️ SYSTEM OVERRIDE: Unlimited Mode DISABLED for User {uid}")
        else:
            # Fallback to global (or just ignore/clear all?)
            # Let's keep global flag for emergency 'STOP ALL' or 'OPEN ALL' if ever needed,
            # but for this specific request "Only me", we prioritize user list.
            self.unlimited_mode = enabled
            logger.warning(f"⚠️ SYSTEM OVERRIDE: Global Unlimited Mode set to {enabled}")

        self._save_state()

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
            with open(self.state_file, "r", encoding="utf-8") as f:
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
                self.user_history[user_id] = {
                    k: [self._dict_to_bucket(b) for b in v_list] for k, v_list in user_hist_data.items()
                }

            # Restore Hourly Usage (Optional)
            for k, hour_map in data.get("global_hourly", {}).items():
                self.global_hourly[k] = {hour: self._dict_to_usage(u) for hour, u in hour_map.items()}
            for user_id, user_hour_map in data.get("user_hourly", {}).items():
                self.user_hourly[user_id] = {
                    k: {hour: self._dict_to_usage(u) for hour, u in hour_map.items()}
                    for k, hour_map in user_hour_map.items()
                }

            # Restore Unlimited Users
            self.unlimited_users = set(data.get("unlimited_users", []))
            self.unlimited_mode = data.get("unlimited_mode", False)

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
            last_update_iso=data.get("last_update_iso", ""),
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
                "user_buckets": {
                    uid: {k: asdict(v) for k, v in ubuckets.items()} for uid, ubuckets in self.user_buckets.items()
                },
                "user_history": {
                    uid: {k: [asdict(b) for b in v] for k, v in uhists.items()}
                    for uid, uhists in self.user_history.items()
                },
                "global_hourly": {
                    k: {hour: asdict(u) for hour, u in hour_map.items()} for k, hour_map in self.global_hourly.items()
                },
                "user_hourly": {
                    uid: {k: {hour: asdict(u) for hour, u in hour_map.items()} for k, hour_map in uhists.items()}
                    for uid, uhists in self.user_hourly.items()
                },
                "unlimited_mode": self.unlimited_mode,
                "unlimited_users": list(self.unlimited_users),
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
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
        # [Override] Check Unlimited Mode (Global OR User-Specific)
        if self.unlimited_mode:
            return AllowDecision(allowed=True, reason="System Override Active (Global Unlimited)")

        if user_id and str(user_id) in self.unlimited_users:
            return AllowDecision(allowed=True, reason="System Override Active (User Unlimited)")

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
            # Apply Safety Buffer
            safe_limit = daily_limit * SAFETY_BUFFER_RATIO

            current_total = (
                bucket.used.tokens_in + bucket.used.tokens_out + bucket.reserved.tokens_in + bucket.reserved.tokens_out
            )
            est_total = est.tokens_in + est.tokens_out
            if current_total + est_total > safe_limit:
                return AllowDecision(
                    allowed=False,
                    reason=f"Daily Token Limit Exceeded (Buffer {int(SAFETY_BUFFER_RATIO * 100)}%): {current_total}/{daily_limit})",
                    fallback_to="local",
                )

            # Check Global Limit (if user_id is provided, we must ALSO check global)
            if user_id is not None:
                global_bucket = self._get_or_create_bucket(lane, provider, None)
                global_current = (
                    global_bucket.used.tokens_in
                    + global_bucket.used.tokens_out
                    + global_bucket.reserved.tokens_in
                    + global_bucket.reserved.tokens_out
                )
                # Check Global vs Same Limit (assuming 2.5M is server total)
                if global_current + est_total > safe_limit:
                    return AllowDecision(
                        allowed=False,
                        reason=f"Global Daily Limit Exceeded (Buffer {int(SAFETY_BUFFER_RATIO * 100)}%): {global_current}/{daily_limit}",
                        fallback_to="local",
                    )

        # Check Burn Limit (USD)
        total_usd_limit = limits.get("total_usd")
        if total_usd_limit:
            current_usd = bucket.used.usd + bucket.reserved.usd
            if current_usd + est.usd > total_usd_limit:
                return AllowDecision(
                    allowed=False,
                    reason=f"Burn Budget Exceeded (${current_usd}/${total_usd_limit})",
                    fallback_to="local",
                )

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

    def commit(
        self, lane: Lane, provider: Provider, user_id: Optional[int], reservation_id: str, actual: Usage
    ) -> float:
        est = self._reservations.pop(reservation_id, None)
        bucket = self._get_or_create_bucket(lane, provider, user_id)

        bucket.used.add(actual)
        if est:
            bucket.reserved.sub(est)

        bucket.last_update_iso = datetime.now(self.timezone).isoformat()
        self._add_hourly_usage(lane, provider, user_id, actual)
        self._save_state()

        return bucket.used.usd

    def rollback(
        self,
        lane: Lane,
        provider: Provider,
        user_id: Optional[int],
        reservation_id: str,
        mode: Literal["release", "keep"] = "release",
    ) -> None:
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

    async def sync_openai_usage(
        self, session: aiohttp.ClientSession, api_key: str, update_local: bool = False
    ) -> Dict[str, Any]:
        """
        Fetches official usage from OpenAI API (v1/usage) for the current month.
        Returns a summary dict: {'total_tokens': int, 'breakdown': dict}.
        If update_local is True, it updates the 'stable/openai' Global Bucket to match reality.
        """
        if not api_key:
            return {"error": "No API Key"}

        try:
            today = datetime.now(self.timezone).date()
            # Start from 1st of month
            start_date = today.replace(day=1)

            total_tokens = 0

            # OpenAI /v1/usage is by date (UTC).
            current = start_date
            while current <= today:
                date_str = current.strftime("%Y-%m-%d")
                url = f"https://api.openai.com/v1/usage?date={date_str}"

                async with session.get(url, headers={"Authorization": f"Bearer {api_key}"}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        day_tokens = 0
                        for entry in data.get("data", []):
                            day_tokens += entry.get("n_generated_tokens_total", 0) + entry.get(
                                "n_context_tokens_total", 0
                            )

                        total_tokens += day_tokens
                    else:
                        logger.warning(f"OpenAI Usage Sync Failed for {date_str}: {resp.status}")

                current += timedelta(days=1)

            result = {"total_tokens": total_tokens, "synced": True, "updated": False}

            if update_local:
                # Update Global Bucket for Stable Lane (Main Shared Lane)
                # We assume most usage is Stable/OpenAI.
                # If we have breakdown by model, we could split, but v1/usage aggregates.
                # Conservative approach: Assign ALL usage to 'stable/openai' Global Bucket.

                bucket = self._get_or_create_bucket("stable", "openai", None)  # Global

                # Check current local
                local_used = bucket.used.tokens_in + bucket.used.tokens_out

                if total_tokens > local_used:
                    # Drift detected: Official > Local
                    diff = total_tokens - local_used
                    # Add difference to 'tokens_out' (Costliest assumption, or split)
                    # Just add to tokens_out to ensure limit checking works.
                    bucket.used.tokens_out += diff
                    bucket.last_update_iso = datetime.now(self.timezone).isoformat()
                    self._save_state()
                    result["updated"] = True
                    result["drift_added"] = diff
                    logger.info(f"🔄 [Sync] Updated Local State. Added {diff} tokens to match Official {total_tokens}.")
                elif total_tokens < local_used:
                    # Local > Official (Maybe delayed API?)
                    # Trust Local for safety, do not reduce.
                    pass

            return result

        except Exception as e:
            logger.error(f"Sync Logic Error: {e}")
            return {"error": str(e)}

    def _check_and_reset_bucket(self, bucket: Bucket, lane: Lane, provider: Provider):
        """
        Checks if the bucket's time period has passed and resets if necessary.
        Resets daily buckets if day changes.
        """
        current_day, _ = self._get_current_time_keys()

        if bucket.day != current_day:
            # Shift to History/Daily Log before resetting?
            # For simplicity, just reset Used stats (or archive them if we had archival logic here).
            # We already have hourly logs, so daily reset is fine.
            bucket.day = current_day
            bucket.used = Usage()  # Reset
            bucket.reserved = Usage()  # Reset
            bucket.last_update_iso = datetime.now(self.timezone).isoformat()
            self._save_state()

    def get_remaining_budget(self, lane: Lane, provider: Provider) -> int:
        """
        Returns the number of tokens remaining before the Daily Limit (Safe).
        Returns -1 if no limit is set.
        """
        bucket = self._get_or_create_bucket(lane, provider, None)

        # Check reset logic first (Implicit)
        self._check_and_reset_bucket(bucket, lane, provider)

        # Get Limit
        limits = COST_LIMITS.get(lane, {}).get(provider, {})
        daily_limit = limits.get("daily_tokens")

        if not daily_limit:
            return -1

        # Calculate used
        current_total = (
            bucket.used.tokens_in + bucket.used.tokens_out + bucket.reserved.tokens_in + bucket.reserved.tokens_out
        )

        # Apply Safety Buffer (so we don't return tokens that would hit the buffer)
        safe_limit = int(daily_limit * SAFETY_BUFFER_RATIO)

        remaining = safe_limit - current_total
        return max(0, remaining)

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
        if not limits:
            return 0.0

        limit = limits.get("daily_tokens")
        if not limit:
            return 0.0

        bucket = self._get_or_create_bucket(lane, provider, None)  # Global
        current = (
            bucket.used.tokens_in + bucket.used.tokens_out + bucket.reserved.tokens_in + bucket.reserved.tokens_out
        )

        return current / limit

    def get_current_usage(self, lane: Lane, provider: Provider, user_id: Optional[int] = None) -> int:
        """Returns the total tokens (In+Out) used today for the specified bucket."""
        bucket = self._get_or_create_bucket(lane, provider, user_id)
        self._check_and_reset_bucket(bucket, lane, provider)
        return bucket.used.tokens_in + bucket.used.tokens_out + bucket.reserved.tokens_in + bucket.reserved.tokens_out
