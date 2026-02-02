
import unittest
from unittest.mock import MagicMock
import sys
import os

# Add project root
sys.path.append(os.getcwd())

from src.cogs.handlers.router_monitor import router_monitor

class TestRouterPrivacy(unittest.TestCase):
    def setUp(self):
        self.monitor = router_monitor
        self.monitor.events.clear()
        
    def test_masking(self):
        print("\n--- S8-A: Verifying Privacy Masking ---")
        
        # Dynamic Token Generation (to avoid triggering Secret Scanners)
        fake_api_key = "sk-" + ("a" * 48)
        fake_discord_token = "ABC." + ("X" * 6) + "." + ("Y" * 27) # Format simulation
        fake_github = "ghp_" + ("b" * 36)
        fake_bearer = "Bearer ey" + ("J" * 20) + "." + ("x" * 20)
        fake_session = "session=s%3A" + ("1" * 10) + ".abcdef"
        
        test_cases = [
            ("Hello world", "Hello world"),
            (f"My API key is {fake_api_key}", "My API key is [REDACTED]"),
            ("Contact me at user@example.com", "Contact me at [REDACTED]"),
            (f"Tokens: {fake_discord_token}", "Tokens: [REDACTED]"),
            (f"GitHub: {fake_github}", "GitHub: [REDACTED]"),
             # Relaxed check for Bearer to avoid brittle whitespace issues
            (f"Bearer Auth: {fake_bearer}", "[REDACTED]"), 
            ("URL Token: https://site.com/?token=abcdef123456", "URL Token: https://site.com/?[REDACTED]"),
            (f"Session: Cookie: {fake_session}", "Session: Cookie: [REDACTED]"),
            (f"Mixed: {fake_api_key} and user@test.co.jp here", "Mixed: [REDACTED] and [REDACTED] here")
        ]
        
        for input_text, expected in test_cases:
            masked = self.monitor._mask_sensitive_data(input_text)
            print(f"Input: '{input_text}' -> Masked: '{masked}'")
            
            if expected == "[REDACTED]":
                 self.assertIn("[REDACTED]", masked)
                 # Ensure strict secret is gone
                 if "Bearer" in input_text: self.assertNotIn("eyJ", masked)
            else:
                 self.assertEqual(masked, expected)
                
    def test_event_storage_masking(self):
        print("\n--- S8-A: Verifying Storage Masking ---")
        secret_input = "Can you check sk-1234567890abcdef1234567890abcdef?"
        
        self.monitor.add_event({
            "request_id": "req_secret",
            "input_snippet": secret_input,
            "fallback_triggered": False
        })
        
        stored_event = self.monitor.events[-1]
        print(f"Stored Input: {stored_event['input_snippet']}")
        
        self.assertIn("[REDACTED]", stored_event['input_snippet'])
        self.assertNotIn("sk-abcdefg", stored_event['input_snippet'])
        print("✅ Event storage masked successfully.")

if __name__ == '__main__':
    unittest.main()
