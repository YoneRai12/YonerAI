import asyncio
import sys
import uuid
import os
import json
from pathlib import Path
from sqlalchemy import text

# Add core to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "core" / "src"))

from ora_core.database.session import engine, AsyncSessionLocal
from ora_core.database.models import Base
from ora_core.database.repo import Repository

async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def test_identity_linking():
    async with AsyncSessionLocal() as session:
        repo = Repository(session)
        
        # 1. Create two separate users
        discord_user = await repo.get_or_create_user("discord", "d123", "DiscordUser")
        web_user = await repo.get_or_create_user("web", "w456", "WebUser")
        
        discord_uid = str(discord_user.id)
        web_uid = str(web_user.id)
        
        print(f"Discord User ID: {discord_uid}")
        print(f"Web User ID: {web_uid}")
        assert discord_uid != web_uid
        
        # 2. Add some data to Web User
        conv = await repo.get_or_create_conversation(None, web_uid)
        await repo.create_user_message_and_run(conv.id, web_uid, "Web message", [], "idem-web")
        await session.commit()
        
        # 3. Create link code from Discord side
        code = "LINK88"
        await repo.create_link_request(discord_uid, code)
        await session.commit()
        
        # 4. Perform Linking (Web user enters code)
        link_req = await repo.get_link_request(code)
        assert link_req.user_id == discord_uid
        
        await repo.link_identities(web_uid, discord_uid)
        
        # 5. Verify results
        # Web identity should now point to discord_user.id
        linked_web_user = await repo.get_or_create_user("web", "w456")
        assert str(linked_web_user.id) == discord_uid
        print("Identity Merged: PASS")
        
        # Data check: Conversation should now belong to discord_user
        res = await session.execute(text("SELECT user_id FROM conversations WHERE id = :cid"), {"cid": conv.id})
        assert res.scalar() == discord_uid
        print("Data Migrated: PASS")

if __name__ == "__main__":
    asyncio.run(setup_db())
    asyncio.run(test_identity_linking())
    print("\n--- IDENTITY LINKING VERIFIED ---")
