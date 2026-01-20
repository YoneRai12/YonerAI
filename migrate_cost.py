
import json
import os
import shutil
from datetime import datetime

STATE_FILE = r"L:\ORA_State\cost_state.json"
BACKUP_FILE = r"L:\ORA_State\cost_state.json.bak"

def migrate_tokens():
    if not os.path.exists(STATE_FILE):
        print(f"Error: {STATE_FILE} not found.")
        return

    # 1. Create Backup
    try:
        shutil.copy2(STATE_FILE, BACKUP_FILE)
        print(f"Backup created at {BACKUP_FILE}")
    except Exception as e:
        print(f"Backup failed: {e}")
        return

    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    total_moved = 0
    target_date = "2026-01-20"
    
    print(f"--- Migrating Stable Usage to Optimization for {target_date} ---")

    # Global Buckets Adjustment (Optional, but good for consistency)
    # Note: Global buckets are just aggregations. Usually derived from users but cost_manager maintains them separately.
    # We should move global bucket counts too.
    if "global_buckets" in data:
        stable_global = data["global_buckets"].get("stable:openai", {})
        opt_global = data["global_buckets"].get("optimization:openai", {})
        
        # Ensure Opt Bucket exists for today
        if not opt_global or opt_global.get("day") != target_date:
             data["global_buckets"]["optimization:openai"] = {
                 "day": target_date,
                 "month": target_date[:7],
                 "used": {"tokens_in": 0, "tokens_out": 0, "usd": 0.0},
                 "reserved": {"tokens_in": 0, "tokens_out": 0, "usd": 0.0},
                 "hard_stopped": False,
                 "last_update_iso": datetime.utcnow().isoformat()
             }
             opt_global = data["global_buckets"]["optimization:openai"]

        if stable_global.get("day") == target_date:
            s_used = stable_global.get("used", {})
            o_used = opt_global.get("used", {})
            
            # Transfer
            o_used["tokens_in"] = o_used.get("tokens_in", 0) + s_used.get("tokens_in", 0)
            o_used["tokens_out"] = o_used.get("tokens_out", 0) + s_used.get("tokens_out", 0)
            o_used["usd"] = o_used.get("usd", 0.0) + s_used.get("usd", 0.0)
            
            # Reset Stable
            s_used["tokens_in"] = 0
            s_used["tokens_out"] = 0
            s_used["usd"] = 0.0
            
            print("Migrated Global Bucket.")

    # User Buckets
    if "user_buckets" in data:
        for uid, buckets in data["user_buckets"].items():
            stable = buckets.get("stable:openai", {})
            
            # Only migrate if Stable has usage TODAY
            if stable.get("day") == target_date:
                s_usage = stable.get("used", {})
                tokens = s_usage.get("tokens_in", 0) + s_usage.get("tokens_out", 0)
                
                if tokens > 0:
                    # Get or Create Opt Bucket
                    opt = buckets.get("optimization:openai")
                    if not opt or opt.get("day") != target_date:
                        buckets["optimization:openai"] = {
                             "day": target_date,
                             "month": target_date[:7],
                             "used": {"tokens_in": 0, "tokens_out": 0, "usd": 0.0},
                             "reserved": {"tokens_in": 0, "tokens_out": 0, "usd": 0.0},
                             "hard_stopped": False,
                             "last_update_iso": datetime.utcnow().isoformat()
                        }
                        opt = buckets["optimization:openai"]
                    
                    o_usage = opt.get("used", {})
                    
                    # Transfer values
                    o_usage["tokens_in"] = o_usage.get("tokens_in", 0) + s_usage.get("tokens_in", 0)
                    o_usage["tokens_out"] = o_usage.get("tokens_out", 0) + s_usage.get("tokens_out", 0)
                    o_usage["usd"] = o_usage.get("usd", 0.0) + s_usage.get("usd", 0.0)
                    
                    total_moved += tokens
                    
                    # Reset Stable
                    s_usage["tokens_in"] = 0
                    s_usage["tokens_out"] = 0
                    s_usage["usd"] = 0.0

    print("-" * 30)
    print(f"Values Updated. Total Tokens Moved: {total_moved}")
    
    # Save
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print("Successfully saved cost_state.json")
    except Exception as e:
        print(f"Error saving JSON: {e}")
        # Restore backup?
        shutil.copy2(BACKUP_FILE, STATE_FILE)
        print("Restored backup due to save error.")

if __name__ == "__main__":
    migrate_tokens()
