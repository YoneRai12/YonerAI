import subprocess
import sys


def _repo_root() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def check_task_history_deletions() -> bool:
    """Keep the legacy task-history tombstone append-only if it is changed."""
    file_to_check = "docs/legacy/FULL_TASK_HISTORY.md"

    try:
        result = subprocess.run(
            ["git", "diff", "-U0", "--exit-code", "--", file_to_check],
            capture_output=True,
            text=True,
            cwd=_repo_root(),
        )

        if result.returncode == 0:
            print(f"No changes detected in {file_to_check}.")
            return True

        diff_output = result.stdout
        deleted_lines = [
            line
            for line in diff_output.splitlines()
            if line.startswith("-") and not line.startswith("---")
        ]

        if deleted_lines:
            print(f"CRITICAL ERROR: Line deletion detected in {file_to_check}!")
            for line in deleted_lines:
                print(f"  Deleted: {line}")
            print("\nTask history must be append-only. Restore deleted lines.")
            return False

        print(f"Changes in {file_to_check} are append-only. OK.")
        return True

    except FileNotFoundError:
        print(f"Warning: {file_to_check} not found. Skipping check.")
        return True
    except Exception as exc:
        print(f"Error during check: {exc}")
        return False


if __name__ == "__main__":
    if not check_task_history_deletions():
        sys.exit(1)
    sys.exit(0)
