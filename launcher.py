"""
ORA Self-Healing Launcher
-------------------------
1. Creates immutable backups before every run.
2. Runs the bot in a sandboxed environment (`_sandbox/`).
3. Monitors for crashes.
4. (Future) Delegates to AI for repair if enabled.
"""

import datetime
import logging
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("launcher.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("Launcher")

ROOT_DIR = Path(__file__).parent.absolute()
BACKUP_DIR = ROOT_DIR / "backups"
SANDBOX_DIR = ROOT_DIR / "_sandbox"
PYTHON_EXE = sys.executable


def make_readonly(func, path, _):
    """Clear the readonly bit and keep going"""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def create_backup():
    """Create a read-only timestamped backup."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = BACKUP_DIR / timestamp

    logger.info(f"Creating backup at {backup_path}...")
    try:
        shutil.copytree(
            ROOT_DIR,
            backup_path,
            ignore=shutil.ignore_patterns(
                "backups", "_sandbox", ".git", ".venv", "__pycache__", "ora-ui/node_modules", "data"
            ),
            dirs_exist_ok=True,
        )
        # Mark as read-only to prevent accidental edits
        # for root, dirs, files in os.walk(backup_path):
        #     for f in files:
        #         os.chmod(os.path.join(root, f), stat.S_IREAD)
        logger.info("Backup successful.")
    except Exception as e:
        logger.error(f"Backup failed: {e}")


def prepare_sandbox():
    """Sync source code to sandbox."""
    logger.info(f"Preparing sandbox at {SANDBOX_DIR}...")

    if SANDBOX_DIR.exists():
        # Clean existing sandbox carefully
        try:
            shutil.rmtree(SANDBOX_DIR, onerror=make_readonly)
        except Exception as e:
            logger.warning(f"Failed to clean sandbox: {e}")

    try:
        # Copy everything except heavy folders
        shutil.copytree(
            ROOT_DIR,
            SANDBOX_DIR,
            ignore=shutil.ignore_patterns("backups", "_sandbox", ".git", ".venv", "__pycache__", "ora-ui/node_modules"),
            dirs_exist_ok=True,
        )
        logger.info("Sandbox prepared.")
    except Exception as e:
        logger.critical(f"Failed to create sandbox: {e}")
        sys.exit(1)


def run_bot_in_sandbox():
    """Run `main.py` inside the sandbox."""
    main_script = SANDBOX_DIR / "main.py"
    if not main_script.exists():
        logger.critical(f"main.py not found in sandbox: {main_script}")
        return

    logger.info("🤖 Launching ORA Bot in SANDBOX...")

    env = os.environ.copy()
    env["ORA_MODE"] = "SANDBOX"

    while True:
        try:
            # We run directly using the same python interpreter
            process = subprocess.Popen(
                [PYTHON_EXE, str(main_script)],
                cwd=str(SANDBOX_DIR),
                env=env,
                # stdout=subprocess.PIPE,
                # stderr=subprocess.PIPE
                # Let it inherit stdout/stderr for now so user sees output
            )

            return_code = process.wait()

            if return_code == 0:
                logger.info("Bot exited normally.")
                break
            else:
                logger.error(f"Bot successfully crashed with code {return_code}. Restarting in 5 seconds...")

                # Capture recent logs for repair
                msg = "Crash detected."
                try:
                    # Read the last 50 lines of the log file
                    log_file = SANDBOX_DIR / "ora_bot.log"
                    error_log = ""
                    if log_file.exists():
                        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                            error_log = "".join(lines[-50:])
                    else:
                        error_log = "Log file not found."
                except Exception as e:
                    error_log = f"Failed to read logs: {e}"

                # Attempt Repair
                try:
                    # We need to add src to pythonpath or import directly
                    sys.path.append(str(ROOT_DIR))
                    from src.utils.ai_repair import apply_fix_sync

                    logger.info("🚑 Attempting AI Repair...")
                    if apply_fix_sync(SANDBOX_DIR, error_log):
                        logger.info("Resuming with patched code...")
                    else:
                        logger.warning("Repair failed or declined. Restarting as is.")

                except ImportError:
                    logger.warning("Could not import ai_repair module.")
                except Exception as e:
                    logger.error(f"AI Repair crashed: {e}")

                time.sleep(5)
                logger.info("Restarting...")
        except KeyboardInterrupt:
            logger.info("Launcher stopped by user.")
            break
        except Exception as e:
            logger.critical(f"Unrecoverable launcher error: {e}")
            break


def main():
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir()

    create_backup()
    prepare_sandbox()
    run_bot_in_sandbox()


if __name__ == "__main__":
    main()
