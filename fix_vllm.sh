#!/bin/bash
set -e
echo "Fixing Dependency Conflict..."
echo "Downgrading huggingface-hub to <1.0 to satisfy transformers..."
pip3 install "huggingface-hub<1.0"
echo "Done. Please try running start_vllm.bat again."
