import asyncio
import logging
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.skills.loader import SkillLoader


# Mocking Discord and ORACog
class MockConfig:
    admin_user_id = 12345
    log_dir = "logs"

class MockORACog:
    async def _check_permission(self, user_id, level):
        print(f"    [MockORACog] Checking permission for {user_id} level {level}")
        return True # Grant all

class MockSystemCog:
    async def execute_tool(self, user_id, action, value):
        return {"status": True, "message": f"Executed {action} with {value}"}

class MockBot:
    def __init__(self):
        self.config = MockConfig()
        self.cogs = {
            "ORACog": MockORACog(),
            "SystemCog": MockSystemCog()
        }
    
    def get_cog(self, name):
        return self.cogs.get(name)

class MockGuild:
    def __init__(self, bot):
        self.me = MockMember(bot, 999, "Bot")
        self.members = []
        self.roles = []
    
    def get_member(self, uid):
        return None
    
    def get_role(self, uid):
        return None
    
    async def create_text_channel(self, name, overwrites=None):
        return MockChannel(name)
    
    async def create_voice_channel(self, name, overwrites=None):
        return MockChannel(name)

class MockMember:
    def __init__(self, bot, uid, name):
        self.id = uid
        self.name = name
        self.display_name = name
        self.bot = bot
        self.guild_permissions = MockPermissions()
        self.top_role = MockRole("TopRole", 100)
    
class MockPermissions:
    manage_roles = True

class MockRole:
    def __init__(self, name, position=1, id=111):
        self.name = name
        self.position = position
        self.id = id
        
    def __ge__(self, other):
        return self.position >= other.position

class MockChannel:
    def __init__(self, name):
        self.name = name
        self.mention = f"#{name}"
        
    async def purge(self, limit=10):
        return [1] * limit
        
    async def send(self, content):
        print(f"    [MockChannel] Sent: {content}")

class MockMessage:
    def __init__(self, bot):
        self.author = MockMember(bot, 12345, "AdminUser")
        self.guild = MockGuild(bot)
        self.channel = MockChannel("general")
        self.client = bot # Important for tool.py

async def verify_skills():
    logging.basicConfig(level=logging.INFO)
    # logger = logging.getLogger("Verifier")
    
    print("--- Verifying Migrated Skills ---")
    
    bot = MockBot()
    loader = SkillLoader()
    loader.load_skills()
    
    msg = MockMessage(bot)
    
    skills_to_test = [
        ("get_logs", {"lines": 5}),
        ("system_control", {"action": "status"}),
        ("create_channel", {"name": "test-channel", "channel_type": "text"}),
        ("cleanup_messages", {"count": 2}),
        ("say", {"message": "Hello Verification"}),
        ("get_role_list", {})
    ]
    
    for tool_name, args in skills_to_test:
        print(f"\nTesting {tool_name}...")
        if tool_name not in loader.skills:
            print(f"FAILED: {tool_name} not loaded.")
            continue
            
        try:
            # We mock LogService call in get_logs effectively by just letting it run or mocking LogService import?
            # LogService reads file so it might fail if file missing, or work. 
            # We'll see. LogService uses config.
            
            result = await loader.execute_tool(tool_name, args, msg)
            print(f"Result: {result[:100]}...") # Truncate
        except Exception as e:
            print(f"Error executing {tool_name}: {e}")

if __name__ == "__main__":
    asyncio.run(verify_skills())
