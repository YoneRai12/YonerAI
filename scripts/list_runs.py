import asyncio
import sys
from pathlib import Path
from sqlalchemy import select

# Add core to path
root = Path(__file__).parent.parent
sys.path.append(str(root / "core" / "src"))

async def list_recent_runs():
    from ora_core.database.session import AsyncSessionLocal
    from ora_core.database.models import Run
    
    async with AsyncSessionLocal() as session:
        stmt = select(Run).order_by(Run.id.desc()).limit(5)
        result = await session.execute(stmt)
        runs = result.scalars().all()
        
        if runs:
            print(f"{'Run ID':\u003c40} | {'Status':\u003c15}")
            print("-" * 55)
            for run in runs:
                print(f"{run.id:\u003c40} | {run.status:\u003c15}")
        else:
            print("No runs found in DB.")

if __name__ == "__main__":
    asyncio.run(list_recent_runs())
