#!/bin/bash
echo "[ORA] Repairing vLLM Installation..."

# 1. Clean pip cache just in case
python3 -m pip cache purge

# 2. Install vLLM specifically
# Using --no-cache-dir to avoid corrupted cache files
python3 -m pip install vllm --no-cache-dir

# 3. Verify
echo "[ORA] Verification:"
python3 -m pip show vllm
