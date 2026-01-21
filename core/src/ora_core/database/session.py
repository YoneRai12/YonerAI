from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Use aiosqlite for async support
from pathlib import Path
# Use absolute path to avoid CWD issues (points to core/ora.db)
DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "ora.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True, connect_args={"check_same_thread": False})

from sqlalchemy import event
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
