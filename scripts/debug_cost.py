
import asyncio
import os
import sys

# Adjust path
sys.path.append(os.getcwd())

from src.utils.cost_manager import CostManager, Usage

def main():
    cm = CostManager()
    print("--- CostManager Diagnostic ---")
    print(f"Unlimited Mode: {cm.unlimited_mode}")
    print(f"Unlimited Users: {cm.unlimited_users}")
    print(f"Timezone: {cm.timezone}")
    
    # Check limit for 'stable' 'openai'
    lane = "stable"
    provider = "openai"
    
    # Global Bucket
    bucket = cm._get_or_create_bucket(lane, provider, None)
    print(f"\nBucket [{lane}:{provider}] (Global):")
    print(f"  Day: {bucket.day}")
    print(f"  Used: {bucket.used}")
    print(f"  Reserved: {bucket.reserved}")
    print(f"  Hard Stopped: {bucket.hard_stopped}")
    
    # Check Logic
    est = Usage(tokens_in=100, tokens_out=0, usd=0.0)
    decision = cm.can_call(lane, provider, None, est)
    print(f"\nCan Call (Global, 100 tokens)? -> {decision}")
    
    # Check a dummy user ID if needed (or user from context if we knew it)
    # Assuming user ID from previous logs? YoneRai12 is the username.
    # We don't know the exact Discord ID easily without logs, but let's check keys in user_buckets
    print(f"\nUser Buckets Keys: {list(cm.user_buckets.keys())}")
    
    for uid in cm.user_buckets:
        u_bucket = cm.user_buckets[uid].get(f"{lane}:{provider}")
        if u_bucket:
            print(f"\nBucket [{lane}:{provider}] (User {uid}):")
            print(f"  Used: {u_bucket.used}")
            decision_u = cm.can_call(lane, provider, int(uid), est)
            print(f"  Can Call? -> {decision_u}")

if __name__ == "__main__":
    main()
