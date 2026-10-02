
import sys
from pathlib import Path

import uvicorn

# Force project root into sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")


if __name__ == "__main__":
    print("Starting ORA Web API (Dashboard Backend)...")
    # Import directly to verify it works
    from src.web.app import app
    
    # Run on Port 8003 (as configured in .env now)
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
