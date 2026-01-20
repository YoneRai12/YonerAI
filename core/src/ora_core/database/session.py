from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Use aiosqlite for async support
from pathlib import Path
# Use absolute path to avoid CWD issues (points to core/ora.db)
DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "ora.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True, connect_args={"check_same_thread": False})
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
