import os
import sys

# Set cache dir to L: drive BEFORE importing huggingface_hub
os.environ["HF_HOME"] = "L:\\ai_models\\huggingface"
os.environ["HUGGINGFACE_HUB_CACHE"] = "L:\\ai_models\\huggingface"

from huggingface_hub import snapshot_download

MODEL_ID = "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"

def download_model():
    print(f"Starting download for {MODEL_ID}...")
    print(f"Target Directory: {os.environ['HF_HOME']}")
    
    try:
        path = snapshot_download(
            repo_id=MODEL_ID,
            repo_type="model",
            resume_download=True
        )
        print(f"Successfully downloaded to: {path}")
    except Exception as e:
        print(f"Download failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_model()
