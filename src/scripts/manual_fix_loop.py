import json
from pathlib import Path

MEMORY_DIR = Path("L:/ORA_Memory/users")


def fix_loop():
    print(f"Scanning {MEMORY_DIR}...")
    if not MEMORY_DIR.exists():
        print("Memory dir not found.")
        return

    fixed = 0

    for f_path in MEMORY_DIR.glob("*.json"):
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            status = data.get("status", "New")
            uid = f_path.stem.split("_")[0]

            print(f"User {uid}: Status={status}")

            if status != "Optimized":
                print(f" -> FIXING {uid} (Status: {status} -> Optimized)")
                data["status"] = "Optimized"

                # Backup just in case
                with open(str(f_path) + ".bak", "w", encoding="utf-8") as bak:
                    json.dump(data, bak, indent=2, ensure_ascii=False)

                # Overwrite
                with open(f_path, "w", encoding="utf-8") as f_out:
                    json.dump(data, f_out, indent=2, ensure_ascii=False)

                fixed += 1
        except Exception as e:
            print(f"Error reading {f_path}: {e}")

    print(f"Scan Complete. Fixed {fixed} files.")


if __name__ == "__main__":
    fix_loop()
