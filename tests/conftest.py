from __future__ import annotations

import os
import sys
from pathlib import Path


# Allow `import src...` in tests without requiring PYTHONPATH hacks.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Avoid flaky "database is locked" failures by forcing tests to use a dedicated sqlite file.
_TEST_DB = ROOT / "data" / "pytest_ora_bot.db"
try:
    _TEST_DB.parent.mkdir(parents=True, exist_ok=True)
    if _TEST_DB.exists():
        _TEST_DB.unlink()
except Exception:
    pass
os.environ.setdefault("ORA_BOT_DB", str(_TEST_DB))
