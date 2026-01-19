
import os

from huggingface_hub import snapshot_download

# Define target directory
BASE_PATH = r"L:\AI_Models\T5Gemma"
VISUAL_PATH = os.path.join(BASE_PATH, "VisualCortex_4B")
VOICE_PATH = os.path.join(BASE_PATH, "VoiceEngine_2B")

def download_model(repo_id, local_dir):
    print(f"Starting download for {repo_id}...")
    print(f"Target: {local_dir}")
    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            resume_download=True
        )
        print(f"Successfully downloaded {repo_id}!")
    except Exception as e:
        print(f"Error downloading {repo_id}: {e}")
        print("Note: If this is a gated model (like google/t5gemma-2-4b-4b), verify you are logged in via 'huggingface-cli login'.")

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs(VISUAL_PATH, exist_ok=True)
    os.makedirs(VOICE_PATH, exist_ok=True)

    # 1. Visual Cortex: T5Gemma 2 4B
    # Note: Requires acceptance of Google's license on HF
    download_model("google/t5gemma-2-4b-4b", VISUAL_PATH)

    # 2. Voice Engine: Aratako T5Gemma-TTS
    download_model("Aratako/T5Gemma-TTS-2b-2b", VOICE_PATH)

    print("Download process completed.")
