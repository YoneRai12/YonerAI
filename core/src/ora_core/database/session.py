import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 1: database, 2: ora_core, 3: src, 4: core, 5: root
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent.parent / ".env")

# Try to get DB name from env, fallback to ora.db
# Note: ORA_BOT_DB in .env might be just "ora_bot.db"
DB_NAME = os.getenv("ORA_BOT_DB", "ora.db")
# Place DB in the root folder alongside the bot and .env
DB_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / DB_NAME
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

print(f"[DB] Connecting to {DB_PATH}")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30}
)

from sqlalchemy import event


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=30000") # 30 seconds
    cursor.close()

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
