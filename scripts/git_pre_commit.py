import sys
import os
import subprocess

# Config
MAX_FILE_SIZE_MB = 5
FORBIDDEN_EXTENSIONS = {'.zip', '.db', '.bak', '.log', '.tmp'}
FORBIDDEN_FILES = {'.env', 'ora_bot.db', 'log.txt'}

def get_staged_files():
    """Get list of files staged for commit."""
    try:
        output = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True)
        return output.splitlines()
    except subprocess.CalledProcessError:
        return []

def check_files():
    staged_files = get_staged_files()
    violations = []

    for file_path in staged_files:
        if not os.path.exists(file_path):
            continue

        # 1. Check File Size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            violations.append(f"❌ [TOO LARGE] {file_path} ({file_size_mb:.2f}MB > {MAX_FILE_SIZE_MB}MB)")

        # 2. Check Forbidden Extensions
        ext = os.path.splitext(file_path)[1].lower()
        if ext in FORBIDDEN_EXTENSIONS:
            violations.append(f"❌ [FORBIDDEN EXTENSION] {file_path}")

        # 3. Check Forbidden Filenames
        if os.path.basename(file_path) in FORBIDDEN_FILES:
            violations.append(f"❌ [FORBIDDEN FILE] {file_path}")

    if violations:
        print("\n" + "!" * 50)
        print("GIT COMMIT BLOCKED BY ORA SECURITY GUARD")
        print("!" * 50)
        for v in violations:
            print(v)
        print("\nReason: Found large files or sensitive data.")
        print("Action: Remove these files from staging using 'git reset <file>'")
        print("!" * 50 + "\n")
        sys.exit(1)

if __name__ == "__main__":
    check_files()
    sys.exit(0)
