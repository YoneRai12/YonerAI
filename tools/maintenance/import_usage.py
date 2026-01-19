import json
import os

STATE_DIR = r"L:\ORA_State"
STATE_FILE = os.path.join(STATE_DIR, "cost_state.json")

def create_import_data():
    if not os.path.exists(STATE_DIR):
        print(f"Error: Directory {STATE_DIR} does not exist.")
        return

    # Structure to match Bucket dataclass
    # 263,985 tokens
    imported_bucket = {
        "day": "2024-12-24", # Yesterday/Past
        "month": "2024-12",
        "used": {
            "tokens_in": 200000,   # Rough split
            "tokens_out": 63985,
            "usd": 0.0 # Assuming free tier or prepaid for now, or unknown
        },
        "reserved": {
            "tokens_in": 0,
            "tokens_out": 0,
            "usd": 0.0
        },
        "hard_stopped": False,
        "last_update_iso": "2024-12-25T00:00:00"
    }
    
    # Target Key
    # Assuming this was mostly 'stable' usage since it's "Usage" in general
    target_key = "stable:openai"

    data = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading existing file: {e}")
            return

    # Ensure History Structure
    if "global_history" not in data:
        data["global_history"] = {}
    
    if target_key not in data["global_history"]:
        data["global_history"][target_key] = []
        
    # Check if already imported (Simple check: total sum)
    current_history = data["global_history"][target_key]
    already_has_import = any(b["day"] == "2024-12-24" for b in current_history)
    
    if already_has_import:
        print("Import seems to have run already (Found 2024-12-24 bucket). Skipping.")
    else:
        current_history.append(imported_bucket)
        print(f"Injected 263,985 tokens into history for {target_key}")

    # Save
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("State saved successfully.")

if __name__ == "__main__":
    create_import_data()
