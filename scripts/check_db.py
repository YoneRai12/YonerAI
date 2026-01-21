import asyncio
import sys
from pathlib import Path

# Add core to path
root = Path(__file__).parent.parent
sys.path.append(str(root / "core" / "src"))

async def check_run_status():
    from ora_core.database.session import AsyncSessionLocal
    from ora_core.database.repo import Repository
    
    # Use the run_id from previous attempt
    run_id = "0e7b0e95-a486-406c-81df-597abcdba49d"
    
    async with AsyncSessionLocal() as session:
        repo = Repository(session)
        run = await repo.get_run(run_id)
        if run:
            print(f"Run ID: {run.id}")
            print(f"Status: {run.status}")
            print(f"User Identity: {run.user_id}")
        else:
            print(f"Run {run_id} not found in DB.")

if __name__ == "__main__":
    asyncio.run(check_run_status())
