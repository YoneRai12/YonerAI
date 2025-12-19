#!/bin/bash
# Enable error handling
set -e

# Resolve directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Testing Discord Webhook via WSL Venv ==="

# 1. Activate Virtual Environment
if [ -d ".venv_wsl" ]; then
    echo "Activating .venv_wsl..."
    source .venv_wsl/bin/activate
else
    echo "Error: .venv_wsl not found! Run train_wsl.sh first."
    exit 1
fi

# 2. Run Test
echo "Running test_discord.py..."
python3 test_discord.py

echo "=== Test Complete ==="
