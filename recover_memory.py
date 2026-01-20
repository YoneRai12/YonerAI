
import os
import shutil
import re

MEMORY_DIR = r"L:\ORA_Memory"
USER_MEMORY_DIR = os.path.join(MEMORY_DIR, "users")

def move_scattered_files():
    if not os.path.exists(USER_MEMORY_DIR):
        os.makedirs(USER_MEMORY_DIR, exist_ok=True)

    print(f"Scanning {MEMORY_DIR} for scattered user files...")
    
    count = 0
    moved = 0
    
    # Simple regex for user files: Starts with digits, ends with .json
    # Examples: 123.json, 123_456_public.json
    pattern = re.compile(r"^\d+.*\.json$")

    for filename in os.listdir(MEMORY_DIR):
        src_path = os.path.join(MEMORY_DIR, filename)
        
        # Skip directories
        if os.path.isdir(src_path):
            continue
            
        # Check filename pattern
        if pattern.match(filename):
            dst_path = os.path.join(USER_MEMORY_DIR, filename)
            
            try:
                # Use os.replace for atomic overwrite on same drive
                os.replace(src_path, dst_path)
                print(f"Moved: {filename}")
                moved += 1
            except Exception as e:
                print(f"Failed to move {filename}: {e}")
                
            count += 1

    print("-" * 30)
    print(f"Total potential user files found: {count}")
    print(f"Successfully moved to 'users/': {moved}")

if __name__ == "__main__":
    move_scattered_files()
