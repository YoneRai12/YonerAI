import json
from pathlib import Path

MEMORY_DIR = Path("L:/ORA_Memory/users")

def repair():
    if not MEMORY_DIR.exists():
        print("Memory directory not found.")
        return

    count = 0
    for file in MEMORY_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            status = data.get("status")
            traits = data.get("traits", [])
            
            # If status is "Optimized" but there are NO traits, it's a false positive.
            if status == "Optimized" and len(traits) == 0:
                print(f"Repairing {file.name}: Optimized -> New")
                data["status"] = "New"
                with open(file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                count += 1
        except Exception as e:
            print(f"Error processing {file.name}: {e}")

    print(f"Finished. Repaired {count} users.")

if __name__ == "__main__":
    repair()
