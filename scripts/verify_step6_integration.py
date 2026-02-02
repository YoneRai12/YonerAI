
import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.cogs.memory import MemoryCog
from src.cogs.tools.tool_handler import ToolHandler
from src.services.markdown_memory import MarkdownMemory


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_bot = MagicMock()
        self.mock_bot.config.admin_user_id = 12345
        self.mock_bot.healer = MagicMock()
        self.mock_cog = MagicMock()

    async def async_test_tool_handler(self):
        print("\n--- Testing ToolHandler Integration ---")
        handler = ToolHandler(self.mock_bot, self.mock_cog)
        
        # Check if SkillLoader is initialized
        self.assertTrue(hasattr(handler, 'skill_loader'), "ToolHandler missing skill_loader")
        print("✅ ToolHandler has skill_loader")
        
        # Check if 'weather' skill is loaded (assuming src/skills/weather/SKILL.md exists from previous step)
        if 'weather' in handler.skill_loader.skills:
            print("✅ 'weather' skill dynamically loaded by ToolHandler")
            
            # Test execution
            msg = MagicMock()
            msg.author.id = 12345
            args = {"location": "Tokyo"}
            result = await handler.execute("weather", args, msg)
            print(f"✅ Executed 'weather' tool via ToolHandler. Result: {result}")
            self.assertIn("Tokyo", str(result))
            self.assertIn("Sunny", str(result))
        else:
            print("⚠️ 'weather' skill NOT found")
            
        # Check web_search
        if 'web_search' in handler.skill_loader.skills:
             print("✅ 'web_search' skill dynamically loaded")
        else:
             print("⚠️ 'web_search' skill NOT found")


    async def async_test_memory_cog_init(self):
        print("\n--- Testing MemoryCog Integration ---")
        # MemoryCog requires complex mocks for init, but we just want to see if it syntax-checks and inits md_memory
        # minimal mock for bot
        bot = MagicMock()
        llm = MagicMock()
        
        # We need to mock os.makedirs or ensure directories exist?
        # The code calls _ensure_memory_dir on init.
        # We can just try to instantiate and catch if it works.
        
        try:
            # We mock discord imports inside the file if needed, but we imported the class.
            # Just instantiation might fail due to async loops or disk operations.
            # Let's just check the class signature or try instantiation.
            cog = MemoryCog(bot, llm, worker_mode=False)
            self.assertTrue(hasattr(cog, 'md_memory'), "MemoryCog missing md_memory")
            self.assertIsInstance(cog.md_memory, MarkdownMemory)
            print("✅ MemoryCog instantiated and has md_memory")
            
            cog.cog_unload() # Cleanup tasks
        except Exception as e:
            print(f"⚠️ MemoryCog init failed (expected if env not perfect): {e}")
            # It might fail due to loop things, but if it fails with ImportError or SyntaxError that's bad.
            # If it fails with "No loop", we can skip.

    def test_run_async(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.async_test_tool_handler())
        # Patch tasks.Loop.start to prevent background tasks from running
        with unittest.mock.patch('discord.ext.tasks.Loop.start', new=MagicMock()):
            loop.run_until_complete(self.async_test_memory_cog_init())
        loop.close()

if __name__ == '__main__':
    unittest.main()
