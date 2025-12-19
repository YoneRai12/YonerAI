#!/usr/bin/env python3
import os
import sys
import shlex
from dotenv import load_dotenv
from phoenix_cli_manager import Config, Monitor

def main():
    """
    Wrapper for training commands with Auto-Healing and Notification.
    """
    # 0. Load Env
    load_dotenv()

    # 1. Determine Command
    args = sys.argv[1:]
    if not args:
        # Default behavior: Run Python script if no args
        args = ["python3", "train_lora.py"]
    
    # Update environment with command for Config to pick up
    os.environ["PHOENIX_TRAIN_CMD"] = " ".join(shlex.quote(a) for a in args)

    print(f"[train_wrapper] Initializing Auto-Healing Monitor for: {os.environ['PHOENIX_TRAIN_CMD']}")
    
    # 2. Config & Monitor
    cfg = Config()
    monitor = Monitor(cfg)
    
    # 3. Run
    sys.exit(monitor.run())

if __name__ == "__main__":
    main()
