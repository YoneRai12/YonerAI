import json
from pathlib import Path

MEMORY_DIR = r"L:\ORA_Memory"
STATE_DIR = r"L:\ORA_State"

def debug_users():
    discord_state_path = Path(STATE_DIR) / "discord_state.json"
    discord_state = {"users": {}, "guilds": {}}
    if discord_state_path.exists():
        with open(discord_state_path, "r", encoding="utf-8") as f:
            discord_state = json.load(f)

    memory_path = Path(MEMORY_DIR) / "users"
    user_files = list(memory_path.glob("*.json"))
    
    print(f"Found {len(user_files)} user files.")
    
    for f in user_files[:10]:
        with open(f, "r", encoding="utf-8") as file:
            data = json.load(file)
            uid = f.stem
            real_id = data.get("discord_user_id", uid.split("_")[0])
            name = data.get("name", "Unknown")
            
            d_user = discord_state["users"].get(real_id, {})
            d_name = d_user.get("name")
            
            print(f"File: {f.name}")
            print(f"  UID: {uid}, RealID: {real_id}")
            print(f"  Name in File: {name}")
            print(f"  Name in DiscordState: {d_name}")
            print("-" * 20)

if __name__ == "__main__":
    debug_users()
