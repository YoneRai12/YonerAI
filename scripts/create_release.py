import subprocess
import sys
from pathlib import Path

def create_release_zip(version):
    repo_root = Path(__file__).parent.parent
    zip_name = f"ORA-{version}.zip"
    output_path = repo_root / zip_name
    
    print(f"Creating release archive for version {version}...")
    
    try:
        # Use git archive to create a clean zip of tracked files only
        # This automatically excludes .env, .venv, logs, etc. if they are not tracked.
        subprocess.run(
            ["git", "archive", "--format=zip", "--output", str(output_path), "HEAD"],
            check=True,
            cwd=str(repo_root)
        )
        print(f"✅ Created: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create archive: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Read from VERSION file if not provided
        version_file = Path(__file__).parent.parent / "VERSION"
        if version_file.exists():
            version = version_file.read_text().strip()
        else:
            print("Usage: python create_release.py <version>")
            sys.exit(1)
    else:
        version = sys.argv[1]
        
    if create_release_zip(version):
        sys.exit(0)
    else:
        sys.exit(1)
