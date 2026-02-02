
import unittest
from unittest.mock import MagicMock, AsyncMock
import sys
import os
import asyncio
import time

# Add project root
sys.path.append(os.getcwd())

from src.cogs.handlers.router_monitor import router_monitor, RouterHealthMonitor

class TestRouterAlerting(unittest.TestCase):
    def setUp(self):
        # Reset singleton state
        self.monitor = router_monitor
        self.monitor.events.clear()
        self.monitor.last_alert_time = 0
        
        # Mock Bot
        self.bot = MagicMock()
        self.bot.config.admin_user_id = 12345
        self.bot.fetch_user = AsyncMock()
        self.user_mock = MagicMock()
        self.user_mock.send = AsyncMock()
        self.bot.fetch_user.return_value = self.user_mock
        self.bot.loop = MagicMock()
        # Suppress "coroutine not awaited" warning from add_event triggers
        self.bot.loop.create_task.side_effect = lambda coro: coro.close()
        
        self.monitor.set_bot(self.bot)

    def test_alert_dispatch(self):
        print("\n--- S8-B: Verifying Alert Dispatch ---")
        
        # 1. Trigger Critical State
        # Add failing events
        fake_api_key = "sk-" + ("a" * 48)
        for i in range(15):
            self.monitor.add_event({
                "request_id": f"fail_{i}",
                "fallback_triggered": True,
                "input_snippet": f"secret {fake_api_key}" # Should be masked
            })
            
        print("Events added. Checking metrics...")
        metrics = self.monitor.get_metrics()
        self.assertEqual(metrics["status"], "CRITICAL")
        
        # 2. Force Alert Dispatch (Simulate async call)
        asyncio.run(self.monitor._check_and_alert())
        
        # 3. Verify Bot Interaction
        self.bot.fetch_user.assert_called_once_with(12345)
        self.user_mock.send.assert_called_once()
        call_args = self.user_mock.send.call_args[0][0]
        print(f"Alert Sent:\n{call_args}")
        
        self.assertIn("🚨 **ORA Router CRITICAL ALERT** 🚨", call_args)
        self.assertIn("Fallback Rate: 100.0%", call_args)
        
        # 4. Verify Context Dump (Mocked Logger)
        last_event = self.monitor.events[-1]
        self.assertIn("[REDACTED]", last_event["input_snippet"])
        print("✅ Alert sent and input masked.")

    def test_alert_fallback(self):
        print("\n--- S8-B: Verifying Alert Fallback ---")
        
        # Setup: DM Failure
        self.user_mock.send.side_effect = Exception("DM Closed")
        
        # Setup: Fallback Channel
        fallback_channel = MagicMock()
        fallback_channel.name = "bot-logs"
        fallback_channel.send = AsyncMock() # Must be awaitable
        self.bot.get_channel.return_value = fallback_channel
        self.bot.config.bot_log_channel_id = 9999
        
        # Trigger Critical
        for i in range(15):
             self.monitor.add_event({"fallback_triggered": True})
             
        asyncio.run(self.monitor._check_and_alert())
        
        # Verify Fallback
        self.user_mock.send.assert_called_once() # Tried DM
        fallback_channel.send.assert_called_once() # Fallback to Channel
        print("✅ Alert fell back to channel after DM failure.")

    def test_alert_cooldown(self):
        print("\n--- S8-B: Verifying Alert Cooldown ---")
        self.monitor.last_alert_time = time.time() # Just alerted
        
        # Trigger another critical state
        for i in range(15):
             self.monitor.add_event({"fallback_triggered": True})
             
        asyncio.run(self.monitor._check_and_alert())
        
        # Should NOT fetch user (blocked by cooldown)
        self.bot.fetch_user.assert_not_called()
        print("✅ Alert suppressed by cooldown.")

if __name__ == '__main__':
    unittest.main()
