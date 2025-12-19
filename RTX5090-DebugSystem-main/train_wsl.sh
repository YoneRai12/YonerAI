#!/bin/bash
set -e

# Configuration
PYTHON_VER="3.10" # Default useful for ML
PROJECT_DIR="/mnt/c/Users/YoneRai12/Desktop/ORADiscordBOT-main3/RTX5090-DebugSystem-main"

echo "=== WSL Training Setup ==="
echo "Target Directory: $PROJECT_DIR"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Cannot find project directory in WSL at $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# 1. System Dependencies (if not present)
echo "Update Apt & Install Python generic deps..."
sudo apt-get update && sudo apt-get install -y python3-pip python3-venv git build-essential

# 2. Virtual Environment
echo "Setting up Virtual Environment (.venv_wsl)..."
if [ ! -d ".venv_wsl" ]; then
    python3 -m venv .venv_wsl
fi
source .venv_wsl/bin/activate

# 3. Upgrade Pip
pip install --upgrade pip

# 4. Install Torch (Linux specific for CUDA 12.8 / RTX 5090)
# RTX 5090 requires CUDA 12.8+ kernels only found in Nightly builds
echo "Installing PyTorch Nightly for Linux (CUDA 12.8)..."
pip uninstall -y torch torchvision torchaudio
pip install --pre --upgrade --force-reinstall --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

# Verify Support
python3 -c "import torch; print(f'Torch: {torch.__version__}'); print(f'CUDA: {torch.version.cuda}'); print(f'Archs: {torch.cuda.get_arch_list()}')"

# 5. Install Other Dependencies
echo "Installing Training Libraries (transformers, peft, trl, bitsandbytes)..."
# Ministral 3 requires latest transformers/peft for correct Tokenizer handling
pip install git+https://github.com/huggingface/transformers git+https://github.com/huggingface/peft trl bitsandbytes datasets accelerate ninja packaging mistral_common tiktoken

# 6. Install Triton (Linux Native)
echo "Installing Triton (Native)..."
pip install triton
python3 -m pip install python-dotenv

# 7. Login to Hugging Face (Check if token exists)
# We assume user might need to log in, but we can try sharing the token or asking.
# For automation, if they have Windows token, it doesn't cross over easily.
# We will use the HF_TOKEN env var if passed, or ask user to login.
if [ -z "$HF_TOKEN" ]; then
    echo "Checking for cached credentials..."
    if ! huggingface-cli whoami > /dev/null 2>&1; then
        echo "Please login to Hugging Face:"
        pip install huggingface_hub
        huggingface-cli login
    fi
fi

# 8. Run Training
echo "=== STARTING TRAINING (Linux/WSL) ==="
# Force Python to unbuffer output
# Force Python to unbuffer output
export PYTHONUNBUFFERED=1
python3 train_wrapper.py python3 train_lora.py

echo "=== Training Complete (WSL) ==="
