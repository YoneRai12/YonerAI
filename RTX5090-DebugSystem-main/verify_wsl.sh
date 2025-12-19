#!/bin/bash
set -e

echo "=== Robust Verification Setup ==="

# Check if current venv works
if [ -d ".venv_wsl" ] && [ -f ".venv_wsl/bin/python3" ]; then
    echo "Checking existing venv..."
    if ./.venv_wsl/bin/python3 -c "import torch" &> /dev/null; then
        echo "Existing venv is good!"
        ./.venv_wsl/bin/python3 verify_model.py
        exit 0
    fi
    echo "Existing venv is corrupted/mismatched. Rebuilding for verification..."
    rm -rf .venv_wsl
fi

echo "Creating new venv..."
python3 -m venv .venv_wsl
source .venv_wsl/bin/activate

echo "Installing minimal dependencies..."
# Use pip cache to speed up (files already downloaded during training)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
pip install transformers peft bitsandbytes accelerate
pip install python-dotenv

echo "Running Verification..."
python3 verify_model.py
