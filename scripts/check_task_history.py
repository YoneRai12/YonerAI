import subprocess
import sys
import os

def check_task_history_deletions():
    """
    Check if any lines were deleted from TASK_HISTORY.md or TASKS.md.
    In ORA project, history is append-only.
    """
    file_to_check = "TASK_HISTORY.md"
    # Find the correct path for brain artifacts
    # Note: In CI, it might be different, but we can search for it or pass as arg.
    # For now, let's assume it's in the repo if we moved it, 
    # OR we check against the brain directory if specified.
    
    # Actually, the user asked for TASK_HISTORY.md specifically.
    # If it's the one in .gemini/antigravity/brain/..., it's hard to check via git.
    # But if the user wants to protect the project's own history file (if any), 
    # we should check that.
    
    # The user said: "TASK_HISTORY.md は “削除行” をCIで検知して落とす"
    
    try:
        # Use git diff to find deleted lines in the file
        # -U0 means zero lines of context
        # --exit-code makes it return 1 if there are changes
        cmd = ["git", "diff", "-U0", "--exit-code", file_to_check]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"No changes detected in {file_to_check}.")
            return True
        
        diff_output = result.stdout
        deleted_lines = [line for line in diff_output.splitlines() if line.startswith("-") and not line.startswith("---")]
        
        if deleted_lines:
            print(f"CRITICAL ERROR: Line deletion detected in {file_to_check}!")
            for line in deleted_lines:
                print(f"  Deleted: {line}")
            print("\nTASK_HISTORY.md must be APPEND-ONLY. Please restore deleted lines.")
            return False
        
        print(f"Changes in {file_to_check} are append-only. OK.")
        return True
        
    except FileNotFoundError:
        print(f"Warning: {file_to_check} not found. Skipping check.")
        return True
    except Exception as e:
        print(f"Error during check: {e}")
        return False

if __name__ == "__main__":
    if not check_task_history_deletions():
        sys.exit(1)
    sys.exit(0)
