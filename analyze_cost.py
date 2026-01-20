
import json
import os
from datetime import datetime

STATE_FILE = r"L:\ORA_State\cost_state.json"

def analyze_and_simulate_migration():
    if not os.path.exists(STATE_FILE):
        print(f"Error: {STATE_FILE} not found.")
        return

    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    total_stable_tokens = 0
    total_optimization_tokens_before = 0
    migration_count = 0
    
    # Target date: Use system date or infer from data? 
    # Dashboard implies today is 2026-01-20.
    target_date = "2026-01-20"
    
    print(f"--- Analyzing Stable Usage for {target_date} ---")

    # Check Global Buckets
    if "global_buckets" in data:
        stable_global = data["global_buckets"].get("stable:openai", {})
        if stable_global.get("day") == target_date:
            usage = stable_global.get("used", {})
            tokens = usage.get("tokens_in", 0) + usage.get("tokens_out", 0)
            print(f"Global Stable: {tokens}")
            total_stable_tokens += tokens

    # Check User Buckets
    if "user_buckets" in data:
        for uid, buckets in data["user_buckets"].items():
            # Check Stable
            stable = buckets.get("stable:openai", {})
            if stable.get("day") == target_date:
                usage = stable.get("used", {})
                tokens = usage.get("tokens_in", 0) + usage.get("tokens_out", 0)
                if tokens > 0:
                    print(f"User {uid}: Stable Usage = {tokens}")
                    total_stable_tokens += tokens
                    migration_count += 1
            
            # Check Optimization (for reference)
            opt = buckets.get("optimization:openai", {})
            if opt.get("day") == target_date:
                usage = opt.get("used", {})
                tokens = usage.get("tokens_in", 0) + usage.get("tokens_out", 0)
                total_optimization_tokens_before += tokens

    print("-" * 30)
    print(f"Total Stable Usage Found: {total_stable_tokens}")
    print(f"Total Optimization Usage Before: {total_optimization_tokens_before}")
    print(f"Users with Stable Usage: {migration_count}")
    print("-" * 30)
    print("Simulating Migration...")
    print(f"New Optimization Total would be: {total_stable_tokens + total_optimization_tokens_before}")

if __name__ == "__main__":
    analyze_and_simulate_migration()
