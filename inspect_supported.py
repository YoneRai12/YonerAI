import os

target_file = r"L:\ComfyUI\comfy\supported_models.py"

if not os.path.exists(target_file):
    print(f"Error: {target_file} not found.")
    exit(1)

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

print("--- Searching for Flux Configuration ---")
lines = content.split('\n')
for i, line in enumerate(lines):
    if "class Flux" in line or "class FLUX" in line:
        print(f"Line {i+1}: {line}")
        # Print context
        for j in range(1, 40):
             if i+j < len(lines):
                 print(f"Line {i+1+j}: {lines[i+j]}")
