
import os

PATHS = [
    r"L:\AI_Models\T5Gemma\VisualCortex_4B",
    r"L:\AI_Models\T5Gemma\VoiceEngine_2B"
]

def list_files(path):
    print(f"\nScanning: {path}")
    if not os.path.exists(path):
        print("Path does not exist!")
        return
    
    files = os.listdir(path)
    if not files:
        print("Directory is empty.")
    
    total_size = 0
    for f in files:
        fp = os.path.join(path, f)
        if os.path.isfile(fp):
            size = os.path.getsize(fp)
            total_size += size
            print(f"- {f}: {size / 1024 / 1024:.2f} MB")
    
    print(f"Total Size: {total_size / 1024 / 1024 / 1024:.2f} GB")

if __name__ == "__main__":
    for p in PATHS:
        list_files(p)
