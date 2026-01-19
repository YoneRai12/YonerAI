import datetime
import logging

from src.utils.cost_manager import Bucket, CostManager

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ORA.CostRepair")

def repair():
    logger.info("Starting Cost Repair...")
    cm = CostManager()
    
    repaired_count = 0
    total_added_usd = 0.0

    # Pricing for GPT-4o-mini (Optimization Lane)
    # IN: $0.15 / 1M = 0.00000015
    # OUT: $0.60 / 1M = 0.00000060
    PRICE_IN = 0.00000015
    PRICE_OUT = 0.00000060

    def fix_bucket(bucket, context_str):
        nonlocal repaired_count, total_added_usd
        
        # We only fix buckets that have tokens but NO cost
        if (bucket.used.tokens_in > 0 or bucket.used.tokens_out > 0) and bucket.used.usd == 0.0:
            # Calculate Estimated Cost
            est_usd = (bucket.used.tokens_in * PRICE_IN) + (bucket.used.tokens_out * PRICE_OUT)
            
            # Apply fix
            bucket.used.usd = est_usd
            
            repaired_count += 1
            total_added_usd += est_usd
            logger.info(f"Fixed {context_str}: {bucket.used.tokens_out} tokens -> ${est_usd:.6f}")

    # 1. Iterate User Buckets
    for uid, buckets in cm.user_buckets.items():
        for key, bucket in buckets.items():
            if "optimization:openai" in key:
                fix_bucket(bucket, f"User {uid} (Current)")

    # 2. Iterate User History
    for uid, hist_buckets in cm.user_history.items():
        for key, bucket_list in hist_buckets.items():
             if "optimization:openai" in key:
                 for i, bucket in enumerate(bucket_list):
                     fix_bucket(bucket, f"User {uid} (Hist #{i})")

    # 3. GLobal Sync (Aggregating User Opt to Global)
    # Because add_cost only updated User buckets previously, Global Opt is empty.
    # We must sum all User Opt usage and add it to Global Opt.
    global_opt_tokens_in = 0
    global_opt_tokens_out = 0
    global_opt_usd = 0.0

    # Calculate Total from User Buckets
    for uid, buckets in cm.user_buckets.items():
        for key, bucket in buckets.items():
            if "optimization:openai" in key:
                 global_opt_tokens_in += bucket.used.tokens_in
                 global_opt_tokens_out += bucket.used.tokens_out
                 global_opt_usd += bucket.used.usd

    # Update/Fix Global Current Bucket
    # We assume 'optimization:openai' is the key
    if global_opt_tokens_out > 0:
        # Find or create global bucket
        # We manually look for it or use the one we iterate below
        pass # The loop below iterates Global Buckets, we'll fix it there or inject it.
    
    # Actually, simpler: Just find the global 'optimization:openai' bucket and FORCE update its values to match the sum (or add to it?)
    # Since Global was likely 0, overwriting/adding is safer.
    
    global_bucket_key = "optimization:openai"
    # Ensure it exists
    if global_bucket_key not in cm.global_buckets:
        # Create dummy bucket if needed, but easier to let endpoints handle? 
        # No, we need it in state.
        # But wait, logic below fixes existing buckets.
        pass

    # Let's inject the sum into the Global Bucket logic
    # We will iterate global buckets. If optimization:openai exists, we check if it's 0. If so, fill it.
    
    # 3. Iterate Global Buckets (Just in case)
    found_global_opt = False
    for key, bucket in cm.global_buckets.items():
        if "optimization:openai" in key:
            found_global_opt = True
            if bucket.used.tokens_out == 0 and global_opt_tokens_out > 0:
                 bucket.used.tokens_in = global_opt_tokens_in
                 bucket.used.tokens_out = global_opt_tokens_out
                 bucket.used.usd = global_opt_usd
                 logger.info(f"Synced Global {key}: {global_opt_tokens_out} tokens -> ${global_opt_usd:.6f}")
            else:
                 # If it exists and has tokens, fix its cost if needed
                 fix_bucket(bucket, f"Global {key} (Current)")
            
    if not found_global_opt and global_opt_tokens_out > 0:
        # Create missing global bucket
        logger.info(f"Creating missing Global Bucket 'optimization:openai' with {global_opt_tokens_out} tokens, ${global_opt_usd:.6f}")
        
        # We need keys for the bucket (day/month). We can grab them from a user bucket or generic today.
        # Since we are repairing "current" state, assuming today is fine.
        day_key = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        month_key = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
        
        new_bucket = Bucket(day=day_key, month=month_key)
        new_bucket.used.tokens_in = global_opt_tokens_in
        new_bucket.used.tokens_out = global_opt_tokens_out
        new_bucket.used.usd = global_opt_usd
        new_bucket.last_update_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        cm.global_buckets["optimization:openai"] = new_bucket
        repaired_count += 1
        total_added_usd += global_opt_usd
        
    # 4. Iterate Global History

    # 4. Iterate Global History
    for key, bucket_list in cm.global_history.items():
        if "optimization:openai" in key:
             for i, bucket in enumerate(bucket_list):
                 fix_bucket(bucket, f"Global {key} (Hist #{i})")

    if repaired_count > 0:
        logger.info(f"Repair Complete. Fixed {repaired_count} buckets. Added Total: ${total_added_usd:.6f}")
        cm._save_state()
        logger.info("State saved successfully.")
    else:
        logger.info("No repair needed. All buckets with tokens already have cost.")

if __name__ == "__main__":
    repair()
