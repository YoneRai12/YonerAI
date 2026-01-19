import os

from huggingface_hub import snapshot_download

model_id = "Aratako/T5Gemma-TTS-2b-2b"
local_dir = r"L:\ai_models\huggingface\Aratako_T5Gemma-TTS-2b-2b"

print(f"Downloading {model_id} to {local_dir}...")
print("This may take a while (~2GB)...")

try:
    os.makedirs(local_dir, exist_ok=True)
    snapshot_download(repo_id=model_id, local_dir=local_dir, local_dir_use_symlinks=False, resume_download=True)
    print("✅ Download Complete! Please restart the bot to enable T5 TTS.")
except Exception as e:
    print(f"❌ Download Failed: {e}")
    print("Note: If this model is gated (requires agreement), you must log in first:")
    print("      Run `huggingface-cli login` in your terminal.")
