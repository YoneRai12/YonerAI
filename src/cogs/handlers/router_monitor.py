
import logging
import time
import asyncio
from typing import List, Dict, Any, Optional
from collections import deque
import statistics

logger = logging.getLogger(__name__)

class RouterHealthMonitor:
    """
    S7: Proactive Anomaly Detection for Tool Router.
    Maintains a rolling window of metrics to detect degradation.
    Singleton pattern to ensure shared state.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RouterHealthMonitor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.window_size = 100
        self.events: deque = deque(maxlen=self.window_size)
        self.bot = None
        self.last_alert_time = 0
        self.alert_cooldown = 900 # 15 minutes
        self._initialized = True
        logger.info("🛡️ RouterHealthMonitor Initialized (S7/S8)")

    def set_bot(self, bot):
        """S8-B: Inject bot instance for alert dispatch."""
        self.bot = bot
        
    def add_event(self, payload: Dict[str, Any]):
        """Ingests a router log event."""
        # Add timestamp if missing
        if "timestamp" not in payload:
            payload["timestamp"] = time.time()
            
        # S8-A: Mask sensitive data BEFORE storage
        if "input_snippet" in payload:
            payload["input_snippet"] = self._mask_sensitive_data(payload["input_snippet"])
            
        self.events.append(payload)
        
        # Real-time Critical Check (S8-B)
        # If this specific event triggered a critical state (e.g. fallback), check if we need to alert.
        if payload.get("fallback_triggered"):
            # Re-calculate metrics to see if we breached the threshold or if this is just one-off
            # Optimization: Just check if rate > 10% inside _check_and_alert
            if self.bot:
                 # Schedule alert check safely
                 self.bot.loop.create_task(self._check_and_alert())

    def _mask_sensitive_data(self, text: str) -> str:
        """S8-A: Masks generic API keys, tokens, emails, and sessions."""
        if not text: return text
        import re
        
        # Patterns (S8 Refinement: Expanded Coverage)
        patterns = [
            r"(sk-[a-zA-Z0-9]{20,})", # OpenAI/Stripe keys
            r"(ghp_[a-zA-Z0-9]{20,})", # GitHub tokens
            r"([a-zA-Z0-9]{24}\.[a-zA-Z0-9]{6}\.[a-zA-Z0-9_-]{27})", # Discord Tokens
            r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", # Email
            r"(Bearer\s+[a-zA-Z0-9\-\._~\+\/]+=*)", # Bearer Token
            r"(token=[a-zA-Z0-9\-\._~\+\/]+)", # URL Token
            r"(session=[a-zA-Z0-9\-\._~\+\/%]+)" # Cookie Session (incl %)
        ]
        
        masked = text
        for pat in patterns:
            masked = re.sub(pat, "[REDACTED]", masked, flags=re.IGNORECASE)
            
        return masked

    async def _check_and_alert(self):
        """S8-B: Checks metrics and dispatches alert if needed."""
        metrics = self.get_metrics()
        status = metrics["status"]
        if status == "CRITICAL":
             current_time = time.time()
             if current_time - self.last_alert_time > self.alert_cooldown:
                 await self._dispatch_alert(metrics)
                 self.last_alert_time = current_time

    async def _dispatch_alert(self, metrics: Dict[str, Any]):
        """S8-B: Dispatches alert to Admin (with Fallback)."""
        if not self.bot: return
        
        alerts_str = "\n".join(metrics["alerts"])
        message = (
            f"🚨 **ORA Router CRITICAL ALERT** 🚨\n"
            f"```\n{alerts_str}\n```\n"
            f"**Metrics:**\n"
            f"- Fallback Rate: {metrics['metrics']['fallback_rate_percent']}%\n"
            f"- Unstable Bundles: {metrics['metrics']['unstable_bundles_count']}\n"
            f"Use `/ora health router` for details."
        )
        
        # S8-A: Always log Context Dump first (it's safe & masked)
        self._dump_critical_context(metrics["alerts"])
        
        # Attempt 1: Admin DM
        try:
            admin_id = self.bot.config.admin_user_id
            if admin_id:
                user = await self.bot.fetch_user(admin_id)
                if user:
                    await user.send(message)
                    logger.warning(f"🚨 S8-B: Dispatched Critical Alert to Admin DM ({admin_id})")
                    return
        except Exception as e:
            logger.warning(f"S8-B: Admin DM failed: {e}. Trying fallback...")

        # Attempt 2: Fallback Channel (Log Channel or System Channel)
        try:
            # Try specific log channel from config (if it exists)
            log_channel_id = getattr(self.bot.config, "bot_log_channel_id", None)
            target_channel = None
            
            if log_channel_id:
                target_channel = self.bot.get_channel(log_channel_id)
            
            # If no log channel, try First Guild's System Channel
            if not target_channel and self.bot.guilds:
                target_channel = self.bot.guilds[0].system_channel
                
            if target_channel:
                await target_channel.send(message)
                logger.warning(f"🚨 S8-B: Dispatched Critical Alert to Fallback Channel ({target_channel.name})")
            else:
                 logger.error("🚨 S8-B: ALL ALERT ROUTES FAILED. Critical Alert could not be delivered.")
                 
        except Exception as e:
             logger.error(f"S8-B: Alert Fallback failed: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates aggregated metrics from the current window."""
        if not self.events:
             return {
                 "status": "No Data",
                 "count": 0
             }
             
        total = len(self.events)
        
        # 1. Fallback Rate
        fallbacks = sum(1 for e in self.events if e.get("fallback_triggered"))
        fallback_rate = (fallbacks / total) * 100
        
        # 2. Retry Rate (Log entries where retry_count > 0)
        retries = sum(1 for e in self.events if e.get("retry_count", 0) > 0)
        retry_rate = (retries / total) * 100
        
        # 3. Latency P95 (LLM Roundtrip)
        latencies = [e.get("router_roundtrip_ms", 0) for e in self.events]
        if latencies:
            latencies.sort()
            p95_index = int(total * 0.95)
            # Clip index if out of bounds (though unlikely with int())
            p95_index = min(p95_index, total - 1)
            latency_p95 = latencies[p95_index]
            latency_avg = statistics.mean(latencies)
        else:
            latency_p95 = 0
            latency_avg = 0
            
        # 4. Cache Stability (S7 Refinement: Bundle-Prefix Invariant)
        # Check mapping: tools_bundle_id -> set(prefix_hash)
        bundle_map = {}
        for e in self.events:
            bid = e.get("tools_bundle_id")
            ph = e.get("prefix_hash")
            if bid and ph:
                if bid not in bundle_map:
                    bundle_map[bid] = set()
                bundle_map[bid].add(ph)
        
        # Stability Check: Any bundle ID mapping to >1 prefix hash?
        unstable_bundles = {bid: hashes for bid, hashes in bundle_map.items() if len(hashes) > 1}
        
        # 5. Bundle Integrity
        unique_bundles = len(bundle_map.keys())
        
        # Alerting Logic (Simple Thresholds)
        alerts = []
        is_critical = False
        
        if fallback_rate > 10:
            alerts.append(f"CRITICAL: High Fallback Rate ({fallback_rate:.1f}%)")
            is_critical = True
        if retry_rate > 15:
            alerts.append(f"WARNING: High Retry Rate ({retry_rate:.1f}%)")
        if unstable_bundles:
            alerts.append(f"WARNING: Bundle Stability Violation (Bundles with unstable prefixes: {len(unstable_bundles)})")
        if latency_p95 > 3000: # 3s
            alerts.append(f"WARNING: High Latency P95 ({latency_p95:.0f}ms)")

        status = "HEALTHY"
        if alerts:
            status = "CRITICAL" if is_critical else "DEGRADED"

        # NOTE: S8-A Context Dump is now handled in _dispatch_alert or called explicitly if needed.
        # But we remove the auto-dump from get_metrics to avoid side effects during simple status checks.
        
        return {
            "status": status,
            "window_size": total,
            "metrics": {
                "fallback_rate_percent": round(fallback_rate, 1),
                "retry_rate_percent": round(retry_rate, 1),
                "latency_p95_ms": round(latency_p95, 1),
                "latency_avg_ms": round(latency_avg, 1),
                "unstable_bundles_count": len(unstable_bundles),
                "unique_bundles": unique_bundles
            },
            "alerts": alerts,
            "last_event_time": self.events[-1]["timestamp"] if self.events else 0
        }

    def _dump_critical_context(self, alerts: List[str]):
        """S8-A: Dumps recent context to log for debugging critical failures."""
        logger.error(f"🚨 CRITICAL ALERT TRIGGERED: {alerts}")
        logger.error("Dumping last 5 router events for debugging:")
        
        recent_events = list(self.events)[-5:]
        for i, event in enumerate(reversed(recent_events)):
            logger.error(f"Event -{i}: ID={event.get('request_id')}, "
                         f"Input='{event.get('input_snippet')}', " # Already masked in add_event
                         f"Fallback={event.get('fallback_triggered')}, "
                         f"Categories={event.get('selected_categories')}")

# Global Instance
router_monitor = RouterHealthMonitor()
