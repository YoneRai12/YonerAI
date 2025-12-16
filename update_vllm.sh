#!/bin/bash
echo "[ORA] Upgrading vLLM capabilities for RTX 5090..."

# Force upgrade pip first
python3 -m pip install --upgrade pip

# Force reinstall vLLM to get the absolute latest
# Using --pre (Pre-release) might be safer for 5090 in late 2025? 
# Or just standard upgrade. Let's try standard first, but with forceful reinstall.
python3 -m pip install --upgrade --force-reinstall vllm

echo "[ORA] Upgrade Complete. Checking version..."
python3 -m pip show vllm
