
from __future__ import annotations

import json
import os
from pathlib import Path


STATE_PATH_ENV = "YONERAI_DEBUG_STATE_PATH"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_PATH = REPO_ROOT / "data" / "cost_state.json"


def main() -> int:
    state_path = Path(os.environ.get(STATE_PATH_ENV, DEFAULT_STATE_PATH)).expanduser()

    try:
        with state_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        uh = data.get("user_history", {})
        print(f"Total Users in History: {len(uh)}")

        if uh:
            uid = list(uh.keys())[0]
            print(f"Sample User ID: {uid}")

            user_data = uh[uid]
            print(f"Lanes for User: {list(user_data.keys())}")

            if user_data:
                lane = list(user_data.keys())[0]
                buckets = user_data[lane]
                print(f"Bucket Count for {lane}: {len(buckets)}")
                if buckets:
                    print(f"First Bucket Day: {buckets[0].get('day')}")
                    print(f"Last Bucket Day: {buckets[-1].get('day')}")

        ub = data.get("user_buckets", {})
        print(f"Total Users in Active Buckets: {len(ub)}")
    except FileNotFoundError:
        print(f"State file not found at {state_path}. Set {STATE_PATH_ENV} correctly or create {DEFAULT_STATE_PATH}.")
        return 1
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
