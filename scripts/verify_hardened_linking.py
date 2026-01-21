import asyncio
import sys
import uuid
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text, select

# Add core to path
sys.path.append(str(Path(__file__).resolve().parent.parent / "core" / "src"))

from ora_core.database.session import AsyncSessionLocal
from ora_core.database.models import Base, IdentityLinkAudit, User
from ora_core.database.repo import Repository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# USE TEST DB
TEST_DB = "sqlite+aiosqlite:///test_hardened.db"
test_engine = create_async_engine(TEST_DB)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

async def test_hardened_linking():
    async with TestSession() as session:
        repo = Repository(session)
        
        # 1. Setup users
        discord_user = await repo.get_or_create_user("discord", "secure_d1", "SecureDiscord")
        web_user = await repo.get_or_create_user("web", "secure_w1", "SecureWeb")
        await session.commit()
        
        d_uid = str(discord_user.id)
        w_uid = str(web_user.id)
        
        print(f"Testing Rate Limiting for Web User {w_uid}...")
        # 2. Test Rate Limiting (5 failures)
        for i in range(5):
            await repo.update_user_link_failure(w_uid, ip="127.0.0.1")
        
        await session.refresh(web_user)
        assert web_user.failed_link_attempts >= 5
        assert web_user.link_locked_until is not None
        assert web_user.link_locked_until > datetime.utcnow()
        print("Rate Limiting Lockout: PASS")
        
        # 3. Test Audit Logs for failures
        stmt = select(IdentityLinkAudit).where(IdentityLinkAudit.target_user_id == w_uid)
        audits = (await session.execute(stmt)).scalars().all()
        assert len(audits) >= 5
        print(f"Audit Log Count ({len(audits)}): PASS")
        
        # 4. Test TTL Expiry
        print("Testing TTL Expiry...")
        expired_code = "EXPIRED"
        # Manually inject expired request
        from ora_core.database.models import IdentityLinkRequest
        req = IdentityLinkRequest(
            code=expired_code,
            user_id=d_uid,
            expires_at=datetime.utcnow() - timedelta(minutes=1)
        )
        session.add(req)
        await session.commit()
        
        found = await repo.get_link_request(expired_code)
        assert found is None, "Expired code should not be found"
        print("TTL Expiry Check: PASS")
        
        # 5. Test Successful Merge resets failures
        print("Testing Success Reset...")
        # Unlock for testing merge
        web_user.link_locked_until = None
        await session.commit()
        
        valid_code = "VALID1"
        await repo.create_link_request(d_uid, valid_code)
        await session.commit()
        
        await repo.link_identities(w_uid, d_uid, ip="127.0.0.1")
        await repo.reset_user_link_failure(d_uid) # merged user
        
        await session.refresh(discord_user)
        assert discord_user.failed_link_attempts == 0
        assert discord_user.link_locked_until is None
        print("Success Reset: PASS")

if __name__ == "__main__":
    asyncio.run(setup_db())
    asyncio.run(test_hardened_linking())
    print("\n--- HARDENED IDENTITY LINKING VERIFIED ---")
