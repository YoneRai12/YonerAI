import os
import platform


def install_hook():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hooks_dir = os.path.join(repo_root, ".git", "hooks")
    hook_file = os.path.join(hooks_dir, "pre-commit")

    if not os.path.exists(hooks_dir):
        print("❌ Error: Not a git repository or .git/hooks directory missing.")
        return

    # Hook content
    # Note: On Windows, we use python explicitly.
    hook_content = f"""#!/bin/sh
python "{os.path.join(repo_root, "scripts", "git_pre_commit.py")}"
"""

    try:
        with open(hook_file, "w", encoding="utf-8") as f:
            f.write(hook_content)

        # Make executable (won't affect Windows much but good practice)
        if platform.system() != "Windows":
            os.chmod(hook_file, 0o755)

        print(f"✅ ORA Git Security Hook installed to {hook_file}")
    except Exception as e:
        print(f"❌ Failed to install hook: {e}")


if __name__ == "__main__":
    install_hook()
