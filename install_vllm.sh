#!/bin/bash
set -e

echo "Updating apt..."
sudo apt-get update

echo "Installing Python dependencies..."
sudo apt-get install -y python3-pip python3-dev git

echo "Installing vLLM (This may take a while)..."
pip3 install vllm

echo "Installing HuggingFace CLI..."
pip3 install -U "huggingface_hub[cli]"

echo "Setup Complete."
